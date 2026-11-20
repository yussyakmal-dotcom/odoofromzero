from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    ya_phone2 = fields.Char(string="Telepon 2", help="Nomor telepon alternatif mitra YA")
