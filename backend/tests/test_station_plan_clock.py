"""Station Clock plan + script length + azura webhook fast path."""
from __future__ import annotations

import unittest
from unittest.mock import patch


class TestStationPlanStore(unittest.TestCase):
    def test_build_and_advance(self):
        from services.tools import station_plan_store as store

        store.clear_plan()
        plan = store.build_shift_clock_plan(horizon="shift_4h", theme="Evening")
        self.assertEqual(plan["horizon"], "shift_4h")
        self.assertGreaterEqual(len(plan["blocks"]), 8)
        store.save_plan(plan)
        loaded = store.load_plan()
        self.assertEqual(loaded["plan_id"], plan["plan_id"])
        nxt = store.next_pending_block(loaded)
        self.assertIsNotNone(nxt)
        store.patch_block(loaded, nxt["id"], status="done")
        store.save_plan(loaded)
        again = store.next_pending_block(store.load_plan())
        self.assertNotEqual(again["id"], nxt["id"])
        store.clear_plan()

    def test_create_handler(self):
        from services.tools.catalog import ToolContext
        from services.tools.station_plan import _handle_create
        from services.tools import station_plan_store as store

        store.clear_plan()
        out = _handle_create(
            ToolContext(
                action="create_station_plan",
                slots={"horizon": "shift_3h"},
                snapshot={},
                owner_message="3 ghante plan",
            )
        )
        self.assertIsNotNone(out)
        self.assertEqual(out["action_type"], "STATION_PLAN_CREATED")
        self.assertIn("Station Clock", out["reply"])
        self.assertIn("not a lab show_plan", out["reply"].lower())
        pkt = out["factual_packet"]
        self.assertEqual(pkt["tool"], "create_station_plan")
        self.assertEqual(len(pkt["plan"]["blocks"]) >= 6, True)
        store.clear_plan()


class TestScriptLengthPolicy(unittest.TestCase):
    def test_long_request_raises_tokens(self):
        from services.brain.operations_workflows import _script_length_policy

        rule, tok = _script_length_policy("lamba RJ intro 600 words banao")
        self.assertIn("LONGER", rule)
        self.assertGreaterEqual(tok, 3072)
        rule2, tok2 = _script_length_policy("short intro")
        self.assertLess(tok2, tok)


class TestComposeNoShortWall(unittest.TestCase):
    def test_script_not_cut_at_1500(self):
        from services.brain.response_composer import compose_response

        body = "Word " * 400  # ~2000 chars
        out = compose_response(body)
        self.assertGreater(len(out), 1500)


class TestAzuraWebhook(unittest.TestCase):
    def test_record_and_latest(self):
        from services.broadcast import azura_events as ev

        entry = ev.record_event(
            {"type": "song_changed", "now_playing": {"song": {"title": "Test", "artist": "A"}}}
        )
        self.assertEqual(entry["title"], "Test")
        latest = ev.latest_events(1)
        self.assertTrue(latest)
        self.assertEqual(latest[0]["title"], "Test")


class TestCatalogAlias(unittest.TestCase):
    def test_daily_show_plan_aliases_to_station_plan(self):
        from services.tools import load_all
        from services.tools.catalog import get, normalize_tool_id

        load_all()
        self.assertEqual(normalize_tool_id("create_daily_show_plan"), "create_station_plan")
        self.assertEqual(normalize_tool_id("daily_show_plan"), "create_station_plan")
        spec = get("create_station_plan")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.route, "live_ops")


if __name__ == "__main__":
    unittest.main()
