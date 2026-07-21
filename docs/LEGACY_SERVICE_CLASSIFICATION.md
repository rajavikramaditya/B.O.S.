# B.O.S. Legacy Service Classification
**Official Migration Map — `backend/services/`**
**Sprint:** Pre-Sprint-12 (Read-Only Audit)
**Action Taken:** Zero files modified or deleted.

---

## Classification Legend

| Code | Category | Target Layer |
|---|---|---|
| **A** | Generic Platform Capability | `backend/capabilities/` (Sprint-12 Framework) |
| **B** | Business Module Logic | `backend/modules/radio/` or `backend/modules/crm/` |
| **C** | AI Manager Logic | `backend/modules/ai_manager/` (future) |
| **D** | Infrastructure / Provider Logic | `backend/providers/` |
| **E** | Dead Legacy | Retire after extraction |

---

## `services/agent/`

| File | Current Responsibility | Category | Target Layer | Migration Sprint | Safe to Remove? | Extraction Required? |
|---|---|---|---|---|---|---|
| `run_kernel.py` | Orchestrates owner requests: goal→plan→inventory→act→verify. Owner Run lifecycle. | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `run_contract.py` | Data contract for OwnerRun state object | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `step.py` | Step execution engine inside Owner Run loop | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `truth_gate.py` | Structural truth enforcement: prevents fake progress/timer/pause claims without tool proof | **C** | AI Manager Module (Policy Extension) | Sprint-15+ | NO | YES |
| `working_context.py` | Working execution context: active slots, pending actions, context window | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `system_knowledge_pack.py` | Packages system context (station health, memory, capabilities) into AI prompt context | **C** | AI Manager Module | Sprint-15+ | NO | YES |

---

## `services/brain/`

| File | Current Responsibility | Category | Target Layer | Migration Sprint | Safe to Remove? | Extraction Required? |
|---|---|---|---|---|---|---|
| `brain.py` | **Main AI decision pipeline.** 1174-line monolith. Receives message → intent → policy → tool → response. | **C** | AI Manager Module (core entrypoint) | Sprint-15+ | NO | YES |
| `capability_manifest.py` | Builds live capability availability report (LLM config, env, AzuraCast, WhatsApp status). | **A+B** | Split: Platform Capability Registry (A) + Radio Module capability reporting (B) | Sprint-12+13 | NO | YES |
| `command_execution_kernel.py` | Thin dispatcher: routes approved commands to executor | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `command_interpreter.py` | LLM-assisted natural language → structured command mapping (28KB). Hinglish NLU. | **C** | AI Manager Module (NLU layer) | Sprint-15+ | NO | YES |
| `context_builder.py` | Assembles context packet for LLM calls (memory, state, station info) | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `contracts.py` | Data contracts: memory packets, context packets, action packets | **C** | AI Manager Module contracts | Sprint-15+ | NO | YES |
| `contracts_foundation.py` | Base contract definitions | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `conversation.py` | WhatsApp owner conversation management (19KB) | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `creative_jobs.py` | Manages radio script/capsule creative generation jobs | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `customer_chat.py` | Customer WhatsApp chat handler (22KB). Customer-facing conversations. | **B** | CRM / Customer Module | Sprint-14 | NO | YES |
| `deterministic_routes.py` | Fast path for deterministic (non-LLM) action routing | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `error_handler.py` | Centralized error response builder for brain pipeline | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `factual_reply.py` | Forces factual-only reply mode | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `feature_flags.py` | Runtime feature flag evaluation (env-based) | **A** | REPLACED by backend/config/flags.py (Sprint-11) | Sprint-11 DONE | YES | NO |
| `live_ops_executor.py` | Thin wrapper forwarding to tools/live_ops | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `live_ops_quick.py` | Quick live ops shortcut path | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `live_state_snapshot.py` | Real-time radio station state snapshot: stream health, AzuraCast status (10KB) | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `live_voice.py` | Live voice broadcast state management (10KB) | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `load_shedding.py` | Graceful degradation when LLM unavailable | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `manager_state.py` | In-memory + Redis AI manager session state (18KB) | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `message_router.py` | Thin router: owner vs customer message dispatch | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `operations_classifier.py` | Classifies radio operations intent with confidence scoring | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `operations_workflows.py` | Radio operations execution workflows (34KB): approve capsule, generate audio, AzuraCast | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `owner_customer_context.py` | Builds customer recall packet for owner context injection (11KB) | **B+C** | Split: CRM Module (B) + AI Manager context (C) | Sprint-13/14 | NO | YES |
| `owner_notifier.py` | Sends WhatsApp notification to owner | **A** | SendMessageCapability → MessagingProvider | Sprint-12 | NO | YES |
| `owner_preferences.py` | Owner preference settings (concise mode, language, tone) | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `prompt_builder.py` | Builds final LLM prompt: system instructions + context + memory (14KB) | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `recorder_review.py` | Recorder/session review management | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `redis_state.py` | Redis session state adapter with local fallback (20KB) | **D** | Infrastructure Provider (RedisProvider) | Sprint-13 | NO | YES |
| `response_composer.py` | Assembles final response for owner (5KB) | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `self_knowledge.py` | Neena self-identity knowledge base (12KB) | **C** | AI Manager Module (Identity Profile) | Sprint-15+ | NO | YES |
| `trace_builder.py` | Builds execution trace for debugging/logging (10KB) | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `vm_status.py` | VM health check (guarded, cannot restart) | **D** | Infrastructure Provider | Sprint-16+ | NO | YES |
| `always_reply.py` | Ensures non-empty reply for all paths | **C** | AI Manager Module | Sprint-15+ | NO | YES |

