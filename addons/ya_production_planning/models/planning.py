from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

SLOTS = [('S1', 'S1 - 05.00 WIB'), ('S2', 'S2 - 09.00 WIB'), ('S3', 'S3 - 11.00 WIB')]


class YaProductionPlanning(models.Model):
    _name = 'ya.production.planning'
    _description = 'YA Production Capacity Planning'
    _rec_name = 'name'
    _order = 'delivery_date desc, slot, kitchen_code'

    name = fields.Char(string='Planning', compute='_compute_name')
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

    @api.depends('delivery_date', 'slot', 'kitchen_code')
    def _compute_name(self):
        for rec in self:
            rec.name = 'Planning'

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def action_publish(self):
        """Publish only the selected kitchen planning, never its siblings."""
        self.ensure_one()
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Only a Manufacturing Manager may publish planning.'))
        if self.state != 'draft':
            raise UserError(_('Only Draft planning can be published.'))
        if not self.line_ids:
            raise UserError(_('Cannot publish planning without SKU lines.'))
        self.write({
            'state': 'published',
            'published_at': fields.Datetime.now(),
            'published_by': self.env.user.id,
        })
        return {'type': 'ir.actions.act_window',
                'res_model': 'ya.production.planning',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'current'}

    def write(self, vals):
        if vals.get('state') == 'published' and not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Only a Manufacturing Manager may publish planning.'))
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
    line_row = fields.Integer(string='Line Row', compute='_compute_line_row')

    @api.depends('source_row')
    def _compute_line_row(self):
        for rec in self:
            rec.line_row = max(0, rec.source_row - 1)
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
        if set(vals) - {'max_capacity'}:
            raise UserError(_('Only Max Capacity may be edited on planning lines.'))
        if any(r.planning_id.state != 'draft' for r in self):
            raise UserError(_('Cannot change Published planning lines.'))
        return super().write(vals)

    def unlink(self):
        if any(r.planning_id.state != 'draft' for r in self):
            raise UserError(_('Cannot delete Published planning lines.'))
        return super().unlink()
