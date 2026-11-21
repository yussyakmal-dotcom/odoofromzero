"""Multi-line Scrap document reusing Odoo 19 standard stock.scrap flows."""
import base64
from io import BytesIO

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

try:
    from openpyxl import Workbook, load_workbook
except ImportError:
    Workbook = load_workbook = None


class YaScrapBatch(models.Model):
    _name = "ya.scrap.batch"
    _description = "YA Multi-SKU Scrap"
    _order = "id desc"

    name = fields.Char(default="New", required=True, copy=False, readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Done")], default="draft",
        required=True, copy=False, index=True
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    location_id = fields.Many2one(
        "stock.location", string="Source Location", required=True,
        domain="[('usage', '=', 'internal')]",
        check_company=True,
    )
    scrap_location_id = fields.Many2one(
        "stock.location", string="Scrap Destination", required=True,
        domain="[('usage', '=', 'inventory')]",
        check_company=True,
    )
    reason_tag_id = fields.Many2one(
        "stock.scrap.reason.tag", string="Scrap Reason", required=True
    )
    source_document = fields.Char(string="Source Document", required=True)
    line_ids = fields.One2many(
        "ya.scrap.batch.line", "batch_id", string="Products", copy=True
    )
    scrap_ids = fields.One2many(
        "stock.scrap", "ya_batch_id", string="Native Scrap Transactions",
        readonly=True,
    )
    scrap_count = fields.Integer(compute="_compute_scrap_count")
    import_file = fields.Binary(
        string="Import Excel (.xlsx)", attachment=False, copy=False
    )
    import_filename = fields.Char(copy=False)

    @api.depends("scrap_ids")
    def _compute_scrap_count(self):
        for rec in self:
            rec.scrap_count = len(rec.scrap_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "ya.scrap.batch"
                ) or "New"
        return super().create(vals_list)

    def write(self, vals):
        if any(batch.state == "done" for batch in self):
            raise UserError(_("Validated Scrap batches cannot be modified."))
        return super().write(vals)

    def unlink(self):
        if any(batch.state != "draft" for batch in self):
            raise UserError(_("Only draft Scrap batches can be deleted."))
        return super().unlink()

    def _validate_header_and_lines(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("This batch is already validated."))
        if not self.line_ids:
            raise UserError(_("Add at least one product."))
        if self.location_id.usage != "internal":
            raise UserError(_("Source must be an internal location."))
        if self.scrap_location_id.usage != "inventory":
            raise UserError(_("Scrap destination must be Inventory Loss."))
        for loc in (self.location_id, self.scrap_location_id):
            if loc.company_id and loc.company_id != self.company_id:
                raise UserError(_("Locations must belong to this company."))
        if not self.source_document.strip():
            raise UserError(_("Source Document is required."))
        for line in self.line_ids:
            if line.qty <= 0:
                raise UserError(_("Quantity must be greater than zero."))
            if not line.uom_id._has_common_reference(line.product_id.uom_id):
                raise UserError(_(
                    "UoM of %(sku)s is incompatible with the product."
                ) % {"sku": line.product_id.default_code or line.product_id.display_name})
            if line.product_id.type == "service":
                raise UserError(_("Services cannot be scrapped."))
            if line.product_id.company_id and line.product_id.company_id != self.company_id:
                raise UserError(_("Product belongs to another company."))

    def action_validate(self):
        for batch in self:
            batch._validate_header_and_lines()
            # One database transaction: if any native Scrap fails, the
            # whole batch is rolled back. Never post stock moves manually.
            with self.env.cr.savepoint():
                for line in batch.line_ids:
                    scrap = self.env["stock.scrap"].with_company(
                        batch.company_id
                    ).create({
                        "product_id": line.product_id.id,
                        "scrap_qty": line.qty,
                        "product_uom_id": line.uom_id.id,
                        "location_id": batch.location_id.id,
                        "scrap_location_id": batch.scrap_location_id.id,
                        "origin": batch.source_document,
                        "company_id": batch.company_id.id,
                        "scrap_reason_tag_ids": [(6, 0, [batch.reason_tag_id.id])],
                        "ya_batch_id": batch.id,
                    })
                    result = scrap.action_validate()
                    if scrap.state != "done":
                        raise UserError(_(
                            "Odoo did not validate Scrap for %(sku)s. Result: %(result)s"
                        ) % {
                            "sku": line.product_id.display_name,
                            "result": str(result),
                        })
                super(YaScrapBatch, batch).write({"state": "done"})
        return True

    def action_view_scraps(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Native Scrap Transactions"),
            "res_model": "stock.scrap",
            "view_mode": "list,form",
            "domain": [("ya_batch_id", "=", self.id)],
            "context": {"create": False},
        }

    def action_download_template(self):
        self.ensure_one()
        if Workbook is None:
            raise UserError(_("Python package openpyxl is not installed."))
        wb = Workbook()
        ws = wb.active
        ws.title = "Scrap Lines"
        ws.append(["SKU", "Quantity", "UoM"])
        ws.append(["EXAMPLE_SKU", 5, "Pcs"])
        ws.freeze_panes = "A2"
        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 18
        ws.column_dimensions["C"].width = 18
        out = BytesIO()
        wb.save(out)
        attachment = self.env["ir.attachment"].create({
            "name": "ya_scrap_import_template.xlsx",
            "type": "binary",
            "datas": base64.b64encode(out.getvalue()),
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "res_model": self._name,
            "res_id": self.id,
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }

    def action_import_xlsx(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Import is allowed only in Draft."))
        if load_workbook is None:
            raise UserError(_("Python package openpyxl is not installed."))
        if not self.import_file:
            raise UserError(_("Select an Excel .xlsx file first."))
        if self.import_filename and not self.import_filename.lower().endswith(".xlsx"):
            raise UserError(_("Only .xlsx files are supported."))
        try:
            raw = base64.b64decode(self.import_file)
            book = load_workbook(BytesIO(raw), read_only=True, data_only=True)
            ws = book.active
            rows = ws.iter_rows(values_only=True)
            header = next(rows, None)
            if not header or [
                str(x or "").strip().casefold() for x in header[:3]
            ] != ["sku", "quantity", "uom"]:
                raise UserError(_("Excel columns must be: SKU, Quantity, UoM"))
            prepared = []
            product_model = self.env["product.product"].with_context(active_test=False)
            uom_model = self.env["uom.uom"]
            for row_num, row in enumerate(rows, start=2):
                if not any(cell is not None and str(cell).strip() for cell in row):
                    continue
                if len(prepared) >= 1000:
                    raise UserError(_("Maximum 1000 Excel rows per import."))
                sku = str(row[0] or "").strip()
                if not sku:
                    raise UserError(_("Row %s: SKU is empty.") % row_num)
                products = product_model.search([("default_code", "=", sku)], limit=2)
                if len(products) != 1:
                    raise UserError(_(
                        "Row %(row)s: SKU %(sku)s missing or not unique."
                    ) % {"row": row_num, "sku": sku})
                product = products[0]
                try:
                    quantity = float(row[1])
                except (ValueError, TypeError, IndexError):
                    raise UserError(_("Row %s: invalid Quantity.") % row_num)
                if not 0 < quantity < float("inf"):
                    raise UserError(_("Row %s: Quantity must be positive and finite.") % row_num)
                uom_name = str(row[2] or "").strip() if len(row) > 2 else ""
                if uom_name:
                    candidates = uom_model.search([("name", "=ilike", uom_name)], limit=2)
                    if len(candidates) != 1:
                        raise UserError(_(
                            "Row %(row)s: UoM %(uom)s missing or ambiguous."
                        ) % {"row": row_num, "uom": uom_name})
                    uom = candidates[0]
                else:
                    uom = product.uom_id
                if not uom._has_common_reference(product.uom_id):
                    raise UserError(_(
                        "Row %(row)s: incompatible UoM for SKU %(sku)s."
                    ) % {"row": row_num, "sku": sku})
                prepared.append((0, 0, {
                    "product_id": product.id,
                    "qty": quantity,
                    "uom_id": uom.id,
                }))
            book.close()
        except UserError:
            raise
        except Exception as exc:
            raise UserError(_("Cannot read Excel: %s") % str(exc)) from exc
        if not prepared:
            raise UserError(_("Excel contains no product rows."))
        self.write({"line_ids": prepared, "import_file": False, "import_filename": False})
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }


class YaScrapBatchLine(models.Model):
    _name = "ya.scrap.batch.line"
    _description = "YA Multi-SKU Scrap Line"
    _order = "id"

    batch_id = fields.Many2one(
        "ya.scrap.batch", required=True, ondelete="cascade", index=True
    )
    product_id = fields.Many2one(
        "product.product", required=True, domain="[('type', '!=', 'service')]"
    )
    qty = fields.Float(string="Quantity", required=True, default=1.0)
    uom_id = fields.Many2one("uom.uom", string="UoM", required=True)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id

    @api.constrains("qty")
    def _check_qty(self):
        for rec in self:
            if rec.qty <= 0:
                raise ValidationError(_("Scrap quantity must be positive."))

    @api.model_create_multi
    def create(self, vals_list):
        batches = self.env["ya.scrap.batch"].browse([
            vals["batch_id"] for vals in vals_list if vals.get("batch_id")
        ])
        if any(batch.state != "draft" for batch in batches):
            raise UserError(_("Cannot add lines to a validated Scrap batch."))
        return super().create(vals_list)

    def write(self, vals):
        if any(line.batch_id.state != "draft" for line in self):
            raise UserError(_("Validated Scrap lines cannot be edited."))
        if vals.get("batch_id"):
            target = self.env["ya.scrap.batch"].browse(vals["batch_id"])
            if target.state != "draft":
                raise UserError(_("Cannot move lines into a validated batch."))
        return super().write(vals)

    def unlink(self):
        if any(line.batch_id.state != "draft" for line in self):
            raise UserError(_("Validated Scrap lines cannot be removed."))
        return super().unlink()


class StockScrap(models.Model):
    _inherit = "stock.scrap"

    ya_batch_id = fields.Many2one(
        "ya.scrap.batch", string="Multi-SKU Scrap Batch",
        readonly=True, index=True, copy=False, ondelete="restrict"
    )
