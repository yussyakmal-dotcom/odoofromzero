"""DEV ONLY: inventory-adjust CDC materials to 10x the CURRENT shortfall of a Packing MO batch.

DO NOT use in production. Runs only in erp-yussyakmal-mrp-test with exact
date/slot. Default DRY RUN. Uses standard stock.quant inventory adjustment,
not SQL updates or stock moves from another warehouse. The adjustment is
intentionally outside the normal CDC replenishment / Purchasing business flow.

PREVIEW:
    sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
      /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf \
      -d erp-yussyakmal-mrp-test --no-http \
      < script/dev_seed_cdc_material_10x_ya.py

APPLY (after backup, review and confirm):
    sudo -u odoo19 env YA_DEV_CDC_STOCK_APPLY=YES_I_CONFIRM_TEST_DB \
      /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell \
      -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http \
      < script/dev_seed_cdc_material_10x_ya.py

The script applies inventory adjustments (creates stock moves), so it commits
ONLY in APPLY mode. All other runs rollback; refuse non-test DB.
"""
import math
import os
from collections import defaultdict

from odoo.tools import float_compare, float_round

EXPECTED_DB = 'erp-yussyakmal-mrp-test'
TARGET_DATE = '2026-11-27'
TARGET_SLOT = 'S1'
MULTIPLIER = 10
APPLY_TOKEN = 'YES_I_CONFIRM_TEST_DB'
APPLY = os.environ.get('YA_DEV_CDC_STOCK_APPLY', '') == APPLY_TOKEN


def fmt(number):
    return ('%.5f' % number).rstrip('0').rstrip('.') or '0'


def wh_stock(env, wh, product_ids):
    stock = defaultdict(lambda: [0.0, 0.0])
    if not product_ids:
        return stock
    for quant in env['stock.quant'].search([
        ('product_id', 'in', list(product_ids)),
        ('location_id', 'child_of', wh.lot_stock_id.id),
        ('location_id.usage', '=', 'internal'),
        ('company_id', '=', wh.company_id.id),
    ]):
        stock[quant.product_id.id][0] += quant.quantity
        stock[quant.product_id.id][1] += quant.reserved_quantity
    return stock


