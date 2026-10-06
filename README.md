# B.O.S. — Business Operating System

**An AI operator that runs a business proactively.** B.O.S. doesn't wait for orders.
It guides customers toward a purchase or booking, saves every lead, plans every
follow-up, reviews the whole business on a schedule, and asks the owner only when
something matters.

- **Guides, doesn't wait.** Every reply moves the conversation forward. Autopilot
  reviews your business on its own and acts on what's safe.
- **Truthful by design.** Actions happen only through verified steps, and replies are
  re-grounded on real results. It never claims something was sent when it wasn't.
- **You stay in control.** Anything that reaches people outside the business, or
  can't be undone, waits in **Approvals**. You pick the autonomy level.
- **Connects to anything.** REST API, signed webhooks (Zapier / Make / n8n), an MCP
  server for AI agents, plus Telegram, WhatsApp Cloud API and email channels.
- **Vendor-neutral AI.** Claude (recommended) or Gemini, swappable at any time.

---

## Quick start (Docker)

```bash
git clone https://github.com/rajavikramaditya/B.O.S.
cd B.O.S.
docker compose up -d
```

Open **http://localhost:8000**. The setup wizard walks you through:

1. Create the owner account
2. Describe your business (this is your operator's playbook)
3. Paste a Claude or Gemini API key
4. Connect a channel (Telegram is the fastest way to try it)

Configuration is optional. Everything can be done from the dashboard, or see
[`.env.example`](.env.example).

> For Telegram and WhatsApp to deliver messages, B.O.S. needs a public **https**
> address. Set `PUBLIC_BASE_URL` (for example behind Caddy, Nginx or Cloudflare Tunnel).

## Local development

```bash
# Backend (Python 3.11+)
cd backend
pip install -r requirements-dev.txt
uvicorn main:app --reload            # http://localhost:8000  (API docs: /api/docs)
python -m pytest -q                  # test suite

# Dashboard (Node 20.19+ / 22+)
cd frontend
npm install
npm run dev                          # http://localhost:5173  (proxies the API)
```

## How it works

Every request, whether it's a customer chat, an owner instruction, an API call, an MCP
tool call or an Autopilot review, goes through the same 11-stage Runtime:

```
Observe → Context → Understand → Reason → Plan → Policy → (Approval)
        → Capability → Execute → Verify (→ Retry) → Memory → Response
```

| Layer | Responsibility | Where |
| --- | --- | --- |
| Gateway | Single entrance for every interface | `backend/gateway/` |
| Runtime | Lifecycle, AI understanding, per-step policy, verification | `backend/runtime/` |
| Capabilities | *What* the platform can do, with declared risk | `backend/capabilities/` |
| Providers | *How* it's done (Claude, Gemini, SQL, channels) | `backend/providers/` |
| Adapters | External systems (Telegram, WhatsApp, SMTP) | `backend/adapters/` |
| Workspace | Business database (separate from memory) | `backend/workspace/` |
| Autopilot | Proactive scheduled reviews | `backend/autopilot/` |
| Integrations | Connectors, API keys, webhooks, MCP | `backend/integrations/` |
| Dashboard | React + TypeScript owner app | `frontend/` |

### Autonomy levels

| Mode | Internal records (contacts, tasks) | Contacting people | Money / deletion / broadcast |
| --- | --- | --- | --- |
| Assist | asks first | asks first | asks first |
| **Autopilot** (default) | automatic | asks first | asks first |
| Autonomous | automatic | automatic | asks first |

Scheduled Autopilot reviews read text customers wrote, so on their own they only read records and
add follow-up tasks. Changing contacts, closing tasks or emitting events from a review waits in Approvals.

## Integrations

**REST API.** Create a key in *Integrations → Developer*, then:

```bash
curl -X POST http://localhost:8000/v1/messages \
  -H "Authorization: Bearer bos_live_..." -H "Content-Type: application/json" \
  -d '{"message": "Hi, do you deliver on Sundays?", "channel": "web",
       "contact": {"name": "Meera", "email": "meera@example.com"}}'
```

Endpoints: `/v1/messages`, `/v1/actions`, `/v1/events`, `/v1/contacts`, `/v1/tasks`,
`/v1/capabilities`. The full OpenAPI reference is at `/api/docs`.

| Scope | Allows |
| --- | --- |
| `runtime` | Send customer messages (`/v1/messages`). Safe for a website chat widget. |
| `operator` | Act as staff: `/v1/actions` and the MCP server. External steps still need owner approval. |
| `records:read` / `records:write` | Read / change contacts and tasks, over REST and inside the Runtime. |
| `events` | Report external events (`/v1/events`) and emit `custom.*` webhook events. |

Scopes are enforced inside the Runtime too: when an API or MCP request plans a step its key isn't
scoped for, a read is refused and anything else waits for owner approval. Keys always act as staff,
never as the platform. Conversation ids sent by an API key stay in that key's own namespace.

**Webhooks.** Events such as `contact.saved`, `task.created`, `approval.requested` and
`autopilot.briefing.ready` are POSTed with a Stripe-style signature:
`BOS-Signature: t=<unix>,v1=<hex HMAC-SHA256 of "<t>.<raw body>">`.

**MCP.** Point any MCP client at `https://your-host/mcp` with an API key that has the
`operator` scope (add `records:read` to let agents read contacts and tasks):

```json
{ "mcpServers": { "bos": { "type": "http", "url": "https://your-host/mcp",
  "headers": { "Authorization": "Bearer bos_live_..." } } } }
```

## Production notes

- Set `BOS_SETUP_TOKEN` before exposing a fresh instance, so only you can create the owner account.
- Behind a managed proxy (Render, Fly, Cloud Run) set `FORWARDED_ALLOW_IPS=*` so rate limits see real client addresses.
- Run a single worker (the default image does). Autopilot's scheduler runs in-process.
- Data lives in `/data` (SQLite by default). Back up that volume, or point
  `DATABASE_URL` / `MEMORY_DATABASE_URL` at PostgreSQL (`docker compose --profile postgres up -d`).
- Integration credentials are encrypted at rest with a key derived from `BOS_SECRET_KEY`.

## Project docs

- [`AGENTS.md`](AGENTS.md): architecture rules for contributors and coding agents
- [`project_status.md`](project_status.md): current state
- [`docs/adr/`](docs/adr): architecture decisions (ADR-008: AI-native Runtime)
