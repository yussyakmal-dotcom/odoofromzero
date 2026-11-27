"""Expose actual MO1 and MO2 in the existing MO Produksi menu.

Use the release relation, not origin text, to identify MO2. Keep Fase1
action unchanged outside the RO_SO clone. Native MO record rules apply.
"""
from odoo import api, models, _
from odoo.exceptions import UserError
from .pp1_native_sources import DB


class ManufacturingProductionNavigation(models.Model):
    _inherit = "mrp.production"

    @api.model
    def action_ya_open_production_mos(self):
        if not (self.env.user.has_group("mrp.group_mrp_user")
                or self.env.user.has_group("mrp.group_mrp_manager")):
            raise UserError(_("Akses MO Produksi tidak diizinkan."))
        action = self.env.ref("ya_workflow_navigation.action_ya_mo_production").read()[0]
        if self.env.cr.dbname != DB:
            return action
        # MO2 deliberately has no ya_packing_batch_line_id. Release lines
        # are immutable, one native MO per line. Read IDs with sudo only
        # because production operators need not have Packing Admin ACL.
        lines = self.env["ya.sale.mo2.release.line"].sudo().search([
            ("mo_id.company_id", "in", self.env.companies.ids)])
        action["domain"] = ["|", ("ya_packing_batch_line_id", "!=", False),
                            ("id", "in", lines.mapped("mo_id").ids)]
        return action
