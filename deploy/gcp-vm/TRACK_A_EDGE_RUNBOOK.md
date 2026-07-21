# Track A — Edge SSL + Reverse Proxy Execution Runbook

**Status:** READY FOR OWNER APPROVAL — **DO NOT EXECUTE** until owner explicitly says so.  
**Date prepared:** 2026-07-10  
**Scope:** VM edge only (`api` / `stream` / `config` hostnames). No mobile app. No Redis/Postgres restart. No public `:8080`.

---

## 0. Preconditions (owner before execution)

1. DNS A records (all → `35.244.15.150`):
   - `api.orairadio.in` — already verified
   - `stream.orairadio.in` — already verified
   - `config.orairadio.in` — **must be added** (not verified yet)
   - `admin.orairadio.in` — DNS ready (GoDaddy); edge cutover = [`TRACK_A_ADMIN_SUBDOMAIN.md`](./TRACK_A_ADMIN_SUBDOMAIN.md)
2. Owner confirms brief AzuraCast container recreate risk (Icecast may blip ~10–60s when applying compose override).
3. Owner confirms LE email for certbot registration (replace `OWNER_EMAIL` below).
4. Track B APK claim remains blocked until this runbook verifies green + phone test.

---

## 1. Current port ownership proof (verified 2026-07-10)

### Host listeners

| Bind | Process | Owner |
|------|---------|--------|
| `0.0.0.0:80` | `docker-proxy` | container **`azuracast`** |
| `0.0.0.0:443` | `docker-proxy` | container **`azuracast`** |
| `0.0.0.0:8000` | `docker-proxy` | container **`azuracast`** (Icecast/station) |
| `127.0.0.1:8080` | `docker-proxy` | container **`neena-backend`** (localhost only) |
| `0.0.0.0:8443` | host `nginx` | **`neena-admin-proxy`** |

### Docker ports (abbrev)

```
neena-backend       127.0.0.1:8080->8000/tcp
azuracast           0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp, ...station ports...
neena-redis         6379/tcp   (no host publish)
neena-postgres      5432/tcp   (no host publish)
```

### AzuraCast compose path

| Item | Path |
|------|------|
| Compose | `/var/azuracast/docker-compose.yml` |
| Env | `/var/azuracast/.env`, `/var/azuracast/azuracast.env` |
| Override today | **none** (`docker-compose.override.yml` missing) |
| Install helper | `/var/azuracast/docker.sh` |
| ACME volume (host) | `/var/lib/docker/volumes/azuracast_acme/_data` |
| ACME in container | `/var/azuracast/storage/acme/` |
| Current cert | self-signed `CN=localhost` (`ssl.crt` → `default.crt`) |

### Nginx include model (inside `azuracast`)

- `/etc/nginx/nginx.conf` includes `/etc/nginx/conf.d/*.conf` then `/etc/nginx/sites-enabled/*`
- `default.vhost` is `default_server` on 80/443; ends with:
  - `include /var/azuracast/stations/*/config/nginx.conf;` ← **stream `/listen/orai_radio` lives here**
  - `include /etc/nginx/azuracast.conf.d/*.conf;` ← **location snippets only** (inside default server)
- **Full extra `server{}` blocks must go in `/etc/nginx/conf.d/`** (not only azuracast.conf.d)

### Networks today

- `azuracast` → **`azuracast_default` only**
- `neena-backend` → **`neena-network` only**
- Therefore AzuraCast **cannot** resolve `neena-backend` until joined

### Live Neena app-config (localhost)

```json
{
  "stream_url": "http://35.244.15.150/listen/orai_radio/radio.mp3",
  "api_base_url": "http://35.244.15.150:8000",
  "backup_stream_url": "http://35.244.15.150/listen/orai_radio/radio.mp3"
}
```

Note: `api_base_url` port **8000** is wrong for Neena (Neena is 8080 localhost / container 8000). After edge works, update remote config to HTTPS domain URLs (separate owner-confirm step).

---

## 2. Exact files / paths to create or edit

