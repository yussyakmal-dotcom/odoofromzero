"""Clone-only immutable cutoff policy versions.

Settings affect delivery dates from an effective date forward. A version
must be published before BOTH the old and new RO deadlines (which precede
all configured SO deadlines) for its first affected delivery date.
No cron, release, or reopening existing closed delivery dates.
"""
import re
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .pp1_native_sources import DB
from .consolidation_cutoff_rules import DEFAULT_POLICY, DISPATCH, schedule


def _minute(value):
    if not isinstance(value,str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]",value):
        raise ValueError("Jam wajib format HH:MM (WIB).")
    hour,minute=map(int,value.split(":"))
    return hour*60+minute


class ConsolidationCutoffSettings(models.Model):
    _name="ya.consolidation.cutoff.settings"
    _description="YA Cutoff Settings Version"
    _order="effective_date desc, id desc"
    _rec_name="effective_date"

    effective_date=fields.Date(string="Berlaku mulai tanggal kirim",required=True,index=True)
    reason=fields.Text(string="Alasan perubahan",required=True)
    ro_days_before=fields.Integer(string="RO H-",required=True,default=2)
    ro_time=fields.Char(string="RO cutoff WIB",required=True,default="08:00")
    s1_days_before=fields.Integer(string="S1 H-",required=True,default=1)
    s1_time=fields.Char(string="SO S1 cutoff WIB",required=True,default="15:00")
    s2_enabled=fields.Boolean(string="Cutoff S2 sudah ditetapkan")
    s2_days_before=fields.Integer(string="S2 H-",default=1)
    s2_time=fields.Char(string="SO S2 cutoff WIB")
    s3_enabled=fields.Boolean(string="Cutoff S3 sudah ditetapkan")
    s3_days_before=fields.Integer(string="S3 H-",default=1)
    s3_time=fields.Char(string="SO S3 cutoff WIB")
    mo2_delay_minutes=fields.Integer(string="Jeda release MO2 (menit)",required=True,default=30)
    _unique_effective_date=models.Constraint("UNIQUE(effective_date)","Tanggal mulai versi cutoff harus unik.")

    def _policy(self):
        self.ensure_one()
        return dict(ro_days_before=self.ro_days_before,ro_minute=_minute(self.ro_time),
            so={"S1":dict(days_before=self.s1_days_before,minute=_minute(self.s1_time)),
                "S2":dict(days_before=self.s2_days_before,minute=_minute(self.s2_time)) if self.s2_enabled else None,
                "S3":dict(days_before=self.s3_days_before,minute=_minute(self.s3_time)) if self.s3_enabled else None},
            mo2_delay_minutes=self.mo2_delay_minutes)

    @api.model
    def _policy_for_delivery(self,day):
        if self.env.cr.dbname!=DB:
            raise UserError(_("Cutoff Settings hanya untuk clone RO_SO."))
        version=self.sudo().search([("effective_date","<=",day)],order="effective_date desc",limit=1)
        return (version._policy(),version.id) if version else (DEFAULT_POLICY,False)

    @api.model_create_multi
    def create(self,vals_list):
        if self.env.cr.dbname!=DB or not self.env.user.has_group("base.group_system"):
            raise UserError(_("Hanya Settings Administrator di clone RO_SO."))
        if len(vals_list)!=1:
            raise UserError(_("Simpan satu versi pengaturan pada satu waktu."))
        # Serialize settings writers. No date-slot locks are taken in this
        # path, and no existing RO, SO, batch or stock is modified.
        self.env.cr.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",
                            ["ya_consolidation_cutoff_settings_v1"])
        from .consolidation_cutoff_gate import utc_now
        with self.env.cr.savepoint():
            previous=self.sudo().search([],order="effective_date desc",limit=1)
            version=super().create(vals_list)
            day=version.effective_date
            if not version.reason or not version.reason.strip():
                raise UserError(_("Alasan perubahan wajib diisi."))
            if previous and day<=previous.effective_date:
                raise UserError(_("Tanggal berlaku harus setelah versi terakhir."))
            try:
                old=previous._policy() if previous else DEFAULT_POLICY
                new=version._policy()
                for slot in DISPATCH:
                    before=schedule(day,slot,old)
                    after=schedule(day,slot,new)
                    if utc_now()>=min(before["ro_cutoff"],after["ro_cutoff"]):
                        raise UserError(_("Tanggal berlaku terlalu dekat: cutoff RO lama dan baru harus masih di masa depan."))
            except (ValueError,TypeError,OverflowError) as exc:
                raise UserError(str(exc)) from exc
            if self.env["ya.packing.batch"].sudo().search_count([("delivery_date",">=",day)]):
                raise UserError(_("Sudah ada batch Packing pada rentang tanggal berlaku; pilih tanggal setelah batch terakhir."))
            return version

    def write(self,vals):
        raise UserError(_("Versi cutoff tidak dapat diubah. Buat versi baru untuk tanggal kirim mendatang."))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_version_history(self):
        raise UserError(_("Riwayat versi cutoff tidak boleh dihapus."))
