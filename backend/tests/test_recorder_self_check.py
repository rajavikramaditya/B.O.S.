"""Owner read-only interaction recorder self-check + live-ops packet-flow."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch


class TestRecorderReviewService(unittest.TestCase):
    def test_build_recorder_review_returns_factual_packet_not_owner_speech(self):
        from services.brain.recorder_review import build_recorder_review

        fake_rows = [
            {
                "id": 10,
                "created_at": "2026-07-10",
                "channel": "whatsapp",
                "action_type": "SEND_AZURACAST_CONFIRM",
                "user_input": "Ha kr do",
                "assistant_reply": "Confirm kariye",
                "trace_json": (
                    '{"reached_interpreter": false, "pending_cleared_without_execute": true, '
                    '"short_circuit_reason": null}'
                ),
            }
        ]
        with patch("database.list_command_center_turns", return_value=fake_rows):
            out = build_recorder_review(limit=5)
        self.assertTrue(out.get("success"))
        self.assertTrue(out.get("read_only"))
        self.assertIn("pending_cleared_without_execute", out.get("findings") or [])
        packet = out.get("factual_packet") or {}
        self.assertEqual(packet.get("tool"), "check_interaction_recorder")
        self.assertEqual(packet.get("mode"), "read_only")
        reply = out.get("reply") or ""
        self.assertNotIn("sir,", reply.lower())
        parsed = json.loads(reply)
        self.assertEqual(parsed.get("tool"), "check_interaction_recorder")
        self.assertNotIn("api_key", reply.lower())

    def test_live_ops_check_interaction_recorder(self):
        from services.brain.live_ops_executor import try_execute_live_ops

        with patch("services.brain.feature_flags.recorder_self_check_enabled", return_value=True), \
             patch(
                 "services.brain.recorder_review.build_recorder_review",
                 return_value={
                     "success": True,
                     "read_only": True,
                     "turn_count": 1,
                     "findings": ["confirm_theatre"],
                     "reply": json.dumps({"tool": "check_interaction_recorder"}),
                     "factual_packet": {"tool": "check_interaction_recorder", "mode": "read_only"},
                 },
             ):
            res = try_execute_live_ops("check_interaction_recorder", {"limit": 8}, snapshot={})
        self.assertIsNotNone(res)
        self.assertEqual(res.get("action_type"), "RECORDER_CHECK")
        self.assertTrue(res.get("read_only"))
        self.assertEqual((res.get("factual_packet") or {}).get("tool"), "check_interaction_recorder")
        self.assertNotIn("sir,", (res.get("reply") or "").lower())

    def test_recorder_check_is_humanized_by_composer(self):
        from services.brain.response_composer import _HUMANIZE_ACTION_TYPES, maybe_humanize_report

        self.assertIn("RECORDER_CHECK", _HUMANIZE_ACTION_TYPES)
        with patch(
            "services.brain.conversation.humanize_factual_reply",
            return_value="Sir, recorder me 3 turns mile; ek pending clear bina execute ke dikha.",
        ) as mock_h:
            out = maybe_humanize_report(
                "recorder check karo",
                "Recorder read-only: 3 turns.",
                "RECORDER_CHECK",
                factual_packet={"tool": "check_interaction_recorder", "turn_count": 3},
            )
        mock_h.assert_called_once()
        self.assertIn("recorder", out.lower())
        # humanize input should be packet JSON, not the short fallback alone
        args, kwargs = mock_h.call_args
        factual = kwargs.get("factual_text") or (args[0] if args else "")
        self.assertIn("check_interaction_recorder", factual)

    def test_flag_off_disables_check(self):
        from services.brain.live_ops_executor import try_execute_live_ops

        with patch("services.brain.feature_flags.recorder_self_check_enabled", return_value=False):
            res = try_execute_live_ops("check_interaction_recorder", {}, snapshot={})
        self.assertEqual(res.get("action_type"), "RECORDER_CHECK_DISABLED")

    def test_channel_filter_is_exact_not_prefix(self):
        from services.brain.recorder_review import build_recorder_review

        fake_rows = [
            {
                "id": 1,
                "created_at": "2026-07-12",
                "channel": "whatsapp",
                "action_type": "station_status",
                "user_input": "status",
                "assistant_reply": "ok",
                "trace_json": "{}",
            },
            {
                "id": 2,
                "created_at": "2026-07-12",
                "channel": "whatsapp_listener",
                "action_type": "CUSTOMER_CONVERSATION",
                "user_input": "hello",
                "assistant_reply": "ji",
                "trace_json": "{}",
            },
        ]
        with patch("database.list_command_center_turns", return_value=fake_rows):
            out = build_recorder_review(limit=10, channel="whatsapp")
        channels = {t["channel"] for t in out.get("turns") or []}
        self.assertEqual(channels, {"whatsapp"})
        self.assertNotIn("whatsapp_listener", channels)


class TestLiveOpsPacketFlow(unittest.TestCase):
    def test_send_azuracast_confirm_is_factual_packet(self):
        from services.brain.live_ops_executor import try_execute_live_ops

        snap = {
            "latest_ready_for_azuracast": {"id": 9, "azuracast_push_allowed": True},
            "latest_capsules": [],
        }
        res = try_execute_live_ops("send_azuracast", {}, snapshot=snap)
        self.assertEqual(res.get("action_type"), "SEND_AZURACAST_CONFIRM")
        self.assertTrue(res.get("require_confirmation"))
        self.assertEqual(res.get("capsule_id"), 9)
        packet = res.get("factual_packet") or {}
        self.assertEqual(packet.get("tool"), "send_azuracast")
        self.assertTrue(packet.get("owner_must_confirm"))
        self.assertNotIn("sir,", (res.get("reply") or "").lower())

    def test_approve_confirm_is_factual_packet(self):
        from services.brain.live_ops_executor import try_execute_live_ops

        snap = {
            "latest_pending_capsule": {"id": 7, "approval_queue_id": 70, "status": "pending_approval"},
            "latest_capsules": [
                {"id": 7, "approval_status": "pending", "status": "pending_approval"},
            ],
        }
        res = try_execute_live_ops("approve_latest_script", {"needs_confirmation": True}, snapshot=snap)
        self.assertEqual(res.get("action_type"), "APPROVE_CONFIRM")
        self.assertTrue(res.get("require_confirmation"))
        self.assertNotIn("sir,", (res.get("reply") or "").lower())
        self.assertEqual((res.get("factual_packet") or {}).get("capsule_id"), 7)

    def test_humanize_live_ops_flag_off_skips_llm(self):
        from services.brain.response_composer import maybe_humanize_report

        with patch("services.brain.feature_flags.humanize_live_ops_enabled", return_value=False), \
             patch("services.brain.conversation.humanize_factual_reply") as mock_h:
            out = maybe_humanize_report(
                "push karo",
                "Confirm required: AzuraCast push capsule #9.",
                "SEND_AZURACAST_CONFIRM",
                factual_packet={"tool": "send_azuracast", "status": "needs_confirmation"},
            )
        mock_h.assert_not_called()
        self.assertIn("Confirm required", out)

    def test_humanize_live_ops_uses_packet_when_flag_on(self):
        from services.brain.response_composer import maybe_humanize_report

        with patch("services.brain.feature_flags.humanize_live_ops_enabled", return_value=True), \
             patch(
                 "services.brain.conversation.humanize_factual_reply",
                 return_value="Capsule 9 push ke liye confirm chahiye.",
             ) as mock_h:
            out = maybe_humanize_report(
                "push karo",
                "Confirm required: AzuraCast push capsule #9.",
                "SEND_AZURACAST_CONFIRM",
                factual_packet={"tool": "send_azuracast", "capsule_id": 9},
            )
        mock_h.assert_called_once()
        self.assertIn("confirm", out.lower())

    def test_list_pending_no_sir(self):
        from services.brain.live_ops_executor import try_execute_live_ops

        with patch(
            "services.broadcast.capsule_service.list_recent_capsules",
            return_value=[{"id": 3, "status": "pending_approval", "title": "RJ"}],
        ):
            res = try_execute_live_ops("list_pending_capsules", {}, snapshot={})
        self.assertEqual(res.get("action_type"), "LIST_PENDING_CAPSULES")
        self.assertNotIn("sir,", (res.get("reply") or "").lower())
        self.assertEqual((res.get("factual_packet") or {}).get("count"), 1)

    def test_recommendation_no_sir(self):
        from services.brain.live_ops_executor import try_execute_live_ops

        res = try_execute_live_ops(
            "what_should_i_do_now",
            {},
            snapshot={
                "pending_scripts_count": 0,
                "stream": "online",
                "recommended_next_action": "create_script",
                "latest_capsules": [],
            },
        )
        self.assertEqual(res.get("action_type"), "LIVE_RECOMMENDATION")
        self.assertNotIn("sir,", (res.get("reply") or "").lower())
        self.assertEqual((res.get("factual_packet") or {}).get("tool"), "what_should_i_do_now")


if __name__ == "__main__":
    unittest.main()
