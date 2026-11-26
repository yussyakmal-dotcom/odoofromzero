"""Clone UAT: approved allocation -> native DO -> existing native store receipt.
No new stock ledger. Native assignment must succeed for every DO atomically.
No automatic Validate, no automatic reallocation or recovery of closed DO.
"""
from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from .pp1_native_sources import DB, PP1SourceError
from .final_packing_review import GROUP
from .final_packing_delivery_bridge import _qa_generate_native_deliveries

_TOKEN=object()


def _qty(m,field):
    return m.product_uom._compute_quantity(m[field],m.product_id.uom_id,round=False)


def _same(a,b):
    return set(a)==set(b) and all(abs(a[k]-b[k])<1e-7 for k in a)


def _totals(moves,field):
    out=defaultdict(float)
    for m in moves:
        out[m.product_id.id]+=_qty(m,field)
    return dict(out)


class FinalPackingDistribution(models.Model):
    _name="ya.final.packing.distribution"
    _description="Post Produksi - Native DO Release"
    _rec_name="release_id"

    release_id=fields.Many2one("ya.final.packing.release",required=True,index=True,readonly=True,ondelete="restrict")
    customer_ids=fields.Many2many("stock.picking","ya_final_distribution_customer_rel","distribution_id","picking_id",readonly=True,copy=False)
    dispatch_ids=fields.Many2many("stock.picking","ya_final_distribution_dispatch_rel","distribution_id","picking_id",readonly=True,copy=False)
    _unique_release=models.Constraint("UNIQUE(release_id)","DO already issued for final release.")

    @api.model_create_multi
    def create(self,vals_list):
        if (self.env.cr.dbname!=DB or not self.env.user.has_group(GROUP)
                or self.env.context.get("_ya_distribution_token") is not _TOKEN):
            raise UserError(_("DO harus melalui Release Final Packing."))
        return super().create(vals_list)

    def write(self,vals):
        raise UserError(_("Distribusi final immutable."))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_distribution(self):
        raise UserError(_("Distribusi final tidak boleh dihapus."))

    def _open_deliveries(self):
        self.ensure_one()
        self.check_access("read")
        receipts=self.env["stock.picking"].search([("ya_source_dispatch_id","in",self.dispatch_ids.ids)])
        return dict(type="ir.actions.act_window",name=_("DO Pelanggan / Toko dan Receipt"),
                    res_model="stock.picking",view_mode="list,form",
                    domain=[("id","in",(self.customer_ids|self.dispatch_ids|receipts).ids)],
                    context={"create":False},target="current")


class FinalPackingReviewDistribution(models.Model):
    _inherit="ya.final.packing.review"

    def action_generate_final_deliveries(self):
        self.ensure_one()
        if self.env.cr.dbname!=DB or not self.env.user.has_group(GROUP):
            raise UserError(_("Packing Admin di clone RO_SO diperlukan."))
        self.check_access("read")
        batch=self.batch_id
        batch.check_access("read")
        Distribution=self.env["ya.final.packing.distribution"]
        with self.env.cr.savepoint():
            lock_ro_slot(self.env.cr,batch.delivery_date,batch.slot)
            self.env.invalidate_all()
            release=self.release_ids
            if len(release)!=1:
                raise UserError(_("Release Final dahulu."))
            data=release._verified_review()
            existing=Distribution.search([("release_id","=",release.id)])
            if existing:
                return existing._open_deliveries()
            batch._ya_pp1_frozen_facts()
            final=self.env["ya.sale.mo2.finalization"].search([("batch_id","=",batch.id)])
            if len(final)!=1 or final.id!=data["demand"]["supply"]["finalization_id"]:
                raise UserError(_("Identitas finalisasi PP2 berubah."))
            final._ya_pp2_frozen_facts()
            # After assembly, the original stock digest is intentionally
            # no longer current. Verify source identities and actual assembly
            # consumption instead, then require fresh native DO reservations.
            original=data["demand"]["recipient_rows"]
            rows=data["validated"]["rows"]
            by_key={(r["kind"],r["source_id"],r["line_id"]):r for r in original}
            orders=defaultdict(list)
            parts=defaultdict(lambda:defaultdict(float))
            for row in rows:
                src=by_key[(row["kind"],row["source_id"],row["line_id"])]
                if row["kind"] in ("SO","SO_PAKET"):
                    orders[row["source_id"]].append(src)
                else:
                    model="ya.package.store.ro" if row["kind"]=="RO_PAKET" else "ya.store.ro"
                    ro=self.env[model].sudo().browse(row["source_id"]).exists()
                    if (len(ro)!=1 or ro.state!="confirmed" or ro.delivery_date!=batch.delivery_date
                            or ro.slot!=batch.slot or ro.store_warehouse_id.id!=row["recipient_id"]):
                        raise UserError(_("RO source changed after release."))
                    line=ro.line_ids.filtered(lambda l:l.id==row["line_id"])
                    if len(line)!=1 or line.product_id.id!=row["product_id"]:
                        raise UserError(_("RO line changed after release."))
                    if abs(line.uom_id._compute_quantity(line.qty_requested,line.product_id.uom_id,round=False)
                           -row["qty_requested"])>1e-7:
                        raise UserError(_("RO quantity changed after release."))
                if row["kind"] in ("SO_PAKET","RO_PAKET") and row["qty_allocated"]:
                    for c in src["components"]:
                        parts[row["product_id"]][c["product_id"]]+=c["qty_per_package"]*row["qty_allocated"]
            for oid,src in orders.items():
                order=self.env["sale.order"].sudo().browse(oid)
                commercial=order.order_line.filtered(lambda l:not l.display_type and not l.is_downpayment and not l._is_global_discount())
                if set(commercial.ids)!={r["line_id"] for r in src}:
                    raise UserError(_("SO line membership changed."))
                if order.ya_confirmed_demand_snapshot:
                    order._ya_verified_confirmed_demand(src)
            for mo in release.assembly_ids:
                if mo.state!="done" or any(m.state!="done" for m in mo.move_raw_ids):
                    raise UserError(_("Paket assembly not DONE"))
                if not _same(_totals(mo.move_raw_ids,"quantity"),parts[mo.product_id.id]):
                    raise UserError(_("Actual Paket component consumption differs from approved allocation."))
            try:
                customers,dispatches=_qa_generate_native_deliveries(batch,data["demand"],data["validated"])
            except (PP1SourceError,ValueError) as exc:
                raise UserError(str(exc)) from exc
            record=Distribution.with_context(_ya_distribution_token=_TOKEN).create({
                "release_id":release.id,"customer_ids":[(6,0,customers.ids)],
                "dispatch_ids":[(6,0,dispatches.ids)]})
            return record._open_deliveries()


