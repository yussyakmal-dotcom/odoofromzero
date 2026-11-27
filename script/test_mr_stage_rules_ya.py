"""Pure source test: no database, no Odoo import."""
import importlib.util
from pathlib import Path
p=Path("addons/ya_sale_production_capacity/models/mr_stage_rules.py")
spec=importlib.util.spec_from_file_location("mr_stage_rules",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.DEFAULT_MODE=={"mr1":"full","mr2":"shortage"}
def check(expected,*args):
    actual=m.stage_quantity(*args)["transfer"]
    assert abs(actual-expected)<1e-9,(expected,actual,args)
check(500,"full",500,3400,500,500,0,0,0)
check(0,"shortage",500,3400,500,500,0,0,0)
check(0,"shortage",250,670,250,250,0,0,0)
check(1000,"shortage",1000,0,0,0,0,0,0)
check(10,"shortage",30,100,80,0,80,80,0)
check(0,"shortage",30,30,0,0,80,0,80)
check(20,"shortage",20,0,0,0,80,0,80)
check(0,"shortage",20,0,0,0,80,0,100)
check(20,"shortage",30,100,90,0,70,70,0)
check(10,"shortage",10,0,0,0,100,0,0)
try:
    m.stage_quantity("shortage",20,100,10,20,0,0,0)
except ValueError:
    pass
else:
    raise AssertionError("Unreconciled reservations accepted")
print("MR_STAGE_RULES_PURE_TEST_PASS")
