{
    'name': 'YA Packing to Store Delivery',
    'version': '19.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Generate store delivery documents from RO allocations; receipt after dispatch',
    'depends': [
        'ya_workflow_navigation',
        'ya_finished_packing_transfer',
        'stock',
    ],
    'data': ['views/store_delivery_views.xml'],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
