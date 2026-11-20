"""DB TEST only: transient receipt CREATE/APPLY test, always ROLLBACK.

Tidak menekan Validate; tidak membuat stok atau backorder permanen.
"""
from odoo.exceptions import UserError


def main():
    print("DATABASE:", env.cr.dbname)
    if env.cr.dbname != "erp-yussyakmal-integer-test":
        raise RuntimeError("Pengujian hanya boleh di database test")
    if "ya.receipt.unit.line" not in env.registry.models:
        raise RuntimeError("Modul ya_multi_uom_receiving belum terinstal")

    try:
        picking = env["stock.picking"].sudo().search(
            [("name", "=", "CDC/IN/00001")], limit=1
        )
        if not picking or picking.state in ("done", "cancel"):
            raise RuntimeError("Receipt CDC/IN/00001 tidak tersedia / sudah selesai")
        if picking.ya_receipt_unit_line_ids:
            raise RuntimeError("Receipt sudah memiliki baris YA; jangan timpa data test")
        moves = picking.move_ids.sorted("id")
        if len(moves) != 2 or any(m.product_id.default_code != "10164" for m in moves):
            raise RuntimeError("Bentuk receipt tidak cocok dengan audit P00009")

        Rule = env["ya.purchase.uom.rule"].sudo()
        Line = env["ya.receipt.unit.line"].sudo()
        kg = Rule.search([
            ("product_id", "=", moves[0].product_id.id),
            ("purchase_label", "=", "Kg"),
        ], limit=1)
        gram = Rule.search([
            ("product_id", "=", moves[0].product_id.id),
            ("purchase_label", "=", "Gram"),
        ], limit=1)
        if not kg or not gram or kg.factor != 1000 or gram.factor != 1:
            raise RuntimeError("Aturan Kg/Gram tidak cocok")

        first = moves.filtered(lambda m: m.product_uom_qty == 25000)
        second = moves.filtered(lambda m: m.product_uom_qty == 500)
        if len(first) != 1 or len(second) != 1:
            raise RuntimeError("Demand move tidak sesuai audit")

        Line.create([
            {"picking_id": picking.id, "move_id": first.id,
             "rule_id": kg.id, "quantity_units": 20},
            {"picking_id": picking.id, "move_id": second.id,
             "rule_id": gram.id, "quantity_units": 500},
        ])
        assert sum(picking.ya_receipt_unit_line_ids.mapped("base_quantity")) == 20500
        print("PASS: dua satuan fisik menghasilkan 20500 Gram")
        picking.action_ya_apply_receipt_units()
        first.invalidate_recordset(["quantity", "move_line_ids"])
        second.invalidate_recordset(["quantity", "move_line_ids"])
        print("AFTER APPLY:", first.quantity, second.quantity)
        assert first.quantity == 20000 and second.quantity == 500
        print("PASS: stock.move.quantity mengikuti 20000 + 500 Gram")
        print("ORM_RECEIVING_TEST_OK: semua perubahan akan di-ROLLBACK")
    finally:
        env.cr.rollback()
        print("ROLLBACK_COMPLETE: tidak ada transaksi uji tersimpan")


main()
