{
    "name": "YA Purchase, Receipt and Vendor Bill Reports",
    "version": "19.0.0.1.0",
    "category": "Purchases",
    "summary": "Print physical purchasing units while retaining native Odoo accounting",
    "depends": ["purchase_stock", "account", "ya_purchase_multi_uom",
                "ya_multi_uom_receiving", "ya_purchase_discount"],
    "data": [
        "views/report_purchase.xml",
        "views/report_receipt.xml",
        "views/report_vendor_bill.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