| Purpose | Host path | Container mount |
|---------|-----------|-----------------|
| Compose override (networks + binds) | `/var/azuracast/docker-compose.override.yml` | n/a |
| Custom nginx vhosts | `/opt/orai-radio-command-center/deploy/azuracast-nginx/orai-public-vhosts.conf` | `/etc/nginx/conf.d/orai-public-vhosts.conf` |
| Static backup JSON | `/opt/orai-radio-command-center/static/app-config.json` | `/var/azuracast/www_tmp/orai-app-config.json` |
| LE cert material | `/var/lib/docker/volumes/azuracast_acme/_data/` | `/var/azuracast/storage/acme/` |
| Do **not** edit | `/var/azuracast/docker-compose.yml` (prefer override) | — |
| Do **not** edit | station `nginx.conf` under `/var/azuracast/stations/...` | stream stays via default include |

**Why override, not main compose:** AzuraCast updater may regenerate `docker-compose.yml`. Override is the supported persistence mechanism.

---

## 3. Exact backups (run first)

```bash
TS=$(date +%Y%m%d%H%M%S)
BK=/var/azuracast/backups/track-a-$TS
sudo mkdir -p "$BK"

# Compose / env
sudo cp -a /var/azuracast/docker-compose.yml "$BK/docker-compose.yml"
sudo cp -a /var/azuracast/.env "$BK/env"
sudo cp -a /var/azuracast/azuracast.env "$BK/azuracast.env"
# override may not exist yet
sudo cp -a /var/azuracast/docker-compose.override.yml "$BK/docker-compose.override.yml" 2>/dev/null || true

# Live nginx dump + default vhost
sudo docker exec azuracast nginx -T > "$BK/nginx-T.before.txt" 2>&1
sudo docker exec azuracast cat /etc/nginx/sites-available/default.vhost > "$BK/default.vhost.before"

# ACME / certs
sudo cp -a /var/lib/docker/volumes/azuracast_acme/_data "$BK/acme_data"

# Network membership proof
sudo docker inspect azuracast --format '{{json .NetworkSettings.Networks}}' > "$BK/azuracast-networks.before.json"
sudo docker inspect neena-backend --format '{{json .NetworkSettings.Networks}}' > "$BK/neena-backend-networks.before.json"

# Neena app_config snapshot
curl -sS http://127.0.0.1:8080/api/public/app-config > "$BK/app-config.before.json"

echo "Backups at $BK"
ls -la "$BK"
```

Backup directory example: `/var/azuracast/backups/track-a-20260710120000/`

---

## 4. Exact config snippets

### 4a. Host static JSON — `/opt/orai-radio-command-center/static/app-config.json`

```json
{
  "config_version": 2,
  "api_base_url": "https://api.orairadio.in",
  "stream_url": "https://stream.orairadio.in/listen/orai_radio/radio.mp3",
  "backup_stream_url": "https://stream.orairadio.in/listen/orai_radio/radio.mp3",
  "maintenance_mode": false,
  "maintenance_message": "Orai Radio is under maintenance. We will be back online soon!",
  "force_update": false,
  "force_refresh": false,
  "min_app_version": 1,
  "minimum_supported_version": 1
}
```

Interim note: same-VM static is **process-independent only**. Permanent design = move `config.orairadio.in` DNS to independent static hosting (ADR-004). App needs no rebuild.

### 4b. Nginx — `/opt/orai-radio-command-center/deploy/azuracast-nginx/orai-public-vhosts.conf`

**Canonical file in repo** (do not maintain a second copy here):  
[`deploy/azuracast-nginx/orai-public-vhosts.conf`](../azuracast-nginx/orai-public-vhosts.conf)

Includes:
- `api.orairadio.in` → `/api/public/` only
- `config.orairadio.in` → static `app-config.json`
- `admin.orairadio.in` → Command Center UI + full `/api/` (see [`TRACK_A_ADMIN_SUBDOMAIN.md`](./TRACK_A_ADMIN_SUBDOMAIN.md))
- `orairadio.in` / `www` → 404

**Stream path:** unchanged via `default.vhost` → `include /var/azuracast/stations/*/config/nginx.conf` which already has `/listen/orai_radio/...` → `127.0.0.1:8000`. After multi-SAN LE cert replaces `ssl.crt`, `https://stream.orairadio.in/listen/...` trusts correctly without a separate stream `server{}`.

### 4c. Compose override — `/var/azuracast/docker-compose.override.yml`

