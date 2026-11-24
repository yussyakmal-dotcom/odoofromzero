"""Joint Pre Produksi -> native kitchen MOs, only for Paket-tagged batches.

Unchanged ordinary batches always delegate to the original tested method.
One MO per kitchen SKU; no WO auto-generation, no Paket assembly MO here.
Package assembly and final DO are separate later standard Odoo stages.
"""
from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot


class YaPackingBatchLineJointRelease(models.Model):
    _inherit = "ya.packing.batch.line"

    def action_generate_selected_mo(self, *args, **kwargs):
        ids = list(self.ids)
        if args and isinstance(args[0], (list, tuple)):
            ids = list(args[0])
        if not ids:
            ids = self.env.context.get("active_ids") or []
        selected = self.browse(ids).exists()
        batches = selected.mapped("batch_id")
        if len(batches) != 1 or not batches.ya_has_package:
            return super().action_generate_selected_mo(*args, **kwargs)
        return self._ya_generate_joint_mos(selected, batches[0], ids)

    def _ya_check_joint_sources(self, batch):
        """Compare both original RO documents and frozen assembly BoMs."""
        current_ordinary = self.env["ya.store.ro"].search([
            ("delivery_date", "=", batch.delivery_date),
            ("slot", "=", batch.slot),
            ("state", "=", "confirmed"),
        ])
        if set(current_ordinary.ids) != set(batch.ro_ids.ids):
            raise UserError(_(
                "RO biasa Confirmed berubah setelah Pre Produksi."
            ))
        current_packages = self.env["ya.package.store.ro"].search([
            ("delivery_date", "=", batch.delivery_date),
            ("slot", "=", batch.slot),
            ("state", "=", "confirmed"),
        ])
        if set(current_packages.ids) != set(batch.ya_package_ro_ids.ids):
            raise UserError(_(
                "RO Paket Confirmed berubah setelah Pre Produksi."
            ))
        original_direct = {}
        for ro in current_ordinary:
            if ro.packing_batch_id != batch:
                raise UserError(_("Ordinary RO is not linked to this frozen batch."))
            for row in ro.line_ids.filtered(lambda rec: rec.qty_requested > 0):
                key = (ro.id, row.product_id.id)
                if key in original_direct:
                    raise UserError(_("Duplicate ordinary RO source SKU."))
                original_direct[key] = row.qty_requested
        snapshot_direct = {}
        for allocation in batch.allocation_ids:
            key = (allocation.ro_id.id, allocation.product_id.id)
            if key in snapshot_direct:
                raise UserError(_("Duplicate ordinary source allocation."))
            if allocation.ro_id.store_warehouse_id != allocation.store_warehouse_id:
                raise UserError(_("Ordinary RO warehouse changed."))
            snapshot_direct[key] = allocation.qty_requested
        if snapshot_direct != original_direct:
            raise UserError(_("Ordinary RO Qty differs from frozen Pre Produksi."))

        original_packages = {}
        for ro in current_packages:
            for row in ro.line_ids.filtered(lambda rec: rec.qty_requested > 0):
                original_packages[(ro.id, row.product_id.id)] = row.qty_requested
        frozen_packages = {}
        for demand in batch.ya_package_demand_ids:
            if (demand.batch_id != batch or
                    demand.package_ro_id.store_warehouse_id != demand.store_warehouse_id or
                    demand.package_ro_id not in current_packages):
                raise UserError(_("Frozen Paket RO source is invalid."))
            key = (demand.package_ro_id.id, demand.product_id.id)
            if key in frozen_packages:
                raise UserError(_("Duplicate frozen Paket SKU source."))
            frozen_packages[key] = demand.qty_requested
            bom = demand.bom_id
            product = demand.product_id
            if (not bom.active or bom.type != "normal" or
                    bom.product_tmpl_id != product.product_tmpl_id or
                    (bom.product_id and bom.product_id != product)):
                raise UserError(_("Paket BoM changed: %s") % product.display_name)
            bo_qty = bom.product_uom_id._compute_quantity(
                bom.product_qty, product.uom_id, round=False)
            if abs(bo_qty - 1.0) > 1e-9:
                raise UserError(_("Paket BoM must output 1: %s") % product.display_name)
            current_components = defaultdict(float)
            for raw in bom.bom_line_ids:
                current_components[raw.product_id.id] += (
                    raw.product_uom_id._compute_quantity(
                        raw.product_qty, raw.product_id.uom_id,
                        round=False))
            frozen_components = {
                component.product_id.id: component
                for component in demand.component_ids
            }
            if set(current_components) != set(frozen_components):
                raise UserError(_("Paket BOM components changed: %s")
                                % product.display_name)
            for component_id, ratio in current_components.items():
                snapshot = frozen_components[component_id]
                precision = snapshot.product_id.uom_id.rounding
                if (snapshot.batch_id != batch or
                        float_compare(snapshot.qty_per_package, ratio,
                                      precision_rounding=precision) != 0 or
                        float_compare(snapshot.qty_required,
                                      ratio * demand.qty_requested,
                                      precision_rounding=precision) != 0):
                    raise UserError(_("Paket BOM component Qty changed: %s")
                                    % product.display_name)
                if snapshot.source_kind == "kitchen":
                    if (not snapshot.kitchen_line_id or
                            snapshot.kitchen_line_id.batch_id != batch or
                            snapshot.kitchen_line_id.product_id != snapshot.product_id):
                        raise UserError(_("Paket kitchen component route changed."))
                elif snapshot.source_kind == "pck":
                    if snapshot.kitchen_line_id:
                        raise UserError(_("PCK-sourced component cannot have kitchen MO."))
                else:
                    raise UserError(_("Unknown Paket component source."))
        if frozen_packages != original_packages:
            raise UserError(_("Paket RO Qty differs from frozen Pre Produksi."))

        protected = defaultdict(float)
        for component in batch.ya_package_component_ids:
            if component.source_kind == "kitchen":
                protected[component.kitchen_line_id.id] += component.qty_required
        for line in batch.line_ids:
            required = protected[line.id]
            if (abs(required - round(required)) > 1e-9 or
                    int(round(required)) != line.ya_package_component_qty):
                raise UserError(_("Paket priority bucket changed for SKU %s.")
                                % line.reference)

    def _ya_generate_joint_mos(self, selected, batch, selected_ids):
        if not self.env.user.has_group("ya_store_ro.group_ya_packing_admin"):
            raise UserError(_("Only Packing Admin can approve Produksi OK."))
        lock_ro_slot(self.env.cr, batch.delivery_date, batch.slot)
        if batch.state != "pre_production":
            raise UserError(_("Batch already released."))
        if (not selected or len(selected) != len(set(selected_ids)) or
                set(selected.ids) != set(batch.line_ids.ids)):
            raise UserError(_(
                "Pilih SEMUA SKU dalam satu Pre Produksi sebelum Produksi OK."
            ))
        if batch.line_ids.mapped("mo_id"):
            raise UserError(_("A kitchen MO already exists for this batch."))
        self._ya_check_joint_sources(batch)

        for line in batch.line_ids:
            rows = batch.allocation_ids.filtered(lambda a: a.line_id == line)
            original = sum(rows.mapped("qty_requested"))
            allocated = sum(rows.mapped("qty_allocated"))
            shortage = sum(rows.mapped("qty_shortage"))
            extras = sum(rows.mapped("qty_surplus"))
            protected = line.ya_package_component_qty
            residual = line.qty_surplus
            if (original != line.qty_requested or
                    shortage != line.qty_shortage or
                    any(r.qty_requested + r.qty_surplus !=
                        r.qty_allocated + r.qty_shortage
                        or r.qty_allocated < 0 or r.qty_surplus < 0 or
                        r.qty_shortage < 0 or
                        (r.qty_surplus and r.qty_shortage) for r in rows) or
                    original + extras != allocated + shortage or
                    protected < 0 or residual < 0 or
                    protected + allocated + residual != line.qty_production):
                raise UserError(_("Qty allocation/Paket/MO mismatch: %s") %
                                line.reference)

        # Original kitchen MO creation semantics, with the joint gross Qty.
        # BoM output/Planning Max converted to product base UoM at snapshot.
        for line in batch.line_ids.sorted(lambda x: (
                x.kitchen_code or "", x.reference or "", x.id)):
            product = line.product_id
            plan = line.planning_id
            bom = line.bom_id
            pt = bom.picking_type_id
            if not pt or not pt.warehouse_id:
                raise UserError(_("Kitchen manufacturing operation type missing."))
            expected = " ".join(("Dapur " + (
                plan.workcenter_id.name or "")).casefold().split())
            actual = " ".join((
                pt.warehouse_id.name or "").casefold().split())
            if (plan.state != "published" or
                    plan.delivery_date != batch.delivery_date or
                    plan.slot != batch.slot or
                    expected != actual or
                    not pt.default_location_src_id or
                    not pt.default_location_dest_id or
                    pt.default_location_dest_id != pt.warehouse_id.lot_stock_id or
                    pt.company_id != self.env.company):
                raise UserError(_("Kitchen MO route changed: %s") % line.reference)
            if ((bom.product_id and bom.product_id != product) or
                    bom.product_tmpl_id != product.product_tmpl_id):
                raise UserError(_("Kitchen BoM product changed: %s") %
                                line.reference)
            output = bom.product_uom_id._compute_quantity(
                bom.product_qty, product.uom_id, round=False)
            capacity_row = plan.line_ids.filtered(
                lambda row: row.product_id == product)
            if len(capacity_row) != 1:
                raise UserError(_("Published Planning SKU no longer unique."))
            capacity = capacity_row.uom_id._compute_quantity(
                capacity_row.max_capacity, product.uom_id, round=False)
            if (abs(output - round(output)) > 1e-9 or round(output) <= 0 or
                    int(round(output)) != line.ya_kitchen_bom_output or
                    line.uom_id != product.uom_id):
                raise UserError(_("Kitchen BoM output/UoM changed after snapshot."))
            if (int(round(capacity)) != line.max_capacity or
                    abs(capacity - line.max_capacity) > 1e-9 or
                    line.qty_production <= 0 or
                    line.qty_production > line.max_capacity or
                    line.qty_production % int(round(output))):
                raise UserError(_("Kitchen MO Qty/Planning Max changed: %s")
                                % line.reference)
            mo = self.env["mrp.production"].create({
                "product_id": product.id,
                "product_qty": float(line.qty_production),
                "product_uom_id": product.uom_id.id,
                "bom_id": bom.id,
                "picking_type_id": pt.id,
                "location_src_id": pt.default_location_src_id.id,
                "location_dest_id": pt.default_location_dest_id.id,
                "company_id": pt.company_id.id,
                "date_start": fields.Datetime.now(),
                "origin": "%s / %s / %s" % (
                    batch.name, line.kitchen_code, line.reference),
                "ya_packing_batch_line_id": line.id,
            })
            mo.action_confirm()
            if mo.state in ("draft", "cancel", "done"):
                raise UserError(_("MO confirmation failed: %s") %
                                line.reference)
            line.with_context(ya_release_production_batch=True).write({
                "mo_id": mo.id,
            })

        if len(batch.line_ids) != len(batch.line_ids.mapped("mo_id")):
            raise UserError(_("Not all kitchen MOs were created."))
        if (sum(batch.allocation_ids.mapped("qty_allocated")) +
                sum(batch.line_ids.mapped("ya_package_component_qty")) +
                sum(batch.line_ids.mapped("qty_surplus")) !=
                sum(batch.line_ids.mapped("qty_production"))):
            raise UserError(_("Mixed Paket/RO MO output conservation failed."))

        batch.sudo().with_context(ya_release_production_batch=True).write({
            "state": "production_ok",
            "released_at": fields.Datetime.now(),
            "released_by": self.env.user.id,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Produksi OK - RO + Paket"),
            "res_model": "ya.packing.batch", "res_id": batch.id,
            "view_mode": "form", "views": [(False, "form")],
            "target": "current",
        }
