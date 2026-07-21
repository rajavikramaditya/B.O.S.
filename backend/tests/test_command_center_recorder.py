"""Unit tests for Command Center interaction recorder (Phase 1)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

_WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _WORKSPACE not in sys.path:
    sys.path.insert(0, _WORKSPACE)

import database as db
import services.cockpit.recorder as recorder
from services.safety.admin_unlock import SESSION_COOKIE_NAME


class TestCommandCenterRecorder(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._orig_db = db.DB_PATH
        db.DB_PATH = self._tmp.name
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._orig_db
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_start_and_end_session(self):
        session_id = recorder.start_session()
        self.assertTrue(db.command_center_session_is_open(session_id))
        recorder.end_session(session_id, end_reason="lock")
        self.assertFalse(db.command_center_session_is_open(session_id))

    def test_record_turn_persists_understanding_and_reply(self):
        session_id = recorder.start_session()
        result = {
            "reply": "Sir, VM healthy hai.",
            "intent": "station_status",
            "route": "manager_response",
            "action_type": "station_status",
            "policy_decision": "allow_safe_tool",
            "selected_model": "auto",
            "actual_model": "gemini-3.1-flash-lite",
            "protected_action_blocked": "No",
            "timing": {"total_ms": 120},
        }
        turn_id = recorder.record_turn(
            session_id=session_id,
            channel="chat",
            user_input="VM ka status batao",
            result=result,
            selected_model="auto",
            latency_ms=120,
        )
        self.assertIsNotNone(turn_id)
        turns = db.list_command_center_turns(session_id=session_id)
        self.assertEqual(len(turns), 1)
        turn = turns[0]
        self.assertEqual(turn["user_input"], "VM ka status batao")
        self.assertEqual(turn["assistant_reply"], "Sir, VM healthy hai.")
        self.assertEqual(turn["intent"], "station_status")
        self.assertEqual(turn["action_type"], "station_status")
        self.assertEqual(turn["policy_decision"], "allow_safe_tool")
        trace = json.loads(turn["trace_json"])
        self.assertEqual(trace["actual_model"], "gemini-3.1-flash-lite")

    def test_redact_sensitive_text(self):
        raw = "api_key=super-secret-token-12345"
        cleaned = recorder.redact_sensitive_text(raw)
        self.assertNotIn("super-secret-token", cleaned)
        self.assertIn("[redacted]", cleaned)

    def test_build_recent_interaction_bundle(self):
        session_id = recorder.start_session()
        recorder.record_turn(
            session_id=session_id,
            channel="chat",
            user_input="hello neena",
            result={"reply": "Namaste Sir", "intent": "other"},
        )
        bundle = recorder.build_recent_interaction_bundle(session_limit=5, turn_limit=5)
        self.assertEqual(bundle["status"], "success")
        self.assertGreaterEqual(len(bundle["sessions"]), 1)
        self.assertGreaterEqual(len(bundle["recent_turns"]), 1)
        self.assertIn(session_id, bundle["turns_by_session"])

    @patch("services.cockpit.recorder.verify_session_token", return_value=True)
    def test_resolve_session_creates_when_admin_unlocked(self, _mock_verify):
        request = MagicMock()
        request.cookies = {SESSION_COOKIE_NAME: "token", recorder.CC_SESSION_COOKIE: ""}
        session_id, is_new = recorder.resolve_session(request)
        self.assertTrue(is_new)
        self.assertTrue(session_id)
        self.assertTrue(db.command_center_session_is_open(session_id))

    def test_record_whatsapp_customer_includes_phone_in_trace(self):
        result = {
            "reply": "App abhi ready nahi hai.",
            "action_type": "CUSTOMER_CONVERSATION",
            "route": "customer_whatsapp",
            "source": "neena_brain",
            "customer_phone_last10": "9876543210",
            "customer_phone_masked": "+91******3210",
            "customer_sender_name": "Ravi",
            "actual_model": "gemini-3.1-flash-lite",
        }
        turn_id = recorder.record_whatsapp_turn(
            user_input="ad lagwani hai",
            result=result,
            latency_ms=90,
            is_owner=False,
        )
        self.assertIsNotNone(turn_id)
        turns = db.list_command_center_turns(limit=5)
        self.assertGreaterEqual(len(turns), 1)
        turn = turns[0]
        self.assertEqual(turn["channel"], "whatsapp_listener")
        self.assertIn("9876543210", turn["session_id"])
        self.assertIn("[customer Ravi", turn["user_input"])
        self.assertIn("ad lagwani hai", turn["user_input"])
        trace = json.loads(turn["trace_json"])
        self.assertEqual(trace["customer_phone_last10"], "9876543210")
        self.assertEqual(trace["customer_sender_name"], "Ravi")

    def test_record_whatsapp_owner_session_unchanged(self):
        turn_id = recorder.record_whatsapp_turn(
            user_input="status batao",
            result={"reply": "OK Sir", "action_type": "station_status"},
            latency_ms=50,
            is_owner=True,
        )
        self.assertIsNotNone(turn_id)
        turns = db.list_command_center_turns(limit=5)
        turn = turns[0]
        self.assertEqual(turn["channel"], "whatsapp")
        self.assertIn("whatsapp-owner-", turn["session_id"])
        self.assertEqual(turn["user_input"], "status batao")

    def test_agent_loop_steps_land_in_trace_json(self):
        session_id = recorder.start_session()
        result = {
            "reply": "Stream OK | Memory OK",
            "action_type": "station_status",
            "route": "live_ops",
            "agent_loop_steps": [
                {"n": 1, "action": "station_status", "action_type": "STATION_STATUS", "ok": True, "source": "seed"},
                {"n": 2, "action": "memory_status", "action_type": "MEMORY_STATUS", "ok": True, "source": "agent_step"},
            ],
            "factual_packet_digest": "agent_loop steps=station_status:STATION_STATUS,memory_status:MEMORY_STATUS",
            "factual_packet": {
                "tool": "agent_loop",
                "step_count": 2,
                "steps": [
                    {"n": 1, "action": "station_status", "action_type": "STATION_STATUS", "ok": True},
                    {"n": 2, "action": "memory_status", "action_type": "MEMORY_STATUS", "ok": True},
                ],
            },
        }
        turn_id = recorder.record_turn(
            session_id=session_id,
            channel="chat",
            user_input="status deep check",
            result=result,
            latency_ms=200,
        )
        self.assertIsNotNone(turn_id)
        turn = db.list_command_center_turns(session_id=session_id)[0]
        trace = json.loads(turn["trace_json"])
        self.assertEqual(len(trace.get("agent_loop_steps") or []), 2)
        self.assertIn("agent_loop", trace.get("factual_packet_digest") or "")
        self.assertNotIn("packets", trace)  # full packets must not dump into audit

    def test_blocked_and_pending_confirm_outcomes(self):
        session_id = recorder.start_session()
        blocked_id = recorder.record_turn(
            session_id=session_id,
            channel="chat",
            user_input="broadcast now",
            result={
                "reply": "Confirm chahiye",
                "protected_action_blocked": "Yes",
                "approval_blocked_reason": "needs_confirm",
                "action_type": "SEND_AZURACAST_BLOCKED",
            },
        )
        confirm_id = recorder.record_turn(
            session_id=session_id,
            channel="chat",
            user_input="air karo",
            result={
                "reply": "Confirm kariye",
                "require_confirmation": True,
                "action_type": "SEND_AZURACAST_CONFIRM",
            },
        )
        self.assertIsNotNone(blocked_id)
        self.assertIsNotNone(confirm_id)
        turns = {t["id"]: t for t in db.list_command_center_turns(session_id=session_id)}
        self.assertTrue(turns[blocked_id]["blocked"])
        self.assertEqual(turns[blocked_id]["outcome"], "blocked")
        self.assertEqual(turns[confirm_id]["outcome"], "pending_confirm")
        self.assertFalse(bool(turns[confirm_id]["blocked"]))

    def test_record_helpers_channels(self):
        self.assertIsNotNone(
            recorder.record_cockpit_action_turn(
                action="pipeline_status",
                result={"reply": "ok", "handled": True},
            )
        )
        self.assertIsNotNone(
            recorder.record_voice_turn(text="hello", result={"job_id": "vj1", "status": "queued"})
        )
        self.assertIsNotNone(
            recorder.record_broadcast_turn(
                action="send_azuracast",
                capsule_id=42,
                result={"success": True, "status": "ok"},
            )
        )
        self.assertIsNotNone(
            recorder.record_admin_event(
                event="unlock_rejected",
                result={"detail": "Unlock phrase rejected."},
                blocked=True,
                outcome="blocked",
            )
        )
        self.assertIsNotNone(
            recorder.record_probe_turn(
                user_input="probe hello",
                result={"reply": "Namaste", "action_type": "other"},
            )
        )
        ids = recorder.record_job_completion_turns(
            [{"job_id": "job_abc", "action": "verify_latest_stream", "status": "succeeded", "owner_message": "Done"}]
        )
        self.assertEqual(len(ids), 1)
        channels = {t["channel"] for t in db.list_command_center_turns(limit=20)}
        self.assertTrue(
            {"cockpit_action", "cockpit_voice", "broadcast", "admin", "probe", "job_completion"}.issubset(channels)
        )

    def test_bundle_channel_exact_filter(self):
        sid = recorder.start_session()
        recorder.record_turn(session_id=sid, channel="chat", user_input="a", result={"reply": "1"})
        recorder.record_whatsapp_turn(
            user_input="b",
            result={"reply": "2", "action_type": "station_status"},
            is_owner=True,
        )
        recorder.record_whatsapp_turn(
            user_input="c",
            result={
                "reply": "3",
                "customer_phone_last10": "9999999999",
                "customer_phone_masked": "+91******9999",
                "customer_sender_name": "X",
            },
            is_owner=False,
        )
        chat_only = recorder.build_recent_interaction_bundle(turn_limit=10, channel="chat")
        self.assertTrue(all(t["channel"] == "chat" for t in chat_only["recent_turns"]))
        wa_only = recorder.build_recent_interaction_bundle(turn_limit=10, channel="whatsapp")
        self.assertTrue(all(t["channel"] == "whatsapp" for t in wa_only["recent_turns"]))
        self.assertFalse(any(t["channel"] == "whatsapp_listener" for t in wa_only["recent_turns"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
