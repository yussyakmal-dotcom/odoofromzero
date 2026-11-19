# Read-only master configuration audit - Odoo 19

Purpose: inspect the existing Odoo configuration before importing YA's COA, product categories and warehouses. The script reports account codes, technical External IDs, journal account references, company accounting defaults, product category valuation settings, warehouse definitions and the state of relevant modules. It compares account codes with `MASTER CONFIG/COA_Bersih_Import.csv` when run from the repository root.

It **does not import, create, modify, delete or commit** any Odoo records. It sets its database transaction to read-only. The output contains configuration names and codes, not passwords, customer details, invoices or account balances.

## Run on the Odoo server

1. Sync/pull the repository to the server.
2. Enter the repository root (`odoofromzero`), which contains `script` and `MASTER CONFIG`.
3. Use the *same Linux user and Odoo configuration* that normally runs your Odoo service. Replace the executable/configuration paths below to match your installation.
4. Run:

```bash
odoo shell -c /etc/odoo/odoo.conf -d erp-yussyakmal --no-http < script/audit_odoo_master.py > odoo_master_audit_raw.txt 2>&1
```

If your install uses `/opt/odoo/odoo-bin` instead of `odoo`, replace the executable. If the service is running in a Python virtual environment, activate it first. Do not use the plain `python` command to execute this file: the script needs the `env` object provided by `odoo shell`.

5. Open `odoo_master_audit_raw.txt`. A successful run contains both `ODOO_MASTER_AUDIT_JSON_BEGIN` and `ODOO_MASTER_AUDIT_JSON_END`. Send the output file back to ChatGPT for review. If there is an exception instead, send only the error lines and omit any secrets or connection strings.

**Privacy:** The report may reveal internal chart-of-account codes, journal names and warehouse names; review it before sharing publicly. Do not post a database password or `/etc/odoo/odoo.conf`.

**Important:** This is a diagnostic only. No changes should be made to default account references until the report has been reviewed. Always back up the database before any later import or update.
