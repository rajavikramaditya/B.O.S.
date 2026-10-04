"""B.O.S. Workspace Context Provider v1.0

`workspace_context` provider: business profile, autopilot mode and a live snapshot
of the business (records, approvals, connected channels, current time).
"""

from datetime import datetime, timezone
from typing import Any, Dict

from integrations.connections import ConnectionStore
from workspace.approvals import ApprovalRepository
from workspace.records import ContactRepository, TaskRepository
from workspace.settings_store import BUSINESS_PROFILE, SettingsStore

from ..base.base_provider import BaseProvider
from ..base.provider_context import ProviderContext
from ..base.provider_metadata import ProviderMetadata

WORKSPACE_CONTEXT = "workspace_context"
CHANNEL_CONNECTORS = ("telegram", "whatsapp", "email")


class WorkspaceContextProvider(BaseProvider):
    def __init__(self, priority: int = 10):
        super().__init__(
            ProviderMetadata(
                name="workspace_context",
                capability=WORKSPACE_CONTEXT,
                priority=priority,
                description="Business profile and live snapshot from the workspace.",
            )
        )

    def _on_initialize(self, context: ProviderContext) -> None:
        pass

    def _on_shutdown(self) -> None:
        pass

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action != "snapshot":
            return {"success": False, "error": f"Unsupported context action '{action}'."}
        upcoming = TaskRepository.list("open", limit=8)
        return {
            "success": True,
            "profile": SettingsStore.get(BUSINESS_PROFILE),
            "autopilot_mode": SettingsStore.autopilot_mode(),
            "snapshot": {
                "now": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                "contacts": ContactRepository.stats(),
                "tasks": TaskRepository.stats(),
                "upcoming_tasks": [
                    {"id": t["id"], "title": t["title"], "due_at": t["due_at"], "contact_id": t["contact_id"]} for t in upcoming
                ],
                "pending_approvals": [
                    {"title": a["title"], "created_at": a["created_at"]} for a in ApprovalRepository.list("pending", limit=10)
                ],
                "connected_channels": [c for c in CHANNEL_CONNECTORS if ConnectionStore.is_connected(c)],
            },
        }
