{
    'name': 'YA Paket RO - Cross Kitchen Demand',
    'version': '19.0.1.3.0',
    'category': 'Inventory',
    'summary': 'Separate store requests for multi-kitchen package assemblies',
    'depends': ['ya_store_ro', 'ya_finished_packing_transfer', 'ya_packing_store_delivery'],
    'data': [
        'security/package_ro_groups.xml',
        'security/ir.model.access.csv',
        'views/package_ro_views.xml',
        'views/package_qty_correction_views.xml',
        'views/joint_slot_preview_views.xml',
        'views/joint_snapshot_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
