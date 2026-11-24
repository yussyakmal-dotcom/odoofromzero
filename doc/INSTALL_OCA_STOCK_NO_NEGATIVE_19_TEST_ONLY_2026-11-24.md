# OCA stock_no_negative Odoo 19 — TEST ONLY deployment gate

**Scope:** dedicated database `erp-yussyakmal-mrp-test` only. Do not
install/update this module on production `erp-yussyakmal`, do not rewrite
native manufacturing MOs, do not restart the shared Odoo service blindly.
Both SUL/Stock stock adjustments on TEST are already committed: first
15 SKU PASS, last 2 SKU PASS, zero leftover negative internal/transit
storable quants verified at last adjustment commit.

OCA source verified from upstream 19.0 on 2026-11-24:
`OCA/stock-logistics-workflow` commit
`e7f9ad50bf698fc7c4c06d2500e3d8c4f124c4a1`,
`stock_no_negative` addon `19.0.1.0.1`, AGPL-3,
declared dependency **stock only**. This is native inventory-quant guard
and NOT a rewrite of MO Confirm/Produce All. It blocks a move/production
that causes a storable internal/transit quant to become negative unless
a product/category/location exception was set.

## Stage A: Source only — do NOT install, restart or modify database

Confirm path `/opt/odoo19/oca-addons` is writable by `odoo19`.
The clone directory and installed-addon symlink must not already exist.
Run separately; if a command fails STOP instead of overwriting anything.

```bash
cd ~/odoofromzero
git pull
test ! -e /opt/odoo19/oca-addons/stock-logistics-workflow
test ! -e /opt/odoo19/custom-addons/stock_no_negative

sudo -u odoo19 git clone --filter=blob:none --sparse -b 19.0 \
  https://github.com/OCA/stock-logistics-workflow.git \
  /opt/odoo19/oca-addons/stock-logistics-workflow

sudo -u odoo19 git -C /opt/odoo19/oca-addons/stock-logistics-workflow \
  sparse-checkout set stock_no_negative
sudo -u odoo19 git -C /opt/odoo19/oca-addons/stock-logistics-workflow \
  checkout --detach e7f9ad50bf698fc7c4c06d2500e3d8c4f124c4a1

sudo ln -s \
  /opt/odoo19/oca-addons/stock-logistics-workflow/stock_no_negative \
  /opt/odoo19/custom-addons/stock_no_negative

sudo -u odoo19 test -r \
  /opt/odoo19/custom-addons/stock_no_negative/__manifest__.py
sudo -u odoo19 git -C /opt/odoo19/oca-addons/stock-logistics-workflow rev-parse HEAD
```

Existing Odoo config has `/opt/odoo19/custom-addons` in
`addons_path`, so **do not modify /etc/odoo19.conf**. Staging files
does NOT install the module into any DB.

## Stage B: Read-only TEST database preflight

```bash
python3 -m py_compile \
  script/check_oca_stock_no_negative_install_ready_readonly_ya.py \
  script/test_oca_stock_no_negative_guard_rollback_ya.py

sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
  /opt/odoo19/odoo/odoo-bin shell \
  -c /etc/odoo19.conf \
  -d erp-yussyakmal-mrp-test --no-http \
  < script/check_oca_stock_no_negative_install_ready_readonly_ya.py
```

Expected final: `OCA_STOCK_NO_NEGATIVE_TEST_INSTALL_READINESS_PASS`
and `NO_DB_WRITES_NO_INSTALL_NO_RESTART`. Must not proceed if a
negative quant or incompatible addon manifest remains.

## Stage C: TEST DB installation (not performed yet)

Before Stage C, **Feri verifies a fresh, restorable backup of
`erp-yussyakmal-mrp-test` (DB plus associated filestore as appropriate)**,
confirms shared-service impact / TEST DB user activity, and explicitly
authorizes the test-only installation command. Prefer a maintenance
window when the TEST UI is idle. Odoo may load/reload the test registry
and acquire database locks. Nothing in this step is a production
module install, but the server has shared filesystem/service and MUST
not be restarted without checking all DBs served.

```bash
sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
  /opt/odoo19/odoo/odoo-bin \
  -c /etc/odoo19.conf \
  -d erp-yussyakmal-mrp-test \
  -i stock_no_negative \
  --stop-after-init --no-http \
  --workers=0
```

Do NOT run until Stage B outputs PASS + backup verified.
If installation fails, DO NOT blindly rerun or restart; inspect the
full error and restore TEST backup if DB was partially updated.

## Stage D: One narrow native guard verification, rollback only

After install, run (TEST only):
```bash
sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
  /opt/odoo19/odoo/odoo-bin shell \
  -c /etc/odoo19.conf \
  -d erp-yussyakmal-mrp-test --no-http \
  < script/test_oca_stock_no_negative_guard_rollback_ya.py
```

Expected `OCA_STOCK_NO_NEGATIVE_GUARD_ROLLBACK_PASS`.
This attempts ONE native untracked premix stock move from known zero
`SUL/Stock`, expects a negative-stock ValidationError, and then
explicitly rolls back. It does not re-run massive MO, RO or DO E2E.
If module installation succeeded but running shared Odoo UI remains
unaware of the addon, diagnose registry/service strategy; do NOT
restart shared service blindly. No production rollout is authorized.
