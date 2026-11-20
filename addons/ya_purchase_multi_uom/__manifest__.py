{
    "name": "YA Purchase Multi-UoM Rules",
    "version": "19.0.1.3.0",
    "category": "Purchases",
    "summary": "Per-SKU integer purchase rules and PO line conversion",
    "depends": ["purchase_stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/purchase_uom_rule_views.xml",
        "views/purchase_order_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
