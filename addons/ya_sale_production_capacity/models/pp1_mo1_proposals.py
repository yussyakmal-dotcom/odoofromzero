"""Source-only MO1 proposals from a freshly reviewed Design B source set.

No ORM writes or public button. Legacy Packing allocation cannot represent
SO-first, unassigned RO shortages or zero-output demand. The final persistent
snapshot and release gate must be implemented separately before operational use.
"""
from odoo.addons.ya_store_ro.models.date_labels import format_ymondd
from .pp1_native_sources import PP1SourceError, require
from .pp1_review_contract import revalidate_review
from odoo import fields

def prepare_mo1_proposals(env, delivery_date, slot, company, expected_digest):
    if not env.user.has_group("ya_store_ro.group_ya_packing_admin"):
        raise PP1SourceError("Only Packing Admin may prepare MO1 release")
    fresh = revalidate_review(env, delivery_date, slot, company, expected_digest)
    facts = fresh["facts"]
    require(not facts["batch_id"], "Existing legacy staged batch requires controlled migration/refresh")
    date = fields.Date.to_date(delivery_date)
    proposals = []
    for row in facts["sku_forecasts"]:
        qty = row["forecast_mo1_qty"]
        if not qty:
            continue
        line = env["ya.production.planning.line"].sudo().browse(row["planning_line_id"]).exists()
        require(bool(line), "Planning line disappeared")
        product = line.product_id
        bom = line._capacity_bom()
        pt = bom.picking_type_id
        require(product.id == row["product_id"] and bom.id == row["bom_id"],
                "MO1 source identity mismatch")
        require(qty > 0 and qty <= row["published_max"] and qty % row["bom_output"] == 0,
                "MO1 Qty exceeds Max or invalid BoM")
        proposals.append({
            "planning_line_id": line.id,
            "planning_id": line.planning_id.id,
            "kitchen_code": line.planning_id.kitchen_code,
            "product_id": product.id,
            "reference": product.default_code or str(product.id),
            "forecast": row,
            "native_mo_vals": {
                "product_id": product.id,
                "product_qty": float(qty),
                "product_uom_id": product.uom_id.id,
                "bom_id": bom.id,
                "picking_type_id": pt.id,
                "location_src_id": pt.default_location_src_id.id,
                "location_dest_id": pt.default_location_dest_id.id,
                "company_id": company.id,
                "origin": "MO1 / %s / %s" % (format_ymondd(date), slot),
            },
        })
    return {"review": fresh, "proposals": proposals,
            "operational_release_allowed": False,
            "cutoff_and_persistent_snapshot_pending": True}
