#!/usr/bin/env bash
set -euo pipefail
test "$(hostname -s)" = odoo19c
cd /var/lib/ya-fase2-testing/source
test "$(git branch --show-current)" = fase2-controlled-planning-revision
python3 -m py_compile addons/ya_sale_production_capacity/models/pp1_mo1_proposals.py script/test_fase2_pp1_native_mo1_payload_rollback.py
ADDONS=$(sudo sed -n 's/^[[:space:]]*addons_path[[:space:]]*=[[:space:]]*//p' /etc/odoo19.conf)
test -n "$ADDONS"
sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
  /opt/odoo19/odoo/odoo-bin shell \
  -c /etc/odoo19.conf \
  -d erp-yussyakmal-mrp-test-RO_SO \
  --addons-path="/var/lib/ya-fase2-testing/addons,$ADDONS" \
  --no-http --max-cron-threads=0 \
  < script/test_fase2_pp1_native_mo1_payload_rollback.py
