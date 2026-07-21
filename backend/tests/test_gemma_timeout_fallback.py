"""M6 — Owner rule: reply must ALWAYS come fast (Gemma + timeout-fallback).

If the primary Gemma is slow, Neena must not make the owner wait ~40s — it should
fall back to the fast flash-lite. These tests lock that behavior at the loop level:
- a slow/timed-out primary Gemma yields a flash-lite reply (never None when a
  fallback answered),
- a primary that was just marked slow this turn is skipped straight to the fallback,
- the slow-model penalty window helpers behave (mark / expire / clear).
"""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import services.llm.provider_router as pr  # noqa: E402
import services.brain.command_interpreter as interp  # noqa: E402
import services.brain.conversation as conv  # noqa: E402
import services.brain.feature_flags as feature_flags  # noqa: E402

GEMMA = "gemma-4-26b-a4b-it"
FLASH = "gemini-3.1-flash-lite"


class TestSlowModelPenalty(unittest.TestCase):
    def setUp(self):
        pr.SLOW_MODEL_PENALTY.clear()

    def tearDown(self):
        pr.SLOW_MODEL_PENALTY.clear()

    def test_mark_and_check(self):
        self.assertFalse(pr.is_model_penalized(GEMMA))
        pr.mark_model_slow(GEMMA, seconds=5.0)
        self.assertTrue(pr.is_model_penalized(GEMMA))

    def test_penalty_expires(self):
        pr.mark_model_slow(GEMMA, seconds=0.01)
        time.sleep(0.05)
        self.assertFalse(pr.is_model_penalized(GEMMA))
        self.assertNotIn(GEMMA, pr.SLOW_MODEL_PENALTY)


class TestConversationFallback(unittest.TestCase):
    def setUp(self):
        pr.SLOW_MODEL_PENALTY.clear()
        self._orig = {
            "smart": feature_flags.smart_reply_enabled,
            "mem": feature_flags.conversation_memory_enabled,
            "key": pr.get_gemini_api_key,
            "chain": conv._conversation_model_chain,
            "call": conv._call_conversation_model,
            "prompt": conv.build_conversation_system_prompt,
        }
        feature_flags.smart_reply_enabled = lambda: True
        feature_flags.conversation_memory_enabled = lambda: False
        pr.get_gemini_api_key = lambda: "k"
        conv._conversation_model_chain = lambda api_key: [GEMMA, FLASH]
        conv.build_conversation_system_prompt = lambda *a, **k: "sys"

    def tearDown(self):
        feature_flags.smart_reply_enabled = self._orig["smart"]
        feature_flags.conversation_memory_enabled = self._orig["mem"]
        pr.get_gemini_api_key = self._orig["key"]
        conv._conversation_model_chain = self._orig["chain"]
        conv._call_conversation_model = self._orig["call"]
        conv.build_conversation_system_prompt = self._orig["prompt"]
        pr.SLOW_MODEL_PENALTY.clear()

    def test_slow_gemma_falls_back_to_flash(self):
        calls = []

        def fake_call(resolved_id, api_key, system_prompt, contents, timeout_seconds=conv.CONVERSATION_TIMEOUT_SECONDS, **_kw):
            calls.append((resolved_id, timeout_seconds))
            if "gemma" in resolved_id:
                pr.mark_model_slow(resolved_id)
                return "", "gemma", "timeout"
            return "flash reply", "gemini", "available"

        conv._call_conversation_model = fake_call
        reply = conv.generate_conversational_reply("kaisi ho")
        self.assertEqual(reply, "flash reply")
        # Gemma tried with the SHORT budget, then flash-lite with the full budget.
        self.assertEqual(calls[0][0], GEMMA)
        self.assertEqual(calls[0][1], conv.GEMMA_SOFT_TIMEOUT_SECONDS)
        self.assertEqual(calls[1][0], FLASH)

    def test_penalized_gemma_is_skipped(self):
        calls = []

        def fake_call(resolved_id, api_key, system_prompt, contents, timeout_seconds=conv.CONVERSATION_TIMEOUT_SECONDS, **_kw):
            calls.append(resolved_id)
            return "flash reply", "gemini", "available"

        conv._call_conversation_model = fake_call
        pr.mark_model_slow(GEMMA, seconds=30.0)
        reply = conv.generate_conversational_reply("kaisi ho")
        self.assertEqual(reply, "flash reply")
        self.assertEqual(calls, [FLASH])  # gemma never called this turn

    def test_healthy_gemma_used_no_fallback(self):
        calls = []

        def fake_call(resolved_id, api_key, system_prompt, contents, timeout_seconds=conv.CONVERSATION_TIMEOUT_SECONDS, **_kw):
            calls.append(resolved_id)
            return "gemma reply", "gemma", "available"

        conv._call_conversation_model = fake_call
        reply = conv.generate_conversational_reply("kaisi ho")
        self.assertEqual(reply, "gemma reply")
        self.assertEqual(calls, [GEMMA])


if __name__ == "__main__":
    unittest.main()