```yaml
services:
  web:
    volumes:
      - /opt/orai-radio-command-center/deploy/azuracast-nginx/orai-public-vhosts.conf:/etc/nginx/conf.d/orai-public-vhosts.conf:ro
      - /opt/orai-radio-command-center/static/app-config.json:/var/azuracast/www_tmp/orai-app-config.json:ro
      - /opt/orai-radio-command-center/frontend:/var/azuracast/www_tmp/orai-admin-frontend:ro
    networks:
      - default
      - neena-network

networks:
  neena-network:
    external: true
    name: neena-network
```

Frontend bind is required for `https://admin.orairadio.in` (see [`TRACK_A_ADMIN_SUBDOMAIN.md`](./TRACK_A_ADMIN_SUBDOMAIN.md)).

---

## 5. Network plan

### How AzuraCast reaches Neena

- Join `azuracast` (`web`) to Docker network **`neena-network`**
- Proxy target: **`http://neena-backend:8000`** (container port, not host 8080)
- Host `127.0.0.1:8080` stays localhost-only for admin; **not** used by AzuraCast proxy

### Persistence

| Method | Persistent after recreate? |
|--------|----------------------------|
| `docker network connect neena-network azuracast` | **NO** |
| `docker-compose.override.yml` `networks:` as above | **YES** |

Proof after apply:

```bash
sudo docker inspect azuracast --format '{{json .NetworkSettings.Networks}}'
# must include both azuracast_default (or default) AND neena-network

sudo docker exec azuracast getent hosts neena-backend
# must resolve to 172.18.x.x

# Recreate persistence proof (only if owner accepts blip):
cd /var/azuracast && sudo docker compose up -d
sudo docker inspect azuracast --format '{{json .NetworkSettings.Networks}}'
```

### Safe compose update

- Prefer **override file** (do not rewrite main `docker-compose.yml`)
- `docker compose up -d` recreates `web` if config changed → **possible brief stream blip**
- Do **not** `compose down`
- Do **not** restart `neena-redis` / `neena-postgres`

---

## 6. SSL plan (Let’s Encrypt)

### Why not AzuraCast UI alone

- AzuraCast System Settings LE is designed for the **installation domain** and writes the shared `ssl.crt` / `ssl.key` pair.
- We need **one trusted cert covering three names** (or three certs). UI multi-SAN for `api`+`stream`+`config` is **not guaranteed** on this install (no `LETSENCRYPT_HOST` set in `.env` today; cert is self-signed localhost).
- **Chosen method:** `certbot certonly --webroot` against AzuraCast ACME challenge dir, issuing **one multi-SAN cert**, then install into the ACME volume paths AzuraCast nginx already uses.

### Challenge path

- Container: `/var/azuracast/storage/acme/challenges/`
- Host volume: `/var/lib/docker/volumes/azuracast_acme/_data/challenges/`
- Already exposed in `default.vhost` at `location /.well-known/acme-challenge`

### Issue + install (commands in §7)

- Domains: `api.orairadio.in,stream.orairadio.in,config.orairadio.in`
- After install: `ssl.crt` / `ssl.key` must be trusted Let’s Encrypt (not `CN=localhost`)
- Reload nginx only (`nginx -s reload`) — **no** Redis/Postgres; prefer **no** full AzuraCast restart for cert swap if files are replaced in-place on the volume

### Reload vs restart impact

| Action | Impact |
|--------|--------|
| `nginx -t` + `nginx -s reload` | Near-zero; connections drain; Icecast usually uninterrupted |
| `docker compose up -d` (override/network) | May recreate `azuracast` → **brief listener blip** |
| `docker compose down` / Redis / Postgres | **Forbidden** |

---

## 7. Exact execution commands (order) — DO NOT RUN YET

Replace `OWNER_EMAIL` before use.

