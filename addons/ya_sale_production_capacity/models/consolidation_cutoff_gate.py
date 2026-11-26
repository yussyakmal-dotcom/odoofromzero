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


def guard_ro_confirm(records, vals):
    if records.env.cr.dbname != DB or vals.get("state") != "confirmed":
        return
    if {"delivery_date","slot","planning_id","store_warehouse_id"}.intersection(vals):
        raise UserError(_("Jangan ubah jadwal/identitas RO bersamaan dengan Confirm."))
    for rec in records.sorted(key=lambda r:(r.delivery_date,r.slot,r.id)):
        day,slot=rec.delivery_date,rec.slot
        lock_ro_slot(records.env.cr,day,slot)
        rec.invalidate_recordset(["delivery_date","slot","state"])
        if rec.delivery_date!=day or rec.slot!=slot or rec.state!="draft":
            raise UserError(_("Jadwal/status RO berubah; refresh sebelum Confirm."))
        if not current_clock(records.env,day,slot)["ro_admission_allowed"]:
            raise UserError(_("Cutoff RO sudah ditutup. Pilih tanggal kirim berikutnya."))


class OrdinaryROCutoff(models.Model):
    _inherit="ya.store.ro"

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
