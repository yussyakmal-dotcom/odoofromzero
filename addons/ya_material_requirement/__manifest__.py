{
    'name': 'YA Material Requirement - MO to CDC (Read Only)',
    'version': '19.0.3.0.0',
    'category': 'Manufacturing',
    'summary': 'Read-only MO component shortages by kitchen and shared CDC stock',
    'depends': ['ya_store_ro', 'mrp', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/material_requirement_views.xml',
        'views/material_requirement_batch_views.xml',
        'report/cdc_picking_list_report.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
