# YA Store RO — Phase 1 (Odoo 19 Community)

**Checkpoint: 22 November 2026. Source candidate only; NOT installed or tested on the Odoo server.**

## Scope implemented

Manager-only menu **YA Production Capacity → RO Toko - Download Template** opens a wizard to choose one **Published Planning** record and a **store warehouse**. Generate RO Excel downloads a file with:

- `info`: `Template Type=YA_STORE_RO_V1`, Planning ID, delivery date, slot, kitchen code, store warehouse ID, store code, store name and instructions.
- `RO`: **Reference | Nama Produk | Qty Pesan**. Only SKU lines with Planning Max > 0 are included. Qty Pesan is **blank** for each SKU.
- One Excel is for **one store + one kitchen + one delivery date + one slot**. The Published Planning is the single source of reference/name/eligibility.

**Decision:** Qty Pesan entered by a store is free (integer, nonnegative). **Do not round it to BoM multiples.** At Packing consolidation after aggregating all store RO (and SO under SO-priority policy), production quantities are **always rounded UP** to the next BoM output multiple. Production surplus is allocated to stores separately from the original requested quantities. **This module does NOT yet implement upload, RO Draft/Confirmed, store-side permissions, Packing consolidation, SO or MO.**

## Protection and pending validation

- No access to this wizard for stores yet. Only Manufacturing Managers can generate the Excel. There is no store role mapping or store-specific record rule yet.
- The warehouse chooser is not yet limited to warehouses classified as stores (the project has not established a definitive automated warehouse-to-store flag). **During testing, select only an actual store warehouse.**
- Files are built using `openpyxl` and stored only transiently in the wizard. No stock, planning, accounting, or RO persistent records are modified.
- When implementing RO upload, validate both metadata and each Reference against Published Planning at confirm time. Do NOT trust editable spreadsheet metadata; do NOT mistake planning Max for an individual store order cap.
- Draft planning is excluded by domain and checked again server-side. Max 0 is filtered out.
- Future TODO: store permissions, XLSX import with duplicate/re-upload checks, Draft → Confirmed → Closed, consolidation & store surplus allocation, accounting impacts on later stock moves.

## Safe first server step: source preflight ONLY

```bash
cd ~/odoofromzero
git pull
python3 script/check_ya_store_ro_source_readonly.py
# Expected: ERROR_COUNT: 0, RO_TEMPLATE_SOURCE_PREFLIGHT_OK
```

Do NOT run `-i` for this candidate until source preflight and permission/UX assumptions have been reviewed. See [skill](../../doc/SKILL_ODOO19_ADDON_WORKFLOW.md) for first-install process after explicit checkpoint.
