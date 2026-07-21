#!/usr/bin/env bash
# Host agent: consume allowlisted self-heal requests from Neena backend.
# Install: /usr/local/bin/neena-self-heal.sh + timer (see neena-self-heal.timer).
set -euo pipefail

DIR="${NEENA_SELF_HEAL_DIR:-/var/lib/neena}"
REQ="${DIR}/self_heal_request.json"
LOG="${NEENA_SELF_HEAL_LOG:-/var/log/neena-self-heal.log}"
COMPOSE_DIR="${NEENA_COMPOSE_DIR:-/opt/orai-radio-command-center}"
COMPOSE_FILE="${NEENA_COMPOSE_FILE:-docker-compose.server.yml}"

mkdir -p "$DIR"
ts() { date -Is; }

log() { echo "$(ts) $*" >>"$LOG"; }

if [[ ! -f "$REQ" ]]; then
  exit 0
fi

# shellcheck disable=SC2002
ACTION=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('action',''))" "$REQ" 2>/dev/null || echo "")
if [[ -z "$ACTION" ]]; then
  log "invalid request file; removing"
  rm -f "$REQ"
  exit 0
fi

# Consume request first to avoid loops.
rm -f "$REQ"
log "executing action=$ACTION"

case "$ACTION" in
  gateway_restart)
    if systemctl restart radio-whatsapp-gateway; then
      log "gateway_restart ok"
    else
      log "gateway_restart FAILED"
      exit 1
    fi
    ;;
  backend_restart)
    cd "$COMPOSE_DIR"
    if sudo docker compose -f "$COMPOSE_FILE" restart neena-backend; then
      log "backend_restart ok"
    else
      log "backend_restart FAILED"
      exit 1
    fi
    ;;
  host_reboot)
    log "host_reboot requested — rebooting in 3s"
    sleep 3
    /sbin/reboot
    ;;
  *)
    log "refused unknown action=$ACTION"
    exit 1
    ;;
esac
