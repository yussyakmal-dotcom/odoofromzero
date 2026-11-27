{
    'name': 'YA MO to CDC Native Internal Transfers',
    'version': '19.0.6.1.1',
    'category': 'Manufacturing',
    'summary': 'Confirmed MO full raw material demand into standard Odoo Internal Transfers; native printing and validation',
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
