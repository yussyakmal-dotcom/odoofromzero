"""Read-only finance readiness audit for RO -> MO -> Packing -> Store.

DB test only. No journal posting, changing accounting settings, or stock.
This is a diagnostic, NOT an accounting signoff.
"""
from collections import Counter

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: test DB only"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_MRP_INVENTORY_ACCOUNTING")
Company = env.company.sudo()
print("COMPANY:", Company.id, Company.name, "CURRENCY:", Company.currency_id.name)
Mods = env["ir.module.module"].sudo()
for name in ("account", "stock", "stock_account", "mrp", "mrp_account",
             "purchase_stock", "account_financial_report", "account_asset_management"):
    mod = Mods.search([("name", "=", name)], limit=1)
    print("MODULE:", name, mod.state if mod else "NOT_FOUND")

Category = env["product.category"].sudo()
categories = Category.search([
    "|", ("complete_name", "ilike", "Produk Jadi"),
    "|", ("complete_name", "ilike", "Bahan Baku"),
    "|", ("complete_name", "ilike", "Konsinyasi"),
    ("complete_name", "ilike", "Packaging"),
], order="complete_name")
print("RELEVANT_CATEGORY_COUNT:", len(categories))
cfields = ["property_cost_method", "property_valuation",
           "property_stock_valuation_account_id",
           "property_stock_account_input_categ_id",
           "property_stock_account_output_categ_id",
           "property_stock_journal", "property_account_expense_categ_id"]
for cat in categories:
    parts = []
    for key in cfields:
        if key in cat._fields:
            val = cat[key]
            parts.append("%s=%s" % (key, val.display_name if
                         cat._fields[key].type == "many2one" and val else val))
    print("CATEGORY:", cat.id, cat.complete_name, "|", "; ".join(parts))

Product = env["product.product"].sudo()
for sku in ("10031", "11076", "12298", "12299"):
    product = Product.search([("default_code", "=", sku)], limit=1)
    if not product:
        print("SAMPLE_SKU_NOT_FOUND:", sku)
        continue
    values = []
    for key in ("standard_price", "cost_method", "valuation",
                "type", "is_storable"):
        if key in product._fields:
            values.append("%s=%s" % (key, product[key]))
    print("SAMPLE_SKU:", sku, product.categ_id.complete_name,
          product.uom_id.name, "; ".join(values))

Location = env["stock.location"].sudo()
for code in ("PCK", "T_KD", "T_SD", "T_MET"):
    wh = env["stock.warehouse"].sudo().search([("code", "=", code)], limit=1)
    if wh:
        print("WAREHOUSE:", code, "STOCK:", wh.lot_stock_id.complete_name,
              "USAGE:", wh.lot_stock_id.usage,
              "COMPANY:", wh.company_id.id)
transit = Location.search([("usage", "=", "transit"),
                           ("name", "=", "Inter-warehouse transit")])
for loc in transit:
    print("TRANSIT:", loc.id, loc.complete_name, "USAGE:", loc.usage,
          "COMPANY:", loc.company_id.id if loc.company_id else "SHARED")
print("PRODUCTION_LOCATION_COUNT:", Location.search_count([("usage", "=", "production")]))
print("=== FINANCIAL MODEL/FIELD INVENTORY ===")
for name in ("stock.valuation.layer", "account.move", "account.move.line",
             "mrp.production", "stock.move"):
    if name not in env.registry.models:
        print("MODEL:", name, "NOT_AVAILABLE")
        continue
    model = env[name].sudo()
    print("MODEL:", name, "AVAILABLE")
    picks = ["value", "unit_cost", "quantity", "remaining_value",
             "remaining_qty", "stock_move_id", "account_move_id",
             "valuation_layer_ids", "stock_valuation_layer_ids",
             "price_unit", "cost_method", "valuation", "state",
             "product_qty", "move_raw_ids", "move_finished_ids"]
    print("FIELDS:", {key: model._fields[key].type
                     for key in picks if key in model._fields})
    if name == "stock.valuation.layer":
        print("SVL_RECORD_COUNT:", model.search_count([]))
    if name == "account.move":
        print("POSTED_ENTRY_COUNT:", model.search_count([
            ("company_id", "=", Company.id), ("move_type", "=", "entry"),
            ("state", "=", "posted")]))
print("=== COMPLETED YA PRODUCTION / DISTRIBUTION SAMPLE ===")
if "ya.packing.batch" in env.registry.models:
    Batch = env["ya.packing.batch"].sudo()
    for batch in Batch.search([], order="id desc", limit=5):
        print("BATCH:", batch.id, batch.name, batch.state,
              "MOs:", len(batch.line_ids.mapped("mo_id")))
        if "ya_store_delivery_ids" in batch._fields:
            for picking in batch.ya_store_delivery_ids:
                print(" YA_TRANSFER:", picking.name, picking.state,
                      picking.ya_store_stage, "LINES:", len(picking.move_ids))
print("NOTE: valuations, journal timing and MO cost correctness require")
print("      transaction-by-transaction quantity/value/GL reconciliation.")
print("READ_ONLY_MRP_INVENTORY_ACCOUNTING_AUDIT_OK")
