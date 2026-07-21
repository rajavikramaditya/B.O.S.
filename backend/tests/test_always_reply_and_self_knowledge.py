"""Dual-model safety net + realtime body awareness (not static memory dump)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.brain.always_reply import DUAL_MODEL_EXHAUSTED, ensure_nonempty_reply, safe_owner_result
from services.brain.self_knowledge import (
    build_live_body_awareness,
    format_body_awareness_for_llm,
    seed_self_knowledge,
    self_knowledge_facts,
)


class TestAlwaysReply(unittest.TestCase):
    def test_empty_is_honest_exhaustion_not_fake_presence(self):
        text = ensure_nonempty_reply("")
        self.assertEqual(text, DUAL_MODEL_EXHAUSTED)
        self.assertIn("dono models", text.lower())
        self.assertNotIn("main yahin hoon", text.lower())
        self.assertNotIn("backend se response nahi", text.lower())

    def test_keeps_real_reply(self):
        self.assertEqual(ensure_nonempty_reply("Ji sir"), "Ji sir")

    def test_safe_owner_result_marks_safety_net(self):
        res = safe_owner_result("hello", error=RuntimeError("boom"))
        self.assertEqual(res["source"], "safety_net")
        self.assertTrue(res["reply"].strip())


class TestRealtimeBodyAwareness(unittest.TestCase):
    def test_no_static_facts_dump(self):
        self.assertEqual(self_knowledge_facts(), [])

    def test_seed_mode_includes_narrative(self):
        with patch("services.memory.self_narrative.seed_neena_self_narrative") as mocked:
            mocked.return_value = {
                "success": True,
                "created": 2,
                "deduped": 5,
                "failed": 0,
                "facts": 7,
                "mode": "self_narrative",
            }
            out = seed_self_knowledge(with_embeddings=False)
        self.assertEqual(out["mode"], "self_narrative_plus_live_body")
        self.assertEqual(out["created"], 2)
        mocked.assert_called_once()

    def test_format_mentions_live_feel(self):
        fake = {
            "parts": [
                {"name": "yaad_short_redis", "ok": True, "feel": "healthy", "detail": "Redis session connected"},
                {"name": "yaad_permanent_postgres", "ok": False, "feel": "hurt", "detail": "Postgres DOWN"},
            ],
            "hurt_count": 1,
            "healthy_count": 1,
            "unknown_count": 0,
            "overall": "hurt",
        }
        text = format_body_awareness_for_llm(fake)
        self.assertIn("LIVE BODY FEEL", text)
        self.assertIn("HURT", text)
        self.assertIn("Postgres DOWN", text)

    @patch("services.brain.self_knowledge.build_live_body_awareness")
    def test_build_called_for_default_format(self, mocked):
        mocked.return_value = {
            "parts": [],
            "hurt_count": 0,
            "healthy_count": 0,
            "unknown_count": 0,
            "overall": "unknown",
        }
        format_body_awareness_for_llm()
        mocked.assert_called_once()


class TestCooldownWaitForFallback(unittest.TestCase):
    def test_fallback_waits_short_cooldown(self):
        import time
        import services.llm.provider_router as pr

        mid = "gemini-3.1-flash-lite-test"
        pr.LAST_INVOCATION[mid] = time.time()
        pr.COOLDOWN_RULES[mid] = 0.4
        try:
            t0 = time.time()
            ok, _wait = pr.check_and_enforce_cooldown(mid, max_wait_seconds=pr.FALLBACK_COOLDOWN_WAIT_SECONDS)
            elapsed = time.time() - t0
            self.assertTrue(ok)
            self.assertGreaterEqual(elapsed, 0.25)
        finally:
            pr.LAST_INVOCATION.pop(mid, None)
            pr.COOLDOWN_RULES.pop(mid, None)

    def test_primary_still_skips_long_cooldown(self):
        import time
        import services.llm.provider_router as pr

        mid = "gemma-skip-test"
        pr.LAST_INVOCATION[mid] = time.time()
        pr.COOLDOWN_RULES[mid] = 10.0
        try:
            ok, wait = pr.check_and_enforce_cooldown(mid)  # default max_wait=2s
            self.assertFalse(ok)
            self.assertGreater(wait, 2.0)
        finally:
            pr.LAST_INVOCATION.pop(mid, None)
            pr.COOLDOWN_RULES.pop(mid, None)


if __name__ == "__main__":
    unittest.main()
