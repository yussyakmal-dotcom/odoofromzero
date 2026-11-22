"""READ-ONLY Odoo shell audit: MO raw component demand vs kitchen / CDC stock.

Only database erp-yussyakmal-mrp-test. No create/write/unlink/transfer/PO/MO.
Usage as Feri from repo:
  sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
    /opt/odoo19/odoo/odoo-bin shell \
    -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http \
    < script/audit_mo_material_cdc_readonly_ya.py

The script compares physical and unreserved stock separately because raw
material reservations belonging to the same MOs can distort naive shortages.
Do NOT issue transfer orders from this diagnostic report yet.
"""
from collections import defaultdict

TARGET_DELIVERY_DATE = '2026-11-27'
TARGET_SLOT = 'S1'
EXPECTED_DB = 'erp-yussyakmal-mrp-test'
MAX_PRINT_ROWS = 75


def fmt(value):
    return ('%.4f' % value).rstrip('0').rstrip('.') or '0'


def stock_snapshot(env, warehouse, product_ids):
    """Physical and total reserved stock in internal sublocations of WH/Stock."""
    if not product_ids:
        return {}
    loc = warehouse.lot_stock_id
    if not loc or loc.usage != 'internal':
        raise ValueError('Invalid internal stock location for warehouse %s'
                         % warehouse.display_name)
    domain = [
        ('product_id', 'in', list(product_ids)),
        ('location_id', 'child_of', loc.id),
        ('location_id.usage', '=', 'internal'),
        ('company_id', '=', warehouse.company_id.id),
    ]
    result = defaultdict(lambda: [0.0, 0.0])
    for quant in env['stock.quant'].search(domain):
        result[quant.product_id.id][0] += quant.quantity
        result[quant.product_id.id][1] += quant.reserved_quantity
    return result


