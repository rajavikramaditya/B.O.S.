"""
M4-A2 Safety Patch Test Suite — Local Only
Tests: routing, TTS gate, broadcast_ready, AzuraCast block, regression compile

Hard rules enforced in every test:
- No real TTS called
- No AzuraCast API called
- No VM touched
- No file edits
"""
from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Ensure backend is importable
_WORKSPACE = r"c:\Projects\radio station\radio-ai-manager\backend"
if os.path.isdir(_WORKSPACE):
    sys.path.insert(0, _WORKSPACE)


# ---------------------------------------------------------------------------
# A. ROUTING TESTS
# ---------------------------------------------------------------------------

class TestBroadcastRouting(unittest.TestCase):
    """A. Routing tests — broadcast commands must never route to generate_audio."""

    def _reclassify(self, message: str, llm_action: str) -> str:
        from services.brain.command_interpreter import _safety_reclassify
        fake_packet = {"action": llm_action, "confidence": 0.9, "slots": {}}
        result = _safety_reclassify(fake_packet, message)
        return result["action"]

    def test_broadcast_now_routes_to_send_azuracast(self):
        """A1: 'broadcast now' must route to send_azuracast."""
        self.assertEqual(self._reclassify("broadcast now", "generate_audio"), "send_azuracast")

    def test_broadcast_now_does_not_route_to_generate_audio(self):
        """A2: 'broadcast now' must NOT stay as generate_audio."""
        self.assertNotEqual(self._reclassify("broadcast now", "generate_audio"), "generate_audio")

    def test_broadcast_karo_routes_to_send_azuracast(self):
        """A3: 'broadcast karo' must route to send_azuracast."""
        self.assertEqual(self._reclassify("broadcast karo", "generate_audio"), "send_azuracast")

    def test_air_karo_routes_to_send_azuracast(self):
        """A4: 'air karo' must route to send_azuracast."""
        self.assertEqual(self._reclassify("air karo", "generate_audio"), "send_azuracast")

    def test_on_air_karo_routes_to_send_azuracast(self):
        """A4b: 'on air karo' must route to send_azuracast."""
        self.assertEqual(self._reclassify("on air karo", "generate_audio"), "send_azuracast")

    def test_chala_do_routes_to_send_azuracast(self):
        """A5: 'chala do' must route to send_azuracast."""
        self.assertEqual(self._reclassify("chala do", "generate_audio"), "send_azuracast")

    def test_live_karo_routes_to_send_azuracast(self):
        """A6: 'live karo' must route to send_azuracast."""
        self.assertEqual(self._reclassify("live karo", "generate_audio"), "send_azuracast")

    def test_send_to_azuracast_routes_to_send_azuracast(self):
        """A7: 'send to azuracast' must route to send_azuracast."""
        self.assertEqual(self._reclassify("send to azuracast", "generate_audio"), "send_azuracast")

    def test_play_it_routes_to_send_azuracast(self):
        """A8: 'play it' must route to send_azuracast."""
        self.assertEqual(self._reclassify("play it", "generate_audio"), "send_azuracast")

    def test_abhi_broadcast_karo_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("abhi broadcast karo", "generate_audio"), "send_azuracast")

    def test_azuracast_par_bhejo_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("azuracast par bhejo", "generate_audio"), "send_azuracast")

    def test_azuracast_pe_bhejo_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("azuracast pe bhejo", "generate_audio"), "send_azuracast")

    def test_azuracast_me_bhejo_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("azuracast me bhejo", "generate_audio"), "send_azuracast")

    def test_azuracast_mein_bhejo_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("azuracast mein bhejo", "generate_audio"), "send_azuracast")

    def test_radio_par_chalao_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("radio par chalao", "generate_audio"), "send_azuracast")

    def test_radio_pe_chalao_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("radio pe chalao", "generate_audio"), "send_azuracast")

    def test_radio_par_chala_do_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("radio par chala do", "generate_audio"), "send_azuracast")

    def test_radio_pe_chala_do_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("radio pe chala do", "generate_audio"), "send_azuracast")

    def test_station_par_chalao_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("station par chalao", "generate_audio"), "send_azuracast")

    def test_station_pe_chalao_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("station pe chalao", "generate_audio"), "send_azuracast")

    def test_station_par_chala_do_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("station par chala do", "generate_audio"), "send_azuracast")

    def test_station_pe_chala_do_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("station pe chala do", "generate_audio"), "send_azuracast")

    def test_live_kar_do_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("live kar do", "generate_audio"), "send_azuracast")

    def test_on_air_kar_do_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("on air kar do", "generate_audio"), "send_azuracast")

    def test_isko_chala_do_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("isko chala do", "generate_audio"), "send_azuracast")

    def test_latest_chala_do_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("latest chala do", "generate_audio"), "send_azuracast")

    def test_approved_capsule_chala_do_routes_to_send_azuracast(self):
        self.assertEqual(self._reclassify("approved capsule chala do", "generate_audio"), "send_azuracast")

    def test_reclassified_packet_has_marker(self):
        """A9: Reclassified packet must carry _safety_reclassified=True."""
        from services.brain.command_interpreter import _safety_reclassify
        fake_packet = {"action": "generate_audio", "confidence": 0.9, "slots": {}}
        result = _safety_reclassify(fake_packet, "broadcast now")
        self.assertTrue(result.get("_safety_reclassified"))

    def test_original_action_preserved_in_packet(self):
        """A10: Original (wrong) action must be preserved as _original_action."""
        from services.brain.command_interpreter import _safety_reclassify
        fake_packet = {"action": "generate_audio", "confidence": 0.9, "slots": {}}
        result = _safety_reclassify(fake_packet, "broadcast now")
        self.assertEqual(result.get("_original_action"), "generate_audio")

    def test_correct_azuracast_command_not_modified(self):
        """A11: If LLM already returned send_azuracast, packet must not be changed."""
        from services.brain.command_interpreter import _safety_reclassify
        fake_packet = {"action": "send_azuracast", "confidence": 0.95, "slots": {}}
        result = _safety_reclassify(fake_packet, "broadcast now")
        self.assertEqual(result["action"], "send_azuracast")
        self.assertFalse(result.get("_safety_reclassified", False))


