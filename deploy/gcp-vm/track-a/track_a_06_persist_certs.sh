#!/bin/bash
set -euo pipefail
BK=$(cat /tmp/track_a_bk_path.txt)
LE=/etc/letsencrypt/live/api.orairadio.in
CERTDIR=/opt/orai-radio-command-center/certs

sudo mkdir -p "$CERTDIR"
sudo cp "$LE/fullchain.pem" "$CERTDIR/fullchain.pem"
sudo cp "$LE/privkey.pem" "$CERTDIR/privkey.pem"
sudo chmod 644 "$CERTDIR/fullchain.pem"
sudo chmod 600 "$CERTDIR/privkey.pem"

# Persist override with cert bind-mounts so recreate cannot restore self-signed
sudo tee /var/azuracast/docker-compose.override.yml >/dev/null <<'EOF'
services:
  web:
    volumes:
      - /opt/orai-radio-command-center/deploy/azuracast-nginx/orai-public-vhosts.conf:/etc/nginx/conf.d/orai-public-vhosts.conf:ro
      - /opt/orai-radio-command-center/static/app-config.json:/var/azuracast/www_tmp/orai-app-config.json:ro
      - /opt/orai-radio-command-center/certs/fullchain.pem:/var/azuracast/storage/acme/default.crt:ro
      - /opt/orai-radio-command-center/certs/privkey.pem:/var/azuracast/storage/acme/default.key:ro
    networks:
      - default
      - neena-network

networks:
  neena-network:
    external: true
    name: neena-network
EOF
sudo cp -a /var/azuracast/docker-compose.override.yml "$BK/docker-compose.override.yml.final"

# Certbot renew deploy hook — refresh stable cert files + nginx reload
sudo tee /etc/letsencrypt/renewal-hooks/deploy/orai-azuracast-reload.sh >/dev/null <<'HOOK'
#!/bin/bash
set -euo pipefail
DOMAIN=api.orairadio.in
cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" /opt/orai-radio-command-center/certs/fullchain.pem
cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" /opt/orai-radio-command-center/certs/privkey.pem
chmod 644 /opt/orai-radio-command-center/certs/fullchain.pem
chmod 600 /opt/orai-radio-command-center/certs/privkey.pem
docker exec azuracast nginx -t && docker exec azuracast nginx -s reload
HOOK
sudo chmod 755 /etc/letsencrypt/renewal-hooks/deploy/orai-azuracast-reload.sh

# Apply mounts with one recreate (owner accepted blip) so certs survive future restarts
cd /var/azuracast
sudo docker compose up -d
sleep 12
sudo docker exec azuracast getent hosts neena-backend
sudo docker exec azuracast openssl x509 -in /var/azuracast/storage/acme/ssl.crt -noout -subject -issuer 2>/dev/null | head -5
sudo docker exec azuracast nginx -t
sudo docker exec azuracast nginx -s reload || true
echo "CERT_PERSIST_OK"
