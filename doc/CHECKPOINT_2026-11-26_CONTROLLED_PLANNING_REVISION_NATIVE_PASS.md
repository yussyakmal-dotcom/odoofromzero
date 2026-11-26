# 2026-11-26 — Controlled Published Planning Revision: native backend PASS

## Scope and source
- Authorized database only: `erp-yussyakmal-mrp-test-RO_SO`.
- Tested source commit: `38688317e1527d537ba13742729c7e007a2d1283`, branch `fase2-controlled-planning-revision`; no main merge or production deployment.
- Persistent isolated worktree: `/var/lib/ya-fase2-testing/source`; addon overrides: `/var/lib/ya-fase2-testing/addons` for ya_production_planning and ya_sale_production_capacity.
- Installed versions reported: 19.0.1.4.0 and 19.0.1.2.0 respectively. GUI ZIP backup completion reported by operator, restore not independently tested.
- Evidence below is operator-supplied terminal output in ChatGPT project, not CI or independent execution.

## Evidence
- Pure rules: 16 cases PASS; static Python/XML PASS.
- Unused: native published increase/decrease, direct-write and blank-reason rejection, stale revision, immutable audit, explicit rollback PASS (`FASE2_PLANNING_REVISION_UNUSED_NATIVE_ROLLBACK_PASS`).
- Ordinary RO: native confirm qty 400, Max 500 -> 750 -> 250, audit shortage 150, original RO unchanged and rollback PASS (`FASE2_PLANNING_REVISION_RO_COMMITTED_NATIVE_PASS`). Initial deletion test hit last-SKU guard; later dedicated test resolved this.
- SO: native wizard confirm qty 300, capacity ledger 300, no early DO, Max 500 -> 750 accepted, decreases to 500 and 250 rejected, referenced deletion rejected, original SO/ledger unchanged, audit and rollback PASS (`FASE2_PLANNING_REVISION_SO_COMMITTED_NATIVE_PASS`).
- Mixed ordinary/Paket RO: Paket 12114 component 11999, demand 8 + 4 = 12, Max 14 -> 21 -> 7, shortage 5, package-only and mixed delete guards, temporary user and fixture rollback PASS (`FASE2_PLANNING_REVISION_MIXED_PACKAGE_RO_NATIVE_PASS`).
- Final delete guard: ordinary RO referenced SKU rejection, unused companion deletion, delete audit, original RO unchanged and rollback PASS (`FASE2_PLANNING_REVISION_FINAL_DELETE_GUARD_PASS`).
- PP1/MO1: native legacy joint stage and native MO release, increases/decreases/deletions rejected for committed and companion SKU at both stages; MO and original demand unchanged; no audit for rejected revision; fixture/MO rollback PASS (`FASE2_PLANNING_REVISION_PP1_MO1_LOCK_NATIVE_PASS`).
- Wizard: manager/operator server-side form/action/ACL test script completed with rollback marker `FASE2_PLANNING_REVISION_WIZARD_INTEGRATION_PASS`; operator supplied terminal tail. Browser visual UAT not yet run.
- /tmp environment disappeared; recovered at persistent path with exact tested commit, loaded module source paths and audit table query verified. No upgrade repeated.

## Remaining gates / known limitations
- Browser visual UAT pending. Do not open this upgraded clone through shared main HTTP service using old addons. Isolate GUI runtime and database access; prefer a separate PostgreSQL instance with same authorized database name restored from clone backup, subject to environment checks. No change to production/Fase1 or shared service.
- Current staged PP1 locks revisions even before Produksi OK; temporary fail-closed restriction until controlled snapshot refresh is implemented. No reopening released MO1.
- RO Max zero, last-SKU deletion, and draft references are restricted by current rules.
- Paket component demand uses current active BoM, not a Confirm-time snapshot; BoM changes after Confirm can change computed commitments. Historical SKU 10035 and 10008 Max values not multiples of current BoM; no correction made.
- Native UAT uses synthetic rollback fixtures and existing master data, not full operational fulfillment. Package/PP1 fixture role setup used sudo; wizard test uses non-sudo manager/operator. No concurrency stress test or entire three-consolidation E2E claim.
- Current PP1/PP2 engine remains legacy; next implement approved Design B from section 8/9 of CHECKPOINT_2026-11-25_FASE2_TIGA_KONSOLIDASI_SO_FIRST_FREEZE.md: PP1 RO+Paket+early confirmed SO; PP2 SO-only incremental MO; physical post-production SO first, RO Paket next, ordinary RO last, surplus unallocated. Settings/cutoffs, slot locks and rolling planning SOP remain open. No main merge until agreed gates.