---

## `services/broadcast/`

| File | Current Responsibility | Category | Target Layer | Migration Sprint | Safe to Remove? | Extraction Required? |
|---|---|---|---|---|---|---|
| `azuracast_client.py` | **AzuraCast REST API client (41KB).** Complete HTTP client for radio station management. | **D** | AzuraCastProvider in backend/providers/ | Sprint-13 | NO | YES |
| `azura_events.py` | AzuraCast webhook event handling | **D** | AzuraCastProvider | Sprint-13 | NO | YES |
| `approval_queue.py` | Owner approval queue for broadcast actions | **A** | ApprovalCapability → Policy Layer | Sprint-12 | NO | YES |
| `capsule_review.py` | Review capsule before broadcast | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `capsule_service.py` | Full capsule lifecycle: create, approve, schedule, play (34KB) | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `listener_path.py` | Listener journey tracking (13KB) | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `playback_control.py` | Manual playback control: skip, pause, restart (10KB) | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `playout.py` | Playout management facade | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `stream_verification.py` | Stream health verification (18KB) | **D** | StreamMonitorProvider | Sprint-13 | NO | YES |

---

## `services/cockpit/`

| File | Current Responsibility | Category | Target Layer | Migration Sprint | Safe to Remove? | Extraction Required? |
|---|---|---|---|---|---|---|
| `action_registry.py` | Command Center action definitions with voice templates (10KB) | **B** | Radio Business Module (UI manifest) | Sprint-13 | NO | YES |
| `action_service.py` | Executes cockpit actions | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `deferred_status.py` | Deferred WhatsApp status arm/fire scheduling (10KB) | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `health_cache.py` | Health cache for fast cockpit status reads | **D** | Infrastructure / Cache Layer | Sprint-16 | NO | YES |
| `job_repository.py` | Job queue repository (8KB) | **D** | Infrastructure Provider (Queue) | Sprint-16 | NO | YES |
| `job_service.py` | Background job lifecycle management | **D** | Infrastructure Provider | Sprint-16 | NO | YES |
| `launch_health.py` | Startup health check (6KB) | **D** | Infrastructure Provider | Sprint-16 | NO | YES |
| `recorder.py` | Session recording and playback (23KB) | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `resource_monitor.py` | CPU/memory resource monitoring (9KB) | **D** | Infrastructure Provider | Sprint-16 | NO | YES |
| `runtime_controller.py` | **Master runtime health**: AzuraCast ping, WhatsApp gateway, VM status (11KB) | **D** | Split: AzuraCastProvider health + WhatsAppProvider health | Sprint-13 | NO | YES |
| `self_heal.py` | Self-healing: auto-restart AzuraCast if down | **D** | AzuraCastProvider (provider-level recovery) | Sprint-13 | NO | YES |
| `status_fast.py` | Fast cached status endpoint (8KB) | **B+D** | Split: Radio Module status + Infrastructure monitoring | Sprint-13 | NO | YES |

---

## `services/content/`

| File | Current Responsibility | Category | Target Layer | Migration Sprint | Safe to Remove? | Extraction Required? |
|---|---|---|---|---|---|---|
| `engine.py` | Content ingestion orchestrator | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `local_news_scraper.py` | RSS/news scraper for local news content | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `source_tools.py` | Tool contract implementations for source data (28KB): weather, traffic, news | **B** | Radio Business Module (StationSourceCapability) | Sprint-13 | NO | YES |

---

## `services/llm/`

