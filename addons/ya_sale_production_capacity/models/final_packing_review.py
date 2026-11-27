"""Final Packing review evidence. No native document generation here."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .pp1_native_sources import DB
from .final_packing_proposal_rules import source_digest

_TOKEN=object()
GROUP="ya_store_ro.group_ya_packing_admin"


class FinalPackingReview(models.Model):
    _name="ya.final.packing.review"
    _description="Post Produksi - Review Alokasi"
    _order="id desc"
    _rec_name="batch_id"

    batch_id=fields.Many2one("ya.packing.batch",required=True,readonly=True,index=True,ondelete="restrict")
    company_id=fields.Many2one("res.company",required=True,readonly=True)
    source_digest=fields.Char(required=True,readonly=True)
    evidence_digest=fields.Char(required=True,readonly=True)
    evidence=fields.Json(required=True,readonly=True)
    warning_count=fields.Integer(readonly=True)
    shortage_total=fields.Integer(readonly=True)
    reason=fields.Text(required=True,readonly=True)
    detail=fields.Text(compute="_compute_detail")

    @api.depends("evidence")
    def _compute_detail(self):
        for rec in self:
            result=(rec.evidence or {}).get("validated",{})
            rows=[]
            for row in result.get("rows",[]):
                product=self.env["product.product"].browse(row["product_id"])
                is_so=row["kind"] in ("SO","SO_PAKET")
                recipient=self.env["res.partner" if is_so else "stock.warehouse"].sudo().browse(row["recipient_id"])
                rows.append("%s | %s | %s | Demand %s | Alokasi %s | Kurang %s | Surplus %s | Sumber #%s/%s" % (
                    row["kind"],recipient.display_name,product.display_name,row["qty_requested"],
                    row["qty_allocated"],row["qty_shortage"],row.get("qty_surplus",0),row["source_id"],row["line_id"]))
            for warning in result.get("review_warnings",[]):
                rows.append("PERHATIAN: %s #%s/%s — %s" % (warning["kind"],warning["source_id"],warning["line_id"],warning["reason"]))
            rec.detail="\n".join(rows)

    @api.model_create_multi
    def create(self,vals_list):
        if (self.env.cr.dbname!=DB or not self.env.user.has_group(GROUP)
                or self.env.context.get("_ya_final_review_token") is not _TOKEN):
            raise UserError(_("Simpan review melalui Post Produksi."))
        return super().create(vals_list)

    def write(self,vals):
        raise UserError(_("Riwayat review tidak boleh diubah."))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_history(self):
        raise UserError(_("Riwayat review tidak boleh dihapus."))

    def _verified_evidence(self):
        self.ensure_one()
        data=self.evidence
        if (self.env.cr.dbname!=DB or self.company_id!=self.env.company
                or source_digest(data)!=self.evidence_digest
                or source_digest(data["demand"])!=self.source_digest
                or data["proposal"]["batch_id"]!=self.batch_id.id):
            raise UserError(_("Integritas review Post Produksi gagal."))
        return data


class PackingBatchFinalReview(models.Model):
    _inherit="ya.packing.batch"

    def action_ya_final_packing_review(self):
        self.ensure_one()
        if self.env.cr.dbname!=DB or not self.env.user.has_group(GROUP):
            raise UserError(_("Packing Admin di clone RO_SO diperlukan."))
        self.check_access("read")
        wizard=self.env["ya.final.packing.review.wizard"].create({"batch_id":self.id})
        return wizard.action_refresh()

    def action_ya_final_packing_review_history(self):
        self.ensure_one()
        if self.env.cr.dbname!=DB or not self.env.user.has_group(GROUP):
            raise UserError(_("Packing Admin di clone RO_SO diperlukan."))
        self.check_access("read")
        return dict(type="ir.actions.act_window",name=_("Riwayat Review Post Produksi"),
                    res_model="ya.final.packing.review",view_mode="list,form",
                    domain=[("batch_id","=",self.id),("company_id","=",self.env.company.id)],
                    context={"create":False},target="current")
