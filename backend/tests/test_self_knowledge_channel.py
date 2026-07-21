"""Body awareness: Redis dict bool bug + WhatsApp inbound must not invent 'toot'."""
from __future__ import annotations

import unittest
from unittest.mock import patch


class SelfKnowledgeBodyTests(unittest.TestCase):
    def test_redis_uses_available_flag_not_bool_dict(self):
        from services.brain import self_knowledge as sk

        with patch.object(sk, "get_inbound_channel", return_value="command_center"), patch(
            "services.brain.redis_state.is_redis_available",
            return_value={"available": False, "reason": "down"},
        ), patch(
            "services.cockpit.runtime_controller.peek_whatsapp_gateway_trace_status",
            return_value="unknown",
        ), patch(
            "services.brain.live_state_snapshot.build_neena_live_state_snapshot",
            return_value={"local_stats": {"cpu": 10, "ram": 20}, "server": "online", "stream": "online"},
        ), patch("services.llm.provider_router.get_gemini_api_key", return_value="k"), patch(
            "services.llm.provider_router.resolve_model_for_role", return_value="gemma-x"
        ), patch(
            "services.llm.provider_router.resolve_and_verify_model", return_value="flash"
        ), patch(
            "services.llm.provider_router.is_model_penalized", return_value=False
        ), patch(
            "services.llm.provider_router.peek_cooldown_wait", return_value=0
        ), patch(
            "services.memory.pg_repository.is_postgres_available",
            return_value={"available": True},
        ):
            body = sk.build_live_body_awareness()
        redis_part = next(p for p in body["parts"] if p["name"] == "yaad_short_redis")
        self.assertEqual(redis_part["feel"], "hurt")

    def test_whatsapp_inbound_marks_mouth_healthy(self):
        from services.brain import self_knowledge as sk

        with sk.inbound_channel_scope("whatsapp"), patch(
            "services.brain.redis_state.is_redis_available",
            return_value={"available": True},
        ), patch(
            "services.cockpit.runtime_controller.peek_whatsapp_gateway_trace_status",
            return_value="offline",
        ) as peek, patch(
            "services.brain.live_state_snapshot.build_neena_live_state_snapshot",
            return_value={"local_stats": {"cpu": 10, "ram": 20}, "server": "online", "stream": "online"},
        ), patch("services.llm.provider_router.get_gemini_api_key", return_value="k"), patch(
            "services.llm.provider_router.resolve_model_for_role", return_value="gemma-x"
        ), patch(
            "services.llm.provider_router.resolve_and_verify_model", return_value="flash"
        ), patch(
            "services.llm.provider_router.is_model_penalized", return_value=False
        ), patch(
            "services.llm.provider_router.peek_cooldown_wait", return_value=0
        ), patch(
            "services.memory.pg_repository.is_postgres_available",
            return_value={"available": True},
        ):
            body = sk.build_live_body_awareness()
            text = sk.format_body_awareness_for_llm(body)
        wa = next(p for p in body["parts"] if p["name"] == "muh_whatsapp")
        self.assertEqual(wa["feel"], "healthy")
        peek.assert_not_called()
        self.assertIn("HEALTH NOTE", text)
        self.assertNotIn("CHANNEL RULE", text)
        self.assertNotIn("gateway=offline", wa["detail"])


if __name__ == "__main__":
    unittest.main()
