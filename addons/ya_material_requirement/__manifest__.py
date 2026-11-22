{
    'name': 'YA Material Requirement - CDC Picking & Internal Transfer Draft',
    'version': '19.0.5.0.0',
    'category': 'Manufacturing',
    'summary': 'MO material requirement, CDC physical picking and native Odoo internal transfer draft',
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
