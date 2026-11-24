"""Read-only joint slot preview for Packing: ordinary RO + cross-kitchen Paket.

No persistent packing.batch, MO, stock move, DO, reservation, or GL side
effects. This is the staged integration/adaptor for the future ONE joint
Pre Produksi snapshot. Operators can continue their native SOP exceptions.
"""
from collections import defaultdict
import hashlib
import json

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
                direct_rows.append({
                    "ro_id": ro.id,
                    "product_id": product.id,
                    "store_id": ro.store_warehouse_id.id,
                    "qty": line.qty_requested,
                })
                candidates = routes.get(product.id, [])
                if len(candidates) != 1 or candidates[0].planning_id != ro.planning_id:
                    raise UserError(_(
                        "SKU %(sku)s has no single eligible kitchen Planning "
                        "route for its Confirmed RO. Check published slot routes."
                    ) % {"sku": product.default_code or product.display_name})
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
            (self.delivery_date, self.slot),
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
            code = self.env["product.product"].browse(item["product_id"]).default_code or item["product_id"]
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
                         (wh.code, product.default_code or product.display_name,
                          item["qty"]))

        lines.append("")
        lines.append("KEBUTUHAN PCK STOCK / SUPPLY MANUAL (belum direservasi):")
        for product_id, qty in result["pck_stock_requirements"].items():
            product = self.env["product.product"].browse(product_id)
            lines.append("%s | Qty %s %s" %
                         (product.default_code or product.display_name,
                          qty, product.uom_id.name))

        warnings = result["warnings"] + notes
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
