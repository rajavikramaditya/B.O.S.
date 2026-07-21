"""Day memory — IST windows, factual packets, diary type (no canned Sir-speech)."""
import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import services.brain.always_reply  # noqa: F401

from services.memory.contract import ALLOWED_PERMANENT_MEMORY_TYPES
from services.memory import day_memory as dm
from services.brain.response_composer import _REPORT_HUMANIZE_ACTION_TYPES


class TestDayWindowResolve(unittest.TestCase):
    def setUp(self):
        # Fixed: 2026-07-16 10:00 IST = 2026-07-16 04:30 UTC
        self.now = datetime(2026, 7, 16, 4, 30, tzinfo=timezone.utc)

    def test_kal_is_yesterday(self):
        w = dm.resolve_day_window("kal kya hua?", now=self.now)
        self.assertTrue(w["ok"])
        self.assertEqual(w["date_ist"], "2026-07-15")
        self.assertEqual(w["label"], "yesterday")

    def test_parso(self):
        w = dm.resolve_day_window("parso kya discuss hua", now=self.now)
        self.assertTrue(w["ok"])
        self.assertEqual(w["date_ist"], "2026-07-14")
        self.assertEqual(w["label"], "day_before_yesterday")

    def test_aaj(self):
        w = dm.resolve_day_window("aaj kya kiya", now=self.now)
        self.assertTrue(w["ok"])
        self.assertEqual(w["date_ist"], "2026-07-16")

    def test_iso_date(self):
        w = dm.resolve_day_window("2026-07-10 pe kya hua", now=self.now)
        self.assertTrue(w["ok"])
        self.assertEqual(w["date_ist"], "2026-07-10")

    def test_n_din_pehle(self):
        w = dm.resolve_day_window("3 din pehle kya hua", now=self.now)
        self.assertTrue(w["ok"])
        self.assertEqual(w["date_ist"], "2026-07-13")
        self.assertEqual(w["label"], "3_days_ago")

    def test_pichhle_mangal(self):
        # 2026-07-16 is Thursday; previous Tuesday = 2026-07-14
        w = dm.resolve_day_window("pichhle mangal kya hua", now=self.now)
        self.assertTrue(w["ok"])
        self.assertEqual(w["date_ist"], "2026-07-14")

    def test_is_hafte_kind_week(self):
        w = dm.resolve_day_window("is hafte kya kiya", now=self.now)
        self.assertTrue(w["ok"])
        self.assertEqual(w["kind"], "week")
        self.assertEqual(w["week_start_ist"], "2026-07-13")

    def test_is_day_question(self):
        self.assertFalse(dm.is_day_memory_question("kal kya hua?"))  # router deprecated
        self.assertFalse(dm.is_day_memory_question("parso discuss"))
        self.assertFalse(dm.is_day_memory_question("3 din pehle kya hua"))
        self.assertFalse(dm.is_day_memory_question("kaisi ho?"))
        self.assertFalse(dm.is_day_memory_question("stream status batao"))
        self.assertFalse(dm.is_day_memory_question("kal kya plan hai"))


class TestDayRecallPacket(unittest.TestCase):
    def test_empty_day_packet_is_factual(self):
        now = datetime(2026, 7, 16, 4, 30, tzinfo=timezone.utc)
        with patch.object(dm, "list_owner_turns_for_window", return_value=[]):
            with patch.object(dm, "get_day_summary_row", return_value=None):
                out = dm.build_day_recall_packet("kal kya hua?", now=now, lazy_diary=False)
        self.assertEqual(out["action_type"], "DAY_MEMORY_RECALL")
        self.assertEqual(out["factual_packet"]["tool"], "day_memory_recall")
        self.assertEqual(out["factual_packet"]["turn_count"], 0)
        self.assertIn("Day memory", out["fallback_line"])
        self.assertNotIn("sir,", out["fallback_line"].lower())

    def test_packet_with_turns(self):
        now = datetime(2026, 7, 16, 4, 30, tzinfo=timezone.utc)
        fake_turns = [
            {
                "id": 1,
                "created_at": "2026-07-15 10:00:00",
                "channel": "chat",
                "user": "status batao",
                "assistant": "Backend ok",
                "action_type": "STATION_STATUS",
                "route": "local",
                "outcome": "success",
                "blocked": False,
            }
        ]
        with patch.object(dm, "list_owner_turns_for_window", return_value=fake_turns):
            with patch.object(dm, "get_day_summary_row", return_value=None):
                out = dm.build_day_recall_packet("kal kya hua", now=now, lazy_diary=False)
        self.assertEqual(out["factual_packet"]["turn_count"], 1)
        self.assertIn("status batao", out["fallback_line"])
        self.assertNotIn("samajh gayi", out["fallback_line"].lower())


