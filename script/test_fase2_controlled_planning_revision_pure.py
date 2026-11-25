from pathlib import Path
import runpy

rules = runpy.run_path(str(Path(__file__).resolve().parents[1] /
    "addons/ya_sale_production_capacity/models/planning_revision_rules.py"))
validate = rules["validate_revision"]

def check(new, *, ro=0, so=0, locked=False, delete=False, referenced=False, allowed=True):
    try:
        validate(400, new, 200, ro=ro, so=so, locked=locked,
                 delete=delete, referenced=referenced)
    except ValueError:
        assert not allowed
    else:
        assert allowed

check(200)
check(600)
check(200, ro=500)
check(600, ro=500)
check(600, so=20)
check(200, so=20, allowed=False)
check(450, allowed=False)
check(600, locked=True, allowed=False)
check(400, delete=True)
check(400, delete=True, ro=1, allowed=False)
check(400, delete=True, so=1, allowed=False)
check(400, delete=True, referenced=True, allowed=False)
check(0, ro=1, allowed=False)
check(0)
check(-200, allowed=False)
check(600, so=800, allowed=False)
print("FASE2_CONTROLLED_PLANNING_REVISION_PURE_PASS (16 cases)")
