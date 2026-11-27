"""Read-only stage register: one row per released MR stage, no duplicated business data."""
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
from .pp1_native_sources import DB
from .mr_stage_rules import DEFAULT_MODE
from .mr_stage_policy import MODES


class MrStageRegister(models.Model):
    _name = "ya.mr.stage.register"
    _description = "Material Requirement per Tahap"
    _auto = False
    _order = "delivery_date desc, slot, stage"
    _rec_name = "name"

    name = fields.Char(readonly=True)
    batch_id = fields.Many2one("ya.packing.batch", readonly=True)
    final_id = fields.Many2one("ya.sale.mo2.finalization", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    delivery_date = fields.Date(readonly=True)
    delivery_date_label = fields.Char(readonly=True)
    slot = fields.Selection([("S1","S1 - 05.00 WIB"),("S2","S2 - 09.00 WIB"),("S3","S3 - 11.00 WIB")], readonly=True)
    stage = fields.Selection([("mr1","MR1"),("mr2","MR2")], readonly=True)
    mo_count = fields.Integer(compute="_compute_stage")
    kitchen_count = fields.Integer(compute="_compute_stage")
    transfer_count = fields.Integer(compute="_compute_stage")
    mode_label = fields.Char(compute="_compute_stage")
    status = fields.Selection([("pending","Belum Terbit"),("issued","Transfer Terbit"),
                               ("zero","Tidak Perlu Transfer"),("done","Transfer Done"),
                               ("review","Perlu Perhatian")], compute="_compute_stage")
    plan_html = fields.Html(compute="_compute_detail")
    material_html = fields.Html(compute="_compute_detail")
    decision_html = fields.Html(compute="_compute_detail")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW ya_mr_stage_register AS
            SELECT b.id::bigint * 2 AS id, b.id AS batch_id,
                   NULL::integer AS final_id,
                   (b.ya_pp1_design_b_snapshot->'facts'->>'company_id')::integer AS company_id,
                   b.delivery_date, to_char(b.delivery_date,'YYYY-Mon-DD') AS delivery_date_label,
                   b.slot, 'mr1'::varchar AS stage,
                   'MR1 / ' || to_char(b.delivery_date,'YYYY-Mon-DD') || ' / ' || b.slot AS name
              FROM ya_packing_batch b
             WHERE b.state='production_ok' AND b.ya_pp1_design_b_snapshot IS NOT NULL
               AND b.ya_pp1_design_b_snapshot->'facts'->>'company_id' IS NOT NULL
            UNION ALL
            SELECT b.id::bigint * 2 + 1, b.id, f.id,
                   (b.ya_pp1_design_b_snapshot->'facts'->>'company_id')::integer,
                   b.delivery_date, to_char(b.delivery_date,'YYYY-Mon-DD'), b.slot, 'mr2'::varchar,
                   'MR2 / ' || to_char(b.delivery_date,'YYYY-Mon-DD') || ' / ' || b.slot
              FROM ya_packing_batch b JOIN ya_sale_mo2_finalization f ON f.batch_id=b.id
             WHERE b.state='production_ok' AND f.ya_pp2_design_b_snapshot IS NOT NULL
               AND b.ya_pp1_design_b_snapshot->'facts'->>'company_id' IS NOT NULL
               AND EXISTS (SELECT 1 FROM ya_sale_mo2_release_line l WHERE l.finalization_id=f.id)
        """)

    def _guard(self):
        self.ensure_one()
        self.check_access("read")
        if (self.env.cr.dbname != DB or self.company_id != self.env.company
                or not (self.env.user.has_group("mrp.group_mrp_manager")
                        or self.env.user.has_group("ya_store_ro.group_ya_packing_admin"))):
            raise UserError(_("Material Requirement tidak tersedia untuk database/perusahaan ini."))
        self.batch_id.check_access("read")

    def _compute_stage(self):
        for row in self:
            row.mo_count = row.kitchen_count = row.transfer_count = 0
            row.mode_label = False
            row.status = "review"
            if self.env.cr.dbname != DB or row.company_id != self.env.company:
                continue
            batch=row.batch_id
            mos=(batch.line_ids.mapped("mo_id") if row.stage=="mr1"
                 else row.final_id.sudo().line_ids.mapped("mo_id"))
            row.mo_count=len(mos)
            row.kitchen_count=len(mos.mapped("picking_type_id.warehouse_id"))
            decision=batch._ya_mr_stage_decision(row.stage)
            picks=batch._ya_mr_stage_existing(row.stage)
            row.transfer_count=len(picks)
            row.mode_label=dict(MODES)[decision.mode if decision else
                ("full" if picks else DEFAULT_MODE[row.stage])]
            if picks:
                row.status=("review" if any(p.state=="cancel" for p in picks)
                            else "done" if all(p.state=="done" for p in picks) else "issued")
            elif decision:
                row.status="review" if any(r["transfer"]>0 for r in decision.facts["rows"]) else "zero"
            else:
                row.status="pending"

    def _compute_detail(self):
        from .mr_stage_display import _table, _qty
        from collections import defaultdict
        for row in self:
            row.plan_html=row.material_html=row.decision_html=False
            if self.env.cr.dbname != DB or row.company_id != self.env.company:
                continue
            batch=row.batch_id
            mos=(batch.line_ids.mapped("mo_id") if row.stage=="mr1"
                 else row.final_id.sudo().line_ids.mapped("mo_id"))
            row.plan_html=_table(("Dapur","SKU / Nama Produk","MO","Qty Produksi","Satuan"),[
                (m.picking_type_id.warehouse_id.display_name,m.product_id.display_name,
                 m.name,_qty(m.product_qty),m.product_uom_id.name) for m in mos])
            raw=defaultdict(float)
            labels={}
            for mo in mos:
                wh=mo.picking_type_id.warehouse_id
                for m in mo.move_raw_ids.filtered(lambda m:m.state!="cancel"):
                    p=m.product_id
                    k=(wh.id,p.id)
                    raw[k]+=m.product_uom._compute_quantity(m.product_uom_qty,p.uom_id,round=False)
                    labels[k]=(wh.display_name,p.display_name,p.uom_id.name)
            row.material_html=_table(("Dapur","SKU / Bahan","Kebutuhan Penuh MO","Satuan"),[
                (labels[k][0],labels[k][1],_qty(q),labels[k][2]) for k,q in sorted(raw.items()) if q>0])
            decision=batch._ya_mr_stage_decision(row.stage)
            if decision:
                from .mr_stage_policy import decision_table
                row.decision_html=decision_table(decision.facts,self.env)

    def action_prepare(self):
        self._guard()
        return self.batch_id._ya_mr_open_stage(self.stage)

    def action_open_transfers(self):
        self._guard()
        picks=self.batch_id._ya_mr_stage_existing(self.stage)
        if not picks:
            raise UserError(_("Belum ada Internal Transfer untuk tahap ini."))
        return self.batch_id._ya_mr_stage_action(self.stage,picks)

    @api.model
    def action_open_register(self):
        if self.env.cr.dbname != DB:
            return self.env.ref("ya_material_requirement.action_ya_material_batch").read()[0]
        if not (self.env.user.has_group("mrp.group_mrp_manager")
                or self.env.user.has_group("ya_store_ro.group_ya_packing_admin")):
            raise UserError(_("Akses Material Requirement tidak diizinkan."))
        action=self.env.ref("ya_sale_production_capacity.action_ya_mr_stage_register").read()[0]
        action["domain"]=[("company_id","=",self.env.company.id)]
        return action
