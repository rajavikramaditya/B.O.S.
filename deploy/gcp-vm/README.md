# GCP Compute VM Deployment Setup

This folder contains service files and configuration templates for deploying the **Orai Radio Command Center** backend and the **WhatsApp Gateway** on a Google Cloud Platform Compute Engine instance.

## Agents: start here

**Day-to-day deploy procedure (Docker, SCP, `--no-deps`):** see
[`AGENT_DEPLOY.md`](./AGENT_DEPLOY.md). Also linked from `AGENTS.md` §4 (Verify / deploy).

## Deployment Target Details (live)
- **SSH**: `mahilkingdomorai@35.244.15.150` (key: `C:\Users\vikas\.ssh\gcp_key`)
- **Docker app dir**: `/opt/orai-radio-command-center` (`docker-compose.server.yml`)
- **Backend container**: `neena-backend` → `127.0.0.1:8080`
- **Admin UI (preferred):** `https://admin.orairadio.in`
- **Admin UI (fallback):** `https://35.244.15.150:8443`
- Cutover runbook: [`TRACK_A_ADMIN_SUBDOMAIN.md`](./TRACK_A_ADMIN_SUBDOMAIN.md)
- **WhatsApp gateway**: systemd `radio-whatsapp-gateway` under
  `/home/mahilkingdomorai/radio-ai-manager/whatsapp`
- **Region/Zone**: `asia-south1-a` (typical)

## Service Orchestration
1. **neena-backend** (Docker): FastAPI Command Center + APIs.
2. **neena-redis / neena-postgres** (Docker): session + memory — do not bounce casually.
3. **radio-whatsapp-gateway** (systemd): WhatsApp Baileys gateway → backend webhooks.
4. **AzuraCast**: separate Docker stack on the same VM — never restart during Neena deploys unless approved.

## Installation Instructions
First-time / checklist: [`DEPLOYMENT_CHECKLIST.md`](./DEPLOYMENT_CHECKLIST.md)
(some older IPs in that file may be stale — prefer `AGENT_DEPLOY.md` for live IP).
