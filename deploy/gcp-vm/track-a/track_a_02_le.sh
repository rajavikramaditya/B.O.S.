#!/bin/bash
# Track A LE issuance — one attempt only. Stop on failure.
set -euo pipefail

BK=$(cat /tmp/track_a_bk_path.txt)
ACME=/var/lib/docker/volumes/azuracast_acme/_data
WR=$ACME/certbot-webroot

sudo mkdir -p "$WR/.well-known"
sudo ln -sfn "$ACME/challenges" "$WR/.well-known/acme-challenge"
# Ensure challenges dir is writable for certbot via symlink
sudo mkdir -p "$ACME/challenges"
sudo chmod 755 "$ACME/challenges"

# Quick HTTP challenge path smoke (AzuraCast default_server)
echo -n "orai-le-probe" | sudo tee "$ACME/challenges/orai-probe.txt" >/dev/null
PROBE=$(curl -sS --max-time 8 "http://api.orairadio.in/.well-known/acme-challenge/orai-probe.txt" || true)
echo "ACME_PROBE=$PROBE"
if [ "$PROBE" != "orai-le-probe" ]; then
  echo "ACME challenge path not reachable via HTTP — abort before certbot"
  sudo rm -f "$ACME/challenges/orai-probe.txt"
  exit 1
fi
sudo rm -f "$ACME/challenges/orai-probe.txt"

echo "=== CERTBOT (single attempt) ==="
sudo certbot certonly --webroot \
  -w "$WR" \
  -d api.orairadio.in \
  -d stream.orairadio.in \
  -d config.orairadio.in \
  --email mahilkingdomorai@gmail.com \
  --agree-tos \
  --non-interactive \
  --keep-until-expiring

LE_LIVE=/etc/letsencrypt/live/api.orairadio.in
sudo test -f "$LE_LIVE/fullchain.pem"
sudo test -f "$LE_LIVE/privkey.pem"

# Backup current defaults then install LE into AzuraCast ACME paths
sudo cp -a "$ACME/default.crt" "$BK/default.crt.pre-le" 2>/dev/null || true
sudo cp -a "$ACME/default.key" "$BK/default.key.pre-le" 2>/dev/null || true
sudo cp "$LE_LIVE/fullchain.pem" "$ACME/default.crt"
sudo cp "$LE_LIVE/privkey.pem" "$ACME/default.key"
sudo chmod 644 "$ACME/default.crt"
sudo chmod 600 "$ACME/default.key"

echo "=== CERT INSTALLED ==="
sudo openssl x509 -in "$ACME/default.crt" -noout -subject -issuer -dates -ext subjectAltName 2>/dev/null | head -30
echo "LE_OK"
