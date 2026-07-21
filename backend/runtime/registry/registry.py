"""B.O.S. Universal Capability Registry v0.1

Central registry storing and resolving universal platform capabilities.
Planner requests capabilities by name/action; capability resolves adapters.
"""

from typing import Any, Dict, List, Optional
from .metadata import CapabilityMetadata
from .base_capability import UniversalCapability


class GenericCapabilityStub(UniversalCapability):
    """Generic capability implementation for platform capabilities."""

    def __init__(self, metadata: CapabilityMetadata, actions: List[str]):
        super().__init__(metadata)
        self._actions = actions

    def supported_actions(self) -> List[str]:
        return self._actions

    def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": True,
            "capability": self.name,
            "action": action,
            "params": params,
            "status": "executed_stub",
        }


class UniversalCapabilityRegistry:
    """Registry managing all available platform capabilities."""

    _registry: Dict[str, UniversalCapability] = {}

    @classmethod
    def register(cls, capability: UniversalCapability) -> None:
        cls._registry[capability.name.lower()] = capability

    @classmethod
    def get(cls, name: str) -> Optional[UniversalCapability]:
        return cls._registry.get(name.lower())

    @classmethod
    def list_metadata(cls) -> List[Dict[str, Any]]:
        return [cap.metadata.to_dict() for cap in cls._registry.values()]

    @classmethod
    def find_capability_for_action(cls, action: str) -> Optional[UniversalCapability]:
        for cap in cls._registry.values():
            if action in cap.supported_actions():
                return cap
        return None

    @classmethod
    def initialize_defaults(cls) -> None:
        """Seed registry with standard B.O.S. Universal Capabilities."""
        defaults = [
            CapabilityMetadata(
                name="messaging",
                description="Generic communication and messaging capability across channels.",
                required_inputs=["message"],
                expected_outputs=["status", "delivered"],
                supported_adapters=["whatsapp", "telegram", "email", "sms"],
            ),
            CapabilityMetadata(
                name="scheduling",
                description="Generic scheduling and calendar event management capability.",
                required_inputs=["event_title", "time"],
                expected_outputs=["event_id", "status"],
                supported_adapters=["google_calendar", "outlook", "internal_clock"],
            ),
            CapabilityMetadata(
                name="workflow",
                description="Workflow orchestration and execution state management.",
                required_inputs=["workflow_id"],
                expected_outputs=["status", "current_node"],
                supported_adapters=["state_graph_runner"],
            ),
            CapabilityMetadata(
                name="knowledge",
                description="Knowledge retrieval and RAG search capability.",
                required_inputs=["query"],
                expected_outputs=["documents", "answer"],
                supported_adapters=["vector_db", "memory_store"],
            ),
            CapabilityMetadata(
                name="memory",
                description="Working and long-term memory storage and recall.",
                required_inputs=["key"],
                expected_outputs=["value"],
                supported_adapters=["redis", "postgres"],
            ),
            CapabilityMetadata(
                name="contacts",
                description="CRM contact and actor profile management.",
                required_inputs=["actor_id"],
                expected_outputs=["profile"],
                supported_adapters=["db_contacts"],
            ),
            CapabilityMetadata(
                name="documents",
                description="Document creation, reading, and archival.",
                required_inputs=["document_name"],
                expected_outputs=["doc_id", "content"],
                supported_adapters=["local_storage", "s3"],
            ),
            CapabilityMetadata(
                name="notification",
                description="System alerts and user notifications.",
                required_inputs=["target", "text"],
                expected_outputs=["notified"],
                supported_adapters=["push_service", "email"],
            ),
            CapabilityMetadata(
                name="analytics",
                description="Business metrics, reporting, and KPI tracking.",
                required_inputs=["metric_name"],
                expected_outputs=["value", "trend"],
                supported_adapters=["telemetry_store"],
            ),
            CapabilityMetadata(
                name="search",
                description="Global business data search.",
                required_inputs=["query"],
                expected_outputs=["results"],
                supported_adapters=["search_engine"],
            ),
            CapabilityMetadata(
                name="automation",
                description="Operational automation and trigger rules.",
                required_inputs=["trigger_name"],
                expected_outputs=["executed"],
                supported_adapters=["trigger_engine"],
            ),
            CapabilityMetadata(
                name="approval",
                description="Human-in-the-loop owner approval gate.",
                required_inputs=["action_id"],
                expected_outputs=["approved", "status"],
                supported_adapters=["owner_confirm_gate"],
            ),
            CapabilityMetadata(
                name="identity",
                description="Actor identity, authentication, and permission checks.",
                required_inputs=["actor_id", "role"],
                expected_outputs=["authorized"],
                supported_adapters=["policy_guard"],
            ),
        ]

        for meta in defaults:
            if meta.name not in cls._registry:
                actions = [meta.name, f"execute_{meta.name}"]
                cls.register(GenericCapabilityStub(meta, actions))


# Auto-initialize defaults on import
UniversalCapabilityRegistry.initialize_defaults()
