"""B.O.S. Autopilot Engine v1.0

The proactive heart of B.O.S.: instead of waiting for orders, it periodically
reviews the whole business through the Runtime, acts on safe opportunities,
queues risky ones for approval, and writes the owner a short briefing.

Every review is an ordinary Runtime request (role "system"), so Policy,
Verification and Memory apply exactly as they do to a chat message.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from gateway.runtime_gateway import RuntimeGateway
from integrations.webhooks import WebhookDispatcher
from workspace.activity import ActivityLog
from workspace.database import WorkspaceDatabase
from workspace.models import AutopilotRun
from workspace.settings_store import SettingsStore

REVIEW_INSTRUCTION = """\
Run a proactive business review now.

1. Study the business profile and snapshot: open and overdue tasks, new and silent contacts,
   items waiting on approval, connected channels, and anything incomplete in the setup.
2. Decide the few actions that would most move the business forward today — follow-ups with
   leads, reminders, clean-up of records, outreach drafts — and plan them as steps.
   Prefer concrete actions over advice. Do not re-plan anything already waiting for approval.
3. Write the reply as a short briefing for the owner: what you noticed, what you did,
   what needs their decision, and the single most important thing for them to do next.
4. Put notable risks and opportunities in insights."""


def run_to_dict(r: AutopilotRun) -> Dict[str, Any]:
    return {
        "id": r.id,
        "trigger": r.trigger,
        "status": r.status,
        "summary": r.summary,
        "insights": r.insights or [],
        "executed": r.executed or [],
        "pending_approvals": r.pending_approvals or [],
        "error": r.error,
        "started_at": r.started_at,
        "finished_at": r.finished_at,
    }


# Autopilot reads text customers wrote (task titles, notes), so it runs unattended only within these
# grants: it reads records and adds follow-up tasks; changing contacts, closing tasks or emitting
# events waits for the owner, and messages still follow the autonomy level.
AUTOPILOT_GRANTS = ("contacts:read", "tasks:read", "business_context:read", "tasks.create_task", "send_message")


class AutopilotEngine:
    """Runs proactive reviews and keeps their history."""

    @classmethod
    def run(cls, trigger: str = "manual") -> Dict[str, Any]:
        with WorkspaceDatabase.session() as db:
            record = AutopilotRun(trigger=trigger)
            db.add(record)
            db.flush()
            run_id = record.id

        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            result = RuntimeGateway.submit(
                role="system",
                message=REVIEW_INSTRUCTION,
                channel="autopilot",
                conversation_id=f"autopilot:{day}",
                sender_name="Autopilot",
                source="autopilot",
                grants=list(AUTOPILOT_GRANTS),
            )
            status = "completed" if result.get("ai_available") else "skipped"
            error = "" if result.get("ai_available") else "AI model is not connected."
            values = {
                "status": status,
                "summary": result.get("reply", ""),
                "insights": result.get("insights", []),
                "executed": [
                    {"title": s.get("title"), "success": s.get("success"), "error": s.get("error")}
                    for s in result.get("executed_steps", [])
                ],
                "pending_approvals": [a["id"] for a in result.get("approvals", [])],
                "error": error,
            }
        except Exception as ex:  # keep the scheduler alive whatever happens
            values = {"status": "failed", "error": str(ex)}

        with WorkspaceDatabase.session() as db:
            record = db.get(AutopilotRun, run_id)
            for key, value in values.items():
                setattr(record, key, value)
            record.finished_at = time.time()
            out = run_to_dict(record)

        if out["status"] == "completed":
            ActivityLog.record("autopilot.briefing", "Autopilot finished a business review", {"run_id": run_id})
            WebhookDispatcher.publish("autopilot.briefing.ready", out)
        return out

    @classmethod
    def latest(cls) -> Optional[Dict[str, Any]]:
        with WorkspaceDatabase.session() as db:
            row = db.scalars(
                select(AutopilotRun).where(AutopilotRun.status == "completed").order_by(AutopilotRun.started_at.desc()).limit(1)
            ).first()
            return run_to_dict(row) if row else None

    @classmethod
    def history(cls, limit: int = 20) -> List[Dict[str, Any]]:
        with WorkspaceDatabase.session() as db:
            rows = db.scalars(select(AutopilotRun).order_by(AutopilotRun.started_at.desc()).limit(limit)).all()
            return [run_to_dict(r) for r in rows]

    @classmethod
    def is_due(cls, interval_minutes: int) -> bool:
        if SettingsStore.autopilot_mode() == "off":
            return False
        with WorkspaceDatabase.session() as db:
            last = db.scalars(select(AutopilotRun).order_by(AutopilotRun.started_at.desc()).limit(1)).first()
        return last is None or (time.time() - last.started_at) >= interval_minutes * 60
