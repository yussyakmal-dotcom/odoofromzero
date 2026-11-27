"""Clone-only MR stage review and immutable issuance decision.

Native stock picking/move remains the operational document. Preview is
read-only apart from the transient review; no physical movement or MO edit.
"""
from collections import defaultdict
import hashlib
import json

from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_round
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from .pp1_native_sources import DB
from .consolidation_cutoff_gate import current_clock
from .mr_stage_rules import DEFAULT_MODE, ISSUE_TOKEN, stage_quantity

MODES = [("full","Full Requirement"),("shortage","Shortage Requirement")]
STAGES = [("mr1","Material Requirement 1"),("mr2","Material Requirement 2")]
OPEN = ("waiting","confirmed","partially_available","assigned")


def _digest(facts):
    return hashlib.sha256(json.dumps(facts,sort_keys=True,separators=(",",":"),
                                    allow_nan=False).encode()).hexdigest()


def _number(q):
    return ("%.8f"%q).rstrip("0").rstrip(".")


def decision_table(facts,env):
    headers=("Dapur","SKU / Bahan","Satuan","Kebutuhan MO","Stok Fisik","Reservasi Total",
             "Kewajiban Lain","Incoming Terbit","Tersedia Proyeksi","Qty Transfer")
    head=Markup("").join(Markup("<th>{}</th>").format(x) for x in headers)
    cells=[]
    for r in facts["rows"]:
        wh=env["stock.warehouse"].sudo().browse(r["warehouse_id"])
        p=env["product.product"].sudo().browse(r["product_id"])
        vals=(wh.display_name,p.display_name,p.uom_id.name,r["gross"],r["physical"],
              r["reserved"],r["other_need"],r["incoming"],
              r["projected_available"],r["transfer"])
        cells.append(Markup("<tr>{}</tr>").format(Markup("").join(
            Markup('<td class="{}">{}</td>').format("text-end" if i>=3 else "",
                _number(v) if i>=3 else v) for i,v in enumerate(vals))))
    info=Markup('<p><strong>{} — {}</strong></p>').format(facts["stage"].upper(),dict(MODES)[facts["mode"]])
    if facts["mode"]=="full":
        info+=Markup("<p>Qty Transfer = kebutuhan penuh MO; angka stok hanya informasi.</p>")
    else:
        info+=Markup("<p>Qty Transfer = kekurangan tahap ini setelah stok dan komitmen lain. Incoming belum menjadi stok fisik; transfer yang sudah terbit tetap wajib dipenuhi.</p>")
    if not any(r["transfer"]>0 for r in facts["rows"]):
        info+=Markup('<p class="text-success"><strong>Tidak perlu Internal Transfer.</strong></p>')
    return info+Markup('<div class="table-responsive"><table class="table table-sm table-bordered"><thead><tr>{}</tr></thead><tbody>{}</tbody></table></div>').format(head,Markup("").join(cells))


class MrStageDecision(models.Model):
    _name="ya.mr.stage.decision"
    _description="YA Keputusan Material Requirement per Tahap"
    _order="batch_id desc,stage"

    batch_id=fields.Many2one("ya.packing.batch",required=True,index=True,readonly=True,ondelete="restrict")
    stage=fields.Selection(STAGES,required=True,readonly=True)
    mode=fields.Selection(MODES,required=True,readonly=True)
    facts=fields.Json(required=True,readonly=True)
    issued_by=fields.Many2one("res.users",required=True,readonly=True)
    issued_at=fields.Datetime(required=True,readonly=True)
    _unique_stage=models.Constraint("UNIQUE(batch_id,stage)","Keputusan MR per tahap sudah terbit.")

    @api.model_create_multi
    def create(self,vals_list):
        if self.env.cr.dbname!=DB or self.env.context.get("_ya_mr_issue_token") is not ISSUE_TOKEN:
            raise UserError(_("Gunakan Siapkan MR1 / MR2."))
        return super().create(vals_list)

    def write(self,vals):
        raise UserError(_("Keputusan Material Requirement yang sudah terbit tidak boleh diubah."))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_issued(self):
        raise UserError(_("Riwayat Material Requirement tidak boleh dihapus."))


