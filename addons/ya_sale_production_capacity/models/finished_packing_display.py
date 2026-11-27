"""Read-only FG handoff presentation, separate from legacy Packing batch views."""
from datetime import datetime
from zoneinfo import ZoneInfo
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .pp1_native_sources import DB
from .mr_stage_display import _table, _qty


class FinishedPackingDisplay(models.Model):
    _inherit = "ya.packing.batch"

    ya_fg_mo1_count = fields.Integer(compute="_compute_ya_fg_display")
    ya_fg_mo2_count = fields.Integer(compute="_compute_ya_fg_display")
    ya_fg_total_mo_count = fields.Integer(compute="_compute_ya_fg_display")
    ya_fg_total_kitchen_count = fields.Integer(compute="_compute_ya_fg_display")
    ya_fg_all_transfer_count = fields.Integer(compute="_compute_ya_fg_display")
    ya_fg_display_status = fields.Selection([
        ("waiting_pp2","Menunggu Produksi OK2"),("waiting_mo","Menunggu MO Done"),
        ("ready","Siap ke Packing"),("transferred","Sudah ke Packing"),
        ("review","Perlu Perhatian"),("expired","Expired")],
        compute="_compute_ya_fg_display")
    ya_fg_detail_html = fields.Html(compute="_compute_ya_fg_display")

    def _ya_fg_display_final(self):
        self.ensure_one()
        return self.env["ya.sale.mo2.finalization"].sudo().search([("batch_id","=",self.id)])

    def _compute_ya_fg_display(self):
        for batch in self:
            batch.ya_fg_mo1_count = batch.ya_fg_mo2_count = 0
            batch.ya_fg_total_mo_count = batch.ya_fg_total_kitchen_count = 0
            batch.ya_fg_all_transfer_count = 0
            batch.ya_fg_display_status = "review"
            batch.ya_fg_detail_html = False
            if self.env.cr.dbname != DB or not batch.ya_pp1_design_b_snapshot:
                continue
            if batch.ya_pp1_design_b_snapshot["facts"]["company_id"] != self.env.company.id:
                continue
            if not (self.env.user.has_group("ya_store_ro.group_ya_packing_admin")
                    or self.env.user.has_group("stock.group_stock_manager")
                    or self.env.user.has_group("mrp.group_mrp_manager")):
                continue
            final=batch._ya_fg_display_final()
            pp2=len(final)==1 and bool(final.ya_pp2_design_b_snapshot)
            mo1=batch.line_ids.mapped("mo_id")
            mo2=final.line_ids.mapped("mo_id").with_env(self.env) if pp2 else self.env["mrp.production"]
            mos=mo1|mo2
            batch.ya_fg_mo1_count=len(mo1)
            batch.ya_fg_mo2_count=len(mo2)
            batch.ya_fg_total_mo_count=len(mos)
            batch.ya_fg_total_kitchen_count=len(mos.mapped("picking_type_id.warehouse_id"))
            picks=batch.ya_fg_transfer_ids
            if pp2:
                picks|=final.line_ids.ya_mo2_fg_picking_ids.with_env(self.env)
            batch.ya_fg_all_transfer_count=len(picks)
            rows=[]
            complete=bool(mos) and all(m.state=="done" for m in mos)
            matches=True
            expected_picks=len(mo1.mapped("picking_type_id.warehouse_id"))+len(mo2)
            for wave,wave_mos in (("MO1",mo1),("MO2",mo2)):
                for mo in wave_mos.sorted(key=lambda m:(m.picking_type_id.warehouse_id.id,m.product_id.id,m.id)):
                    prod=mo.product_id
                    wh=mo.picking_type_id.warehouse_id
                    plan=mo.product_uom_id._compute_quantity(mo.product_qty,prod.uom_id,round=False)
                    finished=mo.move_finished_ids.filtered(lambda m:m.product_id==prod and m.state=="done")
                    actual=sum(m.product_uom._compute_quantity(m.quantity,prod.uom_id,round=False) for m in finished)
                    if mo.state=="done" and (not finished or abs(actual-plan)>1e-7):
                        matches=False
                    if wave=="MO1":
                        linked=picks.filtered(lambda p:p.ya_fg_batch_id==batch and p.ya_fg_kitchen_id==wh)
                    else:
                        linked=final.line_ids.filtered(lambda l:l.mo_id.id==mo.id).ya_mo2_fg_picking_ids.with_env(self.env)
                    received=sum(m.product_uom._compute_quantity(m.quantity,prod.uom_id,round=False)
                        for m in linked.move_ids.filtered(lambda m:m.state=="done" and m.product_id==prod))
                    transfer_status=", ".join("%s (%s)"%(p.name,p.state) for p in linked) or _("Belum transfer")
                    if picks and (len(linked)!=1 or linked.state!="done" or abs(received-actual)>1e-7):
                        matches=False
                    rows.append((wh.display_name,prod.display_name,wave,mo.name,_qty(plan),_qty(actual),
                        prod.uom_id.name,dict(mo._fields["state"]._description_selection(mo.env)).get(mo.state,mo.state),
                        transfer_status,_qty(received)))
            batch.ya_fg_detail_html=_table(("Dapur","SKU / Produk","Tahap","MO","Qty MO",
                "Hasil Aktual","Satuan","Status MO","Transfer ke Packing","Qty Terkirim"),rows)
            if picks:
                batch.ya_fg_display_status=("transferred" if pp2 and complete and matches
                    and len(picks)==expected_picks and all(p.state=="done" for p in picks) else "review")
            elif batch.delivery_date < datetime.now(ZoneInfo("Asia/Jakarta")).date():
                batch.ya_fg_display_status="expired"
            elif not pp2:
                batch.ya_fg_display_status="waiting_pp2"
            elif not complete:
                batch.ya_fg_display_status="waiting_mo"
            elif not matches:
                batch.ya_fg_display_status="review"
            else:
                batch.ya_fg_display_status="ready"

    def action_ya_fg_display_open_mos(self):
        self.ensure_one()
        self.check_access("read")
        if self.env.cr.dbname != DB or not self.ya_pp1_design_b_snapshot:
            raise UserError(_("Gunakan menu MO Produksi."))
        if self.ya_pp1_design_b_snapshot["facts"]["company_id"]!=self.env.company.id:
            raise UserError(_("Perusahaan batch berbeda."))
        final=self._ya_fg_display_final()
        ids=self.line_ids.mapped("mo_id").ids
        if len(final)==1 and final.ya_pp2_design_b_snapshot:
            ids+=final.line_ids.mapped("mo_id").ids
        return dict(type="ir.actions.act_window",name=_("MO1 dan MO2"),
            res_model="mrp.production",view_mode="list,form",domain=[("id","in",ids)],
            context={"create":False},target="current")

    @api.model
    def action_ya_open_fg_display(self):
        if not (self.env.user.has_group("ya_store_ro.group_ya_packing_admin")
                or self.env.user.has_group("stock.group_stock_manager")
                or self.env.user.has_group("mrp.group_mrp_manager")):
            raise UserError(_("Akses Produk Jadi ke Packing tidak diizinkan."))
        if self.env.cr.dbname != DB:
            return self.env.ref("ya_finished_packing_transfer.ya_fg_packing_batch_action").read()[0]
        action=self.env.ref("ya_sale_production_capacity.action_ya_fg_display").read()[0]
        # Existing legacy batches stay in historical menus. Only Design B
        # batches for the active company belong to this Fase2 handoff view.
        batches=self.search([("state","=","production_ok"),("ya_pp1_design_b_snapshot","!=",False)])
        ids=batches.filtered(lambda b:b.ya_pp1_design_b_snapshot["facts"]["company_id"]==self.env.company.id).ids
        action["domain"]=[("id","in",ids)]
        return action
