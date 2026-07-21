#!/bin/bash
# Track A compose override + nginx test/reload. Rollback on nginx -t failure.
set -euo pipefail

BK=$(cat /tmp/track_a_bk_path.txt)

sudo tee /var/azuracast/docker-compose.override.yml >/dev/null <<'EOF'
services:
  web:
    volumes:
      - /opt/orai-radio-command-center/deploy/azuracast-nginx/orai-public-vhosts.conf:/etc/nginx/conf.d/orai-public-vhosts.conf:ro
      - /opt/orai-radio-command-center/static/app-config.json:/var/azuracast/www_tmp/orai-app-config.json:ro
    networks:
      - default
      - neena-network

networks:
  neena-network:
    external: true
    name: neena-network
EOF

sudo cp -a /var/azuracast/docker-compose.override.yml "$BK/docker-compose.override.yml.applied"

echo "=== COMPOSE UP ==="
cd /var/azuracast
sudo docker compose up -d

echo "=== WAIT FOR AZURACAST ==="
sleep 8
sudo docker ps --format 'table {{.Names}}\t{{.Status}}' | head -10

echo "=== NETWORK CHECK ==="
sudo docker inspect azuracast --format '{{json .NetworkSettings.Networks}}'
sudo docker exec azuracast getent hosts neena-backend || {
  echo "neena-backend resolve FAILED"
  exit 1
}

echo "=== NGINX TEST ==="
if ! sudo docker exec azuracast nginx -t; then
  echo "NGINX_TEST_FAILED — initiating rollback"
  sudo mv /var/azuracast/docker-compose.override.yml /var/azuracast/docker-compose.override.yml.failed
  cd /var/azuracast
  sudo docker compose up -d
  sudo docker network disconnect neena-network azuracast 2>/dev/null || true
  sudo cp -a "$BK/acme_data/default.crt" /var/lib/docker/volumes/azuracast_acme/_data/default.crt 2>/dev/null || true
  sudo cp -a "$BK/acme_data/default.key" /var/lib/docker/volumes/azuracast_acme/_data/default.key 2>/dev/null || true
  sudo docker exec azuracast nginx -s reload 2>/dev/null || true
  echo "ROLLBACK_DONE_AFTER_NGINX_T_FAIL"
  exit 1
fi

sudo docker exec azuracast nginx -s reload
echo "NGINX_RELOAD_OK"
