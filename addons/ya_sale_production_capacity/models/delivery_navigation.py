"""Open issued native Fase2 deliveries and receipts; no generation or stock mutation."""
from odoo import api, models, _
from odoo.exceptions import UserError
from .pp1_native_sources import DB


class DeliveryNavigation(models.Model):
    _inherit = "stock.picking"

    @api.model
    def action_ya_open_customer_store_deliveries(self):
        if not any(self.env.user.has_group(g) for g in (
            "mrp.group_mrp_manager", "ya_store_ro.group_ya_packing_admin",
            "stock.group_stock_manager")):
            raise UserError(_("Akses DO Customer & Toko tidak diizinkan."))
        if self.env.cr.dbname != DB:
            return self.env.ref("ya_packing_store_delivery.action_ya_store_distribution_batches").read()[0]
        # Sudo only to obtain approved document identities. Native picking
        # search and resulting action retain actor ACLs and record rules.
        distributions = self.env["ya.final.packing.distribution"].sudo().search([
            ("release_id.company_id", "=", self.env.company.id)])
        customers = distributions.mapped("customer_ids").ids
        dispatches = distributions.mapped("dispatch_ids").ids
        receipts = self.search([("company_id", "=", self.env.company.id),
            ("ya_source_dispatch_id", "in", dispatches),
            ("ya_store_stage", "=", "receipt")]).ids
        visible = self.search([("company_id", "=", self.env.company.id),
            ("id", "in", customers + dispatches + receipts)])
        return dict(type="ir.actions.act_window", name=_("DO Cust & Toko"),
            res_model="stock.picking", view_mode="list,form",
            domain=[("id", "in", visible.ids)], context={"create":False},
            target="current")
