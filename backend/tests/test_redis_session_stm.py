"""Redis / session STM layer — TTL align, pending slots, WC pointers, aging."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestSessionSnapshotTtl(unittest.TestCase):
    def test_default_ttl_matches_working_context(self):
        from services.brain import redis_state as rs

        self.assertEqual(rs.SESSION_SNAPSHOT_TTL_SECONDS, rs.OWNER_WORKING_CONTEXT_TTL_SECONDS)
        self.assertGreaterEqual(rs.SESSION_SNAPSHOT_TTL_SECONDS, 7 * 24 * 3600)


class TestPendingSlots(unittest.TestCase):
    def setUp(self):
        import services.brain.manager_state as ms

        ms._state["pending_action"] = None
        ms._state["pending_slots"] = {"live_ops": None, "memory": None}

    def test_memory_and_live_ops_do_not_overwrite(self):
        import services.brain.manager_state as ms
        import services.brain.redis_state as rs

        with patch.object(ms, "_refresh_redis_available", return_value={"available": False}):
            ms.set_pending_action(
                action_type="memory_edit",
                category="memory",
                risk_level="medium",
                protected=False,
                executable_now=True,
                requires_stage="owner_confirmation",
                expires_after_turns=3,
                payload={"memory_id": 9},
            )
            ms.set_pending_action(
                action_type="send_azuracast",
                category="live_ops",
                risk_level="high",
                protected=True,
                executable_now=True,
                requires_stage="owner_confirmation",
                expires_after_turns=1,
                payload={"resume_action": "send_azuracast"},
            )
            priority = ms.get_pending_action()
            self.assertEqual(priority.get("action_type"), "send_azuracast")
            slots = ms._state["pending_slots"]
            self.assertEqual(slots["memory"]["action_type"], "memory_edit")
            self.assertEqual(slots["live_ops"]["action_type"], "send_azuracast")

            ms.clear_pending_action()  # clears priority (live_ops) only
            self.assertIsNone(ms._state["pending_slots"]["live_ops"])
            self.assertEqual(ms._state["pending_slots"]["memory"]["action_type"], "memory_edit")
            self.assertEqual(ms.get_pending_action().get("action_type"), "memory_edit")

    def test_age_skips_once_then_expires(self):
        import services.brain.manager_state as ms

        with patch.object(ms, "_refresh_redis_available", return_value={"available": False}):
            ms.set_pending_action(
                action_type="send_azuracast",
                category="live_ops",
                risk_level="high",
                protected=True,
                executable_now=True,
                requires_stage="owner_confirmation",
                expires_after_turns=1,
                payload={},
            )
            # Setting turn ages but skip_age_once prevents decrement.
            ms.age_pending_after_turn()
            self.assertIsNotNone(ms.get_pending_action())
            self.assertEqual(ms.get_pending_action().get("turns_remaining"), 1)
            # Next turn ages to 0 and clears.
            ms.age_pending_after_turn()
            self.assertIsNone(ms.get_pending_action())


class TestWorkingContextPointers(unittest.TestCase):
    def test_future_intention_sets_open_goal(self):
        from services.agent import working_context as wc

        with patch.object(wc.feature_flags, "owner_working_context_enabled", return_value=True):
            with patch.object(wc, "load_working_context", return_value={}):
                with patch.object(wc.redis_state, "save_owner_working_context", return_value={"success": True}):
                    ctx = wc.update_working_context_after_turn(
                        message="kal push karna hai",
                        reply="saved",
                        action_type="FUTURE_INTENTION_SAVED",
                        factual_packet={
                            "tool": "future_intention_save",
                            "memory_id": 42,
                            "thread_key": "capsule11",
                        },
                    )
        self.assertEqual(ctx.get("open_goal"), "intention:42")
        self.assertEqual(ctx.get("last_intention_id"), 42)
        self.assertEqual(ctx.get("last_thread_key"), "capsule11")
        block = wc.format_working_context_block(ctx)
        self.assertIn("intention:42", block)
        self.assertIn("last_intention_id", block)

    def test_day_memory_sets_day_pointer(self):
        from services.agent import working_context as wc

        with patch.object(wc.feature_flags, "owner_working_context_enabled", return_value=True):
            with patch.object(wc, "load_working_context", return_value={}):
                with patch.object(wc.redis_state, "save_owner_working_context", return_value={"success": True}):
                    ctx = wc.update_working_context_after_turn(
                        message="kal kya hua",
                        reply="empty",
                        action_type="DAY_MEMORY_RECALL",
                        factual_packet={
                            "tool": "day_memory_recall",
                            "date_ist": "2026-07-15",
                            "label": "yesterday",
                        },
                    )
        self.assertEqual(ctx.get("open_goal"), "day:2026-07-15")
        self.assertEqual(ctx.get("last_day_date_ist"), "2026-07-15")


class TestContinuityPromptHelper(unittest.TestCase):
    def test_build_owner_prompt_context(self):
        from services.memory import continuity as cont

        with patch.object(
            cont,
            "load_owner_continuity",
            return_value={
                "chat_turns": [{"role": "user", "content": "hi"}],
                "working_context": {"open_goal": "x"},
                "working_block": "OWNER WORKING CONTEXT: x",
                "short_context": "SHORT-TERM",
                "pending": None,
                "permanent_context_text": "fact",
                "permanent_hits": [],
            },
        ):
            out = cont.build_owner_prompt_context("hi")
        self.assertIn("OWNER WORKING CONTEXT", out["working_block"])
        self.assertEqual(out["short_context"], "SHORT-TERM")


if __name__ == "__main__":
    unittest.main()
