"""Advisory, non-stored quotation display. No booking or SQL fence writes.

Uses the same kitchen expansion as Confirm, including Paket components.
Numbers are a snapshot, refreshed on field changes or browser reload.
"""
from collections import defaultdict
from markupsafe import Markup
from odoo import api, fields, models
from odoo.exceptions import UserError
from .pp1_native_sources import DB, read_pp1_sources, require
from .consolidation_cutoff_gate import current_clock
from .pp1_design_b_rules import plan_pp1
from .mo2_owner_so_first_rules import plan_so_first_only


def note(text, kind="info"):
    return Markup('<div class="alert alert-{} py-2 mb-2" role="alert">{}</div>').format(kind,text)


def table(headers, rows):
    head=Markup("").join(Markup('<th scope="col">{}</th>').format(h) for h in headers)
    body=Markup("").join(Markup("<tr>{}</tr>").format(Markup("").join(
        Markup('<td class="{}">{}</td>').format(
            "text-end" if isinstance(v,(int,float)) else "",v) for v in row)) for row in rows)
    return Markup('<div class="table-responsive"><table class="table table-sm table-bordered align-middle mb-2"><thead><tr>{}</tr></thead><tbody>{}</tbody></table></div>').format(head,body)


class SaleOrderCapacityDisplay(models.Model):
    _inherit="sale.order"

    ya_capacity_display=fields.Html(string="Kapasitas Produksi",compute="_compute_ya_capacity_display",
        compute_sudo=False,readonly=True,store=False)

    @api.depends("ya_is_capacity_so","state","ya_delivery_date","ya_slot","company_id",
                 "order_line.product_id","order_line.product_uom_qty","order_line.product_uom_id",
                 "order_line.display_type","order_line.is_downpayment","order_line.name")
    def _compute_ya_capacity_display(self):
        for order in self:
            order.ya_capacity_display=False
            if (order.env.cr.dbname!=DB or not order.ya_is_capacity_so
                    or order.state not in ("draft","sent")
                    or not order.env.user.has_group("sales_team.group_sale_salesman")):
                continue
            if not order.ya_delivery_date or not order.ya_slot:
                order.ya_capacity_display=note("Pilih Tanggal Kirim dan Slot Kirim terlebih dahulu.")
                continue
            if not order.order_line.filtered(lambda l:l.product_id and not l.display_type and not l.is_downpayment and not l._is_global_discount()):
                order.ya_capacity_display=note("Pilih produk dan masukkan Qty untuk melihat kapasitas.")
                continue
            try:
                order.ya_capacity_display=order._ya_draft_capacity_display()
            except (UserError,ValueError) as exc:
                order.ya_capacity_display=note(str(exc),"warning")

    def _ya_draft_capacity_display(self):
        self.ensure_one()
        require(self.company_id==self.env.company,"Periksa perusahaan Sales Order.")
        day,slot=self.ya_delivery_date,self.ya_slot
        clock=current_clock(self.env,day,slot)
        domain=[("delivery_date","=",day),("slot","=",slot)]
        preview=self._ya_prepare_capacity_confirm_readonly(day,slot,display_only=True)
        ledger=self.env["ya.sale.capacity.reservation"].sudo().search(domain)
        confirmed=self.env["sale.order"].sudo().search([
            ("ya_is_capacity_so","=",True),("ya_delivery_date","=",day),
            ("ya_slot","=",slot),("state","in",["sale","done"])])
        require(set(confirmed.ids)==set(ledger.mapped("order_id").ids),
                "Data SO dan reservasi tidak cocok; perlu rekonsiliasi.")
        used=defaultdict(int)
        for r in ledger:
            require(r.order_id.company_id==self.company_id and r.qty_required>0
                    and r.product_id==r.planning_line_id.product_id
                    and r.planning_line_id.planning_id.state=="published"
                    and r.planning_line_id.planning_id.delivery_date==day
                    and r.planning_line_id.planning_id.slot==slot,
                    "Data reservasi kapasitas tidak konsisten.")
            used[r.planning_line_id.id]+=r.qty_required
        batch=self.env["ya.packing.batch"].sudo().search(domain)
        require(len(batch)<=1,"Batch Packing ganda; perlu rekonsiliasi.")
        closed=not clock["so_admission_allowed"]
        if batch:
            require(batch.ya_pp1_design_b_snapshot and batch.state=="production_ok",
                    "Batch lama belum direkonsiliasi dengan Fase 2.")
            facts=batch._ya_pp1_frozen_facts()
            require(facts["company_id"]==self.company_id.id,"Perusahaan batch tidak cocok.")
            closed=closed or bool(self.env["ya.sale.mo2.finalization"].sudo().search_count(
                [("batch_id","=",batch.id)])) or bool(batch.ya_store_delivery_ids or
                batch.ya_package_assembly_mo_ids or any(t.state=="done" for t in batch.ya_fg_transfer_ids))
        else:
            facts=read_pp1_sources(self.env,day,slot,self.company_id)
        base={r["product_id"]:r for r in facts["sku_forecasts"]}
        rows=[]
        allocation_rows=[]
        for r in preview["capacity"]:
            product=self.env["product.product"].browse(r["product_id"])
            prior=used[r["planning_line_id"]]
            maximum=r["published_max"]
            draft=r["new_qty"]
            remaining=maximum-prior-draft
            ro=base.get(product.id,{})
            pkg=ro.get("original_ro_package_qty",0)
            store=ro.get("original_ro_store_qty",0)
            common=dict(original_ro_package_qty=pkg,original_ro_store_qty=store,
                        published_max=maximum)
            # Reuse the existing SO-first forecast; never subtract raw RO
            # from the available SO quantity or add RO twice.
            if batch:
                qty1=ro.get("forecast_mo1_qty",0)
                native=batch.line_ids.filtered(lambda line:line.product_id==product)
                require(len(native)==int(qty1>0),"MO1 tidak sesuai snapshot; perlu rekonsiliasi.")
                if native:
                    mo=native.mo_id
                    require(mo and mo.state not in ("draft","cancel") and mo.product_id==product
                            and abs(mo.product_uom_id._compute_quantity(
                                mo.product_qty,product.uom_id,round=False)-qty1)<1e-9,
                            "MO1 berubah atau dibatalkan; perlu rekonsiliasi.")
                def forecast(so):
                    return plan_so_first_only(confirmed_so_qty=so,existing_mo1_output=qty1,
                        existing_mo2_output=0,kitchen_bom_output=r["bom_output"],**common)
                output_key="forecast_total_output"
                surplus_key="theoretical_extra_not_automatically_allocated"
            else:
                def forecast(so):
                    return plan_pp1(confirmed_so_qty=so,bom_output=r["bom_output"],**common)
                output_key="forecast_mo1_qty"
                surplus_key="forecast_unallocated_surplus"
            before=forecast(prior)
            out=before[output_key]
            pkg_before=before["forecast_ro_package_covered"]
            store_before=before["forecast_ro_store_covered"]
            surplus=before[surplus_key]
            available=maximum-prior
            require(available==maximum-out+pkg_before+store_before+surplus,
                    "Komponen kapasitas tidak seimbang.")
            # An invalid/closed draft must not show a fabricated after-allocation.
            after=forecast(prior+draft) if not closed and remaining>=0 else None
            status=("Ditutup" if closed else "Melebihi Max" if remaining<0 else
                    "Tanpa tambah produksi" if after[output_key]==out else "Tambah produksi")
            label=product.display_name+" ("+product.uom_id.name+")"
            rows.append((label,maximum,prior,store_before,
                         0 if closed else available,draft,remaining if not closed else "—",status))
            def transition(key):
                return "%s → %s"%(before[key],after[key]) if after is not None else "%s → —"%before[key]
            allocation_rows.append((label,transition(output_key),maximum-out,
                pkg,transition("forecast_ro_package_covered"),store,
                transition("forecast_ro_store_covered"),transition(surplus_key)))
        result=note("SO dapat mengambil sisa jatah RO tanpa menambah produksi. "
                    "Tersedia SO = sisa kapasitas produksi + sisa jatah RO Paket + sisa jatah RO Toko + surplus. "
                    "Angka adalah proyeksi per SKU, bukan stok fisik.")
        if clock["special_cutoff_id"]:
            result+=note("Special Cutoff berlaku untuk tanggal dan slot ini.")
        if not clock["ro_closed"]:
            result+=note("RO belum ditutup; permintaan masih dapat bertambah.")
        if closed:
            result+=note("Penerimaan SO untuk jadwal ini telah ditutup. Jatah dan produksi di bawah adalah proyeksi historis, bukan stok yang bisa dijual.","warning")
        result+=table(("SKU / Nama Produk","Planning Max","SO Confirmed","Sisa Jatah RO Toko",
            "Tersedia SO","SO Ini","Sisa SO Setelah","Status"),rows)
        result+=Markup("<h5>Rincian Kapasitas dan Jatah RO</h5>")
        result+=table(("SKU / Nama Produk","Produksi sebelum → sesudah","Sisa Kapasitas Produksi",
            "Permintaan RO Paket","Jatah RO Paket sebelum → sesudah","Permintaan RO Toko",
            "Jatah RO Toko sebelum → sesudah","Surplus sebelum → sesudah"),allocation_rows)
        if preview["package_qty"]:
            result+=note("Paket dihitung berdasarkan kebutuhan komponen dapur; stok komponen PCK belum diverifikasi.")
        return result
