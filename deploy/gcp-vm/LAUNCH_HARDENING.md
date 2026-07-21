# M4-A7 — VM launch hardening (docs only — do not deploy without owner approval)

This document complements `DEPLOYMENT_CHECKLIST.md` with boot stability, memory stack, and security notes for the GCP VM.

## 1. Services on VM

| Service | Unit file | Port | Notes |
| --- | --- | --- | --- |
| Command Center API | `radio-command-center.service` | 8080 (VM template) | FastAPI + admin static UI |
| WhatsApp Gateway | `radio-whatsapp-gateway.service` | 3001 | Non-blocking for Command Center |
| AzuraCast | Docker (separate) | 80/443 | Stream + media library |
| Memory stack (optional shadow) | `docker-compose.memory.yml` | 5432 / 6379 | Shadow PG + Redis |

## 2. Environment file

- Path on VM: `/home/mahilkingdomorai/radio-ai-manager/.env`
- Never commit `.env` or print secrets in logs.
- Required for launch:
  - `GEMINI_API_KEY`
  - `AZURACAST_BASE_URL`, `AZURACAST_API_KEY`, `AZURACAST_STATION_ID`, `AZURACAST_TARGET_FOLDER`
  - `COMMAND_CENTER_LOCAL_ONLY=false` only when VM exposure is intentional
  - `ADMIN_AUTH_ENABLED=true` and `ADMIN_API_KEY` set before any public admin exposure

## 3. systemd — backend

```bash
sudo cp deploy/gcp-vm/radio-command-center.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable radio-command-center
sudo systemctl start radio-command-center
```

Recommended `radio-command-center.service` additions (owner applies on VM):

```ini
EnvironmentFile=/home/mahilkingdomorai/radio-ai-manager/.env
Restart=always
RestartSec=5
```

Health after reboot:

```bash
curl -s http://127.0.0.1:8080/api/neena/cockpit-status | head
curl -s http://127.0.0.1:8080/api/neena/launch-health | head
```

## 4. Docker memory stack on VM (optional shadow)

```bash
cd /home/mahilkingdomorai/radio-ai-manager
docker compose -f docker-compose.memory.yml up -d
python tools/local/check_memory_stack.py
```

Containers use `restart: unless-stopped` in compose file. **Never** run `docker compose down -v` in production.

## 5. Docker Engine auto-start

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

## 6. Health endpoints (UI contract)

| Endpoint | Tier | Use |
| --- | --- | --- |
| `GET /api/neena/cockpit-status` | `fast_health` | Command Center UI polling |
| `GET /api/neena/launch-health` | `deep_health` | Manual drawer / diagnostics |
| `GET /api/neena/security-status` | — | Exposure mode check |

## 7. Security

- **Default local dev:** `COMMAND_CENTER_LOCAL_ONLY=true` (auto when `RUNTIME_MODE` contains `LOCAL`).
- **VM exposure:** set `COMMAND_CENTER_LOCAL_ONLY=false` **only** with `ADMIN_AUTH_ENABLED=true` and strong `ADMIN_API_KEY`.
- Public mobile endpoints under `/api/public/*` remain reachable; admin UI and write APIs are guarded.
- **Launch blocker:** `Admin console must remain local-only until ADMIN_API_KEY auth is configured.`

## 8. Rollback

1. `sudo systemctl stop radio-command-center`
2. Restore previous `.env` backup
3. `sudo systemctl start radio-command-center`
4. Verify capsule stream with `tools/verify/test_m4_a4_stream_verification.py` (on VM or owner-approved session)

## 9. Local Windows rehearsal (no VM)

```powershell
powershell -ExecutionPolicy Bypass -File tools/local/start_local_command_center.ps1
python tools/verify/test_m4_a7_launch_hardening.py
```