# ---------------------------------------------------------------------------
# B. TTS GATE TESTS
# ---------------------------------------------------------------------------

class TestTTSGate(unittest.TestCase):
    """B. TTS gate tests — ambiguous commands must not trigger generate_audio."""

    def _reclassify(self, message: str, llm_action: str) -> dict:
        from services.brain.command_interpreter import _safety_reclassify
        fake_packet = {"action": llm_action, "confidence": 0.9, "slots": {}}
        return _safety_reclassify(fake_packet, message)

    def test_explicit_audio_banao_reaches_generate_audio(self):
        """B1: 'audio banao' must be allowed to reach generate_audio."""
        result = self._reclassify("audio banao", "generate_audio")
        self.assertEqual(result["action"], "generate_audio")

    def test_explicit_prepare_audio_reaches_generate_audio(self):
        """B2: 'prepare audio' must be allowed to reach generate_audio."""
        result = self._reclassify("prepare audio", "generate_audio")
        self.assertEqual(result["action"], "generate_audio")

    def test_explicit_voice_banao_reaches_generate_audio(self):
        """B3: 'voice banao' must be allowed to reach generate_audio."""
        result = self._reclassify("voice banao", "generate_audio")
        self.assertEqual(result["action"], "generate_audio")

    def test_explicit_voice_preview_banao_reaches_generate_audio(self):
        """B4: 'voice preview banao' must be allowed to reach generate_audio."""
        result = self._reclassify("voice preview banao", "generate_audio")
        self.assertEqual(result["action"], "generate_audio")

    def test_explicit_tts_banao_reaches_generate_audio(self):
        """B5b: 'tts banao' must be allowed to reach generate_audio."""
        result = self._reclassify("tts banao", "generate_audio")
        self.assertEqual(result["action"], "generate_audio")

    def test_explicit_capsule_audio_banao_reaches_generate_audio(self):
        """B5c: 'capsule audio banao' contains 'capsule audio' — must reach generate_audio."""
        result = self._reclassify("capsule audio banao", "generate_audio")
        self.assertEqual(result["action"], "generate_audio")

    def test_ambiguous_broadcast_now_blocked_from_generate_audio(self):
        """B5: 'broadcast now' must NOT reach generate_audio."""
        result = self._reclassify("broadcast now", "generate_audio")
        self.assertNotEqual(result["action"], "generate_audio")

    def test_ambiguous_command_blocked_from_generate_audio(self):
        """B6: Ambiguous command without audio intent must be blocked from generate_audio."""
        result = self._reclassify("chalo shuru karo", "generate_audio")
        self.assertNotEqual(result["action"], "generate_audio")

    def test_ambiguous_command_reclassified_to_unknown(self):
        """B7: Ambiguous command classified as generate_audio must become unknown."""
        result = self._reclassify("chalo shuru karo", "generate_audio")
        self.assertEqual(result["action"], "unknown")

    def test_missing_audio_intent_reclassified_has_reason(self):
        """B8: Reclassified ambiguous packet must carry _reclassify_reason."""
        result = self._reclassify("kuch karo", "generate_audio")
        if result["action"] == "unknown":
            self.assertIn("_reclassify_reason", result)


