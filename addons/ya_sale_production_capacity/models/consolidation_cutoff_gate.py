"""Clone-only admission guard; no timer or operator release.

Read immutable effective-delivery-date policy versions; approved defaults
apply before the first saved version. No guessed SO cutoff for S2/S3.
"""
from datetime import datetime, timezone
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from .consolidation_cutoff_rules import clock_state
from .pp1_native_sources import DB


def utc_now():
    return datetime.now(timezone.utc)


def current_clock(env, delivery_date, slot):
    if env.cr.dbname != DB:
        raise UserError(_("Cutoff Fase 2 hanya untuk clone RO_SO."))
    try:
        day=fields.Date.to_date(delivery_date)
        policy,version_id=env["ya.consolidation.cutoff.settings"]._policy_for_delivery(day)
        state=clock_state(day,slot,utc_now(),policy)
        state["cutoff_settings_version_id"]=version_id
        return state
    except (ValueError,TypeError) as exc:
        raise UserError(str(exc)) from exc


_CONFIRM_TOKEN=object()


def _lock_ro_parents(records):
    """Shared slot lock for original demand changes, including Draft edits."""
    if records.env.cr.dbname!=DB:
        return
    records.check_access("read")
    keys={(r.delivery_date,r.slot) for r in records}
    for day,slot in sorted(keys,key=lambda k:(str(k[0]),str(k[1]))):
        if day and slot:
            lock_ro_slot(records.env.cr,day,slot)
    records.env.invalidate_all()
    if {(r.delivery_date,r.slot) for r in records}!=keys:
        raise UserError(_("Jadwal RO berubah; refresh sebelum transaksi."))


def _guard_confirmed_qty(lines):
    if lines.env.cr.dbname!=DB:
        return
    _lock_ro_parents(lines.mapped("ro_id"))
    for ro in lines.mapped("ro_id").filtered(lambda r:r.state=="confirmed"):
        if not current_clock(lines.env,ro.delivery_date,ro.slot)["ro_admission_allowed"]:
            raise UserError(_("Cutoff RO sudah ditutup. Koreksi Qty tidak diperbolehkan."))


def guard_ro_confirm(records, vals):
    if records.env.cr.dbname != DB or vals.get("state") != "confirmed":
        return
    if {"delivery_date","slot","planning_id","store_warehouse_id"}.intersection(vals):
        raise UserError(_("Jangan ubah jadwal/identitas RO bersamaan dengan Confirm."))
    _lock_ro_parents(records)
    for rec in records.sorted(key=lambda r:(r.delivery_date,r.slot,r.id)):
        day,slot=rec.delivery_date,rec.slot
        lock_ro_slot(records.env.cr,day,slot)
        rec.invalidate_recordset(["delivery_date","slot","state"])
        if rec.delivery_date!=day or rec.slot!=slot or rec.state!="draft":
            raise UserError(_("Jadwal/status RO berubah; refresh sebelum Confirm."))
        if not current_clock(records.env,day,slot)["ro_admission_allowed"]:
            raise UserError(_("Cutoff RO sudah ditutup. Pilih tanggal kirim berikutnya."))
    if records.env.context.get("_ya_ro_confirm_token") is not _CONFIRM_TOKEN:
        raise UserError(_("Gunakan tombol Confirm RO; status tidak boleh diubah langsung."))


class OrdinaryROCutoff(models.Model):
    _inherit="ya.store.ro"

    def action_confirm(self):
        if self.env.cr.dbname!=DB:
            return super().action_confirm()
        self.ensure_one()
        with self.env.cr.savepoint():
            _lock_ro_parents(self)
            return super(OrdinaryROCutoff,self.with_context(
                _ya_ro_confirm_token=_CONFIRM_TOKEN)).action_confirm()

    @api.model_create_multi
    def create(self,vals_list):
        if self.env.cr.dbname!=DB:
            return super().create(vals_list)
        # Existing imports must create Draft then use native confirmation.
        if any(v.get("state","draft")!="draft" for v in vals_list) or self.env.context.get("default_state","draft")!="draft":
            raise UserError(_("Buat RO dalam Draft; gunakan Confirm."))
        with self.env.cr.savepoint():
            rows=super().create(vals_list)
            if any(r.state!="draft" for r in rows):
                raise UserError(_("Buat RO dalam Draft; gunakan Confirm."))
            return rows

    def write(self,vals):
        guard_ro_confirm(self,vals)
        return super().write(vals)


class PackageROCutoff(models.Model):
    _inherit="ya.package.store.ro"

    def action_confirm(self):
        if self.env.cr.dbname!=DB:
            return super().action_confirm()
        self.ensure_one()
        with self.env.cr.savepoint():
            _lock_ro_parents(self)
            return super(PackageROCutoff,self.with_context(
                _ya_ro_confirm_token=_CONFIRM_TOKEN)).action_confirm()

    @api.model_create_multi
    def create(self,vals_list):
        if self.env.cr.dbname!=DB:
            return super().create(vals_list)
        with self.env.cr.savepoint():
            rows=super().create(vals_list)
            if any(r.state!="draft" for r in rows):
                raise UserError(_("Buat Paket RO dalam Draft; gunakan Confirm."))
            return rows

    def write(self,vals):
        guard_ro_confirm(self,vals)
        return super().write(vals)


class OrdinaryROLineCutoff(models.Model):
    _inherit="ya.store.ro.line"

    def write(self,vals):
        if self.env.cr.dbname==DB:
            _guard_confirmed_qty(self)
        return super().write(vals)


class PackageROLineCutoff(models.Model):
    _inherit="ya.package.store.ro.line"

    def write(self,vals):
        if self.env.cr.dbname==DB:
            _guard_confirmed_qty(self)
            if "ro_id" in vals:
                raise UserError(_("Jangan pindahkan baris Paket RO. Buat baris baru pada Draft RO."))

        return super().write(vals)
