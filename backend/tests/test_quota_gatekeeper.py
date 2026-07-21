"""Two-model quota gate + shared generateContent choke-point tests."""
from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock, patch


class TestQuotaGatekeeper(unittest.TestCase):
    def setUp(self):
        import services.llm.quota_gatekeeper as g

        g._LOCAL_COUNTS.clear()
        g._LOW_COST = False

    def test_hard_cap_defers_non_critical(self):
        import services.llm.quota_gatekeeper as g

        key = g._counter_key("gemma-4-26b-a4b-it")
        _warn, hard = g._caps("gemma")
        g._write_count(key, hard)
        got = g.evaluate_request("gemma-4-26b-a4b-it", priority="owner", purpose="chat")
        self.assertFalse(got["allow"])
        self.assertEqual(got["status"], "quota_deferred")

    def test_owner_critical_allowed_at_hard(self):
        import services.llm.quota_gatekeeper as g

        key = g._counter_key("gemma-4-26b-a4b-it")
        _warn, hard = g._caps("gemma")
        g._write_count(key, hard)
        got = g.evaluate_request("gemma-4-26b-a4b-it", priority="owner_critical", purpose="chat")
        self.assertTrue(got["allow"])

    def test_warn_trips_low_cost_and_agent_steps(self):
        import services.llm.quota_gatekeeper as g

        key = g._counter_key("gemma-4-26b-a4b-it")
        warn, _hard = g._caps("gemma")
        g._write_count(key, warn)
        self.assertTrue(g.low_cost_mode_enabled())
        self.assertEqual(g.agent_loop_max_steps(5, 8, deep=False), 1)


class TestCallGenerateContent(unittest.TestCase):
    def test_429_retries_then_succeeds(self):
        import services.llm.provider_router as pr

        fail = MagicMock(status_code=429, headers={})
        ok = MagicMock(status_code=200, headers={})
        ok.json.return_value = {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]}

        with patch.object(pr, "check_and_enforce_cooldown", return_value=(True, 0.0)), patch.object(
            pr, "update_model_invocation_time"
        ), patch("services.llm.provider_router.requests.post", side_effect=[fail, ok]) as post, patch(
            "services.llm.quota_gatekeeper.evaluate_request",
            return_value={"allow": True, "force_lite": False, "low_cost": False},
        ), patch("services.llm.quota_gatekeeper.record_success", return_value=1), patch(
            "services.llm.provider_router.time.sleep"
        ):
            res, status, meta = pr.call_generate_content(
                "gemma-4-26b-a4b-it",
                "fake-key",
                {"contents": []},
                timeout=5,
                priority="owner",
                purpose="chat",
            )
        self.assertEqual(status, "available")
        self.assertEqual(meta.get("attempts"), 2)
        self.assertEqual(post.call_count, 2)
        self.assertIs(res, ok)

    def test_queue_serializes_two_threads(self):
        import services.llm.provider_router as pr

        active = {"n": 0, "max": 0}
        lock = threading.Lock()

        def _post(*_a, **_k):
            with lock:
                active["n"] += 1
                active["max"] = max(active["max"], active["n"])
            import time as _t

            _t.sleep(0.05)
            with lock:
                active["n"] -= 1
            return MagicMock(status_code=200, headers={})

        with patch.object(pr, "check_and_enforce_cooldown", return_value=(True, 0.0)), patch.object(
            pr, "update_model_invocation_time"
        ), patch("services.llm.provider_router.requests.post", side_effect=_post), patch(
            "services.llm.quota_gatekeeper.evaluate_request",
            return_value={"allow": True, "force_lite": False, "low_cost": False},
        ), patch("services.llm.quota_gatekeeper.record_success", return_value=1):

            def worker():
                pr.call_generate_content(
                    "gemma-4-26b-a4b-it",
                    "fake-key",
                    {"contents": []},
                    timeout=5,
                    priority="owner",
                    purpose="chat",
                )

            threads = [threading.Thread(target=worker) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)
        self.assertEqual(active["max"], 1)


class TestTwoModelRoles(unittest.TestCase):
    def test_primary_is_fast_26b_not_31b(self):
        from services.llm.model_roles import get_public_role_map, is_disallowed_normal_flow

        roles = get_public_role_map()
        self.assertEqual(roles["COMMAND_INTERPRETER_MODEL"]["primary_option"], "gemma-2-26b")
        self.assertEqual(roles["CONVERSATION_MODEL"]["primary_option"], "gemma-2-26b")
        self.assertEqual(roles["CREATIVE_MODEL"]["primary_option"], "gemini-3.1-flash-lite")
        self.assertTrue(is_disallowed_normal_flow("gemma-4-31b-it"))
        self.assertIn("gemma-4-26b-a4b-it", roles["COMMAND_INTERPRETER_MODEL"]["candidate_api_ids"])


if __name__ == "__main__":
    unittest.main()
