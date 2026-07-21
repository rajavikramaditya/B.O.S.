"""MOS / ADR-008 — owner isolation, Redis-first WC, crash commit."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class OwnerDurableScopeTests(unittest.TestCase):
    def test_retrieve_passes_owner_actor_filters(self):
        from services.memory import service as mem

        with patch.object(mem, "is_pgvector_available", return_value={"available": False}), patch.object(
            mem, "is_postgres_available", return_value={"available": True}
        ), patch.object(mem, "search_memories_keyword_pg") as kw, patch.object(
            mem.memory_repository, "search_memories_keyword", return_value=[]
        ):
            kw.return_value = {
                "memories": [
                    {
                        "id": 1,
                        "content": "station tagline",
                        "actor_role": "owner",
                        "subject_key": "owner",
                        "memory_type": "station_identity",
                        "retention": "permanent",
                        "owner_confirmed": True,
                    }
                ]
            }
            hits = mem.retrieve_active_permanent_memories("tagline", limit=3)
        kw.assert_called()
        kwargs = kw.call_args.kwargs
        self.assertEqual(kwargs.get("actor_role"), "owner")
        self.assertEqual(kwargs.get("subject_key"), "owner")
        self.assertEqual(len(hits), 1)

    def test_sqlite_list_defaults_owner_scope(self):
        from services.memory import repository as repo

        owner = {
            "id": 1,
            "content": "owner fact",
            "actor_role": "owner",
            "subject_key": "owner",
            "memory_type": "station_identity",
            "owner_confirmed": 1,
            "retention": "permanent",
            "source": "test",
            "metadata_json": "{}",
        }
        customer = {
            "id": 2,
            "content": "customer name Ravi",
            "actor_role": "customer",
            "subject_key": "9876543210",
            "memory_type": "customer_name",
            "owner_confirmed": 1,
            "retention": "permanent",
            "source": "test",
            "metadata_json": "{}",
        }

        class FakeCursor:
            def __init__(self):
                self.sql = ""
                self.params = ()

            def execute(self, sql, params=None):
                self.sql = sql
                self.params = params or ()

            def fetchall(self):
                # Simulate SQL filter: only return owner when actor/subject in params
                if "actor_role" in self.sql and "owner" in self.params:
                    return [owner]
                return [owner, customer]

        class FakeConn:
            def cursor(self):
                return FakeCursor()

            def close(self):
                return None

        with patch.object(repo.db, "get_db_connection", return_value=FakeConn()), patch.object(
            repo, "_decode_row", side_effect=lambda r: r
        ):
            rows = repo.list_active_memories(limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["subject_key"], "owner")


class RedisFirstWorkingContextTests(unittest.TestCase):
    def test_load_prefers_redis_over_stale_fallback(self):
        from services.agent import working_context as wc

        wc._FALLBACK.clear()
        wc._FALLBACK.update({"last_user_message": "stale-local", "open_goal": "old"})
        with patch.object(
            wc.redis_state,
            "get_owner_working_context",
            return_value={"success": True, "context": {"last_user_message": "from-redis", "open_goal": "new"}},
        ), patch.object(wc.feature_flags, "owner_working_context_enabled", return_value=True):
            ctx = wc.load_working_context()
        self.assertEqual(ctx.get("last_user_message"), "from-redis")
        self.assertEqual(wc._FALLBACK.get("last_user_message"), "from-redis")

    def test_redis_empty_clears_stale_fallback(self):
        from services.agent import working_context as wc

        wc._FALLBACK.clear()
        wc._FALLBACK.update({"last_user_message": "stale"})
        with patch.object(
            wc.redis_state,
            "get_owner_working_context",
            return_value={"success": True, "context": None},
        ), patch.object(wc.feature_flags, "owner_working_context_enabled", return_value=True):
            ctx = wc.load_working_context()
        self.assertEqual(ctx, {})
        self.assertEqual(wc._FALLBACK, {})


class PendingRedisFirstTests(unittest.TestCase):
    def test_redis_empty_does_not_resurrect_local_pending(self):
        import services.brain.manager_state as ms

        ms._state["pending_action"] = {"action_type": "stale_local"}
        with patch.object(ms, "_refresh_redis_available", return_value={"available": True}), patch.object(
            ms.redis_state,
            "get_live_pending_action",
            return_value={"success": True, "action": None},
        ):
            pending = ms.get_pending_action()
        self.assertIsNone(pending)
        self.assertIsNone(ms._state.get("pending_action"))


class CrashCommitTests(unittest.TestCase):
    def test_safe_owner_result_commits_turns(self):
        from services.brain.always_reply import safe_owner_result

        with patch("services.memory.continuity.commit_owner_turn") as commit:
            out = safe_owner_result("hello sir", reply="main yahan hoon")
        commit.assert_called_once()
        args, kwargs = commit.call_args
        self.assertEqual(args[0], "hello sir")
        self.assertIn("yahan", args[1])
        self.assertTrue(out.get("fallback_used"))


class ContinuityLoaderTests(unittest.TestCase):
    def test_load_owner_continuity_shape(self):
        from services.memory.continuity import load_owner_continuity

        with patch("services.brain.feature_flags.conversation_memory_enabled", return_value=True), patch(
            "services.brain.feature_flags.one_brain_foundation_enabled", return_value=True
        ), patch(
            "services.memory.adapter.load_chat_history_contents",
            return_value=[{"role": "user", "parts": [{"text": "hi"}]}],
        ), patch(
            "services.agent.working_context.load_working_context",
            return_value={"open_goal": "test"},
        ), patch(
            "services.agent.working_context.format_working_context_block",
            return_value="OWNER WORKING CONTEXT: test",
        ), patch(
            "services.brain.manager_state.get_pending_action", return_value=None
        ), patch(
            "services.brain.manager_state.build_short_context", return_value="SHORT-TERM"
        ), patch(
            "services.memory.facade.recall",
            return_value={"hits": [], "context_text": ""},
        ):
            bundle = load_owner_continuity("hi")
        self.assertEqual(bundle["role"], "owner")
        self.assertEqual(len(bundle["chat_turns"]), 1)
        self.assertEqual(bundle["working_context"].get("open_goal"), "test")


class SelfKnowledgeHealthNoteTests(unittest.TestCase):
    def test_whatsapp_health_note_not_memory_continuity_hack(self):
        from services.brain import self_knowledge as sk

        with sk.inbound_channel_scope("whatsapp"), patch(
            "services.brain.redis_state.is_redis_available",
            return_value={"available": True},
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
            text = sk.format_body_awareness_for_llm()
        self.assertIn("HEALTH NOTE", text)
        self.assertNotIn("CHANNEL RULE", text)
        self.assertIn("MOS", text)


if __name__ == "__main__":
    unittest.main()
