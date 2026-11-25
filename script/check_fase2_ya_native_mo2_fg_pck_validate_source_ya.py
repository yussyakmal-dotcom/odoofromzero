"""Source-only preflight for native FG GRG->PCK validation rollback QA.

No Odoo imports, database access, addon installation or stock mutation.
Runs before the first clone-only native stock posting experiment.
"""
import ast
from pathlib import Path

path = Path("script/test_fase2_ya_native_mo2_fg_pck_validate_rollback.py")
source = path.read_text(encoding="utf-8")
ast.parse(source, filename=str(path))
for token in (
    'CLONE = "erp-yussyakmal-mrp-test-RO_SO"',
    'Version.installed_version == "19.0.1.1.3"',
    'PREFIXTURE_SQL_COMMITTED_BASELINE_PASS',
    'SET TRANSACTION READ ONLY',
    'SYNTHETIC_CDC_RESERVED_AFTER_PREPARATION',
    'MO2_CDC_NATIVE_DONE_STOCK_DELTAS_PASS',
    'NATIVE_MO2_CONSUMPTION_MATCHES_BOM_PASS',
    '_set_qty_producing()',
    'button_mark_done()',
    'NATIVE_MO2_DONE_STOCK_DELTAS_PASS',
    '_ya_create_mo2_fg_transfer()',
    'MO2_FG_NATIVE_DRAFT_CREATION_PASS',
    'fg_actor = fg.with_user(stock_actor)',
    'fg_actor.action_confirm()',
    'fg_actor.action_assign()',
    'MO2_FG_NATIVE_PCK_STOCK_DELTAS_PASS',
    'MO2_FG_PCK_NEW_FREE_STOCK_ONLY_PASS',
    'NATIVE_FG_MODIFIED_HISTORIC_PCK_RESERVED',
    'MO2_FG_NATIVE_VALIDATED_DOUBLE_CLICK_NO_DUPLICATE_PASS',
    'MO2_FG_PCK_NATIVE_ONE_STEP_VALIDATION_PASS',
    'FASE1_HISTORIC_FG_PICKING_STATE_CHANGED',
    'env.cr.rollback()',
    'ROLLBACK_VERIFIER: INDEPENDENT_SQL_READ_ONLY_CURSOR',
    'NATIVE_STOCK_ROLLBACK_VERIFIED',
    'INDEPENDENT_SQL_SYNTHETIC_OBJECTS_ABSENT_PASS',
    'FASE2_YA_NATIVE_MO2_DONE_FG_PCK_VALIDATE_ROLLBACK_PASS',
    'NO_TEST_OBJECTS_COMMITTED',
):
    assert token in source, "SOURCE_REQUIREMENT_MISSING: %s" % token

assert source.count("button_validate()") == 2, (
    "EXPECTED_CDC_AND_FG_NATIVE_VALIDATE_ONLY"
)
assert source.count("button_mark_done()") == 1, (
    "EXPECTED_ONE_NATIVE_MO2_PRODUCTION_DONE"
)
assert 'env.cr.commit()' not in source, "COMMIT_FORBIDDEN_IN_ROLLBACK_QA"
assert not any(token in source for token in (
    'skip_consumption=True', '"state": "done"', "'state': 'done'",
    'Quant.create(', 'qmodel.create(', 'Quant.write(', 'qmodel.write(',
    'env.invalidate_all()', '.sudo().button_validate()',
)), "UNSAFE_SOURCE_SCOPE"
print("FASE2_YA_NATIVE_MO2_FG_PCK_SOURCE_PREFLIGHT_PASS")
print("SCOPE: CLONE_ONLY_NATIVE_CDC_AND_FG_VALIDATION_ONE_ROLLBACK_TRANSACTION")
print("LEGACY_MO1_FG_AND_STORE_DO_UNTOUCHED_IN_SOURCE")
print("NO_ADDON_INSTALL_OR_STOCK_MUTATION")
