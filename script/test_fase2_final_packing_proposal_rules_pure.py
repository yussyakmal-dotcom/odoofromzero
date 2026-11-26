"""Pure test, reconstructed from the native PASS quantities (not live ORM)."""
from copy import deepcopy
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

path=Path(__file__).resolve().parents[1]/"addons/ya_sale_production_capacity/models/final_packing_proposal_rules.py"
spec=spec_from_file_location("proposal_rules",path)
rules=module_from_spec(spec)
spec.loader.exec_module(rules)

def line(kind,source,recipient,pid,qty,components=None):
    return dict(kind=kind,source_id=source,line_id=source,
        recipient_id=recipient,product_id=pid,qty=qty,bom_id=1405 if components else None,
        components=components or [dict(product_id=pid,source_kind="KITCHEN",qty=qty)])

demand=dict(supply=dict(batch_id=1,delivery_date="2026-12-15",slot="S1",
        rows=[dict(product_id=1015,slot_supply_upper_bound=14),
              dict(product_id=2123,slot_supply_upper_bound=500,pck_free=700)]),
    recipient_rows=[
        line("SO",1,11,1015,5),line("SO",2,12,2123,1),
        line("SO",3,13,2123,1),line("SO",4,14,2123,249),
        line("RO_PAKET",5,23,712,8,[
            dict(product_id=1015,source_kind="KITCHEN",qty_per_package=1.0,qty=8),
            dict(product_id=1029,source_kind="PCK",qty_per_package=1.0,qty=8.0),
            dict(product_id=1252,source_kind="PCK",qty_per_package=1.0,qty=8.0)]),
        line("RO",6,24,1015,4)],
    pck_component_rows=[dict(product_id=1029,free=0,tracking="none"),
                        dict(product_id=1252,free=0,tracking="none")],
    so_paket_confirmation_provenance_missing=[])

def proposed(d,qtys):
    p=rules.build_proposal_template(d)
    assert len(p["rows"])==len(qtys)
    for r,qty in zip(p["rows"],qtys):
        r["qty_allocated"]=qty
    return p

def rejected(d,p,expected):
    try:
        rules.validate_proposal(d,p)
    except rules.ProposalError as exc:
        assert expected in str(exc),(expected,str(exc))
    else:
        raise AssertionError("Accepted invalid proposal: "+expected)

def balance(result,pid):
    return next(r for r in result["component_balances"] if r["product_id"]==pid)

valid=proposed(demand,[5,1,1,249,0,4])
result=rules.validate_proposal(demand,valid)
assert not result["operational_allocation_allowed"]
assert balance(result,1015)["unallocated_upper_bound"]=="5.0" or balance(result,1015)["unallocated_upper_bound"]=="5"
assert balance(result,2123)["unallocated_upper_bound"]=="249"
assert result["rows"][4]["qty_shortage"]==8
assert not result["review_warnings"]
print("ZERO_PCK_COMPONENTS_NO_COMPLETE_PAKET_SO_AND_ORDINARY_RO_FEASIBLE_PASS")
rejected(demand,proposed(demand,[5,1,1,249,1,4]),"Insufficient full component stock")
rejected(demand,proposed(demand,[4,1,1,249,0,4]),"Confirmed SO cannot be partially allocated")
rejected(demand,proposed(demand,[5,1,1,249,0,5]),"Allocation exceeds original demand")
rejected(demand,proposed(demand,[5,1,1,249,0,-1]),"whole nonnegative")
rejected(demand,proposed(demand,[5,1,1,249,0,True]),"whole nonnegative")
rejected(demand,proposed(demand,[5,1,1,249,0,1.5]),"whole nonnegative")
print("COMPLETE_PAKET_SO_FULL_AND_ORIGINAL_RO_LIMIT_GATES_PASS")

full=deepcopy(demand)
for r in full["pck_component_rows"]:
    r["free"]=8
result=rules.validate_proposal(full,proposed(full,[5,1,1,249,8,1]))
assert result["rows"][4]["qty_shortage"]==0 and result["rows"][5]["qty_shortage"]==3
assert float(balance(result,1015)["unallocated_upper_bound"])==0
assert float(balance(result,1029)["used"])==8
rejected(full,proposed(full,[5,1,1,249,7,2]),"Ordinary RO displaces")
review=rules.validate_proposal(full,proposed(full,[5,1,1,249,7,0]))
assert review["review_warnings"]
print("RO_PAKET_PRIORITY_NO_AUTOMATIC_RECIPIENT_CHOICE_PASS")

for field,value in [("delivery_date","2026-12-16"),("slot","S2"),("batch_id",2)]:
    p=deepcopy(valid)
    p[field]=value
    rejected(demand,p,"Stale or changed fixed field")
rejected(full,valid,"Stale or changed fixed field: source_digest")
p=deepcopy(valid)
p["rows"][0]["recipient_id"]=99
rejected(demand,p,"Unknown or duplicate recipient row")
p=deepcopy(valid)
p["rows"].append(deepcopy(p["rows"][0]))
rejected(demand,p,"Unknown or duplicate recipient row")
p=deepcopy(valid)
p["rows"].pop()
rejected(demand,p,"Missing recipient row")
print("FIXED_DATE_SLOT_SOURCE_DIGEST_AND_RECIPIENT_IDENTITY_GATES_PASS")

short=deepcopy(demand)
short["supply"]["rows"][0]["slot_supply_upper_bound"]=4
rejected(short,proposed(short,[5,1,1,249,0,0]),"Insufficient full component stock")
unverified=deepcopy(demand)
unverified["so_paket_confirmation_provenance_missing"]=[10]
rejected(unverified,proposed(unverified,[5,1,1,249,0,4]),"SO Paket confirmation provenance missing")
print("SO_PHYSICAL_SHORTAGE_AND_UNVERIFIED_PAKET_BLOCKED_PASS")
print("FASE2_FINAL_PACKING_PROPOSAL_RULES_PURE_PASS")
print("PREVIEW_ONLY_NO_ORM_NO_ALLOCATION_NO_DO")
