"""PP1 review contract, not a release action. No business document writes.

The preview is a coherent, slot-locked read; its digest must match a fresh
read at Produksi OK. Caller must keep the same transaction open for eventual
release. No native release is authorized by this helper alone.
"""
import hashlib
import json

from odoo import fields
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from .pp1_native_sources import DB, PP1SourceError, read_pp1_sources

ROW_KEYS = {
    "ordinary_ro_rows": ("ro_id", "line_id", "product_id"),
    "ro_package_kitchen_rows": ("ro_id", "line_id", "product_id"),
    "ro_package_pck_rows": ("ro_id", "line_id", "product_id"),
    "so_ledger_rows": ("order_id", "planning_line_id", "ledger_id"),
    "sku_forecasts": ("planning_line_id", "product_id"),
}

def source_digest(facts):
    canonical = dict(facts)
    canonical["published_plan_ids"] = sorted(facts["published_plan_ids"])
    for key, columns in ROW_KEYS.items():
        canonical[key] = sorted(facts[key], key=lambda row: tuple(row[c] for c in columns))
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def read_locked_review(env, delivery_date, slot, company):
    if env.cr.dbname != DB:
        raise PP1SourceError("Wrong database")
    date = fields.Date.to_date(delivery_date)
    if not date or slot not in ("S1", "S2", "S3"):
        raise PP1SourceError("Invalid date/slot")
    lock_ro_slot(env.cr, date, slot)
    env.invalidate_all()
    facts = read_pp1_sources(env, date, slot, company)
    return {"facts": facts, "digest": source_digest(facts)}

def revalidate_review(env, delivery_date, slot, company, expected_digest):
    if not isinstance(expected_digest, str) or len(expected_digest) != 64:
        raise PP1SourceError("Missing valid PP1 review digest")
    fresh = read_locked_review(env, delivery_date, slot, company)
    if fresh["digest"] != expected_digest:
        raise PP1SourceError("PP1 source changed; refresh review before Produksi OK")
    return fresh
