"""Read-only Odoo 19 audit of account references needed before YA COA migration.

Run via `odoo-bin shell < script/audit_coa_dependencies.py`. Prints JSON only.
No records are created, updated, deleted, or committed.
"""

import datetime
import json


def account_reference(rec, field_name):
    if field_name not in rec._fields:
        return None
    value = rec[field_name]
    if not value:
        return None
    if rec._fields[field_name].type == "many2one":
        return {"id": value.id, "code": value.code if "code" in value._fields else "", "name": value.display_name}
    return str(value)


def account_fields(rec):
    return {name: account_reference(rec, name) for name, field in rec._fields.items()
            if field.type == "many2one" and field.comodel_name == "account.account"}


def main():
    odoo_env = globals().get("env")
    if odoo_env is None:
        raise RuntimeError("Run this file from the Odoo shell")
    odoo_env.cr.execute("SET TRANSACTION READ ONLY")
    company_rows = []
    for c in odoo_env["res.company"].sudo().search([]):
        company_rows.append({"company_id": c.id, "company_name": c.name,
                             "account_fields": account_fields(c)})

    journal_rows = []
    for j in odoo_env["account.journal"].sudo().search([]):
        row = {"journal_id": j.id, "code": j.code, "type": j.type,
               "account_fields": account_fields(j), "payment_method_account_fields": []}
        for fname in ("inbound_payment_method_line_ids", "outbound_payment_method_line_ids"):
            if fname in j._fields:
                for line in j[fname]:
                    row["payment_method_account_fields"].append({"line_id": line.id,
                                                                 "direction": fname,
                                                                 "account_fields": account_fields(line)})
        journal_rows.append(row)

    category_rows = []
    for cat in odoo_env["product.category"].sudo().search([]):
        category_rows.append({"category_id": cat.id, "name": cat.complete_name,
                              "cost_method": cat.property_cost_method if "property_cost_method" in cat._fields else None,
                              "valuation": cat.property_valuation if "property_valuation" in cat._fields else None,
                              "account_fields": account_fields(cat)})

    location_rows = []
    if "stock.location" in odoo_env.registry.models:
        locations = odoo_env["stock.location"].sudo().search([("usage", "=", "internal")])
        for loc in locations:
            refs = account_fields(loc)
            if any(value is not None for value in refs.values()):
                location_rows.append({"location_id": loc.id, "name": loc.complete_name,
                                      "account_fields": refs})

    report = {
        "audit": "coa_dependencies_v1",
        "database": odoo_env.cr.dbname,
        "mode": "read_only",
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "companies": company_rows,
        "journals": journal_rows,
        "product_categories": category_rows,
        "internal_locations_with_account_references": location_rows,
        "record_counts": {
            "account_move": odoo_env["account.move"].sudo().search_count([]),
            "account_move_line": odoo_env["account.move.line"].sudo().search_count([]),
            "stock_move": odoo_env["stock.move"].sudo().search_count([]) if "stock.move" in odoo_env.registry.models else None,
        },
    }
    print("=== COA_DEPENDENCIES_BEGIN ===")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print("=== COA_DEPENDENCIES_END ===")


main()