class PackingBatchMRPolicy(models.Model):
    _inherit="ya.packing.batch"

    def _ya_mr_stage_decision(self,stage):
        self.ensure_one()
        return self.env["ya.mr.stage.decision"].sudo().search([
            ("batch_id","=",self.id),("stage","=",stage)])

    def _ya_mr_decision_for_issue(self,stage):
        self.ensure_one()
        if self.env.context.get("_ya_mr_issue_token") is not ISSUE_TOKEN:
            raise UserError(_("Gunakan Siapkan MR1 / MR2 dan Terbitkan."))
        decision=self._ya_mr_stage_decision(stage)
        if len(decision)!=1 or decision.id!=self.env.context.get("_ya_mr_decision_id"):
            raise UserError(_("Keputusan MR tidak sesuai tahap/batch."))
        return decision

    def _ya_mr_stage_existing(self,stage):
        self.ensure_one()
        if stage=="mr1":
            return self._mr_related_native_pickings()
        finals=self.env["ya.sale.mo2.finalization"].sudo().search([("batch_id","=",self.id)])
        return self.env["stock.picking"].search([
            "|",("ya_mr2_finalization_id","in",finals.ids),
            ("ya_mo2_material_release_line_id","in",finals.line_ids.ids)])

    def _ya_mr_stage_action(self,stage,pickings):
        self.ensure_one()
        if not pickings:
            return self._mr_reopen()
        return dict(type="ir.actions.act_window",name=_("Internal Transfer %s")%stage.upper(),
                    res_model="stock.picking",view_mode="list,form",
                    domain=[("id","in",pickings.ids)],context={"create":False},target="current")

    def _ya_mr_stage_guard(self,stage):
        self.ensure_one()
        self.check_access("read")
        if self.env.cr.dbname!=DB or stage not in DEFAULT_MODE:
            raise UserError(_("Material Requirement Fase 2 hanya di clone RO_SO."))
        self._mr_guard()
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise UserError(_("Inventory Administrator diperlukan untuk menerbitkan MR."))
        if stage=="mr2" and not self.env.user.has_group("ya_store_ro.group_ya_packing_admin"):
            raise UserError(_("Packing Admin diperlukan untuk MR2."))
        if current_clock(self.env,self.delivery_date,self.slot)["expired"]:
            raise UserError(_("Tanggal kirim terlewati. Jangan buat permintaan bahan baru."))

    def _ya_mr_open_stage(self,stage):
        self.ensure_one()
        self._mr_guard()
        existing=self._ya_mr_stage_existing(stage)
        decision=self._ya_mr_stage_decision(stage)
        if existing or decision:
            return self._ya_mr_stage_action(stage,existing)
        self._ya_mr_stage_guard(stage)
        wiz=self.env["ya.mr.stage.wizard"].create({
            "batch_id":self.id,"stage":stage,"mode":DEFAULT_MODE[stage]})
        return wiz.action_preview()

    def _ya_mr_stage_facts(self,stage,mode):
        self.ensure_one()
        self._ya_mr_stage_guard(stage)
        if mode not in dict(MODES):
            raise UserError(_("Pilih metode Material Requirement."))
        if self._ya_mr_stage_decision(stage) or self._ya_mr_stage_existing(stage):
            raise UserError(_("MR tahap ini sudah terbit. Buka dokumen existing."))
        # Serialize MR decisions across slots, not native inventory actions.
        self.env.cr.execute("SELECT pg_advisory_xact_lock(%s,%s)",[196027,self.env.company.id])
        self.env.invalidate_all()
        pp1=self._ya_pp1_frozen_facts()
        final=self.env["ya.sale.mo2.finalization"]
        if stage=="mr1":
            facts=pp1
            mos=self.line_ids.mapped("mo_id")
            qkey="forecast_mo1_qty"
        else:
            final=final.sudo().search([("batch_id","=",self.id)])
            if len(final)!=1 or not final.ya_pp2_design_b_snapshot:
                raise UserError(_("Selesaikan Produksi OK 2 dahulu."))
            facts=final._ya_pp2_frozen_facts()
            mos=final.line_ids.mapped("mo_id").with_env(self.env)
            qkey="mo2_increment_due_to_so_only"
        expected={r["product_id"]:r for r in facts["sku_forecasts"] if r[qkey]>0}
        if not mos:
            raise UserError(_("Tidak ada MO tambahan untuk tahap ini."))
        if len(mos)!=len(expected) or set(mos.mapped("product_id").ids)!=set(expected):
            raise UserError(_("Daftar MO tidak sesuai hasil Produksi OK."))
        groups=defaultdict(lambda:{"gross":defaultdict(float),"moves":defaultdict(set)})
        for mo in mos:
            p=mo.product_id
            row=expected[p.id]
            route=row["kitchen_route"]
            wh=mo.picking_type_id.warehouse_id
            if (mo.state!="confirmed" or mo.company_id!=self.env.company
                    or mo.bom_id.id!=row["bom_id"] or wh.id!=route["warehouse_id"]
                    or mo.picking_type_id.id!=route["picking_type_id"]
                    or mo.location_src_id.id!=route["source_id"]
                    or mo.location_dest_id.id!=route["destination_id"]
                    or abs(mo.product_uom_id._compute_quantity(mo.product_qty,p.uom_id,round=False)-row[qkey])>1e-7):
                raise UserError(_("MO %s berubah atau bukan Confirmed; periksa MO sebelum menyiapkan bahan.")%mo.name)
            if not mo.move_raw_ids:
                raise UserError(_("MO %s tidak memiliki bahan baku.")%mo.name)
            for m in mo.move_raw_ids:
                mat=m.product_id
                if m.state in ("done","cancel","draft") or not mat.is_storable:
                    raise UserError(_("Periksa bahan dan status MO %s.")%mo.name)
                qty=m.product_uom._compute_quantity(m.product_uom_qty,mat.uom_id,round=False)
                if qty<0 or (mat.company_id and mat.company_id!=mo.company_id):
                    raise UserError(_("Qty/perusahaan bahan tidak valid: %s.")%mat.display_name)
                if qty:
                    groups[wh.id]["gross"][mat.id]+=qty
                    groups[wh.id]["moves"][mat.id].add(m.id)
        rows=[]
        Move=self.env["stock.move"].sudo()
        Quant=self.env["stock.quant"].sudo()
        Location=self.env["stock.location"].sudo()
        company=self.env.company
        for wh_id,g in sorted(groups.items()):
            wh=self.env["stock.warehouse"].sudo().browse(wh_id)
            if wh.company_id!=company or wh.lot_stock_id.usage!="internal" or wh.code=="CDC":
                raise UserError(_("Rute gudang dapur tidak valid."))
            locs=Location.search([("id","child_of",wh.lot_stock_id.id),("usage","=","internal")]).ids
            pids=sorted(g["gross"])
            own_ids=sorted(set().union(*g["moves"].values()))
            own=Move.browse(own_ids)
            if any(m.location_id.id not in locs for m in own):
                raise UserError(_("Lokasi bahan MO berada di luar gudang dapur %s.")%wh.display_name)
            qmap=defaultdict(lambda:[0.,0.])
            for q in Quant.search([("company_id","=",company.id),("location_id","in",locs),
                                  ("product_id","in",pids),("owner_id","=",False)]):
                qmap[q.product_id.id][0]+=q.quantity
                qmap[q.product_id.id][1]+=q.reserved_quantity
            common=[("company_id","=",company.id),("product_id","in",pids),
                    ("location_id","in",locs),("state","in",OPEN),("id","not in",own_ids)]
            other=Move.search(common+[("raw_material_production_id","!=",False)])
            other|=Move.search(common+[("raw_material_production_id","=",False),
                                        ("location_dest_id","not in",locs)])
            # Final leg into kitchen. Linked issued YA MR documents remain
            # commitments even if native picking has not yet been assigned.
            incoming=Move.search([
                ("company_id","=",company.id),("product_id","in",pids),
                ("location_dest_id","in",locs),("location_id","not in",locs),
                ("location_id.usage","=","internal"),
                ("picking_id","!=",False),("picking_id.picking_type_id.code","=","internal"),
                ("picking_id.state","not in",["done","cancel"]),
                ("state","not in",["done","cancel"]),
                "|",("state","in",OPEN),
                "|",("picking_id.ya_mr_batch_id","!=",False),
                    ("picking_id.ya_mr2_finalization_id","!=",False)])
            def demands(moves):
                out=defaultdict(float)
                for m in moves:
                    p=m.product_id
                    out[p.id]+=m.product_uom._compute_quantity(m.product_uom_qty,p.uom_id,round=False)
                return out
            def reservations(moves):
                out=defaultdict(float)
                for ml in moves.move_line_ids:
                    if ml.state not in ("done","cancel") and ml.location_id.id in locs and not ml.owner_id:
                        out[ml.product_id.id]+=ml.quantity_product_uom
                return out
            other_need=demands(other)
            incoming_need=demands(incoming)
            own_res=reservations(own)
            other_res=reservations(other)
            products=self.env["product.product"].sudo().browse(pids)
            for p in products:
                pid=p.id
                gross=g["gross"][pid]
                physical,reserved=qmap[pid]
                try:
                    result=stage_quantity(mode,gross,physical,reserved,own_res[pid],
                                          other_need[pid],other_res[pid],incoming_need[pid])
                except ValueError as exc:
                    raise UserError(_("%s / %s: %s")%(wh.display_name,p.display_name,str(exc))) from exc
                if mode=="shortage" and result["transfer"]>0:
                    result["transfer"]=min(gross,float_round(result["transfer"],
                        precision_rounding=p.uom_id.rounding,rounding_method="UP"))
                rows.append(dict(warehouse_id=wh_id,product_id=pid,gross=gross,
                                 physical=physical,reserved=reserved,own_reserved=own_res[pid],
                                 other_need=other_need[pid],other_reserved=other_res[pid],
                                 incoming=incoming_need[pid],
                                 incoming_move_ids=sorted(incoming.filtered(lambda m:m.product_id==p).ids),
                                 own_move_ids=sorted(g["moves"][pid]),**result))
        if not rows:
            raise UserError(_("Tidak ada kebutuhan bahan pada MO tahap ini."))
        return dict(batch_id=self.id,stage=stage,mode=mode,final_id=final.id or False,
                    delivery_date=str(self.delivery_date),slot=self.slot,
                    company_id=company.id,mo_ids=sorted(mos.ids),rows=rows)


