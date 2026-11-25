"""Fase 2 final MO2 native manufacturing release, isolated from Fase 1 MO1.

ONE final release per Packing date/slot; one native additional mrp.production
per Published Planning SKU at most. Never write to ya.packing.batch.line.mo_id
or mrp.production.ya_packing_batch_line_id (immutable MO1 linkage).
No SO/RO fulfillment or real PCK transfer is created by this method.

S1 release opens H-1 15:30 WIB after SO cutoff H-1 15:00.
S2/S3 policies unresolved -> fail closed. Only clone allowed.
"""
from collections import defaultdict
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot

from .mo2_priority_rules import calculate_mo2_release, Mo2PriorityError

CLONE_DB = "erp-yussyakmal-mrp-test-RO_SO"
_INTERNAL_CONTEXT = "ya_mo2_finalization_locked"


def _now_wib():
    return datetime.now(ZoneInfo("Asia/Jakarta"))


def _integer_qty(uom, qty, target_uom, label, allow_zero=True):
    val = uom._compute_quantity(qty, target_uom, round=False)
    if (val < 0 or (not allow_zero and val <= 0) or
            abs(val - round(val)) > 1e-9):
        raise UserError(_("%s must be whole units in product base UoM.") % label)
    return int(round(val))


def _restricted_create(env):
    return (env.cr.dbname == CLONE_DB and env.su and
            env.context.get(_INTERNAL_CONTEXT) is True)


class YaSaleMo2Finalization(models.Model):
    _name = "ya.sale.mo2.finalization"
    _description = "YA SO / RO final incremental MO2 production release"
    _order = "delivery_date desc, slot, id desc"

    batch_id = fields.Many2one(
        "ya.packing.batch", required=True, readonly=True, index=True,
        ondelete="restrict",
    )
    delivery_date = fields.Date(required=True, readonly=True, index=True)
    slot = fields.Selection(
        [("S1", "S1 - 05.00 WIB"), ("S2", "S2 - 09.00 WIB"),
         ("S3", "S3 - 11.00 WIB")],
        required=True, readonly=True,
    )
    released_at = fields.Datetime(required=True, readonly=True)
    released_by = fields.Many2one(
        "res.users", required=True, readonly=True, ondelete="restrict")
    line_ids = fields.One2many(
        "ya.sale.mo2.release.line", "finalization_id", readonly=True)

    _unique_batch = models.Constraint(
        "UNIQUE(batch_id)",
        "MO2 final release may happen only once per Packing slot.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not _restricted_create(self.env):
            raise UserError(_("Only locked clone MO2 release may create a finalization."))
        for vals in vals_list:
            batch = self.env["ya.packing.batch"].browse(vals.get("batch_id")).exists()
            if (not batch or batch.state != "production_ok" or
                    batch.delivery_date != fields.Date.to_date(vals.get("delivery_date"))
                    or batch.slot != vals.get("slot")):
                raise UserError(_("MO2 finalization cannot be linked to this batch."))
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_("Final MO2 release is immutable."))

    def unlink(self):
        raise UserError(_("Final MO2 release cannot be deleted."))


