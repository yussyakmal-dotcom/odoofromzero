"""Pure tests, not operational release or evidence of native quant ownership."""
from importlib.util import spec_from_file_location,module_from_spec
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"addons/ya_sale_production_capacity/models/pck_claim_protection_rules.py"
spec=spec_from_file_location("claims",p)
rules=module_from_spec(spec)
spec.loader.exec_module(rules)

def claim(batch,received,done_out,open_demand,reserved):
    return dict(batch_id=batch,received=received,done_out=done_out,
                open_demand=open_demand,reserved=reserved)

# Audit SKU10042: historical batch 1 receipt250, native open50, reserved50.
old=claim(1,250,0,50,50)
r=rules.review_claims(250,50,[old],2)
assert r["global_free"]==200 and r["other_protection"]==200
assert r["conservative_preview_cap"]==0
print("HISTORIC_BATCH_FREE_STOCK_NOT_AVAILABLE_TO_NEW_BATCH_PASS")
# Reconstructed integrated fixture, receipt500 from a new batch.
new=claim(2,500,0,0,0)
r=rules.review_claims(750,50,[old,new],2)
assert r["global_free"]==700 and r["other_protection"]==200
assert r["conservative_preview_cap"]==500
print("CROSS_SLOT_RECEIPTS_RESERVED_ONCE_PASS")
# If an external outbound consumes 100 of the previously shared physical,
# protect old outstanding 200; cannot still promise all 500 to current.
r=rules.review_claims(650,50,[old,new],2)
assert r["conservative_preview_cap"]==400
print("SHARED_PHYSICAL_SHORTAGE_REDUCES_PREVIEW_CAP_PASS")
# Audit SKU12379 received40 and delivered10. Preserve remaining30.
r=rules.review_claims(30,0,[claim(3,40,10,0,0)],2)
assert r["other_protection"]==30 and r["conservative_preview_cap"]==0
# Unreserved open native demand (e.g. old stockout) still needs review.
r=rules.review_claims(100,0,[claim(1,0,0,100,0),claim(2,100,0,0,0)],2)
assert r["other_protection"]==100 and r["conservative_preview_cap"]==0
print("DONE_OUT_AND_UNRESERVED_NATIVE_CLAIMS_PASS")
# Remaining receipt40 vs outstanding native demand60, reservation20:
# max(40-20,60-20)=40, not their sum60.
r=rules.review_claims(120,20,[claim(1,40,0,60,20),claim(2,80,0,0,0)],2)
assert r["other_protection"]==40 and r["conservative_preview_cap"]==60
for phys,res,rows in [(100,50,[claim(1,100,0,50,40)]),
                      (100,50,[claim(1,100,0,40,50)]),
                      (10,20,[])]:
    try:
        rules.review_claims(phys,res,rows,2)
    except ValueError:
        pass
    else:
        raise AssertionError("Unreconciled or invalid reservations accepted")
print("RECONCILIATION_FAIL_CLOSED_PASS")
assert not r["operational_allocation_allowed"]
print("FASE2_PCK_CLAIM_PROTECTION_RULES_PURE_PASS")
print("PREVIEW_ONLY_NO_ORM_NO_RESERVATION_NO_DO")
