"""Native Packing assembly MO per Paket SKU in a joint Packing batch.

Only creates/CONFIRMS standard MOs, not stock and not synthetic WOs.
A finished Paket exists only after Odoo posts its actual component consumption
and finished move. Standard store DO may be prepared only from produced stock.
"""
from collections import defaultdict

from .package_finish_rules import group_package_finish_demands

from odoo import fields, models, _
from odoo.exceptions import UserError

from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot


TEST_DB = "erp-yussyakmal-mrp-test"


class YaPackageAssemblyProduction(models.Model):
    _inherit = "mrp.production"

    ya_package_assembly_batch_id = fields.Many2one(
        "ya.packing.batch", string="Packing Paket Assembly Batch",
        readonly=True, copy=False, index=True, ondelete="restrict",
    )
    _unique_package_batch_product = models.Constraint(
        "UNIQUE(ya_package_assembly_batch_id, product_id)",
        "Only one Paket assembly MO per batch and Paket SKU.",
    )


class YaPackingBatchPackageAssembly(models.Model):
    _inherit = "ya.packing.batch"

    ya_package_assembly_mo_ids = fields.One2many(
        "mrp.production", "ya_package_assembly_batch_id",
        string="MO Rakit Paket di Packing", readonly=True,
    )
    ya_package_assembly_mo_count = fields.Integer(
        compute="_compute_ya_package_assembly_mo_count",
    )

    def _compute_ya_package_assembly_mo_count(self):
        for batch in self:
            batch.ya_package_assembly_mo_count = len(batch.ya_package_assembly_mo_ids)

    def action_ya_open_package_assembly_mos(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("MO Rakit Paket - %s") % self.name,
            "res_model": "mrp.production",
            "view_mode": "list,form",
            "domain": [("id", "in", self.ya_package_assembly_mo_ids.ids)],
            "context": {"create": False},
            "target": "current",
        }

    def _ya_pck_manufacturing_type(self, warehouse):
        """Use a REAL manufacturing operation type for Packing, never fabricate."""
        Types = self.env["stock.picking.type"].sudo()
        candidates = Types.search([
            ("code", "=", "mrp_operation"),
            ("warehouse_id", "=", warehouse.id),
            ("company_id", "=", warehouse.company_id.id),
        ])
        if len(candidates) != 1:
            raise UserError(_(
                "PCK requires ONE existing Manufacturing Operation Type "
                "(found %s). Review warehouse configuration; no fake routing."
            ) % len(candidates))
        operation = candidates[0]
        # Default locations are not assumed to be PCK/Stock: the MO below
        # explicitly sets both locations to PCK/Stock and verifies the result.
        # This respects existing warehouse configuration without a new route.
        return operation

    def action_ya_create_package_assembly_mos(self):
        """Prepare one standard MO per Paket SKU, after kitchens deliver to PCK.

        No duplicated demand per shop. All existing BoM component lines stay
        on the native MO. This action does NOT mark MO Done / move stock.
        """
        self.ensure_one()
        if self.env.cr.dbname != TEST_DB:
            raise UserError(_("Package assembly release is test DB only."))
        if not self.env.user.has_group("ya_store_ro.group_ya_packing_admin"):
            raise UserError(_("Packing Admin required to prepare Paket assembly."))
        if not self.ya_has_package or self.state != "production_ok":
            raise UserError(_("Choose a joint Paket batch with Produksi OK."))

        lock_ro_slot(self.env.cr, self.delivery_date, self.slot)
        self.env.cr.execute(
            "SELECT id FROM ya_packing_batch WHERE id = %s FOR UPDATE",
            [self.id],
        )
        if self.ya_package_assembly_mo_ids:
            if (set(self.ya_package_assembly_mo_ids.mapped("product_id").ids) !=
                    set(self.ya_package_demand_ids.mapped("product_id").ids)):
                raise UserError(_("Incomplete Paket assembly MO set. Review existing MOs."))
            return self.action_ya_open_package_assembly_mos()

        # Kitchen MO Done and standard kitchen->Packing FG transfers are
        # prerequisites for native Paket stock consumption. No phantom stock.
        kitchen_mos = self.line_ids.mapped("mo_id")
        if (len(kitchen_mos) != len(self.line_ids) or
                any(mo.state != "done" for mo in kitchen_mos)):
            raise UserError(_("Complete kitchen MOs before assembling Paket."))
        if kitchen_mos:
            fg = self.ya_fg_transfer_ids
            if not fg or any(p.state != "done" for p in fg):
                raise UserError(_("Complete Produk Jadi Dapur -> Packing first."))

        PCK = self.env["stock.warehouse"].sudo().search([
            ("code", "=", "PCK"),
        ])
        if len(PCK) != 1 or not PCK.lot_stock_id:
            raise UserError(_("PCK/Stock warehouse is missing or ambiguous."))
        if PCK.company_id != self.env.company:
            raise UserError(_("Packing warehouse belongs to a different company."))
        operation = self._ya_pck_manufacturing_type(PCK)
        stock_location = PCK.lot_stock_id
        if stock_location.usage != "internal":
            raise UserError(_("PCK/Stock must be an internal stock location."))

        # All Paket MOs are grouped by final SKU. Individual store allocation
        # remains in immutable ya.packing.package.demand rows for subsequent DO.
        result = group_package_finish_demands([
            {"product_id": d.product_id.id,
             "store_id": d.store_warehouse_id.id,
             "qty": d.qty_requested}
            for d in self.ya_package_demand_ids
        ])
        quantities = result["assembly_mo_qty"]
        boms = {}
        for demand in self.ya_package_demand_ids:
            product = demand.product_id
            bom = demand.bom_id
            if (not bom.active or bom.type != "normal" or
                    bom.product_tmpl_id != product.product_tmpl_id or
                    (bom.product_id and bom.product_id != product)):
                raise UserError(_("Paket assembly BoM invalid: %s") %
                                product.display_name)
            out = bom.product_uom_id._compute_quantity(
                bom.product_qty, product.uom_id, round=False)
            if abs(out - 1.0) > 1e-9:
                raise UserError(_("Assembly BoM must output ONE Paket: %s") %
                                product.display_name)
            if product.id in boms and boms[product.id] != bom.id:
                raise UserError(_("Same Paket SKU has conflicting assembly BoMs."))
            boms[product.id] = bom.id

        if not quantities:
            raise UserError(_("No positive Paket demand was frozen."))

        # Validate frozen BoM and source trace with the existing joint release
        # validator, but do not auto-procure consignment/packaging materials.
        self.env["ya.packing.batch.line"]._ya_check_joint_sources(self)
        MO = self.env["mrp.production"]
        for product_id, qty in sorted(quantities.items()):
            product = self.env["product.product"].browse(product_id)
            mo = MO.create({
                "product_id": product.id,
                "product_qty": float(qty),
                "product_uom_id": product.uom_id.id,
                "bom_id": boms[product_id],
                "picking_type_id": operation.id,
                "location_src_id": stock_location.id,
                "location_dest_id": stock_location.id,
                "company_id": PCK.company_id.id,
                "date_start": fields.Datetime.now(),
                "origin": "%s / Paket %s" % (
                    self.name, product.default_code or product.id),
                "ya_package_assembly_batch_id": self.id,
            })
            mo.action_confirm()
            if mo.state in ("draft", "cancel", "done"):
                raise UserError(_("Paket MO confirmation failed for %s.")
                                % product.display_name)
            if (mo.location_src_id != stock_location or
                    mo.location_dest_id != stock_location):
                raise UserError(_("Paket MO input/output must remain PCK/Stock."))
            # BoM must describe actual components; no empty/fictitious output.
            if not mo.move_raw_ids:
                raise UserError(_("Paket MO has no native Odoo component moves."))
            if "workorder_ids" in mo._fields and mo.workorder_ids:
                raise UserError(_(
                    "Paket BoM generated Work Orders; current SOP uses "
                    "standard Manufacturing Orders WITHOUT WOs. "
                    "Review this Paket BoM's operation lines."
                ))
        if set(self.ya_package_assembly_mo_ids.mapped("product_id").ids) != set(
                self.ya_package_demand_ids.mapped("product_id").ids):
            raise UserError(_("Paket assembly MO output set does not match demand."))
        return self.action_ya_open_package_assembly_mos()
