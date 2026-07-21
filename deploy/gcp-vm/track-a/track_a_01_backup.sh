#!/bin/bash
# Track A step 0+1: DNS check + backups. Stop on failure.
set -euo pipefail

echo "=== DNS CHECK ==="
for h in api.orairadio.in stream.orairadio.in config.orairadio.in; do
  out=$(getent hosts "$h" || true)
  echo "$h -> $out"
  echo "$out" | grep -q '35.244.15.150' || { echo "DNS FAIL for $h"; exit 1; }
done
echo "DNS_OK"

TS=$(date +%Y%m%d%H%M%S)
BK=/var/azuracast/backups/track-a-$TS
sudo mkdir -p "$BK"

sudo cp -a /var/azuracast/docker-compose.yml "$BK/docker-compose.yml"
sudo cp -a /var/azuracast/.env "$BK/env"
sudo cp -a /var/azuracast/azuracast.env "$BK/azuracast.env"
sudo cp -a /var/azuracast/docker-compose.override.yml "$BK/docker-compose.override.yml" 2>/dev/null || true

sudo docker exec azuracast nginx -T 2>&1 | sudo tee "$BK/nginx-T.before.txt" >/dev/null
sudo docker exec azuracast cat /etc/nginx/sites-available/default.vhost | sudo tee "$BK/default.vhost.before" >/dev/null

sudo cp -a /var/lib/docker/volumes/azuracast_acme/_data "$BK/acme_data"

sudo docker inspect azuracast --format '{{json .NetworkSettings.Networks}}' | sudo tee "$BK/azuracast-networks.before.json" >/dev/null
sudo docker inspect neena-backend --format '{{json .NetworkSettings.Networks}}' | sudo tee "$BK/neena-backend-networks.before.json" >/dev/null

curl -sS --max-time 8 http://127.0.0.1:8080/api/public/app-config | sudo tee "$BK/app-config.before.json" >/dev/null || true

echo "BK=$BK"
sudo ls -la "$BK"
echo "$BK" | sudo tee /tmp/track_a_bk_path.txt >/dev/null
