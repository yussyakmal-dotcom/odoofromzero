{
    "name": "YA Integer Quantity Policy",
    "version": "19.0.1.0.0",
    "summary": "Validate whole-number transaction quantities across YA operations",
    "category": "Inventory",
    "depends": ["purchase_stock", "sale_stock", "point_of_sale", "mrp"],
    "data": ["views/integer_quantity_views.xml"],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
