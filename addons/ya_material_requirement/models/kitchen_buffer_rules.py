"""Pure projected-stock replenishment math for permanent kitchen buffer warehouses.

No Odoo dependency, stock move, reservation or transfer is performed here.
All quantities MUST be converted to the same product base UoM before calling.
Reservations belonging to open MOs are NOT a second demand: open_mo_demand
already accounts for their entire unsatisfied material obligations.
"""

def buffer_replenishment(open_mo_demand, kitchen_on_hand, incoming_committed,
                         buffer_target, other_commitments=0):
    """Return breakdown and the outstanding replenishment required.

    open_mo_demand: all still-required raw material for *all* open MOs at
        this kitchen, not only the selected Packing batch.
    kitchen_on_hand: physical stock owned by this kitchen (including reserved
        stock; reservations are allocated to the commitments above).
    incoming_committed: undelivered Qty of VALID, uniquely counted incoming
        internal transfers to the kitchen; EXCLUDE Draft/unapproved transfers,
        already-received stock, cancelled moves and duplicate transfer legs.
    buffer_target: desired physical reserve for the next unattended operating
        period (night/CDC holidays), configured per kitchen+SKU; never inferred.
    other_commitments: additional already-approved obligations not covered by
        open MOs. Must not duplicate MO reservations or incoming.
    """
    vals = (open_mo_demand, kitchen_on_hand, incoming_committed,
            buffer_target, other_commitments)
    if any(not isinstance(x, (int, float)) or isinstance(x, bool)
           or x != x or x in (float('inf'), -float('inf')) or x < 0
           for x in vals):
        raise ValueError("All quantities must be finite, nonnegative numbers")
    gross = float(open_mo_demand) + float(other_commitments) + float(buffer_target)
    supply = float(kitchen_on_hand) + float(incoming_committed)
    return {
        "open_mo_demand": float(open_mo_demand),
        "other_commitments": float(other_commitments),
        "buffer_target": float(buffer_target),
        "kitchen_on_hand": float(kitchen_on_hand),
        "incoming_committed": float(incoming_committed),
        "projected_after_commitments": supply - float(open_mo_demand) - float(other_commitments),
        "replenishment_qty": max(gross - supply, 0.0),
    }
