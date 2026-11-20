{
    "name": "YA Multi-UoM Receiving",
    "version": "19.0.0.1.0",
    "category": "Inventory",
    "summary": "Capture physical receipt quantities in per-SKU units",
    "depends": ["purchase_stock", "ya_purchase_multi_uom", "ya_integer_quantity"],
    "data": [
        "security/ir.model.access.csv",
        "views/stock_picking_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
