"""Date/slot closing: actual business event, independent of preparation queue."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from .pp1_native_sources import DB

GROUP = "ya_store_ro.group_ya_packing_admin"
TOKEN = object()
DEFAULT = {"pp1": "scheduled", "pp2": "manual"}
EPOCH = "ya_closing_lifecycle.activation_utc"


class ClosingLifecycle(models.Model):
    _name = "ya.consolidation.closing"
    _description = "YA Closing per Tanggal Kirim / Slot / Tahap"
    _order = "delivery_date desc, slot, stage"

    delivery_date = fields.Date(required=True, readonly=True, index=True)
    slot = fields.Selection([("S1","S1"),("S2","S2"),("S3","S3")], required=True, readonly=True)
    stage = fields.Selection([("pp1","PP1 - RO"),("pp2","PP2 - SO")], required=True, readonly=True)
    mode = fields.Selection([("scheduled","Scheduled Closing"),("manual","Manual Closing")], required=True, readonly=True)
    closed_at = fields.Datetime(readonly=True)
    closed_by = fields.Many2one("res.users", readonly=True)
    _unique_key = models.Constraint("UNIQUE(delivery_date,slot,stage)", "Closing harus unik.")

    def init(self):
        if self.env.cr.dbname == DB:
            # One-time migration boundary. Never reopen an old elapsed SO cutoff.
            params = self.env["ir.config_parameter"].sudo()
            if not params.get_param(EPOCH):
                params.set_param(EPOCH, fields.Datetime.to_string(fields.Datetime.now()))

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.cr.dbname != DB or self.env.context.get("_ya_closing_token") is not TOKEN:
            raise UserError(_("Gunakan aksi Closing PP1 / PP2."))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.cr.dbname != DB or self.env.context.get("_ya_closing_token") is not TOKEN:
            raise UserError(_("Gunakan aksi Closing PP1 / PP2."))
        if set(vals) - {"closed_at","closed_by"} or any(self.mapped("closed_at")):
            raise UserError(_("Riwayat Closing tidak boleh diubah."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_closing(self):
        raise UserError(_("Riwayat Closing tidak boleh dihapus."))

    @api.model
    def _slot_rows(self, day, slot):
        return self.sudo().search([("delivery_date","=",day),("slot","=",slot)])

    @api.model
    def _set_mode(self, day, slot, stage, mode):
        from .consolidation_cutoff_gate import current_clock
        if self.env.cr.dbname != DB or not self.env.user.has_group("base.group_system"):
            raise UserError(_("Hanya Settings Administrator dapat memilih metode Closing."))
        if stage not in DEFAULT or mode not in ("manual","scheduled"):
            raise UserError(_("Metode Closing tidak valid."))
        lock_ro_slot(self.env.cr, day, slot)
        self.env.invalidate_all()
        clock = current_clock(self.env, day, slot)
        if clock["dispatch_passed"] or clock["ro_closed"] or self._slot_rows(day,slot).filtered(lambda r:r.stage==stage):
            raise UserError(_("Metode hanya dapat ditetapkan sekali sebelum Closing RO."))
        if stage=="pp2" and mode=="scheduled" and not clock["so_cutoff_configured"]:
            raise UserError(_("Tetapkan cutoff SO untuk Scheduled Closing PP2."))
        return self.sudo().with_context(_ya_closing_token=TOKEN).create(dict(
            delivery_date=day,slot=slot,stage=stage,mode=mode))

    @api.model
    def _close(self, day, slot, stage):
        from .consolidation_cutoff_gate import current_clock
        if self.env.cr.dbname != DB or not self.env.user.has_group(GROUP):
            raise UserError(_("Hanya Packing Admin dapat melakukan Closing."))
        if stage not in DEFAULT:
            raise UserError(_("Tahap Closing tidak valid."))
        lock_ro_slot(self.env.cr,day,slot)
        self.env.invalidate_all()
        clock=current_clock(self.env,day,slot)
        if clock["expired"]:
            raise UserError(_("Expired - Gagal Produksi. Buat siklus baru."))
        key="ro" if stage=="pp1" else "so"
        row=self._slot_rows(day,slot).filtered(lambda r:r.stage==stage)
        if row.closed_at:
            return row
        if stage=="pp2" and not self.env["ya.packing.batch"].sudo().search_count([
                ("delivery_date","=",day),("slot","=",slot),("state","=","production_ok"),
                ("ya_pp1_design_b_snapshot","!=",False)]):
            raise UserError(_("Selesaikan PP1 sebelum Closing PP2."))
        if clock[stage+"_mode"]=="scheduled" and not clock[key+"_closed"]:
            raise UserError(_("Scheduled Closing belum mencapai cutoff."))
        vals=dict(closed_at=fields.Datetime.now(),closed_by=self.env.uid)
        guarded=self.sudo().with_context(_ya_closing_token=TOKEN)
        if row:
            row.with_context(_ya_closing_token=TOKEN).write(vals)
            return row
        return guarded.create(dict(vals,delivery_date=day,slot=slot,stage=stage,mode=clock[stage+"_mode"]))


class ManufacturingClosingGate(models.Model):
    _inherit = "mrp.production"

    def _ya_check_pp2_before_production(self):
        if self.env.cr.dbname != DB:
            return
        for mo in self:
            batch=mo.sudo().ya_packing_batch_line_id.batch_id
            if not batch:
                batch=self.env["ya.sale.mo2.release.line"].sudo().search([("mo_id","=",mo.id)],limit=1).finalization_id.batch_id
            if not batch or not batch.ya_pp1_design_b_snapshot:
                continue
            lock_ro_slot(self.env.cr,batch.delivery_date,batch.slot)
            self.env.invalidate_all()
            from .consolidation_cutoff_gate import utc_now
            from .consolidation_cutoff_rules import WIB
            if batch.delivery_date < utc_now().astimezone(WIB).date() and mo.state not in ("done","cancel"):
                raise UserError(_("Expired - Gagal Produksi. MO lama tidak boleh diproduksi."))
            final=self.env["ya.sale.mo2.finalization"].sudo().search([("batch_id","=",batch.id)])
            if len(final)!=1 or not final.ya_pp2_design_b_snapshot:
                raise UserError(_("PP2 wajib selesai sebelum pelaksanaan produksi MO1."))
            final._ya_pp2_frozen_facts()

    def button_mark_done(self):
        self._ya_check_pp2_before_production()
        return super().button_mark_done()

    def _post_inventory(self, *args, **kwargs):
        self._ya_check_pp2_before_production()
        return super()._post_inventory(*args, **kwargs)
