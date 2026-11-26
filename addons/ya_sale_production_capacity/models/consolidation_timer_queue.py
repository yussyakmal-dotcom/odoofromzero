"""Hybrid preparation queue, clone only. No release or stock operations.

Clock admission is independent of cron. The cron prepares PP1 at RO cutoff
and PP2 at SO cutoff; PP2 release delay remains enforced by the operator
action. A fresh operator review always supersedes the timer digest.
"""
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from .pp1_native_sources import DB, PP1SourceError
from .pp1_review_contract import read_locked_review
from .consolidation_cutoff_gate import current_clock
from . import consolidation_cutoff_gate as gate
from .consolidation_cutoff_rules import WIB

_TOKEN=object()
GROUP="ya_store_ro.group_ya_packing_admin"


class ConsolidationTimerQueue(models.Model):
    _name="ya.consolidation.timer.queue"
    _description="YA Antrean Konsolidasi PP1 / PP2"
    _order="delivery_date, slot, stage"
    _rec_name="delivery_date"

    delivery_date=fields.Date(required=True,index=True,readonly=True)
    slot=fields.Selection([("S1","S1"),("S2","S2"),("S3","S3")],required=True,readonly=True)
    stage=fields.Selection([("pp1","Pre Produksi 1"),("pp2","Pre Produksi 2")],required=True,readonly=True)
    state=fields.Selection([("ready","Siap Review"),("waiting","Menunggu Jeda MO2"),
                            ("blocked","Perlu Perhatian"),("released","Produksi OK"),
                            ("expired","Dispatch Terlewat")],required=True,readonly=True)
    digest=fields.Char(readonly=True)
    sku_count=fields.Integer(readonly=True)
    note=fields.Char(readonly=True)
    prepared_at=fields.Datetime(readonly=True)
    batch_id=fields.Many2one("ya.packing.batch",readonly=True,ondelete="restrict")
    _unique_slot_stage=models.Constraint("UNIQUE(delivery_date,slot,stage)",
                                       "Antrean konsolidasi tanggal/slot/tahap harus unik.")

    @api.model_create_multi
    def create(self,vals_list):
        if self.env.cr.dbname!=DB or self.env.context.get("_ya_timer_token") is not _TOKEN:
            raise UserError(_("Antrean dibuat oleh timer konsolidasi."))
        return super().create(vals_list)

    def write(self,vals):
        if self.env.cr.dbname!=DB or self.env.context.get("_ya_timer_token") is not _TOKEN:
            raise UserError(_("Antrean diperbarui oleh timer konsolidasi."))
        if {"delivery_date","slot","stage"}.intersection(vals):
            raise UserError(_("Identitas antrean tidak boleh berubah."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_timer_history(self):
        raise UserError(_("Riwayat antrean tidak boleh dihapus."))

    @api.model
    def _cron_prepare_consolidation(self):
        if self.env.cr.dbname!=DB:
            return
        if not self.env.user.has_group(GROUP):
            raise UserError(_("User Scheduled Action harus Packing Admin."))
        today=gate.utc_now().astimezone(WIB).date()
        # Include published plans and open queue entries; also surface
        # confirmed demand whose planning has disappeared. The maximum
        # configurable cutoff is 365 days before delivery.
        horizon=today+timedelta(days=366)
        domain=[("delivery_date",">=",today),("delivery_date","<=",horizon)]
        keys=set()
        for model,extra in (
            ("ya.production.planning",[("state","=","published")]),
            ("ya.store.ro",[("state","=","confirmed")]),
            ("ya.package.store.ro",[("state","=","confirmed")]),
            (self._name,[("state","in",["ready","waiting","blocked"])])):
            keys.update((r.delivery_date,r.slot) for r in self.env[model].sudo().search(domain+extra))
        orders=self.env["sale.order"].sudo().search([
            ("ya_is_capacity_so","=",True),("state","in",["sale","done"]),
            ("ya_delivery_date",">=",today),("ya_delivery_date","<=",horizon)])
        keys.update((r.ya_delivery_date,r.ya_slot) for r in orders)
        keys.update((r.delivery_date,r.slot) for r in self.sudo().search([
            ("delivery_date","<",today),("state","in",["ready","waiting","blocked"])]))
        for day,slot in sorted((d,s) for d,s in keys if d and s in ("S1","S2","S3")):
            # Do not lock every future Published slot merely because a
            # plan exists. Recheck the clock again under the slot mutex.
            if not current_clock(self.env,day,slot)["ro_closed"]:
                continue
            with self.env.cr.savepoint():
                self._prepare_slot(day,slot)

    @api.model
    def _prepare_slot(self,day,slot):
        lock_ro_slot(self.env.cr,day,slot)
        self.env.invalidate_all()
        clock=current_clock(self.env,day,slot)
        Queue=self.sudo().with_context(_ya_timer_token=_TOKEN)
        Batch=self.env["ya.packing.batch"]
        batch=Batch.search([("delivery_date","=",day),("slot","=",slot)])
        final=self.env["ya.sale.mo2.finalization"].sudo().search([("batch_id","in",batch.ids)])
        for stage in ("pp1","pp2"):
            key=[("delivery_date","=",day),("slot","=",slot),("stage","=",stage)]
            entry=Queue.search(key)
            completed=bool(batch.ya_pp1_design_b_snapshot and batch.state=="production_ok") if stage=="pp1" else bool(final.ya_pp2_design_b_snapshot)
            if completed:
                if entry:
                    entry._set_prepared(dict(state="released",digest=False,sku_count=0,
                                             note="Produksi OK",batch_id=batch.id))
                continue
            if stage=="pp1" and not clock["ro_closed"]:
                continue
            if stage=="pp2" and not clock["so_closed"]:
                # S2/S3 without approved cutoff never auto-prepare PP2.
                continue
            vals=dict(state="blocked",digest=False,sku_count=0,note=False,batch_id=batch.id)
            try:
                if stage=="pp1":
                    if batch:
                        raise UserError(_("Batch legacy membutuhkan rekonsiliasi."))
                    review=read_locked_review(self.env,day,slot,self.env.company)
                    if not any(r["forecast_mo1_qty"]>0 for r in review["facts"]["sku_forecasts"]):
                        raise UserError(_("Tidak ada output MO1 positif; review manual diperlukan."))
                else:
                    if not batch.ya_pp1_design_b_snapshot or batch.state!="production_ok":
                        raise UserError(_("Menunggu Produksi OK 1."))
                    review=batch._ya_read_pp2_design_b_review()
                vals.update(state="ready",
                            digest=review["digest"],sku_count=len(review["facts"]["sku_forecasts"]),
                            note=("WARNING: Dispatch terlewat. " if clock["dispatch_passed"] else "")+"Hitung ulang saat operator membuka review.")
            except (PP1SourceError,UserError,ValueError) as exc:
                vals["note"]=str(exc)[:500]
            if entry:
                entry._set_prepared(vals)
            else:
                Queue.create(dict(vals,delivery_date=day,slot=slot,stage=stage,
                                  prepared_at=fields.Datetime.now()))

    def _set_prepared(self,vals):
        self.ensure_one()
        # Idempotent: identical refresh does not churn timestamps.
        if any((self[k].id if k=="batch_id" else self[k])!=v for k,v in vals.items()):
            self.write(dict(vals,prepared_at=fields.Datetime.now()))

    def action_open_review(self):
        self.ensure_one()
        if self.env.cr.dbname!=DB or not self.env.user.has_group(GROUP):
            raise UserError(_("Hanya Packing Admin di clone RO_SO."))
        self.check_access("read")
        # Never consume a cached timer digest for release.
        if self.state not in ("ready","waiting","blocked"):
            raise UserError(_("Antrean ini sudah selesai atau melewati dispatch."))
        wizard=self.env["ya.consolidation.review.wizard"].create({
            "stage":self.stage,"delivery_date":self.delivery_date,"slot":self.slot})
        return wizard.action_review()
