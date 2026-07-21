"""W2: Azura schedule hands — no SQLite fake grid."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestStationScheduleTruth(unittest.TestCase):
    def test_packet_never_uses_sqlite(self):
        from services.tools.live_ops_executor import try_execute_live_ops

        fake = {
            "checked": True,
            "timed_slots": [],
            "timed_schedule_available": False,
            "timed_schedule_status": "empty",
            "playlists": [{"id": 3, "name": "General", "is_enabled": True}],
            "queue_length": 1,
            "queue_peek": [{"title": "Song A", "artist": "X"}],
            "playing_next": {"title": "Song B", "artist": "Y"},
            "next_status": "ok",
            "errors": [],
        }
        with patch(
            "services.broadcast.azuracast_client.get_station_schedule_truth",
            return_value=fake,
        ):
            out = try_execute_live_ops("get_station_schedule", {}, snapshot={}, owner_message="schedule")
        self.assertEqual(out.get("action_type"), "STATION_SCHEDULE")
        fp = out["factual_packet"]
        self.assertFalse(fp.get("sqlite_grid_used"))
        self.assertEqual(fp.get("playlist_count"), 1)
        self.assertEqual(fp.get("timed_note"), "cannot_clock_schedule")

    def test_azura_down_cannot(self):
        from services.tools.live_ops_executor import try_execute_live_ops

        with patch(
            "services.broadcast.azuracast_client.get_station_schedule_truth",
            return_value={
                "checked": False,
                "errors": ["AZURACAST_BASE_URL missing"],
                "timed_slots": [],
                "playlists": [],
            },
        ):
            out = try_execute_live_ops("get_station_schedule", {}, snapshot={}, owner_message="x")
        self.assertEqual(out.get("action_type"), "STATION_SCHEDULE_CANNOT")
        self.assertIn("Cannot", out.get("reply", ""))
        self.assertEqual(out["factual_packet"].get("reason"), "azura_schedule_unavailable")

    def test_whats_next_unavailable(self):
        from services.tools.live_ops_executor import try_execute_live_ops

        with patch(
            "services.broadcast.azuracast_client.get_station_schedule_truth",
            return_value={
                "checked": True,
                "playing_next": None,
                "next_status": "next_unavailable",
                "queue_length": 0,
                "queue_peek": [],
            },
        ):
            out = try_execute_live_ops("whats_next", {}, snapshot={}, owner_message="next")
        self.assertEqual(out.get("action_type"), "WHATS_NEXT_UNAVAILABLE")
        self.assertEqual(out["factual_packet"].get("status"), "next_unavailable")

    def test_assign_needs_confirm(self):
        from services.tools.live_ops_executor import try_execute_live_ops

        out = try_execute_live_ops(
            "assign_capsule_to_playlist",
            {"capsule_id": 11},
            snapshot={},
            owner_message="assign",
        )
        self.assertEqual(out.get("action_type"), "ASSIGN_PLAYLIST_CONFIRM")
        self.assertTrue(out.get("require_confirmation"))

    def test_assign_executes_with_explicit(self):
        from services.tools.live_ops_executor import try_execute_live_ops

        with patch(
            "services.broadcast.playback_control.ensure_capsule_playback",
            return_value={
                "success": True,
                "playback_status": "playlist_assigned",
                "message": "Assigned ok",
                "safe_details": {"playlist_id": "5"},
            },
        ):
            out = try_execute_live_ops(
                "assign_capsule_to_playlist",
                {"capsule_id": 11, "playlist_id": "5", "explicit_approval": True},
                snapshot={},
                owner_message="haan",
            )
        self.assertEqual(out.get("action_type"), "ASSIGN_PLAYLIST")
        self.assertEqual(out["factual_packet"].get("status"), "ok")


class TestScheduleRoutes(unittest.TestCase):
    def test_schedule_not_phrase_nlu(self):
        """AGENTS hygiene: schedule/whats_next are interpreter+catalog, not phrase gates."""
        from services.brain.deterministic_routes import resolve_deterministic_action

        self.assertIsNone(resolve_deterministic_action("aaj schedule / playlists kya hain"))
        self.assertIsNone(resolve_deterministic_action("whats next on stream"))


class TestScheduleKernel(unittest.TestCase):
    def test_kernel_schedule_recipe(self):
        from services.agent.run_kernel import run_owner_kernel

        fake = {
            "reply": "Azura truth",
            "action_type": "STATION_SCHEDULE",
            "factual_packet": {
                "tool": "get_station_schedule",
                "status": "ok",
                "sqlite_grid_used": False,
                "playlist_count": 2,
            },
        }
        with patch(
            "services.brain.operations_workflows.try_handle_interpreter_packet",
            return_value=None,
        ), patch(
            "services.tools.live_ops_executor.try_execute_live_ops",
            return_value=fake,
        ), patch(
            "services.tools.loop.extend_live_ops_result",
            side_effect=lambda **kw: kw["first_result"],
        ):
            out = run_owner_kernel(
                message="aaj schedule dikhao",
                interpreter_packet={"action": "get_station_schedule", "slots": {}},
                selected_model="test",
                mem_packet={},
                mem_context="",
                tb=MagicMock(),
            )
        self.assertEqual(out.get("action_type"), "STATION_SCHEDULE")
        self.assertEqual(out["owner_run"].get("status"), "verified")


if __name__ == "__main__":
    unittest.main()
