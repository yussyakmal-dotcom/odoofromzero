#!/usr/bin/env bash
# Create an isolated GUI-test copy, not a replacement for the owner's GUI backup.
# No Odoo HTTP process is launched. Never modify the original cluster/database.
set -euo pipefail
test "$(hostname -s)" = odoo19c
DB=erp-yussyakmal-mrp-test-RO_SO
CLUSTER=yafase2uat
SRC_PORT=5432
DST_PORT=55432
SOCKET=/var/run/postgresql
ROOT=/var/lib/ya-fase2-uat
REPO=/var/lib/ya-fase2-testing/source
CONFIG=/etc/odoo19.conf
PG_BIN=/usr/lib/postgresql/16/bin
test "$(git -C "$REPO" branch --show-current)" = fase2-controlled-planning-revision
test -r "$REPO/addons/ya_sale_production_capacity/models/planning_revision.py"
test "$(df -Pk /var/lib | awk 'NR==2 {print $4}')" -gt 4194304
if pg_lsclusters --no-header | awk -v p="$DST_PORT" -v c="$CLUSTER" '$3==p || $2==c {found=1} END {exit !found}'; then
    echo STOP_TARGET_CLUSTER_OR_PORT_ALREADY_EXISTS
    exit 1
fi
test ! -e "$ROOT"
test ! -e "/etc/postgresql/16/$CLUSTER"
test ! -e "/var/lib/postgresql/16/$CLUSTER"
test ! -e "$SOCKET/.s.PGSQL.$DST_PORT"
if ss -H -ltn "sport = :$DST_PORT" | grep -q .; then
    echo STOP_TARGET_PORT_IN_USE
    exit 1
fi
src() {
    sudo -u postgres env PGOPTIONS="-c default_transaction_read_only=on" "$PG_BIN/psql" -X -v ON_ERROR_STOP=1 -h "$SOCKET" -p "$SRC_PORT" "$@"
}
dst() {
    sudo -u postgres "$PG_BIN/psql" -X -v ON_ERROR_STOP=1 -h "$SOCKET" -p "$DST_PORT" "$@"
}
test "$(src -At -d postgres -c "SELECT current_setting('data_directory')")" = /var/lib/postgresql/16/main
meta=$(src -At -F '|' -d postgres -c "SELECT pg_encoding_to_char(encoding), datcollate, datctype, datlocprovider FROM pg_database WHERE datname='$DB'")
IFS='|' read -r encoding collate ctype provider <<< "$meta"
test "$encoding" = UTF8
test "$provider" = c
test -n "$collate"
test -n "$ctype"
test "$(src -At -d "$DB" -c "SELECT count(*) FROM ir_module_module WHERE state='installed' AND name IN ('ya_production_planning','ya_sale_production_capacity')")" = 2
test "$(src -At -d "$DB" -c "SELECT (to_regclass('ya_planning_revision_audit') IS NOT NULL)::int")" = 1
DATA_DIR=$(sudo -H -u odoo19 env PYTHONPATH=/opt/odoo19/odoo /opt/odoo19/venv/bin/python3 -c 'from odoo.tools import config; config.parse_config(["-c", "/etc/odoo19.conf", "--no-http"]); print(config["data_dir"])')
test -n "$DATA_DIR"
test "${DATA_DIR:0:1}" = /
SOURCE_FS="$DATA_DIR/filestore/$DB"
attachment_count=$(src -At -d "$DB" -c "SELECT count(*) FROM ir_attachment WHERE store_fname IS NOT NULL AND store_fname <> ''")
echo "SOURCE_FILESTORE_ATTACHMENT_COUNT=$attachment_count"
if test "$attachment_count" -gt 0; then
    sudo -u odoo19 test -d "$SOURCE_FS"
fi
echo "SOURCE_PREFLIGHT_PASS"
echo "Creating NEW PostgreSQL cluster $CLUSTER, socket port $DST_PORT (no TCP)."
sudo pg_createcluster --port="$DST_PORT" --start-conf=manual -o "listen_addresses=''" 16 "$CLUSTER"
sudo pg_ctlcluster 16 "$CLUSTER" start
test "$(dst -At -d postgres -c "SELECT current_setting('data_directory')")" = "/var/lib/postgresql/16/$CLUSTER"
test "$(dst -At -d postgres -c "SHOW port")" = "$DST_PORT"
test -z "$(dst -At -d postgres -c "SHOW listen_addresses")"
dst -d postgres -c "CREATE ROLE odoo19 LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE"
sudo -u postgres "$PG_BIN/createdb" -h "$SOCKET" -p "$DST_PORT" --owner=odoo19 --template=template0 --encoding="$encoding" --lc-collate="$collate" --lc-ctype="$ctype" "$DB"
# Streaming logical copy. Source transaction is read-only; no dump file in repo.
sudo -u postgres env PGOPTIONS="-c default_transaction_read_only=on" "$PG_BIN/pg_dump" -h "$SOCKET" -p "$SRC_PORT" --format=custom "$DB" |
    sudo -u postgres "$PG_BIN/pg_restore" -h "$SOCKET" -p "$DST_PORT" --dbname="$DB" --role=odoo19 --no-owner --no-acl --no-tablespaces --exit-on-error --single-transaction
echo "ISOLATED_DATABASE_COPY_PASS"
sudo install -d -m 700 -o odoo19 -g "$(id -gn odoo19)" "$ROOT" "$ROOT/filestore" "$ROOT/filestore/$DB"
if sudo -u odoo19 test -d "$SOURCE_FS"; then
    sudo -u odoo19 cp -a "$SOURCE_FS/." "$ROOT/filestore/$DB/"
fi
# Confirm every restored database file reference is present in the isolated copy.
# Odoo's store_fname is a relative content-addressed path.
dst -At -d "$DB" -c "SELECT DISTINCT store_fname FROM ir_attachment WHERE store_fname IS NOT NULL AND store_fname <> ''" |
    sudo -u odoo19 /opt/odoo19/venv/bin/python3 -c '
import sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
missing=0
for line in sys.stdin:
    p=(root/line.rstrip("\n")).resolve()
    if not p.is_relative_to(root) or not p.is_file():
        missing+=1
print("MISSING_FILESTORE_REFERENCES:",missing)
assert missing==0
' "$ROOT/filestore/$DB"
test "$(sudo -u odoo19 "$PG_BIN/psql" -X -At -v ON_ERROR_STOP=1 -h "$SOCKET" -p "$DST_PORT" -d "$DB" -c "SELECT current_user")" = odoo19
dst -d "$DB" -c "SELECT name, state, latest_version FROM ir_module_module WHERE name IN ('ya_production_planning','ya_sale_production_capacity') ORDER BY name"
dst -d "$DB" -c "SELECT count(*) AS revision_audit_count FROM ya_planning_revision_audit"
pg_lsclusters
echo "FASE2_ISOLATED_DATABASE_COPY_PASS"
echo "HTTP_NOT_STARTED; NEUTRALIZATION_AND_REGISTRY_GATE_PENDING"
