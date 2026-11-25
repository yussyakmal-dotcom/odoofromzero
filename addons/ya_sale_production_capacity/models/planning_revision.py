from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from .planning_revision_rules import validate_revision

CLONE_DB = "erp-yussyakmal-mrp-test-RO_SO"
_TOKEN = object()


def whole(qty):
    if qty < 0 or abs(qty - round(qty)) > 1e-9:
        raise UserError(_("Quantity must be whole in its target UoM."))
    return int(round(qty))


class PlanningRevisionAudit(models.Model):
    _name = "ya.planning.revision.audit"
    _description = "Published Planning Revision Audit"
    _order = "id desc"

    planning_id = fields.Many2one("ya.production.planning", required=True, ondelete="restrict")
    planning_line_ref = fields.Integer(required=True)
    product_id = fields.Many2one("product.product", required=True, ondelete="restrict")
    delivery_date = fields.Date(required=True)
    slot = fields.Char(required=True)
    old_max = fields.Integer(required=True)
    new_max = fields.Integer(required=True)
    ro_qty = fields.Integer(required=True)
    so_qty = fields.Integer(required=True)
    ro_shortage_before = fields.Integer(required=True)
    ro_shortage_after = fields.Integer(required=True)
    operation = fields.Selection([("max", "Max"), ("delete", "Delete")], required=True)
    reason = fields.Text(required=True)
    actor_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    changed_at = fields.Datetime(required=True)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.cr.dbname != CLONE_DB or self.env.context.get("_ya_revision_token") is not _TOKEN:
            raise UserError(_("Audit may only be created by controlled revision."))
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_("Revision audit is immutable."))

    def unlink(self):
        raise UserError(_("Revision audit is immutable."))


class PlanningRevision(models.Model):
    _inherit = "ya.production.planning"

    def action_ya_open_revision(self):
        self.ensure_one()
        if self.env.cr.dbname != CLONE_DB or not self.env.user.has_group("mrp.group_mrp_manager") or self.state != "published":
            raise UserError(_("Published revision restricted to clone Manufacturing Managers."))
        return {
            "type": "ir.actions.act_window", "name": _("Revisi Published Planning"),
            "res_model": "ya.planning.revision.wizard", "view_mode": "form",
            "target": "new", "context": {"default_planning_id": self.id},
        }