class YaSaleMo2ReleaseLine(models.Model):
    _name = "ya.sale.mo2.release.line"
    _description = "MO2 per Published Planning kitchen SKU"
    _order = "planning_line_id, id"

    finalization_id = fields.Many2one(
        "ya.sale.mo2.finalization", required=True, readonly=True,
        index=True, ondelete="restrict")
    planning_line_id = fields.Many2one(
        "ya.production.planning.line", required=True, readonly=True,
        index=True, ondelete="restrict")
    product_id = fields.Many2one(
        "product.product", required=True, readonly=True, ondelete="restrict")
    mo_id = fields.Many2one(
        "mrp.production", required=True, readonly=True, index=True,
        ondelete="restrict")
    qty_mo2 = fields.Integer(required=True, readonly=True)
    qty_mo1 = fields.Integer(required=True, readonly=True)
    qty_so = fields.Integer(required=True, readonly=True)
    qty_ro_package = fields.Integer(required=True, readonly=True)
    qty_ro_direct = fields.Integer(required=True, readonly=True)
    published_max = fields.Integer(required=True, readonly=True)
    bom_output = fields.Integer(required=True, readonly=True)

    _unique_planning_line = models.Constraint(
        "UNIQUE(planning_line_id)",
        "Only one additional MO2 is permitted per Published Planning SKU.",
    )
    _unique_native_mo = models.Constraint(
        "UNIQUE(mo_id)", "One native Manufacturing Order per MO2 record.",
    )
    _positive_mo2 = models.Constraint(
        "CHECK(qty_mo2 > 0)", "Incremental MO2 output must be positive.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not _restricted_create(self.env):
            raise UserError(_("MO2 lines can only be created by locked release."))
        for vals in vals_list:
            session = self.env["ya.sale.mo2.finalization"].browse(
                vals.get("finalization_id")).exists()
            plan = self.env["ya.production.planning.line"].browse(
                vals.get("planning_line_id")).exists()
            mo = self.env["mrp.production"].browse(vals.get("mo_id")).exists()
            if (not session or not plan or not mo or
                    plan.planning_id.delivery_date != session.delivery_date
                    or plan.planning_id.slot != session.slot
                    or plan.planning_id.state != "published"
                    or plan.product_id.id != vals.get("product_id")
                    or mo.product_id != plan.product_id
                    or mo.ya_packing_batch_line_id
                    or any(not isinstance(vals.get(key), int) or
                           isinstance(vals.get(key), bool) or vals[key] < 0
                           for key in ("qty_mo1", "qty_so",
                                       "qty_ro_package", "qty_ro_direct",
                                       "published_max", "bom_output"))):
                raise UserError(_("Invalid native MO2 / Published Planning link."))
            if (not isinstance(vals.get("qty_mo2"), int)
                    or isinstance(vals.get("qty_mo2"), bool)
                    or vals["qty_mo2"] <= 0
                    or vals["bom_output"] <= 0
                    or vals["qty_mo1"] + vals["qty_mo2"] > vals["published_max"]
                    or vals["qty_mo2"] % vals["bom_output"]
                    or abs(mo.product_uom_id._compute_quantity(
                        mo.product_qty, plan.product_id.uom_id, round=False
                    ) - vals["qty_mo2"]) > 1e-9):
                raise UserError(_("MO2 Qty / BoM / Max Capacity integrity failure."))
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_("MO2 records are immutable."))

    def unlink(self):
        raise UserError(_("MO2 records cannot be deleted."))