class ApprovedNativeDeliveryPicking(models.Model):
    _inherit="stock.picking"

    def _ya_approved_distribution(self,field):
        self.ensure_one()
        return self.env["ya.final.packing.distribution"].sudo().search([(field,"in",[self.id])])

    def _ya_store_delivery_db_allowed(self):
        self.ensure_one()
        if self.env.cr.dbname!=DB:
            return super()._ya_store_delivery_db_allowed()
        self=self.sudo()  # Read approved identity only; native Validate retains actor ACL.
        dispatch=self if self.ya_store_stage=="dispatch" else self.ya_source_dispatch_id
        if not dispatch:
            return False
        dist=dispatch._ya_approved_distribution("dispatch_ids")
        if len(dist)!=1:
            return False
        rel=dist.release_id
        if (rel.batch_id!=self.ya_store_batch_id or rel.company_id!=self.company_id
                or dispatch.ya_store_stage!="dispatch"
                or dispatch.ya_store_batch_id!=self.ya_store_batch_id
                or dispatch.ya_store_warehouse_id!=self.ya_store_warehouse_id):
            return False
        # Preserve existing dispatch/receipt partial/zero semantics. The
        # original approved dispatch demand may not be edited.
        expected=defaultdict(float)
        for r in rel.review_id.evidence["validated"]["rows"]:
            if r["kind"] in ("RO","RO_PAKET") and r["recipient_id"]==dispatch.ya_store_warehouse_id.id and r["qty_allocated"]:
                expected[r["product_id"]]+=r["qty_allocated"]
        if not _same(_totals(dispatch.move_ids,"product_uom_qty"),expected):
            return False
        if self.ya_store_stage=="receipt":
            shipped=_totals(dispatch.move_ids.filtered(lambda m:m.state=="done"),"quantity")
            if not _same(_totals(self.move_ids,"product_uom_qty"),shipped):
                return False
        return True

    def _ya_check_approved_customer(self):
        if self.env.cr.dbname!=DB:
            return
        for picking in self:
            dist=picking._ya_approved_distribution("customer_ids")
            if not dist:
                continue
            if len(dist)!=1:
                raise UserError(_("Customer DO approval ambiguous."))
            rel=dist.release_id
            batch=rel.batch_id
            lock_ro_slot(self.env.cr,batch.delivery_date,batch.slot)
            self.env.invalidate_all()
            order=picking.sudo().move_ids.mapped("sale_line_id.order_id")
            if len(order)!=1 or order.company_id!=rel.company_id or picking.company_id!=rel.company_id:
                raise UserError(_("Customer DO source mismatch."))
            data=rel.review_id.evidence
            expected={r["line_id"]:r for r in data["validated"]["rows"]
                      if r["kind"] in ("SO","SO_PAKET") and r["source_id"]==order.id}
            root=self.env["stock.warehouse"].sudo().browse(data["demand"]["supply"]["pck_id"]).lot_stock_id
            if (picking.state!="assigned" or picking.location_id!=root
                    or picking.location_dest_id!=order.partner_shipping_id.with_company(order.company_id).property_stock_customer
                    or picking.partner_id!=order.partner_shipping_id
                    or len(picking.move_ids)!=len(expected)
                    or set(picking.move_ids.mapped("sale_line_id").ids)!=set(expected)):
                raise UserError(_("Customer DO must match approved full demand and route."))
            for m in picking.move_ids:
                r=expected[m.sale_line_id.id]
                if (m.product_id.id!=r["product_id"] or r["recipient_id"]!=picking.partner_id.id
                        or m.state!="assigned" or not m.picked or not m.move_line_ids
                        or abs(_qty(m,"product_uom_qty")-r["qty_allocated"])>1e-7
                        or abs(_qty(m,"quantity")-r["qty_allocated"])>1e-7
                        or m.location_id!=root or m.location_dest_id!=picking.location_dest_id
                        or any(l.location_id!=root or l.location_dest_id!=picking.location_dest_id
                               or l.lot_id or l.owner_id or l.package_id for l in m.move_line_ids)):
                    raise UserError(_("Confirmed SO must be picked and shipped in full."))

    def button_validate(self):
        self._ya_check_approved_customer()
        return super().button_validate()

    def _action_done(self):
        self._ya_check_approved_customer()
        return super()._action_done()
