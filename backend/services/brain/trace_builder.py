import time

class _TraceBuilder:
    """Lightweight per-request trace accumulator. No secrets/prompts exposed."""
    def __init__(self):
        self._t0 = time.monotonic()
        self._checkpoints = {"routing": 0.0, "tools": 0.0, "llm": 0.0, "db": 0.0}
        self._last = self._t0
        self.steps = []
        self.source = "local_router"
        self.route = "unknown"
        self.selected_model = "auto"
        self.actual_model = None
        self.actual_api_model_id = None
        self.candidate_ids = []
        self.candidate_models = []
        self.model_verification_status = "not_checked"
        self.fallback_used = False
        self.fallback_model_used = False
        self.llm_used = False
        self.llm_provider = "none"
        self.llm_status = "not_used"
        
        # Action Packet Trace Fields
        self.intent = None
        self.confidence = 0.0
        self.route_type = None
        self.tool = None
        self.tool_suggested = "None"
        self.tool_executed = "false"
        self.tool_result_present = "false"
        self.executed_tool_name = "null"
        self.risk_level = "low"
        self.needs_owner_approval = False
        self.protected_action_requested = None
        self.next_safe_action = None
        self.local_tool_executed = "None"
        self.protected_action_blocked = "No"

        # Memory Trace Fields
        self.memory_mode = "short_term_only"
        self.memory_search_used = "short_term_only"
        self.memory_hits_count = 0
        self.embedding_model_used = None
        self.memory_backend = None
        self.semantic_memory_used = False
        self.memory_fallback_reason = None
        self.postgres_write_status = None
        self.postgres_embedding_status = None
        self.memory_write_backend = None
        self.postgres_memory_id = None
        self.sqlite_mirror_status = None
        self.sqlite_memory_id = None
        self.memory_save_status = None
        self.short_context_used = "No"

        # Session / Redis Trace Fields
        self.session_backend = None
        self.redis_available = None
        self.pending_state_source = None
        self.pending_candidate_active = None
        self.redis_fallback_reason = None
        self.whatsapp_gateway = None

        # M3 Operations Trace Fields
        self.operation_intent = None
        self.intent_confidence = None
        self.intent_source = None
        self.workflow_name = None
        self.extracted_fields = None
        self.memory_applied = None

        # Model Call Count Fields
        self.intent_model_call_count = 0
        self.response_model_call_count = 0
        self.total_model_call_count = 0
        self.model_unavailable_reason = None
        self.model_rate_limited = False
        self.retry_after_hint = None
        self.model_call_status = None

        # Approval/Policy Trace Fields
        self.pending_approval_type = None
        self.pending_approval_active = "No"
        self.approval_consumed = "No"
        self.approval_blocked_reason = None
        
        self.manager_action_packet_used = "No"
        self.is_followup = "No"
        self.followup_type = "None"
        self.refers_to_pending_action = "No"
        self.approval_strength = "None"
        self.pending_action_type = "None"
        self.pending_action_protected = "No"
        self.pending_action_executable_now = "No"
        self.policy_decision = "None"
        self.response_composer_model_used = "None"
        self.final_reply_source = "local_router"
        
        # Capability Manifest Trace Fields
        self.capability_manifest_used = "No"
        self.capabilities_count = 0
        self.unavailable_capabilities_count = 0
        self.capability_truth_level_summary = None

        # Reachability / blink audit (no secrets)
        self.reached_interpreter = False
        self.reached_model = False
        self.short_circuit_reason = None
        self.pending_cleared_without_execute = False
        self.pending_action_snapshot = None
        self.action_packet_summary = None
        self.capsule_id_resolved = None
        self.azuracast_push_block_reason = None
        self.blink_events = []

    def blink(self, event: str, **detail):
        """Record a mid-turn blink for the interaction recorder (no secrets)."""
        entry = {"event": event}
        for k, v in detail.items():
            if v is not None:
                entry[k] = v
        self.blink_events.append(entry)
        if len(self.blink_events) > 24:
            self.blink_events = self.blink_events[-24:]

    def step(self, name: str, msg: str):
        now = time.monotonic()
        self.steps.append({"step": name, "status": "done", "message": msg})
        self._last = now

    def mark(self, key: str):
        """Record elapsed time for a phase key."""
        if key in self._checkpoints:
            self._checkpoints[key] = round((time.monotonic() - self._t0) * 1000)

    def build(self) -> dict:
        total_ms = round((time.monotonic() - self._t0) * 1000)
        return {
            "source": self.source,
            "route": self.route,
            "selected_model": self.selected_model,
            "actual_model": self.actual_model,
            "actual_api_model_id": self.actual_api_model_id,
            "candidate_ids": self.candidate_ids,
            "candidate_models": self.candidate_models,
            "model_verification_status": self.model_verification_status,
            "fallback_used": self.fallback_used,
            "fallback_model_used": self.fallback_model_used,
            "llm": {
                "used": self.llm_used,
                "provider": self.llm_provider,
                "status": self.llm_status,
            },
            "timing": {
                "total_ms": total_ms,
                "llm_ms": self._checkpoints["llm"],
                "tools_ms": self._checkpoints["tools"],
                "db_ms": self._checkpoints["db"],
            },
            "trace": self.steps,
            # Action Packet Trace Fields
            "intent": self.intent,
            "confidence": self.confidence,
            "route_type": self.route_type,
            "tool": self.tool,
            "tool_suggested": self.tool_suggested,
            "tool_executed": self.tool_executed,
            "tool_result_present": self.tool_result_present,
            "executed_tool_name": self.executed_tool_name,
            "risk_level": self.risk_level,
            "needs_owner_approval": self.needs_owner_approval,
            "protected_action_requested": self.protected_action_requested,
            "next_safe_action": self.next_safe_action,
            "local_tool_executed": self.local_tool_executed,
            "protected_action_blocked": self.protected_action_blocked,
            # Memory Trace Fields
            "memory_mode": self.memory_mode,
            "memory_search_used": self.memory_search_used,
            "memory_hits_count": self.memory_hits_count,
            "embedding_model_used": self.embedding_model_used,
            "memory_backend": self.memory_backend,
            "semantic_memory_used": self.semantic_memory_used,
            "memory_fallback_reason": self.memory_fallback_reason,
            "postgres_write_status": self.postgres_write_status,
            "postgres_embedding_status": self.postgres_embedding_status,
            "memory_write_backend": self.memory_write_backend,
            "postgres_memory_id": self.postgres_memory_id,
            "sqlite_mirror_status": self.sqlite_mirror_status,
            "sqlite_memory_id": self.sqlite_memory_id,
            "memory_save_status": self.memory_save_status,
            "short_context_used": self.short_context_used,
            # Session / Redis Trace Fields
            "session_backend": self.session_backend,
            "redis_available": self.redis_available,
            "pending_state_source": self.pending_state_source,
            "pending_candidate_active": self.pending_candidate_active,
            "redis_fallback_reason": self.redis_fallback_reason,
            "whatsapp_gateway": self.whatsapp_gateway,
            # M3 Operations Trace Fields
            "operation_intent": self.operation_intent,
            "intent_confidence": self.intent_confidence,
            "intent_source": self.intent_source,
            "workflow_name": self.workflow_name,
            "extracted_fields": self.extracted_fields,
            "memory_applied": self.memory_applied,
            # Model Call Count Fields
            "intent_model_call_count": self.intent_model_call_count,
            "response_model_call_count": self.response_model_call_count,
            "total_model_call_count": self.total_model_call_count,
            "model_unavailable_reason": self.model_unavailable_reason,
            "model_rate_limited": self.model_rate_limited,
            "retry_after_hint": self.retry_after_hint,
            "model_call_status": self.model_call_status,
            # Approval/Policy Trace Fields
            "pending_approval_type": self.pending_approval_type,
            "pending_approval_active": self.pending_approval_active,
            "approval_consumed": self.approval_consumed,
            "approval_blocked_reason": self.approval_blocked_reason,
            "manager_action_packet_used": self.manager_action_packet_used,
            "is_followup": self.is_followup,
            "followup_type": self.followup_type,
            "refers_to_pending_action": self.refers_to_pending_action,
            "approval_strength": self.approval_strength,
            "pending_action_type": self.pending_action_type,
            "pending_action_protected": self.pending_action_protected,
            "pending_action_executable_now": self.pending_action_executable_now,
            "policy_decision": self.policy_decision,
            "response_composer_model_used": self.response_composer_model_used,
            "final_reply_source": self.final_reply_source,
            # Capability Manifest Trace Fields
            "capability_manifest_used": self.capability_manifest_used,
            "capabilities_count": self.capabilities_count,
            "unavailable_capabilities_count": self.unavailable_capabilities_count,
            "capability_truth_level_summary": self.capability_truth_level_summary,
            # Reachability / blink audit
            "reached_interpreter": self.reached_interpreter,
            "reached_model": self.reached_model,
            "short_circuit_reason": self.short_circuit_reason,
            "pending_cleared_without_execute": self.pending_cleared_without_execute,
            "pending_action_snapshot": self.pending_action_snapshot,
            "action_packet_summary": self.action_packet_summary,
            "capsule_id_resolved": self.capsule_id_resolved,
            "azuracast_push_block_reason": self.azuracast_push_block_reason,
            "blink_events": list(self.blink_events),
        }