class PlanningLineRevision(models.Model):
    _inherit = "ya.production.planning.line"

    def _ya_revision_allowed(self):
        return (self.env.cr.dbname == CLONE_DB
                and self.env.user.has_group("mrp.group_mrp_manager")
                and self.env.context.get("_ya_revision_token") is _TOKEN)

    def _ya_revision_facts(self):
        self.ensure_one()
        plan = self.planning_id
        product = self.product_id
        domain = [("delivery_date", "=", plan.delivery_date), ("slot", "=", plan.slot)]
        batches = self.env["ya.packing.batch"].sudo().search(domain)
        direct = self.env["ya.store.ro.line"].sudo().search([
            ("ro_id.planning_id", "=", plan.id), ("product_id", "=", product.id)])
        ro = sum(whole(l.uom_id._compute_quantity(l.qty_requested, self.uom_id, round=False))
                 for l in direct if l.ro_id.state == "confirmed")
        referenced = bool(direct)
        packages = self.env["ya.package.store.ro"].sudo().search(domain)
        for order in packages:
            for line in order.line_ids.filtered(lambda l: l.qty_requested > 0):
                pkg = line.product_id
                boms = self.env["mrp.bom"].sudo().search([
                    ("active", "=", True), ("type", "=", "normal"),
                    ("product_tmpl_id", "=", pkg.product_tmpl_id.id),
                    "|", ("product_id", "=", False), ("product_id", "=", pkg.id)])
                if len(boms) != 1 or abs(boms.product_uom_id._compute_quantity(
                        boms.product_qty, pkg.uom_id, round=False) - 1) > 1e-9:
                    raise UserError(_("Invalid Paket BoM; reconcile before revision."))
                parts = boms.bom_line_ids.filtered(lambda x: x.product_id == product)
                if parts:
                    referenced = True
                    if order.state == "confirmed":
                        qty = sum(p.product_uom_id._compute_quantity(p.product_qty, self.uom_id, round=False)
                                  for p in parts)
                        ro += whole(qty * line.uom_id._compute_quantity(
                            line.qty_requested, pkg.uom_id, round=False))
        ledger = self.env["ya.sale.capacity.reservation"].sudo().search(domain)
        confirmed = self.env["sale.order"].sudo().search([
            ("ya_is_capacity_so", "=", True), ("ya_delivery_date", "=", plan.delivery_date),
            ("ya_slot", "=", plan.slot), ("state", "in", ["sale", "done"])])
        if set(ledger.mapped("order_id").ids) != set(confirmed.ids):
            raise UserError(_("SO ledger mismatch; reconcile before revision."))
        for row in ledger:
            if (row.planning_line_id.planning_id.state != "published"
                    or row.planning_line_id.planning_id.delivery_date != plan.delivery_date
                    or row.planning_line_id.planning_id.slot != plan.slot
                    or row.product_id != row.planning_line_id.product_id):
                raise UserError(_("Invalid SO ledger."))
        relevant = ledger.filtered(lambda r: r.product_id == product)
        if any(r.planning_line_id != self for r in relevant):
            raise UserError(_("Conflicting SO kitchen route."))
        so = sum(whole(product.uom_id._compute_quantity(r.qty_required, self.uom_id, round=False))
                 for r in relevant)
        return ro, so, bool(batches), referenced

    def _ya_controlled_revision(self, new_max, reason, expected_max, delete=False):
        self.ensure_one()
        if self.env.cr.dbname != CLONE_DB or not self.env.user.has_group("mrp.group_mrp_manager"):
            raise UserError(_("Revision restricted to clone Manufacturing Managers."))
        if not (reason or "").strip():
            raise UserError(_("Revision reason required."))
        plan = self.planning_id
        lock_ro_slot(self.env.cr, plan.delivery_date, plan.slot)
        self.env.invalidate_all()
        if not self.exists() or self.planning_id.state != "published" or self.max_capacity != expected_max:
            raise UserError(_("Planning changed; reopen revision."))
        if self.planning_id != plan:
            raise UserError(_("Planning identity changed."))
        bom = self._capacity_bom()
        if not bom.active or bom.type != "normal" or bom.product_uom_id != self.uom_id:
            raise UserError(_("Invalid capacity BoM."))
        batch = whole(bom.product_qty)
        ro, so, locked, referenced = self._ya_revision_facts()
        old = self.max_capacity
        try:
            validate_revision(old, new_max, batch, ro=ro, so=so, locked=locked,
                              delete=delete, referenced=referenced)
        except ValueError as exc:
            raise UserError(str(exc)) from exc
        if not delete and old == new_max:
            raise UserError(_("Max unchanged."))
        vals = dict(planning_id=plan.id, planning_line_ref=self.id,
                    product_id=self.product_id.id, delivery_date=plan.delivery_date,
                    slot=plan.slot, old_max=old, new_max=0 if delete else new_max,
                    ro_qty=ro, so_qty=so,
                    ro_shortage_before=max(0, ro-max(0, old-so)),
                    ro_shortage_after=max(0, ro-max(0, (0 if delete else new_max)-so)),
                    operation="delete" if delete else "max", reason=reason.strip(),
                    actor_id=self.env.user.id, changed_at=fields.Datetime.now())
        guarded = self.with_context(_ya_revision_token=_TOKEN)
        if delete:
            guarded._ya_revision_unlink()
        else:
            guarded._ya_revision_write(new_max)
        self.env["ya.planning.revision.audit"].sudo().with_context(
            _ya_revision_token=_TOKEN).create(vals)
        return True
