"""Future intentions + local memory recall packets (no canned Sir-speech)."""
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import services.brain.always_reply  # noqa: F401

from services.memory.contract import ALLOWED_PERMANENT_MEMORY_TYPES
from services.memory import future_intention as fi
from services.memory import service as memory_service
from services.brain.response_composer import _REPORT_HUMANIZE_ACTION_TYPES


class TestFutureIntentionDetect(unittest.TestCase):
    def test_statement_and_question(self):
        self.assertFalse(fi.is_future_intention_statement("kal capsule push karna hai"))  # router deprecated
        self.assertFalse(fi.is_future_intention_statement("plan hai ki RJ tone soft rakhenge"))
        self.assertFalse(fi.is_future_intention_statement("kal kya hua?"))
        self.assertFalse(fi.is_future_intention_question("kal kya plan hai"))
        self.assertFalse(fi.is_future_intention_question("mere plans kya hain"))
        self.assertFalse(fi.is_future_intention_question("kal kya hua"))

    def test_lifecycle_compound_not_bare(self):
        self.assertEqual(fi.detect_lifecycle_op("plan ho gaya"), "complete")
        self.assertEqual(fi.detect_lifecycle_op("plan cancel"), "cancel")
        self.assertEqual(fi.detect_lifecycle_op("plan postpone kal"), "postpone")
        self.assertIsNone(fi.detect_lifecycle_op("ho gaya"))
        self.assertIsNone(fi.detect_lifecycle_op("haan"))
        self.assertFalse(fi.is_future_intention_statement("plan ho gaya"))

    def test_thread_key_extract(self):
        self.assertEqual(fi.extract_thread_key("kal push karna hai thread:capsule11"), "capsule11")

    def test_target_date_kal_is_tomorrow(self):
        now = datetime(2026, 7, 16, 4, 30, tzinfo=timezone.utc)
        self.assertEqual(
            fi.resolve_intention_target_date("kal capsule push karna hai", now=now),
            "2026-07-17",
        )

    def test_type_allowed(self):
        self.assertIn(fi.TYPE_FUTURE_INTENTION, ALLOWED_PERMANENT_MEMORY_TYPES)
        self.assertIn("FUTURE_INTENTION_SAVED", _REPORT_HUMANIZE_ACTION_TYPES)
        self.assertIn("FUTURE_INTENTION_RECALL", _REPORT_HUMANIZE_ACTION_TYPES)
        self.assertIn("FUTURE_INTENTION_COMPLETE", _REPORT_HUMANIZE_ACTION_TYPES)
        self.assertIn("FUTURE_INTENTION_CANCEL", _REPORT_HUMANIZE_ACTION_TYPES)
        self.assertIn("FUTURE_INTENTION_POSTPONE", _REPORT_HUMANIZE_ACTION_TYPES)


class TestFutureLifecycleApply(unittest.TestCase):
    def test_complete_patches_meta(self):
        fake = {
            "id": 42,
            "content": "push capsule",
            "target_date_ist": "2026-07-17",
            "status": "open",
            "metadata": {"status": "open", "target_date_ist": "2026-07-17"},
        }
        with patch.object(fi, "_resolve_target_intention", return_value=fake):
            with patch.object(fi, "_patch_intention_meta", return_value=True) as patch_meta:
                out = fi.apply_lifecycle("plan ho gaya")
        self.assertTrue(out["ok"])
        self.assertEqual(out["action_type"], "FUTURE_INTENTION_COMPLETE")
        self.assertEqual(patch_meta.call_args.args[0], 42)
        self.assertEqual(patch_meta.call_args.args[1]["status"], "done")
        self.assertNotIn("sir,", out["fallback_line"].lower())


class TestFutureRecallPacket(unittest.TestCase):
    def test_recall_empty_is_factual(self):
        with patch.object(fi, "list_active_intentions", return_value=[]):
            out = fi.build_future_recall_packet("kal kya plan hai")
        self.assertEqual(out["action_type"], "FUTURE_INTENTION_RECALL")
        self.assertEqual(out["factual_packet"]["count"], 0)
        self.assertNotIn("sir,", out["fallback_line"].lower())
        self.assertNotIn("samajh", out["fallback_line"].lower())


class TestLocalMemoryRecallPacket(unittest.TestCase):
    def test_no_sir_template(self):
        with patch.object(
            memory_service,
            "retrieve_active_permanent_memories",
            return_value=[{"content": "Bundeli tone", "memory_type": "owner_style_preference"}],
        ):
            out = memory_service.build_local_memory_recall_packet("kya yaad hai tone?")
        self.assertIsNotNone(out)
        self.assertEqual(out["factual_packet"]["tool"], "permanent_memory_retrieval")
        self.assertIn("Bundeli tone", out["fallback_line"])
        self.assertNotIn("sir,", out["fallback_line"].lower())
        self.assertIn("PERMANENT_MEMORY_RETRIEVAL", _REPORT_HUMANIZE_ACTION_TYPES)


if __name__ == "__main__":
    unittest.main()
