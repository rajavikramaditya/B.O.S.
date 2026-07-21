"""Phase 1–2: working context + system knowledge pack."""
from __future__ import annotations

import unittest
from unittest.mock import patch


class TestWorkingContext(unittest.TestCase):
    def test_update_and_format_with_fallback(self):
        import services.agent.working_context as wc

        wc._FALLBACK.clear()
        with patch.object(
            wc.redis_state,
            "save_owner_working_context",
            return_value={"success": False},
        ), patch.object(
            wc.redis_state,
            "get_owner_working_context",
            return_value={"success": False, "context": None},
        ), patch.object(
            wc.feature_flags,
            "owner_working_context_enabled",
            return_value=True,
        ), patch(
            "services.memory.edit_service.get_pending_memory_edit",
            return_value=None,
        ), patch(
            "services.memory.service.get_pending_permanent_memory_candidate",
            return_value=None,
        ):
            ctx = wc.update_working_context_after_turn(
                message="Result??",
                reply="Job started",
                action_type="STREAM_VERIFY",
                route="verify_stream",
                require_confirmation=False,
            )
            self.assertEqual(ctx.get("last_action_type"), "STREAM_VERIFY")
            block = wc.format_working_context_block()
            self.assertIn("OWNER WORKING CONTEXT", block)
            self.assertIn("STREAM_VERIFY", block)
            self.assertIn("Result??", block)

    def test_disabled_returns_empty(self):
        import services.agent.working_context as wc

        with patch.object(wc.feature_flags, "owner_working_context_enabled", return_value=False):
            self.assertEqual(wc.format_working_context_block(), "")
            self.assertEqual(
                wc.update_working_context_after_turn(message="x", reply="y", action_type="A"),
                {},
            )


class TestSystemKnowledgePack(unittest.TestCase):
    def test_pack_contains_core_rules(self):
        import services.agent.system_knowledge_pack as sk

        with patch.object(sk.feature_flags, "system_knowledge_pack_enabled", return_value=True):
            text = sk.system_knowledge_pack_text()
        self.assertIn("SYSTEM KNOWLEDGE PACK", text)
        self.assertIn("manage_memory", text)
        self.assertIn("Safety Kernel", text)
        self.assertIn("Customer", text)
        self.assertIn("never claim sleep mode", text.lower())
        self.assertIn("CPU hurt", text)
        self.assertIn("LIVE CLOCK", text)

    def test_pack_off(self):
        import services.agent.system_knowledge_pack as sk

        with patch.object(sk.feature_flags, "system_knowledge_pack_enabled", return_value=False):
            self.assertEqual(sk.system_knowledge_pack_text(), "")


if __name__ == "__main__":
    unittest.main()