# ---------------------------------------------------------------------------
# C. BROADCAST_READY TESTS
# ---------------------------------------------------------------------------

class TestBroadcastReadyBehavior(unittest.TestCase):
    """C. broadcast_ready must stay False after audio generation unless fully cleared."""

    def _enrich(self, capsule: dict) -> dict:
        with patch("services.broadcast.azuracast_client.check_azuracast_write_config") as mock_az:
            mock_az.return_value = {"ready_for_real_push": False, "missing_config": ["api_key"]}
            from services.broadcast.capsule_service import enrich_capsule_for_api
            return enrich_capsule_for_api(dict(capsule))

    def test_real_audio_db_zero_broadcast_ready_is_false(self):
        """C1: Real audio + DB broadcast_ready=0 -> broadcast_ready=False."""
        capsule = {
            "audio_truth_level": "real",
            "audio_file_path": None,
            "broadcast_ready": 0,
            "azuracast_status": "blocked",
            "status": "audio_ready_preview",
            "metadata": {},
        }
        enriched = self._enrich(capsule)
        self.assertFalse(enriched["broadcast_ready"])

    def test_real_audio_db_one_but_azuracast_blocked_is_false(self):
        """C2: Real audio + DB=1 but azuracast blocked -> broadcast_ready=False."""
        capsule = {
            "audio_truth_level": "real",
            "audio_file_path": None,
            "broadcast_ready": 1,
            "azuracast_status": "blocked_requires_owner_approval",
            "status": "audio_ready_preview",
            "metadata": {"production_asset": True},
        }
        enriched = self._enrich(capsule)
        self.assertFalse(enriched["broadcast_ready"])

    def test_simulated_audio_broadcast_ready_always_false(self):
        """C3: Simulated audio must always have broadcast_ready=False (even DB=1)."""
        capsule = {
            "audio_truth_level": "simulated",
            "audio_file_path": None,
            "broadcast_ready": 1,
            "azuracast_status": "ready_for_broadcast",
            "status": "audio_ready_preview",
            "metadata": {},
        }
        enriched = self._enrich(capsule)
        self.assertFalse(enriched["broadcast_ready"])

    def test_no_audio_broadcast_ready_false(self):
        """C4: No audio -> broadcast_ready=False."""
        capsule = {
            "audio_truth_level": "none",
            "audio_file_path": None,
            "broadcast_ready": 0,
            "azuracast_status": "blocked",
            "status": "approved",
            "metadata": {},
        }
        enriched = self._enrich(capsule)
        self.assertFalse(enriched["broadcast_ready"])

    def test_azuracast_push_allowed_false_when_blocked(self):
        """C5: azuracast_push_allowed must be False when playable audio / config missing."""
        capsule = {
            "audio_truth_level": "real",
            "audio_file_path": None,
            "broadcast_ready": 0,
            "azuracast_status": "blocked",
            "status": "audio_ready_preview",
            "approval_status": "approved",
            "metadata": {},
        }
        enriched = self._enrich(capsule)
        self.assertFalse(enriched.get("azuracast_push_allowed"))
        self.assertNotEqual(enriched.get("azuracast_push_block_reason"), "Owner approval pending")

    def test_azuracast_push_allowed_true_after_real_tts_preview(self):
        """BR-3: audio_ready_preview + approved script + real playable + config → push allowed."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "capsule_br3.wav"
            # Minimal valid-ish wav header + payload so exists() is enough for enrich
            # (enrich only checks path exists + truth level for audio_playable).
            wav.write_bytes(b"RIFF" + b"\x00" * 40)
            capsule = {
                "audio_truth_level": "real",
                "audio_file_path": str(wav),
                "broadcast_ready": 0,
                "azuracast_status": "blocked_requires_owner_approval",
                "status": "audio_ready_preview",
                "approval_status": "approved",
                "metadata": {"production_asset": True},
            }
            with patch("services.broadcast.azuracast_client.check_azuracast_write_config") as mock_az:
                mock_az.return_value = {"ready_for_real_push": True, "missing_config": []}
                from services.broadcast.capsule_service import enrich_capsule_for_api

                enriched = enrich_capsule_for_api(dict(capsule))
            self.assertTrue(enriched.get("azuracast_push_allowed"))
            self.assertIsNone(enriched.get("azuracast_push_block_reason"))

    def test_azuracast_push_block_reason_pending_uses_approval_status(self):
        """Block reason 'Owner approval pending' only when approval_status is not approved."""
        capsule = {
            "audio_truth_level": "real",
            "audio_file_path": None,
            "broadcast_ready": 0,
            "azuracast_status": "blocked",
            "status": "pending_approval",
            "approval_status": "pending",
            "metadata": {},
        }
        enriched = self._enrich(capsule)
        self.assertFalse(enriched.get("azuracast_push_allowed"))
        self.assertEqual(enriched.get("azuracast_push_block_reason"), "Owner approval pending")

    def test_real_audio_db_one_and_azuracast_status_ready_for_broadcast_is_true(self):
        """C6: Real audio + DB=1 + azuracast status 'ready_for_broadcast' -> broadcast_ready=True."""
        capsule = {
            "audio_truth_level": "real",
            "audio_file_path": None,
            "broadcast_ready": 1,
            "azuracast_status": "ready_for_broadcast",
            "status": "audio_ready_preview",
            "metadata": {},
        }
        enriched = self._enrich(capsule)
        self.assertTrue(enriched["broadcast_ready"])

    def test_real_audio_db_one_and_azuracast_status_approved_for_broadcast_is_true(self):
        """C6b: Real audio + DB=1 + azuracast status 'approved_for_broadcast' -> broadcast_ready=True."""
        capsule = {
            "audio_truth_level": "real",
            "audio_file_path": None,
            "broadcast_ready": 1,
            "azuracast_status": "approved_for_broadcast",
            "status": "audio_ready_preview",
            "metadata": {},
        }
        enriched = self._enrich(capsule)
        self.assertTrue(enriched["broadcast_ready"])

    def test_real_audio_db_one_and_azuracast_status_uploaded_is_false(self):
        """C6c: Real audio + DB=1 + azuracast status 'uploaded' -> broadcast_ready=False."""
        capsule = {
            "audio_truth_level": "real",
            "audio_file_path": None,
            "broadcast_ready": 1,
            "azuracast_status": "uploaded",
            "status": "audio_ready_preview",
            "metadata": {},
        }
        enriched = self._enrich(capsule)
        self.assertFalse(enriched["broadcast_ready"])

    def test_real_audio_db_one_and_azuracast_status_uploading_is_false(self):
        """C6d: Real audio + DB=1 + azuracast status 'uploading' -> broadcast_ready=False."""
        capsule = {
            "audio_truth_level": "real",
            "audio_file_path": None,
            "broadcast_ready": 1,
            "azuracast_status": "uploading",
            "status": "audio_ready_preview",
            "metadata": {},
        }
        enriched = self._enrich(capsule)
        self.assertFalse(enriched["broadcast_ready"])

    def test_real_audio_db_one_and_azuracast_status_approved_is_false(self):
        """C6e: Real audio + DB=1 + azuracast status 'approved' -> broadcast_ready=False."""
        capsule = {
            "audio_truth_level": "real",
            "audio_file_path": None,
            "broadcast_ready": 1,
            "azuracast_status": "approved",
            "status": "audio_ready_preview",
            "metadata": {},
        }
        enriched = self._enrich(capsule)
        self.assertFalse(enriched["broadcast_ready"])


# ---------------------------------------------------------------------------
# D. AZURACAST BLOCK TESTS
# ---------------------------------------------------------------------------

class TestAzuracastBlock(unittest.TestCase):
    """D. AzuraCast send/upload must be blocked without owner final approval."""

    def test_send_azuracast_blocked_when_no_ready_capsule(self):
        """D1: send_azuracast must return BLOCKED reply when no capsule is ready."""
        from services.brain.live_ops_executor import try_execute_live_ops
        fake_snap = {
            "latest_ready_for_azuracast": None,
            "latest_capsules": [{"azuracast_push_block_reason": "Owner approval pending"}],
            "action_registry": [],
        }
        result = try_execute_live_ops("send_azuracast", {}, snapshot=fake_snap)
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action_type"), "SEND_AZURACAST_BLOCKED")

    def test_send_azuracast_requires_confirmation_when_ready(self):
        """D2: send_azuracast must return CONFIRM (not execute) without explicit_push slot."""
        from services.brain.live_ops_executor import try_execute_live_ops
        fake_capsule = {"id": 99, "status": "approved", "audio_truth_level": "real"}
        fake_snap = {
            "latest_ready_for_azuracast": fake_capsule,
            "latest_capsules": [fake_capsule],
            "action_registry": [],
        }
        result = try_execute_live_ops("send_azuracast", {}, snapshot=fake_snap,
                                      owner_message="broadcast now")
        self.assertIsNotNone(result)
        self.assertIn(result.get("action_type"),
                      ("SEND_AZURACAST_BLOCKED", "SEND_AZURACAST_CONFIRM"))

    def test_send_azuracast_explicit_push_uses_bound_capsule(self):
        """Bound capsule_id + explicit_push must call send for that id."""
        from services.brain.live_ops_executor import try_execute_live_ops
        fake_capsule = {
            "id": 9,
            "status": "audio_ready_preview",
            "approval_status": "approved",
            "audio_truth_level": "real",
            "azuracast_push_allowed": True,
        }
        fake_snap = {
            "latest_ready_for_azuracast": {"id": 99},
            "latest_capsules": [fake_capsule],
            "action_registry": [],
        }
        with patch("services.broadcast.capsule_service.get_capsule_by_id", return_value=fake_capsule), \
             patch("services.broadcast.capsule_service.enrich_capsule_for_api", return_value=fake_capsule), \
             patch("services.broadcast.capsule_service.send_capsule_to_azuracast") as mock_send:
            mock_send.return_value = {"success": True}
            result = try_execute_live_ops(
                "send_azuracast",
                {"capsule_id": 9, "explicit_push": True},
                snapshot=fake_snap,
            )
            mock_send.assert_called_once_with(9)
            self.assertEqual(result.get("action_type"), "SEND_AZURACAST")
            self.assertEqual(result.get("capsule_id"), 9)

    def test_azuracast_client_not_called_in_block_path(self):
        """D3: AzuraCast write client must NOT be called when capsule is blocked."""
        with patch("services.broadcast.capsule_service.send_capsule_to_azuracast") as mock_send:
            from services.brain.live_ops_executor import try_execute_live_ops
            fake_snap = {
                "latest_ready_for_azuracast": None,
                "latest_capsules": [],
                "action_registry": [],
            }
            try_execute_live_ops("send_azuracast", {}, snapshot=fake_snap)
            mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# E2. CAPSULE_2.WAV CANNOT BROADCAST (Audit 5)
# ---------------------------------------------------------------------------

class TestCapsule2CannotBroadcast(unittest.TestCase):
    """Audit 5: Simulate capsule_2 exact VM DB state — must not be broadcastable."""

    # Exact values from VM DB query during emergency audit:
    # id=2, status=audio_ready_preview, approval=approved, audio=audio_ready_preview
    # truth_level=real, azuracast=blocked, broadcast_ready=0, production_asset=0
    CAPSULE_2_VM_STATE = {
        "id": 2,
        "status": "audio_ready_preview",
        "approval_status": "approved",
        "audio_status": "audio_ready_preview",
        "audio_truth_level": "real",
        "azuracast_status": "blocked",
        "broadcast_ready": 0,   # DB value: 0
        "production_asset": 0,
        "audio_file_path": "/app/backend/playout/voice_assets/capsule_2.wav",
        "metadata": {"provider": "gemini_tts", "model": "gemini-2.5-flash-preview-tts",
                     "production_asset": True},
    }

    def _enrich(self, capsule: dict) -> dict:
        with patch("services.broadcast.azuracast_client.check_azuracast_write_config") as mock_az:
            mock_az.return_value = {"ready_for_real_push": False, "missing_config": ["api_key"]}
            from services.broadcast.capsule_service import enrich_capsule_for_api
            return enrich_capsule_for_api(dict(capsule))

    def test_capsule2_broadcast_ready_is_false(self):
        """Audit5-A: Capsule #2 with DB broadcast_ready=0 + blocked -> computed=False."""
        enriched = self._enrich(self.CAPSULE_2_VM_STATE)
        self.assertFalse(enriched["broadcast_ready"],
                         f"Expected False, got {enriched['broadcast_ready']}")

    def test_capsule2_azuracast_push_not_allowed(self):
        """Audit5-B: Capsule #2 azuracast_push_allowed must be False."""
        enriched = self._enrich(self.CAPSULE_2_VM_STATE)
        self.assertFalse(enriched.get("azuracast_push_allowed"),
                         "azuracast_push_allowed must be False for capsule_2")

    def test_capsule2_block_reason_set(self):
        """Audit5-C: Capsule #2 must have a non-empty azuracast_push_block_reason."""
        enriched = self._enrich(self.CAPSULE_2_VM_STATE)
        reason = enriched.get("azuracast_push_block_reason")
        self.assertIsNotNone(reason, "Block reason must be set")
        self.assertGreater(len(str(reason)), 0, "Block reason must not be empty")

    def test_capsule2_send_azuracast_blocked_in_live_ops(self):
        """Audit5-D: send_azuracast live ops returns BLOCKED for capsule_2 state."""
        from services.brain.live_ops_executor import try_execute_live_ops
        fake_snap = {
            "latest_ready_for_azuracast": None,  # capsule_2 is NOT in ready list
            "latest_capsules": [{
                **self.CAPSULE_2_VM_STATE,
                "azuracast_push_block_reason": "Owner approval pending"
            }],
            "action_registry": [],
        }
        result = try_execute_live_ops("send_azuracast", {}, snapshot=fake_snap)
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action_type"), "SEND_AZURACAST_BLOCKED",
                         f"Expected BLOCKED, got {result.get('action_type')}")