class MrStageWizard(models.TransientModel):
    _name="ya.mr.stage.wizard"
    _description="YA Review dan Terbitkan Material Requirement"

    batch_id=fields.Many2one("ya.packing.batch",required=True,readonly=True)
    stage=fields.Selection(STAGES,required=True,readonly=True)
    mode=fields.Selection(MODES,required=True)
    delivery_date=fields.Date(related="batch_id.delivery_date",readonly=True)
    slot=fields.Selection(related="batch_id.slot",readonly=True)
    digest=fields.Char(readonly=True)
    preview_html=fields.Html(readonly=True)

    @api.onchange("mode")
    def _onchange_mode(self):
        self.digest=False
        self.preview_html=False

    def _reopen(self):
        self.ensure_one()
        return dict(type="ir.actions.act_window",name=_("Siapkan %s")%self.stage.upper(),
                    res_model=self._name,res_id=self.id,view_mode="form",
                    views=[(self.env.ref("ya_sale_production_capacity.view_ya_mr_stage_wizard").id,"form")],
                    target="current")

    def action_preview(self):
        self.ensure_one()
        facts=self.batch_id._ya_mr_stage_facts(self.stage,self.mode)
        self.write({"digest":_digest(facts),"preview_html":decision_table(facts,self.env)})
        return self._reopen()

    def action_issue(self):
        self.ensure_one()
        self.check_access("write")
        batch=self.batch_id
        batch._mr_guard()
        if batch._ya_mr_stage_decision(self.stage) or batch._ya_mr_stage_existing(self.stage):
            return batch._ya_mr_stage_action(self.stage,batch._ya_mr_stage_existing(self.stage))
        with self.env.cr.savepoint():
            facts=batch._ya_mr_stage_facts(self.stage,self.mode)
            if not self.digest or self.digest!=_digest(facts):
                raise UserError(_("Data bahan/stok berubah. Klik Hitung / Refresh sebelum Terbitkan."))
            decision=self.env["ya.mr.stage.decision"].sudo().with_context(
                _ya_mr_issue_token=ISSUE_TOKEN).create({
                    "batch_id":batch.id,"stage":self.stage,"mode":self.mode,
                    "facts":facts,"issued_by":self.env.uid,"issued_at":fields.Datetime.now()})
            guarded=batch.with_context(_ya_mr_issue_token=ISSUE_TOKEN,_ya_mr_decision_id=decision.id)
            positive=any(r["transfer"]>0 for r in facts["rows"])
            if self.stage=="mr1":
                if positive:
                    guarded.action_mr_generate_native_transfers()
                else:
                    guarded._mr_store_snapshot(guarded._mr_calculate_wizard())
            elif positive:
                guarded.action_mr2_generate_native_transfers()
            self.env.invalidate_all()
            pickings=batch._ya_mr_stage_existing(self.stage)
            expected={r["warehouse_id"] for r in facts["rows"] if r["transfer"]>0}
            actual={p.ya_mr_kitchen_id.id if self.stage=="mr1" else p.ya_mr2_kitchen_id.id
                    for p in pickings}
            if expected!=actual or len(pickings)!=len(expected):
                raise UserError(_("Dokumen transfer tidak sesuai keputusan MR; seluruh penerbitan dibatalkan."))
            for picking in pickings:
                wh=picking.ya_mr_kitchen_id if self.stage=="mr1" else picking.ya_mr2_kitchen_id
                wanted={r["product_id"]:r["transfer"] for r in facts["rows"]
                        if r["warehouse_id"]==wh.id and r["transfer"]>0}
                actual_qty={m.product_id.id:m.product_uom._compute_quantity(
                    m.product_uom_qty,m.product_id.uom_id,round=False) for m in picking.move_ids}
                if len(actual_qty)!=len(picking.move_ids) or set(wanted)!=set(actual_qty) or any(
                        abs(wanted[k]-actual_qty[k])>1e-7 for k in wanted):
                    raise UserError(_("Qty dokumen transfer tidak sesuai keputusan MR."))
            return batch._ya_mr_stage_action(self.stage,pickings)
