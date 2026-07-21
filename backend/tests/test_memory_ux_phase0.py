"""Phase 0 memory UX: stable ids, hann confirm, manage vs propose guards."""
from __future__ import annotations

import unittest
from unittest.mock import patch


class TestStableMemoryIds(unittest.TestCase):
    def test_list_shows_id_not_rank(self):
        from services.memory import edit_service as mes

        fake = [
            {"id": 27, "content": "tagline A", "memory_type": "station_identity"},
            {"id": 5, "content": "style B", "memory_type": "owner_style_preference"},
        ]
        with patch.object(mes, "list_active_memories_pg", return_value={"memories": fake}):
            text = mes.list_owner_memories_text()
        self.assertIn("id=5", text)
        self.assertIn("id=27", text)
        self.assertNotIn("1. [", text)
        self.assertIn("stable id", text.lower())
        self.assertNotIn("sir,", text.lower())

    def test_resolve_by_postgres_id(self):
        from services.memory import edit_service as mes

        row = {
            "id": 27,
            "content": "tagline",
            "memory_type": "station_identity",
            "owner_confirmed": True,
            "retention": "permanent",
        }
        with patch.object(mes, "get_memory_pg", return_value={"memory": row}):
            self.assertEqual(mes._resolve_target("27")["id"], 27)
            self.assertEqual(mes._resolve_target("id 27")["id"], 27)
            self.assertEqual(mes._resolve_target("memory id=27")["id"], 27)

    def test_resolve_does_not_use_list_rank(self):
        from services.memory import edit_service as mes

        with patch.object(mes, "get_memory_pg", return_value={"memory": None}):
            with patch.object(mes, "search_memories_keyword_pg", return_value={"memories": []}):
                self.assertIsNone(mes._resolve_target("1"))


class TestHannConfirm(unittest.TestCase):
    def test_hann_is_confirmation_only(self):
        from services.llm.intent_router import is_affirmative_reply, is_confirmation_only

        self.assertTrue(is_confirmation_only("hann"))
        self.assertTrue(is_confirmation_only("Hann"))
        self.assertTrue(is_confirmation_only("hann!"))
        self.assertTrue(is_affirmative_reply("hann"))


class TestProposeGuards(unittest.TestCase):
    def test_propose_blocked_when_edit_pending(self):
        from services.brain.live_ops_executor import try_execute_live_ops

        with patch(
            "services.memory.service.get_pending_permanent_memory_candidate",
            return_value=None,
        ), patch(
            "services.memory.edit_service.get_pending_memory_edit",
            return_value={"operation": "delete", "memory_id": 10},
        ):
            res = try_execute_live_ops(
                "propose_permanent_memory",
                {"content": "new fact"},
                snapshot={},
                owner_message="new fact",
            )
        self.assertIsNotNone(res)
        self.assertFalse(res.get("ok"))
        self.assertIn("pending", (res.get("reply") or "").lower())

    def test_propose_rejects_hann_as_content(self):
        from services.brain.live_ops_executor import try_execute_live_ops

        with patch(
            "services.memory.service.get_pending_permanent_memory_candidate",
            return_value=None,
        ), patch(
            "services.memory.edit_service.get_pending_memory_edit",
            return_value=None,
        ):
            res = try_execute_live_ops(
                "propose_permanent_memory",
                {"content": "Hann"},
                snapshot={},
                owner_message="Hann",
            )
        self.assertIsNotNone(res)
        self.assertFalse(res.get("ok"))
        self.assertIn("content", (res.get("reply") or "").lower())


if __name__ == "__main__":
    unittest.main()
