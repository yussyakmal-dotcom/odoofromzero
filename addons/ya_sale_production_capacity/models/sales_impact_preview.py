"""Read-only Sales impact, using the same math and sources as Design B.
No customer details from other orders exposed to the wizard.
"""
from odoo import fields, models, _
from odoo.exceptions import UserError
from .pp1_native_sources import DB, require
from .pp1_review_contract import read_locked_review
from .pp1_design_b_rules import preview_before_pp1_release
from .pp2_native_sources import read_pp2_forecast
from .mo2_owner_so_first_rules import plan_so_first_only
from .consolidation_cutoff_gate import current_clock
from .so_demand_snapshot import digest


class SaleOrderImpact(models.Model):
    _inherit="sale.order"

    def _ya_read_sales_impact(self, day, slot):
        self.ensure_one()
        if self.env.cr.dbname!=DB or not self.env.user.has_group("sales_team.group_sale_salesman"):
            raise UserError(_("Sales permission required in RO_SO."))
        self.check_access("write")
        if self.company_id!=self.env.company:
            raise UserError(_("Sales company mismatch."))
        day=fields.Date.to_date(day)
        # Same native booking preflight and slot/order locks, but NO writes.
        booking=self._ya_prepare_locked_booking(day,slot)
        self.env.invalidate_all()
        clock=current_clock(self.env,day,slot)
        domain=[("delivery_date","=",day),("slot","=",slot)]
        batch=self.env["ya.packing.batch"].sudo().search(domain)
        try:
            require(len(batch)<=1,"Duplicate Packing batch")
            if batch:
                require(batch.ya_pp1_design_b_snapshot and batch.state=="production_ok",
                        "Legacy/staged batch requires reconciliation")
                facts=read_pp2_forecast(batch,sales_preview=True)
                baseline_digest=digest(facts)
                stage="pp2"
            else:
                review=read_locked_review(self.env,day,slot,self.company_id)
                facts=review["facts"]
                baseline_digest=review["digest"]
                stage="pp1"
            forecasts={r["product_id"]:r for r in facts["sku_forecasts"]}
            checks={r["planning_line_id"]:r["calculation"] for r in booking["capacity_checks"]}
            lines=[]
            for r in booking["reservation_rows"]:
                pid=r["product_id"]
                c=checks[r["planning_line_id"]]
                base=forecasts.get(pid,{})
                prior=c["existing_confirmed_so_qty"]
                require(base.get("confirmed_so_qty",0)==prior,"Forecast/ledger Qty mismatch")
                common=dict(original_ro_package_qty=base.get("original_ro_package_qty",0),
                            original_ro_store_qty=base.get("original_ro_store_qty",0),
                            published_max=c["published_max"])
                if stage=="pp1":
                    impact=preview_before_pp1_release(draft_so_qty=r["qty_required"],
                        confirmed_so_qty=prior,bom_output=c["bom_output"],
                        ro_closed=clock["ro_closed"],**common)
                    before,after=impact["before"],impact["after"]
                    out0,out1=before["forecast_mo1_qty"],after["forecast_mo1_qty"]
                    extra0,extra1=before["forecast_unallocated_surplus"],after["forecast_unallocated_surplus"]
                    mo2_before=mo2_after=0
                else:
                    require(base.get("preexisting_mo1_qty",0)==c["mo1_output"],"MO1 quantity mismatch")
                    args=dict(existing_mo1_output=c["mo1_output"],existing_mo2_output=0,
                              kitchen_bom_output=c["bom_output"],**common)
                    before=plan_so_first_only(confirmed_so_qty=prior,**args)
                    after=plan_so_first_only(confirmed_so_qty=prior+r["qty_required"],**args)
                    out0,out1=before["forecast_total_output"],after["forecast_total_output"]
                    extra0,extra1=before["theoretical_extra_not_automatically_allocated"],after["theoretical_extra_not_automatically_allocated"]
                    mo2_before,mo2_after=before["mo2_increment_due_to_so_only"],after["mo2_increment_due_to_so_only"]
                lines.append(dict(product_id=pid,new_qty=r["qty_required"],so_before=prior,
                    so_after=prior+r["qty_required"],bom_output=c["bom_output"],
                    published_max=c["published_max"],remaining_capacity=c["remaining_so_qty_capacity"],
                    ro_package=common["original_ro_package_qty"],ro_store=common["original_ro_store_qty"],
                    mo1=c["mo1_output"],mo2_before=mo2_before,mo2_after=mo2_after,
                    output_before=out0,output_after=out1,additional_output=out1-out0,
                    surplus_before=extra0,surplus_after=extra1,
                    new_surplus=max(0,extra1-extra0),absorbed_surplus=max(0,extra0-extra1),
                    ro_package_short_before=before["forecast_ro_package_shortage"],
                    ro_package_short_after=after["forecast_ro_package_shortage"],
                    ro_store_short_before=before["forecast_ro_store_shortage"],
                    ro_store_short_after=after["forecast_ro_store_shortage"]))
        except ValueError as exc:
            raise UserError(str(exc)) from exc
        payload=dict(order_id=self.id,company_id=self.company_id.id,day=str(day),slot=slot,
            stage=stage,ro_closed=clock["ro_closed"],policy_version=clock["cutoff_settings_version_id"],
            special_cutoff_id=clock["special_cutoff_id"],
            source_digest=baseline_digest,source_rows=booking["source_rows"],lines=lines,
            pck_requirements=sorted(booking["pck_stock_requirements"].items()))
        return dict(payload=payload,digest=digest(payload))
