"""Prepare staged Odoo 19 COA import files from validated YA master + audits.

This script operates on local files only; it never connects to Odoo or imports.
Usage: python3 script/build_coa_test_files.py MASTER_CSV MASTER_AUDIT DEPENDENCY_AUDIT OUTPUT_DIR
"""

import csv
import json
import sys
from pathlib import Path


TYPE = {"Bank and Cash": "asset_cash", "Receivable": "asset_receivable",
        "Current Assets": "asset_current", "Non-current Assets": "asset_non_current",
        "Prepayments": "asset_prepayments", "Fixed Assets": "asset_fixed",
        "Current Liabilities": "liability_current", "Non-current Liabilities": "liability_non_current",
        "Payable": "liability_payable", "Equity": "equity", "Current Year Earnings": "equity_unaffected",
        "Income": "income", "Other Income": "income_other", "Expenses": "expense",
        "Cost of Revenue": "expense_direct_cost"}

# Code in YA : code of the Odoo record to preserve (from read-only audit).
REUSE = {"11120004": "11120003", "11120005": "11120004", "1112006": "11120002",
         "1120010": "11210010", "1120012": "11210011", "2110010": "21100010"}
STOCK_NEW = {"1130019", "2171091"}
KEEP = {"99999900"}


def parse_report(path, begin, end):
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text.split(begin, 1)[1].split(end, 1)[0])


def write(path, headers, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def main():
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    with Path(sys.argv[1]).open(newline="", encoding="utf-8-sig") as fh:
        master_rows = list(csv.DictReader(fh))
    original = parse_report(sys.argv[2], "=== ODOO_MASTER_AUDIT_JSON_BEGIN ===", "=== ODOO_MASTER_AUDIT_JSON_END ===")
    dependencies = parse_report(sys.argv[3], "=== COA_DEPENDENCIES_BEGIN ===", "=== COA_DEPENDENCIES_END ===")
    if original["database"] != "erp-yussyakmal" or dependencies["database"] != "erp-yussyakmal":
        raise SystemExit("Database mismatch")
    if any(dependencies["record_counts"].get(key) != 0 for key in ("account_move", "account_move_line", "stock_move")):
        raise SystemExit("Transactions found: STOP and revise migration plan")
    master = {r["Code"]: r for r in master_rows}
    if len(master) != 391 or len(master_rows) != len(master):
        raise SystemExit("Expected 391 unique master account codes")
    existing = {str(r["code"]): r for r in original["accounts"]}
    if len(existing) != len(original["accounts"]):
        raise SystemExit("Duplicate Odoo account code")
    for target, source in REUSE.items():
        if source not in existing or not existing[source].get("external_id") or target not in master:
            raise SystemExit("Missing mapped record: " + target + " <- " + source)
        if target != "11120004" and target in existing and target != source:
            raise SystemExit("Unexpected occupied target: " + target)
    if existing["11120004"]["external_id"] == existing["11120003"]["external_id"]:
        raise SystemExit("Outstanding accounts reference same record")

    def fields(master_code, source_code):
        m = master[master_code]
        return {"External ID": existing[source_code]["external_id"], "Code": master_code,
                "Account Name": m["Account Name"], "Type": TYPE[m["Type"]],
                "Allow Reconciliation": "TRUE" if m["Allow Reconciliation"].strip().lower() == "true" else "FALSE"}

    release = [fields("11120005", "11120004")]
    updates = []
    additions = []
    for code, m in master.items():
        if code in KEEP or code == "11120005":
            continue
        if code in REUSE:
            updates.append(fields(code, REUSE[code]))
        elif code in existing:
            if not existing[code].get("external_id"):
                raise SystemExit("Missing External ID: " + code)
            updates.append(fields(code, code))
        else:
            additions.append({"Code": code, "Account Name": m["Account Name"],
                              "Type": TYPE[m["Type"]],
                              "Allow Reconciliation": "TRUE" if m["Allow Reconciliation"].strip().lower() == "true" else "FALSE"})
    if (len(release), len(updates), len(additions), len(KEEP)) != (1, 21, 368, 1):
        raise SystemExit(f"Unexpected counts: {len(release)}, {len(updates)}, {len(additions)}")
    out = Path(sys.argv[4]); out.mkdir(parents=True, exist_ok=True)
    update_headers = ["External ID", "Code", "Account Name", "Type", "Allow Reconciliation"]
    create_headers = ["Code", "Account Name", "Type", "Allow Reconciliation"]
    write(out / "TEST_COA_00_Release_Code.csv", update_headers, release)
    write(out / "TEST_COA_01_Update_Existing.csv", update_headers, updates)
    write(out / "TEST_COA_02_Create_New.csv", create_headers, additions)
    print("Prepared TEST files: release 1, update 21, create 368, keep 1. No database changes.")


if __name__ == "__main__":
    main()
