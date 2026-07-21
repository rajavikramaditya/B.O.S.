#!/bin/bash
set -euo pipefail
BK=/opt/orai-backups/sni-admin-20260712b
sudo mkdir -p "$BK"
sudo cp -a /opt/neena-admin-proxy/nginx.conf "$BK/nginx.conf.before" 2>/dev/null || true
sudo cp -a /var/azuracast/docker-compose.override.yml "$BK/" 2>/dev/null || true

# Fix corrupted .env line without dumping secrets
sudo python3 - <<'PY'
from pathlib import Path
p = Path("/var/azuracast/.env")
text = p.read_text(encoding="utf-8", errors="replace")
lines = text.splitlines()
out = []
seen_https = False
for line in lines:
    if line.startswith("NGINX_TIMEOUT=") and "AZURACAST_HTTPS_PORT=" in line:
        # split mangled: NGINX_TIMEOUT=1800AZURACAST_HTTPS_PORT=4443
        left, _, rest = line.partition("AZURACAST_HTTPS_PORT=")
        out.append(left)  # NGINX_TIMEOUT=1800
        if not seen_https:
            out.append("AZURACAST_HTTPS_PORT=4443")
            seen_https = True
        continue
    if line.startswith("AZURACAST_HTTPS_PORT="):
        if seen_https:
            continue
        out.append("AZURACAST_HTTPS_PORT=4443")
        seen_https = True
        continue
    out.append(line)
if not seen_https:
    out.append("AZURACAST_HTTPS_PORT=4443")
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("env_https_fixed")
PY

grep -E '^(NGINX_TIMEOUT|AZURACAST_HTTPS_PORT)=' /var/azuracast/.env

# Ensure nginx SNI config + LE certs
sudo cp /tmp/neena-admin-nginx.conf /opt/neena-admin-proxy/nginx.conf
sudo cp /opt/orai-radio-command-center/certs/fullchain.pem /opt/neena-admin-proxy/certs/neena.crt
sudo cp /opt/orai-radio-command-center/certs/privkey.pem /opt/neena-admin-proxy/certs/neena.key
sudo chmod 644 /opt/neena-admin-proxy/certs/neena.crt
sudo chmod 600 /opt/neena-admin-proxy/certs/neena.key

cd /var/azuracast
sudo docker compose up -d
sleep 12
sudo docker ps --format '{{.Names}} {{.Status}}' | grep -E 'azuracast|neena-admin' || true
echo 'LISTENERS:'
sudo ss -lntp | grep -E ':(443|4443|8443|80)\s' || true

# Validate + restart admin-proxy so it binds public 443 stream
sudo docker exec neena-admin-proxy nginx -t
sudo docker restart neena-admin-proxy
sleep 4
echo 'LISTENERS_AFTER_PROXY:'
sudo ss -lntp | grep -E ':(443|4443|8443|80)\s' || true

curl -sS -o /dev/null -w 'admin443=%{http_code}\n' --max-time 20 https://admin.orairadio.in/ || true
curl -sS -o /dev/null -w 'admin8443=%{http_code}\n' --max-time 15 https://admin.orairadio.in:8443/ || true
curl -sS -o /dev/null -w 'api=%{http_code}\n' --max-time 15 https://api.orairadio.in/api/public/app-config || true
curl -sS -o /dev/null -w 'config=%{http_code}\n' --max-time 15 https://config.orairadio.in/app-config.json || true
curl -sSI --max-time 15 https://stream.orairadio.in/listen/orai_radio/radio.mp3 2>/dev/null | head -3 || true
echo SNI_FIX_DONE
