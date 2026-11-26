"""YA SO Confirm wizard: atomic locked capacity + commercial SO on RO_SO clone."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.ya_store_ro.models.date_labels import format_ymondd


class YaSaleCapacityConfirmWizard(models.TransientModel):
    _name = 'ya.sale.capacity.confirm.wizard'
    _description = 'YA Sales Order Delivery Schedule Confirmation Gate'

    order_id = fields.Many2one('sale.order', required=True, readonly=True)
    delivery_date = fields.Date(string='YA Tanggal Kirim', required=True)
    slot = fields.Selection(
        [('S1', 'S1 - 05.00 WIB'), ('S2', 'S2 - 09.00 WIB'),
         ('S3', 'S3 - 11.00 WIB')],
        string='YA Slot Kirim', required=True,
    )
    delivery_date_label = fields.Char(
        string='Format YYYY-Mon-DD', compute='_compute_delivery_date_label',
    )

    @api.depends('delivery_date')
    def _compute_delivery_date_label(self):
        for wizard in self:
            wizard.delivery_date_label = format_ymondd(wizard.delivery_date)

    impact_digest=fields.Char(readonly=True)
    impact_payload=fields.Json(readonly=True)
    impact_summary=fields.Text(readonly=True)

    @api.onchange("delivery_date","slot")
    def _onchange_impact_schedule(self):
        self.impact_digest=False
        self.impact_payload=False
        self.impact_summary=False

    def _read_impact(self):
        self.ensure_one()
        self.check_access("write")
        if not self.delivery_date or not self.slot:
            raise ValidationError(_("YA Tanggal Kirim dan YA Slot Kirim wajib diisi."))
        return self.order_id._ya_read_sales_impact(self.delivery_date,self.slot)

    def action_review_impact(self):
        self.ensure_one()
        result=self._read_impact()
        data=result["payload"]
        lines=["Sebelum Produksi OK 1: proyeksi MO1" if data["stage"]=="pp1" else
               "Setelah Produksi OK 1: MO1 tetap; MO2 hanya untuk kebutuhan SO."]
        if not data["ro_closed"]:
            lines.append("PERHATIAN: RO belum ditutup. Demand RO yang diketahui masih bisa bertambah.")
        lines.append("Proyeksi kapasitas, bukan stok fisik atau jaminan ketersediaan Paket.")
        for r in data["lines"]:
            product=self.env["product.product"].browse(r["product_id"])
            lines.extend(["",product.display_name,
                "SO terkonfirmasi: %s → %s (draft +%s)"%(r["so_before"],r["so_after"],r["new_qty"]),
                "BoM %s | Max %s | Sisa kapasitas SO %s"%(r["bom_output"],r["published_max"],r["remaining_capacity"]),
                "Produksi total: %s → %s (tambahan %s)"%(r["output_before"],r["output_after"],r["additional_output"]),
                "MO1 native %s | Proyeksi MO2 %s → %s"%(r["mo1"],r["mo2_before"],r["mo2_after"]),
                "Surplus: %s → %s (baru %s, terserap %s)"%(r["surplus_before"],r["surplus_after"],r["new_surplus"],r["absorbed_surplus"]),
                "RO Paket komponen %s | kurang %s → %s"%(r["ro_package"],r["ro_package_short_before"],r["ro_package_short_after"]),
                "RO biasa %s | kurang %s → %s"%(r["ro_store"],r["ro_store_short_before"],r["ro_store_short_after"])])
            if r["new_surplus"] or r["ro_package_short_after"]>r["ro_package_short_before"] or r["ro_store_short_after"]>r["ro_store_short_before"]:
                lines.append("PERHATIAN: tinjau surplus / dampak RO sebelum Confirm.")
        for pid,qty in data["pck_requirements"]:
            lines.append("Komponen Paket PCK: %s | kebutuhan %s (stok belum diverifikasi)"%(
                self.env["product.product"].browse(pid).display_name,qty))
        self.write({"impact_digest":result["digest"],"impact_payload":data,"impact_summary":"\n".join(lines)})
        return dict(type="ir.actions.act_window",name=_("Simulasi Dampak Sales Order"),
                    res_model=self._name,res_id=self.id,view_mode="form",
                    views=[(self.env.ref("ya_sale_production_capacity.view_ya_sale_capacity_confirm_wizard_form").id,"form")],
                    target="new")

    def action_check_and_confirm(self):
        self.ensure_one()
        with self.env.cr.savepoint():
            if not self.impact_digest:
                raise UserError(_("Jalankan Simulasi Dampak terlebih dahulu."))
            fresh=self._read_impact()
            if fresh["digest"]!=self.impact_digest:
                raise UserError(_("Data berubah. Jalankan ulang Simulasi Dampak sebelum Confirm."))
            # The same transaction holds slot/order locks across preview and
            # the existing atomic native Confirm. No warning is a hard gate.
            return self.order_id._ya_confirm_with_protected_capacity(self.delivery_date,self.slot)
