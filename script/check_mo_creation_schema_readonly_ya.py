"""READ-ONLY schema preflight for using STANDARD Odoo 19 MO after RO consolidation.

Run against erp-yussyakmal-mrp-test only. No create/write/unlink/commit.
Shell:
 sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell \
   -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http \
   < script/check_mo_creation_schema_readonly_ya.py
"""
MODEL = env['mrp.production']
print('DB:', env.cr.dbname)
assert env.cr.dbname == 'erp-yussyakmal-mrp-test', 'Wrong DB; abort!'
print('MODE: READ_ONLY_MO_SCHEMA')
for name in (
    'product_id', 'product_qty', 'product_uom_id', 'bom_id', 'picking_type_id',
    'location_src_id', 'location_dest_id', 'date_start', 'date_finished',
    'origin', 'company_id', 'state', 'move_raw_ids', 'move_finished_ids',
    'workorder_ids',
):
    f = MODEL._fields.get(name)
    print('MO_FIELD:', name, f.type if f else 'MISSING',
          'required=' + str(f.required) if f else '')
print('MO_METHOD_ACTION_CONFIRM:', callable(getattr(MODEL, 'action_confirm', None)))
print('MO_METHOD_ACTION_ASSIGN:', callable(getattr(MODEL, 'action_assign', None)))
print('MO_DEFAULT_GET:', {
    k: (v.id if hasattr(v, 'id') else str(v))
    for k, v in MODEL.default_get([
        'picking_type_id', 'location_src_id', 'location_dest_id', 'company_id',
    ]).items()
})
for name in ['ya.production.planning', 'ya.store.ro', 'ya.packing.preview']:
    print('CUSTOM_MODEL:', name, name in env.registry)
print('MAPPING_SAMPLE_CONFIRMED_RO:')
RO = env['ya.store.ro']
orders = RO.search([('state', '=', 'confirmed')], limit=3, order='id desc')
for ro in orders:
    p = ro.planning_id
    print('RO', ro.id, 'date', p.delivery_date, 'slot', p.slot,
          'kitchen', p.kitchen_code, 'workcenter', p.workcenter_id.name)
    for line in ro.line_ids.filtered(lambda line: line.qty_requested > 0)[:3]:
        matching = p.line_ids.filtered(lambda x: x.product_id == line.product_id)
        if len(matching) != 1:
            print('  SKU', line.reference, 'PLAN_LINE_MISMATCH', len(matching))
            continue
        bom = matching._capacity_bom()
        pt = bom.picking_type_id
        print('  SKU', line.reference, 'RO_QTY', line.qty_requested,
              'BOM', bom.id, 'BoM_Output', bom.product_qty,
              'BoM_UoM', bom.product_uom_id.name,
              'PickingType', pt.id, pt.name,
              'Warehouse', pt.warehouse_id.name,
              'PT_Source', pt.default_location_src_id.complete_name,
              'PT_Dest', pt.default_location_dest_id.complete_name)
print('MO_SCHEMA_READONLY_OK')
