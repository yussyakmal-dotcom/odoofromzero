{
    'name': 'YA Production Planning - XLSX Capacity',
    'version': '19.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Import production capacity by delivery date and slot from XLSX',
    'depends': ['mrp', 'stock'],
    'external_dependencies': {'python': ['openpyxl']},
    'data': [
        'security/ir.model.access.csv',
        'views/planning_views.xml',
        'views/import_wizard_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
