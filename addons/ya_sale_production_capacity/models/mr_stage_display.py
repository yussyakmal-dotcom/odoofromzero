"""Separate visible MR1/MR2 plans without changing native material arithmetic."""
from collections import defaultdict

from markupsafe import Markup
from odoo import fields, models, _
from odoo.exceptions import UserError
from .pp1_native_sources import DB
from .mr_stage_policy import decision_table, MODES


def _table(headers, rows):
    head = Markup("").join(Markup("<th>{}</th>").format(h) for h in headers)
    body = Markup("").join(Markup("<tr>{}</tr>").format(
        Markup("").join(Markup("<td>{}</td>").format(v) for v in row)
    ) for row in rows)
    return Markup('<div class="table-responsive"><table class="table table-sm table-bordered"><thead><tr>{}</tr></thead><tbody>{}</tbody></table></div>').format(head, body)


def _qty(q):
    return ("%.8f" % q).rstrip("0").rstrip(".")


class PackingBatchMRStageDisplay(models.Model):
    _inherit = "ya.packing.batch"

    ya_mr1_plan_html = fields.Html(compute="_compute_ya_mr_stage_display")
    ya_mr2_plan_html = fields.Html(compute="_compute_ya_mr_stage_display")
    ya_mr2_material_html = fields.Html(compute="_compute_ya_mr_stage_display")
    ya_mr2_ready = fields.Boolean(compute="_compute_ya_mr_stage_display")
    ya_mr2_has_mo = fields.Boolean(compute="_compute_ya_mr_stage_display")
    ya_mr2_transfer_count = fields.Integer(compute="_compute_ya_mr_stage_display")
    ya_mr1_issued = fields.Boolean(compute="_compute_ya_mr_stage_display")
    ya_mr2_issued = fields.Boolean(compute="_compute_ya_mr_stage_display")
    ya_mr1_method_status = fields.Char(compute="_compute_ya_mr_stage_display")
    ya_mr2_method_status = fields.Char(compute="_compute_ya_mr_stage_display")
    ya_mr1_decision_html = fields.Html(compute="_compute_ya_mr_stage_display")
    ya_mr2_decision_html = fields.Html(compute="_compute_ya_mr_stage_display")

    def _compute_ya_mr_stage_display(self):
        for batch in self:
            batch.ya_mr1_plan_html = False
            batch.ya_mr2_plan_html = False
            batch.ya_mr2_material_html = False
            batch.ya_mr2_ready = False
            batch.ya_mr2_has_mo = False
            batch.ya_mr2_transfer_count = 0
            batch.ya_mr1_issued = False
            batch.ya_mr2_issued = False
            batch.ya_mr1_method_status = False
            batch.ya_mr2_method_status = False
            batch.ya_mr1_decision_html = False
            batch.ya_mr2_decision_html = False
            if self.env.cr.dbname != DB or not batch.ya_pp1_design_b_snapshot:
                continue
            if not (self.env.user.has_group("mrp.group_mrp_manager")
                    or self.env.user.has_group("ya_store_ro.group_ya_packing_admin")):
                continue
            if batch.ya_pp1_design_b_snapshot["facts"]["company_id"] != self.env.company.id:
                continue
            headers = ("Dapur", "SKU / Nama Produk", "MO", "Qty Produksi", "Satuan", "Status MO")
            def plan(mos):
                return _table(headers, [
                    (mo.picking_type_id.warehouse_id.display_name, mo.product_id.display_name,
                     mo.name, _qty(mo.product_qty), mo.product_uom_id.name,
                     dict(mo._fields["state"]._description_selection(mo.env)).get(mo.state, mo.state))
                    for mo in mos.sorted(key=lambda m:(m.picking_type_id.warehouse_id.id,m.product_id.id,m.id))
                ])
            batch.ya_mr1_plan_html = plan(batch.line_ids.mapped("mo_id"))
            for stage,default in (("mr1","Full Requirement"),("mr2","Shortage Requirement")):
                decision=batch._ya_mr_stage_decision(stage)
                existing=batch._ya_mr_stage_existing(stage)
                batch["ya_"+stage+"_issued"]=bool(decision or existing)
                if decision:
                    batch["ya_"+stage+"_method_status"]=dict(MODES)[decision.mode]+(
                        " - Sudah terbit" if existing else " - Tidak perlu transfer")
                    batch["ya_"+stage+"_decision_html"]=decision_table(decision.facts,self.env)
                elif existing:
                    batch["ya_"+stage+"_method_status"]="Full Requirement - Dokumen sudah terbit"
                else:
                    batch["ya_"+stage+"_method_status"]=default+" - Default, belum terbit"
            finals = self.env["ya.sale.mo2.finalization"].sudo().search([("batch_id","=",batch.id)])
            if len(finals) != 1 or not finals.ya_pp2_design_b_snapshot:
                batch.ya_mr2_plan_html = _("MR2 belum tersedia. Selesaikan Closing dan Produksi OK 2.")
                continue
            final = finals[0]
            batch.ya_mr2_ready = True
            mos = final.line_ids.mapped("mo_id")
            batch.ya_mr2_has_mo = bool(mos)
            pickings = batch._ya_mr_stage_existing("mr2")
            batch.ya_mr2_transfer_count = len(pickings)
            if not mos:
                batch.ya_mr2_method_status = _("Tidak perlu MR2 - PP2 tanpa MO2")
                batch.ya_mr2_plan_html = _("PP2 selesai tanpa tambahan MO2.")
                continue
            batch.ya_mr2_plan_html = plan(mos)
            raw = defaultdict(float)
            labels = {}
            for mo in mos:
                wh = mo.picking_type_id.warehouse_id
                for move in mo.move_raw_ids.filtered(lambda m:m.state != "cancel"):
                    product = move.product_id
                    key = (wh.id, product.id)
                    raw[key] += move.product_uom._compute_quantity(
                        move.product_uom_qty, product.uom_id, round=False)
                    labels[key] = (wh.display_name, product.display_name, product.uom_id.name)
            rows = [(labels[k][0], labels[k][1], _qty(q), labels[k][2])
                    for k,q in sorted(raw.items()) if q > 0]
            batch.ya_mr2_material_html = _table(
                ("Dapur", "Bahan", "Kebutuhan Penuh MO2", "Satuan"), rows)

    def action_mr2_open_native_transfers(self):
        self.ensure_one()
        self._mr_guard()
        final = self.env["ya.sale.mo2.finalization"].sudo().search([("batch_id","=",self.id)])
        if len(final) != 1 or not final.ya_pp2_design_b_snapshot:
            raise UserError(_("MR2 membutuhkan Produksi OK 2."))
        ids = self._ya_mr_stage_existing("mr2").ids
        return dict(type="ir.actions.act_window", name=_("Internal Transfer MR2"),
                    res_model="stock.picking", view_mode="list,form",
                    domain=[("id","in",ids)], context={"create":False}, target="current")
