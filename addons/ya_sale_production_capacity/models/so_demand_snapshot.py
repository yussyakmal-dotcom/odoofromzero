"""Immutable confirmation-time commercial demand for YA SO, clone only."""
import hashlib
import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .pp1_native_sources import DB

_TOKEN = object()

def digest(facts):
    return hashlib.sha256(json.dumps(facts,sort_keys=True,separators=(",",":"),
        allow_nan=False).encode()).hexdigest()

class SaleOrderDemandSnapshot(models.Model):
    _inherit = "sale.order"

    ya_confirmed_demand_snapshot = fields.Json(readonly=True,copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any("ya_confirmed_demand_snapshot" in v for v in vals_list):
            raise UserError(_("YA confirmed demand snapshot cannot be supplied on create."))
        return super().create(vals_list)

    def write(self, vals):
        if "ya_confirmed_demand_snapshot" in vals:
            self.ensure_one()
            if (self.env.cr.dbname!=DB or self.env.context.get("_ya_so_demand_token") is not _TOKEN
                    or self.state not in ("draft","sent") or not self.ya_is_capacity_so
                    or self.ya_confirmed_demand_snapshot):
                raise UserError(_("YA confirmed demand snapshot is immutable."))
        return super().write(vals)

    def _ya_freeze_confirmed_demand(self, booking, ledger):
        self.ensure_one()
        if (self.env.cr.dbname!=DB or not self.ya_is_capacity_so
                or self.state not in ("draft","sent")
                or not self.env.user.has_group("sales_team.group_sale_salesman")
                or self.ya_confirmed_demand_snapshot):
            raise UserError(_("Invalid YA demand snapshot transaction."))
        expected=sorted((r["planning_line_id"],r["product_id"],r["qty_required"])
                        for r in booking["reservation_rows"])
        actual=sorted((r.planning_line_id.id,r.product_id.id,r.qty_required) for r in ledger)
        if not ledger or set(ledger.mapped("order_id").ids)!={self.id} or actual!=expected:
            raise UserError(_("YA demand snapshot ledger mismatch."))
        facts=dict(order_id=self.id,company_id=self.company_id.id,
                   delivery_date=str(self.ya_delivery_date),slot=self.ya_slot,
                   source_rows=booking["source_rows"],
                   ledger_rows=sorted([dict(ledger_id=r.id,planning_line_id=r.planning_line_id.id,
                       product_id=r.product_id.id,qty_required=r.qty_required) for r in ledger],
                       key=lambda r:r["ledger_id"]))
        self.with_context(_ya_so_demand_token=_TOKEN).write({
            "ya_confirmed_demand_snapshot":dict(version=1,facts=facts,digest=digest(facts),
                actor_id=self.env.uid,confirmed_at=fields.Datetime.to_string(fields.Datetime.now()))})

    def _ya_verified_confirmed_demand(self, current_rows=None):
        self.ensure_one()
        snapshot=self.ya_confirmed_demand_snapshot
        if not snapshot or snapshot.get("version")!=1:
            raise UserError(_("Missing YA confirmation-time demand snapshot."))
        facts=snapshot["facts"]
        if (digest(facts)!=snapshot["digest"] or self.state not in ("sale","done")
                or facts["order_id"]!=self.id or facts["company_id"]!=self.company_id.id
                or facts["delivery_date"]!=str(self.ya_delivery_date) or facts["slot"]!=self.ya_slot):
            raise UserError(_("YA confirmed demand snapshot integrity failure."))
        ledger=self.env["ya.sale.capacity.reservation"].sudo().search([("order_id","=",self.id)])
        actual=sorted([dict(ledger_id=r.id,planning_line_id=r.planning_line_id.id,
                      product_id=r.product_id.id,qty_required=r.qty_required) for r in ledger],
                      key=lambda r:r["ledger_id"])
        if actual!=facts["ledger_rows"]:
            raise UserError(_("YA confirmed demand snapshot ledger changed."))
        if current_rows is not None and sorted(current_rows,key=lambda r:r["line_id"])!=facts["source_rows"]:
            raise UserError(_("YA confirmed recipient demand or Paket BoM changed; reconcile."))
        return facts

    def _ya_confirm_with_protected_capacity(self, delivery_date, slot):
        # A failed confirm must not leave the snapshot or ledger behind even
        # if a caller catches the exception inside an outer transaction.
        with self.env.cr.savepoint():
            result=super()._ya_confirm_with_protected_capacity(delivery_date,slot)
            self._ya_verified_confirmed_demand()
            return result
