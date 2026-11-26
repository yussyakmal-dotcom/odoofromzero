#!/usr/bin/env bash
# Run as Feri from ~/odoofromzero on odoo19c. Stop the temporary 8072
# foreground process first. No config edits, no new service, no DB cloning.
set -euo pipefail
umask 077
DB="erp-yussyakmal-mrp-test-RO_SO"
ACTIVE="/opt/odoo19/custom-addons"
CONF="/etc/odoo19.conf"
SERVICE="odoo19.service"
MODULES=(ya_production_planning ya_store_ro ya_material_requirement ya_finished_packing_transfer ya_packing_store_delivery ya_sale_production_capacity)
REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"
test "$(hostname -s)" = odoo19c
test "$(git branch --show-current)" = main
git merge-base --is-ancestor 96f75858fdd01329062c4e62cd137d2e384b30c4 HEAD
test -z "$(git status --porcelain --untracked-files=no)"
sudo -v
sudo systemctl is-active --quiet "$SERVICE"
if sudo ss -H -ltn 'sport = :8072' | grep -q .; then
  echo "STOP: close the temporary Odoo 8072 process (Ctrl+C) before deployment."
  exit 1
fi
ADDONS="$(sudo sed -n 's/^[[:space:]]*addons_path[[:space:]]*=[[:space:]]*//p' "$CONF" | tr -d '[:space:]')"
case ",$ADDONS," in
  *",$ACTIVE,"*) ;;
  *) echo "STOP: original custom-addons directory not found in Odoo config."; exit 1 ;;
esac
for m in "${MODULES[@]}"; do
  test -f "$REPO/addons/$m/__manifest__.py"
  sudo test -d "$ACTIVE/$m"
  if sudo test -L "$ACTIVE/$m"; then
    echo "STOP: active module $m is a symlink; inspect before replacing."
    exit 1
  fi
done
# No shared-runtime schema mismatch: the new Sales module must not be
# installed on other databases that are not being upgraded.
DBS="$(sudo -u postgres psql -X -v ON_ERROR_STOP=1 -At -d postgres -c "SELECT datname FROM pg_database WHERE datallowconn AND NOT datistemplate ORDER BY datname")"
while IFS= read -r other; do
  [ -n "$other" ] || continue
  [ "$other" != "$DB" ] || continue
  table="$(sudo -u postgres psql -X -v ON_ERROR_STOP=1 -At -d "$other" -c "SELECT to_regclass('public.ir_module_module')")"
  [ -n "$table" ] || continue
  state="$(sudo -u postgres psql -X -v ON_ERROR_STOP=1 -At -d "$other" -c "SELECT state FROM ir_module_module WHERE name='ya_sale_production_capacity'")"
  case "$state" in
    installed|"to upgrade"|"to install"|"to remove")
      echo "STOP: $other also uses Sales Fase 2 ($state). Do not change shared runtime without a compatibility decision."
      exit 1 ;;
  esac
done <<< "$DBS"
state="$(sudo -u postgres psql -X -v ON_ERROR_STOP=1 -At -d "$DB" -c "SELECT state FROM ir_module_module WHERE name='ya_sale_production_capacity'")"
test "$state" = installed
BACKUP="$HOME/odoo8069_before_integration_$(date +%Y%m%d_%H%M%S)"
mkdir -m 700 "$BACKUP"
git rev-parse HEAD > "$BACKUP/target-git-commit.txt"
printf '%s\n' b56e05646523a66d9e21bf218a05257356cec2d5 > "$BACKUP/previous-main-git-commit.txt"
echo "BACKUP_DIRECTORY=$BACKUP"
echo "Stopping the original Odoo service for the deployment window."
phase=backup
trap 'rc=$?; if [ "$rc" -ne 0 ]; then echo "DEPLOYMENT_STOPPED phase=$phase backup=$BACKUP"; if [ "$phase" = backup ]; then sudo systemctl start "$SERVICE" || true; else echo "Do not retry or restore blindly; preserve this backup and report the error."; fi; fi' EXIT
sudo systemctl stop "$SERVICE"
sudo tar -C "$ACTIVE" -cpf "$BACKUP/active-addons.tar" "${MODULES[@]}"
sudo tar -tf "$BACKUP/active-addons.tar" > "$BACKUP/active-addons-list.txt"
sudo -u postgres pg_dump -Fc "$DB" > "$BACKUP/RO_SO.dump"
pg_restore -l "$BACKUP/RO_SO.dump" > "$BACKUP/RO_SO-toc.txt"
echo "BACKUP_VERIFIED_LISTABLE"
phase=deploy
for m in "${MODULES[@]}"; do
  sudo cp -a "$REPO/addons/$m/." "$ACTIVE/$m/"
  sudo chown -R odoo19:odoo19 "$ACTIVE/$m"
done
phase=upgrade
sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin \
  -c "$CONF" -d "$DB" -u ya_sale_production_capacity \
  --stop-after-init --no-http --max-cron-threads=0
echo "RO_SO_UPGRADE_SUCCESS"
phase=start
sudo systemctl start "$SERVICE"
sudo systemctl is-active "$SERVICE"
echo "SINGLE_ODOO_8069_SOURCE_DEPLOYED"
echo "BACKUP_DIRECTORY=$BACKUP"
echo "Open http://192.168.202.197:8069/odoo?db=$DB and verify actual GUI."
echo "No upgrade of other databases. No new port or service. Cron remains subject to existing settings."
