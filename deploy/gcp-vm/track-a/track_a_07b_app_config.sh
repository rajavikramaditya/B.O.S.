#!/bin/bash
set -euo pipefail

sudo docker exec -i neena-backend python - <<'PY'
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
    print(f"updated {k}={v}")

cfg = db.get_app_config()
print("RESULT", {k: cfg.get(k) for k in updates})
PY

echo "=== LOCAL ==="
curl -sS --max-time 10 http://127.0.0.1:8080/api/public/app-config
echo
echo "=== PUBLIC HTTPS ==="
curl -sS --max-time 15 https://api.orairadio.in/api/public/app-config
echo
