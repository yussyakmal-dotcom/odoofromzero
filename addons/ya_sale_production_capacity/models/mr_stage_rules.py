"""Pure stage-specific MR arithmetic; no Odoo dependency or stock writes."""
from math import isfinite

ISSUE_TOKEN = object()
DEFAULT_MODE = {"mr1": "full", "mr2": "shortage"}


def stage_quantity(mode, gross, physical, reserved, own_reserved,
                   other_need, other_reserved, incoming):
    vals = (gross, physical, reserved, own_reserved, other_need, other_reserved, incoming)
    if mode not in ("full", "shortage") or any(not isfinite(v) for v in vals) or gross < 0:
        raise ValueError("Data metode/kebutuhan bahan tidak valid.")
    external = max(0., reserved-own_reserved-other_reserved)
    if mode == "shortage":
        if any(v < 0 for v in vals):
            raise ValueError("Stok/komitmen negatif. Periksa stok dapur.")
        if reserved > physical+1e-7 or own_reserved+other_reserved > reserved+1e-7:
            raise ValueError("Reservasi tidak cocok dengan stok fisik. Periksa stok dan Check Availability.")
        if own_reserved > gross+1e-7 or other_reserved > other_need+1e-7:
            raise ValueError("Reservasi melebihi kebutuhan MO/transfer terbuka.")
    # Open obligations include their own reservations. Do not deduct twice.
    physical_available = max(0., physical-other_need-external)
    projected = max(0., physical+incoming-other_need-external)
    # Never add an unrelated pre-existing shortage to this stage.
    transfer = float(gross) if mode == "full" else min(gross, max(0., gross-projected))
    return dict(external_reserved=external, physical_available=physical_available,
                projected_available=projected, transfer=transfer)
