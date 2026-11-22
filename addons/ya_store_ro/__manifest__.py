{
    'name': 'YA Store RO - Published Planning Template',
    'version': '19.0.3.0.0',
    'category': 'Inventory',
    'summary': 'Generate store RO Excel templates from Published Production Planning',
    'depends': ['ya_production_planning', 'stock'],
    'external_dependencies': {'python': ['openpyxl']},
    'data': [
        'security/ir.model.access.csv',
        'views/ro_template_wizard_views.xml',
        'views/ro_import_wizard_views.xml',
        'views/ro_documents_views.xml',
        'views/packing_preview_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
