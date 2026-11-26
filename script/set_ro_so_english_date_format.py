"""Owner-approved one-time language date format update in RO_SO only.

Run using Odoo shell on the existing 8069 instance. No backup, restart,
module upgrade, stored business date changes or other database access.
"""
if env.cr.dbname != "erp-yussyakmal-mrp-test-RO_SO":
    raise RuntimeError("Wrong database: refusing to change language settings")

langs = env["res.lang"].sudo().search([
    ("active", "=", True),
    ("code", "=like", "en_%"),
])
if not langs:
    raise RuntimeError("No active English language found; no changes committed")

for lang in langs:
    print("BEFORE:", lang.code, lang.date_format)
    if lang.date_format != "%Y-%b-%d":
        lang.write({"date_format": "%Y-%b-%d"})
    print("AFTER:", lang.code, lang.date_format)

env.cr.commit()
print("DATABASE:", env.cr.dbname)
print("DATE_FORMAT_UPDATE_COMMITTED")
print("Sign out and sign in again, then hard refresh browser.")
