"""B.O.S. Workspace Records Provider v1.0

`business_records` provider backed by the workspace business database.

Actions:
    upsert_contact  {name?, phone?, email?, channel?, external_id?, stage?, tags?, notes?, attributes?}
    find_contact    {id? | phone? | email? | external_id?}
    list_contacts   {search?, stage?, limit?}
    create_task     {title, description?, due_at?, contact_id?}
    complete_task   {task_id}
    list_tasks      {status?, limit?}
    summary         {}
"""

from typing import Any, Dict

from workspace.records import ContactRepository, TaskRepository

from ..base.base_provider import BaseProvider
from ..base.provider_context import ProviderContext
from ..base.provider_metadata import ProviderMetadata

BUSINESS_RECORDS = "business_records"


class WorkspaceRecordsProvider(BaseProvider):
    def __init__(self, priority: int = 10):
        super().__init__(
            ProviderMetadata(
                name="workspace_records",
                capability=BUSINESS_RECORDS,
                priority=priority,
                description="Contacts and tasks stored in the workspace database.",
            )
        )

    def _on_initialize(self, context: ProviderContext) -> None:
        pass

    def _on_shutdown(self) -> None:
        pass

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "upsert_contact":
            contact = ContactRepository.upsert(params)
            return {"success": True, "contact": contact}
        if action == "find_contact":
            contact = ContactRepository.find(params)
            return {"success": contact is not None, "contact": contact, "error": None if contact else "Contact not found."}
        if action == "list_contacts":
            items = ContactRepository.list(str(params.get("search") or ""), str(params.get("stage") or ""), int(params.get("limit") or 50))
            return {"success": True, "contacts": items}
        if action == "create_task":
            return {"success": True, "task": TaskRepository.create(params)}
        if action == "complete_task":
            task = TaskRepository.complete(str(params.get("task_id") or ""))
            return {"success": task is not None, "task": task, "error": None if task else "Task not found."}
        if action == "list_tasks":
            return {"success": True, "tasks": TaskRepository.list(str(params.get("status", "open")), int(params.get("limit") or 50))}
        if action == "summary":
            return {"success": True, "contacts": ContactRepository.stats(), "tasks": TaskRepository.stats()}
        return {"success": False, "error": f"Unsupported records action '{action}'."}
