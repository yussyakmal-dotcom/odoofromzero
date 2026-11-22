# YA Production Planning (Odoo 19 Community) — review candidate

Status: **SOURCE CANDIDATE, NOT YET INSTALLED OR TESTED ON ODOO SERVER**.

Purpose: Import a multi-sheet XLSX matching the approved `template_jadwal(1).xlsx`: `info` maps sheet names to Work Center kitchen codes; kitchen sheets contain `DAPUR | Product | Max | Unit`. Delivery date and S1/S2/S3 slot are selected in the wizard.

Flow: **Upload → Validate & Preview → Save Draft → Publish Entire Upload**. One plan per kitchen/date/slot. This addon does not create MO, stock moves, RO, or accounting entries. The XLSX SKU selection is controlled by SOP; this addon performs technical checks.

Validation: XLSX format, sheet links and headers, duplicate references, integer nonnegative Max, Reference matching product.product.default_code, product name, one active Work Center per kitchen code, and UoM equal to product stock UoM. Alternate Multi-UoM conversions **are not yet enabled**. A zero Max is retained in planning but will not be eligible when RO integration is built.

Preview writes only transient wizard records; Save Draft creates/overwrites only Draft planning; Published plans cannot be overwritten. Publish requires all plans for the date/slot to belong to the same import batch.

## First server step: source preflight only (no DB modifications)

```bash
cd ~/odoofromzero
git pull
/opt/odoo19/venv/bin/python3 script/check_production_planning_source_readonly_ya.py
```

Inspect the terminal output. **Do not deploy or install yet.** A successful static preflight does not confirm Odoo ORM/API, business master matching, or UI installation.

## Environment

Development DB: `erp-yussyakmal-mrp-test` only. Never touch `erp-yussyakmal` or `erp-yussyakmal-integer-test` without explicit approval.

After source preflight, next stage is a controlled install rehearsal on the MRP test database with backups and rollback plan. Do not treat this README as permission for installation.
