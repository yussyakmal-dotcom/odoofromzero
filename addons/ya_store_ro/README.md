# YA Store RO — Phase 1 (Odoo 19 Community)

**Checkpoint: 22 November 2026. Feri melaporkan addon sudah berhasil dijalankan di MRP test; XLSX berhasil diunduh dan SKU sesuai Published Planning. Generator smoke test PASS, fitur upload/Confirm RO belum dibuat.**

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

## Hasil uji GUI Feri (22 November 2026)

**PASS (laporan user):** form generator template dapat dipakai, XLSX berhasil diunduh, SKU pada XLSX cocok dengan SKU dapur Published. Dengan demikian **status addon bukan lagi sekadar source candidate**, melainkan terpasang dan generator bekerja di MRP test menurut pengguna. Tidak ada bukti proses upload RO atau order Confirmed karena keduanya belum diimplementasikan. **Lanjutkan fitur import XLSX → Draft/Confirmed**, bukan mengulang instalasi pertama.

## Phase 2 RO workflow — source in GitHub, server validation pending

New persistent `ya.store.ro` and `ya.store.ro.line` models, import wizard `ya.store.ro.import`, list/form views, and ACL added in addon version `19.0.2.0.0`. Intended sequence: **Upload Excel → Validate & Preview → Save Draft → edit Qty Pesan in Odoo → Confirm RO → immutable Confirmed**. Excel accelerates initial input; it is **not the final order validation**. Reupload only replaces a Draft for the same store + Published Planning; a Confirmed RO cannot be overwritten. Draft Qty Pesan can be edited directly and is a nonnegative integer with **no BoM rounding**. Confirm checks Published status, eligible SKU, and at least one SKU with positive Qty. No stock moves or DO created. User explicitly reconfirmed this behavior. **Phase 2 smoke test PASS menurut laporan Feri: upload, Draft, edit Qty, Confirm.**

## Checkpoint laporan uji Feri — RO Tahap 2 PASS (22 November 2026)

**Feri melaporkan seluruh flow RO Toko berhasil di GUI MRP test:** (1) upload XLSX, (2) Save Draft, (3) edit Qty Pesan pada Draft, (4) Confirm RO. Artinya **smoke test fungsional alur RO Tahap 2 PASS menurut laporan user**; belum ada bukti uji edge cases (file rusak, duplicate, pembatasan hak toko, Confirmed immutable via API, atau akuntansi). Jangan mengulang instalasi/upgrade tahap ini tanpa perubahan kode.

**Tahap 3 berikutnya: konsolidasi oleh Packing** untuk semua RO Confirmed per tanggal kirim + slot + dapur + SKU; pertahankan requested per toko, hitung kebutuhan gabungan, Qty Produksi **ceil ke kelipatan BoM** (bukan nearest/bukan down), catat surplus terpisah untuk dialokasikan ke toko, rancang penanganan Max Capacity dan prioritas SO, lalu MO dan DO/internal transfer pada tahap berikutnya. **Belum diimplementasi.** Jangan membuat transfer atau MO saat Confirm RO. Detail algoritma alokasi surplus dan kasus kapasitas belum final.

## RO-only cycle decision — prorata surplus until store receipt (22 November 2026)

**Feri decided:** Phase 1 RO-only Packing consolidation uses **PRORATA of production surplus by original requested Qty per store**. **SO is deferred entirely** from the first-cycle MO logic, and its priority/allocation rules must be revisited when SO is activated; do not implement SO logic now. Complete **one end-to-end operational cycle** first: Confirmed RO → Packing consolidation → MO/production → transfer from kitchen to Packing → Packing/Transit to store → receipt at store.

**Allocation method chosen for implementation:** deterministic **largest remainder** (Hamilton) with whole-unit Qty and store ID ascending tie-break: total required = sum of all Confirmed store RO for the same kitchen/date/slot/SKU; produced = round UP to BoM batch; surplus = produced - required; each store receives at least its original Qty, plus floor(surplus * its Requested / Total Requested), remaining units go to largest fractional remainder. Zero-request stores receive zero additional Qty; no random or manual splitting. Keep original requested, allocated surplus and final allocated as distinct quantities. Example BoM24, requests 13/27/9 → required49, produced72, surplus23 → allocated 19/40/13. This arithmetic choice requires user UI test before actual distribution.

**Source milestone (not yet deployed or GUI tested):** `addons/ya_store_ro/models/allocation_rules.py` pure calculation + `script/test_ro_packing_prorata_pure_ya.py` script. **No new Odoo view, database table, MO or stock move yet.** This file is deliberately independent of Odoo and does not affect the currently installed RO behavior. Next: source test, add Packing consolidation preview (confirmed RO only) with capacity exception if rounding up exceeds Published Max; then stage MO and warehouse moves/receipt with accounting valuation test. Do not silently cut quantity below requested or exceed Published capacity.
