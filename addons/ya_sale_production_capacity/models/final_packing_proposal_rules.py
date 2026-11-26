"""Pure review-only candidate validation for Final Packing Design B.

No database writes, no allocation algorithm or recipient ranking.
A human or external tool may propose quantities. This is not authorization:
stock is an upper bound, cross-slot claims are unresolved, and no native
reservations/assembly/DO are created. SO Paket provenance remains a gate.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json


class ProposalError(ValueError):
    pass


def check(ok, message):
    if not ok:
        raise ProposalError(message)


def number(value):
    check(not isinstance(value, bool) and isinstance(value, (int, float)),
          "Quantity must be numeric")
    try:
        n = Decimal(str(value))
    except InvalidOperation as exc:
        raise ProposalError("Invalid quantity") from exc
    check(n.is_finite() and n >= 0, "Quantity must be finite and nonnegative")
    return n


def integer(value):
    check(type(value) is int and value >= 0, "Allocation must be a whole nonnegative integer")
    return value


def key(row):
    return tuple(row[k] for k in ("kind","source_id","line_id","recipient_id","product_id"))


def source_digest(demand):
    return sha256(json.dumps(demand, sort_keys=True, separators=(",", ":"),
                              allow_nan=False).encode()).hexdigest()


def build_proposal_template(demand):
    """Return fixed identities and blank quantity slots, not recommendations."""
    supply = demand["supply"]
    return {
        "batch_id": supply["batch_id"],
        "delivery_date": supply["delivery_date"], "slot": supply["slot"],
        "source_digest": source_digest(demand),
        "rows": [dict(kind=r["kind"], source_id=r["source_id"],
                      line_id=r["line_id"], recipient_id=r["recipient_id"],
                      product_id=r["product_id"], qty_allocated=None)
                 for r in demand["recipient_rows"]],
    }


def validate_proposal(demand, proposal):
    template = build_proposal_template(demand)
    check(set(proposal) == set(template), "Unexpected proposal fields")
    for k in ("batch_id", "delivery_date", "slot", "source_digest"):
        check(type(proposal[k]) is type(template[k]) and proposal[k] == template[k],
              "Stale or changed fixed field: "+k)
    check(not demand["so_paket_confirmation_provenance_missing"],
          "SO Paket confirmation provenance missing; review required")
    rows = demand["recipient_rows"]
    original = {key(r):r for r in rows}
    check(len(original)==len(rows), "Duplicate source recipient line")
    proposals = {}
    expected_fields = {"kind","source_id","line_id","recipient_id","product_id","qty_allocated"}
    for r in proposal["rows"]:
        check(set(r)==expected_fields, "Unexpected proposal row fields")
        check(type(r["kind"]) is str and all(type(r[f]) is int for f in
              ("source_id","line_id","recipient_id","product_id")), "Invalid row identity type")
        k = key(r)
        check(k in original and k not in proposals, "Unknown or duplicate recipient row")
        proposals[k] = integer(r["qty_allocated"])
    check(set(proposals)==set(original), "Missing recipient row; use explicit zero")

    available = {}
    for r in demand["supply"]["rows"]:
        k = ("KITCHEN", r["product_id"])
        check(k not in available, "Duplicate kitchen supply")
        available[k] = number(r["slot_supply_upper_bound"])
        if "claim_preview_cap" in r:
            available[k] = min(available[k],number(r["claim_preview_cap"]))
    for r in demand["pck_component_rows"]:
        k = ("PCK", r["product_id"])
        check(k not in available and ("KITCHEN", r["product_id"]) not in available,
              "Duplicate/ambiguous component supply")
        # Tracked stock cannot be claimed by this untracked-stock preview.
        available[k] = number(r["free"]) if r["tracking"]=="none" else Decimal(0)
        if "claim_preview_cap" in r:
            available[k] = min(available[k],number(r["claim_preview_cap"]))

    total = defaultdict(Decimal)
    ordinary = defaultdict(Decimal)
    parts_by_key = {}
    result = []
    for k,r in original.items():
        requested = integer(r["qty"])
        check(requested>0, "Invalid original demand")
        qty = proposals[k]
        check(r["kind"] in ("SO","SO_PAKET","RO_PAKET","RO"), "Unknown demand class")
        check(qty<=requested, "Allocation exceeds original demand")
        if r["kind"] in ("SO","SO_PAKET"):
            check(qty==requested, "Confirmed SO cannot be partially allocated")
        parts = {}
        for c in r["components"]:
            ck = (c["source_kind"],c["product_id"])
            check(ck in available and ck not in parts, "Missing/duplicate component supply")
            ratio = number(c.get("qty_per_package",1))
            check(ratio>0 and abs(ratio*requested-number(c["qty"]))<=Decimal("0.000000001"),
                  "Inconsistent component requirement")
            if ck[0]=="KITCHEN":
                check(ratio==ratio.to_integral_value(), "Fractional kitchen finished-goods ratio")
            parts[ck] = ratio
            total[ck] += ratio*qty
            if r["kind"]=="RO":
                ordinary[ck] += ratio*qty
        check(bool(parts), "Empty component list")
        parts_by_key[k] = parts
        result.append(dict(kind=r["kind"],source_id=r["source_id"],line_id=r["line_id"],
                           recipient_id=r["recipient_id"],product_id=r["product_id"],
                           qty_requested=requested,qty_allocated=qty,qty_shortage=requested-qty))
    remaining = {}
    for k,supply in available.items():
        check(total[k]<=supply, "Insufficient full component stock: %s" % (k,))
        remaining[k] = supply-total[k]

    # Do not let ordinary RO displace a feasible additional RO Paket.
    # This is a local priority test, not a global optimization or fairness
    # algorithm for competing packages/stores. Flag unused feasible demand
    # for review, rather than silently choosing a recipient.
    warnings = []
    for k,r in original.items():
        if proposals[k]==r["qty"] or r["kind"] not in ("RO","RO_PAKET"):
            continue
        parts=parts_by_key[k]
        can_fill=all(remaining[c]>=ratio for c,ratio in parts.items())
        if r["kind"]=="RO_PAKET":
            before_ro=all(remaining[c]+ordinary[c]>=ratio for c,ratio in parts.items())
            check(not (before_ro and not can_fill),
                  "Ordinary RO displaces a feasible higher-priority RO Paket")
        if can_fill:
            warnings.append(dict(kind=r["kind"],source_id=r["source_id"],line_id=r["line_id"],
                                 reason="Additional unit feasible; review unfilled demand"))
    return {
        "rows":result,
        "component_balances":[dict(source_kind=k[0],product_id=k[1],
                                   upper_bound=str(available[k]),used=str(total[k]),
                                   unallocated_upper_bound=str(remaining[k]))
                              for k in sorted(available)],
        "review_warnings":warnings,
        "preview_only":True,
        "operational_allocation_allowed":False,
        "cross_slot_claims_pending":True,
        "recipient_shortage_policy_pending":True,
    }
