# YA Sales Order — Production Capacity

## Stage 1 — Source only, not installed
Adds a **separate custom SO entry** under YA Production Capacity → SEBELUM PRODUKSI → Sales Order, reusing the native `sale.order` model. A YA order requires delivery date and slot that exist among Published Planning records. Native Sales → Orders remains separate and continues without YA slot/reservation restrictions.

This first stage **does not reserve capacity, confirm YA SO, generate MO2, or change Packing**. The YA Confirm button intentionally raises an explicit error until a tested reservation engine exists; otherwise the system would accept an order without reserving production capacity.

Source is protected by a backend YA classification boolean and server-side validation; view-only `required` is not considered sufficient. The Published schedule lookup is scoped by date+slot and requires at least one Published kitchen planning; product-by-product capacity verification is a later gate.

## Safety
- GitHub-first; test only `erp-yussyakmal-mrp-test`.
- Do not upgrade other addons or touch existing RO, Package, MO or DO.
- Before first installation: source checks, GUI backup, copy ONLY this addon, `-i ya_sale_production_capacity`, verify registry, then UI smoke.
- See `doc/FASE2_SO_CAPACITY_AND_PACKING_DESIGN_2026-11-25.md`.
