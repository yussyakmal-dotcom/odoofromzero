# YA Production Planning (Odoo 19 Community) — review candidate

Status: **SOURCE CANDIDATE, NOT YET INSTALLED OR TESTED ON ODOO SERVER**.

Purpose: Import a multi-sheet XLSX matching the approved `template_jadwal(1).xlsx`: `info` maps sheet names to Work Center kitchen codes; kitchen sheets contain `DAPUR | Product | Max | Unit`. Delivery date and S1/S2/S3 slot are selected in the wizard.

Flow: **Upload → Validate & Preview → Save Draft → Publish Entire Upload**. One plan per kitchen/date/slot. This addon does not create MO, stock moves, RO, or accounting entries. The XLSX SKU selection is controlled by SOP; this addon performs technical checks.

Validation: XLSX format, sheet links and headers, duplicate references, integer nonnegative Max, Reference matching product.product.default_code, product name, one active Work Center per kitchen code, and UoM equal to the finished-product UoM of the unique BoM belonging to the DAPUR warehouse. Differences from stock UoM are accepted when the BoM output UoM matches Excel. Alternate Multi-UoM conversions **are not enabled**; Production Planning does not convert quantities or generate MOs. A zero Max is retained in planning but will not be eligible when RO integration is built.

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

## Update: per-kitchen publishing and unified list (22 November 2026)

- A complete XLSX upload can still save multiple kitchen Drafts in one delivery date/slot.
- **Publish This Kitchen** changes only the selected Draft to Published; other kitchen Drafts remain Draft.
- The Production Planning menu displays both Draft and Published in one list, with separate search filters and grouping.
- Published is immutable for SKU Max and acts as **future input** for store RO templates, filtered to Max > 0. **RO creation and store ordering are NOT implemented in this addon yet**; no shop can actually submit an RO solely because a planning was Published.
- Do not reupload or delete existing Drafts just to apply this UI/workflow change.
- Upgrading this addon affects views and model methods only; use the MRP test database and check a GUI backup exists first.

## Reupload behavior (2026-11-22)

A workbook is scoped to the selected delivery date and slot; its `info` sheet lists participating kitchens. Each kitchen is identified by **delivery date + slot + kitchen code**.

- **Not present:** create a new Draft.
- **Present and Draft:** replace all SKU lines and Max quantities for **that kitchen only**. Omitted kitchens are not deleted or modified.
- **Present and Published:** skip completely and keep the Published data untouched; other Draft/new kitchens in the same upload still proceed.
- **Preview:** show per-kitchen expected CREATE / REPLACE / SKIP before saving. After Save Draft, a notification summarizes the actual actions and opens planning records for that date and slot.
- Published always remains immutable, and all writes are in one Odoo request transaction; a failure rolls back new Draft creation and Draft replacement together.
- The XLSX is still validated against SKU/BoM UoM master data. This change does not create RO transactions or authorize store orders.

## List header upload shortcut

The Production Planning list now has **Upload Planning XLSX** available in its list toolbar to Manufacturing Managers, without requiring record selection. This opens the *existing* import wizard. No changes to CSV/XLSX parsing, database contents, publish semantics, or store RO behavior. In Odoo 19 the list header uses `<button type="object" display="always"/>`, invoking model method `action_open_upload_wizard`.

Deploy both `models/planning.py` and `views/planning_views.xml`, upgrade **only** `ya_production_planning` in `erp-yussyakmal-mrp-test` to reload XML, restart service, then test list shortcut. Existing Draft/Published planning records should remain as they are.
