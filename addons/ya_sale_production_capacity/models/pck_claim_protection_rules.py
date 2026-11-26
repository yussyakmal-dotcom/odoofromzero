"""Pure conservative PCK claim protection, NOT a stock entitlement.

Inputs are exact-root base-UoM quantities and independently reconciled
native reservations. A batch's remaining received stock and its outbound
demand overlap; use max, not sum. Existing native reservations are already
deducted from global free stock. No release of other-slot surplus, priority
between slots, or treatment of unissued demand is decided here.
"""
from decimal import Decimal
from math import isfinite


def qty(v):
    if isinstance(v,bool) or not isinstance(v,(int,float,Decimal)):
        raise ValueError("Invalid stock quantity")
    n=Decimal(str(v))
    if not n.is_finite() or n<0:
        raise ValueError("Invalid stock quantity")
    return n


def review_claims(physical,reserved,claims,current_batch_id):
    physical,reserved=qty(physical),qty(reserved)
    if reserved>physical:
        raise ValueError("Reserved exceeds physical")
    by_batch={}
    for row in claims:
        bid=row["batch_id"]
        if bid in by_batch:
            raise ValueError("Duplicate batch claim")
        receipt,done,open_demand,held=(qty(row[k]) for k in
            ("received","done_out","open_demand","reserved"))
        if held>open_demand:
            raise ValueError("Reservation exceeds native open demand")
        residual=max(Decimal(0),receipt-done)
        # A held unit can satisfy either the outstanding received stock
        # protection or the outbound obligation, never two deductions.
        protection=max(Decimal(0),residual-held,open_demand-held)
        by_batch[bid]=dict(received=receipt,done_out=done,
            open_demand=open_demand,reserved=held,
            residual_receipt=residual,additional_protection=protection)
    if sum(r["reserved"] for r in by_batch.values())!=reserved:
        raise ValueError("Native reservations not reconciled to quant reserved")
    own=by_batch.get(current_batch_id)
    other=sum((r["additional_protection"] for bid,r in by_batch.items()
               if bid!=current_batch_id),Decimal(0))
    free=physical-reserved
    remaining=max(Decimal(0),free-other)
    own_cap=max(Decimal(0),own["residual_receipt"]-own["reserved"]) if own else Decimal(0)
    return dict(global_free=free,other_protection=other,
        shared_free_after_other_protection=remaining,
        own_unreserved_receipt_cap=own_cap,
        conservative_preview_cap=min(remaining,own_cap),
        other_claim_shortfall=max(Decimal(0),other-free),
        claims=by_batch,preview_only=True,operational_allocation_allowed=False)
