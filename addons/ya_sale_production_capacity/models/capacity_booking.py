"""Atomic capacity ledger preparation for YA SO confirmation.

This service is SOURCE-ONLY and NOT wired to any UI Confirm action. Future
activation must put it in the SAME transaction as native SO confirmation,
suppress the native warehouse delivery for YA safely, and integrate SO
priority/MO2/PCK before enabling the wizard.
"""
from collections import defaultdict

from odoo import models, _
from odoo.exceptions import UserError

from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot

from .confirm_capacity_math import CapacityDecisionError, check_so_capacity

CLONE_DB = "erp-yussyakmal-mrp-test-RO_SO"


class SaleOrderYACapacityBooking(models.Model):
    _inherit = "sale.order"

    def _ya_prepare_locked_booking(self, delivery_date, slot):
        """Lock the date/slot, re-evaluate SO demand, verify prior commitments.

        Returns the *intended* reservation rows and MO2 increment calculations;
        makes no business-document writes. Advisory transaction lock is shared
        with ordinary RO, Paket RO, Pre Produksi and Produksi OK.
        """
        self.ensure_one()
        if self.env.cr.dbname != CLONE_DB:
            raise UserError(_("Only RO_SO clone is authorized for YA SO development."))
        if not self.ya_is_capacity_so or self.state not in ("draft", "sent"):
            raise UserError(_("Choose one YA Draft/Sent quotation."))

        lock_ro_slot(self.env.cr, delivery_date, slot)
        # Protect against two workers simultaneously confirming the SAME SO.
        self.env.cr.execute(
            "SELECT id FROM sale_order WHERE id = %s FOR UPDATE", (self.id,))
        self.invalidate_recordset(["state", "ya_delivery_date", "ya_slot"])
        if self.state not in ("draft", "sent"):
            raise UserError(_("Quotation YA already confirmed elsewhere."))

        preview = self._ya_prepare_capacity_confirm_readonly(
            delivery_date, slot)
        if not preview["capacity"]:
            raise UserError(_("Quotation YA tidak mempunyai SKU produksi dapur. "
                              "Periksa produk dan BoM Paket."))

        Reservations = self.env["ya.sale.capacity.reservation"].sudo()
        prior = Reservations.search([
            ("delivery_date", "=", delivery_date),
            ("slot", "=", slot),
        ])

        if prior.filtered(lambda r: r.order_id == self):
            raise UserError(_("This YA quotation already has capacity reservations."))

        # Fail closed for missing, inconsistent, or unexpectedly edited
        # legacy confirmed SO records: never guess their capacity.
        confirmed_orders = self.env["sale.order"].sudo().search([
            ("ya_is_capacity_so", "=", True),
            ("ya_delivery_date", "=", delivery_date),
            ("ya_slot", "=", slot),
            ("state", "in", ("sale", "done")),
        ])
        prior_order_ids = set(prior.mapped("order_id").ids)
        if any(o.id not in prior_order_ids for o in confirmed_orders):
            raise UserError(_(
                "Confirmed YA SO without capacity ledger exists for this slot. "
                "Reconciliation required; automatic new booking is blocked."
            ))
        if any(
                r.order_id.state not in ("sale", "done")
                or not r.order_id.ya_is_capacity_so
                or r.order_id.ya_delivery_date != delivery_date
                or r.order_id.ya_slot != slot
                or r.planning_line_id.planning_id.state != "published"
                or r.planning_line_id.product_id != r.product_id
                for r in prior):
            raise UserError(_("Previous YA SO capacity ledger is inconsistent. "
                              "Resolve it before confirming another order."))

        reserved_qty = defaultdict(int)
        for row in prior:
            reserved_qty[row.planning_line_id.id] += row.qty_required

        Batch = self.env["ya.packing.batch"].sudo()
        batch = Batch.search([
            ("delivery_date", "=", delivery_date),
            ("slot", "=", slot),
        ])
        if len(batch) > 1:
            raise UserError(_("More than one Packing batch exists for the slot."))

        booking_rows = []
        demand_checks = []
        for item in preview["capacity"]:
            plan_line = self.env["ya.production.planning.line"].sudo().browse(
                item["planning_line_id"])
            matching = batch.line_ids.filtered(
                lambda row: row.planning_id == plan_line.planning_id
                and row.product_id == plan_line.product_id
            ) if batch else self.env["ya.packing.batch.line"].browse()
            if len(matching) > 1:
                raise UserError(_("Duplicate MO1 production rows for SKU %s.")
                                % plan_line.product_id.display_name)
            mo1_qty = 0
            if matching and matching.mo_id:
                mo = matching.mo_id
                if mo.state == "cancel" or mo.product_id != plan_line.product_id:
                    raise UserError(_("MO1 invalid/cancelled: %s.")
                                    % plan_line.product_id.display_name)
                actual = mo.product_uom_id._compute_quantity(
                    mo.product_qty, plan_line.product_id.uom_id, round=False)
                if actual < 0 or abs(actual - round(actual)) > 1e-9:
                    raise UserError(_("MO1 output has an invalid UoM: %s.")
                                    % plan_line.product_id.display_name)
                mo1_qty = int(round(actual))
            elif batch and batch.state == "production_ok" and matching:
                raise UserError(_("Produksi OK lacks MO1 for SKU %s.")
                                % plan_line.product_id.display_name)
            # MO2 model does NOT exist yet. This is a proposed increment,
            # not a released or reserved manufacturing order.
            try:
                calculated = check_so_capacity(
                    new_so_qty=item["new_qty"],
                    existing_so_qty=reserved_qty[plan_line.id],
                    published_max=item["published_max"],
                    bom_output=item["bom_output"],
                    mo1_output=mo1_qty,
                    mo2_output=0,
                    slot_open=True,  # Cut-off must be enforced before activation.
                )
            except CapacityDecisionError as exc:
                raise UserError(_("SO %(order)s, SKU %(sku)s: %(reason)s") % {
                    "order": self.name,
                    "sku": plan_line.product_id.default_code
                    or plan_line.product_id.display_name,
                    "reason": str(exc),
                }) from exc
            booking_rows.append({
                "order_id": self.id,
                "planning_line_id": plan_line.id,
                "product_id": plan_line.product_id.id,
                "delivery_date": delivery_date,
                "slot": slot,
                "qty_required": item["new_qty"],
            })
            demand_checks.append({
                "planning_line_id": plan_line.id,
                "calculation": calculated,
            })
        return {
            "reservation_rows": booking_rows,
            "capacity_checks": demand_checks,
            "package_qty": preview["package_qty"],
            "pck_stock_requirements": preview["pck_stock_requirements"],
            "pck_manual_finished_ids": preview["pck_manual_finished_ids"],
            "requires_packing_mo2_integration": any(
                x["calculation"]["incremental_mo2_output_needed"] > 0
                for x in demand_checks
            ),
        }

    def _ya_write_locked_capacity_reservations(self, booking):
        """Future internal booking step. NOT called by Confirm wizard yet.

        Call only after a successful _ya_prepare_locked_booking and as part
        of ONE transaction that will also safely confirm SO. A failed
        confirmation must roll back the ledger rows automatically.
        """
        self.ensure_one()
        if self.env.cr.dbname != CLONE_DB or self.state not in ("draft", "sent"):
            raise UserError(_("Refusing capacity reservations outside YA clone Draft SO."))
        rows = booking.get("reservation_rows") or []
        if not rows or any(row["order_id"] != self.id for row in rows):
            raise UserError(_("Invalid or empty SO capacity booking proposal."))
        # Reacquire/revalidate the same slot lock and quote row lock. A
        # proposal generated earlier is never trusted after another booking.
        fresh = self._ya_prepare_locked_booking(
            rows[0]["delivery_date"], rows[0]["slot"])
        if fresh["reservation_rows"] != rows:
            raise UserError(_("YA SO demand or reserved capacity changed. "
                              "Recalculate Confirm before booking."))
        return self.env["ya.sale.capacity.reservation"].sudo().with_context(
            ya_sale_confirm_slot_locked=True
        ).create(rows)
