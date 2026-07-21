"""M0 foundation unit tests for Orai Radio Neena system."""
from __future__ import annotations

import sys
import os
import unittest
from pydantic import ValidationError

# Ensure backend path is importable
_WORKSPACE = r"c:\Projects\radio station\radio-ai-manager\backend"
if os.path.isdir(_WORKSPACE):
    sys.path.insert(0, _WORKSPACE)


class TestNeenaFoundationM0(unittest.TestCase):
    """M0 architecture foundation test suite."""

    def test_safety_kernel_exists(self):
        """1. Safety Kernel file and import check."""
        try:
            import services.safety.kernel as sk
            self.assertTrue(callable(sk.classify_owner_command_safety))
            self.assertTrue(callable(sk.is_broadcast_ready))
        except ImportError as e:
            self.fail(f"Safety Kernel import failed: {e}")

    def test_broadcast_phrase_maps_to_send_azuracast(self):
        """2. Broadcast phrases from safety kernel map to protected broadcast (send_azuracast)."""
        from services.safety.kernel import classify_owner_command_safety, BROADCAST_PROTECTED_PATTERNS
        for phrase in BROADCAST_PROTECTED_PATTERNS:
            res = classify_owner_command_safety(phrase, "generate_audio")
            self.assertEqual(res["action"], "send_azuracast",
                             f"Phrase '{phrase}' did not map to send_azuracast")

    def test_broadcast_now_cannot_become_generate_audio(self):
        """3. 'broadcast now' override check."""
        from services.safety.kernel import classify_owner_command_safety
        res = classify_owner_command_safety("broadcast now", "generate_audio")
        self.assertEqual(res["action"], "send_azuracast")
        self.assertNotEqual(res["action"], "generate_audio")

    def test_explicit_audio_phrase_recognized(self):
        """4. Explicit audio phrases are allowed to map to generate_audio."""
        from services.safety.kernel import classify_owner_command_safety, EXPLICIT_AUDIO_INTENTS
        for intent in EXPLICIT_AUDIO_INTENTS:
            res = classify_owner_command_safety(intent, "generate_audio")
            self.assertEqual(res["action"], "generate_audio",
                             f"Explicit intent '{intent}' was incorrectly blocked")

    def test_is_broadcast_ready_tri_gate_positive(self):
        """5. is_broadcast_ready() evaluates to True only when all tri-gate conditions are met."""
        from services.safety.kernel import is_broadcast_ready
        # True conditions
        self.assertTrue(is_broadcast_ready("real", 1, "ready_for_broadcast"))
        self.assertTrue(is_broadcast_ready("real", True, "approved_for_broadcast"))

    def test_is_broadcast_ready_tri_gate_negative(self):
        """6. is_broadcast_ready() evaluates to False for invalid statuses."""
        from services.safety.kernel import is_broadcast_ready
        # False conditions
        self.assertFalse(is_broadcast_ready("simulated", 1, "ready_for_broadcast"))
        self.assertFalse(is_broadcast_ready("real", 0, "ready_for_broadcast"))
        self.assertFalse(is_broadcast_ready("real", 1, "uploaded"))
        self.assertFalse(is_broadcast_ready("real", 1, "uploading"))
        self.assertFalse(is_broadcast_ready("real", 1, "approved"))
        self.assertFalse(is_broadcast_ready("real", 1, "blocked"))
        self.assertFalse(is_broadcast_ready("real", 1, "not_sent"))
        self.assertFalse(is_broadcast_ready("real", 1, None))
        self.assertFalse(is_broadcast_ready("real", 1, "unknown"))

    def test_error_response_contract(self):
        """7. ErrorResponse model matches AGENTS rule 6 mandated fields."""
        from services.brain.contracts_foundation import ErrorResponse

        # Test required fields validation
        with self.assertRaises(ValidationError):
            # Missing error_code and message
            ErrorResponse()

        # Rule 6 mandated fields must exist on the model (pydantic v1/v2 safe)
        model_fields = getattr(ErrorResponse, "model_fields", None) or ErrorResponse.__fields__
        for field in ("error_code", "message", "details", "recoverable", "next_action"):
            self.assertIn(field, model_fields, f"ErrorResponse missing rule-6 field: {field}")

        resp = ErrorResponse(
            error_code="TEST_ERROR",
            message="An error occurred",
            recoverable=True,
            next_action="retry_after_5s",
        )
        self.assertFalse(resp.ok)
        self.assertEqual(resp.error_code, "TEST_ERROR")
        self.assertEqual(resp.message, "An error occurred")
        self.assertTrue(resp.recoverable)
        self.assertEqual(resp.next_action, "retry_after_5s")
        self.assertTrue(resp.timestamp.endswith("Z"))

    def test_agents_md_rules_lock(self):
        """8. AGENTS.md exists and contains Safety Kernel and no VM deploy rule."""
        possible_paths = [
            os.path.join(_WORKSPACE, "..", "AGENTS.md"),
            os.path.join(_WORKSPACE, "..", ".agents", "AGENTS.md")
        ]
        found = False
        content = ""
        for path in possible_paths:
            if os.path.exists(path):
                found = True
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                break
                
        self.assertTrue(found, "AGENTS.md not found in expected paths")
        self.assertIn("Safety Kernel", content)
        self.assertIn("VM", content)
        self.assertIn("deploy", content.lower())

    def test_predeploy_script_exists(self):
        """9. Verify scripts/neena_predeploy_check.py exists on disk."""
        script_path = os.path.abspath(os.path.join(_WORKSPACE, "..", "scripts", "neena_predeploy_check.py"))
        self.assertTrue(os.path.exists(script_path), f"Predeploy check script missing at {script_path}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
