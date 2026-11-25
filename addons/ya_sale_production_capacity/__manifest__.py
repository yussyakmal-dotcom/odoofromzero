{
    'name': 'YA Sales Order - Production Capacity',
    'version': '19.0.1.0.1',
    'category': 'Manufacturing',
    'summary': 'Separate YA production SO entry from standard Odoo Sales Orders',
    'depends': ['sale_stock', 'ya_workflow_navigation', 'ya_package_store_ro'],
    'data': [
        'views/ya_sale_order_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