def audit(env):
    if env.cr.dbname != EXPECTED_DB:
        raise RuntimeError('REFUSED: database is %s (only %s allowed)' %
                           (env.cr.dbname, EXPECTED_DB))
    print('DATABASE:', env.cr.dbname)
    print('MODE: READ_ONLY_MO_RAW_MATERIAL_CDC')
    print('TARGET_DATE:', TARGET_DELIVERY_DATE, 'SLOT:', TARGET_SLOT)
    if ('ya.packing.batch' not in env or 'mrp.production' not in env):
        raise RuntimeError('Missing YA Packing / MRP model in registry')

    batches = env['ya.packing.batch'].search([
        ('delivery_date', '=', TARGET_DELIVERY_DATE),
        ('slot', '=', TARGET_SLOT),
    ])
    if len(batches) != 1 or batches.state != 'production_ok':
        print('TARGET_BATCH_NOT_READY:', len(batches))
        for batch in batches:
            print('BATCH:', batch.name, 'STATUS:', batch.state)
        print('No components calculated; verify date/slot and Produksi OK.')
        return

    batch = batches[0]
    mo_rows = batch.line_ids
    if not mo_rows or any(not row.mo_id for row in mo_rows):
        raise RuntimeError('Batch is missing linked MO records')
    mos = mo_rows.mapped('mo_id')
    if any(mo.state in ('done', 'cancel') for mo in mos):
        raise RuntimeError('Some MOs are done/cancelled; reconcile before new CDC request')
    print('BATCH:', batch.name, 'MO_COUNT:', len(mos))
    print('MO_STATES:', sorted(set(mos.mapped('state'))))

    whs = env['stock.warehouse'].search([
        ('company_id', 'in', list(set(mos.mapped('company_id').ids)))
    ])
    for wh in whs.sorted(lambda row: (row.name or '', row.id)):
        print('WAREHOUSE:', wh.id, wh.code, wh.name,
              'STOCK_LOCATION:', wh.lot_stock_id.complete_name)

    central_candidates = whs.filtered(
        lambda wh: any(term in ((wh.name or '') + ' ' + (wh.code or '')).casefold()
                       for term in ('cdc', 'central', 'pusat'))
    )
    cdc_wh = central_candidates[0] if len(central_candidates) == 1 else False
    print('CDC_MATCH_COUNT:', len(central_candidates))
    if cdc_wh:
        print('CDC_CANDIDATE:', cdc_wh.id, cdc_wh.name, cdc_wh.lot_stock_id.complete_name)
    else:
        print('CDC_NOT_UNAMBIGUOUS: manual mapping needed; no CDC balance assumed')

    needs = defaultdict(lambda: {'qty': 0.0, 'move_count': 0, 'mo_ids': set(),
                                 'source_location_ids': set()})
    kitchens = {}
    for mo in mos:
        wh = mo.picking_type_id.warehouse_id
        if not wh or not wh.lot_stock_id:
            raise RuntimeError('MO %s has no unambiguous kitchen warehouse' % mo.name)
        if wh.company_id != mo.company_id:
            raise RuntimeError('MO %s company and kitchen warehouse mismatch' % mo.name)
        kitchens[wh.id] = wh
        for move in mo.move_raw_ids:
            if move.state in ('done', 'cancel') or not move.product_id:
                continue
            qty_base = move.product_uom._compute_quantity(
                move.product_uom_qty, move.product_id.uom_id, round=False,
            )
            if qty_base <= 0:
                continue
            key = (wh.id, move.product_id.id)
            row = needs[key]
            row['qty'] += qty_base
            row['move_count'] += 1
            row['mo_ids'].add(mo.id)
            row['source_location_ids'].add(move.location_id.id)

    if not needs:
        print('NO_OPEN_RAW_COMPONENT_MOVES: inspect MO BoM/confirmation')
        return
    products = env['product.product'].browse(sorted({k[1] for k in needs}))
    product_by_id = {p.id: p for p in products}
    product_ids = set(products.ids)
    stocks = {
        wh_id: stock_snapshot(env, wh, product_ids)
        for wh_id, wh in kitchens.items()
    }
    cdc_stock = stock_snapshot(env, cdc_wh, product_ids) if cdc_wh else {}
    rows = []
    for (wh_id, product_id), requirement in needs.items():
        wh = kitchens[wh_id]
        product = product_by_id[product_id]
        physical, reserved = stocks[wh_id].get(product_id, [0.0, 0.0])
        free = max(0.0, physical - reserved)
        demand = requirement['qty']
        # Diagnostics only: lower/upper estimates, not a transfer order.
        # A same-MO reservation may be counted in reserved stock already.
        min_possible_shortage = max(0.0, demand - max(physical, 0.0))
        max_possible_shortage = max(0.0, demand - free)
        cdc_available = None
        if cdc_wh:
            cdc_qty, cdc_reserved = cdc_stock.get(product_id, [0.0, 0.0])
            cdc_available = max(0.0, cdc_qty - cdc_reserved)
        rows.append((wh, product, demand, physical, reserved, free,
                     min_possible_shortage, max_possible_shortage,
                     cdc_available, requirement))
    rows.sort(key=lambda item: (-item[7], item[0].name or '',
                                 item[1].default_code or '', item[1].id))
    print('COMPONENT_GROUP_COUNT:', len(rows))
    print('RAW_MOVE_COUNT:', sum(row[9]['move_count'] for row in rows))
    print('MO_COMPONENT_SOURCE_LOCATION_MISMATCHES:')
    for wh, product, *_, requirement in rows:
        source_locations = env['stock.location'].browse(
            sorted(requirement['source_location_ids']))
        outside = source_locations.filtered(
            lambda location: not (
                location.id == wh.lot_stock_id.id or
                location.id in env['stock.location'].search([
                    ('id', 'child_of', wh.lot_stock_id.id)
                ]).ids
            )
        )
        if outside:
            print('SOURCE_OUTSIDE_KITCHEN_STOCK:', wh.name, product.default_code,
                  ','.join(outside.mapped('complete_name')))
    print('TOP_COMPONENTS (kitchen | SKU | need | on_hand | reserved_all | free | '
          'shortfall_if_no_reservation | shortfall_if_reserved_elsewhere | '
          'CDC_free | UoM):')
    for wh, product, demand, physical, reserved, free, lower, upper, cdc, _ in rows[:MAX_PRINT_ROWS]:
        print('COMPONENT:', wh.name, '|', product.default_code or product.id,
              '|', fmt(demand), '|', fmt(physical), '|', fmt(reserved),
              '|', fmt(free), '|', fmt(lower), '|', fmt(upper),
              '|', fmt(cdc) if cdc is not None else 'CDC_UNKNOWN',
              '|', product.uom_id.name)
    if len(rows) > MAX_PRINT_ROWS:
        print('TRUNCATED_ROWS:', len(rows) - MAX_PRINT_ROWS)
    print('WARNING: shortage interval is DIAGNOSTIC, not an approved CDC request.')
    print('WARNING: same-MO stock reservations, outstanding receipts/transfers, '
          'lot/FEFO, and supplier replenishment must be reconciled before '
          'automatically requesting stock.')
    print('AUDIT_READ_ONLY_OK')


try:
    audit(env)
finally:
    env.cr.rollback()
