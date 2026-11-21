{
    "name": "YA Multi-SKU Scrap",
    "version": "19.0.1.0.0",
    "summary": "One Scrap document, one reason and source document, many products with Excel import",
    "category": "Inventory/Inventory",
    "depends": ["stock"],
    "data": [
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/scrap_batch_views.xml",
    ],
    "external_dependencies": {"python": ["openpyxl"]},
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
