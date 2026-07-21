"""W1 clock + W3 time_status morning remaining (savdhaan backlog)."""
from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch


class TestLiveClockBlock(unittest.TestCase):
    def test_format_contains_ist_authority(self):
        from services.memory.continuity import format_live_clock_block

        now = datetime(2026, 7, 16, 2, 31, 0)
        line = format_live_clock_block(now)
        self.assertIn("LIVE CLOCK", line)
        self.assertIn("IST=2026-07-16 02:31:00", line)
        self.assertNotIn("sir,", line.lower())

    def test_prompt_context_includes_clock(self):
        from services.memory import continuity as c

        with patch.object(
            c,
            "load_owner_continuity",
            return_value={
                "chat_turns": [],
                "working_context": {},
                "working_block": "",
                "short_context": "",
                "pending": None,
                "permanent_context_text": "",
                "permanent_hits": [],
            },
        ):
            ctx = c.build_owner_prompt_context("hi")
        self.assertIn("IST=", ctx.get("clock_block") or "")


class TestMorningRemaining(unittest.TestCase):
    def test_afternoon_until_next_morning(self):
        from services.tools.bind_handlers import _minutes_until_morning_ist

        now = datetime(2026, 7, 16, 14, 0, 0)
        mins = _minutes_until_morning_ist(now, morning_hour=6)
        # 14:00 → next 06:00 = 16 hours = 960 minutes
        self.assertEqual(mins, 960)

    def test_just_before_morning(self):
        from services.tools.bind_handlers import _minutes_until_morning_ist

        now = datetime(2026, 7, 16, 5, 50, 0)
        self.assertEqual(_minutes_until_morning_ist(now, morning_hour=6), 10)

    def test_at_morning_rolls_next_day(self):
        from services.tools.bind_handlers import _minutes_until_morning_ist

        now = datetime(2026, 7, 16, 6, 0, 0)
        self.assertEqual(_minutes_until_morning_ist(now, morning_hour=6), 24 * 60)

    def test_handler_packet_has_fields_no_sir(self):
        from services.tools.bind_handlers import _time_status_handler
        from services.tools.catalog import ToolContext

        ctx = ToolContext(action="time_status", slots={}, snapshot={})
        res = _time_status_handler(ctx) or {}
        packet = res.get("factual_packet") or {}
        self.assertEqual(packet.get("morning_local_hour"), 6)
        self.assertIn("minutes_until_local_morning", packet)
        self.assertIn("hours_until_morning", packet)
        self.assertNotIn("sir,", (res.get("reply") or "").lower())


if __name__ == "__main__":
    unittest.main()
