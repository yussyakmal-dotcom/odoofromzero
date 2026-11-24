"""Store-level cross-kitchen Paket RO. No stock/MO/GL side effects.

Separate from existing kitchen-scoped ya.store.ro: no fake Planning.
Future integration must include these confirmed requests in the immutable
same-date/slot Pre Produksi snapshot before any package assembly/DO.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot

CATEGORY = "All / Produk Jadi / Paket"
SLOTS = [
    ("S1", "S1 - 05.00 WIB"),
    ("S2", "S2 - 09.00 WIB"),
    ("S3", "S3 - 11.00 WIB"),
]


class YaPackageStoreRO(models.Model):
    _name = "ya.package.store.ro"
    _description = "YA Multi-kitchen Paket RO per Store"
    _order = "delivery_date desc, slot, id desc"

    name = fields.Char(compute="_compute_name")
    delivery_date = fields.Date(required=True, index=True)
    slot = fields.Selection(SLOTS, required=True, index=True)
    store_warehouse_id = fields.Many2one(
        "stock.warehouse", required=True, index=True, ondelete="restrict"
    )
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed")],
        default="draft", required=True, index=True,
    )
    line_ids = fields.One2many("ya.package.store.ro.line", "ro_id", copy=False)
    qty_total = fields.Integer(compute="_compute_qty_total")
    line_count = fields.Integer(compute="_compute_qty_total")
    confirmed_at = fields.Datetime(readonly=True)
    confirmed_by = fields.Many2one("res.users", readonly=True)

    _unique_date_slot_store = models.Constraint(
        "UNIQUE(delivery_date, slot, store_warehouse_id)",
        "Only one Paket RO per store, date and slot."
    )

    @api.depends("delivery_date", "slot", "store_warehouse_id")
    def _compute_name(self):
        for record in self:
            record.name = "RO Paket %s %s %s" % (
                record.delivery_date or "-",
                record.slot or "-",
                record.store_warehouse_id.code or "-",
            )

    @api.depends("line_ids.qty_requested")
    def _compute_qty_total(self):
        for record in self:
            record.line_count = len(record.line_ids)
            record.qty_total = sum(record.line_ids.mapped("qty_requested"))

    def _check_paket_category(self):
        for record in self:
            for line in record.line_ids:
                if line.product_id.categ_id.complete_name != CATEGORY:
                    raise ValidationError(
                        _("SKU %s must belong to category %s.") % (
                            line.product_id.display_name, CATEGORY)
                    )

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group("mrp.group_mrp_manager"):
            raise UserError(_("Manufacturing Manager access required."))
        if self.state != "draft":
            raise UserError(_("Only Draft Paket RO can be confirmed."))
        lock_ro_slot(self.env.cr, self.delivery_date, self.slot)
        if self.env["ya.packing.batch"].sudo().search_count([
            ("delivery_date", "=", self.delivery_date),
            ("slot", "=", self.slot),
        ]):
            raise UserError(_(
                "Pre Produksi/Produksi OK already exists for this date and slot. "
                "Paket RO cannot be added to a frozen batch."
            ))
        if not self.store_warehouse_id.active:
            raise UserError(_("Choose an active store warehouse."))
        if not self.line_ids.filtered(lambda l: l.qty_requested > 0):
            raise UserError(_("At least one Paket must have a positive Qty."))
        self._check_paket_category()
        self.with_context(ya_package_confirm=True).write({
            "state": "confirmed",
            "confirmed_at": fields.Datetime.now(),
            "confirmed_by": self.env.user.id,
        })
        return {"type": "ir.actions.act_window", "res_model": self._name,
                "res_id": self.id, "view_mode": "form",
                "views": [(False, "form")], "target": "current"}

    @api.model_create_multi
    def create(self, vals_list):
        if any(set(vals).intersection({"state", "confirmed_at", "confirmed_by"})
               for vals in vals_list):
            raise UserError(_("Create Paket RO in Draft; use Confirm button."))
        return super().create(vals_list)

    def write(self, vals):
        if any(rec.state == "confirmed" for rec in self):
            raise UserError(_("Confirmed Paket RO is immutable."))
        if "state" in vals and vals["state"] != "confirmed":
            raise UserError(_("Paket RO status cannot be changed manually."))
        if vals.get("state") == "confirmed" and not (
                self.env.context.get("ya_package_confirm")
                and self.env.user.has_group("mrp.group_mrp_manager")):
            raise UserError(_("Use Paket RO Confirm button."))
        protected = {"delivery_date", "slot", "store_warehouse_id"}
        if protected.intersection(vals) and any(rec.line_ids for rec in self):
            raise UserError(_("Cannot change date, slot or store after adding SKU lines."))
        return super().write(vals)

    def unlink(self):
        if any(rec.state != "draft" for rec in self):
            raise UserError(_("Confirmed Paket RO cannot be deleted."))
        return super().unlink()


class YaPackageStoreROLine(models.Model):
    _name = "ya.package.store.ro.line"
    _description = "YA Multi-kitchen Paket Store RO Line"
    _order = "id"

    ro_id = fields.Many2one(
        "ya.package.store.ro", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("product.product", required=True)
    qty_requested = fields.Integer(required=True, default=0)
    uom_id = fields.Many2one(
        "uom.uom", related="product_id.uom_id", readonly=True)

    _unique_product = models.Constraint(
        "UNIQUE(ro_id, product_id)", "Duplicate Paket SKU in this RO.")
    _qty_nonnegative = models.Constraint(
        "CHECK(qty_requested >= 0)", "Paket Qty must not be negative.")

    @api.constrains("product_id")
    def _check_category(self):
        for line in self:
            if line.product_id and line.product_id.categ_id.complete_name != CATEGORY:
                raise ValidationError(_("Only multi-kitchen Paket SKU allowed."))

    @api.constrains("qty_requested")
    def _check_qty(self):
        for line in self:
            if line.qty_requested < 0:
                raise ValidationError(_("Paket Qty must be nonnegative."))

    @api.model_create_multi
    def create(self, vals_list):
        parents = self.env["ya.package.store.ro"].browse(
            [v["ro_id"] for v in vals_list if v.get("ro_id")])
        if any(ro.state != "draft" for ro in parents):
            raise UserError(_("Confirmed Paket RO cannot be changed."))
        return super().create(vals_list)

    def write(self, vals):
        if any(line.ro_id.state != "draft" for line in self):
            raise UserError(_("Confirmed Paket RO lines cannot be edited."))
        return super().write(vals)

    def unlink(self):
        if any(line.ro_id.state != "draft" for line in self):
            raise UserError(_("Confirmed Paket RO lines cannot be deleted."))
        return super().unlink()