class TestDayDiaryContract(unittest.TestCase):
    def test_type_allowed(self):
        self.assertIn(dm.TYPE_DAY_SUMMARY, ALLOWED_PERMANENT_MEMORY_TYPES)
        self.assertIn(dm.TYPE_WEEK_SUMMARY, ALLOWED_PERMANENT_MEMORY_TYPES)

    def test_humanize_allowlisted(self):
        self.assertIn("DAY_MEMORY_RECALL", _REPORT_HUMANIZE_ACTION_TYPES)

    def test_digest_in_upsert(self):
        turns = [
            {
                "id": 1,
                "created_at": "2026-07-15T10:00:00+00:00",
                "channel": "chat",
                "user": "hello",
                "assistant": "hi",
                "action_type": "CONVERSATION",
                "route": "x",
                "outcome": "success",
                "blocked": False,
            }
        ]
        with patch.object(dm, "list_owner_turns_for_window", return_value=turns):
            with patch("services.memory.pg_repository.is_postgres_available", return_value={"available": True}):
                with patch(
                    "services.memory.pg_repository.create_memory_pg_idempotent",
                    return_value={"success": True, "deduped": False, "memory": {"id": 9}},
                ) as create:
                    out = dm.upsert_day_summary("2026-07-15")
        self.assertTrue(out["success"])
        self.assertTrue(out["created"])
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["write_dedupe_key"], "neena_day_2026-07-15")
        self.assertEqual(kwargs["memory_type"], dm.TYPE_DAY_SUMMARY)
        self.assertIn("Digest:", kwargs["content"])

    def test_week_upsert_synthesizes_days(self):
        day_rows_fake = [
            {"date_ist": "2026-07-13", "turn_count": 2, "digest": "a→b", "has_diary": True},
            {"date_ist": "2026-07-14", "turn_count": 1, "digest": "c→d", "has_diary": True},
        ]

        def fake_get(date_ist):
            for r in day_rows_fake:
                if r["date_ist"] == date_ist:
                    return {
                        "id": 1,
                        "content": f"Day diary {date_ist}\nDigest: {r['digest']}\nTimeline:\nx",
                        "metadata": {"digest": r["digest"], "turn_count": r["turn_count"]},
                    }
            return None

        with patch.object(dm, "upsert_day_summary", return_value={"success": True}):
            with patch.object(dm, "get_day_summary_row", side_effect=fake_get):
                with patch("services.memory.pg_repository.is_postgres_available", return_value={"available": True}):
                    with patch(
                        "services.memory.pg_repository.create_memory_pg_idempotent",
                        return_value={"success": True, "deduped": False, "memory": {"id": 11}},
                    ) as create:
                        out = dm.upsert_week_summary("2026-07-13", "2026-07-14", lazy_day_diaries=True)
        self.assertTrue(out["success"])
        self.assertEqual(out["turn_count_total"], 3)
        self.assertEqual(create.call_args.kwargs["memory_type"], dm.TYPE_WEEK_SUMMARY)
        self.assertIn("Week diary", create.call_args.kwargs["content"])


if __name__ == "__main__":
    unittest.main()
