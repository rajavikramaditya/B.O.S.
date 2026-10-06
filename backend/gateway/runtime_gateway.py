"""B.O.S. Runtime Gateway v1.0

The single entrance every interface uses to reach the Runtime: dashboard chat,
messaging channels, the public API, the MCP server and Autopilot.

It submits requests to BOSRuntimeEngine and turns the outcome into platform
effects: approval requests, the activity feed, webhook events and channel replies.
It holds no business logic of its own.
"""

from typing import Any, Dict, List, Optional

from capabilities.base.capability_context import CapabilityContext
from capabilities.resolver import CapabilityResolver
from integrations.webhooks import WebhookDispatcher
from runtime.engine import BOSRuntimeEngine
from workspace.activity import ActivityLog
from workspace.approvals import ApprovalRepository

# Platform events derived from verified step results (capability.action → event type).
STEP_EVENTS = {
    "contacts.upsert_contact": "contact.saved",
    "tasks.create_task": "task.created",
    "tasks.complete_task": "task.completed",
}


class RuntimeGateway:
    """Submits work to the Runtime and applies its verified outcome."""

    @classmethod
    def submit(
        cls,
        *,
        role: str,
        message: str,
        channel: str,
        conversation_id: str,
        sender_name: str = "",
        actor_ref: str = "",
        raw_payload: Optional[Dict[str, Any]] = None,
        source: str = "chat",
        preapproved: bool = False,
        grants: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        result = BOSRuntimeEngine.execute(
            role=role,
            message=message,
            sender_name=sender_name or ("Owner" if role == "owner" else "Guest"),
            channel=channel,
            raw_payload=raw_payload or {},
            conversation_id=conversation_id,
            actor_ref=actor_ref,
            preapproved=preapproved,
            grants=grants,
        )
        result["approvals"] = cls._open_approvals(result.get("pending_steps", []), source, conversation_id)
        cls._record_effects(result, channel=channel, role=role, sender_name=sender_name, message=message)
        return result

    @classmethod
    def approve(cls, approval_id: str) -> Dict[str, Any]:
        claimed = ApprovalRepository.claim_pending(approval_id, "running")
        if claimed is None:
            current = ApprovalRepository.get(approval_id)
            return {"ok": False, "error": "Approval not found." if current is None else f"Approval is already {current['status']}."}

        step = {
            "capability": claimed["capability"],
            "action": claimed["action"],
            "params": claimed["params"],
            "title": claimed["title"],
            "reason": claimed["rationale"],
        }
        result = BOSRuntimeEngine.execute(
            role="owner",
            message=f"Owner approved: {claimed['title']}",
            channel="approvals",
            raw_payload={"plan": [step]},
            conversation_id="approvals",
            preapproved=True,
        )
        executed = result.get("executed_steps") or []
        ok = bool(executed) and all(s.get("success") for s in executed)
        error = None if ok else (executed[0].get("error") if executed else "The step could not run.")
        updated = ApprovalRepository.set_status(
            approval_id, "executed" if ok else "failed", {"steps": executed, "error": error}
        )
        cls._record_effects(result, channel="approvals", role="owner", sender_name="Owner", message="")
        ActivityLog.record("approval.executed" if ok else "approval.failed", claimed["title"], {"approval_id": approval_id, "error": error})
        WebhookDispatcher.publish("approval.decided", {"approval": updated, "decision": "approved", "success": ok})
        return {"ok": ok, "approval": updated, "error": error}

    @classmethod
    def reject(cls, approval_id: str) -> Dict[str, Any]:
        updated = ApprovalRepository.claim_pending(approval_id, "rejected")
        if updated is None:
            return {"ok": False, "error": "Approval not found or already decided."}
        ActivityLog.record("approval.rejected", updated["title"], {"approval_id": approval_id})
        WebhookDispatcher.publish("approval.decided", {"approval": updated, "decision": "rejected"})
        return {"ok": True, "approval": updated}

    @classmethod
    def identify_contact(cls, *, channel: str, external_id: str, name: str = "", phone: str = "", email: str = "") -> str:
        """Find or create the contact behind an inbound channel identity; returns its id."""
        result = CapabilityResolver.execute(
            "contacts",
            "upsert_contact",
            {
                "channel": channel,
                "external_id": f"{channel}:{external_id}",
                "name": name,
                "phone": phone,
                "email": email,
                # Phone/email here are self-reported, so they must never select an existing record.
                "match_on": ["external_id"],
            },
            CapabilityContext(module_id="gateway"),
        )
        contact = (result.data or {}).get("contact") or {}
        if contact.get("created"):
            ActivityLog.record("contact.new", f"New contact via {channel}: {name or external_id}", {"contact_id": contact.get("id")})
            WebhookDispatcher.publish("contact.saved", {"contact": contact})
        return str(contact.get("id") or "")

    @classmethod
    def deliver_reply(cls, *, channel: str, recipient: str, text: str) -> bool:
        """Send the Runtime's reply back on the channel the person used."""
        if not text or not recipient:
            return False
        result = CapabilityResolver.execute(
            "send_message",
            "send",
            {"channel": channel, "recipient": recipient, "text": text},
            CapabilityContext(module_id="gateway"),
        )
        delivered = bool(result.success and (result.data or {}).get("success"))
        if not delivered:
            ActivityLog.record("channel.delivery_failed", f"Reply on {channel} failed", {"error": result.error or (result.data or {}).get("error")})
        return delivered

    @classmethod
    def _open_approvals(cls, pending: List[Dict[str, Any]], source: str, conversation_id: str) -> List[Dict[str, Any]]:
        created = []
        for step in pending:
            approval = ApprovalRepository.create(step, source=source, conversation_id=conversation_id)
            created.append(approval)
            ActivityLog.record("approval.requested", approval["title"], {"approval_id": approval["id"], "source": source})
            WebhookDispatcher.publish("approval.requested", {"approval": approval})
        return created

    @classmethod
    def _record_effects(cls, result: Dict[str, Any], *, channel: str, role: str, sender_name: str, message: str) -> None:
        for step in result.get("executed_steps") or []:
            if not step.get("success") or step.get("risk") == "read":
                continue
            key = f"{step['capability']}.{step['action']}"
            ActivityLog.record("action.executed", step.get("title") or key, {"capability": step["capability"], "action": step["action"]})
            WebhookDispatcher.publish("action.executed", {"step": step})
            if key in STEP_EVENTS:
                WebhookDispatcher.publish(STEP_EVENTS[key], step.get("data") or {})

        if role in ("customer", "employee") and message:
            payload = {"channel": channel, "sender": sender_name, "conversation_id": result.get("conversation_id")}
            WebhookDispatcher.publish("conversation.message.received", {**payload, "text": message})
            if result.get("reply"):
                WebhookDispatcher.publish("conversation.reply.sent", {**payload, "text": result["reply"]})
