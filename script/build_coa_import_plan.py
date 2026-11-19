"""Build DRAFT COA migration CSVs from the read-only Odoo audit.

Usage: python3 script/build_coa_import_plan.py AUDIT_REPORT MASTER_CSV OUTPUT_DIR
No Odoo connection is made. Generated files must be reviewed before import.
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path


TYPE_MAP = {
    "Bank and Cash": "asset_cash", "Receivable": "asset_receivable",
    "Current Assets": "asset_current", "Non-current Assets": "asset_non_current",
    "Prepayments": "asset_prepayments", "Fixed Assets": "asset_fixed",
    "Current Liabilities": "liability_current", "Non-current Liabilities": "liability_non_current",
    "Payable": "liability_payable", "Equity": "equity",
    "Current Year Earnings": "equity_unaffected", "Income": "income",
    "Other Income": "income_other", "Expenses": "expense",
    "Cost of Revenue": "expense_direct_cost",
}

# Target code : (existing Odoo code, reason). These are human-review items,
# not automated updates, because other records may depend on those accounts.
SPECIAL = {
    "11120004": ("11120003", "Incoming outstanding account; 11120004 currently belongs to outgoing payments"),
    "11120005": ("11120004", "Outgoing outstanding account; first resolve code collision"),
    "1112006": ("11120002", "Bank suspense linked to bank and cash journals"),
    "1120010": ("11210010", "Receivable account may be a company/partner default"),
    "1120012": ("11210011", "PoS receivable is a company default"),
    "2110010": ("21100010", "Payable account may be a company/partner default"),
    "1130019": ("", "Stock interim delivered; verify valuation routing"),
    "2171091": ("29000000", "Stock interim received; verify stock accounting and category defaults"),
    "99999900": ("99999900", "Keep Odoo 19 current-year-earnings record and type"),
    "22110010": ("22110010", "Bank loan: liability_current versus liability_non_current"),
}


def read_audit(path):
    text = path.read_text(encoding="utf-8")
    body = text.split("=== ODOO_MASTER_AUDIT_JSON_BEGIN ===", 1)[1].split("=== ODOO_MASTER_AUDIT_JSON_END ===", 1)[0]
    return json.loads(body)


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    if len(sys.argv) != 4:
        raise SystemExit("Usage: python3 script/build_coa_import_plan.py AUDIT_REPORT MASTER_CSV OUTPUT_DIR")
    audit = read_audit(Path(sys.argv[1]))
    if audit.get("database") != "erp-yussyakmal":
        raise SystemExit("Database mismatch; expected erp-yussyakmal")
    with Path(sys.argv[2]).open(encoding="utf-8-sig", newline="") as handle:
        master = list(csv.DictReader(handle))
    current = {str(a["code"]): a for a in audit["accounts"]}
    duplicates = [c for c, n in Counter(x["Code"] for x in master).items() if n != 1]
    if duplicates:
        raise SystemExit("Duplicate master codes: " + repr(duplicates))
    out = Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)

    updates, additions, review = [], [], []
    for row in master:
        code = row["Code"].strip(); name = row["Account Name"].strip()
        account_type = TYPE_MAP.get(row["Type"], "")
        if not account_type:
            raise SystemExit("Unknown account type: " + row["Type"])
        rec = row["Allow Reconciliation"].strip().lower() == "true"
        existing = current.get(code)
        if code in SPECIAL:
            source, reason = SPECIAL[code]
            review.append({"Target Code": code, "YA Account Name": name, "Odoo Source Code": source,
                           "Odoo External ID": current.get(source, {}).get("external_id", ""),
                           "Target Type": account_type, "Status": "REVIEW", "Reason": reason})
        elif existing:
            if not existing.get("external_id"):
                review.append({"Target Code": code, "YA Account Name": name, "Odoo Source Code": code,
                               "Target Type": account_type, "Status": "REVIEW", "Reason": "No External ID"})
            else:
                updates.append({"External ID": existing["external_id"], "Code": code,
                                "Account Name": name, "Type": account_type,
                                "Allow Reconciliation": str(rec).upper()})
        else:
            additions.append({"Code": code, "Account Name": name,
                              "Type": account_type, "Allow Reconciliation": str(rec).upper()})

    write_csv(out / "DRAFT_COA_01_Update_Existing.csv",
              ["External ID", "Code", "Account Name", "Type", "Allow Reconciliation"], updates)
    write_csv(out / "DRAFT_COA_02_Import_New.csv",
              ["Code", "Account Name", "Type", "Allow Reconciliation"], additions)
    write_csv(out / "COA_03_Review.csv",
              ["Target Code", "YA Account Name", "Odoo Source Code", "Odoo External ID", "Target Type", "Status", "Reason"], review)
    print(json.dumps({"database": audit["database"], "master": len(master), "draft_updates": len(updates),
                      "draft_additions": len(additions), "review_required": len(review)}, indent=2))
    print("DRAFT files must NOT be imported until review cases and journal/company defaults are resolved.")


if __name__ == "__main__":
    main()
