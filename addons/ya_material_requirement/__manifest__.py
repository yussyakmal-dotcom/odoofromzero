{
    'name': 'YA Material Requirement - MO to CDC & Physical Picking',
    'version': '19.0.4.1.0',
    'category': 'Manufacturing',
    'summary': 'MO material requirement, printable CDC list and physical quantity confirmation (no stock moves)',
    'depends': ['ya_store_ro', 'mrp', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/material_requirement_views.xml',
        'views/material_requirement_batch_views.xml',
        'views/cdc_pick_confirmation_views.xml',
        'report/cdc_picking_list_report.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
