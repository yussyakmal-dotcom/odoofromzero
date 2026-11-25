from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PlanningRevisionWizard(models.TransientModel):
    _name = "ya.planning.revision.wizard"
    _description = "Controlled Published Planning Revision"

    planning_id = fields.Many2one("ya.production.planning", required=True, readonly=True)
    line_id = fields.Many2one("ya.production.planning.line", required=True, ondelete="cascade")
    old_max = fields.Integer(readonly=True)
    new_max = fields.Integer()
    delete_sku = fields.Boolean()
    reason = fields.Text(required=True)

    @api.onchange("line_id")
    def _onchange_line(self):
        self.old_max = self.line_id.max_capacity
        self.new_max = self.old_max

    def action_apply(self):
        self.ensure_one()
        if self.line_id.planning_id != self.planning_id:
            raise UserError(_("SKU does not belong to selected Planning."))
        self.line_id._ya_controlled_revision(
            self.new_max, self.reason, self.old_max, delete=self.delete_sku)
        return {"type": "ir.actions.act_window_close"}
