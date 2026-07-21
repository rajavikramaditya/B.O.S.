# Agent deploy mechanism (canonical)

**Read this before any VM deploy.** Full first-time install notes are in
`DEPLOYMENT_CHECKLIST.md` / `README.md` (some IPs there may be stale).
**Live runtime today is Dockerized Command Center**, not bare systemd uvicorn.

## Live target (current)

| Item | Value |
|------|--------|
| SSH | `ssh -i C:\Users\vikas\.ssh\gcp_key mahilkingdomorai@35.244.15.150` |
| App dir on VM | `/opt/orai-radio-command-center` |
| Compose file | `docker-compose.server.yml` |
| Backend container | `neena-backend` (host `127.0.0.1:8080` → container `8000`) |
| Admin UI (preferred) | `https://admin.orairadio.in` |
| Admin UI (fallback) | `https://35.244.15.150:8443` (host nginx) |
| WhatsApp gateway | systemd `radio-whatsapp-gateway` from `/home/mahilkingdomorai/radio-ai-manager/whatsapp` (separate from Docker app dir) |
| Redis / Postgres | `neena-redis`, `neena-postgres` — **do not restart** unless owner explicitly asks |

## Rules (always)

1. Owner must explicitly approve deploy.
2. Local tests + `python scripts/neena_predeploy_check.py` must pass first.
3. Never print `.env`, secrets, tokens, API keys. Never `docker exec env`.
4. Rebuild/recreate **only** what changed. Prefer:
   `sudo docker compose -f docker-compose.server.yml up -d --no-deps neena-backend`
5. Do **not** restart AzuraCast, Postgres, Redis, or prune Docker unless approved.
6. Do not touch mobile app / stream / expose 8080 publicly.
7. After deploy: `/healthz` HTTP 200 + short owner/customer smoke note for owner.

## Backend-only deploy (most common)

`/opt/orai-radio-command-center` is often root-owned — **SCP to `/tmp` then
`sudo cp`**. Do not use PowerShell `$HOST` (reserved); use `$VM`.

```powershell
$KEY = "C:\Users\vikas\.ssh\gcp_key"
$VM  = "mahilkingdomorai@35.244.15.150"
# example one file:
scp -i $KEY "c:\Projects\radio station\radio-ai-manager\backend\services\FILE.py" `
  "${VM}:/tmp/neena_deploy/FILE.py"
```

On VM (single-quoted remote command so `$T` is not eaten by PowerShell):

```bash
ssh -i C:\Users\vikas\.ssh\gcp_key mahilkingdomorai@35.244.15.150 \
  'sudo cp /tmp/neena_deploy/FILE.py /opt/orai-radio-command-center/backend/services/FILE.py'
```

Then rebuild **only** backend:

```bash
ssh -i C:\Users\vikas\.ssh\gcp_key mahilkingdomorai@35.244.15.150 \
  'cd /opt/orai-radio-command-center && sudo docker compose -f docker-compose.server.yml build neena-backend && sudo docker compose -f docker-compose.server.yml up -d --no-deps neena-backend && sudo docker builder prune -af && sleep 12 && curl -sS -w "\nHTTP=%{http_code}\n" http://127.0.0.1:8080/healthz'
```

**Always prune Docker build cache after a backend image build.** Left alone it can grow to ~20GB and fill the 49GB root disk (root cause of the 2026-07-15 ~74% disk alert). A daily host cron/`docker-builder-prune.timer` also keeps this trimmed — do not disable it.

## Self-heal host agent (ADR-011 — only with owner approval)

One-time host setup (after compose includes `/var/lib/neena` volume):

```bash
sudo mkdir -p /var/lib/neena
sudo cp deploy/gcp-vm/neena-self-heal.sh /usr/local/bin/neena-self-heal.sh
sudo chmod +x /usr/local/bin/neena-self-heal.sh
sudo cp deploy/gcp-vm/neena-self-heal.service /etc/systemd/system/
sudo cp deploy/gcp-vm/neena-self-heal.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now neena-self-heal.timer
```

`.env` on VM (start dry-run): `NEENA_SELF_HEAL=1`, `NEENA_SELF_HEAL_DRY_RUN=1`, then later `NEENA_SELF_HEAL_DRY_RUN=0` and optionally `NEENA_SELF_HEAL_ALLOW_REBOOT=1`. Recreate `neena-backend` so compose mount + env apply. Never enable reboot without confirming host agent logs first.

## WhatsApp gateway deploy (only if `whatsapp/gateway.js` changed)

Gateway is **not** inside the Docker app dir. Copy to the home tree and restart systemd:

```powershell
scp -i C:\Users\vikas\.ssh\gcp_key `
  "c:\Projects\radio station\radio-ai-manager\whatsapp\gateway.js" `
  mahilkingdomorai@35.244.15.150:/home/mahilkingdomorai/radio-ai-manager/whatsapp/gateway.js
```

```bash
sudo systemctl restart radio-whatsapp-gateway
sudo systemctl status radio-whatsapp-gateway --no-pager
```

## Frontend-only

SCP files under `/opt/orai-radio-command-center/frontend/`. If the image bakes
frontend in, rebuild `neena-backend` the same way; otherwise nginx may serve
static from the mounted tree — verify which path the live container uses before
assuming a rebuild is needed.

## Rollback

GitHub checkpoint on `main` (see `project_status.md`). Re-SCP known-good files
from that commit and rebuild `neena-backend --no-deps`, or restore previous
files from VM backup if kept.