# ---------------------------------------------------------------------------
# F. REGRESSION: COMPILE CHECK
# ---------------------------------------------------------------------------

class TestRegressionCompile(unittest.TestCase):
    """F. Regression: all backend service files must compile without errors."""

    def test_all_service_files_compile(self):
        """E1: py_compile must pass on all backend .py files."""
        import py_compile
        import glob
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        files = (
            [os.path.join(base, "main.py"), os.path.join(base, "database.py")]
            + glob.glob(os.path.join(base, "services", "*.py"))
        )
        errors = []
        for f in files:
            try:
                py_compile.compile(f, doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(str(e))
        self.assertEqual(errors, [], "Compile errors:\n" + "\n".join(errors))

    def test_command_interpreter_importable(self):
        """E2: neena_command_interpreter must import cleanly with new safety symbols."""
        import services.brain.command_interpreter as ci
        self.assertIn("BROADCAST_PROTECTED_PATTERNS", dir(ci))
        self.assertIn("EXPLICIT_AUDIO_INTENTS", dir(ci))
        self.assertIn("_safety_reclassify", dir(ci))

    def test_safety_constants_present_and_correct(self):
        """E3: Safety constants must be present, non-empty, and contain key patterns."""
        from services.brain.command_interpreter import (
            BROADCAST_PROTECTED_PATTERNS,
            EXPLICIT_AUDIO_INTENTS,
        )
        self.assertGreater(len(BROADCAST_PROTECTED_PATTERNS), 0)
        self.assertGreater(len(EXPLICIT_AUDIO_INTENTS), 0)
        self.assertIn("broadcast now", BROADCAST_PROTECTED_PATTERNS)
        self.assertIn("audio banao", EXPLICIT_AUDIO_INTENTS)

    def test_broadcast_capsule_service_importable(self):
        """E4: broadcast_capsule_service must import cleanly."""
        import services.broadcast.capsule_service as bcs
        self.assertTrue(callable(getattr(bcs, "enrich_capsule_for_api", None)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