```bash
# ---------- 0) Preconditions check ----------
getent hosts api.orairadio.in stream.orairadio.in config.orairadio.in
# all must show 35.244.15.150

# ---------- 1) Backups (§3) ----------
TS=$(date +%Y%m%d%H%M%S)
BK=/var/azuracast/backups/track-a-$TS
sudo mkdir -p "$BK"
sudo cp -a /var/azuracast/docker-compose.yml "$BK/docker-compose.yml"
sudo cp -a /var/azuracast/.env "$BK/env"
sudo cp -a /var/azuracast/azuracast.env "$BK/azuracast.env"
sudo docker exec azuracast nginx -T > "$BK/nginx-T.before.txt" 2>&1
sudo cp -a /var/lib/docker/volumes/azuracast_acme/_data "$BK/acme_data"
sudo docker inspect azuracast --format '{{json .NetworkSettings.Networks}}' > "$BK/azuracast-networks.before.json"
curl -sS http://127.0.0.1:8080/api/public/app-config > "$BK/app-config.before.json"

# ---------- 2) Create host files ----------
sudo mkdir -p /opt/orai-radio-command-center/deploy/azuracast-nginx
sudo mkdir -p /opt/orai-radio-command-center/static

# Write orai-public-vhosts.conf (snippet §4b) and app-config.json (snippet §4a)
# e.g. sudo nano ... or scp from workstation

sudo chmod 644 /opt/orai-radio-command-center/deploy/azuracast-nginx/orai-public-vhosts.conf
sudo chmod 644 /opt/orai-radio-command-center/static/app-config.json

# ---------- 3) LE multi-SAN cert (webroot) ----------
# Install certbot on host if missing:
#   sudo apt-get update && sudo apt-get install -y certbot

sudo certbot certonly --webroot \
  -w /var/lib/docker/volumes/azuracast_acme/_data/challenges \
  -d api.orairadio.in \
  -d stream.orairadio.in \
  -d config.orairadio.in \
  -d admin.orairadio.in \
  --email OWNER_EMAIL \
  --agree-tos \
  --non-interactive \
  --expand

# Install into AzuraCast ACME paths (keep copies of old defaults in $BK)
LE_LIVE=$(sudo ls -d /etc/letsencrypt/live/api.orairadio.in | head -1)
sudo cp -a /var/lib/docker/volumes/azuracast_acme/_data/default.crt "$BK/default.crt.bak"
sudo cp -a /var/lib/docker/volumes/azuracast_acme/_data/default.key "$BK/default.key.bak"
sudo cp "$LE_LIVE/fullchain.pem" /var/lib/docker/volumes/azuracast_acme/_data/default.crt
sudo cp "$LE_LIVE/privkey.pem" /var/lib/docker/volumes/azuracast_acme/_data/default.key
# ssl.crt / ssl.key are already symlinks to default.crt / default.key

# ---------- 4) Compose override + apply ----------
sudo tee /var/azuracast/docker-compose.override.yml >/dev/null <<'EOF'
services:
  web:
    volumes:
      - /opt/orai-radio-command-center/deploy/azuracast-nginx/orai-public-vhosts.conf:/etc/nginx/conf.d/orai-public-vhosts.conf:ro
      - /opt/orai-radio-command-center/static/app-config.json:/var/azuracast/www_tmp/orai-app-config.json:ro
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
# Expect possible brief azuracast recreate / stream blip

# ---------- 5) Nginx test + reload ----------
sudo docker exec azuracast nginx -t
sudo docker exec azuracast nginx -s reload

# ---------- 6) Optional: update Neena app_config to HTTPS domains ----------
# Only with owner confirm + existing admin token / Neena tool.
# Do NOT use HTTP IP as production api_base_url after edge is green.
```

**Cert renew hook (post-success, document only):** renew via certbot renew + copy fullchain/privkey into ACME volume + `nginx -s reload`.

---

## 8. Verification commands

