# Track A.1 — Permanent Command Center on `admin.orairadio.in`

**Status:** LIVE — SNI split (2026-07-12): public `:443` for `admin.orairadio.in` terminates on `neena-admin-proxy` (same stack as `:8443`). AzuraCast HTTPS is loopback `:4443` (`AZURACAST_HTTPS_PORT=4443`).  
**Preferred URL:** `https://admin.orairadio.in`  
**Fallback:** `https://admin.orairadio.in:8443`

## Why (Edge SSL footgun)

DNS A `admin` → VM was never enough. Serving CC through **AzuraCast public :443**
made Edge show `ERR_SSL_PROTOCOL_ERROR` while `:8443` (neena-admin-proxy) worked.
**Working fix:** SNI split — public `:443` terminates admin on neena-admin-proxy;
AzuraCast HTTPS moved to loopback `:4443`. Full symptom/fix: `project_history.md`
§ “admin.orairadio.in Edge ERR_SSL_PROTOCOL_ERROR”.

## Live facts (gcp-vm)

- LE cert `api.orairadio.in` SANs include `admin` — sync to:
  - `/opt/orai-radio-command-center/certs/{fullchain,privkey}.pem`
  - `/opt/neena-admin-proxy/certs/neena.{crt,key}`
- `/var/azuracast/.env`: `AZURACAST_HTTPS_PORT=4443` (do not leave public 443 on AzuraCast).
- Host nginx: `/opt/neena-admin-proxy/nginx.conf` (= repo `deploy/gcp-vm/nginx.conf`) — stream ssl_preread + `:8443` UI.
- AzuraCast vhosts listen **`4443 ssl`**: `deploy/azuracast-nginx/orai-public-vhosts.conf`.
- VM Neena `.env`: `COMMAND_CENTER_LOCAL_ONLY=false`, `ADMIN_AUTH_ENABLED=true`.
- Backups used: `/opt/orai-backups/pre-deploy-*`, `/opt/orai-backups/sni-admin-*`.

## Re-apply (owner-approved only)

```bash
BK=/var/azuracast/backups/admin-cc-$(date +%Y%m%d-%H%M%S)
sudo mkdir -p "$BK"
sudo cp -a /var/azuracast/docker-compose.override.yml "$BK/" 2>/dev/null || true

sudo chmod 644 /opt/orai-radio-command-center/deploy/azuracast-nginx/orai-public-vhosts.conf

# Only if SAN missing admin — expand then copy into /opt/.../certs/
# sudo certbot certonly --webroot -w /var/lib/docker/volumes/azuracast_acme/_data/challenges \
#   -d api.orairadio.in -d stream.orairadio.in -d config.orairadio.in -d admin.orairadio.in \
#   --expand --agree-tos --non-interactive
# sudo cp /etc/letsencrypt/live/api.orairadio.in/fullchain.pem /opt/orai-radio-command-center/certs/fullchain.pem
# sudo cp /etc/letsencrypt/live/api.orairadio.in/privkey.pem /opt/orai-radio-command-center/certs/privkey.pem

sudo tee /var/azuracast/docker-compose.override.yml >/dev/null <<'EOF'
services:
  web:
    volumes:
      - /opt/orai-radio-command-center/deploy/azuracast-nginx/orai-public-vhosts.conf:/etc/nginx/conf.d/orai-public-vhosts.conf:ro
      - /opt/orai-radio-command-center/static/app-config.json:/var/azuracast/www_tmp/orai-app-config.json:ro
      - /opt/orai-radio-command-center/certs/fullchain.pem:/var/azuracast/storage/acme/default.crt:ro
      - /opt/orai-radio-command-center/certs/privkey.pem:/var/azuracast/storage/acme/default.key:ro
      - /opt/orai-radio-command-center/frontend:/var/azuracast/www_tmp/orai-admin-frontend:ro
    networks:
      - default
      - neena-network

networks:
  neena-network:
    external: true
    name: neena-network
EOF

cd /var/azuracast
sudo docker compose up -d
sudo docker exec azuracast nginx -t
sudo docker exec azuracast nginx -s reload
```

## Verify

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://admin.orairadio.in/
curl -sS -o /dev/null -w '%{http_code}\n' https://admin.orairadio.in/healthz
curl -sS -o /dev/null -w '%{http_code}\n' https://admin.orairadio.in/api/neena/security-status
curl -sS -o /dev/null -w '%{http_code}\n' https://api.orairadio.in/api/neena/chat
# Expect: admin 200s; api private 404
```

**Browser:** `https://admin.orairadio.in` → owner phrase gate → unlock.  
If Edge shows `ERR_SSL_PROTOCOL_ERROR` on :443, use trusted fallback  
`https://admin.orairadio.in:8443` (same LE cert on `neena-admin-proxy`) or Incognito after nginx reload.

## Rollback

Restore `/opt/orai-backups/pre-deploy-*` app-code.tar + override; rebuild `neena-backend --no-deps`; AzuraCast `docker compose up -d`; nginx reload.  
Fallback UI: `https://35.244.15.150:8443`.
