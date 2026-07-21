"""AzuraCast write kill-switch — M4-A1 hard-block replaced by AZURACAST_WRITES_ENABLED."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

_WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _WORKSPACE not in sys.path:
    sys.path.insert(0, _WORKSPACE)

import services.broadcast.azuracast_client as az


class TestAzuracastWritesGate(unittest.TestCase):
    def test_writes_disabled_by_default(self):
        with patch.dict(os.environ, {"AZURACAST_WRITES_ENABLED": ""}, clear=False):
            self.assertFalse(az.azuracast_writes_enabled())

    def test_upload_blocked_when_flag_off(self):
        with patch.dict(os.environ, {"AZURACAST_WRITES_ENABLED": "false"}, clear=False):
            res = az.upload_media_file("/tmp/fake.mp3")
            self.assertFalse(res.get("success"))
            self.assertIn("AZURACAST_WRITES_ENABLED", res.get("error", ""))

    def test_upload_reaches_config_check_when_flag_on(self):
        with patch.dict(
            os.environ,
            {
                "AZURACAST_WRITES_ENABLED": "true",
                "AZURACAST_BASE_URL": "",
                "AZURACAST_API_KEY": "",
            },
            clear=False,
        ):
            res = az.upload_media_file("/tmp/fake.mp3")
            self.assertFalse(res.get("success"))
            # Past kill-switch → missing config path (not M4-A1 hard-block)
            self.assertNotIn("M4-A1", res.get("error", ""))
            self.assertIn("missing", (res.get("error") or "").lower())

    def test_write_config_reports_writes_enabled(self):
        with patch.dict(os.environ, {"AZURACAST_WRITES_ENABLED": "true"}, clear=False):
            cfg = az.check_azuracast_write_config()
            self.assertTrue(cfg.get("writes_enabled"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
