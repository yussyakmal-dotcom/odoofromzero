{
    'name': 'YA Workflow Navigation',
    'version': '19.0.1.0.1',
    'category': 'Manufacturing',
    'summary': 'Group production menus into before, during and after production',
    'depends': [
        'ya_production_planning',
        'ya_store_ro',
        'ya_material_requirement',
        'ya_finished_packing_transfer',
    ],
    'data': ['views/workflow_navigation_menus.xml'],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
