# Legacy Idea Catalog

## Overview
This catalog documents product ideas, user workflows, business capabilities, AI behaviors, and UX features extracted from the legacy AI Radio Manager codebase for preservation in the Business Operating System (B.O.S.).

---

# 1. Radio & Broadcasting Module

| Field | Description |
| :--- | :--- |
| **Legacy Module** | `backend/services/broadcast/`, `backend/routers/broadcast.py`, `azuracast_webhook.py` |
| **Purpose** | Audio streaming, song dedications, station telemetry, and AzuraCast autoDJ integration |
| **Ideas Found** | Live stream status polling, pending listener song dedications (Apna Gaana), playlist push, automated autoDJ restarts, stream verification checks |
| **Capability Mapping** | `automation`, `messaging`, `scheduling` |
| **Exists in B.O.S.?** | Yes (mapped to Radio Business Module) |
| **Future Priority** | Medium (Industry-specific module) |

---

# 2. Local News & Content Scraper

| Field | Description |
| :--- | :--- |
| **Legacy Module** | `backend/services/content/local_news_scraper.py` |
| **Purpose** | Local news headlines scraping for Orai / Jalaun region |
| **Ideas Found** | Real-time regional news ingestion to inform AI prompt context and content generation |
| **Capability Mapping** | `knowledge`, `search` |
| **Exists in B.O.S.?** | Yes (RAG / Knowledge Graph ingestion) |
| **Future Priority** | High (Generic Knowledge Ingestion) |

---

# 3. Safety Kernel & Owner Approval Gate

| Field | Description |
| :--- | :--- |
| **Legacy Module** | `backend/services/safety/kernel.py`, `policy_engine.py`, `admin_security.py` |
| **Purpose** | Human-in-the-loop protection against irreversible administrative actions |
| **Ideas Found** | Mandatory owner confirmation for protected actions (`send_azuracast`, `delete_db`, `restart_server`), one-tap affirmative confirmation ("haan", "yes", "confirm") |
| **Capability Mapping** | `approval`, `identity` |
| **Exists in B.O.S.?** | Yes (`PolicyEngineV2`, `ApprovalWorkflowTemplate`, `DecisionEngine`) |
| **Future Priority** | Core (Already integrated) |

---

# 4. Telemetry & Cockpit Command Center

| Field | Description |
| :--- | :--- |
| **Legacy Module** | `backend/services/cockpit/runtime_controller.py`, `status_fast.py`, `action_registry.py` |
| **Purpose** | System load stats, RAM/CPU metrics, active job queue monitoring, service health checks |
| **Ideas Found** | Live telemetry snapshotting (`build_live_state_snapshot`), service readiness flags, active job tracking, resource overload warnings |
| **Capability Mapping** | `analytics`, `automation` |
| **Exists in B.O.S.?** | Yes (`ExecutionContext`, `AnalyticsCapability`) |
| **Future Priority** | High (Generic Cockpit Dashboard) |

---

# 5. Customer Brain & Chat Threads

| Field | Description |
| :--- | :--- |
| **Legacy Module** | `backend/services/brain/customer_chat.py`, `owner_customer_context.py` |
| **Purpose** | External listener/customer inquiry processing, Hinglish tone humanization, thread recall |
| **Ideas Found** | Actor-aware response synthesis, role separation (Owner vs Customer vs Employee), multi-channel chat routing, conversational memory persist |
| **Capability Mapping** | `messaging`, `memory`, `contacts` |
| **Exists in B.O.S.?** | Yes (`IntentEngine`, `CustomerRequestWorkflowTemplate`) |
| **Future Priority** | Core (Already integrated) |

---

# 6. Memory Edit & Approval Buffer

| Field | Description |
| :--- | :--- |
| **Legacy Module** | `backend/services/memory/edit_service.py` |
| **Purpose** | Staging pending memory updates before owner confirmation |
| **Ideas Found** | Pending memory edits state machine, approval buffer for long-term memory updates |
| **Capability Mapping** | `memory`, `approval` |
| **Exists in B.O.S.?** | Yes (`WorkflowMemory`, `HistoryStore`) |
| **Future Priority** | Core (Already integrated) |
