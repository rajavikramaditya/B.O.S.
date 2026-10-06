# Project

Business Operating System (B.O.S.)

# Current Stage

Launch Readiness — Platform Activated

# Current Sprint

Sprint-13 (Platform Activation & Launch Readiness)

# Current Milestone

Sprint-13 Completed: the Runtime runs end to end with AI understanding, per-step policy and verification. The owner dashboard, channels (Telegram and WhatsApp inbound, SMTP outbound email), public API, webhooks, MCP server, Autopilot and Docker deployment are in place. Security review hardening (scoped API keys enforced in the Runtime, namespaced identities, self-service field limits, Autopilot grants, signed and size-capped channel webhooks) is done. 82 tests passing.

# Current Priority

Pilot with one real business on the live deployment (bos.orbitcore.in, Gemini, Telegram)

# Repository Status

B.O.S. repository on GitHub (`https://github.com/rajavikramaditya/B.O.S.`). Legacy Neena project remains the migration source; its deploy files are archived in `legacy/deploy/`.

# Completed

- Sprint-13: the platform is activated end to end (Runtime with AI understanding, per-step policy and verification; owner dashboard; Telegram and WhatsApp inbound channels, SMTP outbound email; public API, signed webhooks and MCP server; Autopilot; Docker image and CI).
- Deployed on Render (web service plus Postgres) at `bos.orbitcore.in`, from branch `claude/nifty-shannon-5t1q7w`.
- Security review hardening on PR #1: scoped API keys enforced inside the Runtime, namespaced conversations and identities, customer self-service field limits, Autopilot grants, signed and size-capped channel webhooks, least-privilege API keys, internal contact fields hidden from customer turns. 82 tests passing.
- The full task log is in `project_history.md`.

# In Progress

- None

# Blockers

- Render is on the free plan (the service sleeps when idle, and the free Postgres expires on 2026-11-03). Upgrading needs a payment card on the owner's Render account.

# Next Tasks

1. Merge PR #1 into `main` and point the Render deploy branch at `main`
2. Pilot with one real business; tune the operating prompts from real conversations
3. Website chat widget (embeddable `<script>` using `/v1/messages`)
4. Calendar/booking and payments capabilities (via business modules)
5. Multi-user workspaces (staff roles) and multi-tenant hosting
6. RETIRE keyword-based `IntentClassifier` and B-01 recency cache once nothing references them
7. Sprint-13 legacy plan (Radio Business Module, AzuraCast/ElevenLabs providers) as an installable module

# Current Goal

Transform the existing Neena AI Radio Manager into a universal Business Operating System without rewriting the project.
