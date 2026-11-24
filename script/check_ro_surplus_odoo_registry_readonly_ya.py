"""Read-only smoke test of upgraded YA Store RO inside Odoo test DB.

Run ONLY on erp-yussyakmal-mrp-test, after source-only tests and a controlled
ya_store_ro module upgrade. This script creates NO RO/MO/transfers.
It checks: module version, Odoo registered transient field, DB-stored views,
and the imported runtime allocator. It is NOT end-to-end UAT.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: WRONG DATABASE"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_RO_SURPLUS_ODOO_REGISTRY")

module = env["ir.module.module"].sudo().search([
    ("name", "=", "ya_store_ro")
])
assert len(module) == 1, "Missing or ambiguous ya_store_ro module"
print("MODULE_STATE:", module.state)
print("MODULE_INSTALLED_VERSION:", module.installed_version)
assert module.state == "installed", "ya_store_ro is not installed"
assert module.installed_version == "19.0.8.1.3", (
    "ya_store_ro module upgrade to version 19.0.8.1.3 not confirmed"
)

preview = env["ya.packing.preview"]
assert "total_surplus_distributed" in preview._fields, (
    "Odoo registry has not loaded the new surplus distributed field"
)
field = env["ir.model.fields"].sudo().search([
    ("model", "=", "ya.packing.preview"),
    ("name", "=", "total_surplus_distributed"),
])
assert len(field) == 1, "Odoo metadata for new surplus field is missing"

preview_view = env.ref("ya_store_ro.view_ya_packing_preview_form")
batch_view = env.ref("ya_store_ro.view_ya_packing_batch_form")
preview_xml = str(preview_view.arch_db)
batch_xml = str(batch_view.arch_db)
assert 'name="total_surplus_distributed"' in preview_xml, (
    "Preview form in Odoo database still uses an older version"
)
assert 'Tambahan Surplus BoM' in preview_xml, (
    "Preview form missing per-store surplus allocation"
)
assert 'Tambahan Surplus BoM' in batch_xml, (
    "Frozen batch form missing per-store surplus allocation"
)
assert "Selisih pembulatan BoM TIDAK dibagikan ke toko" not in preview_xml, (
    "Obsolete no-surplus message still stored in Odoo view"
)

from odoo.addons.ya_store_ro.models.allocation_rules import allocate_capacity_prorata
produced, allocated, status = allocate_capacity_prorata(
    {11: 6, 22: 9}, 10, 20
)
assert (produced, status) == (20, "ok"), (produced, status)
assert allocated == {
    11: {"requested": 6, "surplus": 2, "shortage": 0, "allocated": 8},
    22: {"requested": 9, "surplus": 3, "shortage": 0, "allocated": 12},
}, allocated
assert sum(row["allocated"] for row in allocated.values()) == produced
print("ODOO_RUNTIME_ALLOCATOR_SURPLUS_PASS")
print("ODOO_REGISTERED_SURPLUS_FIELD_PASS")
print("ODOO_DB_VIEW_SURPLUS_PASS")
print("READ_ONLY_RO_SURPLUS_REGISTRY_PASS")
print("NOTE: registry/view smoke PASS does NOT verify Pre Produksi, MO, transfer, or DO transactions.")