def run(env):
    if env.cr.dbname != EXPECTED_DB:
        raise RuntimeError('REFUSED: database %s, only %s allowed' %
                           (env.cr.dbname, EXPECTED_DB))
    if os.environ.get('YA_DEV_CDC_STOCK_APPLY') and not APPLY:
        raise RuntimeError('Invalid YA_DEV_CDC_STOCK_APPLY token: abort')
    if not isinstance(MULTIPLIER, int) or MULTIPLIER != 10:
        raise RuntimeError('REFUSED: unexpected multiplier')

    print('DATABASE:', env.cr.dbname)
    print('MODE:', 'APPLY_TEST_DB_ONLY' if APPLY else 'DRY_RUN_READ_ONLY')
    print('BATCH:', TARGET_DATE, TARGET_SLOT, 'MULTIPLIER:', MULTIPLIER)

    batches = env['ya.packing.batch'].search([
        ('delivery_date', '=', TARGET_DATE),
        ('slot', '=', TARGET_SLOT),
        ('state', '=', 'production_ok'),
    ])
    if len(batches) != 1:
        raise RuntimeError('Expected exactly one Produksi OK Packing batch')
    links = batches.line_ids
    if not links or any(not row.mo_id for row in links):
        raise RuntimeError('Missing Packing-to-MO links')
    mos = links.mapped('mo_id')
    if len(mos) != len(links) or any(mo.state != 'confirmed' for mo in mos):
        raise RuntimeError('Expected distinct Confirmed MOs only; not running')
    companies = mos.mapped('company_id')
    if len(companies) != 1:
        raise RuntimeError('Multiple MO companies; cannot seed')
    company = companies[0]
    CDC = env['stock.warehouse'].search([
        ('company_id', '=', company.id), ('code', '=', 'CDC'),
    ])
    if len(CDC) != 1 or CDC.lot_stock_id.usage != 'internal':
        raise RuntimeError('Cannot identify unique CDC internal stock location')
    cdc = CDC[0]
    if cdc.lot_stock_id.company_id and cdc.lot_stock_id.company_id != company:
        raise RuntimeError('CDC stock location company mismatch')
    print('CDC:', cdc.name, cdc.lot_stock_id.complete_name)

    needs = defaultdict(float)
    kitchens = {}
    source_ids = defaultdict(set)
    for mo in mos:
        kitchen = mo.picking_type_id.warehouse_id
        if not kitchen or not kitchen.lot_stock_id or kitchen == cdc:
            raise RuntimeError('MO %s has invalid kitchen routing' % mo.name)
        if kitchen.company_id != company:
            raise RuntimeError('MO %s has another company warehouse' % mo.name)
        kitchens[kitchen.id] = kitchen
        for move in mo.move_raw_ids:
            if move.state in ('cancel', 'done') or not move.product_id:
                continue
            qty = move.product_uom._compute_quantity(
                move.product_uom_qty, move.product_id.uom_id, round=False,
            )
            if qty < 0:
                raise RuntimeError('Negative MO raw demand: %s' % mo.name)
            if qty <= 0:
                continue
            key = (kitchen.id, move.product_id.id)
            needs[key] += qty
            source_ids[key].add(move.location_id.id)
    if not needs:
        raise RuntimeError('No MO raw materials found')

    locations = env['stock.location']
    for kitchen in kitchens.values():
        allowed = set(locations.search([
            ('id', 'child_of', kitchen.lot_stock_id.id),
        ]).ids)
        for (wh_id, product_id), src in source_ids.items():
            if wh_id == kitchen.id and not src.issubset(allowed):
                raise RuntimeError(
                    'Raw move source not in kitchen Stock: %s %s' %
                    (kitchen.name, product_id)
                )

    product_ids = {pid for _, pid in needs}
    products = {p.id: p for p in env['product.product'].browse(sorted(product_ids))}
    kitchen_stock = {
        wh_id: wh_stock(env, wh, product_ids)
        for wh_id, wh in kitchens.items()
    }
    cdc_stock = wh_stock(env, cdc, product_ids)

    # Conservative upper-bound shortage; this sample data has zero reservations.
    # To avoid 10x distorted demand where reservations exist, REFUSE to seed.
    shortage = defaultdict(float)
    for (wh_id, pid), need in needs.items():
        on_hand, reserved = kitchen_stock[wh_id][pid]
        if reserved > 0:
            raise RuntimeError('Kitchen stock has reservations: %s %s; review first'
                               % (kitchens[wh_id].name, products[pid].display_name))
        if on_hand < 0:
            raise RuntimeError('Negative kitchen stock for %s' % products[pid].display_name)
        shortage[pid] += max(need - on_hand, 0.0)

    # Every product shortage must be assessed against the SHARED CDC stock only ONCE.
    plans = []
    for pid, gross_shortage in sorted(shortage.items()):
        p = products[pid]
        current, reserved = cdc_stock[pid]
        if reserved > 0 or current < 0:
            raise RuntimeError('CDC reserved/negative stock for %s; review first'
                               % p.display_name)
        if p.tracking != 'none':
            raise RuntimeError('Lot/serial-tracked product %s cannot be '
                               'seeded without lot information' % p.display_name)
        if 'is_storable' in p._fields and not p.is_storable:
            raise RuntimeError('Not a storable product: %s' % p.display_name)
        if 'is_storable' not in p._fields and p.type != 'product':
            raise RuntimeError('Not a storable product: %s' % p.display_name)
        rounding = p.uom_id.rounding
        if not rounding or rounding <= 0:
            raise RuntimeError('Invalid stock UoM rounding for %s' % p.display_name)

        # Desired CDC stock: ten times the CURRENT outstanding demand.
        # Not ten times a previous adjustment; repeat run becomes a no-op
        # as soon as CDC is already sufficient.
        outstanding = max(gross_shortage - current, 0.0)
        desired = max(current, MULTIPLIER * outstanding)
        desired = float_round(desired, precision_rounding=rounding, rounding_method='UP')
        addition = max(desired - current, 0.0)
        if float_compare(addition, 0.0, precision_rounding=rounding) <= 0:
            continue

        # Inventory count at exact CDC/Stock is safe only when this product has
        # no existing child-location stock: never silently override bin balances.
        root_quant = env['stock.quant'].search([
            ('product_id', '=', pid),
            ('location_id', '=', cdc.lot_stock_id.id),
            ('company_id', '=', company.id),
        ])
        if len(root_quant) > 1:
            raise RuntimeError('Multiple CDC root quants for %s' % p.display_name)
        root_qty = sum(root_quant.mapped('quantity'))
        if float_compare(root_qty, current, precision_rounding=rounding) != 0:
            raise RuntimeError('CDC product has child-location stock: %s'
                               % p.display_name)
        plans.append((p, gross_shortage, current, outstanding, desired, addition,
                      root_quant[:1]))

    print('CONFIRMED_MOS:', len(mos))
    print('KITCHENS:', ', '.join(sorted(x.name for x in kitchens.values())))
    print('MO_KITCHEN_COMPONENT_GROUPS:', len(needs))
    print('PRODUCTS_TO_ADJUST:', len(plans))
    print('PER_PRODUCT: CODE | BAHAN | GROSS_SHORT | CDC_ON_HAND | OUTSTANDING | '
          'CDC_TARGET_10X | ADD_QTY | UOM')
    for p, gross, current, outstanding, desired, addition, _ in plans:
        print('ADJUST:', p.default_code or p.id, '|',
              p.display_name, '|', fmt(gross), '|', fmt(current),
              '|', fmt(outstanding), '|', fmt(desired),
              '|', fmt(addition), '|', p.uom_id.name)

    if not APPLY:
        print('PREVIEW_ONLY_OK: No stock changes. Backup GUI database before APPLY.')
        return
    if not plans:
        print('APPLY_NO_CHANGES: stock already covers 10x target under current rule.')
        return

    # Standard inventory adjustment, not direct edits to stock.quant.quantity.
    # Single transaction: any error triggers rollback of ALL adjustments.
    adjusted = 0
    for p, gross, current, outstanding, desired, addition, existing in plans:
        quant = existing
        if not quant:
            quant = env['stock.quant'].with_context(inventory_mode=True).create({
                'product_id': p.id,
                'location_id': cdc.lot_stock_id.id,
                'company_id': company.id,
            })
        quant.with_context(inventory_mode=True).write({
            'inventory_quantity': desired,
        })
        quant.action_apply_inventory()
        adjusted += 1
        new_stock = wh_stock(env, cdc, {p.id})[p.id][0]
        if float_compare(new_stock, desired,
                         precision_rounding=p.uom_id.rounding) != 0:
            raise RuntimeError(
                'POST_ADJUST_MISMATCH for %s expected %s observed %s' %
                (p.display_name, fmt(desired), fmt(new_stock))
            )
    print('STOCK_ADJUSTED_PRODUCTS:', adjusted)
    env.cr.commit()
    print('APPLY_COMMITTED_TEST_DB_ONLY')


try:
    run(env)
except Exception:
    env.cr.rollback()
    raise
else:
    if not APPLY:
        env.cr.rollback()
