{
    'name': 'YA Sales Order - Production Capacity',
    'version': '19.0.1.1.3',
    'category': 'Manufacturing',
    'summary': 'Separate YA production SO entry from standard Odoo Sales Orders',
    'depends': ['sale_stock', 'ya_workflow_navigation', 'ya_package_store_ro'],
    'data': [
        'security/ir.model.access.csv',
        'views/ya_sale_order_views.xml',
        'views/ya_sale_confirm_wizard_views.xml',
        'views/ya_quotation_discount_wizard_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