| File | Current Responsibility | Category | Target Layer | Migration Sprint | Safe to Remove? | Extraction Required? |
|---|---|---|---|---|---|---|
| `provider_router.py` | **LLM routing engine (27KB)**: Gemini + OpenAI fallback, rate limiting, model selection | **D** | GeminiProvider + OpenAIProvider in backend/providers/ | Sprint-13 | NO | YES |
| `intent_llm.py` | LLM-based intent classification (Neena system prompt, 13KB) | **C** | AI Manager Module (Intent Layer) | Sprint-15+ | NO | YES |
| `intent_router.py` | Fast pattern-based intent pre-routing | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `model_roles.py` | Model role configuration (primary/secondary/creative) | **D** | LLMProvider configuration schema | Sprint-13 | NO | YES |
| `model_status.py` | Model health status and availability check | **D** | LLMProvider health reporting | Sprint-13 | NO | YES |
| `quota_gatekeeper.py` | API quota management and rate limiting (5KB) | **D** | LLMProvider rate limit policy | Sprint-13 | NO | YES |

---

## `services/memory/`

| File | Current Responsibility | Category | Target Layer | Migration Sprint | Safe to Remove? | Extraction Required? |
|---|---|---|---|---|---|---|
| `service.py` | **Core memory service (42KB)**: read/write/recall with SQLite+Postgres+pgvector | **A** | StoreDocumentCapability + MemoryProvider | Sprint-12+13 | NO | YES |
| `pg_repository.py` | PostgreSQL + pgvector memory repository (28KB) | **D** | PostgresMemoryProvider in backend/providers/ | Sprint-13 | NO | YES |
| `repository.py` | SQLite memory repository (14KB) | **D** | SQLiteMemoryProvider in backend/providers/ | Sprint-13 | NO | YES |
| `facade.py` | Memory access facade (15KB): unified API over SQLite+Postgres | **A** | MemoryCapability facade | Sprint-12 | NO | YES |
| `contract.py` | Memory type contracts: permanent/temporary, classification rules (8KB) | **A** | MemoryCapability schema contracts | Sprint-12 | NO | YES |
| `adapter.py` | Thin memory adapter bridging brain and memory service | **A** | MemoryCapability adapter | Sprint-12 | NO | YES |
| `continuity.py` | Session continuity (conversation thread persistence) | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `customer_salient.py` | Customer salient facts memory | **B** | CRM Module | Sprint-14 | NO | YES |
| `day_memory.py` | Daily memory timeline and recall (30KB) | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `edit_service.py` | Memory edit/correction service (14KB) | **A** | MemoryCapability (edit action) | Sprint-12 | NO | YES |
| `embedding_provider.py` | Text embedding generation (3KB): Gemini embedding API | **D** | EmbeddingProvider in backend/providers/ | Sprint-13 | NO | YES |
| `future_intention.py` | Future intention memory tracking (17KB) | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `production_health.py` | Memory backend health reporting | **D** | Infrastructure Provider health | Sprint-13 | NO | YES |
| `self_change.py` | AI manager self-state change tracking (18KB) | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `self_narrative.py` | Neena's narrative/story about herself (22KB) | **C** | AI Manager Module (Identity) | Sprint-15+ | NO | YES |
| `status.py` | Memory status summary | **D** | Memory Provider health | Sprint-13 | NO | YES |

---

## `services/safety/`

| File | Current Responsibility | Category | Target Layer | Migration Sprint | Safe to Remove? | Extraction Required? |
|---|---|---|---|---|---|---|
| `kernel.py` | **M0 Safety Kernel**: protected action enforcement, broadcast safety guards | **A** | SecurityPolicy extension in PolicyEngineV2 | Sprint-12 | NO | YES |
| `policy_engine.py` | Legacy policy engine (13KB): routing rules, approval logic | **A** | Migrate patterns to PolicyEngineV2 extensions | Sprint-12 | NO | YES |
| `policy_guard.py` | Policy guard: checks if action is allowed | **A** | PolicyEngineV2 extension | Sprint-12 | NO | YES |
| `admin_security.py` | Admin panel security (8KB): PIN auth, session tokens | **D** | AuthProvider / Security Infrastructure | Sprint-16 | NO | YES |
| `admin_unlock.py` | Admin unlock flow (8KB) | **D** | AuthProvider | Sprint-16 | NO | YES |
| `security_config.py` | SSL verification config | **D** | Infrastructure configuration (ConfigurationFramework) | Sprint-11 DONE | YES | NO |

---

## `services/tools/`

