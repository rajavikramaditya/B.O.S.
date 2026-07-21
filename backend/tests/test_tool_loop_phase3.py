"""Phase 6 agent loop — LLM mid-step chooser (replaces next_step / mini_plan)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestAgentStepNormalize(unittest.TestCase):
    def test_unsafe_continue_becomes_done(self):
        from services.agent.step import _normalize_decision

        got = _normalize_decision(
            {"decision": "continue", "action": "send_azuracast", "slots": {}, "reason": "x"}
        )
        self.assertEqual(got["decision"], "done")
        self.assertIsNone(got["action"])

    def test_safe_continue(self):
        from services.agent.step import _normalize_decision

        got = _normalize_decision(
            {"decision": "continue", "action": "station_status", "slots": {"a": 1}, "reason": "need"}
        )
        self.assertEqual(got["decision"], "continue")
        self.assertEqual(got["action"], "station_status")
        self.assertEqual(got["slots"], {"a": 1})

    def test_invalid_json_fail_closed(self):
        from services.agent.step import _normalize_decision

        got = _normalize_decision(None)
        self.assertEqual(got["decision"], "done")


class TestAgentToolLoop(unittest.TestCase):
    def test_disabled_passthrough(self):
        import services.tools.loop as tl

        first = {"reply": "a", "action_type": "X", "factual_packet": {"next_step": "station_status"}}
        with patch.object(tl.feature_flags, "bounded_tool_loop_enabled", return_value=False), patch.object(
            tl.feature_flags, "deep_agent_loop_enabled", return_value=False
        ):
            out = tl.extend_live_ops_result(
                message="x", first_result=first, first_action="pipeline_status", tb=MagicMock()
            )
        self.assertIs(out, first)

    def test_llm_continue_then_done(self):
        import services.tools.loop as tl

        first = {
            "reply": "pipeline ok",
            "action_type": "PIPELINE_STATUS",
            "factual_packet": {"tool": "pipeline"},
            "ok": True,
        }
        second = {
            "reply": "do capsule next",
            "action_type": "LIVE_RECOMMENDATION",
            "factual_packet": {"tool": "recommend"},
            "ok": True,
        }
        choices = [
            {"decision": "continue", "action": "what_should_i_do_now", "slots": {}, "reason": "need"},
            {"decision": "done", "action": None, "slots": {}, "reason": "enough"},
        ]
        tb = MagicMock()
        with patch.object(tl.feature_flags, "bounded_tool_loop_enabled", return_value=True), patch.object(
            tl.feature_flags, "deep_agent_loop_enabled", return_value=False
        ), patch.object(tl, "choose_next_agent_step", side_effect=choices), patch.object(
            tl, "_execute_followup", return_value=second
        ), patch.object(tl, "_try_synthesize_reply", return_value="Sir, pipeline theek; agla capsule approve."), patch.object(
            tl, "_max_steps", return_value=5
        ), patch(
            "services.brain.live_state_snapshot.build_neena_live_state_snapshot",
            return_value={},
        ):
            out = tl.extend_live_ops_result(
                message="kya karun",
                first_result=dict(first),
                first_action="pipeline_status",
                tb=tb,
            )
        self.assertEqual(out["factual_packet"]["tool"], "agent_loop")
        self.assertEqual(out["factual_packet"]["step_count"], 2)
        self.assertIn("capsule", out["reply"].lower())
        tb.blink.assert_any_call(
            "agent_step", n=2, decision="continue", action="what_should_i_do_now", reason="need"
        )

    def test_does_not_auto_chain_protected(self):
        import services.tools.loop as tl

        first = {
            "reply": "confirm push",
            "action_type": "SEND_AZURACAST_CONFIRM",
            "require_confirmation": True,
            "factual_packet": {"next_step": "station_status"},
        }
        with patch.object(tl.feature_flags, "bounded_tool_loop_enabled", return_value=True), patch.object(
            tl.feature_flags, "deep_agent_loop_enabled", return_value=False
        ):
            out = tl.extend_live_ops_result(
                message="push", first_result=first, first_action="send_azuracast", tb=MagicMock()
            )
        self.assertIs(out, first)

    def test_confirm_decision_stops(self):
        import services.tools.loop as tl

        first = {
            "reply": "diag ok",
            "action_type": "DIAGNOSTICS",
            "factual_packet": {"tool": "diagnostics"},
            "ok": True,
        }
        seed = dict(first)
        with patch.object(tl.feature_flags, "bounded_tool_loop_enabled", return_value=True), patch.object(
            tl.feature_flags, "deep_agent_loop_enabled", return_value=False
        ), patch.object(
            tl,
            "choose_next_agent_step",
            return_value={"decision": "confirm", "action": None, "slots": {}, "reason": "need push"},
        ), patch.object(tl, "_execute_followup") as exec_mock, patch(
            "services.brain.live_state_snapshot.build_neena_live_state_snapshot",
            return_value={},
        ):
            out = tl.extend_live_ops_result(
                message="diagnostics",
                first_result=seed,
                first_action="diagnostics",
                tb=MagicMock(),
            )
        exec_mock.assert_not_called()
        self.assertIs(out, seed)

    def test_timeout_fail_closed_no_chain(self):
        import services.tools.loop as tl

        first = {
            "reply": "station ok",
            "action_type": "STATION_STATUS",
            "factual_packet": {"tool": "station"},
            "ok": True,
        }
        seed = dict(first)
        with patch.object(tl.feature_flags, "bounded_tool_loop_enabled", return_value=True), patch.object(
            tl.feature_flags, "deep_agent_loop_enabled", return_value=False
        ), patch.object(
            tl,
            "choose_next_agent_step",
            return_value={"decision": "done", "action": None, "slots": {}, "reason": "timeout"},
        ), patch.object(tl, "_execute_followup") as exec_mock, patch(
            "services.brain.live_state_snapshot.build_neena_live_state_snapshot",
            return_value={},
        ):
            out = tl.extend_live_ops_result(
                message="status",
                first_result=seed,
                first_action="station_status",
                tb=MagicMock(),
            )
        exec_mock.assert_not_called()
        self.assertIs(out, seed)

    def test_deep_budget_allows_more_llm_steps(self):
        import services.tools.loop as tl

        first = {
            "reply": "diag ok",
            "action_type": "DIAGNOSTICS",
            "factual_packet": {"tool": "diagnostics"},
            "ok": True,
        }
        seq = [
            {"decision": "continue", "action": "station_status", "slots": {}, "reason": "a"},
            {"decision": "continue", "action": "pipeline_status", "slots": {}, "reason": "b"},
            {"decision": "continue", "action": "what_should_i_do_now", "slots": {}, "reason": "c"},
            {"decision": "done", "action": None, "slots": {}, "reason": "enough"},
        ]
        responses = {
            "station_status": {
                "reply": "station ok",
                "action_type": "STATION_STATUS",
                "factual_packet": {"tool": "station"},
                "ok": True,
            },
            "pipeline_status": {
                "reply": "pipe ok",
                "action_type": "PIPELINE_STATUS",
                "factual_packet": {"tool": "pipeline"},
                "ok": True,
            },
            "what_should_i_do_now": {
                "reply": "do next",
                "action_type": "LIVE_RECOMMENDATION",
                "factual_packet": {"tool": "recommend"},
                "ok": True,
            },
        }

        def _exec(action, slots, snap=None, message=None):
            return responses.get(action)

        with patch.object(tl.feature_flags, "bounded_tool_loop_enabled", return_value=True), patch.object(
            tl.feature_flags, "deep_agent_loop_enabled", return_value=True
        ), patch.object(tl, "choose_next_agent_step", side_effect=seq), patch.object(
            tl, "_execute_followup", side_effect=_exec
        ), patch.object(tl, "_try_synthesize_reply", return_value=None), patch.object(
            tl, "_max_steps", return_value=8
        ), patch(
            "services.brain.live_state_snapshot.build_neena_live_state_snapshot",
            return_value={},
        ):
            out = tl.extend_live_ops_result(
                message="diagnostics",
                first_result=dict(first),
                first_action="diagnostics",
                tb=MagicMock(),
            )
        self.assertEqual(out["factual_packet"]["tool"], "agent_loop")
        self.assertGreaterEqual(out["factual_packet"]["step_count"], 3)
        self.assertTrue(out["factual_packet"]["deep"])


if __name__ == "__main__":
    unittest.main()
