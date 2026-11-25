"""Read-only Fase 2 check: is YA quotation using the intended action/form view?
Run via Odoo shell stdin on the RO_SO clone, never on primary DB.
"""
from lxml import etree

EXPECTED_DB = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == EXPECTED_DB, "STOP_WRONG_DATABASE: " + env.cr.dbname

module = env["ir.module.module"].search(
    [("name", "=", "ya_sale_production_capacity")], limit=1
)
action = env.ref("ya_sale_production_capacity.action_ya_capacity_sale_orders")
view = env.ref("ya_sale_production_capacity.view_ya_capacity_sale_order_form")

print("DATABASE:", env.cr.dbname)
print("MODULE_STATE:", module.state if module else "NOT_FOUND")
print("INSTALLED_VERSION:", module.installed_version if module else "NOT_FOUND")
print("ACTION_ID:", action.id)
print("ACTION_NAME:", action.name)
print("ACTION_RES_MODEL:", action.res_model)
print("ACTION_CONTEXT:", action.context)
print("ACTION_DOMAIN:", action.domain)
print("ACTION_VIEWS:", action.views)
print("ACTION_FORM_BINDINGS:", [
    (v.sequence, v.view_mode, v.view_id.id, v.view_id.name)
    for v in action.view_ids if v.view_mode == "form"
])
print("EXPECTED_FORM_VIEW_ID:", view.id)
print("FORM_VIEW_MODE:", view.mode)
print("FORM_VIEW_ACTIVE:", view.active)
print("FORM_VIEW_INHERITS:", view.inherit_id.id if view.inherit_id else None)

arch = env["sale.order"].get_view(view_id=view.id, view_type="form")["arch"]
if isinstance(arch, bytes):
    root = etree.fromstring(arch)
else:
    root = etree.fromstring(arch.encode("utf-8"))
for name in ("ya_is_capacity_so", "ya_delivery_date", "ya_delivery_date_label", "ya_slot"):
    nodes = root.xpath(".//field[@name='%s']" % name)
    print("MERGED_FIELD:", name, "COUNT:", len(nodes))
    for node in nodes:
        print("  ATTRS:", dict(node.attrib))
        print("  PARENT_TAG:", node.getparent().tag if node.getparent() is not None else "NONE")
# Inspect ancestor modifiers: a field may exist in the merged XML yet be
# hidden by a wrapping group/page. Do not treat XML presence as UI proof.
for name in ("ya_delivery_date", "ya_slot"):
    for node in root.xpath(".//field[@name='%s']" % name):
        print("FIELD_ANCESTORS:", name)
        current = node.getparent()
        depth = 0
        while current is not None and depth < 12:
            attrs = {k: v for k, v in current.attrib.items()
                     if k in ("name", "string", "invisible", "groups",
                              "readonly", "attrs", "states")}
            print("  LEVEL:", depth + 1, "TAG:", current.tag, "ATTRS:", attrs)
            if current.tag == "form":
                break
            current = current.getparent()
            depth += 1
print("READ_ONLY_YA_FORM_DIAGNOSTIC_COMPLETE")
