"""B.O.S. Core Capability Catalog v1.0

Industry-neutral capabilities every business needs. Business modules add more.
Risk levels:  read  — no side effects
              safe  — internal record keeping (contacts, tasks)
              external — reaches people or systems outside the platform
              sensitive — money, deletion, or irreversible effects (always needs a human)
"""

from typing import List

from capabilities.base.base_capability import BaseCapability

from .provider_backed import ProviderBackedCapability, declare_actions

CONTACT_FIELDS = {
    "name": "Full name",
    "phone": "Phone with country code",
    "email": "Email address",
    "channel": "Where they reached us (telegram, whatsapp, email, web, ...)",
    "stage": "lead | prospect | customer | partner | inactive",
    "tags": "List of short labels",
    "notes": "What we learned (needs, budget, timing)",
    "attributes": "Object of extra business-specific fields",
}


def build_core_capabilities() -> List[BaseCapability]:
    return [
        ProviderBackedCapability(
            name="contacts",
            category="crm",
            description="Customers, leads and partners: save, update, look up and list contacts.",
            provider_capability="business_records",
            actions={
                "upsert_contact": {
                    "risk": "safe",
                    "params": {"id": "Existing contact id (optional)", **CONTACT_FIELDS},
                    "self_service": "id",
                },
                "find_contact": {"risk": "read", "params": {"id": "Contact id", "phone": "Phone", "email": "Email"}},
                "list_contacts": {"risk": "read", "params": {"search": "Text to search", "stage": "Filter by stage", "limit": "Max results"}},
            },
        ),
        ProviderBackedCapability(
            name="tasks",
            category="operations",
            description="Follow-ups and to-dos for the business, optionally linked to a contact.",
            provider_capability="business_records",
            actions={
                "create_task": {
                    "risk": "safe",
                    "params": {
                        "title": "Short task title",
                        "description": "Details",
                        "due_at": "ISO-8601 datetime",
                        "contact_id": "Related contact id",
                    },
                    "self_service": "contact_id",
                },
                "complete_task": {"risk": "safe", "params": {"task_id": "Task id"}},
                "list_tasks": {"risk": "read", "params": {"status": "open | done", "limit": "Max results"}},
            },
        ),
        ProviderBackedCapability(
            name="business_context",
            category="system",
            description="Business profile and live operating snapshot.",
            provider_capability="workspace_context",
            planner_visible=False,
            actions={"snapshot": {"risk": "read"}},
        ),
        ProviderBackedCapability(
            name="conversation_memory",
            category="memory",
            description="Conversation history across all channels.",
            provider_capability="conversation_memory",
            planner_visible=False,
            actions={
                "append": {"risk": "safe"},
                "history": {"risk": "read"},
                "list_conversations": {"risk": "read"},
                "get_conversation": {"risk": "read"},
            },
        ),
        ProviderBackedCapability(
            name="integration_events",
            category="integrations",
            description="Publish a business event to connected apps (webhooks, Zapier, Make, n8n, custom systems).",
            provider_capability="event_delivery",
            actions={
                "emit_event": {
                    "risk": "safe",
                    "params": {"event": "Event name, e.g. lead.qualified", "data": "Object with event details"},
                },
            },
        ),
    ]


def declare_reference_capabilities(generate_text: BaseCapability, send_message: BaseCapability) -> None:
    """Expose the reference capabilities to the planner with their risk declarations."""
    declare_actions(
        generate_text,
        {"generate": {"risk": "read"}, "summarize": {"risk": "read"}, "transform": {"risk": "read"}},
        planner_visible=False,
    )
    declare_actions(
        send_message,
        {
            "send": {
                "risk": "external",
                "params": {
                    "channel": "telegram | whatsapp | email (must be connected)",
                    "recipient": "Chat id, phone with country code, or email",
                    "text": "Message body",
                    "subject": "Email subject (email only)",
                },
            },
            "broadcast": {
                "risk": "sensitive",
                "params": {"channel": "Channel", "recipients": "List of recipients", "text": "Message body"},
            },
        },
    )
