# YA Sales Order — Production Capacity

## Stage 1 — Quotation first; YA schedule only at confirmation

**Source version 19.0.1.0.4; deployment on clone NOT YET VERIFIED.**

- Dedicated menu **YA Production Capacity → SEBELUM PRODUKSI → Sales Order** uses native Odoo `sale.order` and protected workflow marker `ya_is_capacity_so`.
- **Quotation Draft/Sent does not require YA Tanggal Kirim or YA Slot Kirim.** It can be saved and sent without Published Planning. YA fields are hidden in draft/sent on the dedicated primary form.
- Clicking native **Confirm** for a YA quotation opens the **YA Jadwal Kirim** wizard. This wizard requires a delivery date + slot with Published Planning.
- **Stage 1 deliberately blocks the final confirmation after checking the schedule**, because production-capacity reservation of individual SKUs and Paket components does not yet exist. No SO confirmation, capacity reservation, MO or stock is posted by the wizard.
- Standard Sales quotation/SO in **Sales → Orders** remains native and is not required to choose YA slot. Its confirmation delegates to Odoo.
- SO date is still a native `fields.Date`; standard date-picker remains available in the confirmation wizard, with `YYYY-Mon-DD` computed read-only label based on existing `ya_store_ro.models.date_labels.format_ymondd`. Custom YA SO list uses the same formatted label.

## Implementation boundary
This source is an interim **safe confirmation gate**, not a working SO reservation. **Next stage**: add atomic Published capacity budget and Package component expansion to the wizard, persist date + slot on Confirmed YA SO within the same transaction, call native confirmation only after successful reservation, then integrate MO1/MO2 and PCK final allocation.

## Safe deployment
- Development DB **ONLY**: `erp-yussyakmal-mrp-test-RO_SO` (clone).
- Original Fase 1 DB `erp-yussyakmal-mrp-test`, main `erp-yussyakmal`, and integer-test must not be changed.
- `git pull` → source preflight → compileall → verified GUI backup → deploy **only this addon** → `-u ya_sale_production_capacity` if already installed (not `-i`).
- Restart Odoo service at a safe time; inspect module state, form draft/sent, confirm wizard, native Sales unaffected.
- See `doc/CHECKPOINT_2026-11-25_FASE2_RO_SO_CLONE.md` and `doc/FASE2_SO_CAPACITY_AND_PACKING_DESIGN_2026-11-25.md`.
