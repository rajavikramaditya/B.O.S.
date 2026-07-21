"""Tests for listener_path_service — diagnose + allowlisted app_config updates."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


class TestListenerPathService(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmpdir.name, "test.db")
        self.db_patch = patch("database.DB_PATH", self.db_path)
        self.db_patch.start()
        import database as db

        db.init_db()
        db.update_app_config("api_base_url", "https://api.orairadio.in")
        db.update_app_config("stream_url", "https://stream.orairadio.in/listen/orai_radio/radio.mp3")
        db.update_app_config("backup_stream_url", "")

    def tearDown(self):
        self.db_patch.stop()
        self._tmpdir.cleanup()

    def test_set_requires_confirmation(self):
        from services.broadcast.listener_path import set_app_listener_config

        res = set_app_listener_config(stream_url="http://35.244.15.150/listen/orai_radio/radio.mp3")
        self.assertTrue(res.get("require_confirmation"))
        self.assertFalse(res.get("success"))

    def test_set_allowlist_and_apply(self):
        from services.broadcast.listener_path import get_app_listener_config, set_app_listener_config

        res = set_app_listener_config(
            stream_url="http://35.244.15.150/listen/orai_radio/radio.mp3",
            api_base_url="http://35.244.15.150:8080",
            confirmed=True,
        )
        self.assertTrue(res.get("success"))
        cfg = get_app_listener_config()
        self.assertEqual(cfg["stream_url"], "http://35.244.15.150/listen/orai_radio/radio.mp3")
        self.assertEqual(cfg["api_base_url"], "http://35.244.15.150:8080")

    def test_bootstrap_v2_allowlist_keys(self):
        import database as db
        from services.broadcast.listener_path import APP_CONFIG_ALLOWLIST

        for key in ("config_version", "force_refresh", "min_app_version"):
            self.assertIn(key, APP_CONFIG_ALLOWLIST)
            db.update_app_config(key, "1" if key != "force_refresh" else "false")
        cfg = db.get_app_config()
        self.assertEqual(cfg.get("config_version"), 1)
        self.assertEqual(cfg.get("min_app_version"), 1)
        self.assertFalse(cfg.get("force_refresh"))

    def test_diagnose_station_ok_app_url_dead(self):
        import services.broadcast.listener_path as lps

        with patch.object(
            lps,
            "_dns_ok",
            return_value={"ok": False, "host": "dead.example", "ips": [], "error": "gaierror"},
        ):
            with patch.object(
                lps,
                "_http_probe",
                return_value={
                    "ok": True,
                    "url": "http://35.244.15.150/listen/orai_radio/radio.mp3",
                    "http_status": 200,
                    "bytes_sample": 200,
                    "error": None,
                },
            ):
                with patch(
                    "services.broadcast.azuracast_client.get_azuracast_status",
                    return_value={
                        "configured": True,
                        "stream_reachable": True,
                        "icecast_status": "online",
                        "now_playing_title": "Test Song",
                        "listener_count": 1,
                        "stream_url": "http://35.244.15.150/listen/orai_radio/radio.mp3",
                    },
                ):
                    diag = lps.diagnose_listener_path()
        self.assertEqual(diag.get("verdict"), "station_ok_app_url_dead")
        self.assertIsNotNone(diag.get("proposed_fix"))

    def test_live_ops_diagnose_action(self):
        from services.brain.live_ops_executor import try_execute_live_ops

        fake = {
            "verdict": "station_ok_app_url_dead",
            "next_step": "DNS fix",
            "station": {"now_playing_title": "x"},
            "icecast_probe": {"ok": True},
            "app_stream_dns": {"ok": False},
            "app_stream_probe": {"ok": False},
            "api_dns": {"ok": False},
            "api_config_probe": {"ok": False},
            "proposed_fix": {"stream_url": "http://x", "api_base_url": "http://y"},
            "message": "test",
        }
        with patch("services.brain.feature_flags.listener_path_tools_enabled", return_value=True):
            with patch("services.broadcast.listener_path.diagnose_listener_path", return_value=fake):
                with patch("services.broadcast.listener_path.format_diagnose_reply", return_value="diag reply"):
                    res = try_execute_live_ops("diagnose_listener_path", {}, snapshot={})
        self.assertEqual(res.get("action_type"), "DIAGNOSE_LISTENER_PATH")
        self.assertTrue(res.get("require_confirmation"))
        self.assertEqual(res.get("pending_fix_action"), "fix_app_listener_path")


if __name__ == "__main__":
    unittest.main()
