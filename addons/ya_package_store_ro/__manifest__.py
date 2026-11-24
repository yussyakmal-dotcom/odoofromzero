{
    'name': 'YA Paket RO - Cross Kitchen Demand',
    'version': '19.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Separate store requests for multi-kitchen package assemblies',
    'depends': ['ya_store_ro'],
    'data': [
        'security/ir.model.access.csv',
        'views/package_ro_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
