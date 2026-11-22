from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

SLOTS = [('S1', 'S1 - 05.00 WIB'), ('S2', 'S2 - 09.00 WIB'), ('S3', 'S3 - 11.00 WIB')]


class YaProductionPlanning(models.Model):
    _name = 'ya.production.planning'
    _description = 'YA Production Capacity Planning'
    _order = 'delivery_date desc, slot, kitchen_code'

    delivery_date = fields.Date(required=True, index=True)
    slot = fields.Selection(SLOTS, required=True, index=True)
    kitchen_code = fields.Char(required=True, readonly=True, index=True)
    workcenter_id = fields.Many2one('mrp.workcenter', required=True, readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('published', 'Published')],
                             required=True, default='draft', index=True)
    line_ids = fields.One2many('ya.production.planning.line', 'planning_id', copy=False)
    upload_filename = fields.Char(readonly=True)
    import_batch = fields.Char(readonly=True, index=True)
    published_at = fields.Datetime(readonly=True)
    published_by = fields.Many2one('res.users', readonly=True)
    line_count = fields.Integer(compute='_compute_line_count')
    _unique_delivery_slot_kitchen = models.Constraint(
        'UNIQUE(delivery_date, slot, kitchen_code)',
        'Only one planning is allowed per delivery date, slot, and kitchen.')

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def action_publish_batch(self):
        self.ensure_one()
        if self.state != 'draft' or not self.import_batch:
            raise UserError(_('Only a Draft with an import batch may be published.'))
        batch = self.search([('import_batch', '=', self.import_batch)])
        siblings = self.search([
            ('delivery_date', '=', self.delivery_date),
            ('slot', '=', self.slot)])
        if set(batch.ids) != set(siblings.ids):
            raise UserError(_('The selected date and slot contain other planning documents.'))
        batch.action_publish()
        return {'type': 'ir.actions.act_window',
                'res_model': 'ya.production.planning',
                'domain': [('id', 'in', batch.ids)],
                'view_mode': 'list,form'}

    def action_publish(self):
        if not self:
            return True
        dates = {(p.delivery_date, p.slot, p.import_batch) for p in self}
        if len(dates) != 1:
            raise UserError(_('Publish only one complete delivery-slot batch at a time.'))
        for rec in self:
            if rec.state != 'draft' or not rec.line_ids:
                raise UserError(_('All planning documents must be nonempty Drafts.'))
        self.write({'state': 'published',
                    'published_at': fields.Datetime.now(),
                    'published_by': self.env.user.id})
        return True

    def write(self, vals):
        protected = {'delivery_date', 'slot', 'kitchen_code', 'workcenter_id',
                     'line_ids', 'upload_filename', 'import_batch'}
        if protected.intersection(vals) and any(p.state != 'draft' for p in self):
            raise UserError(_('Published planning cannot be edited.'))
        if vals.get('state') == 'draft' and any(p.state == 'published' for p in self):
            raise UserError(_('Published planning cannot be reopened.'))
        return super().write(vals)

    def unlink(self):
        if any(p.state == 'published' for p in self):
            raise UserError(_('Published planning cannot be deleted.'))
        return super().unlink()


class YaProductionPlanningLine(models.Model):
    _name = 'ya.production.planning.line'
    _description = 'YA Production Capacity Planning Line'
    _order = 'id'

    planning_id = fields.Many2one('ya.production.planning', required=True,
                                  ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', required=True, readonly=True)
    reference = fields.Char(required=True, readonly=True)
    max_capacity = fields.Integer(required=True)
    uom_id = fields.Many2one('uom.uom', required=True, readonly=True)
    source_sheet = fields.Char(readonly=True)
    source_row = fields.Integer(readonly=True)
    _unique_planning_product = models.Constraint(
        'UNIQUE(planning_id, product_id)', 'Duplicate SKU in planning.')
    _capacity_nonnegative = models.Constraint(
        'CHECK(max_capacity >= 0)', 'Max capacity must not be negative.')

    @api.constrains('max_capacity')
    def _check_capacity(self):
        for rec in self:
            if rec.max_capacity < 0:
                raise ValidationError(_('Max capacity must not be negative.'))

    @api.model_create_multi
    def create(self, vals_list):
        plan_ids = [v['planning_id'] for v in vals_list if v.get('planning_id')]
        if plan_ids and self.env['ya.production.planning'].browse(plan_ids).filtered(
                lambda p: p.state != 'draft'):
            raise UserError(_('Cannot add lines to Published planning.'))
        return super().create(vals_list)

    def write(self, vals):
        if any(r.planning_id.state != 'draft' for r in self):
            raise UserError(_('Cannot change Published planning lines.'))
        return super().write(vals)

    def unlink(self):
        if any(r.planning_id.state != 'draft' for r in self):
            raise UserError(_('Cannot delete Published planning lines.'))
        return super().unlink()
