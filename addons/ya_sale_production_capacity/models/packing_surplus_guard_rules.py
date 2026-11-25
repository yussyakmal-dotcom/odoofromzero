"""Source-only, pure Fase2 final-PCK entitlement guard (NOT imported/deployed).

Owner safety invariant: Actual production / PCK physical free availability
does NOT authorize giving extras to shops or customers who did not order.
This is a proposed final allocation PREVIEW only. Authoritative open demand
must be derived in a separate real ORM adapter from Confirmed SO, confirmed
RO Paket & ordinary RO, with explicit recipient/source IDs. It MUST exclude
previously reserved/delivered/allocated quantities before calling this rule.
Do not use this to mark whole packages assembled: BoM completeness must be
verified by the independent native PCK assembly gate first.

No Odoo imports, no stock updates, no DO, no automatic internal-transfer
fallback. Does not alter historical immutable Pre Production RO snapshots.
"""


class SurplusAllocationError(ValueError):
    pass


VALID_TIERS = ("SO_DIRECT", "SO_PAKET_COMPONENT",
               "RO_PAKET_COMPONENT", "RO_STORE")


def _whole(x, label, positive=False):
    if isinstance(x, bool) or not isinstance(x, int):
        raise SurplusAllocationError("%s must be whole base UoM" % label)
    if x < 0 or (positive and x == 0):
        raise SurplusAllocationError(
            "%s must be %s" % (
                label, "positive" if positive else "nonnegative"
            )
        )
    return x


def preview_only_authorized_entitlements(*, pck_stock_by_sku,
                                         open_entitlements):
    """Fail-closed native free-stock allocation preview for FINAL Packing.

    pck_stock_by_sku: {sku_int: {physical:int, reserved:int}} after applying
      native Odoo stock and reserved checks, in exact PRODUCT BASE UOM.
      Caller must ensure no other owner/lot/package stock is included.
    open_entitlements: [{sku:int, tier:str, source_id:int, recipient_id:int,
                         qty_open:int}] derived from CONFIRMED demand sources.
      qty_open must already subtract existing physical DO/allocations. Every
      entitlement MUST map to an approved destination and a unique demand.
      SO Paket and RO Paket rows describe provisional COMPONENT ENTITLEMENT,
      not final assembled Paket deliveries.
    Returns one preview row per entitlement, and all unallocated extra
    in PCK. Any shortage fails closed (no implicit prorata or SO tie-break).
    """
    if not isinstance(pck_stock_by_sku, dict) or not isinstance(
            open_entitlements, (tuple, list)):
        raise SurplusAllocationError("Wrong stock or demand container")
    available = {}
    for sku, record in pck_stock_by_sku.items():
        _whole(sku, "Product ID", positive=True)
        if not isinstance(record, dict):
            raise SurplusAllocationError("Stock detail missing")
        physical = _whole(record.get("physical"), "PCK physical")
        reserved = _whole(record.get("reserved"), "PCK reserved")
        if reserved > physical:
            raise SurplusAllocationError(
                "Native reserved cannot exceed physical SKU %s" % sku
            )
        available[sku] = physical-reserved

    required = {}
    unique = set()
    plan = []
    for row in open_entitlements:
        if not isinstance(row, dict):
            raise SurplusAllocationError("Demand source must be mapping")
        sku = _whole(row.get("sku"), "Source SKU", positive=True)
        tier = row.get("tier")
        if tier not in VALID_TIERS:
            raise SurplusAllocationError("Unapproved demand tier %s" % tier)
        source_id = _whole(
            row.get("source_id"), "Confirmed demand ID", positive=True
        )
        recipient_id = _whole(
            row.get("recipient_id"), "Destination ID", positive=True
        )
        quantity = _whole(row.get("qty_open"), "Open need")
        identity = (tier, source_id, recipient_id, sku)
        if identity in unique:
            raise SurplusAllocationError(
                "Duplicated entitlement identity %s" % (identity,)
            )
        unique.add(identity)
        required[sku] = required.get(sku, 0)+quantity
        plan.append({
            "sku":sku, "tier":tier, "source_id":source_id,
            "recipient_id":recipient_id,
            "qty_entitled":quantity, "qty_preview_allocated":quantity,
            "qty_surplus_allocated":0
        })

    short = {
        sku: required[sku]-available.get(sku, 0)
        for sku in sorted(required)
        if required[sku] > available.get(sku, 0)
    }
    if short:
        raise SurplusAllocationError(
            "STOP_UNDERSTOCK_NO_AUTOMATIC_TIER_TIE_BREAK: %s" % short
        )
    unallocated = {
        sku: available[sku] - required.get(sku, 0)
        for sku in sorted(available)
    }
    assert all(x >= 0 for x in unallocated.values())
    assert all(
        sum(row["qty_preview_allocated"]
            for row in plan if row["sku"] == sku)
        + unallocated[sku] == available[sku]
        for sku in available
    )
    assert all(row["qty_surplus_allocated"] == 0 for row in plan)
    return {
        "allocation_rows": sorted(
            plan,
            key=lambda r: (
                VALID_TIERS.index(r["tier"]), r["source_id"],
                r["recipient_id"], r["sku"]
            ),
        ),
        "qty_open_authorized_per_sku": dict(sorted(required.items())),
        "qty_unallocated_pck_per_sku": unallocated,
        "automatic_surplus_to_store_or_so": 0,
        "requires_separate_owner_decision_for_surplus": any(
            qty > 0 for qty in unallocated.values()
        ),
        "operator_final_do_not_created": True,
        "pure_preview_only": True,
    }