| File | Current Responsibility | Category | Target Layer | Migration Sprint | Safe to Remove? | Extraction Required? |
|---|---|---|---|---|---|---|
| `definitions.py` | Tool catalog definitions (10KB): all tool names, descriptions, categories | **C** | AI Manager Module (Tool Registry) | Sprint-15+ | NO | YES |
| `catalog.py` | Tool catalog management (5KB) | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `catalog_health.py` | Tool catalog health check | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `legacy_gemini_registry.py` | **Legacy Gemini function-calling tool registry (31KB)**: all tool schemas for Gemini | **C** | AI Manager Module → ProviderCapabilitySchema | Sprint-15+ | NO | YES |
| `executor.py` | Tool execution engine (4KB) | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `loop.py` | Tool execution loop (11KB): retry, fallback, verify | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `bind_handlers.py` | Binds action handlers to tool names | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `customer_whatsapp.py` | Customer WhatsApp message sender | **B** | CRM Module → WhatsAppProvider | Sprint-14 | NO | YES |
| `deferred_whatsapp_status.py` | Deferred WhatsApp status scheduling | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `memory_notebook.py` | Notebook memory tools: day recap, summary, future intentions | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `self_change_status.py` | Self-status change tool wrapper | **C** | AI Manager Module | Sprint-15+ | NO | YES |
| `station_plan.py` | Station content plan generation (10KB) | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `station_plan_store.py` | Station plan persistence (5KB) | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `live_ops_executor.py` | Live ops execution wrapper | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `live_ops_quick.py` | Live ops quick action wrapper | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `live_ops/_dispatch.py` | **Master live ops dispatcher (74KB)** — dispatches all radio station actions | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `live_ops/_common.py` | Shared live ops utilities | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `live_ops/azura_pulse.py` | AzuraCast pulse check | **D** | AzuraCastProvider | Sprint-13 | NO | YES |
| `live_ops/capsules.py` | Capsule ops wrapper | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `live_ops/memory_ops.py` | Memory ops in live_ops context | **A** | MemoryCapability | Sprint-12 | NO | YES |
| `live_ops/recorder.py` | Recorder ops wrapper | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `live_ops/status.py` | Station status handler | **B** | Radio Business Module | Sprint-13 | NO | YES |
| `live_ops/stream_listener.py` | Stream listener status | **D** | StreamMonitorProvider | Sprint-13 | NO | YES |

---

## `services/voice/`

| File | Current Responsibility | Category | Target Layer | Migration Sprint | Safe to Remove? | Extraction Required? |
|---|---|---|---|---|---|---|
| `gen_service.py` | **TTS voice generation (31KB)**: ElevenLabs + Gemini TTS, audio encoding | **D** | TTSProvider (ElevenLabsProvider, GeminiTTSProvider) | Sprint-13 | NO | YES |
| `cockpit_voice.py` | Cockpit voice UI state management (14KB) | **B** | Radio Business Module (UI) | Sprint-13 | NO | YES |
| `generator.py` | Thin voice generation wrapper | **D** | TTSProvider | Sprint-13 | NO | YES |
| `local_service.py` | Local (offline) TTS fallback | **D** | LocalTTSProvider | Sprint-13 | NO | YES |
| `whatsapp_handler.py` | WhatsApp voice message handler | **B** | Radio Business Module | Sprint-13 | NO | YES |

---

## Summary by Category

| Category | Count | Target Layer | Migration Sprint |
|---|---|---|---|
| **A — Generic Platform Capability** | ~15 files | backend/capabilities/ + backend/config/ | Sprint-12 |
| **B — Business Module Logic** | ~35 files | backend/modules/radio/, backend/modules/crm/ | Sprint-13, Sprint-14 |
| **C — AI Manager Logic** | ~28 files | backend/modules/ai_manager/ | Sprint-15+ |
| **D — Infrastructure / Provider** | ~20 files | backend/providers/ | Sprint-13 |
| **E — Dead Legacy** | 0 files | N/A | N/A |

---

## Top Priority Migrations

### Sprint-12 — Capability Framework (NOW)
- services/brain/owner_notifier.py → SendMessageCapability
- services/memory/adapter.py, facade.py, contract.py → MemoryCapability
- services/broadcast/approval_queue.py → ApprovalCapability
- services/safety/kernel.py, policy_guard.py → PolicyEngineV2 extensions

### Sprint-13 — Radio Business Module + Provider Layer
- services/broadcast/ (entire) → AzuraCastProvider + Radio Module
- services/content/ (entire) → Radio Module
- services/tools/live_ops/ (entire) → Radio Module
- services/llm/provider_router.py → GeminiProvider + OpenAIProvider
- services/voice/gen_service.py → ElevenLabsProvider + GeminiTTSProvider
- services/memory/pg_repository.py → PostgresMemoryProvider

### Sprint-15+ — AI Manager Module
- services/brain/brain.py (1174 lines — main AI loop)
- services/brain/command_interpreter.py (28KB NLU)
- services/agent/ (entire folder)
- services/brain/manager_state.py, redis_state.py

---

## Files Safe To Remove Right Now

**None.** Every file still has active consumers in the running product.
Migration Order: KEEP → REFACTOR → EXTRACT → REPLACE → RETIRE