```bash
# A) API app-config (must be Neena JSON, trusted cert)
curl -v --max-time 15 https://api.orairadio.in/api/public/app-config
# Expect: HTTP/2 200, JSON with stream_url/api_base_url, issuer Let's Encrypt
# Fail if: AzuraCast HTML/405, or SSL verify error

# B) Stream
curl -I --max-time 15 https://stream.orairadio.in/listen/orai_radio/radio.mp3
# Expect: HTTP 200/302/206, content-type audio related or redirect to audio
curl -sS --max-time 10 -r 0-255 -o /tmp/stream-sample.bin -w 'code=%{http_code} ctype=%{content_type}\n' \
  https://stream.orairadio.in/listen/orai_radio/radio.mp3

# C) Backup config JSON
curl -v --max-time 15 https://config.orairadio.in/app-config.json
# Expect: 200 application/json

# C2) Admin Command Center (permanent)
curl -sS -o /dev/null -w '%{http_code}\n' https://admin.orairadio.in/
curl -sS -w '\nHTTP=%{http_code}\n' https://admin.orairadio.in/healthz
# Expect: 200; see TRACK_A_ADMIN_SUBDOMAIN.md for full cutover

# D) api must NOT proxy admin
curl -sS -o /dev/null -w '%{http_code}\n' https://api.orairadio.in/api/admin/app-config/stream_url
# Expect: 404 (or non-Neena); must not return Neena admin success

# E) 8080 not public
ss -lntp | grep 8080
# Expect: 127.0.0.1:8080 only
curl -sS --max-time 5 http://35.244.15.150:8080/api/public/app-config || echo 'public_8080_unreachable_OK'
# From an external network / phone: connection refused/timeout = OK

# F) Network persistence + DNS inside azuracast
sudo docker exec azuracast getent hosts neena-backend
sudo docker inspect azuracast --format '{{json .NetworkSettings.Networks}}'

# G) Cert SANs
echo | openssl s_client -connect api.orairadio.in:443 -servername api.orairadio.in 2>/dev/null \
  | openssl x509 -noout -subject -issuer -ext subjectAltName
```

**Pass criteria:** A–C green with trusted LE; D closed; E localhost-only; F resolves `neena-backend`.

---

## 9. Rollback commands

```bash
# Set BK to the timestamped backup dir from §3
BK=/var/azuracast/backups/track-a-YYYYMMDDHHMMSS

# 1) Remove override (network + binds)
sudo mv /var/azuracast/docker-compose.override.yml /var/azuracast/docker-compose.override.yml.failed 2>/dev/null || true
# if a prior override existed: sudo cp "$BK/docker-compose.override.yml" /var/azuracast/docker-compose.override.yml

# 2) Restore certs
sudo cp -a "$BK/acme_data/default.crt" /var/lib/docker/volumes/azuracast_acme/_data/default.crt
sudo cp -a "$BK/acme_data/default.key" /var/lib/docker/volumes/azuracast_acme/_data/default.key

# 3) Recreate azuracast without override networks
cd /var/azuracast
sudo docker compose up -d

# 4) If runtime network leftover:
sudo docker network disconnect neena-network azuracast 2>/dev/null || true

# 5) Nginx reload
sudo docker exec azuracast nginx -t && sudo docker exec azuracast nginx -s reload

# 6) Host files can remain (unused) or:
# sudo rm -f /opt/orai-radio-command-center/deploy/azuracast-nginx/orai-public-vhosts.conf

# Verify rollback: https://api.orairadio.in may again show old behavior; stream HTTP should still work
```

Do **not** restart Redis/Postgres during rollback.

---

## 10. Risk notes

| Risk | Expectation |
|------|-------------|
| Downtime | Nginx reload ≈ none. `compose up -d` with override ≈ **10–60s** possible AzuraCast/web blip |
| Listener stream | May briefly disconnect during container recreate; Icecast ports rebound with container |
| LE rate limits | Avoid repeated failed issuances; fix DNS for `config` first |
| Wrong proxy scope | Mitigated by `/api/public/` only + `location / return 404` on `api` host |
| 8080 exposure | Unchanged — stays `127.0.0.1:8080` |
| Same-VM config JSON | Interim only (ADR-004); not infrastructure-independent |

### Will NOT be touched

- Mobile app / APK
- `neena-redis`, `neena-postgres` (no restart)
- AzuraCast broadcast/playlist/station content
- Host nginx on `:8443` / admin proxy (unless unrelated)
- Public publish of Neena `:8080`
- SSL verification bypass in app

---

## Owner approval gate

Reply with explicit approval to execute Track A, including:

1. Confirm `config.orairadio.in` DNS A → `35.244.15.150` is live  
2. Provide LE email for `OWNER_EMAIL`  
3. Accept possible brief AzuraCast stream blip on `compose up -d`  

Until then: **no VM changes, no SSL issuance, no AzuraCast recreate.**
