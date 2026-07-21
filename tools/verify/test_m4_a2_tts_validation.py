import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import wave
import struct
import math
import tempfile
import sqlite3
import json

# Ensure backend directory is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

import database as db
from services.voice.gen_service import (
    validate_audio_file,
    safe_delete_invalid_file,
    VOICE_ASSETS_DIR,
    render_script_audio,
    generate_capsule_audio
)
from services.broadcast.capsule_service import (
    update_capsule_audio_status,
    create_capsule_from_script,
    get_capsule_by_id,
    send_capsule_to_azuracast
)

class TestTTSValidation(unittest.TestCase):
    def setUp(self):
        # Setup clean temporary SQLite database
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        
        # Patch database path
        self.db_path_patch = patch("database.DB_PATH", self.temp_db_path)
        self.db_path_patch.start()
        
        db.init_db()
        
        # Save original env and patch config
        self.original_env = dict(os.environ)
        os.environ["ALLOW_SIMULATED_TTS_DEV_ONLY"] = "true"
        
        # Setup temporary directories for audio testing
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_assets_dir = self.temp_dir_obj.name
        
        self.assets_dir_patch = patch("services.voice.gen_service.VOICE_ASSETS_DIR", self.temp_assets_dir)
        self.assets_dir_patch.start()
        
        # Patch activity log
        self.activity_patch = patch("database.add_activity_log", return_value=None)
        self.activity_patch.start()

    def tearDown(self):
        self.assets_dir_patch.stop()
        self.db_path_patch.stop()
        self.activity_patch.stop()
        self.temp_dir_obj.cleanup()
        
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass
                
        os.environ.clear()
        os.environ.update(self.original_env)

    def _create_valid_wav(self, path, duration=0.5):
        sample_rate = 22050
        n_frames = int(sample_rate * duration)
        frames = bytearray()
        for i in range(n_frames):
            val = int(32767 * 0.12 * math.sin(2 * math.pi * 440 * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(bytes(frames))

    def _create_valid_mp3(self, path):
        # 10 bytes ID3 header + 10 bytes content
        id3_header = b'ID3\x03\x00\x00\x00\x00\x00\n' + b'x'*10
        # MPEG sync frame marker b'\xff\xfb' (11111111 11111011) + padding
        mpeg_sync = b'\xff\xfb\x90\x44' + b'\x00'*150
        with open(path, "wb") as f:
            f.write(id3_header + mpeg_sync)

    def test_01_valid_wav_passes(self):
        wav_path = os.path.join(self.temp_assets_dir, "test_valid.wav")
        self._create_valid_wav(wav_path, duration=0.5)
        
        res = validate_audio_file(wav_path)
        self.assertTrue(res["valid"])
        self.assertEqual(res["format"], "wav")
        self.assertEqual(res["duration"], 0.5)
        self.assertEqual(res["sample_rate"], 22050)
        self.assertEqual(res["channels"], 1)

    def test_02_short_wav_fails(self):
        wav_path = os.path.join(self.temp_assets_dir, "test_short.wav")
        self._create_valid_wav(wav_path, duration=0.1) # < 0.2 seconds limit
        
        res = validate_audio_file(wav_path)
        self.assertFalse(res["valid"])
        self.assertIn("too short", res["error"])

    def test_03_corrupt_wav_fails(self):
        wav_path = os.path.join(self.temp_assets_dir, "test_corrupt.wav")
        with open(wav_path, "wb") as f:
            f.write(b"WAVCORRUPTHEADER"*20)
            
        res = validate_audio_file(wav_path, "wav")
        self.assertFalse(res["valid"])
        self.assertIn("Failed to parse WAV headers", res["error"])

    def test_04_valid_mp3_passes(self):
        mp3_path = os.path.join(self.temp_assets_dir, "test_valid.mp3")
        self._create_valid_mp3(mp3_path)
        
        res = validate_audio_file(mp3_path, "mp3")
        self.assertTrue(res["valid"])
        self.assertEqual(res["format"], "mp3")
        self.assertTrue(res["duration_unknown"])

    def test_05_id3_only_mp3_fails(self):
        mp3_path = os.path.join(self.temp_assets_dir, "test_id3_only.mp3")
        id3_header = b'ID3\x03\x00\x00\x00\x00\x00\n' + b'x'*150
        with open(mp3_path, "wb") as f:
            f.write(id3_header)
            
        res = validate_audio_file(mp3_path, "mp3")
        self.assertFalse(res["valid"])
        self.assertIn("No valid MPEG frame sync", res["error"])

    def test_06_corrupt_mp3_fails(self):
        mp3_path = os.path.join(self.temp_assets_dir, "test_corrupt.mp3")
        with open(mp3_path, "wb") as f:
            f.write(b"NOTANMP3FILE"*20)
            
        res = validate_audio_file(mp3_path, "mp3")
        self.assertFalse(res["valid"])
        self.assertIn("No valid MPEG frame sync", res["error"])

    def test_07_empty_file_fails(self):
        empty_path = os.path.join(self.temp_assets_dir, "test_empty.wav")
        with open(empty_path, "wb") as f:
            pass
            
        res = validate_audio_file(empty_path)
        self.assertFalse(res["valid"])
        self.assertIn("too small", res["error"])

    def test_08_safe_delete_invalid_file(self):
        # 1. Safe path inside temp assets dir
        path_inside = os.path.join(self.temp_assets_dir, "inside.wav")
        with open(path_inside, "wb") as f:
            f.write(b"some content")
        self.assertTrue(os.path.exists(path_inside))
        safe_delete_invalid_file(path_inside)
        self.assertFalse(os.path.exists(path_inside))

        # 2. Prevent delete outside assets dir
        temp_fd, outside_path = tempfile.mkstemp()
        os.close(temp_fd)
        try:
            self.assertTrue(os.path.exists(outside_path))
            safe_delete_invalid_file(outside_path)
            self.assertTrue(os.path.exists(outside_path))  # safety block prevents delete
        finally:
            if os.path.exists(outside_path):
                os.remove(outside_path)

    def test_09_failed_validation_keeps_approved_state(self):
        os.environ["ALLOW_SIMULATED_TTS_DEV_ONLY"] = "false"
        capsule = create_capsule_from_script(
            approval_queue_id=101,
            script_text="Wait a second...",
            capsule_type="morning_update",
            source="manual"
        )
        cap_id = capsule["id"]
        
        # Approve capsule
        from services.broadcast.capsule_service import approve_capsule
        approve_capsule(cap_id, approved_by="owner")
        
        # Inject corrupted generator write
        def mock_render(text, path):
            with open(path, "wb") as f:
                f.write(b"CORRUPT")
            return {"success": True, "model": "gemini-3.1"}
            
        with patch("services.voice.gen_service._render_gemini_tts", side_effect=mock_render):
            with patch("services.voice.gen_service._has_real_api_key", return_value=True):
                res = generate_capsule_audio(cap_id, regenerate=True)
                self.assertFalse(res["success"])
                
                # Check DB status
                updated = get_capsule_by_id(cap_id)
                self.assertEqual(updated["status"], "approved") # keeps approved!
                self.assertEqual(updated["audio_status"], "failed")
                self.assertIn("validation failed", updated["error_message"])

    def test_10_real_tts_validated_sets_status_correctly(self):
        capsule = create_capsule_from_script(
            approval_queue_id=102,
            script_text="This is a real TTS preview test script.",
            capsule_type="morning_update",
            source="manual"
        )
        cap_id = capsule["id"]
        
        from services.broadcast.capsule_service import approve_capsule
        approve_capsule(cap_id, approved_by="owner")
        
        # Mock successful Real TTS write
        def mock_render(text, path):
            self._create_valid_wav(path, duration=0.8)
            return {"success": True, "model": "gemini-2.5", "voice_name": "Kore"}
            
        with patch("services.voice.gen_service._render_gemini_tts", side_effect=mock_render):
            with patch("services.voice.gen_service._has_real_api_key", return_value=True):
                res = generate_capsule_audio(cap_id, regenerate=True)
                self.assertTrue(res["success"])
                
                updated = get_capsule_by_id(cap_id)
                self.assertEqual(updated["status"], "audio_ready_preview")
                self.assertEqual(updated["audio_status"], "real_tts_ready")
                self.assertEqual(updated["audio_truth_level"], "real")
                self.assertEqual(updated["broadcast_ready"], 0) # false
                self.assertEqual(updated["azuracast_status"], "blocked_requires_owner_approval")

    def test_11_simulated_sets_status_correctly(self):
        capsule = create_capsule_from_script(
            approval_queue_id=103,
            script_text="This is a simulated preview test script.",
            capsule_type="morning_update",
            source="manual"
        )
        cap_id = capsule["id"]
        
        from services.broadcast.capsule_service import approve_capsule
        approve_capsule(cap_id, approved_by="owner")
        
        # Force simulate by disabling real provider keys
        with patch("services.voice.gen_service._has_real_api_key", return_value=False):
            res = generate_capsule_audio(cap_id, regenerate=True)
            self.assertTrue(res["success"])
            
            updated = get_capsule_by_id(cap_id)
            self.assertEqual(updated["status"], "audio_ready_preview")
            self.assertEqual(updated["audio_status"], "simulated_preview")
            self.assertEqual(updated["audio_truth_level"], "simulated")
            self.assertEqual(updated["broadcast_ready"], 0) # false
            self.assertEqual(updated["production_asset"], 0) # false
            self.assertEqual(updated["azuracast_status"], "blocked_requires_owner_approval")

    def test_12_azuracast_remains_blocked(self):
        # Even if capsule is in audio_ready_preview state, any upload to AzuraCast returns blocked status
        capsule = create_capsule_from_script(
            approval_queue_id=104,
            script_text="Safe test script.",
            capsule_type="morning_update",
            source="manual"
        )
        cap_id = capsule["id"]
        
        # Try to send
        res = send_capsule_to_azuracast(cap_id)
        self.assertFalse(res["success"])
        self.assertEqual(res["azuracast_status"], "blocked")

    def test_13_audio_serving_endpoint(self):
        # Import TestClient
        from fastapi.testclient import TestClient
        from main import app
        
        client = TestClient(app)
        
        # Test capsule mock audio path setup
        capsule = create_capsule_from_script(
            approval_queue_id=105,
            script_text="Verify serving path...",
            capsule_type="morning_update",
            source="manual"
        )
        cap_id = capsule["id"]
        
        audio_file = os.path.join(self.temp_assets_dir, f"capsule_{cap_id}.wav")
        self._create_valid_wav(audio_file)
        
        # Update path in DB
        update_capsule_audio_status(105, audio_file, "real")
        
        # 1. Unauthorized request when ADMIN_AUTH_ENABLED=true
        with patch.dict(os.environ, {"ADMIN_AUTH_ENABLED": "true", "ADMIN_API_KEY": "secret"}):
            # Unauthorized GET (no headers)
            res = client.get(f"/api/neena/capsules/{cap_id}/audio")
            self.assertEqual(res.status_code, 401)
            
            # Authorized GET
            res = client.get(f"/api/neena/capsules/{cap_id}/audio", headers={"Authorization": "Bearer secret"})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers["content-type"], "audio/wav")

        # 2. Directory traversal attempt
        traversal_path = os.path.abspath(os.path.join(self.temp_assets_dir, "..", "outside.wav"))
        with open(traversal_path, "wb") as f:
            f.write(b"outside contents")
            
        try:
            update_capsule_audio_status(105, traversal_path, "real")
            with patch.dict(os.environ, {"ADMIN_AUTH_ENABLED": "true", "ADMIN_API_KEY": "secret"}):
                res = client.get(f"/api/neena/capsules/{cap_id}/audio", headers={"Authorization": "Bearer secret"})
                self.assertEqual(res.status_code, 403)
                self.assertIn("Access denied", res.json()["detail"])
        finally:
            if os.path.exists(traversal_path):
                os.remove(traversal_path)

if __name__ == "__main__":
    unittest.main()
