"""Ledger for immutable YA SO kitchen-capacity promises.

Only source code until actual SO-confirm/Packing integration is verified.
Booking MUST be done in one database transaction holding the RO/Packing
date-slot advisory lock; no independent manual booking from the UI.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

CLONE_DB = "erp-yussyakmal-mrp-test-RO_SO"


class YaSaleCapacityReservation(models.Model):
    _name = "ya.sale.capacity.reservation"
    _description = "YA Confirmed Sales Order - Protected Kitchen Capacity"
    _order = "delivery_date desc, slot, product_id, order_id"

    order_id = fields.Many2one(
        "sale.order", required=True, readonly=True, index=True,
        ondelete="restrict",
    )
    planning_line_id = fields.Many2one(
        "ya.production.planning.line", required=True, readonly=True,
        index=True, ondelete="restrict",
    )
    product_id = fields.Many2one(
        "product.product", required=True, readonly=True, ondelete="restrict",
    )
    delivery_date = fields.Date(required=True, readonly=True, index=True)
    slot = fields.Selection(
        [("S1", "S1 - 05.00 WIB"), ("S2", "S2 - 09.00 WIB"),
         ("S3", "S3 - 11.00 WIB")],
        required=True, readonly=True, index=True,
    )
    qty_required = fields.Integer(
        string="Protected kitchen Qty (product base UoM)",
        required=True, readonly=True,
    )

    _unique_order_planning_line = models.Constraint(
        "UNIQUE(order_id, planning_line_id)",
        "One protected capacity row per Sales Order and Published Planning SKU.",
    )
    _positive_qty = models.Constraint(
        "CHECK(qty_required > 0)",
        "A protected SO kitchen quantity must be positive.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if (self.env.cr.dbname != CLONE_DB or not self.env.su or
                not self.env.context.get("ya_sale_confirm_slot_locked")):
            raise UserError(_(
                "Protected YA SO capacity can only be recorded in the "
                "atomic Confirm transaction on the RO_SO clone."
            ))
        for vals in vals_list:
            order = self.env["sale.order"].browse(vals.get("order_id")).exists()
            line = self.env["ya.production.planning.line"].browse(
                vals.get("planning_line_id")
            ).exists()
            if not order or not line or not order.ya_is_capacity_so:
                raise ValidationError(_("Invalid YA SO / kitchen capacity link."))
            planning = line.planning_id
            if (order.state not in ("draft", "sent") or
                    planning.state != "published" or
                    planning.delivery_date != fields.Date.to_date(vals.get("delivery_date")) or
                    planning.slot != vals.get("slot") or
                    line.product_id.id != vals.get("product_id") or
                    not isinstance(vals.get("qty_required"), int) or
                    isinstance(vals.get("qty_required"), bool) or
                    vals["qty_required"] <= 0):
                raise ValidationError(_("YA SO reservation is not consistent with Published Planning."))
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_("Confirmed YA SO capacity cannot be edited manually."))

    def unlink(self):
        raise UserError(_("Confirmed YA SO capacity cannot be deleted manually."))
