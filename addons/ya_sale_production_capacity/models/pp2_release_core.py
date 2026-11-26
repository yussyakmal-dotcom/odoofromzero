"""Private Design B Produksi OK 2 core, clone rollback QA only.

No public action, scheduler or cutoff bypass for operational use.
Caller must enforce configured SO cutoff and release delay before activation.
Existing MO2 finalization and release line models are reused.
"""
import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.ya_store_ro.models.date_labels import format_ymondd

from .pp1_native_sources import DB
from .pp2_native_sources import read_pp2_forecast

_TOKEN = object()


def pp2_digest(facts):
    payload = json.dumps(facts, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Mo2FinalizationDesignB(models.Model):
    _inherit = "ya.sale.mo2.finalization"

    ya_pp2_design_b_snapshot = fields.Json(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            batch = self.env["ya.packing.batch"].sudo().browse(vals.get("batch_id")).exists()
            if batch.ya_pp1_design_b_snapshot or "ya_pp2_design_b_snapshot" in vals:
                if (self.env.cr.dbname != DB or not batch.ya_pp1_design_b_snapshot
                        or self.env.context.get("_ya_pp2_token") is not _TOKEN
                        or not self.env.user.has_group("ya_store_ro.group_ya_packing_admin")
                        or not vals.get("ya_pp2_design_b_snapshot")):
                    raise UserError(_("Design B PP2 requires its private release core."))
        return super().create(vals_list)

    def _ya_pp2_frozen_facts(self):
        self.ensure_one()
        snapshot = self.ya_pp2_design_b_snapshot
        if not snapshot or snapshot.get("version") != 1:
            raise UserError(_("Missing Design B PP2 snapshot."))
        facts = snapshot["facts"]
        batch = self.batch_id
        if (pp2_digest(facts) != snapshot["digest"]
                or facts["batch_id"] != batch.id
                or facts["delivery_date"] != str(self.delivery_date)
                or facts["slot"] != self.slot
                or facts["pp1_digest"] != batch.ya_pp1_design_b_snapshot["digest"]):
            raise UserError(_("Design B PP2 snapshot integrity failure."))
        batch._ya_pp1_frozen_facts()
        expected = {r["planning_line_id"]: r for r in facts["sku_forecasts"]
                    if r["mo2_increment_due_to_so_only"] > 0}
        if set(self.line_ids.mapped("planning_line_id").ids) != set(expected):
            raise UserError(_("Design B MO2 release lines differ from snapshot."))
        for row in self.line_ids:
            fact = expected[row.planning_line_id.id]
            if (row.product_id.id != fact["product_id"]
                    or row.qty_mo2 != fact["mo2_increment_due_to_so_only"]
                    or row.qty_mo1 != fact["preexisting_mo1_qty"]
                    or row.qty_so != fact["confirmed_so_qty"]
                    or row.qty_ro_package != fact["original_ro_package_qty"]
                    or row.qty_ro_direct != fact["original_ro_store_qty"]
                    or row.published_max != fact["published_max"]
                    or row.bom_output != fact["bom_output"]
                    or not row.mo_id or row.mo_id.product_id != row.product_id
                    or row.mo_id.ya_packing_batch_line_id):
                raise UserError(_("Design B MO2 release identity mismatch."))
        return facts


class Mo2ReleaseLineDesignB(models.Model):
    _inherit = "ya.sale.mo2.release.line"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            final = self.env["ya.sale.mo2.finalization"].sudo().browse(
                vals.get("finalization_id")).exists()
            if final.batch_id.ya_pp1_design_b_snapshot:
                if (self.env.context.get("_ya_pp2_token") is not _TOKEN
                        or not final.ya_pp2_design_b_snapshot):
                    raise UserError(_("Design B MO2 lines require its private release core."))
        return super().create(vals_list)


class PackingBatchDesignBPP2(models.Model):
    _inherit = "ya.packing.batch"

    def _ya_read_pp2_design_b_review(self):
        self.ensure_one()
        try:
            facts = read_pp2_forecast(self)
        except ValueError as exc:
            raise UserError(str(exc)) from exc
        return {"facts": facts, "digest": pp2_digest(facts)}

    def _ya_release_pp2_design_b_core(self, expected_digest):
        """Atomic private release, including finalization with zero new MO."""
        self.ensure_one()
        if (self.env.cr.dbname != DB
                or not self.env.user.has_group("ya_store_ro.group_ya_packing_admin")):
            raise UserError(_("Design B PP2 restricted to clone Packing Admin."))
        with self.env.cr.savepoint():
            # Reader acquires the shared date-slot transaction lock.
            review = self._ya_read_pp2_design_b_review()
            if review["digest"] != expected_digest:
                raise UserError(_("PP2 source changed; refresh review before Produksi OK 2."))
            facts = review["facts"]
            snapshot = {"version": 1, "digest": review["digest"], "facts": facts,
                        "actor_id": self.env.uid,
                        "released_at": fields.Datetime.to_string(fields.Datetime.now())}
            final = self.env["ya.sale.mo2.finalization"].sudo().with_context(
                ya_mo2_finalization_locked=True, _ya_pp2_token=_TOKEN).create({
                    "batch_id": self.id, "delivery_date": self.delivery_date,
                    "slot": self.slot, "released_by": self.env.uid,
                    "released_at": fields.Datetime.now(),
                    "ya_pp2_design_b_snapshot": snapshot,
                })
            for row in facts["sku_forecasts"]:
                qty = row["mo2_increment_due_to_so_only"]
                if not qty:
                    continue
                plan = self.env["ya.production.planning.line"].sudo().browse(
                    row["planning_line_id"])
                product = plan.product_id
                bom = plan._capacity_bom()
                pt = bom.picking_type_id
                mo = self.env["mrp.production"].create({
                    "product_id": product.id, "product_qty": float(qty),
                    "product_uom_id": product.uom_id.id, "bom_id": bom.id,
                    "picking_type_id": pt.id,
                    "location_src_id": pt.default_location_src_id.id,
                    "location_dest_id": pt.default_location_dest_id.id,
                    "company_id": pt.company_id.id,
                    "date_start": fields.Datetime.now(),
                    "origin": "MO2 / %s / %s" % (format_ymondd(self.delivery_date), self.slot),
                })
                mo.action_confirm()
                if (mo.state in ("draft", "cancel", "done") or mo.workorder_ids
                        or mo.ya_packing_batch_line_id or mo.product_qty != qty):
                    raise UserError(_("Design B native MO2 integrity failure."))
                self.env["ya.sale.mo2.release.line"].sudo().with_context(
                    ya_mo2_finalization_locked=True, _ya_pp2_token=_TOKEN).create({
                        "finalization_id": final.id, "planning_line_id": plan.id,
                        "product_id": product.id, "mo_id": mo.id, "qty_mo2": qty,
                        "qty_mo1": row["preexisting_mo1_qty"],
                        "qty_so": row["confirmed_so_qty"],
                        "qty_ro_package": row["original_ro_package_qty"],
                        "qty_ro_direct": row["original_ro_store_qty"],
                        "published_max": row["published_max"], "bom_output": row["bom_output"],
                    })
            final._ya_pp2_frozen_facts()
            return final.with_env(self.env)
