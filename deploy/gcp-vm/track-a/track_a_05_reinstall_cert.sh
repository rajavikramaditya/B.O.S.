#!/bin/bash
set -euo pipefail
ACME=/var/lib/docker/volumes/azuracast_acme/_data
LE=/etc/letsencrypt/live/api.orairadio.in
BK=$(cat /tmp/track_a_bk_path.txt)

echo "=== ACME DIR ==="
sudo ls -la "$ACME"
echo "=== LE DIR ==="
sudo ls -la "$LE"

echo "=== BEFORE ==="
sudo openssl x509 -in "$ACME/default.crt" -noout -subject -issuer || true

sudo cp "$LE/fullchain.pem" "$ACME/default.crt"
sudo cp "$LE/privkey.pem" "$ACME/default.key"
sudo chmod 644 "$ACME/default.crt"
sudo chmod 600 "$ACME/default.key"

# Also copy into backup for reference
sudo cp "$LE/fullchain.pem" "$BK/le-fullchain.pem"
sudo cp "$LE/privkey.pem" "$BK/le-privkey.pem"

echo "=== AFTER HOST ==="
sudo openssl x509 -in "$ACME/default.crt" -noout -subject -issuer -ext subjectAltName 2>/dev/null | head -20

echo "=== AFTER CONTAINER ==="
sudo docker exec azuracast openssl x509 -in /var/azuracast/storage/acme/ssl.crt -noout -subject -issuer -ext subjectAltName 2>/dev/null | head -20

sudo docker exec azuracast nginx -t
sudo docker exec azuracast nginx -s reload
sleep 2

echo "=== LIVE TLS ==="
echo | openssl s_client -connect api.orairadio.in:443 -servername api.orairadio.in 2>/dev/null \
  | openssl x509 -noout -subject -issuer -ext subjectAltName 2>/dev/null | head -20
