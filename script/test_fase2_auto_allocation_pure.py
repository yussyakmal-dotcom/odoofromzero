"""Source-only regression for restored Fase1 prorata and Fase2 priorities."""
from copy import deepcopy
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
root=Path(__file__).resolve().parents[1]/"addons"
def load(name,path):
    spec=spec_from_file_location(name,root/path)
    mod=module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
rules=load("proposal_rules","ya_sale_production_capacity/models/final_packing_proposal_rules.py")
base=load("allocation_rules","ya_store_ro/models/allocation_rules.py")
def line(kind,i,store,pid,qty,components=None):
    return dict(kind=kind,source_id=i,line_id=i,recipient_id=store,product_id=pid,qty=qty,
        components=components or [dict(product_id=pid,source_kind="KITCHEN",qty=qty)])
def fixture(rows,cap,pck=None):
    return dict(supply=dict(batch_id=60,delivery_date="2026-12-01",slot="S1",
        rows=[dict(product_id=p,slot_supply_upper_bound=q) for p,q in cap.items()]),
        recipient_rows=rows,pck_component_rows=pck or [],so_paket_confirmation_provenance_missing=[])
def auto(d):
    return rules.auto_allocate(d,base.allocate_capacity_prorata,base.allocate_surplus_prorata)
def reject(fn,message):
    try:
        fn()
    except rules.ProposalError as exc:
        assert message in str(exc),str(exc)
    else:
        raise AssertionError("Expected rejection: "+message)
d=fixture([line("RO",1,11,3,2),line("RO",2,11,1,40),line("RO",3,12,3,1),
    line("RO",4,12,2,2),line("RO",5,12,1,50),line("SO",6,20,1,245),
    line("SO",7,20,2,4),line("SO",8,20,3,2)],{1:250,2:15,3:40})
p=auto(d)
assert [r["qty_allocated"] for r in p["rows"]]==[25,2,13,11,3,245,4,2]
v=rules.validate_proposal(d,p)
assert sum(r["qty_shortage"] for r in v["rows"])==85
assert sum(r["qty_surplus"] for r in v["rows"])==44
assert all(float(r["unallocated_upper_bound"])==0 for r in v["component_balances"])
assert auto(d)==p
edited=deepcopy(p)
edited["rows"][0]["qty_allocated"]=24
edited["rows"][2]["qty_allocated"]=14
rules.validate_proposal(d,edited)
edited["rows"][2]["qty_allocated"]=15
reject(lambda:rules.validate_proposal(d,edited),"Insufficient full component stock")
edited=deepcopy(p)
edited["rows"][5]["qty_allocated"]=244
reject(lambda:rules.validate_proposal(d,edited),"Confirmed SO")
old=deepcopy(p)
old.pop("policy")
reject(lambda:rules.validate_proposal(d,old),"Allocation exceeds original demand")
print("DEC01_PRORATA_EDIT_AND_LEGACY_POLICY_PASS")
pkg=[dict(product_id=1,source_kind="KITCHEN",qty_per_package=2,qty=8)]
d=fixture([line("SO",1,20,1,3),line("RO_PAKET",2,11,10,4,pkg),
    line("RO",3,12,1,2)],{1:14})
p=auto(d)
assert [r["qty_allocated"] for r in p["rows"]]==[3,4,3]
bad=deepcopy(p);bad["rows"][1]["qty_allocated"]=5
reject(lambda:rules.validate_proposal(d,bad),"Allocation exceeds original demand")
bad=deepcopy(p);bad["rows"][1]["qty_allocated"]=3;bad["rows"][2]["qty_allocated"]=5
reject(lambda:rules.validate_proposal(d,bad),"Ordinary RO displaces")
d["supply"]["rows"][0]["slot_supply_upper_bound"]=2
reject(lambda:auto(d),"Insufficient full component stock")
d=fixture([line("SO",1,20,1,2)],{1:10})
assert float(rules.validate_proposal(d,auto(d))["component_balances"][0]["unallocated_upper_bound"])==8
d=fixture([line("RO_PAKET",1,11,10,4,pkg),line("RO_PAKET",2,12,11,4,pkg)],{1:10})
reject(lambda:auto(d),"RO Paket berbeda")
print("PACKAGE_PRIORITY_SO_SHORTAGE_NO_RO_AND_AMBIGUOUS_PACKAGE_PASS")
print("FASE2_AUTO_ALLOCATION_PURE_PASS")
