"""One-brain foundation + human-like memory (1B/2A) unit tests."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

_WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _WORKSPACE not in sys.path:
    sys.path.insert(0, _WORKSPACE)

import database as db


class TestFadeScoring(unittest.TestCase):
    def test_fade_floor_never_zero(self):
        from services.memory.facade import fade_factor

        with patch("services.brain.feature_flags.memory_soft_fade_enabled", return_value=True):
            old = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
            f = fade_factor(last_recalled_at=old)
        self.assertGreaterEqual(f, 0.05)
        self.assertLessEqual(f, 1.0)

    def test_fade_disabled_is_one(self):
        from services.memory.facade import fade_factor

        with patch("services.brain.feature_flags.memory_soft_fade_enabled", return_value=False):
            f = fade_factor(last_recalled_at="2000-01-01T00:00:00+00:00")
        self.assertEqual(f, 1.0)


class TestMemoryFacadeRoles(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._orig = db.DB_PATH
        db.DB_PATH = self._tmp.name
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._orig
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_customer_cannot_propose_owner_write(self):
        from services.memory.facade import propose_write

        res = propose_write(role="customer", content="x", memory_type="customer_name")
        self.assertTrue(res.get("blocked"))

    def test_auto_salient_allowlist_and_persist(self):
        from services.memory.facade import auto_salient_write
        import services.memory.repository as repo

        with patch("services.brain.feature_flags.customer_salient_memory_enabled", return_value=True), \
             patch("services.brain.feature_flags.one_brain_foundation_enabled", return_value=True), \
             patch("services.memory.embedding_provider.embed_text", return_value={"success": False}):
            res = auto_salient_write(
                phone="9876543210",
                memory_type="customer_name",
                content="Ravi",
                source_message="mera naam Ravi hai",
            )
        self.assertTrue(res.get("ok"))
        hits = repo.search_memories_by_subject(
            actor_role="customer", subject_key="9876543210", query="Ravi", limit=5
        )
        self.assertTrue(any("Ravi" in (h.get("content") or "") for h in hits))

    def test_customer_recall_keeps_name_when_query_mismatches(self):
        import services.memory.repository as repo

        with patch("services.brain.feature_flags.customer_salient_memory_enabled", return_value=True), \
             patch("services.brain.feature_flags.one_brain_foundation_enabled", return_value=True), \
             patch("services.memory.embedding_provider.embed_text", return_value={"success": False}):
            from services.memory.facade import auto_salient_write

            auto_salient_write(
                phone="9111222333",
                memory_type="customer_name",
                content="Asha",
                source_message="whatsapp_pushname",
            )
            auto_salient_write(
                phone="9111222333",
                memory_type="show_interest",
                content="wants morning RJ show",
                source_message="subah show pasand",
            )
        hits = repo.search_memories_by_subject(
            actor_role="customer",
            subject_key="9111222333",
            query="ad lagwani hai",
            limit=5,
        )
        self.assertTrue(
            any((h.get("memory_type") or "") == "customer_name" for h in hits),
            msg="customer_name must survive unrelated query filter",
        )

    def test_auto_salient_rejects_non_allowlisted(self):
        from services.memory.facade import auto_salient_write

        with patch("services.brain.feature_flags.customer_salient_memory_enabled", return_value=True), \
             patch("services.brain.feature_flags.one_brain_foundation_enabled", return_value=True):
            res = auto_salient_write(
                phone="9876543210",
                memory_type="station_policy",
                content="broadcast freely",
            )
        self.assertTrue(res.get("blocked"))

    def test_sqlite_actor_columns_exist(self):
        import services.memory.repository as repo

        out = repo.ensure_memory_schema()
        self.assertTrue(out.get("success"))
        conn = db.get_db_connection()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(neena_memories)").fetchall()}
        conn.close()
        for c in ("actor_role", "subject_key", "salience", "last_recalled_at", "recall_count"):
            self.assertIn(c, cols)


class TestProposePermanentMemoryLiveOps(unittest.TestCase):
    def test_propose_autosaves_without_confirm_gate(self):
        """Owner directives save immediately — no pending-confirm round-trip."""
        from services.brain.live_ops_executor import try_execute_live_ops

        with patch(
            "services.memory.facade.propose_write",
            return_value={
                "ok": True,
                "require_confirmation": False,
                "status": "saved",
                "action_type": "PROPOSE_PERMANENT_MEMORY",
                "reply": "Saved permanently — \"short replies\".",
                "candidate": {"content": "short replies", "memory_type": "owner_style_preference"},
                "postgres_memory_id": "pg-1",
            },
        ):
            res = try_execute_live_ops(
                "propose_permanent_memory",
                {"content": "short replies", "memory_type": "owner_style_preference"},
                snapshot={},
            )
        self.assertEqual(res.get("action_type"), "PROPOSE_PERMANENT_MEMORY")
        self.assertFalse(res.get("require_confirmation"))
        self.assertTrue(res.get("ok"))
        self.assertNotIn("sir,", (res.get("reply") or "").lower())


class TestRouterCcParity(unittest.TestCase):
    @patch("services.brain.brain.process_owner_message", return_value={"reply": "OK", "action_type": "x"})
    def test_owner_via_router(self, mock_o):
        from services.brain.message_router import process_message

        res = process_message(role="owner", message="hi", selected_model="auto")
        mock_o.assert_called_once_with("hi", selected_model="auto", channel="command_center")
        self.assertEqual(res["reply"], "OK")


if __name__ == "__main__":
    unittest.main()
