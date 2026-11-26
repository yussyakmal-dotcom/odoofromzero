"""Joint Packing preview + snapshot staging for ordinary RO and Paket.

Calculate Preview is read-only for business documents. Stage creates ONE
immutable real ya.packing.batch / Pre Produksi date-slot, with no MO/stock
move, DO, reservations or GL effects. Source is UNINSTALLED pending complete
Paket assembly/DO and end-to-end test, so the current ordinary workflow stays.
"""
from collections import defaultdict
import hashlib
import json

from odoo.addons.ya_store_ro.models.date_labels import format_ymondd
from odoo import fields, models, _

from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from odoo.exceptions import UserError

from odoo.addons.ya_store_ro.models.package_priority_rules import (
    plan_kitchen_capacity_with_package_priority,
)
from .joint_slot_rules import JointSlotError, plan_joint_slot


class YaPackageJointSlotPreview(models.TransientModel):
    _name = "ya.package.joint.slot.preview"
    _description = "Packing Preview - RO Toko + Paket in One Delivery Slot"

    delivery_date = fields.Date(
        string="Tanggal Kirim", required=True,
        default=fields.Date.context_today,
    )
    slot = fields.Selection(
        [("S1", "S1 - 05.00 WIB"),
         ("S2", "S2 - 09.00 WIB"),
         ("S3", "S3 - 11.00 WIB")],
        required=True, default="S1",
    )
    summary = fields.Text(string="Konsolidasi Terpadu (Read Only)", readonly=True)
    ordinary_ro_count = fields.Integer(readonly=True)
    package_ro_count = fields.Integer(readonly=True)
    kitchen_sku_count = fields.Integer(readonly=True)
    kitchen_mo_qty = fields.Integer(readonly=True)
    pending_internal_transfer = fields.Integer(readonly=True)
    note = fields.Text(readonly=True)
    source_digest = fields.Char(readonly=True, copy=False)
    has_shortage = fields.Boolean(readonly=True)
    accept_shortage = fields.Boolean(string="Saya menyetujui pengurangan jatah RO toko")

    def _build_joint_plan(self):
        self.ensure_one()
        if not self.env.user.has_group("ya_store_ro.group_ya_packing_admin"):
            raise UserError(_("Only Packing Admin may consolidate RO."))
        if not self.delivery_date or not self.slot:
            raise UserError(_("Choose delivery date and slot."))

        ordinary = self.env["ya.store.ro"].search([
            ("delivery_date", "=", self.delivery_date),
            ("slot", "=", self.slot),
            ("state", "=", "confirmed"),
        ])
        packages = self.env["ya.package.store.ro"].search([
            ("delivery_date", "=", self.delivery_date),
            ("slot", "=", self.slot),
            ("state", "=", "confirmed"),
        ])
        if not ordinary and not packages:
            raise UserError(_("No Confirmed RO (ordinary or Paket) for this slot."))

        # Routing uses the actual published Planning date+slot. It is NOT
        # guessed from product category, code, BoM name or an imaginary kitchen.
        plannings = self.env["ya.production.planning"].search([
            ("delivery_date", "=", self.delivery_date),
            ("slot", "=", self.slot),
            ("state", "=", "published"),
        ])
        routes = defaultdict(list)
        for planning in plannings:
            for line in planning.line_ids:
                if line.max_capacity > 0:
                    routes[line.product_id.id].append(line)

        direct_rows = []
        package_rows = []
        required_kitchen_products = set()
        notes = []
        for ro in ordinary:
            if ro.planning_id.state != "published":
                raise UserError(_("Ordinary RO %s is not linked to Published Planning.") % ro.name)
            if ro.planning_id.delivery_date != self.delivery_date or ro.planning_id.slot != self.slot:
                raise UserError(_("Ordinary RO %s has mismatched date/slot Planning.") % ro.name)
            for line in ro.line_ids:
                if line.qty_requested <= 0:
                    continue
                product = line.product_id
                candidates = routes.get(product.id, [])
                if len(candidates) != 1 or candidates[0].planning_id != ro.planning_id:
                    raise UserError(_(
                        "SKU %(sku)s has no single eligible kitchen Planning "
                        "route for its Confirmed RO. Check published slot routes."
                    ) % {"sku": product.with_context(display_default_code=True).display_name})
                if line.uom_id != candidates[0].uom_id:
                    raise UserError(_(
                        "RO/Planning UoM differs for SKU %s. Verify the "
                        "existing Confirmed RO before joint consolidation."
                    ) % (product.with_context(display_default_code=True).display_name))
                # Historical RO stores Qty in the published Planning UoM,
                # while joint kitchen MOs, Paket components and store DOs
                # all use the product BASE UoM. Convert rather than silently
                # treating one Uter, box, etc. as one individual item.
                qty_base = line.uom_id._compute_quantity(
                    line.qty_requested, product.uom_id, round=False)
                if abs(qty_base - round(qty_base)) > 1e-9:
                    raise UserError(_(
                        "RO SKU %s converts to a fractional finished unit; "
                        "review source UoM with Packing."
                    ) % (product.with_context(display_default_code=True).display_name))
                direct_rows.append({
                    "ro_id": ro.id,
                    "product_id": product.id,
                    "store_id": ro.store_warehouse_id.id,
                    "qty": int(round(qty_base)),
                })
                required_kitchen_products.add(product.id)

        Bom = self.env["mrp.bom"].sudo()
        for ro in packages:
            for line in ro.line_ids:
                if line.qty_requested <= 0:
                    continue
                product = line.product_id
                if product.categ_id.complete_name != "All / Produk Jadi / Paket":
                    notes.append("REVIEW Paket category: %s" % product.display_name)
                boms = Bom.search([
                    ("active", "=", True), ("type", "=", "normal"),
                    ("product_tmpl_id", "=", product.product_tmpl_id.id),
                    "|", ("product_id", "=", False),
                    ("product_id", "=", product.id),
                ])
                if len(boms) != 1:
                    raise UserError(_(
                        "Paket %s needs one active normal assembly BoM."
                    ) % product.display_name)
                bom = boms[0]
                finished_qty = bom.product_uom_id._compute_quantity(
                    bom.product_qty, product.uom_id, round=False)
                if abs(finished_qty - 1) > 1e-9:
                    raise UserError(_(
                        "Paket %s assembly BoM must produce exactly 1 Paket."
                    ) % product.display_name)
                components = defaultdict(float)
                for bom_line in bom.bom_line_ids:
                    component = bom_line.product_id
                    qty = bom_line.product_uom_id._compute_quantity(
                        bom_line.product_qty, component.uom_id, round=False)
                    if qty <= 0:
                        raise UserError(_("BoM component Qty must be positive: %s")
                                        % component.display_name)
                    components[component.id] += qty
                if not components:
                    raise UserError(_("Empty Paket assembly BoM: %s") % product.display_name)
                component_values = []
                for component_id, qty_per_package in sorted(components.items()):
                    component = self.env["product.product"].browse(component_id)
                    candidates = routes.get(component_id, [])
                    if len(candidates) == 1:
                        kind = "KITCHEN"
                        required_kitchen_products.add(component_id)
                    else:
                        # A native PCK stock or manual internal transfer is
                        # permitted by 20-year SOP. No fake kitchen Planning.
                        kind = "PCK"
                        if (component.categ_id.complete_name or "").startswith(
                                "All / Produk Jadi"):
                            notes.append(
                                "MANUAL PCK SOURCE: %s (published kitchen routes: %s) "
                                "- confirm stock/transfer with Packing" %
                                (component.display_name, len(candidates)))
                    component_values.append({
                        "product_id": component_id,
                        "qty_per_package": qty_per_package,
                        "source_kind": kind,
                    })
                package_rows.append({
                    "ro_id": ro.id,
                    "bom_id": bom.id,
                    "product_id": product.id,
                    "store_id": ro.store_warehouse_id.id,
                    "qty": line.qty_requested,
                    "components": component_values,
                })

        kitchen_specs = {}
        for product_id in sorted(required_kitchen_products):
            candidates = routes.get(product_id) or []
            if len(candidates) != 1:
                raise UserError(_(
                    "Kitchen SKU %s has ambiguous Published Planning for this slot."
                ) % product_id)
            item = candidates[0]
            bom = item._capacity_bom()
            output = bom.product_uom_id._compute_quantity(
                bom.product_qty, item.product_id.uom_id, round=False)
            if output <= 0 or int(output) != output:
                raise UserError(_("Invalid kitchen BoM output: %s") %
                                item.product_id.display_name)
            capacity = item.uom_id._compute_quantity(
                item.max_capacity, item.product_id.uom_id, round=False)
            if capacity < 0 or int(capacity) != capacity:
                raise UserError(_(
                    "Kitchen Planning Max for SKU %s does not convert to "
                    "a whole output quantity. Review its UoM."
                ) % item.product_id.display_name)
            kitchen_specs[product_id] = {
                "planning_id": item.planning_id.id,
                "kitchen_code": item.planning_id.kitchen_code,
                "bom_id": bom.id,
                "bom_output": int(output),
                "max_capacity": int(capacity),
            }

        try:
            result = plan_joint_slot(
                direct_rows, package_rows, kitchen_specs,
                plan_kitchen_capacity_with_package_priority)
        except JointSlotError as exc:
            raise UserError(_("Joint RO/Paket preview cannot calculate: %s") % exc)

        return result, ordinary, packages, package_rows, direct_rows, notes

    def _plan_digest(self, result, ordinary, packages):
        """Canonical immutable-source signature of Packing's displayed preview."""
        data = {
            "date": str(self.delivery_date), "slot": self.slot,
            "ordinary_ids": sorted(ordinary.ids),
            "package_ids": sorted(packages.ids),
            "joint_plan": result,
        }
        payload = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def action_preview(self):
        self.ensure_one()
        result, ordinary, packages, package_rows, direct_rows, notes = (
            self._build_joint_plan()
        )
        lines = [
            "RO TERPADU - Tanggal %s / Slot %s" %
            (format_ymondd(self.delivery_date), self.slot),
            "RO biasa Confirmed: %s | RO Paket Confirmed: %s" %
            (len(ordinary), len(packages)),
            "MO dapur: %s SKU | Qty rencana: %s" %
            (len(result["kitchen_mo_plans"]), result["total_kitchen_mo_qty"]),
            "Sisa untuk Internal Transfer standar: %s" %
            result["total_pending_internal_transfer"],
            "",
            "RENCANA PER DAPUR / SKU (Paket lebih dulu, kemudian RO toko):",
        ]
        for item in result["kitchen_mo_plans"]:
            code = self.env["product.product"].browse(item["product_id"]).with_context(display_default_code=True).display_name
            lines.append(
                "%s / %s | Paket %s | RO toko %s | MO %s | Internal Transfer %s | %s" %
                (item["kitchen_code"], code, item["package_component_qty"],
                 item["direct_store_requested"], item["qty_production"],
                 item["qty_pending_internal_transfer"], item["status"]))
            for store, allocation in sorted(item["store_allocations"].items()):
                wh = self.env["stock.warehouse"].browse(store)
                lines.append(
                    "  Toko %s: RO %s + Surplus %s - Kekurangan %s = Jatah %s" %
                    (wh.code, allocation["requested"], allocation["surplus"],
                     allocation["shortage"], allocation["allocated"]))

        lines.append("")
        lines.append("PAKET JADI YANG HARUS DIRAKIT DI PACKING (BoM output = 1):")
        for item in result["package_store_delivery"]:
            product = self.env["product.product"].browse(item["product_id"])
            wh = self.env["stock.warehouse"].browse(item["store_id"])
            lines.append("%s | %s | Qty %s" %
                         (wh.code, product.with_context(display_default_code=True).display_name,
                          item["qty"]))

        lines.append("")
        lines.append("KEBUTUHAN PCK STOCK / SUPPLY MANUAL (belum direservasi):")
        for product_id, qty in result["pck_stock_requirements"].items():
            product = self.env["product.product"].browse(product_id)
            lines.append("%s | Qty %s %s" %
                         (product.with_context(display_default_code=True).display_name,
                          qty, product.uom_id.name))

        warnings = []
        for warning in result["warnings"]:
            # Pure planner warnings identify products by numeric record ID.
            # Convert only known product warning prefixes for operator display.
            for prefix in ("Paket ", "Kitchen SKU "):
                if warning.startswith(prefix):
                    tail = warning[len(prefix):]
                    raw_id = tail.split(" ", 1)[0].rstrip(":")
                    if raw_id.isdigit():
                        product = self.env["product.product"].browse(int(raw_id)).exists()
                        if product:
                            warning = prefix + product.with_context(display_default_code=True).display_name + tail[len(raw_id):]
                    break
            warnings.append(warning)
        warnings += notes
        self.write({
            "ordinary_ro_count": len(ordinary),
            "package_ro_count": len(packages),
            "kitchen_sku_count": len(result["kitchen_mo_plans"]),
            "kitchen_mo_qty": result["total_kitchen_mo_qty"],
            "pending_internal_transfer": result["total_pending_internal_transfer"],
            "summary": "\n".join(lines),
            "note": "\n".join(warnings) if warnings else
            "Tidak ada catatan routing. Ini masih preview; bukan Produksi OK.",
            "source_digest": self._plan_digest(result, ordinary, packages),
            "has_shortage": any(
                sum(x["shortage"] for x in item["store_allocations"].values())
                for item in result["kitchen_mo_plans"]
            ),
            "accept_shortage": False,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Packing - Preview RO + Paket"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }

    def action_move_to_preproduction(self):
        """Freeze ONE date-slot for both RO streams. No MO/stock operations."""
        self.ensure_one()
        if not self.env.user.has_group("ya_store_ro.group_ya_packing_admin"):
            raise UserError(_("Only Packing Admin can stage Pre Produksi."))
        if not self.source_digest:
            raise UserError(_("Hitung Konsolidasi RO + Paket dahulu."))

        # The exact mutex used by normal RO confirmations and qty corrections.
        lock_ro_slot(self.env.cr, self.delivery_date, self.slot)
        Batch = self.env["ya.packing.batch"]
        if Batch.search_count([
            ("delivery_date", "=", self.delivery_date),
            ("slot", "=", self.slot),
        ]):
            raise UserError(_(
                "Pre Produksi already exists for this delivery date and slot."
            ))

        result, ordinary, packages, package_rows, direct_rows, _notes = (
            self._build_joint_plan()
        )
        if not packages:
            raise UserError(_(
                "Tidak ada RO Paket Confirmed. Gunakan alur RO biasa yang sudah berjalan."
            ))
        if self._plan_digest(result, ordinary, packages) != self.source_digest:
            raise UserError(_(
                "RO, BoM, atau Planning berubah setelah preview. "
                "Hitung Konsolidasi ulang agar jatah final tetap jelas."
            ))
        if any(ro.packing_batch_id for ro in ordinary):
            raise UserError(_("An ordinary RO has already entered Pre Produksi."))
        blocked = [
            item for item in result["kitchen_mo_plans"]
            if item["status"].startswith("blocked") or
               item["qty_production"] <= 0
        ]
        if blocked:
            raise UserError(_(
                "Periksa Planning Max/BoM SKU dapur sebelum membuat Pre Produksi: %s."
            ) % ", ".join(str(x["product_id"]) for x in blocked))
        if self.has_shortage and not self.accept_shortage:
            raise UserError(_(
                "Ada kekurangan jatah RO toko setelah prioritas Paket. "
                "Periksa hasil prorata dan setujui pengurangan jatah."
            ))

        lines = []
        Products = self.env["product.product"]
        for item in result["kitchen_mo_plans"]:
            product = Products.browse(item["product_id"])
            plan = self.env["ya.production.planning"].browse(item["planning_id"])
            bom = self.env["mrp.bom"].browse(item["bom_id"])
            pt = bom.picking_type_id
            if (plan.state != "published" or not pt or
                    not pt.warehouse_id or not pt.default_location_src_id
                    or not pt.default_location_dest_id or
                    pt.company_id != self.env.company):
                raise UserError(_("Missing or invalid kitchen MO route for %s.")
                                % product.display_name)
            expected = " ".join(("Dapur " +
                (plan.workcenter_id.name or "")).casefold().split())
            actual = " ".join((pt.warehouse_id.name or "").casefold().split())
            if expected != actual or pt.default_location_dest_id != pt.warehouse_id.lot_stock_id:
                raise UserError(_(
                    "Dapur SKU %s does not match the MO finished-goods warehouse."
                ) % product.display_name)
            if ((bom.product_id and bom.product_id != product) or
                    bom.product_tmpl_id != product.product_tmpl_id):
                raise UserError(_("Kitchen BoM product mismatch: %s") %
                                product.display_name)
            if item["qty_production"] > item["max_capacity"]:
                raise UserError(_("Kitchen MO exceeds Published Planning Max: %s")
                                % product.display_name)
            if item["qty_production"] % item["bom_output"]:
                raise UserError(_("Kitchen MO not rounded to a whole BoM: %s")
                                % product.display_name)
            lines.append((0, 0, {
                "planning_id": plan.id,
                "kitchen_code": item["kitchen_code"],
                "product_id": product.id,
                "reference": product.default_code or str(product.id),
                "bom_id": bom.id,
                "qty_requested": item["direct_store_requested"],
                "ya_package_component_qty": item["package_component_qty"],
                "ya_kitchen_bom_output": item["bom_output"],
                "qty_production": item["qty_production"],
                "qty_surplus": item["qty_pending_internal_transfer"],
                "qty_shortage": sum(
                    a["shortage"] for a in item["store_allocations"].values()
                ),
                "max_capacity": item["max_capacity"],
                "uom_id": product.uom_id.id,
            }))

        # Same canonical date-slot as ordinary Packing, no parallel fake
        # kitchen Planning or separate production batch.
        batch = Batch.with_context(ya_create_production_batch=True).create({
            "delivery_date": self.delivery_date,
            "slot": self.slot,
            "state": "pre_production",
            "ya_has_package": True,
            "ro_ids": [(6, 0, ordinary.ids)],
            "ya_package_ro_ids": [(6, 0, packages.ids)],
            "line_ids": lines,
            "staged_by": self.env.user.id,
            "staged_at": fields.Datetime.now(),
        })
        by_product = {line.product_id.id: line for line in batch.line_ids}
        if len(by_product) != len(batch.line_ids):
            raise UserError(_("Duplicate kitchen SKU in joint snapshot."))

        # RO-based shop deliveries remain on the existing allocation model.
        # Store extras may be positive. Unallocated round-up remains on
        # batch.line.qty_surplus, for separate native internal transfer.
        source_by_store = {}
        for row in direct_rows:
            key = (row["product_id"], row["store_id"])
            if key in source_by_store:
                raise UserError(_("Duplicate ordinary RO source for SKU/store."))
            source_by_store[key] = row["ro_id"]
        Allocation = self.env["ya.packing.batch.allocation"].with_context(
            ya_create_production_batch=True)
        for item in result["kitchen_mo_plans"]:
            line = by_product[item["product_id"]]
            for store, a in sorted(item["store_allocations"].items()):
                source_ro = source_by_store.get((item["product_id"], store))
                if not source_ro:
                    raise UserError(_("Missing original RO for kitchen allocation."))
                Allocation.create({
                    "batch_id": batch.id, "line_id": line.id,
                    "ro_id": source_ro,
                    "kitchen_code": item["kitchen_code"],
                    "reference": line.reference,
                    "product_id": item["product_id"],
                    "store_warehouse_id": store,
                    "qty_requested": a["requested"],
                    "qty_surplus": a["surplus"],
                    "qty_shortage": a["shortage"],
                    "qty_allocated": a["allocated"],
                })

        Demand = self.env["ya.packing.package.demand"].with_context(
            ya_package_create_joint_snapshot=True)
        Component = self.env["ya.packing.package.component"].with_context(
            ya_package_create_joint_snapshot=True)
        for request in package_rows:
            pkg = self.env["product.product"].browse(request["product_id"])
            demand = Demand.create({
                "batch_id": batch.id, "package_ro_id": request["ro_id"],
                "product_id": pkg.id,
                "store_warehouse_id": request["store_id"],
                "bom_id": request["bom_id"],
                "qty_requested": request["qty"],
            })
            for comp in request["components"]:
                product = Products.browse(comp["product_id"])
                is_kitchen = comp["source_kind"] == "KITCHEN"
                linked = by_product.get(product.id) if is_kitchen else None
                if is_kitchen and not linked:
                    raise UserError(_(
                        "Missing kitchen MO line for Paket component %s."
                    ) % product.display_name)
                Component.create({
                    "batch_id": batch.id,
                    "demand_id": demand.id,
                    "product_id": product.id,
                    "source_kind": "kitchen" if is_kitchen else "pck",
                    "kitchen_line_id": linked.id if linked else False,
                    "uom_id": product.uom_id.id,
                    "qty_per_package": comp["qty_per_package"],
                    "qty_required": comp["qty_per_package"] * request["qty"],
                })

        if ordinary:
            ordinary.sudo().with_context(
                ya_stage_or_reset_packing=True).write({
                    "packing_batch_id": batch.id,
                })
        return {
            "type": "ir.actions.act_window",
            "name": _("Pre Produksi - RO + Paket"),
            "res_model": "ya.packing.batch.line",
            "view_mode": "list",
            "views": [(self.env.ref(
                "ya_store_ro.view_ya_packing_preproduction_line_list").id,
                "list")],
            "domain": [("batch_id", "=", batch.id)],
            "target": "current",
        }
