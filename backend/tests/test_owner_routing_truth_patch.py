"""Owner routing + capabilities truth patch tests."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

_WORKSPACE = r"c:\Projects\radio station\radio-ai-manager\backend"
if os.path.isdir(_WORKSPACE):
    sys.path.insert(0, _WORKSPACE)


class TestDeterministicRouting(unittest.TestCase):
    def test_no_phrase_deterministic_routes(self):
        from services.brain.deterministic_routes import resolve_deterministic_action

        for msg in (
            "hi neena command center lock karo",
            "command center lock karo",
            "VM ka status batao",
            "capsule status batao",
            "5 min baad WhatsApp pe status bhej dena",
            "session kya hai",
        ):
            self.assertIsNone(resolve_deterministic_action(msg), msg)


class TestInterpreterLocalRoutes(unittest.TestCase):
    def test_routing_truth_no_phrase_override_for_session_chat(self):
        from services.brain.command_interpreter import _routing_truth_reclassify

        pkt = {"action": "timeout_diagnosis", "confidence": 0.9, "slots": {}}
        out = _routing_truth_reclassify(pkt, "session kya hai")
        self.assertEqual(out["action"], "timeout_diagnosis")


class TestLiveOpsExecution(unittest.TestCase):
    _SNAP = {
        "whatsapp_gateway": "offline",
        "stream": "unknown",
        "stream_stable": True,
        "latest_capsules": [],
    }

    def test_admin_lock_reply(self):
        from services.tools.live_ops_executor import try_execute_live_ops

        res = try_execute_live_ops("admin_lock", {}, snapshot=self._SNAP)
        reply = (res.get("reply") or "").lower()
        self.assertTrue("lock" in reply and "command center" in reply)
        self.assertEqual(res["ui_action"]["type"], "admin_lock")

    def test_auth_session_explain_reply(self):
        from services.tools.live_ops_executor import try_execute_live_ops

        res = try_execute_live_ops("auth_session_explain", {}, snapshot=self._SNAP)
        reply = res["reply"]
        self.assertIn("7 days", reply)
        self.assertNotIn("timeout diagnosis", reply.lower())

    @patch("services.brain.vm_status.psutil")
    def test_vm_status_reply(self, mock_psutil):
        from services.tools.live_ops_executor import try_execute_live_ops

        mock_psutil.cpu_percent.return_value = 12.0
        mock_psutil.virtual_memory.return_value = MagicMock(
            used=1_000_000_000, total=4_000_000_000, percent=25.0
        )
        mock_psutil.swap_memory.return_value = MagicMock(used=0, total=1_000_000_000)
        mock_psutil.disk_usage.return_value = MagicMock(percent=40.0, free=50_000_000_000)

        res = try_execute_live_ops("vm_status", {}, snapshot=self._SNAP)
        self.assertIn("VM/cloud status", res["reply"])
        self.assertIn("8080 local-only", res["reply"])

    def test_capabilities_truth_no_overclaim(self):
        from services.tools.live_ops_executor import try_execute_live_ops

        with patch("services.voice.gen_service.get_broadcast_audio_readiness") as mock_ready:
            mock_ready.return_value = {
                "ready_push_ready": False,
                "blockers": ["owner approval required"],
                "audio": {"can_produce_real_audio": False},
                "azuracast": {"ready_for_real_push": False},
            }
            res = try_execute_live_ops("capabilities", {}, snapshot=self._SNAP)
        reply = res["reply"]
        self.assertIn("Safe admin available", reply)
        self.assertTrue("blocked" in reply.lower())
        self.assertNotIn("AzuraCast upload queue safely gate ke saath", reply)
        meta = res.get("_capability_manifest_meta") or {}
        self.assertGreater(meta.get("capabilities_count", 0), 0)

    def test_broadcast_commands_blocked(self):
        from services.tools.live_ops_executor import try_execute_live_ops

        for msg in ("broadcast now", "azuracast par bhejo", "radio par chala do"):
            res = try_execute_live_ops(
                "send_azuracast", {}, snapshot=self._SNAP, owner_message=msg
            )
            self.assertIn("blocked", res["reply"].lower())


if __name__ == "__main__":
    unittest.main()
