"""Clone-only actual FG operator integration, no new stock ledger.

Reuse the Fase1 one-click MO1 generator and existing native MO2 FG helper.
Keep their respective relational identities. PP2 must be finalized first
under the already tested source contract; all eligible MOs must be Done.
"""
from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from .pp1_native_sources import DB, PP1SourceError
from .final_packing_supply import read_final_packing_kitchen_supply


class PackingBatchFinishedIntegration(models.Model):
    _inherit="ya.packing.batch"

    def _ya_fg_db_allowed(self):
        self.ensure_one()
        if self.env.cr.dbname==DB:
            return bool(self.ya_pp1_design_b_snapshot)
        return super()._ya_fg_db_allowed()

    def _ya_fg_validate_native_picking(self,picking,moves):
        if self.env.cr.dbname!=DB:
            return super()._ya_fg_validate_native_picking(picking,moves)
        # Native reservation, not manual forcing of quantity from physical stock.
        picking.action_confirm()
        picking.action_assign()
        if picking.state!="assigned" or set(picking.move_ids.ids)!=set(moves.ids):
            raise UserError(_("Stok produk jadi bebas belum cukup untuk Packing."))
        for move in moves:
            if (move.state!="assigned" or float_compare(move.quantity,move.product_uom_qty,
                    precision_rounding=move.product_uom.rounding)!=0
                    or not move.move_line_ids or any(l.location_id!=picking.location_id
                    or l.location_dest_id!=picking.location_dest_id or l.lot_id
                    or l.owner_id or l.package_id or l.result_package_id for l in move.move_line_ids)):
                raise UserError(_("Reservasi native FG tidak lengkap atau lokasi/lot berbeda."))
        moves.write({"picked":True})
        moves.mapped("move_line_ids").write({"picked":True})
        response=picking.with_context(skip_immediate=True,skip_backorder=True,
                    cancel_backorder=True).button_validate()
        if picking.state!="done" or any(m.state!="done" for m in moves):
            raise UserError(_("Native Validate FG belum Done: %s") % str(response))

    def action_ya_fg_open_transfers(self):
        self.ensure_one()
        action=super().action_ya_fg_open_transfers()
        if self.env.cr.dbname==DB and self.ya_pp1_design_b_snapshot:
            finals=self.env["ya.sale.mo2.finalization"].sudo().search([("batch_id","=",self.id)])
            ids=(self.ya_fg_transfer_ids.ids+finals.line_ids.ya_mo2_fg_picking_ids.ids)
            action["domain"]=[("id","in",ids)]
        return action

    def action_ya_fg_move_to_packing(self):
        self.ensure_one()
        if self.env.cr.dbname!=DB:
            return super().action_ya_fg_move_to_packing()
        if not self.env.user.has_group("ya_store_ro.group_ya_packing_admin"):
            raise UserError(_("Packing Admin required for Design B FG."))
        self.check_access("read")
        with self.env.cr.savepoint():
            lock_ro_slot(self.env.cr,self.delivery_date,self.slot)
            self.env.invalidate_all()
            pp1=self._ya_pp1_frozen_facts()
            if pp1["company_id"]!=self.env.company.id:
                raise UserError(_("FG company mismatch."))
            final=self.env["ya.sale.mo2.finalization"].search([("batch_id","=",self.id)])
            if len(final)!=1 or not final.ya_pp2_design_b_snapshot:
                raise UserError(_("Finalisasi PP2 dahulu sebelum handoff ke Packing."))
            pp2=final._ya_pp2_frozen_facts()
            forecasts={r["product_id"]:r for r in pp2["sku_forecasts"]}
            existing=self.ya_fg_transfer_ids|final.line_ids.ya_mo2_fg_picking_ids
            if existing:
                # Never regenerate an incomplete previously issued handoff.
                if not self.ya_store_delivery_ids and not self.ya_package_assembly_mo_ids:
                    try:
                        read_final_packing_kitchen_supply(self)
                    except PP1SourceError as exc:
                        raise UserError(str(exc)) from exc
                return self.action_ya_fg_open_transfers()
            if self.ya_store_delivery_ids or self.ya_package_assembly_mo_ids or self.allocation_ids:
                raise UserError(_("Packing distribution already started."))
            excluded=set(x.strip() for x in (self.env["ir.config_parameter"].sudo().get_param(
                "ya_finished_packing_transfer.exclude_sku_codes","11076") or "").split(",") if x.strip())
            # Check both waves before issuing anything; current Design B
            # final supply rejects discrepancies and WIP. Do not skip a MO.
            for wave,lines in (("MO1",self.line_ids),("MO2",final.line_ids)):
                for line in lines:
                    mo=line.mo_id
                    product=mo.product_id
                    fact=forecasts[product.id]
                    route=fact["kitchen_route"]
                    qty=fact["preexisting_mo1_qty"] if wave=="MO1" else line.qty_mo2
                    finished=mo.move_finished_ids.filtered(lambda m:m.product_id==product)
                    if (mo.state!="done" or not finished or product.default_code in excluded
                            or product.tracking!="none" or not product.is_storable
                            or mo.company_id!=self.env.company or mo.bom_id.id!=fact["bom_id"]
                            or mo.picking_type_id.id!=route["picking_type_id"]
                            or mo.location_dest_id.id!=route["destination_id"]
                            or mo.location_src_id.id!=route["source_id"]
                            or any(m.state!="done" or m.location_dest_id!=mo.location_dest_id for m in finished)):
                        raise UserError(_("Semua MO1/MO2 harus Done sesuai rute asli: %s") % mo.name)
                    actual=sum(m.product_uom._compute_quantity(m.quantity,product.uom_id,round=False)
                               for m in finished)
                    planned=mo.product_uom_id._compute_quantity(mo.product_qty,product.uom_id,round=False)
                    if abs(actual-qty)>1e-7 or abs(planned-qty)>1e-7:
                        raise UserError(_("Qty hasil produksi berbeda; rekonsiliasi: %s") % mo.name)
            # Fase1 native generator remains one picking per kitchen.
            super().action_ya_fg_move_to_packing()
            # Retain tested independent MO2 native source links. Operator
            # does not click once per SKU; this is one atomic action.
            for line in final.line_ids:
                picking=line._ya_create_mo2_fg_transfer()
                self._ya_fg_validate_native_picking(picking,picking.move_ids)
            try:
                read_final_packing_kitchen_supply(self)
            except PP1SourceError as exc:
                raise UserError(str(exc)) from exc
            return self.action_ya_fg_open_transfers()
