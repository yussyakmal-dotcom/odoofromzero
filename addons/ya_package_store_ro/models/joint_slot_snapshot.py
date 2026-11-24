"""Immutable Paket additions to existing YA Packing batch / Pre Produksi.

Do NOT replace the 20-year business process or the tested ordinary RO flow.
Exactly ONE date-slot Packing batch retains regular kitchen MO lines plus
cross-kitchen Paket source rows and their BOM component source trace.
Source only until full joint Production OK + Packing assembly/DO is ready.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


def _packing_snapshot_create_allowed(env):
    return bool(
        env.context.get("ya_package_create_joint_snapshot")
        and env.user.has_group("ya_store_ro.group_ya_packing_admin")
    )


class YaPackingBatchPackageLink(models.Model):
    _inherit = "ya.packing.batch"

    ya_has_package = fields.Boolean(
        string="Konsolidasi RO + Paket", readonly=True, copy=False,
    )
    ya_package_ro_ids = fields.Many2many(
        "ya.package.store.ro",
        "ya_packing_batch_package_ro_rel",
        "batch_id", "package_ro_id",
        string="RO Paket Confirmed (Snapshot)", readonly=True, copy=False,
    )
    ya_package_demand_ids = fields.One2many(
        "ya.packing.package.demand", "batch_id",
        string="Paket Jadi untuk Toko", readonly=True,
    )
    ya_package_component_ids = fields.One2many(
        "ya.packing.package.component", "batch_id",
        string="Komponen BoM Paket (Snapshot)", readonly=True,
    )


class YaPackingBatchLinePackageFields(models.Model):
    _inherit = "ya.packing.batch.line"

    ya_package_component_qty = fields.Integer(
        string="Prioritas Komponen Paket", readonly=True, copy=False,
        help="Qty produk jadi dapur yang dialokasikan untuk perakitan Paket di Packing.",
    )


class YaPackingPackageDemand(models.Model):
    _name = "ya.packing.package.demand"
    _description = "Snapshot RO Paket Finished SKU per Store"
    _order = "store_warehouse_id, product_id, id"

    batch_id = fields.Many2one(
        "ya.packing.batch", required=True, readonly=True,
        ondelete="restrict", index=True,
    )
    package_ro_id = fields.Many2one(
        "ya.package.store.ro", required=True, readonly=True,
        ondelete="restrict", index=True,
    )
    product_id = fields.Many2one(
        "product.product", required=True, readonly=True,
        ondelete="restrict",
    )
    store_warehouse_id = fields.Many2one(
        "stock.warehouse", required=True, readonly=True,
        ondelete="restrict",
    )
    bom_id = fields.Many2one(
        "mrp.bom", required=True, readonly=True,
        ondelete="restrict",
    )
    qty_requested = fields.Integer(required=True, readonly=True)
    component_ids = fields.One2many(
        "ya.packing.package.component", "demand_id",
        readonly=True,
    )

    _unique_ro_package = models.Constraint(
        "UNIQUE(batch_id, package_ro_id, product_id)",
        "Only one frozen Paket SKU line per source RO in a batch.",
    )
    _qty_positive = models.Constraint(
        "CHECK(qty_requested > 0)", "Frozen Paket Qty must be positive.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not _packing_snapshot_create_allowed(self.env):
            raise UserError(_("Only Packing can stage the Paket snapshot."))
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_("Frozen Paket demand cannot be edited."))

    def unlink(self):
        raise UserError(_("Frozen Paket demand cannot be deleted."))


class YaPackingPackageComponent(models.Model):
    _name = "ya.packing.package.component"
    _description = "Frozen Paket Assembly BoM Components"
    _order = "demand_id, product_id, id"

    batch_id = fields.Many2one(
        "ya.packing.batch", required=True, readonly=True,
        ondelete="restrict", index=True,
    )
    demand_id = fields.Many2one(
        "ya.packing.package.demand", required=True, readonly=True,
        ondelete="restrict", index=True,
    )
    product_id = fields.Many2one(
        "product.product", required=True, readonly=True,
        ondelete="restrict",
    )
    source_kind = fields.Selection([
        ("kitchen", "Produk Jadi Dapur"),
        ("pck", "Stok / Supply Manual ke Packing"),
    ], required=True, readonly=True)
    kitchen_line_id = fields.Many2one(
        "ya.packing.batch.line", readonly=True, ondelete="restrict",
    )
    uom_id = fields.Many2one(
        "uom.uom", required=True, readonly=True,
    )
    qty_per_package = fields.Float(readonly=True, required=True, digits="Product Unit of Measure")
    qty_required = fields.Float(readonly=True, required=True, digits="Product Unit of Measure")

    _qty_required_positive = models.Constraint(
        "CHECK(qty_required > 0)", "Paket component Qty must be positive.",
    )
    _unique_demand_product = models.Constraint(
        "UNIQUE(demand_id, product_id)",
        "Each component is represented once per frozen Paket demand.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not _packing_snapshot_create_allowed(self.env):
            raise UserError(_("Only Packing can freeze Paket BoM components."))
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_("Frozen Paket component cannot be edited."))

    def unlink(self):
        raise UserError(_("Frozen Paket component cannot be deleted."))
