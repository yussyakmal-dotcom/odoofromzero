"""Clone-only source reader for Design B PP1, not yet wired to actions.

No writes. The caller supplies a coherent transaction snapshot; release must
re-read under the shared date-slot mutex and validate cutoff, digest and roles.
Ledger is the current confirmed SO kitchen promise, not physical stock.
"""
from collections import defaultdict
from odoo import fields
from .pp1_design_b_rules import plan_pp1

DB = "erp-yussyakmal-mrp-test-RO_SO"

class PP1SourceError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise PP1SourceError(message)

def whole(value, label):
    require(value >= 0 and abs(value-round(value)) < 1e-9,
            "Invalid whole base UoM: %s" % label)
    return int(round(value))

def read_pp1_sources(env, delivery_date, slot, company):
    require(env.cr.dbname == DB, "Wrong database")
    delivery = fields.Date.to_date(delivery_date)
    require(delivery and slot in ("S1", "S2", "S3"), "Invalid date/slot")
    company.ensure_one()
    domain = [("delivery_date", "=", delivery), ("slot", "=", slot)]
    plans = env["ya.production.planning"].sudo().search(domain+[("state","=","published")])
    require(bool(plans), "No Published Planning")
    batches = env["ya.packing.batch"].sudo().search(domain)
    require(len(batches) <= 1, "Duplicate Packing Batch")
    require(not batches or batches.state == "pre_production",
            "PP1 already released: do not recalculate as unreleased")
    routes = defaultdict(list)
    for line in plans.line_ids:
        routes[line.product_id.id].append(line)

    ro_rows, pkg_rows, so_rows, pck_rows = [], [], [], []
    ro_qty, pkg_qty, so_qty = defaultdict(int), defaultdict(int), defaultdict(int)
    seen = set()
    ordinary = env["ya.store.ro"].sudo().search(domain+[("state","=","confirmed")])
    packages = env["ya.package.store.ro"].sudo().search(domain+[("state","=","confirmed")])
    for ro in ordinary:
        require(ro.store_warehouse_id.company_id == company and ro.planning_id in plans,
                "RO company/planning mismatch: %s" % ro.id)
        for row in ro.line_ids:
            require(row.qty_requested >= 0, "Negative RO: %s" % row.id)
            if not row.qty_requested:
                continue
            product = row.product_id
            candidates = routes[product.id]
            require(len(candidates) == 1 and candidates[0].planning_id == ro.planning_id,
                    "RO missing/ambiguous route: %s" % product.default_code)
            key = (ro.id, product.id)
            require(key not in seen, "Duplicate ordinary RO product")
            seen.add(key)
            qty = whole(row.uom_id._compute_quantity(row.qty_requested, product.uom_id, round=False), row.id)
            require(qty > 0, "RO converted to zero")
            ro_qty[product.id] += qty
            ro_rows.append(dict(ro_id=ro.id, line_id=row.id, store_id=ro.store_warehouse_id.id,
                                product_id=product.id, qty=qty))
    seen.clear()
    for ro in packages:
        require(ro.store_warehouse_id.company_id == company, "Paket RO company mismatch")
        for row in ro.line_ids:
            require(row.qty_requested >= 0, "Negative Paket RO")
            if not row.qty_requested:
                continue
            product = row.product_id
            key = (ro.id, product.id)
            require(key not in seen, "Duplicate Paket RO product")
            seen.add(key)
            require(product.categ_id.complete_name == "All / Produk Jadi / Paket", "Invalid Paket category")
            qty = whole(row.uom_id._compute_quantity(row.qty_requested, product.uom_id, round=False), row.id)
            require(qty > 0, "Paket converted to zero")
            boms = env["mrp.bom"].sudo().search([
                ("active","=",True), ("type","=","normal"),
                ("product_tmpl_id","=",product.product_tmpl_id.id),
                "|",("product_id","=",False),("product_id","=",product.id)])
            require(len(boms)==1, "Missing/ambiguous Paket BoM: %s" % product.default_code)
            bom = boms[0]
            require(not bom.company_id or bom.company_id == company, "Paket BoM company mismatch")
            require(abs(bom.product_uom_id._compute_quantity(bom.product_qty, product.uom_id, round=False)-1)<1e-9,
                    "Paket BoM must output 1")
            parts = defaultdict(float)
            for part in bom.bom_line_ids:
                require(part.product_id.categ_id.complete_name != "All / Produk Jadi / Paket",
                        "Nested Paket requires separate review")
                ratio = part.product_uom_id._compute_quantity(part.product_qty, part.product_id.uom_id, round=False)
                require(ratio > 0, "Nonpositive Paket component")
                parts[part.product_id.id] += ratio
            require(bool(parts), "Empty Paket BoM")
            for pid, ratio in sorted(parts.items()):
                candidates = routes[pid]
                require(len(candidates) <= 1, "Ambiguous Paket component route: %s" % pid)
                info = dict(ro_id=ro.id, line_id=row.id, store_id=ro.store_warehouse_id.id,
                            package_id=product.id, bom_id=bom.id, package_qty=qty,
                            product_id=pid, qty_per_package=ratio)
                if candidates:
                    info["qty"] = whole(ratio*qty, pid)
                    require(info["qty"]>0, "Paket kitchen component converted to zero")
                    pkg_qty[pid] += info["qty"]
                    pkg_rows.append(info)
                else:
                    # Existing owner policy permits standard supply to PCK.
                    # No claim of physical availability or automatic rerouting.
                    info["qty"] = ratio*qty
                    pck_rows.append(info)
    orders = env["sale.order"].sudo().search([
        ("ya_is_capacity_so","=",True),("ya_delivery_date","=",delivery),
        ("ya_slot","=",slot),("state","in",["sale","done"])])
    ledger = env["ya.sale.capacity.reservation"].sudo().search(domain)
    require(set(orders.ids)==set(ledger.mapped("order_id").ids), "Confirmed SO/ledger identity mismatch")
    seen.clear()
    for row in ledger:
        pid = row.product_id.id
        require(row.order_id.company_id == company and row.order_id in orders, "SO order mismatch")
        require(len(routes[pid]) == 1 and routes[pid][0] == row.planning_line_id,
                "SO ledger route mismatch: %s" % row.id)
        key = (row.order_id.id,row.planning_line_id.id)
        require(key not in seen and row.qty_required > 0, "Invalid/duplicate SO ledger")
        seen.add(key)
        so_qty[pid] += row.qty_required
        so_rows.append(dict(ledger_id=row.id, order_id=row.order_id.id,
                            planning_line_id=row.planning_line_id.id, product_id=pid,
                            qty=row.qty_required))
    result = []
    for pid in sorted(set(ro_qty)|set(pkg_qty)|set(so_qty)):
        line = routes[pid][0]
        product = line.product_id
        bom = line._capacity_bom()
        pt = bom.picking_type_id
        expected = " ".join(("Dapur "+(line.planning_id.workcenter_id.name or "")).casefold().split())
        actual = " ".join((pt.warehouse_id.name or "").casefold().split()) if pt else ""
        require(bom.active and bom.type=="normal" and bom.product_tmpl_id==product.product_tmpl_id
                and (not bom.product_id or bom.product_id==product)
                and (not bom.company_id or bom.company_id==company)
                and pt and pt.company_id==company and pt.warehouse_id
                and pt.default_location_src_id and pt.default_location_dest_id
                and pt.default_location_dest_id==pt.warehouse_id.lot_stock_id and expected==actual,
                "Invalid kitchen BoM/route: %s" % product.default_code)
        output = whole(bom.product_uom_id._compute_quantity(bom.product_qty,product.uom_id,round=False),pid)
        maximum = whole(line.uom_id._compute_quantity(line.max_capacity,product.uom_id,round=False),pid)
        calculation = plan_pp1(confirmed_so_qty=so_qty[pid],original_ro_package_qty=pkg_qty[pid],
                               original_ro_store_qty=ro_qty[pid],bom_output=output,published_max=maximum)
        result.append(dict(product_id=pid, sku=product.default_code, planning_line_id=line.id,
                           planning_id=line.planning_id.id, bom_id=bom.id, bom_output=output,
                           published_max=maximum, **calculation))
    return dict(delivery_date=str(delivery),slot=slot,company_id=company.id,
                published_plan_ids=plans.ids, batch_id=batches.id if batches else None,
                ordinary_ro_rows=ro_rows, ro_package_kitchen_rows=pkg_rows,
                ro_package_pck_rows=pck_rows, so_ledger_rows=so_rows, sku_forecasts=result,
                ro_cutoff_not_verified=True, confirmed_so_ledger_not_reexpanded=True,
                so_paket_pck_requirements_not_in_ledger=True,
                forecast_only=True)
