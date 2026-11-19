"""Read-only Odoo 19 master configuration audit. Run inside `odoo shell`.

This script does not create, modify, unlink or commit any Odoo records.
Run from the root of the odoofromzero checkout to compare master CSV files.
"""

import csv
import datetime
import json
import os
import sys
from pathlib import Path


def value(record, field):
    if field not in record._fields:
        return None
    v = record[field]
    if record._fields[field].type == "many2one":
        return {"id": v.id, "display_name": v.display_name} if v else None
    if record._fields[field].type in ("many2many", "one2many"):
        return [{"id": x.id, "display_name": x.display_name} for x in v]
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    return v if v is not False else False


def record_dict(record, fields):
    return {f: value(record, f) for f in fields if f in record._fields}


def load_csv(path):
    if not path.is_file():
        return {"status": "missing", "path": str(path)}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    return {"status": "loaded", "path": str(path), "rows": rows}


def main():
    # `env` is provided by the Odoo shell, not a standalone Python interpreter.
    odoo_env = globals().get("env")
    if odoo_env is None:
        raise RuntimeError("Run with `odoo shell -d <database> < script/audit_odoo_master.py`")

    # Database-side safeguard. No writes are performed in this script.
    odoo_env.cr.execute("SET TRANSACTION READ ONLY")
    account_model = odoo_env["account.account"].sudo().with_context(active_test=False)
    accounts = account_model.search([], order="code,id")
    account_fields = ["id", "code", "name", "account_type", "reconcile", "deprecated", "company_ids", "company_id", "currency_id"]
    account_rows = []
    external_ids = accounts.get_external_id()
    for a in accounts:
        row = record_dict(a, account_fields)
        row["external_id"] = external_ids.get(a.id) or ""
        account_rows.append(row)

    journals = []
    journal_fields = ["id", "name", "code", "type", "company_id", "default_account_id", "suspense_account_id", "profit_account_id", "loss_account_id"]
    for journal in odoo_env["account.journal"].sudo().search([]):
        row = record_dict(journal, journal_fields)
        row["incoming_payment_methods"] = []
        row["outgoing_payment_methods"] = []
        for field, output_key in [("inbound_payment_method_line_ids", "incoming_payment_methods"), ("outbound_payment_method_line_ids", "outgoing_payment_methods")]:
            if field in journal._fields:
                for line in journal[field]:
                    row[output_key].append(record_dict(line, ["id", "name", "payment_method_id", "payment_account_id"]))
        journals.append(row)

    companies = []
    company_fields = ["id", "name", "country_id", "currency_id", "account_fiscal_country_id", "account_default_pos_receivable_account_id", "account_journal_suspense_account_id", "account_journal_payment_debit_account_id", "account_journal_payment_credit_account_id", "property_stock_account_input_categ_id", "property_stock_account_output_categ_id", "property_stock_valuation_account_id"]
    for company in odoo_env["res.company"].sudo().search([]):
        companies.append(record_dict(company, company_fields))

    categories = []
    category_fields = ["id", "name", "parent_id", "property_cost_method", "property_valuation", "property_account_income_categ_id", "property_account_expense_categ_id", "property_stock_account_input_categ_id", "property_stock_account_output_categ_id", "property_stock_valuation_account_id"]
    if "product.category" in odoo_env.registry.models:
        for category in odoo_env["product.category"].sudo().search([]):
            categories.append(record_dict(category, category_fields))

    warehouses = []
    if "stock.warehouse" in odoo_env.registry.models:
        for warehouse in odoo_env["stock.warehouse"].sudo().search([]):
            warehouses.append(record_dict(warehouse, ["id", "name", "code", "company_id", "lot_stock_id", "view_location_id"]))

    module_names = ["stock", "account", "account_usability", "account_financial_report", "account_reconcile_oca", "account_asset_management", "account_fiscal_year"]
    modules = [record_dict(mod, ["name", "state", "latest_version"]) for mod in odoo_env["ir.module.module"].sudo().search([("name", "in", module_names)])]

    master_dir = Path(os.environ.get("ODOO_MASTER_CSV_DIR", "MASTER CONFIG"))
    master = load_csv(master_dir / "COA_Bersih_Import.csv")
    master_codes = {}
    if master["status"] == "loaded":
        master_codes = {r.get("Code", "").strip(): r for r in master["rows"]}
    existing_by_code = {}
    for row in account_rows:
        existing_by_code.setdefault(str(row.get("code") or ""), []).append(row)
    comparison = []
    for code, row in master_codes.items():
        current = existing_by_code.get(code, [])
        comparison.append({
            "code": code,
            "master_name": row.get("Account Name"),
            "master_type": row.get("Type"),
            "master_reconcile": row.get("Allow Reconciliation"),
            "status": "code_exists" if current else "new_code",
            "existing": current,
        })

    result = {
        "audit_version": "1.0",
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "database": odoo_env.cr.dbname,
        "mode": "read_only",
        "modules": modules,
        "companies": companies,
        "accounts": account_rows,
        "journals": journals,
        "product_categories": categories,
        "warehouses": warehouses,
        "master_file": {"status": master["status"], "path": master["path"], "count": len(master.get("rows", []))},
        "master_account_comparison": comparison,
    }
    print("=== ODOO_MASTER_AUDIT_JSON_BEGIN ===")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print("=== ODOO_MASTER_AUDIT_JSON_END ===")


main()
