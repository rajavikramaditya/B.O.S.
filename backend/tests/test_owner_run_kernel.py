"""W0/W1: truth gate + owner run kernel + now_playing routing."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestTruthGate(unittest.TestCase):
    def test_deferred_ask_reason(self):
        from services.agent.truth_gate import unavailable_action_reason
        import os

        os.environ["NEENA_DEFERRED_STATUS"] = "0"
        try:
            self.assertEqual(
                unavailable_action_reason("5 min baad WhatsApp pe status bhej dena"),
                "deferred_followthrough_not_armed",
            )
        finally:
            os.environ["NEENA_DEFERRED_STATUS"] = "1"
        self.assertEqual(
            unavailable_action_reason("diagnostics pause kar do"),
            "no_pause_diagnostics_tool",
        )
        self.assertIsNone(unavailable_action_reason("ab kya chal raha hai"))

    def test_scrub_fake_timer_without_facts(self):
        from services.agent.truth_gate import enforce_truth_on_reply
        import os

        os.environ["NEENA_DEFERRED_STATUS"] = "0"
        try:
            reply, pkt = enforce_truth_on_reply(
                "5 min baad WhatsApp pe status bhej dena",
                "Sir, timer set kar diya, 5 minute me bhej dungi.",
                factual_packet=None,
            )
        finally:
            os.environ["NEENA_DEFERRED_STATUS"] = "1"
        self.assertIn("timer", reply.lower())
        self.assertIsNotNone(pkt)
        self.assertEqual(pkt.get("status"), "cannot")

    def test_keep_reply_when_facts_present(self):
        from services.agent.truth_gate import enforce_truth_on_reply

        text, pkt = enforce_truth_on_reply(
            "station status",
            "Stream online.",
            factual_packet={"tool": "station_status", "status": "ok"},
        )
        self.assertEqual(text, "Stream online.")
        self.assertIsNone(pkt)

    def test_scrub_fake_customer_outbound_without_tool(self):
        from services.agent.truth_gate import enforce_truth_on_reply

        reply, pkt = enforce_truth_on_reply(
            "Sneha ko message kro pucho kya vo theek hai",
            "Sir, main abhi Sneha ko message bhejti hoon. "
            "Main abhi `send_whatsapp_message` tool use karke ye message bhej rahi hoon.",
            factual_packet=None,
        )
        self.assertIn("customer", reply.lower())
        self.assertEqual(pkt.get("reason"), "no_customer_outbound_tool")
        self.assertNotIn("nahi bolungi", reply.lower())
        self.assertLess(len(reply), 100)

    def test_scrub_empty_customer_claim_hands_off_recall(self):
        from services.agent.truth_gate import NEEDS_CUSTOMER_RECALL, enforce_truth_on_reply

        reply, pkt = enforce_truth_on_reply(
            "Batayo koi customer se bat hui ajj ??",
            "Sir, abhi tak mere paas koi naya customer message nahi aaya hai.",
            factual_packet=None,
        )
        self.assertEqual(pkt.get("reason"), NEEDS_CUSTOMER_RECALL)
        self.assertIn("check", reply.lower())
        self.assertNotIn("jhoot", reply.lower())
        self.assertNotIn("nahi bolungi", reply.lower())

    def test_hello_empty_customer_claim_not_scrubbed(self):
        from services.agent.truth_gate import enforce_truth_on_reply

        text, pkt = enforce_truth_on_reply(
            "Hello neena",
            "Hello Sir! Abhi koi naya customer message nahi aaya.",
            factual_packet=None,
        )
        self.assertIsNone(pkt)
        self.assertIn("Hello", text)

    def test_allow_empty_claim_when_recall_packet_checked(self):
        from services.agent.truth_gate import enforce_truth_on_reply

        text, pkt = enforce_truth_on_reply(
            "Batayo koi customer se bat hui ajj ??",
            "Checked — aaj IST window me koi customer message nahi aaya.",
            factual_packet={
                "tool": "customer_whatsapp_recall",
                "status": "empty",
                "checked": True,
            },
        )
        self.assertEqual(text[:7], "Checked")
        self.assertIsNone(pkt)

    def test_scrub_audio_generate_claim_without_packet(self):
        from services.agent.truth_gate import enforce_truth_on_reply

        reply, pkt = enforce_truth_on_reply(
            "capsule audio dobara try karo",
            "Sir, main abhi audio generate kar rahi hoon, command bhej diya.",
            factual_packet=None,
        )
        self.assertIn("tool", reply.lower())
        self.assertEqual(pkt.get("reason"), "work_claim_without_facts")
        self.assertNotIn("invent", reply.lower())
        self.assertLess(len(reply), 90)

    def test_allow_audio_claim_when_job_packet_present(self):
        from services.agent.truth_gate import enforce_truth_on_reply

        text, pkt = enforce_truth_on_reply(
            "capsule audio generate karo",
            "Audio job queue me hai, job_id=abc.",
            factual_packet={
                "tool": "generate_audio",
                "status": "accepted",
                "job_id": "abc",
            },
        )
        self.assertIn("job_id", text)
        self.assertIsNone(pkt)

    def test_scrub_commitment_theatre_without_facts(self):
        from services.agent.truth_gate import enforce_truth_on_reply

        reply, pkt = enforce_truth_on_reply(
            "ye kaam ho jayega?",
            "Sir, main abhi kar dungi, ho jayega.",
            factual_packet=None,
        )
        self.assertIn("tool", reply.lower())
        self.assertEqual(pkt.get("reason"), "no_tool_result")
        self.assertNotIn("invent", reply.lower())
        self.assertLess(len(reply), 90)

    def test_chat_grammar_kar_rahi_not_scrubbed(self):
        from services.agent.truth_gate import enforce_truth_on_reply

        text, pkt = enforce_truth_on_reply(
            "kaise ho",
            "Sir, main bilkul theek hoon — aapse baat kar rahi hoon.",
            factual_packet=None,
        )
        self.assertIn("baat kar rahi", text)
        self.assertIsNone(pkt)


class TestRunKernel(unittest.TestCase):
    def test_cannot_on_deferred_before_tools(self):
        from services.agent.run_kernel import run_owner_kernel
        import os

        os.environ["NEENA_DEFERRED_STATUS"] = "0"
        try:
            out = run_owner_kernel(
                message="5 min baad status WhatsApp pe bhejo",
                interpreter_packet={"action": "unknown", "slots": {}},
                selected_model="test",
                mem_packet={},
                mem_context="",
                tb=MagicMock(),
            )
        finally:
            os.environ["NEENA_DEFERRED_STATUS"] = "1"
        self.assertIsNotNone(out)
        self.assertEqual(out.get("action_type"), "CANNOT")
        self.assertIn("timer", out.get("reply", "").lower())
        self.assertNotIn("Cannot:", out.get("reply", ""))
        self.assertEqual(out["factual_packet"].get("tool"), "truth_gate")

    def test_should_enter_for_now_playing(self):
        from services.agent.run_kernel import should_enter_kernel

        self.assertTrue(should_enter_kernel("now_playing", "ab kya chal raha"))
        self.assertFalse(should_enter_kernel("conversation", "hello"))
        import os

        os.environ["NEENA_DEFERRED_STATUS"] = "0"
        try:
            self.assertTrue(should_enter_kernel("unknown", "timer set kar do 5 min status"))
        finally:
            os.environ["NEENA_DEFERRED_STATUS"] = "1"

    def test_now_playing_via_live_ops_fallback(self):
        from services.agent.run_kernel import run_owner_kernel

        fake_ops = {
            "reply": "Now playing: Test Song",
            "action_type": "NOW_PLAYING",
            "factual_packet": {
                "tool": "now_playing",
                "now_playing_title": "Test Song",
                "now_playing_artist": "Artist",
                "status": "ok",
            },
        }
        with patch(
            "services.brain.operations_workflows.try_handle_interpreter_packet",
            return_value=None,
        ), patch(
            "services.tools.live_ops_executor.try_execute_live_ops",
            return_value=fake_ops,
        ), patch(
            "services.tools.loop.extend_live_ops_result",
            side_effect=lambda **kw: kw["first_result"],
        ):
            out = run_owner_kernel(
                message="ab kya chal raha hai",
                interpreter_packet={"action": "now_playing", "slots": {}},
                selected_model="test",
                mem_packet={},
                mem_context="",
                tb=MagicMock(),
                live_snapshot={},
            )
        self.assertIsNotNone(out)
        self.assertEqual(out.get("action_type"), "NOW_PLAYING")
        self.assertIn("owner_run", out)
        self.assertEqual(out["owner_run"].get("status"), "verified")

    def test_empty_act_becomes_cannot(self):
        from services.agent.run_kernel import run_owner_kernel

        weak = {
            "reply": "Sir, main abhi audio generate kar rahi hoon.",
            "action_type": "GENERATE_AUDIO",
        }
        with patch(
            "services.agent.run_kernel._catalog_ids",
            return_value={"generate_audio"},
        ), patch(
            "services.brain.operations_workflows.try_handle_interpreter_packet",
            return_value=weak,
        ), patch(
            "services.tools.live_ops_executor.try_execute_live_ops",
            return_value=None,
        ), patch(
            "services.tools.loop.extend_live_ops_result",
            side_effect=lambda **kw: kw["first_result"],
        ):
            out = run_owner_kernel(
                message="audio dobara try karo",
                interpreter_packet={"action": "generate_audio", "slots": {}},
                selected_model="test",
                mem_packet={},
                mem_context="",
                tb=MagicMock(),
                live_snapshot={},
            )
        self.assertIsNotNone(out)
        self.assertEqual(out.get("action_type"), "CANNOT")
        self.assertIn("tool", out.get("reply", "").lower())
        self.assertNotIn("Cannot:", out.get("reply", ""))
        self.assertEqual(out["factual_packet"].get("reason"), "no_tool_result")


class TestNowPlayingRoute(unittest.TestCase):
    def test_now_playing_not_phrase_nlu(self):
        """AGENTS hygiene: now_playing is interpreter+catalog, not phrase gate."""
        from services.brain.deterministic_routes import resolve_deterministic_action

        self.assertIsNone(resolve_deterministic_action("ab kya chal raha hai radio pe"))

    def test_live_ops_now_playing_packet(self):
        from services.tools.live_ops_executor import try_execute_live_ops

        with patch(
            "services.broadcast.azuracast_client.get_azuracast_status",
            return_value={
                "now_playing_title": "Mandi Update",
                "now_playing_artist": "Neena",
                "stream_reachable": True,
            },
        ):
            out = try_execute_live_ops("now_playing", {}, snapshot={}, owner_message="np")
        self.assertIsNotNone(out)
        self.assertEqual(out.get("action_type"), "NOW_PLAYING")
        self.assertEqual(out["factual_packet"]["now_playing_title"], "Mandi Update")
        self.assertEqual(out["factual_packet"]["managed_target"], "azuracast")


class TestSystemPackIdentity(unittest.TestCase):
    def test_pack_identity_and_kernel(self):
        import services.agent.system_knowledge_pack as sk

        with patch.object(sk.feature_flags, "system_knowledge_pack_enabled", return_value=True):
            text = sk.system_knowledge_pack_text()
        self.assertIn("SEPARATE agent PRODUCT", text)
        self.assertIn("Owner Run Kernel", text)
        self.assertIn("Cannot", text)
        self.assertIn("Ada-style", text)
        self.assertEqual(sk.PACK_VERSION, "2026-07-18.v10")
        self.assertIn("arm_deferred_status", text)


if __name__ == "__main__":
    unittest.main()
