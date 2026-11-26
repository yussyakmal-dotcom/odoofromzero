"""Clone UAT: immutable final approval, native Paket reservation.
Direct DO quantities remain unreserved until the subsequent delivery stage.
No new allocation algorithm, no DO, no native stock posting at approval.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from .final_packing_review import GROUP
from .pp1_native_sources import DB, PP1SourceError
from .final_packing_demand import read_final_packing_demand
from .final_packing_proposal_rules import validate_proposal, source_digest
from .final_packing_assembly_bridge import _qa_create_native_paket_assembly

_TOKEN=object()


class FinalPackingRelease(models.Model):
    _name="ya.final.packing.release"
    _description="Post Produksi - Final Allocation Release"
    _rec_name="batch_id"

    batch_id=fields.Many2one("ya.packing.batch",required=True,readonly=True,index=True,ondelete="restrict")
    review_id=fields.Many2one("ya.final.packing.review",required=True,readonly=True,ondelete="restrict")
    company_id=fields.Many2one("res.company",required=True,readonly=True)
    evidence_digest=fields.Char(required=True,readonly=True)
    assembly_ids=fields.Many2many("mrp.production",readonly=True,copy=False)
    _unique_batch=models.Constraint("UNIQUE(batch_id)","Final Packing release already exists for this batch.")

    @api.model_create_multi
    def create(self,vals_list):
        if (self.env.cr.dbname!=DB or not self.env.user.has_group(GROUP)
                or self.env.context.get("_ya_final_release_token") is not _TOKEN):
            raise UserError(_("Release hanya melalui review Post Produksi."))
        return super().create(vals_list)

    def write(self,vals):
        raise UserError(_("Final Packing release immutable."))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_release(self):
        raise UserError(_("Final Packing release tidak boleh dihapus."))

    def _verified_review(self):
        self.ensure_one()
        review=self.review_id
        data=review._verified_evidence()
        if (self.company_id!=self.env.company or self.batch_id!=review.batch_id
                or self.evidence_digest!=review.evidence_digest
                or self.assembly_ids!=self.batch_id.ya_package_assembly_mo_ids):
            raise UserError(_("Final Packing release integrity failure."))
        return data


class FinalPackingReviewRelease(models.Model):
    _inherit="ya.final.packing.review"

    release_ids=fields.One2many("ya.final.packing.release","review_id",readonly=True)

    def action_release_paket(self):
        self.ensure_one()
        if self.env.cr.dbname!=DB or not self.env.user.has_group(GROUP):
            raise UserError(_("Packing Admin di clone RO_SO diperlukan."))
        self.check_access("read")
        batch=self.batch_id
        batch.check_access("read")
        Release=self.env["ya.final.packing.release"]
        with self.env.cr.savepoint():
            lock_ro_slot(self.env.cr,batch.delivery_date,batch.slot)
            self.env.invalidate_all()
            if Release.search_count([("batch_id","=",batch.id)]):
                raise UserError(_("Final Packing sudah release."))
            latest=self.search([("batch_id","=",batch.id)],order="id desc",limit=1)
            if latest!=self:
                raise UserError(_("Gunakan review terakhir untuk batch ini."))
            data=self._verified_evidence()
            try:
                demand=read_final_packing_demand(batch)
                if source_digest(demand)!=self.source_digest:
                    raise UserError(_("Data sumber/stok berubah. Buat review baru sebelum release."))
                validated=validate_proposal(demand,data["proposal"])
                if validated!=data["validated"]:
                    raise UserError(_("Hasil validator berubah. Buat review baru."))
                # The existing bridge reads and validates again, creates one
                # native MO per Paket SKU and reserves its actual components.
                assemblies=_qa_create_native_paket_assembly(batch,data["proposal"])
                release=Release.with_context(_ya_final_release_token=_TOKEN).create({
                    "batch_id":batch.id,"review_id":self.id,"company_id":self.env.company.id,
                    "evidence_digest":self.evidence_digest,"assembly_ids":[(6,0,assemblies.ids)]})
                release._verified_review()
            except (PP1SourceError,ValueError) as exc:
                raise UserError(str(exc)) from exc
            return dict(type="ir.actions.act_window",name=_("Review Final Packing - Released"),
                        res_model=self._name,res_id=self.id,view_mode="form",target="current")

    def action_open_released_paket(self):
        self.ensure_one()
        if self.env.cr.dbname!=DB or not self.env.user.has_group(GROUP):
            raise UserError(_("Packing Admin di clone RO_SO diperlukan."))
        self.check_access("read")
        release=self.release_ids
        if len(release)!=1:
            raise UserError(_("Belum ada release."))
        release._verified_review()
        return self.batch_id.action_ya_open_package_assembly_mos()


class PackingBatchReleasedReviewGuard(models.Model):
    _inherit="ya.packing.batch"

    def action_ya_final_packing_review(self):
        self.ensure_one()
        if self.env.cr.dbname==DB:
            self.check_access("read")
            if self.env["ya.final.packing.release"].sudo().search_count([("batch_id","=",self.id)]):
                raise UserError(_("Final Packing sudah release; buka Riwayat Review Alokasi."))
        return super().action_ya_final_packing_review()
