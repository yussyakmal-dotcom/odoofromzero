"""Read-only Fase2 audit of native MO2 -> CDC / Finished Goods -> PCK bridge.

Run with Odoo shell on ONLY erp-yussyakmal-mrp-test-RO_SO.
Read installed schemas and GitHub-synced Fase1 source; NO ORM writes.
This is a design gate, NOT a test of actual material transfers or deliveries.
"""
from pathlib import Path

DB = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == DB, "STOP_WRONG_DATABASE"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_MO2_MATERIAL_FG_BRIDGE_AUDIT")

paths = {
    "MR_CALC": Path("addons/ya_material_requirement/models/material_requirement.py"),
    "MR_BATCH": Path("addons/ya_material_requirement/models/material_requirement_batch.py"),
    "MR_TRANSFER": Path("addons/ya_material_requirement/models/material_requirement_direct_transfer.py"),
    "FG_KITCHEN_TO_PCK": Path("addons/ya_finished_packing_transfer/models/finished_packing.py"),
    "STORE_DO": Path("addons/ya_packing_store_delivery/models/store_delivery.py"),
    "MO2_RELEASE": Path("addons/ya_sale_production_capacity/models/mo2_release.py"),
}
signals = {
    "MR_CALC": ("TEST_DB = 'erp-yussyakmal-mrp-test'",
                "links.mapped('mo_id')",
                "mo.state != 'confirmed'"),
    "MR_BATCH": ("TEST_DB = 'erp-yussyakmal-mrp-test'",
                 "def _mr_guard(self):"),
    "MR_TRANSFER": ("TEST_DB = 'erp-yussyakmal-mrp-test'",
                    "UNIQUE(ya_mr_batch_id, ya_mr_kitchen_id)"),
    "FG_KITCHEN_TO_PCK": ('TEST_DB = "erp-yussyakmal-mrp-test"',
                          'self.line_ids.mapped("mo_id")',
                          "UNIQUE(ya_fg_batch_id, ya_fg_kitchen_id)"),
    "STORE_DO": ('TEST_DB = "erp-yussyakmal-mrp-test"',
                 'self.line_ids.mapped("mo_id")'),
    "MO2_RELEASE": ('CLONE_DB = "erp-yussyakmal-mrp-test-RO_SO"',
                    'self.env["mrp.production"].create({',
                    '"ya.sale.mo2.release.line"'),
}
for label, path in paths.items():
    assert path.is_file(), "STOP_SOURCE_FILE_MISSING: %s" % path
    raw = path.read_text(encoding="utf-8")
    found = {needle: needle in raw for needle in signals[label]}
    print("SOURCE_LINK:", label, "SIGNALS:", found)
    assert all(found.values()), "STOP_SOURCE_CONTRACT_CHANGED: %s" % label

modnames = (
    "ya_sale_production_capacity", "ya_material_requirement",
    "ya_finished_packing_transfer", "ya_packing_store_delivery",
    "ya_store_ro", "ya_package_store_ro", "ya_production_planning",
)
Modules = env["ir.module.module"].sudo()
for name in modnames:
    rec = Modules.search([("name", "=", name)], limit=1)
    print("MODULE:", name,
          "STATE:", rec.state if rec else None,
          "VERSION:", rec.installed_version if rec else None)

Batch = env["ya.packing.batch"].sudo()
Stock = env["stock.picking"].sudo()
MO = env["mrp.production"].sudo()
Final = env["ya.sale.mo2.finalization"].sudo()
Release = env["ya.sale.mo2.release.line"].sudo()

print("BRIDGE_SCHEMAS:", {
    "batch_mo1": "line_ids" in Batch._fields,
    "batch_finished_picking_links": "ya_fg_transfer_ids" in Batch._fields,
    "batch_mr_native_pickings": "mr_native_transfer_ids" in Batch._fields,
    "mo1_native_link": "ya_packing_batch_line_id" in MO._fields,
    "mo2_release_native_link": "mo_id" in Release._fields,
    "mo2_release_planning_link": "planning_line_id" in Release._fields,
    "mo2_finalization_batch_link": "batch_id" in Final._fields,
    "stock_mr_batch_link": "ya_mr_batch_id" in Stock._fields,
    "stock_mr_kitchen_link": "ya_mr_kitchen_id" in Stock._fields,
    "stock_fg_batch_link": "ya_fg_batch_id" in Stock._fields,
    "stock_fg_kitchen_link": "ya_fg_kitchen_id" in Stock._fields,
    "stock_store_dispatch_stage": "ya_store_stage" in Stock._fields,
})
print("MO2_PERSISTED_FINALIZATION_COUNT:", Final.search_count([]))
print("MO2_PERSISTED_RELEASE_LINE_COUNT:", Release.search_count([]))
print("EXISTING_MO1_PACKING_BATCH_COUNT:", Batch.search_count([]))
sample = Batch.search([], order="delivery_date desc,slot,id", limit=1)
if sample:
    print("EXISTING_BATCH_SAMPLE:",
          "ID:", sample.id,
          "DATE:", sample.delivery_date,
          "SLOT:", sample.slot,
          "STATE:", sample.state,
          "MO1:", len(sample.line_ids.mapped("mo_id")),
          "MR_NATIVE_PICKINGS:", len(sample.mr_native_transfer_ids),
          "FG_NATIVE_PICKINGS:", len(sample.ya_fg_transfer_ids),
          "STORE_DO:", len(sample.ya_store_delivery_ids))
print("INTEGRATION_GAPS_CONFIRMED_IN_SOURCE:")
print("1. Phase1 material requirement reads only batch.line_ids.mo_id and confirmed MO1.")
print("2. Phase1 material transfer UNIQUE(batch,kitchen), cannot silently repeat for MO2.")
print("3. Phase1 finished-goods transfer reads only batch.line_ids.mo_id; UNIQUE(batch,kitchen).")
print("4. Phase1 store DO reads MO1 kitchens and frozen allocations, not SO-first final allocation.")
print("5. Phase1 MR/FG/DO stock actions explicitly restrict previous first-phase test DB.")
print("READ_ONLY_MO2_MATERIAL_FG_BRIDGE_AUDIT_PASS")
print("NO_STOCK_MO_OR_PICKING_MUTATION")
