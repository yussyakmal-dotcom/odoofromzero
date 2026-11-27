"""MR2: native CDC transfer per finalized PP2 kitchen; full raw demand.

Existing single-line link retained for historical QA documents only.
No extra material calculator or stock ledger. Issued native demand is frozen
for validation; only actual native stock moves perform the transfer.
"""
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from .pp1_native_sources import DB as CLONE_DB

_TOKEN=object()


class StockPickingMo2Material(models.Model):
    _inherit="stock.picking"

    ya_mo2_material_release_line_id=fields.Many2one(
        "ya.sale.mo2.release.line",readonly=True,copy=False,index=True,ondelete="restrict")
    _unique_mo2_material_wave=models.Constraint(
        "UNIQUE(ya_mo2_material_release_line_id)","The same MO2 already has its CDC material transfer.")
    ya_mr2_finalization_id=fields.Many2one("ya.sale.mo2.finalization",
        readonly=True,copy=False,index=True,ondelete="restrict")
    ya_mr2_kitchen_id=fields.Many2one("stock.warehouse",
        readonly=True,copy=False,index=True,ondelete="restrict")
    ya_mr2_issued_demand=fields.Json(readonly=True,copy=False)
    _unique_mr2_kitchen=models.Constraint(
        "UNIQUE(ya_mr2_finalization_id,ya_mr2_kitchen_id)",
        "MR2 already exists for this PP2 kitchen.")
    _MR2_FIELDS=frozenset(("ya_mr2_finalization_id","ya_mr2_kitchen_id","ya_mr2_issued_demand"))

    @api.model_create_multi
    def create(self,vals_list):
        if any(self._MR2_FIELDS.intersection(v) for v in vals_list):
            if self.env.cr.dbname!=CLONE_DB or self.env.context.get("_ya_mr2_token") is not _TOKEN:
                raise UserError(_("MR2 harus dibuat melalui Material Requirement."))
        return super().create(vals_list)

    def write(self,vals):
        if self._MR2_FIELDS.intersection(vals):
            raise UserError(_("Identitas dan Demand MR2 immutable."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_mr2_issued(self):
        if any(p.ya_mr2_finalization_id for p in self):
            raise UserError(_("MR2 yang telah terbit tidak boleh dihapus."))

    def _ya_check_grouped_mr2(self):
        self.ensure_one()
        if self.env.cr.dbname!=CLONE_DB:
            raise UserError(_("MR2 hanya di clone RO_SO."))
        final=self.ya_mr2_finalization_id.sudo()
        batch=final.batch_id
        lock_ro_slot(self.env.cr,batch.delivery_date,batch.slot)
        self.env.invalidate_all()
        final._ya_pp2_frozen_facts()
        facts=self.ya_mr2_issued_demand
        kitchen=self.ya_mr2_kitchen_id
        cdc=self.env["stock.warehouse"].search([("code","=","CDC"),("company_id","=",self.company_id.id)])
        lines=final.line_ids.filtered(lambda l:l.mo_id.picking_type_id.warehouse_id==kitchen)
        if (not facts or facts["line_ids"]!=sorted(lines.ids) or len(cdc)!=1
                or self.location_id!=cdc.lot_stock_id or self.location_dest_id!=kitchen.lot_stock_id
                or self.picking_type_id!=cdc.int_type_id or self.company_id!=kitchen.company_id
                or self.state in ("done","cancel")):
            raise UserError(_("Identitas/rute MR2 berubah."))
        expected={int(k):v for k,v in facts["demand"].items()}
        actual={}
        for m in self.move_ids:
            pid=m.product_id.id
            if (pid in actual or m.state in ("done","cancel") or m.product_uom!=m.product_id.uom_id
                    or m.location_id!=self.location_id or m.location_dest_id!=self.location_dest_id
                    or m.company_id!=self.company_id):
                raise UserError(_("Baris MR2 tidak sesuai dokumen terbit."))
            actual[pid]=m.product_uom_qty
            if float_compare(m.quantity,m.product_uom_qty,precision_rounding=m.product_uom.rounding)!=0:
                raise UserError(_("MR2 wajib dipenuhi penuh; Qty harus sama dengan Demand."))
        if set(actual)!=set(expected) or any(abs(actual[p]-expected[p])>1e-7 for p in expected):
            raise UserError(_("Demand MR2 berubah dari dokumen terbit."))
        # Native reservations are the source of truth. Do not let draft
        # Validate auto-fill zero or consume stock allocated elsewhere.
        if self.state!="assigned" or any(m.state!="assigned" for m in self.move_ids):
            raise UserError(_("Reserve seluruh bahan MR2 sebelum Validate."))
        for m in self.move_ids:
            if not m.picked or not m.move_line_ids or any(l.location_id!=self.location_id
                    or l.location_dest_id!=self.location_dest_id for l in m.move_line_ids):
                raise UserError(_("Konfirmasi Picked dan lokasi aktual MR2 terlebih dahulu."))
        self._ya_check_mr2_physical()

    def _ya_check_mr2_physical(self):
        self.ensure_one()
        # Check exact native quant keys, including lot/owner/package; don't
        # double subtract this picking's reservations.
        Quant=self.env["stock.quant"].sudo()
        totals=defaultdict(float)
        for l in self.move_ids.move_line_ids:
            key=(l.product_id.id,l.location_id.id,l.lot_id.id,l.owner_id.id,l.package_id.id)
            totals[key]+=l.quantity_product_uom
        for (pid,loc,lot,owner,pkg),qty in totals.items():
            q=Quant.search([("company_id","=",self.company_id.id),("product_id","=",pid),
                ("location_id","=",loc),("lot_id","=",lot),("owner_id","=",owner),("package_id","=",pkg)])
            physical=sum(q.mapped("quantity"))
            reserved=sum(q.mapped("reserved_quantity"))
            rounding=self.env["product.product"].browse(pid).uom_id.rounding
            if float_compare(physical,max(qty,reserved),precision_rounding=rounding)<0:
                raise UserError(_("Stok fisik CDC tidak cukup untuk MR2."))

    def button_validate(self):
        grouped=self.filtered("ya_mr2_finalization_id")
        if grouped:
            if len(self)!=1:
                raise UserError(_("Validate MR2 satu dokumen per dapur."))
            self._ya_check_grouped_mr2()
        return super().button_validate()

    def _action_done(self):
        grouped=self.filtered("ya_mr2_finalization_id")
        if grouped:
            if len(self)!=1:
                raise UserError(_("Validate MR2 satu dokumen per dapur."))
            self._ya_check_grouped_mr2()
        return super()._action_done()


class YaMo2MaterialReleaseLine(models.Model):
    _inherit="ya.sale.mo2.release.line"

    ya_mo2_material_picking_ids=fields.One2many(
        "stock.picking","ya_mo2_material_release_line_id",readonly=True)

    def _ya_mr2_pickings(self):
        self.ensure_one()
        grouped=self.env["stock.picking"].search([
            ("ya_mr2_finalization_id","=",self.finalization_id.id),
            ("ya_mr2_kitchen_id","=",self.mo_id.picking_type_id.warehouse_id.id)])
        return grouped|self.ya_mo2_material_picking_ids

    def _ya_create_mo2_cdc_transfer(self):
        """Compatibility entrypoint: create the entire kitchen wave, not just this MO."""
        self.ensure_one()
        if self.env.cr.dbname!=CLONE_DB or not self.env.user.has_group("stock.group_stock_manager"):
            raise UserError(_("Inventory Administrator required in RO_SO."))
        session=self.finalization_id
        batch=session.batch_id
        lock_ro_slot(self.env.cr,batch.delivery_date,batch.slot)
        self.env.invalidate_all()
        session._ya_pp2_frozen_facts()
        kitchen=self.mo_id.picking_type_id.warehouse_id
        company=self.mo_id.company_id
        lines=session.line_ids.filtered(lambda l:l.mo_id.picking_type_id.warehouse_id==kitchen)
        if not lines or self not in lines or company!=self.env.company:
            raise UserError(_("MR2 kitchen/company mismatch."))
        Picking=self.env["stock.picking"].with_company(company)
        if lines.mapped("ya_mo2_material_picking_ids"):
            raise UserError(_("MR2 legacy sudah ada; rekonsiliasi, jangan duplikasi."))
        existing=Picking.search([("ya_mr2_finalization_id","=",session.id),("ya_mr2_kitchen_id","=",kitchen.id)])
        if existing:
            if existing.ya_mr2_issued_demand["line_ids"]!=sorted(lines.ids):
                raise UserError(_("MR2 existing membership mismatch."))
            return existing
        if batch.state!="production_ok" or batch.ya_store_delivery_ids or batch.ya_package_assembly_mo_ids:
            raise UserError(_("MR2 membutuhkan PP2 sebelum distribusi."))
        cdc=self.env["stock.warehouse"].search([("code","=","CDC"),("company_id","=",company.id)])
        if len(cdc)!=1 or cdc==kitchen or kitchen.company_id!=company or kitchen.lot_stock_id.usage!="internal":
            raise UserError(_("Invalid CDC/kitchen route."))
        source=cdc.lot_stock_id
        operation=cdc.int_type_id
        if source.usage!="internal" or operation.code!="internal" or operation.company_id!=company or operation.warehouse_id!=cdc:
            raise UserError(_("Invalid CDC operation."))
        children=set(self.env["stock.location"].search([("id","child_of",kitchen.lot_stock_id.id)]).ids)
        requirements=defaultdict(float)
        products={}
        for line in lines:
            mo=line.mo_id
            if (mo.state!="confirmed" or mo.product_id!=line.product_id or mo.company_id!=company
                    or mo.ya_packing_batch_line_id or mo.location_dest_id!=kitchen.lot_stock_id
                    or mo.location_src_id!=mo.picking_type_id.default_location_src_id
                    or mo.bom_id!=line.planning_line_id._capacity_bom()
                    or abs(mo.product_uom_id._compute_quantity(mo.product_qty,mo.product_id.uom_id,round=False)-line.qty_mo2)>1e-7):
                raise UserError(_("MO2 harus Confirmed dengan Qty/BoM/rute asli."))
            if not mo.move_raw_ids:
                raise UserError(_("MO2 raw moves missing."))
            for move in mo.move_raw_ids:
                mat=move.product_id
                if (move.state in ("done","cancel") or move.location_id.id not in children
                        or not mat.is_storable or (mat.company_id and mat.company_id!=company)):
                    raise UserError(_("Invalid native MO2 raw material."))
                qty=move.product_uom._compute_quantity(move.product_uom_qty,mat.uom_id,round=False)
                if qty<0:
                    raise UserError(_("Negative MO2 material requirement."))
                if qty:
                    requirements[mat.id]+=qty
                    products[mat.id]=mat
        if not requirements:
            raise UserError(_("No positive MO2 material demand."))
        origin_prefix="YA-MR2-%s-CDC-%s"%(session.id,kitchen.code)
        origin="%s / %s / %s / MR2"%(origin_prefix,batch.delivery_date.strftime("%Y-%b-%d"),batch.slot)
        if Picking.search_count(["|",("origin","=",origin_prefix),("origin","=like",origin_prefix+" / %")]):
            raise UserError(_("Unlinked MR2 document; reconcile."))
        picking=Picking.with_context(_ya_mr2_token=_TOKEN).create({
            "ya_mr2_finalization_id":session.id,"ya_mr2_kitchen_id":kitchen.id,
            "ya_mr2_issued_demand":{"line_ids":sorted(lines.ids),
                                    "demand":{str(p):q for p,q in requirements.items()}},
            "picking_type_id":operation.id,"company_id":company.id,
            "location_id":source.id,"location_dest_id":kitchen.lot_stock_id.id,
            "origin":origin,"note":"MR2 | Full MO2 raw demand only. CDC → Dapur. No buffer deduction."})
        moves=self.env["stock.move"].with_company(company).create([
            {"picking_id":picking.id,"product_id":pid,"product_uom":products[pid].uom_id.id,
             "product_uom_qty":qty,"location_id":source.id,"location_dest_id":kitchen.lot_stock_id.id,
             "company_id":company.id} for pid,qty in sorted(requirements.items())])
        # Mimic tested Phase1 low-click prefill for available untracked
        # exact CDC stock-bin items; do not misrepresent unavailable quantities.
        Quant = self.env["stock.quant"].sudo().with_company(company)
        for move in moves:
            mat = move.product_id
            if mat.tracking != "none":
                continue
            quants = Quant.search([
                ("product_id", "=", mat.id),
                ("location_id", "=", source.id),
                ("company_id", "=", company.id),
                ("lot_id", "=", False),
                ("package_id", "=", False),
                ("owner_id", "=", False),
            ])
            free = sum(max(0, q.quantity - q.reserved_quantity) for q in quants)
            if float_compare(move.product_uom_qty, free,
                             precision_rounding=mat.uom_id.rounding) > 0:
                continue
            move.write({"quantity": move.product_uom_qty})
            move.invalidate_recordset(["quantity", "state"])
            if (move.state in ("done", "cancel") or
                    float_compare(
                        move.quantity, move.product_uom_qty,
                        precision_rounding=mat.uom_id.rounding,
                    ) != 0):
                raise UserError(_("MO2 CDC prefilling mismatch, rollback."))
        if picking.state in ("done", "cancel"):
            raise UserError(_("MO2 CDC document already closed unexpectedly."))
        return picking


class PackingBatchMR2(models.Model):
    _inherit="ya.packing.batch"

    def action_mr2_generate_native_transfers(self):
        self.ensure_one()
        if self.env.cr.dbname!=CLONE_DB or not self.env.user.has_group("stock.group_stock_manager"):
            raise UserError(_("Inventory Administrator required in RO_SO."))
        with self.env.cr.savepoint():
            lock_ro_slot(self.env.cr,self.delivery_date,self.slot)
            self.env.invalidate_all()
            final=self.env["ya.sale.mo2.finalization"].sudo().search([("batch_id","=",self.id)])
            if len(final)!=1 or not final.ya_pp2_design_b_snapshot:
                raise UserError(_("MR2 membutuhkan Produksi OK 2."))
            final._ya_pp2_frozen_facts()
            if not final.line_ids:
                raise UserError(_("PP2 selesai tanpa MO2; tidak ada MR2."))
            # Read finalization with sudo only; create under operator's native ACL.
            lines=final.line_ids.with_env(self.env)
            # Stock manager may not have Packing Admin ACL for finalization.
            if not self.env.user.has_group("ya_store_ro.group_ya_packing_admin"):
                raise UserError(_("Packing Admin juga diperlukan untuk akses batch."))
            pickings=self.env["stock.picking"]
            kitchens=lines.mapped("mo_id.picking_type_id.warehouse_id")
            for kitchen in kitchens.sorted("id"):
                first=lines.filtered(lambda l:l.mo_id.picking_type_id.warehouse_id==kitchen)[:1]
                pickings|=first._ya_create_mo2_cdc_transfer()
            return dict(type="ir.actions.act_window",name=_("Internal Transfer MR2"),
                        res_model="stock.picking",view_mode="list,form",
                        domain=[("id","in",pickings.ids)],context={"create":False},target="current")