class YaPackingBatchMo2Release(models.Model):
    _inherit = "ya.packing.batch"

    def _ya_prepare_mo2_final_release(self):
        """Read source demand and compute MO2 proposals under slot mutex.

        Snapshots for normal RO and RO Paket are immutable since Pre Produksi.
        This method never modifies MO1, original RO, Packing allocations or
        Published Planning. Callers must use the same slot transaction lock.
        """
        self.ensure_one()
        if self.env.cr.dbname != CLONE_DB:
            raise UserError(_("MO2 restricted to the RO_SO clone."))
        if not self.env.user.has_group("ya_store_ro.group_ya_packing_admin"):
            raise UserError(_("Only YA Packing Admin can release MO2."))
        if self.state != "production_ok":
            raise UserError(_("Release MO1 through Produksi OK before MO2."))
        if self.slot != "S1":
            raise UserError(_("MO2 cut-off for S2/S3 has not been approved."))
        now = _now_wib()
        start = datetime.combine(
            self.delivery_date - timedelta(days=1), time(15, 30),
            tzinfo=ZoneInfo("Asia/Jakarta"))
        depart = datetime.combine(
            self.delivery_date, time(5), tzinfo=ZoneInfo("Asia/Jakarta"))
        if not (start <= now < depart):
            raise UserError(_(
                "MO2 S1 final release may run only after H-1 15:30 WIB "
                "and before dispatch on the delivery date."
            ))

        lock_ro_slot(self.env.cr, self.delivery_date, self.slot)
        if self.env["ya.sale.mo2.finalization"].sudo().search_count([
            ("batch_id", "=", self.id)]):
            raise UserError(_("MO2 is already FINAL for this date/slot."))
        if (self.ya_store_delivery_ids or self.ya_package_assembly_mo_ids
                or self.ya_fg_transfer_ids):
            raise UserError(_(
                "Packing transfers, Paket assembly or store DO already exist; "
                "MO2 final release is closed. Do not alter completed transfers."
            ))

        expected_ro = self.env["ya.store.ro"].sudo().search([
            ("delivery_date", "=", self.delivery_date),
            ("slot", "=", self.slot), ("state", "=", "confirmed"),
        ])
        expected_pkg = self.env["ya.package.store.ro"].sudo().search([
            ("delivery_date", "=", self.delivery_date),
            ("slot", "=", self.slot), ("state", "=", "confirmed"),
        ])
        if set(expected_ro.ids) != set(self.ro_ids.ids):
            raise UserError(_("Confirmed ordinary RO differs from frozen batch."))
        if set(expected_pkg.ids) != set(self.ya_package_ro_ids.ids):
            raise UserError(_("Confirmed Paket RO differs from frozen batch."))
        if bool(expected_pkg) != bool(self.ya_has_package):
            raise UserError(_("Paket snapshot mismatch with confirmed Paket RO."))

        planning = self.env["ya.production.planning"].sudo().search([
            ("delivery_date", "=", self.delivery_date),
            ("slot", "=", self.slot), ("state", "=", "published"),
        ])
        by_sku = defaultdict(list)
        for p in planning:
            for line in p.line_ids:
                by_sku[line.product_id.id].append(line)

        ledgers = self.env["ya.sale.capacity.reservation"].sudo().search([
            ("delivery_date", "=", self.delivery_date),
            ("slot", "=", self.slot),
        ])
        confirmed = self.env["sale.order"].sudo().search([
            ("ya_is_capacity_so", "=", True),
            ("ya_delivery_date", "=", self.delivery_date),
            ("ya_slot", "=", self.slot),
            ("state", "in", ["sale", "done"]),
        ])
        if set(ledgers.mapped("order_id").ids) != set(confirmed.ids):
            raise UserError(_("SO ledger does not match confirmed YA SO for the slot."))
        so_by_sku = defaultdict(int)
        for r in ledgers:
            if (r.order_id.state not in ("sale", "done")
                    or r.planning_line_id.planning_id.state != "published"
                    or r.planning_line_id.planning_id.delivery_date != self.delivery_date
                    or r.planning_line_id.planning_id.slot != self.slot
                    or r.planning_line_id.product_id != r.product_id):
                raise UserError(_("Invalid protected YA SO ledger."))
            so_by_sku[r.product_id.id] += r.qty_required

        ro_direct = defaultdict(int)
        mo1_by_sku = {}
        for row in self.line_ids:
            if row.product_id.id in mo1_by_sku:
                raise UserError(_("Duplicate MO1 kitchen route in Packing batch."))
            mo1_by_sku[row.product_id.id] = row
            if row.uom_id != row.product_id.uom_id:
                raise UserError(_("MO1 batch UoM differs from product base UoM."))
            direct = self.allocation_ids.filtered(lambda a: a.line_id == row)
            if sum(direct.mapped("qty_requested")) != row.qty_requested:
                raise UserError(_("Original RO frozen snapshot quantity changed."))
            ro_direct[row.product_id.id] += row.qty_requested

        ro_package = defaultdict(int)
        for c in self.ya_package_component_ids:
            if c.source_kind != "kitchen":
                continue
            row = c.kitchen_line_id
            if not row or row.batch_id != self or row.product_id != c.product_id:
                raise UserError(_("Paket kitchen component has invalid MO1 link."))
            ro_package[c.product_id.id] += _integer_qty(
                c.uom_id, c.qty_required, c.product_id.uom_id,
                "RO Paket kitchen component", allow_zero=False)

        for row in self.line_ids:
            if ro_package[row.product_id.id] != row.ya_package_component_qty:
                raise UserError(_("RO Paket frozen components differ from batch."))
        candidate_products = (set(so_by_sku)
                              | set(ro_direct) | set(ro_package))
        if not candidate_products:
            # No SO or original RO demand: nothing to release, but still final.
            return []
        proposals = []
        for sku in sorted(candidate_products):
            routes = by_sku.get(sku) or []
            if len(routes) != 1:
                raise UserError(_("MO2 needs exactly one Published kitchen route for SKU %s.")
                                % sku)
            plan = routes[0]
            product = plan.product_id
            bom = plan._capacity_bom()
            pt = bom.picking_type_id
            expected = " ".join(
                ("Dapur " + (plan.planning_id.workcenter_id.name or "")
                 ).casefold().split())
            actual = (" ".join((pt.warehouse_id.name or "").casefold().split())
                      if pt and pt.warehouse_id else "")
            if (not bom.active or bom.type != "normal"
                    or bom.product_tmpl_id != product.product_tmpl_id
                    or (bom.product_id and bom.product_id != product)
                    or not pt or not pt.warehouse_id
                    or not pt.default_location_src_id
                    or not pt.default_location_dest_id
                    or pt.default_location_dest_id != pt.warehouse_id.lot_stock_id
                    or pt.company_id != self.env.company
                    or actual != expected):
                raise UserError(_("Kitchen BoM/warehouse route invalid for SKU %s.") % sku)
            output = _integer_qty(
                bom.product_uom_id, bom.product_qty, product.uom_id,
                "Kitchen BoM output", allow_zero=False)
            maximum = _integer_qty(
                plan.uom_id, plan.max_capacity, product.uom_id,
                "Published Planning Max")
            row = mo1_by_sku.get(sku)
            mo1_qty = 0
            if row:
                if row.planning_id != plan.planning_id or row.bom_id != bom:
                    raise UserError(_("MO1 frozen Planning/BoM changed for SKU %s.") % sku)
                if not row.mo_id or row.mo_id.state == "cancel":
                    raise UserError(_("MO1 missing or CANCELLED; reconcile SKU %s first.") % sku)
                mo = row.mo_id
                if (mo.product_id != product or mo.bom_id != bom
                        or mo.picking_type_id != pt):
                    raise UserError(_("MO1 product/BoM/route mismatch for SKU %s.") % sku)
                mo1_qty = _integer_qty(
                    mo.product_uom_id, mo.product_qty, product.uom_id,
                    "Existing MO1 output", allow_zero=False)
                if mo1_qty != row.qty_production:
                    raise UserError(_("Frozen MO1 output changed for SKU %s.") % sku)
            try:
                calc = calculate_mo2_release(
                    total_confirmed_so=so_by_sku[sku],
                    mo1_output=mo1_qty,
                    existing_mo2_output=0,
                    published_max=maximum,
                    kitchen_bom_output=output,
                    ro_package_components=ro_package[sku],
                    ro_direct_finished=ro_direct[sku],
                    so_cutoff_closed=True,
                    packing_physical_started=False,
                )
            except Mo2PriorityError as exc:
                raise UserError(_("MO2 SKU %s: %s") % (sku, exc)) from exc
            if calc["mo2_incremental_qty"]:
                proposals.append({
                    "plan": plan, "batch_line": row, "bom": bom,
                    "picking_type": pt, "qty": calc["mo2_incremental_qty"],
                    "mo1_qty": mo1_qty, "so_qty": so_by_sku[sku],
                    "ro_package": ro_package[sku],
                    "ro_direct": ro_direct[sku],
                    "max_capacity": maximum,
                    "bom_output": output,
                })
        return proposals

    def _ya_release_final_mo2(self):
        """Internal MO2 release. Not wired into a GUI button before rollback QA."""
        self.ensure_one()
        proposals = self._ya_prepare_mo2_final_release()
        final = self.env["ya.sale.mo2.finalization"].sudo().with_context(
            ya_mo2_finalization_locked=True
        ).create({
            "batch_id": self.id,
            "delivery_date": self.delivery_date,
            "slot": self.slot,
            "released_at": fields.Datetime.now(),
            "released_by": self.env.user.id,
        })
        for item in proposals:
            plan = item["plan"]
            product = plan.product_id
            pt = item["picking_type"]
            mo = self.env["mrp.production"].create({
                "product_id": product.id,
                "product_qty": float(item["qty"]),
                "product_uom_id": product.uom_id.id,
                "bom_id": item["bom"].id,
                "picking_type_id": pt.id,
                "location_src_id": pt.default_location_src_id.id,
                "location_dest_id": pt.default_location_dest_id.id,
                "company_id": pt.company_id.id,
                "date_start": fields.Datetime.now(),
                "origin": "MO2 / %s / %s" % (
                    self.delivery_date.strftime("%Y-%b-%d"), self.slot),
                # NEVER set ya_packing_batch_line_id (reserved to MO1).
            })
            mo.action_confirm()
            if mo.state in ("draft", "cancel", "done"):
                raise UserError(_("Native MO2 could not be confirmed for SKU %s.")
                                % product.display_name)
            self.env["ya.sale.mo2.release.line"].sudo().with_context(
                ya_mo2_finalization_locked=True
            ).create({
                "finalization_id": final.id,
                "planning_line_id": plan.id,
                "product_id": product.id,
                "mo_id": mo.id,
                "qty_mo2": item["qty"],
                "qty_mo1": item["mo1_qty"],
                "qty_so": item["so_qty"],
                "qty_ro_package": item["ro_package"],
                "qty_ro_direct": item["ro_direct"],
                "published_max": item["max_capacity"],
                "bom_output": item["bom_output"],
            })
        return final
