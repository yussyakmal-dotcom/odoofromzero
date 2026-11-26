"""Clone-only immutable cutoff policy versions.

Settings affect delivery dates from an effective date forward. A version
must be published before BOTH the old and new RO deadlines (which precede
all configured SO deadlines) for its first affected delivery date.
No cron, release, or reopening existing closed delivery dates.
"""
import re
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from odoo.addons.ya_store_ro.models.date_labels import format_ymondd
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
    mo2_delay_minutes=fields.Integer(string="Jeda release MO2 (menit)",required=True,default=0)
    _unique_effective_date=models.Constraint("UNIQUE(effective_date)","Tanggal mulai versi cutoff harus unik.")

    def init(self):
        # Technical synchronization only; no ORM/RPC model or stock ledger.
        # Upgrade on the isolated clone before the new lock is used.
        if self.env.cr.dbname == DB:
            self.env.cr.execute("""
                CREATE TABLE IF NOT EXISTS ya_consolidation_slot_fence (
                    delivery_date date NOT NULL,
                    slot varchar NOT NULL CHECK (slot IN ('S1','S2','S3')),
                    revision bigint NOT NULL CHECK (revision > 0),
                    PRIMARY KEY (delivery_date, slot)
                )
            """)

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


class ConsolidationSpecialCutoff(models.Model):
    _name = "ya.consolidation.special.cutoff"
    _description = "YA Special Cutoff per Tanggal Kirim dan Slot"
    _order = "delivery_date desc, slot"
    _rec_name = "name"

    name = fields.Char(compute="_compute_name")
    delivery_date = fields.Date(string="Tanggal Kirim", required=True, index=True)
    slot = fields.Selection([("S1","S1 - 05.00 WIB"), ("S2","S2 - 09.00 WIB"),
                             ("S3","S3 - 11.00 WIB")], required=True)
    ro_cutoff_date = fields.Date(string="Tanggal Cutoff RO", required=True)
    ro_time = fields.Char(string="Jam Cutoff RO (WIB)", required=True, default="08:00")
    so_cutoff_date = fields.Date(string="Tanggal Cutoff SO", required=True)
    so_time = fields.Char(string="Jam Cutoff SO (WIB)", required=True, default="15:00")
    mo2_delay_minutes = fields.Integer(string="Jeda PP2 (menit)", required=True, default=0)
    reason = fields.Text(string="Alasan Special Cutoff", required=True)
    pp2_earliest_label = fields.Char(string="Produksi OK 2 paling awal (WIB)",
                                     compute="_compute_pp2_earliest")
    _unique_delivery_slot = models.Constraint(
        "UNIQUE(delivery_date, slot)", "Special Cutoff untuk tanggal kirim dan slot ini sudah ada.")

    @api.depends("delivery_date", "slot")
    def _compute_name(self):
        for row in self:
            row.name = "Special Cutoff / %s / %s" % (
                format_ymondd(row.delivery_date), row.slot or "-")

    def _policy(self):
        self.ensure_one()
        day = self.delivery_date
        if not day or not self.ro_cutoff_date or not self.so_cutoff_date or self.slot not in DISPATCH:
            raise ValueError("Isi tanggal kirim, slot, tanggal cutoff RO dan SO.")
        return dict(
            ro_days_before=(day-self.ro_cutoff_date).days, ro_minute=_minute(self.ro_time),
            so={key: dict(days_before=(day-self.so_cutoff_date).days,
                         minute=_minute(self.so_time)) if key==self.slot else None
                for key in DISPATCH},
            mo2_delay_minutes=self.mo2_delay_minutes,
        )

    @api.depends("delivery_date", "slot", "ro_cutoff_date", "ro_time",
                 "so_cutoff_date", "so_time", "mo2_delay_minutes")
    def _compute_pp2_earliest(self):
        for row in self:
            try:
                deadline = schedule(row.delivery_date, row.slot, dict(row._policy(),mo2_delay_minutes=0))["pp2_earliest"]
                row.pp2_earliest_label = format_ymondd(deadline)+deadline.strftime(" %H:%M")
            except (ValueError, TypeError, OverflowError):
                row.pp2_earliest_label = False

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.cr.dbname != DB or not self.env.user.has_group("base.group_system"):
            raise UserError(_("Special Cutoff hanya untuk Settings Administrator di clone RO_SO."))
        if len(vals_list) != 1:
            raise UserError(_("Simpan satu Special Cutoff pada satu waktu."))
        # Same date-slot transaction fence as Confirm RO/SO and PP1/PP2.
        # A stale concurrent transaction must retry rather than admit on
        # an old cutoff. Do not change the clock or any business documents.
        from .consolidation_cutoff_gate import utc_now
        with self.env.cr.savepoint():
            vals = vals_list[0]
            day = fields.Date.to_date(vals.get("delivery_date"))
            slot = vals.get("slot")
            if not day or slot not in DISPATCH:
                raise UserError(_("Isi Tanggal Kirim dan Slot."))
            self.env.cr.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",
                                ["ya_consolidation_cutoff_settings_v1"])
            lock_ro_slot(self.env.cr, day, slot)
            self.env.invalidate_all()
            domain = [("delivery_date","=",day),("slot","=",slot)]
            if self.sudo().search_count(domain):
                raise UserError(_("Special Cutoff sudah tersimpan untuk tanggal dan slot ini."))
            if self.env["ya.packing.batch"].sudo().search_count(domain):
                raise UserError(_("Sudah ada batch Packing. Jadwal tidak boleh diubah."))
            default_policy, _version = self.env["ya.consolidation.cutoff.settings"]._policy_for_delivery(day)
            row = super().create(vals_list)
            if not row.reason or not row.reason.strip():
                raise UserError(_("Alasan Special Cutoff wajib diisi."))
            try:
                old = schedule(day,slot,default_policy)
                new = schedule(day,slot,row._policy())
                if utc_now() >= min(old["ro_cutoff"],new["ro_cutoff"]):
                    raise UserError(_("Cutoff RO lama dan baru harus masih di masa depan. Jadwal yang sudah ditutup tidak boleh dibuka kembali."))
            except (ValueError,TypeError,OverflowError) as exc:
                raise UserError(str(exc)) from exc
            return row

    def write(self, vals):
        raise UserError(_("Special Cutoff tersimpan tidak dapat diubah."))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_special_history(self):
        raise UserError(_("Riwayat Special Cutoff tidak boleh dihapus."))
