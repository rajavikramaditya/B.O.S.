"""Characterization tests for neena_brain.process_owner_message pipeline.

Purpose: pin the CURRENT behavior of the dispatch pipeline BEFORE refactoring it
(rule 2 SRP split done safely). These are hermetic — every sub-module and network
seam is mocked, so the tests assert routing/return behavior only, never real LLM /
DB / Redis calls.

Two groups:
  * TestPreIntentGuards — locks the pre-intent guard phase (permanent-memory
    candidate handling + approval-only clarify) that gets extracted into a stage.
  * TestLegacyCreativeTailUnreachable — proves the old "Stage C legacy creative
    LLM path" is dead code (both the exact-command and NL-interpreter branches
    always return before it), so it can be removed with confidence.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class _BrainHarness:
    """Shared hermetic seams so process_owner_message never touches the network."""

    def base_patches(self, nb):
        return [
            mock.patch.object(nb.memory_service, "get_pending_permanent_memory_candidate", return_value=None),
            mock.patch.object(nb.memory_service, "is_explicit_permanent_memory_request", return_value=False),
            mock.patch.object(nb.memory_service, "is_memory_rejection_message", return_value=False),
            mock.patch.object(nb.memory_service, "is_direct_memory_question", return_value=False),
            mock.patch.object(nb.memory_service, "get_memory_context_packet", return_value={"context_text": ""}),
            mock.patch.object(nb.manager_state, "get_pending_action", return_value=None),
            mock.patch.object(nb, "_apply_session_trace", side_effect=lambda *a, **k: None),
            mock.patch.object(nb, "_save_and_return", side_effect=lambda message, reply, **kw: {"reply": reply, **kw}),
            mock.patch.object(nb.rc, "get_whatsapp_gateway_trace_status", return_value=""),
        ]


class TestPreIntentGuards(unittest.TestCase):
    """Pre-intent guard phase (permanent memory + approval-only clarify)."""

    def _run(self, message, patches):
        import services.brain.brain as nb
        started = [p.start() for p in patches]
        self.addCleanup(lambda: [p.stop() for p in patches])
        return nb.process_owner_message(message)

    def test_permanent_memory_confirmation(self):
        import services.brain.brain as nb
        h = _BrainHarness().base_patches(nb)
        h[0] = mock.patch.object(nb.memory_service, "get_pending_permanent_memory_candidate",
                                 return_value={"candidate": "x"})
        h.append(mock.patch.object(nb.memory_service, "confirm_pending_permanent_memory_candidate",
                                   return_value={"reply": "Yaad rakh liya sir.", "status": "saved"}))
        result = self._run("haan", h)
        self.assertEqual(result["action_type"], "PERMANENT_MEMORY_SAVE")
        self.assertIn("Yaad rakh liya", result["reply"])

    def test_permanent_memory_cancel(self):
        import services.brain.brain as nb
        h = _BrainHarness().base_patches(nb)
        h[0] = mock.patch.object(nb.memory_service, "get_pending_permanent_memory_candidate",
                                 return_value={"candidate": "x"})
        h[2] = mock.patch.object(nb.memory_service, "is_memory_rejection_message", return_value=True)
        h.append(mock.patch.object(nb.memory_service, "cancel_pending_permanent_memory_candidate",
                                   return_value={"reply": "Theek hai, save nahi kiya."}))
        result = self._run("rehne do", h)
        self.assertEqual(result["action_type"], "PERMANENT_MEMORY_CANCEL")

    def test_explicit_permanent_memory_no_local_router_autosave(self):
        """AGENTS hygiene: remember markers do not short-circuit to PERMANENT_MEMORY_CANDIDATE."""
        import services.brain.brain as nb

        create = mock.Mock(return_value={"reply": "should not run", "status": "pending_confirmation"})
        h = _BrainHarness().base_patches(nb)
        h[1] = mock.patch.object(nb.memory_service, "is_explicit_permanent_memory_request", return_value=True)
        h.append(mock.patch.object(nb.memory_service, "create_pending_permanent_memory_candidate", create))
        h.append(mock.patch.object(nb.pr, "is_llm_configured", return_value=True))
        h.append(
            mock.patch(
                "services.brain.command_interpreter.interpret_owner_command",
                return_value=(
                    {"action": "unknown", "confidence": 0.1, "slots": {}},
                    "local",
                    "available",
                    None,
                ),
            )
        )
        h.append(mock.patch.object(nb, "_smart_conversational_reply", return_value=None))
        h.append(
            mock.patch(
                "services.brain.live_state_snapshot.build_neena_live_state_snapshot",
                return_value={},
            )
        )
        result = self._run("yaad rakhna mera naam Vikas hai", h)
        create.assert_not_called()
        self.assertNotEqual(result.get("action_type"), "PERMANENT_MEMORY_CANDIDATE")

    def test_approval_only_with_no_pending_asks_clarification(self):
        import services.brain.brain as nb
        h = _BrainHarness().base_patches(nb)
        result = self._run("haan", h)
        self.assertEqual(result["action_type"], "clarification")
        self.assertIn("pending", result["reply"].lower())


class TestLegacyCreativeTailUnreachable(unittest.TestCase):
    """Prove the 'Stage C legacy creative LLM path' is dead code.

    Owner path always returns via diagnostics exact, forbidden, or interpreter —
    never falls through to get_station_context()/build_response_system_prompt().
    """

    def _tail_sentinel_patches(self, nb):
        def _boom(*a, **k):
            raise AssertionError("legacy creative tail was reached (should be dead code)")

        return _BrainHarness().base_patches(nb) + [
            mock.patch.object(nb, "get_station_context", side_effect=_boom),
            mock.patch.object(nb, "build_response_system_prompt", side_effect=_boom),
            mock.patch.object(nb.pr, "is_llm_configured", return_value=True),
            mock.patch.object(nb.feature_flags, "smart_reply_enabled", return_value=False),
        ]

    def test_diagnostics_exact_does_not_reach_tail(self):
        import services.brain.brain as nb

        patches = self._tail_sentinel_patches(nb) + [
            mock.patch.object(
                nb,
                "_run_diagnostics_fast_path",
                return_value={"reply": "ok", "action_type": "RUN_DIAGNOSTICS"},
            ),
        ]
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        result = nb.process_owner_message("diagnostics")
        self.assertEqual(result["action_type"], "RUN_DIAGNOSTICS")

    def test_nl_interpreter_path_does_not_reach_tail(self):
        import services.brain.brain as nb
        import services.brain.command_interpreter as ci
        import services.brain.live_state_snapshot as snap

        patches = self._tail_sentinel_patches(nb) + [
            mock.patch.object(
                ci,
                "interpret_owner_command",
                return_value=(
                    {"action": "unknown", "confidence": 0.0, "slots": {}},
                    "gemma",
                    "available",
                    "gemma-4-31b",
                ),
            ),
            mock.patch.object(snap, "build_neena_live_state_snapshot", return_value={}),
            mock.patch.object(snap, "format_snapshot_for_interpreter", return_value=""),
            mock.patch.object(nb, "_smart_conversational_reply", return_value=None),
        ]
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        result = nb.process_owner_message("kuch creative likho types of thing")
        self.assertEqual(result["action_type"], "clarification")


if __name__ == "__main__":
    unittest.main()
