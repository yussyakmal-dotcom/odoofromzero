#!/usr/bin/env bash
set -euo pipefail

DB="erp-yussyakmal-mrp-test-RO_SO"
ROOT="/var/lib/ya-fase2-testing"
CONFIG="/etc/odoo19.conf"

echo "=== SERVER ==="
hostname
test "$(hostname -s)" = "odoo19c"
test -r "$ROOT/source/addons/ya_sale_production_capacity/models/planning_revision.py"
echo "=== ISOLATED SOURCE ==="
git -C "$ROOT/source" rev-parse HEAD
echo "=== ODOO CONFIG (non-secret fields only) ==="
sudo grep -E '^[[:space:]]*(db_name|dbfilter|list_db|http_port|http_interface|workers|data_dir)[[:space:]]*=' "$CONFIG" || true
echo "=== POSTGRESQL CLUSTERS ==="
pg_lsclusters
echo "=== DISK CAPACITY ==="
df -h /var/lib
echo "=== CLONE DATABASE SIZE ==="
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d postgres -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database WHERE datname = '$DB';"
echo "=== CLONE CONNECTIONS ==="
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d postgres -c "SELECT application_name, state, count(*) FROM pg_stat_activity WHERE datname = '$DB' GROUP BY application_name, state;"
echo "=== LISTENING PORTS ==="
sudo ss -ltn
echo "FASE2_GUI_ENVIRONMENT_READONLY_AUDIT_COMPLETE"
