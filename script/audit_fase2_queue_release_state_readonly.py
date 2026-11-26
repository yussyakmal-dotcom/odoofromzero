"""Read-only diagnosis: native batch status vs PP1/PP2 queue."""
assert env.cr.dbname=="erp-yussyakmal-mrp-test-RO_SO"
Queue=env["ya.consolidation.timer.queue"].sudo()
Batch=env["ya.packing.batch"].sudo()
Final=env["ya.sale.mo2.finalization"].sudo()
print("DATABASE:",env.cr.dbname)
for q in Queue.search([],order="delivery_date desc,slot,stage"):
    bs=Batch.search([("delivery_date","=",q.delivery_date),("slot","=",q.slot)])
    fs=Final.search([("batch_id","in",bs.ids)])
    print("QUEUE:",q.delivery_date,q.slot,q.stage,q.state,"BATCHES:",
          [(b.id,b.state,bool(b.ya_pp1_design_b_snapshot)) for b in bs],
          "PP2:",[(f.id,bool(f.ya_pp2_design_b_snapshot)) for f in fs])
env.cr.rollback()
print("QUEUE_RELEASE_STATE_AUDIT_READ_ONLY_DONE")
