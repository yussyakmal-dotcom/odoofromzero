#!/usr/bin/env bash
set -euo pipefail
test "$(hostname -s)" = "odoo19c"
DB="erp-yussyakmal-mrp-test-RO_SO"

echo "=== FILESYSTEMS AND BLOCK DEVICES ==="
df -hT
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
echo "=== LVM CAPACITY (read-only reports) ==="
sudo vgs -o vg_name,vg_size,vg_free
sudo lvs -o vg_name,lv_name,lv_size
echo "=== STORAGE USAGE (top-level directories only) ==="
sudo du -x -h --max-depth=1 /var/lib /var/log /opt 2>/dev/null | sort -h
echo "=== ODOO SERVICE ==="
systemctl show odoo19.service -p MainPID -p ActiveState
echo "=== CLONE CONNECTION DETAILS ==="
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d postgres -c "SELECT pid, application_name, state, backend_type FROM pg_stat_activity WHERE datname = '$DB';"
echo "=== ODOO APPLICATION PROCESS (no command-line secrets) ==="
while IFS= read -r app; do
    if [[ "$app" =~ ^odoo-([0-9]+)$ ]]; then
        ps -p "${BASH_REMATCH[1]}" -o pid,ppid,user,comm || true
    fi
done < <(sudo -u postgres psql -X -At -v ON_ERROR_STOP=1 -d postgres -c "SELECT DISTINCT application_name FROM pg_stat_activity WHERE datname = '$DB';")
echo "FASE2_STORAGE_ISOLATION_READONLY_AUDIT_COMPLETE"
