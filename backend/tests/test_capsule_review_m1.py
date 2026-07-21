"""Unit tests for Neena Capsule Review Manager M1."""
from __future__ import annotations

import os
import sys
import sqlite3
import unittest
from unittest.mock import patch, MagicMock

# Ensure backend path is in sys.path
_WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _WORKSPACE not in sys.path:
    sys.path.insert(0, _WORKSPACE)


class ConnectionWrapper:
    def __init__(self, conn):
        self.__dict__['_conn'] = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __setattr__(self, name, value):
        setattr(self._conn, name, value)

    def close(self):
        pass


class TestCapsuleReviewM1(unittest.TestCase):
    """M1 Capsule Review Manager test suite."""

    def setUp(self):
        # Create in-memory DB and set up table schema
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE broadcast_capsules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                approval_queue_id INTEGER UNIQUE,
                capsule_type TEXT NOT NULL DEFAULT 'unknown',
                title TEXT,
                topic TEXT,
                script_text TEXT NOT NULL,
                language TEXT,
                tone TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                source TEXT NOT NULL DEFAULT 'unknown',
                audio_file_path TEXT,
                audio_path TEXT,
                audio_truth_level TEXT NOT NULL DEFAULT 'none',
                audio_status TEXT NOT NULL DEFAULT 'none',
                audio_provider TEXT,
                approval_status TEXT NOT NULL DEFAULT 'pending',
                azuracast_status TEXT NOT NULL DEFAULT 'not_sent',
                azuracast_playlist_id TEXT,
                azuracast_media_id TEXT,
                stream_verification_status TEXT NOT NULL DEFAULT 'unknown',
                truth_level TEXT NOT NULL DEFAULT 'local_only',
                owner_notes TEXT,
                safety_notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                approved_at DATETIME,
                approved_by TEXT,
                rejected_at DATETIME,
                rejected_by TEXT,
                reject_reason TEXT,
                error_message TEXT,
                metadata_json TEXT,
                audio_metadata_json TEXT,
                broadcast_ready INTEGER DEFAULT 0,
                production_asset INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

        # Patch database connection helpers using ConnectionWrapper
        self.wrapper = ConnectionWrapper(self.conn)
        self.db_patcher = patch("database.get_db_connection", return_value=self.wrapper)
        self.db_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()
        self.conn.close()

    def test_list_recent_capsules(self):
        """M1.1: list_recent_capsules works safely and returns expected count."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO broadcast_capsules (script_text, status, approval_status, broadcast_ready)
            VALUES ('Test script 1', 'pending_approval', 'pending', 0)
        """)
        self.conn.commit()

        from services.broadcast.capsule_review import list_recent_capsules_review
        res = list_recent_capsules_review(limit=5)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["script_text"], "Test script 1")

    def test_get_capsule_review_summary(self):
        """M1.2: get_capsule_review_summary shows correct summary and broadcast_ready=False."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO broadcast_capsules (script_text, status, approval_status, broadcast_ready, azuracast_status)
            VALUES ('Test script 2', 'pending_approval', 'pending', 0, 'blocked')
        """)
        self.conn.commit()

        from services.broadcast.capsule_review import get_capsule_review_summary
        summary = get_capsule_review_summary()
        self.assertIsNotNone(summary)
        self.assertEqual(summary["script_text"], "Test script 2")
        self.assertFalse(summary["broadcast_ready"])
        self.assertEqual(summary["azuracast_status"], "blocked")

    def test_mark_capsule_script_approved(self):
        """M1.3: mark_capsule_script_approved updates status without setting broadcast_ready."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO broadcast_capsules (script_text, status, approval_status, broadcast_ready)
            VALUES ('Test script 3', 'pending_approval', 'pending', 0)
        """)
        self.conn.commit()

        from services.broadcast.capsule_review import mark_capsule_script_approved
        res = mark_capsule_script_approved(1)
        self.assertEqual(res["status"], "approved")
        self.assertEqual(res["approval_status"], "approved")
        self.assertEqual(res["broadcast_ready"], 0)

    def test_mark_capsule_script_rejected(self):
        """M1.4: mark_capsule_script_rejected updates status and reason without setting broadcast_ready."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO broadcast_capsules (script_text, status, approval_status, broadcast_ready)
            VALUES ('Test script 4', 'pending_approval', 'pending', 0)
        """)
        self.conn.commit()

        from services.broadcast.capsule_review import mark_capsule_script_rejected
        res = mark_capsule_script_rejected(1, "Incorrect fact mentioned")
        self.assertEqual(res["status"], "rejected")
        self.assertEqual(res["approval_status"], "rejected")
        self.assertEqual(res["reject_reason"], "Incorrect fact mentioned")
        self.assertEqual(res["broadcast_ready"], 0)

    def test_mark_capsule_needs_revision(self):
        """M1.5: mark_capsule_needs_revision updates status to needs_revision without setting broadcast_ready."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO broadcast_capsules (script_text, status, approval_status, broadcast_ready)
            VALUES ('Test script 5', 'pending_approval', 'pending', 0)
        """)
        self.conn.commit()

        from services.broadcast.capsule_review import mark_capsule_needs_revision
        res = mark_capsule_needs_revision(1, "Change tone to friendly")
        self.assertEqual(res["status"], "needs_revision")
        self.assertEqual(res["approval_status"], "needs_revision")
        self.assertEqual(res["reject_reason"], "Change tone to friendly")
        self.assertEqual(res["broadcast_ready"], 0)

    @patch("services.brain.command_interpreter._call_interpreter_model")
    @patch("services.brain.command_interpreter._interpreter_model_chain")
    @patch("services.brain.command_interpreter.pr.get_gemini_api_key")
    def test_routing_review_commands_via_interpreter(self, mock_key, mock_chain, mock_call):
        """AGENTS hygiene: capsule review actions come from interpreter LLM, not string gates."""
        mock_key.return_value = "fake-key"
        mock_chain.return_value = ["gemini-1.5-flash"]
        from services.brain.command_interpreter import interpret_owner_command

        cases = [
            ("script approve karo", "approve_capsule", {}),
            ("script reject karo", "reject_capsule", {"reject_reason": "Rejected by owner"}),
            ("revision chahiye", "needs_revision", {"reason": "Revision requested by owner"}),
            ("latest capsule dikhao", "open_latest_capsule", {}),
            ("last 5 capsules dikhao", "list_pending_capsules", {"limit": 5}),
        ]
        for msg, action, slots in cases:
            mock_call.return_value = (
                {"action": action, "confidence": 0.95, "slots": slots},
                "mock",
                "available",
            )
            pkt, provider, status, _ = interpret_owner_command(msg)
            self.assertEqual(pkt["action"], action, msg)
            self.assertEqual(provider, "mock")
            self.assertEqual(status, "available")
            self.assertNotEqual(provider, "local")

    @patch("services.brain.command_interpreter._call_interpreter_model")
    @patch("services.brain.command_interpreter._interpreter_model_chain")
    @patch("services.brain.command_interpreter.pr.get_gemini_api_key")
    def test_protected_broadcast_commands_still_blocked(self, mock_key, mock_chain, mock_call):
        """M1.7: Protected broadcast commands are reclassified to send_azuracast."""
        mock_key.return_value = "fake-key"
        mock_chain.return_value = ["gemini-1.5-flash"]
        mock_call.return_value = ({"action": "generate_audio", "confidence": 0.9, "slots": {}}, "mock", "available")
        
        from services.brain.command_interpreter import interpret_owner_command
        pkt, _, _, _ = interpret_owner_command("broadcast now")
        self.assertEqual(pkt["action"], "send_azuracast")


if __name__ == "__main__":
    unittest.main(verbosity=2)
