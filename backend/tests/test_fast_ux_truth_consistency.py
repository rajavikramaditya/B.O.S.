"""M4-A8.5 — Fast UX Truth Consistency tests (AGENTS hygiene Wave A)."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

_WORKSPACE = r"c:\Projects\radio station\radio-ai-manager\backend"
if os.path.isdir(_WORKSPACE):
    sys.path.insert(0, _WORKSPACE)

from services.llm.intent_router import is_exact_command, route_intent
from services.llm.model_status import build_model_status_reply


class TestFastUXTruthConsistency(unittest.TestCase):
    def test_exact_command_is_diagnostics_only(self):
        self.assertTrue(is_exact_command("diagnostics"))
        self.assertTrue(is_exact_command("diagnostics run karo"))
        for msg in (
            "model status batao",
            "Gemini chal raha hai kya",
            "schedule",
            "stream status",
            "auto mode start",
        ):
            self.assertFalse(is_exact_command(msg), msg)

    def test_model_status_not_phrase_routed(self):
        for msg in (
            "abhi kaun sa model use kar rahi ho",
            "model status batao",
            "Gemini chal raha hai kya",
        ):
            routed = route_intent(msg)
            self.assertEqual(routed["intent_type"], "CHAT_CONVERSATION", msg)

    def test_diagnostics_routes_exact(self):
        routed = route_intent("diagnostics")
        self.assertEqual(routed["intent_type"], "DIAGNOSTICS")

    @patch("services.llm.provider_router.resolve_model_for_role")
    @patch("services.llm.provider_router.is_llm_configured")
    def test_model_status_reply_format(self, mock_llm_config, mock_resolve_model):
        mock_resolve_model.side_effect = lambda role: f"mock-{role.lower()}"
        mock_llm_config.return_value = True

        reply = build_model_status_reply()
        self.assertIn("interpreter=mock-command_interpreter_model", reply)
        self.assertIn("creative=mock-creative_model", reply)


if __name__ == "__main__":
    unittest.main(verbosity=2)
