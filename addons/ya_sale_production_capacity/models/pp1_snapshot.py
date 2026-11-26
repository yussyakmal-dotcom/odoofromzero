"""Private Design B release core, clone-only. No GUI or scheduler entry yet.

The caller MUST enforce the approved RO cutoff and operator review before
calling this core. Until those gates are wired, only rollback QA may invoke
it. Original demand is frozen in JSON; no legacy recipient allocation rows
are manufactured. Fase 1 and historic batches retain their existing schema
semantics. Downstream Design B readers must use the frozen source facts.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .pp1_native_sources import DB, PP1SourceError
from .pp1_mo1_proposals import prepare_mo1_proposals
from .pp1_review_contract import source_digest

_TOKEN = object()

class PackingBatchDesignB(models.Model):
    _inherit = "ya.packing.batch"

    ya_pp1_design_b_snapshot = fields.Json(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any("ya_pp1_design_b_snapshot" in v for v in vals_list):
            if (self.env.cr.dbname != DB
                    or self.env.context.get("_ya_pp1_snapshot_token") is not _TOKEN
                    or not self.env.user.has_group("ya_store_ro.group_ya_packing_admin")):
                raise UserError(_("Design B snapshot may only be created by its release core."))
        return super().create(vals_list)

    def write(self, vals):
        if "ya_pp1_design_b_snapshot" in vals:
            raise UserError(_("Design B PP1 snapshot is immutable."))
        if any(b.ya_pp1_design_b_snapshot for b in self):
            if self.env.context.get("_ya_pp1_snapshot_token") is not _TOKEN:
                raise UserError(_("Design B PP1 batch is immutable."))
        return super().write(vals)

    def _ya_pp1_frozen_facts(self):
        self.ensure_one()
        snapshot = self.ya_pp1_design_b_snapshot
        if not snapshot or snapshot.get("version") != 1:
            raise UserError(_("Missing Design B snapshot."))
        facts = snapshot["facts"]
        if (source_digest(facts) != snapshot["digest"]
                or facts["delivery_date"] != str(self.delivery_date)
                or facts["slot"] != self.slot
                or set(facts["ordinary_ro_ids"]) != set(self.ro_ids.ids)
                or set(facts["package_ro_ids"]) != set(self.ya_package_ro_ids.ids)):
            raise UserError(_("Design B PP1 snapshot integrity failure."))
        return facts

    @api.model
    def _ya_create_pp1_design_b_release_core(self, delivery_date, slot, expected_digest):
        """Atomic internal core; NOT an authorized operational entry point."""
        if self.env.cr.dbname != DB or not self.env.user.has_group("ya_store_ro.group_ya_packing_admin"):
            raise UserError(_("Design B release core restricted to clone Packing Admin."))
        with self.env.cr.savepoint():
            try:
                prepared = prepare_mo1_proposals(
                    self.env, delivery_date, slot, self.env.company, expected_digest)
            except (PP1SourceError, ValueError) as exc:
                raise UserError(str(exc)) from exc
            facts = prepared["review"]["facts"]
            items = prepared["proposals"]
            # Zero-output demand remains visible in snapshot. If ALL quantities
            # are zero, the operator path is unresolved; never create fake MO.
            if not items:
                raise UserError(_("No positive MO1 output; PP1 exception requires review."))
            ordinary = self.env["ya.store.ro"].sudo().browse(facts["ordinary_ro_ids"])
            if any(ordinary.mapped("packing_batch_id")):
                raise UserError(_("Ordinary RO already staged."))
            snapshot = {"version": 1, "digest": prepared["review"]["digest"],
                        "facts": facts, "actor_id": self.env.uid,
                        "released_at": fields.Datetime.to_string(fields.Datetime.now())}
            guarded = self.with_context(ya_create_production_batch=True,
                                        _ya_pp1_snapshot_token=_TOKEN)
            batch = guarded.create({
                "delivery_date": delivery_date, "slot": slot, "state": "pre_production",
                "ya_pp1_design_b_snapshot": snapshot,
                "ro_ids": [(6,0,facts["ordinary_ro_ids"])],
                "ya_package_ro_ids": [(6,0,facts["package_ro_ids"])],
                "ya_has_package": bool(facts["package_ro_ids"]),
                "staged_by": self.env.uid, "staged_at": fields.Datetime.now(),
                "line_ids": [(0,0,{
                    "planning_id": p["planning_id"], "kitchen_code": p["kitchen_code"],
                    "product_id": p["product_id"], "reference": p["reference"],
                    "bom_id": p["native_mo_vals"]["bom_id"],
                    "uom_id": p["native_mo_vals"]["product_uom_id"],
                    "qty_requested": p["forecast"]["original_ro_store_qty"],
                    "ya_kitchen_bom_output": p["forecast"]["bom_output"],
                    "qty_production": p["forecast"]["forecast_mo1_qty"],
                    "max_capacity": p["forecast"]["published_max"],
                    # Legacy allocation fields are not used as entitlements.
                    "qty_shortage": p["forecast"]["forecast_ro_store_shortage"],
                    "qty_surplus": p["forecast"]["forecast_unallocated_surplus"],
                    "ya_package_component_qty": p["forecast"]["forecast_ro_package_covered"],
                }) for p in items],
            })
            by_product = {p["product_id"]:p for p in items}
            if len(batch.line_ids) != len(by_product):
                raise UserError(_("Design B MO1 line count mismatch."))
            if ordinary:
                ordinary.with_context(ya_stage_or_reset_packing=True).write(
                    {"packing_batch_id": batch.id})
            for row in batch.line_ids:
                item = by_product[row.product_id.id]
                mo = self.env["mrp.production"].create(dict(
                    item["native_mo_vals"], ya_packing_batch_line_id=row.id))
                mo.action_confirm()
                if (mo.state in ("draft","done","cancel") or mo.workorder_ids
                        or mo.ya_packing_batch_line_id != row
                        or mo.product_qty != row.qty_production):
                    raise UserError(_("Design B native MO1 integrity failure."))
                row.with_context(ya_release_production_batch=True).write({"mo_id":mo.id})
            if len(batch.line_ids.mapped("mo_id")) != len(items):
                raise UserError(_("Incomplete Design B MO1 release."))
            batch._ya_pp1_frozen_facts()
            batch.sudo().with_context(ya_release_production_batch=True,
                _ya_pp1_snapshot_token=_TOKEN).write({
                    "state":"production_ok","released_by":self.env.uid,
                    "released_at":fields.Datetime.now()})
            return batch

class PackingBatchLineDesignB(models.Model):
    _inherit = "ya.packing.batch.line"

    def write(self, vals):
        if any(row.batch_id.ya_pp1_design_b_snapshot for row in self):
            if self.env.context.get("_ya_pp1_snapshot_token") is not _TOKEN:
                raise UserError(_("Design B MO1 batch link is immutable."))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        batches = self.env["ya.packing.batch"].sudo().browse(
            [v["batch_id"] for v in vals_list if v.get("batch_id")])
        if any(b.ya_pp1_design_b_snapshot for b in batches):
            if self.env.context.get("_ya_pp1_snapshot_token") is not _TOKEN:
                raise UserError(_("Design B MO1 batch lines are immutable."))
        return super().create(vals_list)

class PackingAllocationDesignB(models.Model):
    _inherit = "ya.packing.batch.allocation"

    @api.model_create_multi
    def create(self, vals_list):
        batches = self.env["ya.packing.batch"].sudo().browse(
            [v["batch_id"] for v in vals_list if v.get("batch_id")])
        if any(b.ya_pp1_design_b_snapshot for b in batches):
            raise UserError(_("Design B final allocation requires its own verified ledger."))
        return super().create(vals_list)
