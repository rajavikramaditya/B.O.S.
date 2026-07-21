#!/bin/bash
# Update app_config via Neena container Python (localhost DB) — no public admin exposure.
set -euo pipefail

sudo docker exec neena-backend python - <<'PY'
import database as db

updates = {
    "api_base_url": "https://api.orairadio.in",
    "stream_url": "https://stream.orairadio.in/listen/orai_radio/radio.mp3",
    "backup_stream_url": "https://stream.orairadio.in/listen/orai_radio/radio.mp3",
    "config_version": "2",
    "force_refresh": "true",
}
for k, v in updates.items():
    db.update_app_config(k, v)
    print(f"updated {k}")

cfg = db.get_app_config()
for k in updates:
    print(f"{k}={cfg.get(k)!r}")
PY

echo "=== LOCAL ==="
curl -sS --max-time 10 http://127.0.0.1:8080/api/public/app-config
echo
echo "=== PUBLIC HTTPS ==="
curl -sS --max-time 15 https://api.orairadio.in/api/public/app-config
echo
echo "=== STREAM RECHECK ==="
curl -sS --max-time 12 -r 0-255 -o /tmp/stream2.bin -w 'HTTP=%{http_code} ctype=%{content_type} ssl=%{ssl_verify_result}\n' \
  https://stream.orairadio.in/listen/orai_radio/radio.mp3
echo "=== CONFIG JSON RECHECK ==="
curl -sS --max-time 10 -w '\nHTTP=%{http_code} ssl=%{ssl_verify_result}\n' https://config.orairadio.in/app-config.json
echo "=== ADMIN BLOCK RECHECK ==="
curl -sS --max-time 10 -o /dev/null -w 'HTTP=%{http_code}\n' https://api.orairadio.in/api/admin/app-config/stream_url
echo "=== 8080 ==="
ss -lntp | grep 8080 || true
curl -sS --max-time 5 http://35.244.15.150:8080/healthz && echo OPEN || echo PUBLIC_8080_UNREACHABLE_OK
