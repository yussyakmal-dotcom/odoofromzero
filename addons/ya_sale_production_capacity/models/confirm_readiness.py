"""Read-only YA Sales confirm route adapter. No reservation or SO writes.

Normal Sale discounts are not kitchen demand. A Paket is represented by
its kitchen component quantities, never as a fabricated kitchen output.
"""
from collections import defaultdict

from odoo import models, _
from odoo.exceptions import UserError

from .confirm_capacity_math import (
    CapacityDecisionError, check_so_capacity, expand_so_package_requirements,
)


def _finished_whole(uom, value, target_uom, label):
    qty = uom._compute_quantity(value, target_uom, round=False)
    if qty <= 0 or abs(qty - round(qty)) > 1e-9:
        raise UserError(_(
            "%(label)s harus menghasilkan Qty produk jadi positif dan bulat "
            "pada satuan dasar: %(qty)s"
        ) % {"label": label, "qty": qty})
    return int(round(qty))


class SaleOrderYACapacityPreview(models.Model):
    _inherit = "sale.order"

    def _ya_prepare_capacity_confirm_readonly(self, delivery_date, slot, *, display_only=False):
        """Return preflight demand/capacity for one YA quotation, with no writes.

        NOT a concurrency-safe confirmed reservation. The eventual Confirm
        must recheck after acquiring the SAME date-slot mutex as RO/Packing.
        """
        self.ensure_one()
        if not self.ya_is_capacity_so or self.state not in ("draft", "sent"):
            raise UserError(_("Hanya Quotation YA Draft/Sent yang dapat diproses."))
        if not delivery_date or slot not in ("S1", "S2", "S3"):
            raise UserError(_("Isi Tanggal Kirim dan Slot Kirim YA."))

        planning = self.env["ya.production.planning"].sudo().search([
            ("delivery_date", "=", delivery_date),
            ("slot", "=", slot),
            ("state", "=", "published"),
        ])
        if not planning:
            raise UserError(_("Belum ada Published Planning untuk %s / %s.")
                            % (delivery_date, slot))

        routes = defaultdict(list)
        for p in planning:
            for plan_line in p.line_ids:
                routes[plan_line.product_id.id].append(plan_line)

        direct = defaultdict(int)
        packages = defaultdict(int)
        package_boms = {}
        package_bom_ids = {}
        commercial_lines = []
        component_source = {}
        pck_manual_finished = set()
        counted_product_lines = 0

        for line in self.order_line:
            if line.display_type or line.is_downpayment:
                continue
            # Odoo19 global discounts create a service line. It is a financial
            # reduction, NOT a manufactured SKU.
            if line._is_global_discount():
                continue
            product = line.product_id
            if not product:
                raise UserError(_("Quotation YA mempunyai baris tanpa produk."))
            code = product.default_code or product.display_name
            qty = _finished_whole(
                line.product_uom_id, line.product_uom_qty,
                product.uom_id, "SO SKU %s" % code,
            )
            counted_product_lines += 1
            commercial_lines.append((line.id,product.id,qty))
            if product.categ_id.complete_name == "All / Produk Jadi / Paket":
                packages[product.id] += qty
                if product.id in package_boms:
                    continue
                boms = self.env["mrp.bom"].sudo().search([
                    ("active", "=", True),
                    ("type", "=", "normal"),
                    ("product_tmpl_id", "=", product.product_tmpl_id.id),
                    "|", ("product_id", "=", False),
                    ("product_id", "=", product.id),
                ])
                if len(boms) != 1:
                    raise UserError(_(
                        "Paket %(sku)s harus mempunyai tepat satu BoM aktif; ditemukan %(count)s."
                    ) % {"sku": code, "count": len(boms)})
                bom = boms[0]
                if bom.company_id and bom.company_id != self.company_id:
                    raise UserError(_("Paket BoM company mismatch."))
                package_bom_ids[product.id] = bom.id
                output = bom.product_uom_id._compute_quantity(
                    bom.product_qty, product.uom_id, round=False)
                if abs(output - 1.0) > 1e-9:
                    raise UserError(_("Paket %s: output BoM harus tepat 1 Paket.") % code)
                parts = defaultdict(float)
                for bom_line in bom.bom_line_ids:
                    component = bom_line.product_id
                    if (component.categ_id.complete_name == "All / Produk Jadi / Paket"
                            or (component.company_id and component.company_id != self.company_id)):
                        raise UserError(_("Nested Paket or component company mismatch."))
                    converted = bom_line.product_uom_id._compute_quantity(
                        bom_line.product_qty, component.uom_id, round=False)
                    if converted <= 0:
                        raise UserError(_("Paket %s mempunyai Qty komponen tidak valid.") % code)
                    parts[component.id] += converted
                if not parts:
                    raise UserError(_("Paket %s tidak mempunyai komponen BoM.") % code)
                package_boms[product.id] = dict(parts)
                continue

            candidates = routes.get(product.id, [])
            if len(candidates) != 1:
                raise UserError(_(
                    "SKU %(sku)s tidak mempunyai tepat satu rute dapur pada "
                    "Published Planning %(date)s / %(slot)s (ditemukan %(n)s). "
                    "Gunakan SKU terjadwal atau periksa Planning dapur."
                ) % {
                    "sku": code, "date": delivery_date, "slot": slot,
                    "n": len(candidates),
                })
            direct[product.id] += qty

        if not counted_product_lines:
            raise UserError(_("Quotation YA belum mempunyai produk jadi yang dapat dikonfirmasi."))

        for pkg_id, parts in package_boms.items():
            for component_id, ratio in parts.items():
                candidates = routes.get(component_id, [])
                if len(candidates) > 1:
                    raise UserError(_(
                        "Komponen Paket SKU %(sku)s mempunyai rute dapur ganda "
                        "pada Published Planning."
                    ) % {"sku": self.env["product.product"].browse(component_id).default_code or component_id})
                kind = "KITCHEN" if len(candidates) == 1 else "PCK"
                previous = component_source.get(component_id)
                if previous and previous != kind:
                    raise UserError(_("Konflik sumber komponen Paket %s.") % component_id)
                component_source[component_id] = kind
                if kind == "KITCHEN":
                    # Odoo UoM conversion returns float (e.g. 2.0) even for
                    # integer finished-goods units. Validate then normalize
                    # before the strict pure-demand engine.
                    if abs(ratio - round(ratio)) > 1e-9:
                        raise UserError(_(
                            "Komponen Paket SKU %(sku)s menghasilkan Qty "
                            "produk jadi dapur pecahan: %(qty)s"
                        ) % {"sku": component_id, "qty": ratio})
                    package_boms[pkg_id][component_id] = int(round(ratio))
                else:
                    c = self.env["product.product"].browse(component_id)
                    if (c.categ_id.complete_name or "").startswith("All / Produk Jadi"):
                        pck_manual_finished.add(component_id)

        try:
            result = expand_so_package_requirements(
                dict(direct), dict(packages), package_boms, component_source)
        except CapacityDecisionError as exc:
            raise UserError(_("Komponen Paket tidak valid: %s") % exc) from exc

        capacity = []
        for product_id, new_qty in sorted(result["kitchen_requirements"].items()):
            candidates = routes.get(product_id, [])
            if len(candidates) != 1:
                raise UserError(_("Tidak ada satu rute Published Planning untuk SKU %s.")
                                % product_id)
            plan_line = candidates[0]
            product = plan_line.product_id
            bom = plan_line._capacity_bom()
            pt = bom.picking_type_id
            expected_wh = " ".join(
                ("Dapur " + (plan_line.planning_id.workcenter_id.name or "")
                ).casefold().split())
            actual_wh = " ".join(
                (pt.warehouse_id.name or "").casefold().split()) if pt else ""
            if (not bom.active or bom.type != "normal" or
                    bom.product_tmpl_id != product.product_tmpl_id or
                    (bom.product_id and bom.product_id != product) or
                    not pt or not pt.default_location_src_id or
                    not pt.default_location_dest_id or
                    not pt.warehouse_id or
                    pt.default_location_dest_id != pt.warehouse_id.lot_stock_id or
                    pt.company_id != self.company_id or
                    actual_wh != expected_wh):
                raise UserError(_(
                    "SKU %(sku)s: BoM/Work Center/Gudang dapur berubah "
                    "atau tidak sesuai Published Planning. Periksa routing."
                ) % {"sku": product.default_code or product.display_name})
            output = _finished_whole(
                bom.product_uom_id, bom.product_qty, product.uom_id,
                "BoM SKU %s" % (product.default_code or product.display_name),
            )
            maximum = plan_line.uom_id._compute_quantity(
                plan_line.max_capacity, product.uom_id, round=False)
            if maximum < 0 or abs(maximum - round(maximum)) > 1e-9:
                raise UserError(_("Planning Max SKU %s bukan Qty satuan dasar bulat.")
                                % (product.default_code or product.display_name))
            if not new_qty:
                continue
            try:
                # Display must show over-capacity quantities, not hide the numbers.
                # Confirm always uses the default strict path.
                if display_only:
                    preview = None
                else:
                    preview = check_so_capacity(new_qty, 0, int(round(maximum)), output)
                # This is a preflight for NEW demand only. Confirmed-SO
                # reservations and MO1/MO2 must be read under the slot lock
                # by the eventual transactional Confirm engine.
            except CapacityDecisionError as exc:
                raise UserError(_("SKU %s: %s")
                                % (product.default_code or product.display_name, exc)) from exc
            capacity.append({
                "planning_line_id": plan_line.id,
                "product_id": product_id,
                "new_qty": new_qty,
                "bom_output": output,
                "published_max": int(round(maximum)),
                "preflight": preview,
            })

        source_rows = []
        # Unsaved quotation lines have NewId identities. Display does not
        # need source identities; the Confirm path still freezes actual IDs.
        for line_id,pid,qty in ([] if display_only else commercial_lines):
            if pid in package_boms:
                parts = [dict(product_id=c,source_kind=component_source[c],
                              qty_per_package=ratio,qty=ratio*qty)
                         for c,ratio in sorted(package_boms[pid].items())]
                kind,bom_id="SO_PAKET",package_bom_ids[pid]
            else:
                parts=[dict(product_id=pid,source_kind="KITCHEN",qty=qty)]
                kind,bom_id="SO",None
            source_rows.append(dict(kind=kind,source_id=self.id,line_id=line_id,
                recipient_id=self.partner_shipping_id.id,product_id=pid,qty=qty,
                bom_id=bom_id,components=parts))
        return {
            "source_rows": sorted(source_rows,key=lambda r:r["line_id"]),
            "capacity": capacity,
            "pck_stock_requirements": result["pck_stock_requirements"],
            "pck_manual_finished_ids": sorted(pck_manual_finished),
            "package_qty": dict(packages),
            "counted_product_lines": counted_product_lines,
        }
