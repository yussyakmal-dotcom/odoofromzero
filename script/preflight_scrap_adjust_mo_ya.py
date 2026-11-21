"""Read-only preflight for YA Scrap vs Inventory Adjustment vs MO study.

Examines actual Odoo 19 Community model fields, stock locations, selected
manufacturing product valuation and accounting integration. Does NOT create
stock, scrap, inventory adjustment, MO or journal entry.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Wrong database"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PREFLIGHT")
model_specs = {
    "stock.scrap": [
        "name", "state", "product_id", "scrap_qty", "product_uom_id",
        "location_id", "scrap_location_id", "origin", "production_id",
        "picking_id", "lot_id", "reason", "reason_id", "company_id",
        "move_id",
    ],
    "stock.quant": [
        "product_id", "location_id", "quantity", "inventory_quantity",
        "inventory_diff_quantity", "inventory_date", "inventory_quantity_set",
        "inventory_user_id", "inventory_reason_id",
    ],
    "stock.move": [
        "name", "state", "product_id", "product_uom_qty", "product_uom",
        "quantity", "location_id", "location_dest_id", "origin",
        "production_id", "raw_material_production_id", "scrapped",
        "account_move_ids", "value", "price_unit",
    ],
    "mrp.production": [
        "name", "state", "product_id", "product_qty", "qty_producing",
        "product_uom_id", "bom_id", "move_raw_ids", "move_finished_ids",
        "backorder_sequence", "production_location_id", "location_src_id",
        "location_dest_id",
    ],
    "product.category": [
        "property_cost_method", "property_valuation",
        "property_stock_valuation_account_id", "property_stock_account_input_categ_id",
        "property_stock_account_output_categ_id",
    ],
    "stock.location": [
        "name", "usage", "scrap_location", "valuation_in_account_id",
        "valuation_out_account_id",
    ],
}
for model_name, fields in model_specs.items():
    try:
        model = env[model_name].sudo()
    except KeyError:
        print("MODEL_UNAVAILABLE:", model_name)
        continue
    print("MODEL:", model_name)
    for field in fields:
        if field in model._fields:
            definition = model._fields[field]
            print("  FIELD:", field, "| TYPE:", definition.type,
                  "| REQUIRED:", bool(definition.required),
                  "| RELATED:", getattr(definition, "related", None))
        else:
            print("  FIELD_ABSENT:", field)
    for method in {
        "stock.scrap": ["action_validate"],
        "stock.quant": ["action_apply_inventory", "_apply_inventory"],
        "mrp.production": ["button_mark_done", "_post_inventory"],
    }.get(model_name, []):
        print("  METHOD:", method, "AVAILABLE:", hasattr(model, method))

Loc = env["stock.location"].sudo().with_context(active_test=False)
scrap_locs = Loc.search([("scrap_location", "=", True)]) if "scrap_location" in Loc._fields else Loc.browse()
print("SCRAP_LOCATIONS:", len(scrap_locs))
for loc in scrap_locs:
    print("SCRAP_DESTINATION:", loc.id, loc.complete_name,
          "| USAGE:", loc.usage, "| ACTIVE:", loc.active)
print("INVENTORY_LOSS_LOCATIONS:")
for loc in Loc.search([("usage", "=", "inventory")]):
    print("  LOSS_LOCATION:", loc.id, loc.complete_name,
          "| SCRAP:", loc.scrap_location if "scrap_location" in Loc._fields else "n/a")
bom = env["mrp.bom"].sudo().search([("code", "=", "BOM12499")], limit=2)
assert len(bom) == 1, "BOM12499 missing/duplicated"
product = bom.product_id
category = product.categ_id
print("SAMPLE_BOM:", bom.code, product.default_code,
      "| OUTPUT:", bom.product_qty, bom.product_uom_id.name)
print("PRODUCT_TYPE:", product.type, "| TRACKING:", product.tracking)
print("PRODUCT_COST:", product.standard_price, "| COST_CURRENCY:", product.currency_id.name)
print("CATEGORY:", category.complete_name)
for field in ("property_cost_method", "property_valuation",
              "property_stock_valuation_account_id"):
    if field in category._fields:
        val = category[field]
        print("CATEGORY_FIELD:", field,
              val.display_name if getattr(val, "_name", None) else val)
for model_name in ("stock.valuation.layer", "account.move"):
    try:
        model = env[model_name].sudo()
    except KeyError:
        print("VALUATION_MODEL_UNAVAILABLE:", model_name)
    else:
        print("VALUATION_MODEL_AVAILABLE:", model_name,
              "| COUNT:", model.search_count([]))
print("CURRENT_SCRAP_COUNT:", env["stock.scrap"].sudo().search_count([]))
print("CURRENT_MO_COUNT:", env["mrp.production"].sudo().search_count([]))
print("SCRAP_COMPARISON_PREFLIGHT_OK: no database changes")
