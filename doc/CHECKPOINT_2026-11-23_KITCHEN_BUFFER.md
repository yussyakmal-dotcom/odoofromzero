# DECISION OVERRIDE — 2026-Nov-23 (LATEST / OWNER-APPROVED)

**This section supersedes the proposed automatic buffer replenishment formula below.** Odoo runs alongside operational SOP, not as sole workflow gate. Every confirmed MO's entire raw material demand should be represented on its Packing batch internal transfer; kitchen buffer is permanent, accumulation is acceptable, other warehouses can exchange inventory using native transfers. Once an Internal Transfer is issued, its full demand must be fulfilled per SOP, independent of production success. Do not automatically subtract other outstanding transfers or kitchen stock from a newly-issued MO demand, suppress a transfer because of reservations, or block document creation for temporary CDC shortage. Inventory movements still occur only on native Odoo Validate, with correct actual qty and no negative physical stock. Existing transfers are not cancelled/replaced by refresh.

**Implemented in GitHub source (NOT server-installed):** `material_requirement_direct_transfer.py` uses `line.required_qty` for native stock.move Demand; removes `reservation_review_count`, `cdc_shortage_count` and `short_max != short_min` blockers; preserves one batch/kitchen document per automatic generation button to avoid accidental double-click creation of the exact same document, not to prohibit standalone supplemental transfers. `views/material_requirement_batch_views.xml` explains this on-screen. Manifest version bumped to `19.0.6.1.0`. `kitchen_buffer_rules.py` is now an UNINTEGRATED prototype, not the approved calculator; do not use its formula to implement transfers.

**Still pending:** validate Python/XML on actual server before upgrade; read-only test of expected full demand for 14 MO / 74 SKUs; GUI upgrade only on `erp-yussyakmal-mrp-test` after backup; confirm 1 native picking / kitchen, stock.move Demand equals full MO raw demand, Odoo Qty may only be prefilled when stock is physically available, and validation remains manual. Existing snapshots' short_min/max and CDC shortage badges are diagnostics only, NOT transfer quantities or blockers.

---

# CHECKPOINT — Permanent Kitchen Buffer Replenishment (2026-Nov-23)

User correction: every production kitchen has its own **permanent raw-material buffer warehouse**, because the CDC is closed during night production and on holidays. CDC transfers supply the kitchen's continuing operations. Delivered raw material is **not required to be consumed by the particular MO or same-day production**; unconsumed material remains kitchen inventory for the next MO. Failed production does not silently cancel previously approved transfer obligations.

**Source-only math added:** `addons/ya_material_requirement/models/kitchen_buffer_rules.py`, pure tests `script/test_kitchen_buffer_rules_ya.py`. Formula per kitchen/product, all figures in base UoM:

```
required_before_supply = ALL open MO unfulfilled obligations
                       + other independently committed obligations
                       + configured kitchen buffer target
supply = physical kitchen stock + VALID undelivered committed incoming transfers
new_replenishment_qty = max(required_before_supply - supply, 0)
```

**Critical:** MO reservations are not subtracted from physical kitchen stock a second time. Their requirements are included once in open MO obligations. When reconciling 10 outstanding transfers, include only the remaining quantity of genuine noncancelled committed incoming transfers, scoped by product, kitchen destination, company, leg and stock state. Do not count draft, already received, duplicate legs, unrelated transfers, or routed transit and direct delivery twice. Fulfilled/done stock already included in kitchen on-hand must never also be incoming. MO cancelled/done/partially consumed demands need exact treatment and shall not be invented from confirmed list alone.

**Buffer target must be configured explicitly per kitchen/SKU** from expected consumption during CDC closure plus safety margin; zero is NOT an approved permanent buffer policy. Do not silently choose 1 day, 2 days, or other invented factor. User did not supply targets yet. Any change to targets is separate from MO history.

**Deployment status:** source-only first step, NOT integrated into production Material Requirement calculation or automatic native transfer generation, NOT deployed or tested on Odoo server. Existing `material_requirement.py` and `material_requirement_direct_transfer.py` still implement old per-batch short_min/short_max; **do not use those draft transfer quantities as authoritative buffer replenishment** until integration/verified ORM and GUI test. Do not apply stock adjustment, validate transfers, change MO reservations, or modify main DB as part of this change.

Next implementation after quantity/source mapping audit: build read-only per-kitchen/SKU projection of all open MO obligations and valid outstanding incoming by actual native stock.move routes; maintain explicit buffer target in master; validate planned vs reserved/received and idempotency; then replace per-batch transfer qty with projection, with Odoo native stock picking and operator exception review. Test database exclusively: `erp-yussyakmal-mrp-test`. Keep GitHub-first, GUI backup before module upgrade. Run `python3 script/test_kitchen_buffer_rules_ya.py` as feri. No standard Purchase workflow changes.
