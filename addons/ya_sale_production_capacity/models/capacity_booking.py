"""Atomic capacity ledger preparation for YA SO confirmation.

The confirm transaction is clone-only. It reserves a Published Planning
capacity ledger and confirms the native commercial SO without early delivery.
Physical MO2/Packing allocation/real PCK delivery are separate next phases.
"""
from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import UserError

from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot

from .confirm_capacity_math import CapacityDecisionError, check_so_capacity
from .consolidation_cutoff_gate import current_clock

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
        if slot not in ("S1", "S2", "S3") or not delivery_date:
            raise UserError(_("Tanggal dan Slot Kirim YA wajib sebelum Confirm."))
        delivery = fields.Date.to_date(delivery_date)
        lock_ro_slot(self.env.cr, delivery_date, slot)
        # Protect against two workers simultaneously confirming the SAME SO.
        self.env.cr.execute(
            "SELECT id FROM sale_order WHERE id = %s FOR UPDATE", (self.id,))
        self.invalidate_recordset(["state", "ya_delivery_date", "ya_slot"])
        if self.state not in ("draft", "sent"):
            raise UserError(_("Quotation YA already confirmed elsewhere."))

        # Check wall clock AFTER both transaction locks, including a
        # delayed worker that entered before cutoff but obtained lock later.
        clock = current_clock(self.env,delivery,slot)
        if clock["dispatch_passed"]:
            raise UserError(_("Waktu keberangkatan slot sudah berlalu."))
        if not clock["so_admission_allowed"]:
            raise UserError(_("Cutoff SO sudah ditutup. Pilih tanggal kirim berikutnya."))

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
        if batch and batch.ya_pp1_design_b_snapshot and self.env["ya.sale.mo2.finalization"].sudo().search_count([
                ("batch_id", "=", batch.id)]):
            raise UserError(_("PP2 already finalized; SO booking is closed."))
        if batch and (
                batch.ya_store_delivery_ids or
                batch.ya_package_assembly_mo_ids or
                any(t.state == "done" for t in batch.ya_fg_transfer_ids)):
            raise UserError(_(
                "Packing atau dispatch tanggal/slot ini sudah berjalan. "
                "Tidak boleh menambah reservasi SO setelah alokasi fisik "
                "atau pengiriman mulai diproses."
            ))

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
            "source_rows": preview["source_rows"],
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
        """Write protected capacity in the SAME database transaction as SO confirm.

        Must be called after _ya_prepare_locked_booking. A failed confirmation
        rolls back BOTH native SO state and all ledger rows.
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
        if (fresh["reservation_rows"] != rows or
                fresh["source_rows"] != booking["source_rows"]):
            raise UserError(_("YA SO demand or reserved capacity changed. "
                              "Recalculate Confirm before booking."))
        return self.env["ya.sale.capacity.reservation"].sudo().with_context(
            ya_sale_confirm_slot_locked=True
        ).create(rows)

    def _ya_confirm_with_protected_capacity(self, delivery_date, slot):
        """Clone-only atomic Confirm: quote -> capacity ledger -> native SO.

        No kitchen MO, Packing allocation, stock transfer, invoice, or native
        warehouse Delivery may be created here. Subsequent Fase 2 work must
        consume the protected ledger during MO1/MO2 and PCK allocation.
        """
        self.ensure_one()
        if self.env.cr.dbname != CLONE_DB:
            raise UserError(_("SO capacity Confirm hanya boleh di database clone RO_SO."))
        if not self.env.user.has_group("sales_team.group_sale_salesman"):
            raise UserError(_("Sales permission is required to Confirm YA SO."))
        # Locks a date-slot shared with RO, Paket RO and Packing; also locks
        # this quotation row to avoid duplicate Confirm across workers.
        booking = self._ya_prepare_locked_booking(delivery_date, slot)
        if self.picking_ids:
            raise UserError(_("Quotation YA has unexpected outgoing deliveries."))

        # Schedule is finalized only AFTER passing all capacity checks.
        # All three operations below are atomic in the Odoo HTTP transaction.
        self.write({"ya_delivery_date": delivery_date, "ya_slot": slot})
        created = self._ya_write_locked_capacity_reservations(booking)
        if len(created) != len(booking["reservation_rows"]):
            raise UserError(_("YA capacity ledger is incomplete; Confirm rolled back."))

        # sale_stock must not create a DO from the normal Sales warehouse.
        # Packing will later issue the actual PCK -> Customer delivery.
        self._ya_freeze_confirmed_demand(booking, created)
        self._ya_native_confirm_without_early_delivery()

        if (self.state not in ("sale", "done") or self.picking_ids or
                self.ya_delivery_date != delivery_date or self.ya_slot != slot):
            raise UserError(_("YA SO Confirm integrity check failed; rolled back."))
        if sum(created.mapped("qty_required")) != sum(
                row["qty_required"] for row in booking["reservation_rows"]):
            raise UserError(_("YA capacity ledger Qty mismatch; rolled back."))

        return {
            "type": "ir.actions.act_window",
            "name": _("YA Sales Order Confirmed (Production Reserved)"),
            "res_model": "sale.order",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(self.env.ref(
                "ya_sale_production_capacity.view_ya_capacity_sale_order_form"
            ).id, "form")],
            "target": "current",
        }
