"""Clone authorization adapter for actual Fase1 MR1, no new calculation.

Requires isolated ya_material_requirement source with default-preserving
authorization hooks. Never patch module globals or permit legacy batch
generation in clone. Original Fase1 runtime remains unchanged.
"""
from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from .pp1_native_sources import DB


class PackingBatchMo1Material(models.Model):
    _inherit="ya.packing.batch"

    def _ya_mr_batch_db_allowed(self):
        self.ensure_one()
        if self.env.cr.dbname==DB:
            return bool(self.sudo().ya_pp1_design_b_snapshot)
        return super()._ya_mr_batch_db_allowed()

    def _mr_guard(self):
        if self.env.cr.dbname==DB:
            self.ensure_one()
            lock_ro_slot(self.env.cr,self.delivery_date,self.slot)
            self.env.invalidate_all()
            facts=self._ya_pp1_frozen_facts()
            if facts["company_id"]!=self.env.company.id:
                raise UserError(_("MR1 company differs from frozen PP1."))
        return super()._mr_guard()

    def action_mr_generate_native_transfers(self):
        if self.env.cr.dbname==DB:
            with self.env.cr.savepoint():
                return super().action_mr_generate_native_transfers()
        return super().action_mr_generate_native_transfers()

    def action_mr_open_pick_confirmations(self):
        if self.env.cr.dbname==DB:
            raise UserError(_("Gunakan Buat Internal Transfers Odoo untuk MR1 Design B."))
        return super().action_mr_open_pick_confirmations()

    def action_mr_print(self):
        if self.env.cr.dbname==DB:
            raise UserError(_("Print Picking Operations / Delivery Slip dari Internal Transfer native."))
        return super().action_mr_print()


class MaterialRequirementMo1Wizard(models.TransientModel):
    _inherit="ya.material.requirement.wizard"

    def _ya_mr_calculate_db_allowed(self):
        if self.env.cr.dbname==DB:
            return True
        return super()._ya_mr_calculate_db_allowed()

    def action_calculate(self):
        if self.env.cr.dbname==DB:
            self.ensure_one()
            if not self.delivery_date or not self.slot:
                raise UserError(_("Pilih tanggal kirim dan slot."))
            lock_ro_slot(self.env.cr,self.delivery_date,self.slot)
            self.env.invalidate_all()
            batch=self.env["ya.packing.batch"].search([
                ("delivery_date","=",self.delivery_date),("slot","=",self.slot),
                ("state","=","production_ok")])
            if len(batch)!=1 or not batch.ya_pp1_design_b_snapshot:
                raise UserError(_("MR1 membutuhkan batch PP1 Design B."))
            batch._mr_guard()
        return super().action_calculate()


class StockPickingMR1Origin(models.Model):
    _inherit = "stock.picking"

    @api.model_create_multi
    def create(self, vals_list):
        # Keep the old prefix: Fase1 duplicate detection searches that prefix.
        if self.env.cr.dbname == DB:
            vals_list = [dict(vals) for vals in vals_list]
            for vals in vals_list:
                batch = self.env["ya.packing.batch"].sudo().browse(vals.get("ya_mr_batch_id")).exists()
                origin = vals.get("origin") or ""
                if (batch and batch.ya_pp1_design_b_snapshot
                        and origin.startswith("YA-MR-%s-CDC-" % batch.id)):
                    vals["origin"] = "%s / %s / %s / MR1" % (
                        origin, batch.delivery_date.strftime("%Y-%b-%d"), batch.slot)
        return super().create(vals_list)
