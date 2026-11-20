{
    "name": "YA Purchase Discount",
    "version": "19.0.1.1.0",
    "category": "Purchases",
    "summary": "Exclusive line/global PO discounts in percent or currency amount",
    "depends": ["purchase", "ya_purchase_multi_uom"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/purchase_discount_wizard_views.xml",
        "views/purchase_discount_views.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}
