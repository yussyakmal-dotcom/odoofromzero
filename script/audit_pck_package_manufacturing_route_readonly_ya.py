"""READ ONLY: identify actual PCK manufacture operation type and BoM operations.

Only erp-yussyakmal-mrp-test. Does NOT write stock/MO/BOM/master data.
Run through odoo-bin shell stdin, after GUI backup is NOT required for read.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: wrong DB"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PCK_PACKAGE_MANUFACTURING_ROUTE")
W = env["stock.warehouse"].sudo()
warehouses = W.search([("code", "=", "PCK")])
print("PCK_WAREHOUSE_COUNT:", len(warehouses))
assert len(warehouses) == 1, "PCK must be unique"
pck = warehouses[0]
print("PCK_WAREHOUSE:", pck.id, pck.name,
      "COMPANY:", pck.company_id.id,
      "STOCK:", pck.lot_stock_id.id, pck.lot_stock_id.complete_name)
print("WAREHOUSE_MANU_TYPE_FIELD:", "manu_type_id" in W._fields)
if "manu_type_id" in W._fields:
    t = pck.manu_type_id
    print("PCK_MANU_TYPE:",
          t.id if t else None, t.name if t else None,
          t.code if t else None,
          t.warehouse_id.id if t else None,
          t.default_location_src_id.complete_name if t else None,
          t.default_location_dest_id.complete_name if t else None)
types = env["stock.picking.type"].sudo().search([
    ("code", "=", "mrp_operation"),
    ("company_id", "=", pck.company_id.id),
])
for t in types.sorted("id"):
    print("MANUFACTURING_OPERATION_TYPE:", t.id, t.name,
          "WAREHOUSE:", t.warehouse_id.code or "-",
          "SOURCE:", t.default_location_src_id.complete_name or "-",
          "DEST:", t.default_location_dest_id.complete_name or "-")
Bom = env["mrp.bom"].sudo()
Product = env["product.product"].sudo()
cats = env["product.category"].sudo().search([
    ("complete_name", "=", "All / Produk Jadi / Paket"),
])
assert len(cats) == 1, "Paket category master must be unique"
pkgs = Product.search([("categ_id", "=", cats.id)])
print("PAKET_SKU_COUNT:", len(pkgs))
no_bom = 0
has_ops = 0
operation_examples = []
bom_pt = {}
for pkg in pkgs:
    boms = Bom.search([
        ("product_tmpl_id", "=", pkg.product_tmpl_id.id),
        ("active", "=", True), ("type", "=", "normal"),
        "|", ("product_id", "=", False), ("product_id", "=", pkg.id),
    ])
    if len(boms) != 1:
        no_bom += 1
        continue
    bom = boms[0]
    pt = bom.picking_type_id
    k = (pt.id, pt.name) if pt else ("none", "-")
    bom_pt[k] = bom_pt.get(k, 0) + 1
    ops = bom.operation_ids if "operation_ids" in Bom._fields else []
    if ops:
        has_ops += 1
        if len(operation_examples) < 15:
            operation_examples.append((pkg.default_code, bom.id, len(ops)))
print("PACKAGE_MISSING_OR_MULTIPLE_NORMAL_BOM:", no_bom)
print("PACKAGE_BOM_OPERATION_TYPE_COUNTS:", sorted(bom_pt.items(), key=lambda x: str(x[0])))
print("PACKAGE_BOMS_WITH_OPERATIONS:", has_ops)
print("PACKAGE_OPERATION_EXAMPLES:", operation_examples)
print("STOCK_QUANT_SOURCE:", "PCK/Stock; native Odoo checks required before marking MO Done")
print("READ_ONLY_PCK_PACKAGE_ROUTE_OK")
