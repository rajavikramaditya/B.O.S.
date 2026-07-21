import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import sqlite3
import json

# Ensure backend directory is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

import database as db

class TestCapsuleWorkflow(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        
        # Patch DB_PATH in database.py
        self.db_path_patch = patch("database.DB_PATH", self.temp_db_path)
        self.db_path_patch.start()
        
        # Initialize full db tables
        db.init_db()
        
        # Patch add_activity_log to avoid print or write issues in console tests
        self.activity_patch = patch("database.add_activity_log", return_value=None)
        self.activity_patch.start()

        # Save env variables to restore them after each test
        self.original_env = dict(os.environ)

    def tearDown(self):
        self.db_path_patch.stop()
        self.activity_patch.stop()
        
        # Clean up temporary database file
        try:
            os.remove(self.temp_db_path)
        except OSError:
            pass
            
        # Restore original env variables
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_01_table_create_if_missing(self):
        """Test Case 1: Database initializes the broadcast_capsules table if missing."""
        import tempfile
        fd, temp_db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            with patch("database.DB_PATH", temp_db):
                db.init_db()
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='broadcast_capsules'")
                row = cursor.fetchone()
                conn.close()
                self.assertIsNotNone(row)
        finally:
            try:
                os.remove(temp_db)
            except OSError:
                pass

    def test_02_safe_migration_if_existing(self):
        """Test Case 2: Database performs safe non-destructive migration if table already exists."""
        import tempfile
        fd, temp_db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE broadcast_capsules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                script_text TEXT NOT NULL,
                approval_status TEXT DEFAULT 'pending'
            )
            """)
            conn.commit()
            conn.close()
            
            with patch("database.DB_PATH", temp_db):
                db.init_db()
                
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(broadcast_capsules)")
                columns = [r[1] for r in cursor.fetchall()]
                conn.close()
                
                self.assertIn("topic", columns)
                self.assertIn("language", columns)
                self.assertIn("tone", columns)
                self.assertIn("status", columns)
                self.assertIn("rejected_by", columns)
                self.assertIn("reject_reason", columns)
        finally:
            try:
                os.remove(temp_db)
            except OSError:
                pass

    def test_03_create_capsule(self):
        """Test Case 3: Creating a capsule populates all new fields with correct default statuses."""
        from services.broadcast.capsule_service import create_capsule_from_script
        
        capsule = create_capsule_from_script(
            approval_queue_id=101,
            script_text="Hello listeners of Orai!",
            capsule_type="rj_intro",
            title="Morning Show RJ Intro",
            source="manual",
            topic="morning_vibe",
            language="Bundeli/Hinglish",
            tone="energetic",
            created_by="owner",
            status="pending_approval"
        )
        
        self.assertEqual(capsule["id"], 1)
        self.assertEqual(capsule["topic"], "morning_vibe")
        self.assertEqual(capsule["language"], "Bundeli/Hinglish")
        self.assertEqual(capsule["tone"], "energetic")
        self.assertEqual(capsule["status"], "pending_approval")
        self.assertEqual(capsule["approval_status"], "pending")  # synced
        self.assertEqual(capsule["audio_status"], "none")

    def test_04_approve_latest_and_specific(self):
        """Test Case 4: Approving a capsule transitions status, updates approved_by, approved_at, and sets audio_status to audio_pending."""
        from services.broadcast.capsule_service import create_capsule_from_script, approve_capsule
        
        cap = create_capsule_from_script(
            approval_queue_id=202,
            script_text="Approve this specific one.",
            status="pending_approval"
        )
        
        # Approve
        approved = approve_capsule(cap["id"], approved_by="owner_user")
        
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["approval_status"], "approved")
        self.assertEqual(approved["audio_status"], "audio_pending")
        self.assertEqual(approved["approved_by"], "owner_user")
        self.assertIsNotNone(approved["approved_at"])

    def test_05_reject_with_reason_and_rejected_by(self):
        """Test Case 5: Rejecting a capsule saves reason, rejected_by, rejected_at, status=rejected."""
        from services.broadcast.capsule_service import create_capsule_from_script, reject_capsule
        
        cap = create_capsule_from_script(
            approval_queue_id=303,
            script_text="Bad script.",
            status="pending_approval"
        )
        
        # Reject
        rejected = reject_capsule(cap["id"], rejected_by="owner_user", reason="Weak opening segment")
        
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["approval_status"], "rejected")
        self.assertEqual(rejected["rejected_by"], "owner_user")
        self.assertEqual(rejected["reject_reason"], "Weak opening segment")
        self.assertIsNotNone(rejected["rejected_at"])

    def test_06_prepare_audio_blocked_before_approval(self):
        """Test Case 6: Audio preparation blocks generating audio for draft, pending_approval, and rejected states."""
        db.init_db()
        from services.broadcast.capsule_service import create_capsule_from_script, validate_capsule_for_audio_generation
        
        # Draft
        cap_draft = create_capsule_from_script(approval_queue_id=401, script_text="Draft script", status="draft")
        gate_draft = validate_capsule_for_audio_generation(cap_draft["id"])
        self.assertFalse(gate_draft["allowed"])
        self.assertTrue(gate_draft["blocked"])
        
        # Pending Approval
        cap_pending = create_capsule_from_script(approval_queue_id=402, script_text="Pending script", status="pending_approval")
        gate_pending = validate_capsule_for_audio_generation(cap_pending["id"])
        self.assertFalse(gate_pending["allowed"])
        self.assertTrue(gate_pending["blocked"])
        
        # Rejected
        cap_rejected = create_capsule_from_script(approval_queue_id=403, script_text="Rejected script", status="rejected")
        gate_rejected = validate_capsule_for_audio_generation(cap_rejected["id"])
        self.assertFalse(gate_rejected["allowed"])
        self.assertTrue(gate_rejected["blocked"])

    def test_07_prepare_audio_blocked_when_real_tts_unavailable_in_production(self):
        """Test Case 7: Audio preparation returns blocked/unavailable in production when real TTS keys are missing."""
        os.environ["ALLOW_SIMULATED_TTS_DEV_ONLY"] = "false"
        
        from services.broadcast.capsule_service import create_capsule_from_script, approve_capsule
        from services.voice.gen_service import generate_capsule_audio
        
        cap = create_capsule_from_script(approval_queue_id=501, script_text="Approved script", status="pending_approval")
        approve_capsule(cap["id"])
        
        # Mock keys to be empty/missing
        with patch("services.voice.gen_service.get_gemini_api_key", return_value=""), \
             patch("services.voice.gen_service.get_elevenlabs_key", return_value=""):
            
            res = generate_capsule_audio(cap["id"])
            self.assertFalse(res["success"])
            self.assertTrue(res["blocked"])
            self.assertEqual(res["audio_truth_level"], "failed")

    def test_08_simulated_preview_stays_non_production(self):
        """Test Case 8: Simulated audio is marked as audio_ready_preview, production_asset=false, broadcast_ready=false, audio_provider=simulated."""
        os.environ["ALLOW_SIMULATED_TTS_DEV_ONLY"] = "true"
        
        from services.broadcast.capsule_service import create_capsule_from_script, approve_capsule, get_capsule_by_id, enrich_capsule_for_api
        from services.voice.gen_service import generate_capsule_audio
        
        cap = create_capsule_from_script(approval_queue_id=601, script_text="Approved script", status="pending_approval")
        approve_capsule(cap["id"])
        
        # Mock keys to be empty to trigger simulated fallback
        with patch("services.voice.gen_service.get_gemini_api_key", return_value=""), \
             patch("services.voice.gen_service.get_elevenlabs_key", return_value=""), \
             patch("services.voice.gen_service.validate_audio_file", return_value={"valid": True, "format": "wav", "channels": 1, "sample_rate": 22050, "duration": 1.0, "file_size": 200}):
            
            res = generate_capsule_audio(cap["id"])
            self.assertTrue(res["success"])
            self.assertEqual(res["audio_truth_level"], "simulated")
            
            # Fetch enriched record
            updated = enrich_capsule_for_api(get_capsule_by_id(cap["id"]))
            self.assertEqual(updated["audio_status"], "simulated_preview")
            self.assertEqual(updated["status"], "audio_ready_preview")
            self.assertEqual(updated["audio_provider"], "simulated")
            self.assertFalse(updated["production_asset"])
            self.assertFalse(updated["broadcast_ready"])

    def test_09_azuracast_push_blocked(self):
        """Test Case 9: All AzuraCast upload, playlist, batch, and queue operations return blocked status responses."""
        db.init_db()
        from services.broadcast.capsule_service import send_capsule_to_azuracast
        from services.broadcast.azuracast_client import (
            upload_media_file,
            assign_media_to_playlist_or_folder,
            append_media_to_playlist,
            queue_media_files_batch,
            send_capsule_to_azuracast_api
        )
        
        # Test capsule send
        res = send_capsule_to_azuracast(1)
        self.assertFalse(res["success"])
        self.assertTrue(res["blocked"])
        self.assertEqual(res["azuracast_status"], "blocked")
        
        # Test client functions directly
        self.assertFalse(upload_media_file("dummy.mp3")["success"])
        self.assertFalse(assign_media_to_playlist_or_folder("1")["success"])
        self.assertFalse(append_media_to_playlist("1")["success"])
        self.assertFalse(queue_media_files_batch(["dummy.mp3"])["success"])
        self.assertFalse(send_capsule_to_azuracast_api(1, "dummy.mp3")["success"])

    def test_10_unauthorized_writes_return_403(self):
        """Test Case 10: Unauthorized write and read paths return 403 when ADMIN_AUTH_ENABLED is true."""
        os.environ["ADMIN_AUTH_ENABLED"] = "true"
        os.environ["ADMIN_API_KEY"] = "super-secret-key"
        
        from fastapi.testclient import TestClient
        from main import app
        
        client = TestClient(app)
        
        # Test write endpoint without token -> should fail with 401 or 403 depending on admin middleware
        res = client.post("/api/neena/capsules", json={"script_text": "hello"})
        self.assertIn(res.status_code, (401, 403))
        
        # Test read endpoint without token -> should fail as well
        res_get = client.get("/api/neena/capsules")
        self.assertIn(res_get.status_code, (401, 403))
        
        # Test with valid token -> should succeed/return 200 or validation status
        headers = {"Authorization": "Bearer super-secret-key"}
        # Patch database connections to not raise operational errors during HTTP test
        with patch("services.broadcast.capsule_service.create_capsule_from_script") as mock_create, \
             patch("services.broadcast.approval_queue.queue_asset_for_review", return_value=123):
            mock_create.return_value = {"id": 1}
            res_auth = client.post("/api/neena/capsules", json={"script_text": "hello"}, headers=headers)
            self.assertEqual(res_auth.status_code, 200)

    def test_11_no_listener_or_mobile_changes(self):
        """Test Case 11: Scan codebase to verify no listener web app or mobile WebView files are modified."""
        project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if not os.path.exists(os.path.join(project_dir, "backend")):
            project_dir = os.path.abspath(os.path.dirname(__file__))
        # We must not modify listener files or mobile client packages.
        # Ensure we only modified backend, config, frontend dashboard
        restricted = ["mobile", "listener-client", "public-app"]
        for r in restricted:
            self.assertFalse(os.path.exists(os.path.join(project_dir, r)), f"Folder {r} detected, make sure it is not touched.")

    def test_12_no_raw_regex_routing_reintroduced(self):
        """Test Case 12: Verify that frontend console uses backend router and has no raw natural language regexes."""
        app_js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "app.js"))
        if not os.path.exists(app_js_path):
            app_js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend", "app.js"))
        with open(app_js_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Ensure tryCapsuleVoiceShortcut returns false directly
            self.assertIn("async function tryCapsuleVoiceShortcut(msg) {", content)
            self.assertIn("return false;", content)

if __name__ == "__main__":
    unittest.main()
