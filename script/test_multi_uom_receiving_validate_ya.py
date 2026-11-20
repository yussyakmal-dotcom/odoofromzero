"""Integration test Odoo 19 Receiving: action Validate + no backorder, always ROLLBACK.

HANYA database test; menggunakan CDC/IN/00001 jika masih assigned.
Membatalkan juga perubahan create_backorder, stock.quant, jurnal valuasi,
dan qty_received karena seluruh transaction di-ROLLBACK.
"""
from odoo.tools.float_utils import float_compare


def main():
    print("DATABASE:", env.cr.dbname)
    print("MODE: INTEGRATION VALIDATE TEST, ALL ROLLBACK")
    if env.cr.dbname != "erp-yussyakmal-integer-test":
        raise RuntimeError("STOP: bukan database test")

    try:
        picking = env["stock.picking"].sudo().search(
            [("name", "=", "CDC/IN/00001")], limit=1
        )
        if not picking or picking.state != "assigned":
            raise RuntimeError("Receipt bukan Ready; jangan mengubah pengujian lain")
        if picking.ya_receipt_unit_line_ids:
            raise RuntimeError("Sudah ada baris fisik tersimpan; hentikan tes")
        moves = picking.move_ids.sorted("id")
        if len(moves) != 2 or any(m.product_id.default_code != "10164" for m in moves):
            raise RuntimeError("Receipt bukan P00009 / SKU 10164 sesuai audit")
        first = moves.filtered(lambda m: m.product_uom_qty == 25000)
        second = moves.filtered(lambda m: m.product_uom_qty == 500)
        if len(first) != 1 or len(second) != 1:
            raise RuntimeError("Demand tidak cocok")
        if first.purchase_line_id.order_id.name != "P00009":
            raise RuntimeError("Sumber PO tidak cocok")

        Rule = env["ya.purchase.uom.rule"].sudo()
        kg = Rule.search([
            ("product_id", "=", first.product_id.id),
            ("purchase_label", "=", "Kg"),
        ], limit=1)
        gram = Rule.search([
            ("product_id", "=", first.product_id.id),
            ("purchase_label", "=", "Gram"),
        ], limit=1)
        if not kg or not gram or kg.factor != 1000 or gram.factor != 1:
            raise RuntimeError("Master konversi tidak sesuai")

        entries = env["ya.receipt.unit.line"].sudo().create([
            {"picking_id": picking.id, "move_id": first.id,
             "rule_id": kg.id, "quantity_units": 20},
            {"picking_id": picking.id, "move_id": second.id,
             "rule_id": gram.id, "quantity_units": 500},
        ])
        assert sum(entries.mapped("base_quantity")) == 20500
        print("PASS: physical qty 20 Kg + 500 Gram => 20500 Gram")

        old_policy = picking.picking_type_id.create_backorder
        picking.picking_type_id.sudo().write({"create_backorder": "never"})
        print("TEST ONLY backorder policy:", old_policy, "-> never")

        picking.action_ya_apply_receipt_units()
        first.invalidate_recordset(["quantity"])
        second.invalidate_recordset(["quantity"])
        assert first.quantity == 20000 and second.quantity == 500
        print("PASS: move quantities = 20000 and 500")

        result = picking.button_validate()
        if isinstance(result, dict) and result.get("res_model"):
            raise AssertionError("Validate returned wizard: %s" % result.get("res_model"))
        picking.invalidate_recordset(["state", "backorder_ids"])
        if picking.state != "done":
            raise AssertionError("Receipt did not finish: %s" % picking.state)
        if picking.backorder_ids:
            raise AssertionError("Unexpected backorder %s" % picking.backorder_ids.ids)
        print("PASS: receipt DONE, zero backorders")

        po_lines = first.purchase_line_id | second.purchase_line_id
        po_lines.invalidate_recordset(["qty_received"])
        expected = {first.purchase_line_id.id: 20000, second.purchase_line_id.id: 500}
        for line in po_lines:
            qty = line.qty_received
            print("PO LINE:", line.id, "qty_received:", qty)
            if float_compare(qty, expected[line.id], precision_rounding=1.0):
                raise AssertionError("Received qty mismatch")
        print("PASS: PO qty_received follows actual receipt")
        print("INTEGRATION_VALIDATE_OK: rolling back ALL changes")
    finally:
        env.cr.rollback()
        print("ROLLBACK_COMPLETE: no test receipt/stock/backorder persisted")


main()
