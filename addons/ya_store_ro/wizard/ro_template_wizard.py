"""Phase 1 RO: download a store-specific XLSX from one Published kitchen plan.

No RO documents, order quantities, MO, stock moves, or accounting side effects.
"""
import base64
from io import BytesIO

from odoo import fields, models, _
from odoo.exceptions import UserError

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
except ImportError:
    Workbook = None


class YaStoreRoTemplate(models.TransientModel):
    _name = 'ya.store.ro.template'
    _description = 'YA Store Replenishment Order XLSX Template'

    planning_id = fields.Many2one(
        'ya.production.planning', string='Published Planning',
        required=True, domain=[('state', '=', 'published')],
    )
    store_warehouse_id = fields.Many2one(
        'stock.warehouse', string='Toko / Store Warehouse', required=True,
    )
    file = fields.Binary(string='Download RO Template', readonly=True,
                         attachment=False)
    filename = fields.Char(readonly=True)
    line_count = fields.Integer(readonly=True)
    state = fields.Selection(
        [('choose', 'Choose Planning'), ('ready', 'Ready to Download')],
        default='choose', required=True,
    )

    def action_generate_template(self):
        self.ensure_one()
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Only a Manufacturing Manager can generate RO templates at this stage.'))
        if not Workbook:
            raise UserError(_('openpyxl is missing from the Odoo Python environment.'))

        plan = self.planning_id
        # Never use a Draft, even if the wizard was opened before publication changed.
        if not plan or plan.state != 'published':
            raise UserError(_('Choose a Published Planning document.'))
        if not self.store_warehouse_id or not self.store_warehouse_id.active:
            raise UserError(_('Choose an active store warehouse.'))
        if plan.company_id and self.store_warehouse_id.company_id != plan.company_id:
            raise UserError(_('Store and Planning must belong to the same company.'))

        lines = plan.line_ids.filtered(lambda r: r.max_capacity > 0).sorted(
            key=lambda r: (r.reference or '', r.id)
        )
        if not lines:
            raise UserError(_('Published Planning has no SKU with Max greater than zero.'))

        # Each template is tied to ONE store, ONE kitchen and ONE delivery slot.
        # The eventual RO importer must validate all information on the info sheet
        # against the Published Planning and must not trust editable cells alone.
        wb = Workbook()
        info = wb.active
        info.title = 'info'
        facts = [
            ('Field', 'Value'),
            ('Template Type', 'YA_STORE_RO_V1'),
            ('Planning ID', plan.id),
            ('Delivery Date', fields.Date.to_string(plan.delivery_date)),
            ('Slot', plan.slot),
            ('Kitchen Code', plan.kitchen_code),
            ('Store Warehouse ID', self.store_warehouse_id.id),
            ('Store Code', self.store_warehouse_id.code or ''),
            ('Store Name', self.store_warehouse_id.name),
            ('Instructions', 'Fill Qty Pesan as a nonnegative whole number; no BoM rounding per store.'),
        ]
        for row in facts:
            info.append(row)
        info.column_dimensions['A'].width = 27
        info.column_dimensions['B'].width = 88

        sheet = wb.create_sheet('RO')
        sheet.append(['Reference', 'Nama Produk', 'Qty Pesan'])
        for line in lines:
            sheet.append([line.reference, line.product_id.name, None])
            # Keep exported product codes and names literal text even if they
            # start with characters that spreadsheet engines interpret as formulas.
            for col in (1, 2):
                sheet.cell(row=sheet.max_row, column=col).data_type = 's'
        sheet.freeze_panes = 'C2'
        sheet.auto_filter.ref = 'A1:C%s' % sheet.max_row
        for col, width in {'A': 23, 'B': 65, 'C': 19}.items():
            sheet.column_dimensions[col].width = width
        for ws in (info, sheet):
            for cell in ws[1]:
                cell.font = Font(bold=True, color='FFFFFF')
                cell.fill = PatternFill(fill_type='solid', fgColor='23415B')
                cell.alignment = Alignment(vertical='center')
            ws.row_dimensions[1].height = 22

        stream = BytesIO()
        try:
            wb.save(stream)
            content = stream.getvalue()
        finally:
            wb.close()
            stream.close()

        filename = 'RO_%s_%s_%s_%s.xlsx' % (
            fields.Date.to_string(plan.delivery_date).replace('-', ''),
            plan.slot, plan.kitchen_code,
            (self.store_warehouse_id.code or str(self.store_warehouse_id.id)).replace('/', '_'),
        )
        self.write({
            'file': base64.b64encode(content),
            'filename': filename,
            'line_count': len(lines),
            'state': 'ready',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }
