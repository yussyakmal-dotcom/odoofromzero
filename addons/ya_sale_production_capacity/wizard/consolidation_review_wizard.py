"""Clone operator review and clock-gated manual release. No timer."""
from odoo.addons.ya_store_ro.models.date_labels import format_ymondd
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.ya_sale_production_capacity.models.pp1_native_sources import DB
from odoo.addons.ya_sale_production_capacity.models.pp1_review_contract import read_locked_review
from odoo.addons.ya_sale_production_capacity.models.consolidation_cutoff_gate import current_clock
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot


class YaConsolidationReviewWizard(models.TransientModel):
    _name = "ya.consolidation.review.wizard"
    _description = "YA Design B PP1 / PP2 Review"

    stage = fields.Selection([("pp1", "Pre Produksi 1"), ("pp2", "Pre Produksi 2")],
                             required=True, default="pp1")
    delivery_date = fields.Date(required=True)
    slot = fields.Selection([("S1","S1 - 05.00 WIB"),("S2","S2 - 09.00 WIB"),
                             ("S3","S3 - 11.00 WIB")], required=True)
    reviewed_identity = fields.Char(readonly=True)
    digest = fields.Char(readonly=True)
    cutoff_info = fields.Char(readonly=True)
    reviewed_cutoff_key = fields.Char(readonly=True)
    line_ids = fields.One2many("ya.consolidation.review.line", "wizard_id", readonly=True)

    @api.onchange("stage", "delivery_date", "slot")
    def _onchange_review_identity(self):
        self.line_ids = [(5,0,0)]
        self.digest = False
        self.reviewed_identity = False
        self.cutoff_info = False
        self.reviewed_cutoff_key = False

    def action_review(self):
        self.ensure_one()
        if self.env.cr.dbname != DB or not self.env.user.has_group("ya_store_ro.group_ya_packing_admin"):
            raise UserError(_("Preview Fase 2 hanya untuk Packing Admin di clone RO_SO."))
        if not self.delivery_date or self.stage not in ("pp1","pp2") or self.slot not in ("S1","S2","S3"):
            raise UserError(_("Pilih tanggal kirim dan slot."))
        lock_ro_slot(self.env.cr, self.delivery_date, self.slot)
        try:
            if self.stage == "pp1":
                review = read_locked_review(self.env, self.delivery_date, self.slot, self.env.company)
            else:
                batch = self.env["ya.packing.batch"].search([
                    ("delivery_date","=",self.delivery_date),("slot","=",self.slot)])
                if len(batch)!=1 or not batch.ya_pp1_design_b_snapshot:
                    raise UserError(_("PP2 membutuhkan PP1 Design B yang sudah Produksi OK."))
                review = batch._ya_read_pp2_design_b_review()
        except ValueError as exc:
            raise UserError(str(exc)) from exc
        rows = []
        for row in review["facts"]["sku_forecasts"]:
            rows.append((0,0,dict(
                product_id=row["product_id"],
                kitchen_id=row["kitchen_route"]["warehouse_id"],
                qty_so=row["confirmed_so_qty"],
                qty_ro_paket=row["original_ro_package_qty"],
                qty_ro=row["original_ro_store_qty"],
                bom_output=row["bom_output"],published_max=row["published_max"],
                qty_mo1=row["forecast_mo1_qty"] if self.stage=="pp1" else row["preexisting_mo1_qty"],
                qty_mo2=0 if self.stage=="pp1" else row["mo2_increment_due_to_so_only"],
                shortage_ro_paket=row["forecast_ro_package_shortage"],
                shortage_ro=row["forecast_ro_store_shortage"],
                surplus=row["forecast_unallocated_surplus"] if self.stage=="pp1"
                    else row["theoretical_extra_not_automatically_allocated"],
            )))
        clock = current_clock(self.env,self.delivery_date,self.slot)
        deadline = clock["ro_cutoff"] if self.stage=="pp1" else clock["pp2_earliest"]
        ready = clock["pp1_clock_ready"] if self.stage=="pp1" else clock["pp2_clock_ready"]
        info = (_("Boleh release setelah review.") if ready else
                _("Belum boleh release / dispatch sudah lewat."))
        info += " " + ((format_ymondd(deadline)+deadline.strftime(" %H:%M WIB")) if deadline else _("Cutoff SO belum ditetapkan."))
        info = clock["cutoff_source"] + " — " + info
        self.write(dict(line_ids=[(5,0,0)]+rows,digest=review["digest"],cutoff_info=info,
                        reviewed_cutoff_key=self._cutoff_key(clock),
                        reviewed_identity="%s / %s / %s"%(self.stage.upper(),format_ymondd(self.delivery_date),self.slot)))
        return dict(type="ir.actions.act_window",name=_("Review Konsolidasi Fase 2"),
                    res_model=self._name,res_id=self.id,view_mode="form",target="current",
                    views=[(self.env.ref("ya_sale_production_capacity.view_ya_consolidation_review_wizard").id,"form")])

    @api.model
    def _cutoff_key(self, clock):
        return "%s:%s" % (clock["cutoff_source"], clock["special_cutoff_id"] or clock["cutoff_settings_version_id"] or 0)

    def action_release(self):
        self.ensure_one()
        if self.env.cr.dbname != DB or not self.env.user.has_group("ya_store_ro.group_ya_packing_admin"):
            raise UserError(_("Produksi OK hanya untuk Packing Admin di clone RO_SO."))
        self.check_access("write")
        day,slot,stage=self.delivery_date,self.slot,self.stage
        if not day or slot not in ("S1","S2","S3") or stage not in ("pp1","pp2"):
            raise UserError(_("Pilih tanggal kirim, slot dan tahap."))
        with self.env.cr.savepoint():
            lock_ro_slot(self.env.cr,day,slot)
            self.env.cr.execute("SELECT id FROM ya_consolidation_review_wizard WHERE id=%s FOR UPDATE",[self.id])
            self.invalidate_recordset()
            identity="%s / %s / %s"%(stage.upper(),format_ymondd(day),slot)
            if (self.delivery_date!=day or self.slot!=slot or self.stage!=stage or
                    self.reviewed_identity!=identity or not self.digest):
                raise UserError(_("Refresh review sebelum Produksi OK."))
            clock=current_clock(self.env,day,slot)
            if self.reviewed_cutoff_key != self._cutoff_key(clock):
                raise UserError(_("Jadwal cutoff berubah. Refresh review sebelum Produksi OK."))
            if stage=="pp1" and not clock["pp1_clock_ready"]:
                raise UserError(_("Produksi OK 1 hanya setelah cutoff RO dan sebelum dispatch."))
            if stage=="pp2" and not clock["pp2_clock_ready"]:
                raise UserError(_("Produksi OK 2 membutuhkan cutoff SO terkonfigurasi, jeda MO2 terpenuhi dan sebelum dispatch."))
            Batch=self.env["ya.packing.batch"]
            # Core independently rechecks the source digest, under slot lock.
            if stage=="pp1":
                batch=Batch._ya_create_pp1_design_b_release_core(day,slot,self.digest)
            else:
                batch=Batch.search([("delivery_date","=",day),("slot","=",slot)])
                if len(batch)!=1 or not batch.ya_pp1_design_b_snapshot:
                    raise UserError(_("PP2 membutuhkan PP1 Design B yang sudah Produksi OK."))
                batch._ya_release_pp2_design_b_core(self.digest)
            self.write({"digest":False,"cutoff_info":_("Produksi OK berhasil.")})
            return dict(type="ir.actions.act_window",name=_("Produksi OK"),
                        res_model="ya.packing.batch",res_id=batch.id,
                        view_mode="form",target="current")


class YaConsolidationReviewLine(models.TransientModel):
    _name = "ya.consolidation.review.line"
    _description = "YA Consolidation Review SKU"
    _order = "kitchen_id, product_id"

    wizard_id = fields.Many2one("ya.consolidation.review.wizard",required=True,ondelete="cascade")
    product_id = fields.Many2one("product.product",readonly=True)
    kitchen_id = fields.Many2one("stock.warehouse",readonly=True)
    qty_so = fields.Integer(readonly=True)
    qty_ro_paket = fields.Integer(readonly=True)
    qty_ro = fields.Integer(readonly=True)
    bom_output = fields.Integer(readonly=True)
    published_max = fields.Integer(readonly=True)
    qty_mo1 = fields.Integer(readonly=True)
    qty_mo2 = fields.Integer(readonly=True)
    shortage_ro_paket = fields.Integer(readonly=True)
    shortage_ro = fields.Integer(readonly=True)
    surplus = fields.Integer(readonly=True)
