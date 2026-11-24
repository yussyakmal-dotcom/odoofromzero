"""Route ordinary Packing consolidation to the single joint preview if Paket RO exist.

No extra user-facing block, no changes to ordinary RO-only slots. Existing
working action stays owned by ya_store_ro for all ordinary-only deliveries.
"""
from odoo import models
from odoo.addons.ya_store_ro.models.date_labels import parse_ymondd


class YaPackingPreviewPackageRoute(models.TransientModel):
    _inherit = "ya.packing.preview"

    def action_move_to_preproduction(self):
        self.ensure_one()
        date = parse_ymondd(self.delivery_date_yyyymmdd)
        has_package = self.env["ya.package.store.ro"].search_count([
            ("delivery_date", "=", date),
            ("slot", "=", self.slot),
            ("state", "=", "confirmed"),
        ])
        if not has_package:
            return super().action_move_to_preproduction()
        action = self.env.ref(
            "ya_package_store_ro.action_ya_package_joint_slot_preview"
        ).read()[0]
        action["context"] = {
            "default_delivery_date": str(date),
            "default_slot": self.slot,
        }
        return action
