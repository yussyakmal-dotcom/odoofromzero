"""Review only. Manual explicit proposal; no default recipient ranking."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from ..models.final_packing_review import _TOKEN, GROUP
from ..models.pp1_native_sources import DB
from ..models.final_packing_demand import read_final_packing_demand
from ..models.final_packing_proposal_rules import build_proposal_template, validate_proposal, source_digest, auto_allocate, PRORATA_POLICY, key
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from odoo.addons.ya_store_ro.models.allocation_rules import allocate_capacity_prorata, allocate_surplus_prorata


class FinalPackingReviewWizard(models.TransientModel):
    _name="ya.final.packing.review.wizard"
    _description="Post Produksi - Final Packing Allocation Review"

    batch_id=fields.Many2one("ya.packing.batch",required=True,readonly=True)
    digest=fields.Char(readonly=True)
    line_ids=fields.One2many("ya.final.packing.review.line","wizard_id")
    supply_ids=fields.One2many("ya.final.packing.supply.line","wizard_id",readonly=True)
    reason=fields.Text(string="Catatan keputusan alokasi")
    result=fields.Text(readonly=True)

    def _guard(self):
        self.ensure_one()
        if self.env.cr.dbname!=DB or not self.env.user.has_group(GROUP):
            raise UserError(_("Packing Admin di clone RO_SO diperlukan."))
        self.check_access("write")
        self.batch_id.check_access("read")
        lock_ro_slot(self.env.cr,self.batch_id.delivery_date,self.batch_id.slot)
        self.env.invalidate_all()
        if self.env["ya.final.packing.release"].sudo().search_count([("batch_id","=",self.batch_id.id)]):
            raise UserError(_("Final Packing sudah release; buka Riwayat Review Alokasi."))

    def _read(self):
        try:
            return read_final_packing_demand(self.batch_id)
        except ValueError as exc:
            raise UserError(str(exc)) from exc

    def _reopen(self):
        return dict(type="ir.actions.act_window",name=_("Post Produksi / Final Packing Allocation"),
                    res_model=self._name,res_id=self.id,view_mode="form",
                    views=[(self.env.ref("ya_sale_production_capacity.view_ya_final_packing_review_wizard").id,"form")],
                    target="current")

    def action_refresh(self):
        self._guard()
        demand=self._read()
        lines=[]
        for r in demand["recipient_rows"]:
            is_so=r["kind"] in ("SO","SO_PAKET")
            source=self.env["sale.order" if is_so else
                "ya.package.store.ro" if r["kind"]=="RO_PAKET" else "ya.store.ro"].sudo().browse(r["source_id"])
            recipient=self.env["res.partner" if is_so else "stock.warehouse"].sudo().browse(r["recipient_id"])
            lines.append((0,0,dict(kind=r["kind"],source_id=r["source_id"],line_id=r["line_id"],
                recipient_id=r["recipient_id"],source_label=source.display_name,
                recipient_label=recipient.display_name,product_id=r["product_id"],qty_requested=r["qty"],
                qty_allocated=r["qty"] if is_so else -1)))
        supplies=[]
        for r in demand["supply"]["rows"]:
            supplies.append((0,0,dict(product_id=r["product_id"],source_kind="KITCHEN",
                received=r["mo1_mo2_received_qty"],physical=r["pck_physical"],
                reserved=r["pck_reserved"],free=r["pck_free"],upper_bound=r["slot_supply_upper_bound"])))
        for r in demand["pck_component_rows"]:
            supplies.append((0,0,dict(product_id=r["product_id"],source_kind="PCK",
                physical=r["physical"],reserved=r["reserved"],free=r["free"],
                upper_bound=r["free"] if r["tracking"]=="none" else 0)))
        self.write({"digest":source_digest(demand),"line_ids":[(5,0,0)]+lines,
            "supply_ids":[(5,0,0)]+supplies,"result":False,"reason":False})
        return self._reopen()

    def _allocation_error(self, exc):
        import re
        msg=str(exc)
        match=re.search(r"\('(?:KITCHEN|PCK)', (\d+)\)",msg)
        if match:
            product=self.env["product.product"].browse(int(match.group(1))).exists()
            if product:
                msg=msg[:match.start()]+product.display_name+msg[match.end():]
        return UserError(msg)

    def action_auto_allocate(self):
        self._guard()
        demand=self._read()
        if self.digest!=source_digest(demand):
            raise UserError(_("Data sumber/stok berubah. Refresh dahulu."))
        try:
            proposal=auto_allocate(demand,allocate_capacity_prorata,allocate_surplus_prorata)
        except ValueError as exc:
            raise self._allocation_error(exc) from exc
        quantities={key(r):r["qty_allocated"] for r in proposal["rows"]}
        for line in self.line_ids:
            ident=(line.kind,line.source_id,line.line_id,line.recipient_id,line.product_id.id)
            if ident not in quantities:
                raise UserError(_("Baris review berubah. Refresh dahulu."))
            line.qty_allocated=quantities[ident]
        self.result=_("Usulan prorata terisi. Periksa dan koreksi sebelum Simpan Review.")
        return self._reopen()

    def action_save_review(self):
        self._guard()
        with self.env.cr.savepoint():
            demand=self._read()
            if self.digest!=source_digest(demand):
                raise UserError(_("Data sumber/stok berubah. Refresh review sebelum menyimpan."))
            if not self.reason or not self.reason.strip():
                raise UserError(_("Isi catatan keputusan review."))
            proposal=build_proposal_template(demand,policy=PRORATA_POLICY)
            proposal["rows"]=[dict(kind=l.kind,source_id=l.source_id,line_id=l.line_id,
                recipient_id=l.recipient_id,product_id=l.product_id.id,qty_allocated=l.qty_allocated)
                for l in self.line_ids]
            try:
                validated=validate_proposal(demand,proposal)
            except ValueError as exc:
                raise self._allocation_error(exc) from exc
            evidence=dict(demand=demand,proposal=proposal,validated=validated)
            review=self.env["ya.final.packing.review"].with_context(_ya_final_review_token=_TOKEN).create({
                "batch_id":self.batch_id.id,"company_id":self.env.company.id,
                "source_digest":self.digest,"evidence_digest":source_digest(evidence),
                "evidence":evidence,"reason":self.reason,
                "warning_count":len(validated["review_warnings"]),
                "shortage_total":sum(r["qty_shortage"] for r in validated["rows"])})
            self.result=_("Review #%s tersimpan. Belum reservasi, approval release, MO Paket atau DO.") % review.id
            return self._reopen()


class FinalPackingReviewLine(models.TransientModel):
    _name="ya.final.packing.review.line"
    _description="Review Alokasi per Penerima"
    _order="kind, source_id, line_id"

    wizard_id=fields.Many2one("ya.final.packing.review.wizard",required=True,ondelete="cascade")
    kind=fields.Selection([("SO","SO"),("SO_PAKET","SO Paket"),("RO_PAKET","RO Paket"),("RO","RO")],readonly=True)
    source_id=fields.Integer(readonly=True)
    line_id=fields.Integer(readonly=True)
    recipient_id=fields.Integer(readonly=True)
    source_label=fields.Char(readonly=True)
    recipient_label=fields.Char(readonly=True)
    product_id=fields.Many2one("product.product",readonly=True)
    qty_requested=fields.Integer(readonly=True)
    qty_allocated=fields.Integer(default=-1)
    qty_shortage=fields.Integer(compute="_compute_shortage")
    qty_surplus=fields.Integer(compute="_compute_shortage")

    @api.depends("qty_allocated","qty_requested")
    def _compute_shortage(self):
        for r in self:
            r.qty_shortage=max(r.qty_requested-r.qty_allocated,0) if r.qty_allocated>=0 else 0
            r.qty_surplus=max(r.qty_allocated-r.qty_requested,0)


class FinalPackingSupplyLine(models.TransientModel):
    _name="ya.final.packing.supply.line"
    _description="Stok Fisik untuk Review Post Produksi"

    wizard_id=fields.Many2one("ya.final.packing.review.wizard",required=True,ondelete="cascade")
    source_kind=fields.Selection([("KITCHEN","Hasil Dapur"),("PCK","Komponen PCK")],readonly=True)
    product_id=fields.Many2one("product.product",readonly=True)
    received=fields.Float(readonly=True)
    physical=fields.Float(readonly=True)
    reserved=fields.Float(readonly=True)
    free=fields.Float(readonly=True)
    upper_bound=fields.Float(readonly=True)
