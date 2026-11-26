# PP1 Design B — 2026-Nov-26

Read the active Fase 2 design freeze sections 8–9 and the Controlled Planning Revision checkpoint first. GitHub-first; use the persistent worktree with git pull; only existing RO_SO clone for native rollback.

## Evidence from Feri
- d9aa0c3: FASE2_PP1_DESIGN_B_PURE_PASS, six groups including whole BoM, Max, cumulative pre-PP1 sales and SO-first.
- 3b27e1b: FASE2_PP1_NATIVE_SOURCES_ROLLBACK_PASS. SKU11999 / BoM7 / Max14: native ordinary RO4 + RO Paket component8, then native confirmed SO5. MO1 projection14, SO5/Paket8/ordinary1, ordinary shortage3. Draft excluded, original RO/Paket unchanged, no PP1/DO and fixture rollback.
- b8d5524: FASE2_PP1_REVIEW_REFRESH_ROLLBACK_PASS. Shared date-slot transaction lock, stale review rejected after SO confirmation, fresh canonical digest accepted; same-transaction test, not concurrent-session stress proof.
- Storage expanded per operator: root ext4 23G, 12G available, 45% used. Shared Odoo PID873 still has original clone connection. Owner rejected extra PostgreSQL cluster setup; DO NOT run prepare_fase2_isolated_gui_database.sh. Defer visual GUI until integrated UAT; no change to main service or Fase1. Existing clone is sufficient for shell rollback.

## Next gate (source committed, not tested)
- Native MO1 proposals from locked fresh review, deterministic date origin, real native MOs with canonical batch-line link in temporary rollback-only test. Additional SO-only SKU10042, expected BoM250 and MO1 250, mixed SKU11999 MO1 14. Run script/run_fase2_pp1_native_mo1_payload_rollback.sh; target FASE2_PP1_NATIVE_MO1_PAYLOAD_ROLLBACK_PASS.
- Deliberately no operational Production OK action, no legacy recipient allocation and no persisted batch. Legacy models assume RO-based output conservation; need proper immutable Design B snapshot with SO and original RO provenance, and downstream gates before enabling release. A temporary incomplete preproduction batch is ONLY a rolled-back native linkage fixture.
- Still open: settings/cutoff, actual native release and staged refresh, full SO Paket and PCK requirements, frozen BoM identity, per-store shortage decision, concurrency, cumulative post-PP1 forecast and SO-only PP2, final packing ledger. No deploy, no schema upgrade and no main merge.
