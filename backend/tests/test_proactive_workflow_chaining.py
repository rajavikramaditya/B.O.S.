"""Unit tests for proactive workflow chaining (approve -> generate_audio -> send_azuracast -> assign_capsule_to_playlist)."""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from unittest.mock import MagicMock, patch

class TestProactiveChaining(unittest.TestCase):
    @patch("services.brain.manager_state.set_pending_action")
    def test_approve_script_proactive_chaining(self, mock_set_pending):
        from services.brain.brain import _save_and_return

        # Factual packet represents a successful script approval
        factual_packet = {
            "tool": "approve_capsule",
            "status": "ok",
            "capsule_id": 50,
            "approval_id": 12,
        }

        res = _save_and_return(
            message="approve script",
            reply="Capsule approved.",
            require_confirmation=False,
            factual_packet=factual_packet,
        )

        # It must append the prompt
        self.assertIn("Kya main ab iska audio generate karoon? (Haan/Nahi)", res["reply"])
        # It must call set_pending_action with generate_audio
        mock_set_pending.assert_called_once()
        kwargs = mock_set_pending.call_args.kwargs
        self.assertEqual(kwargs.get("action_type"), "generate_audio")
        self.assertEqual(kwargs.get("payload", {}).get("capsule_id"), 50)

    @patch("services.brain.manager_state.set_pending_action")
    def test_generate_audio_proactive_chaining(self, mock_set_pending):
        from services.brain.brain import _save_and_return

        factual_packet = {
            "tool": "generate_audio",
            "status": "ok",
            "capsule_id": 50,
        }

        res = _save_and_return(
            message="generate audio",
            reply="Audio prepared.",
            require_confirmation=False,
            factual_packet=factual_packet,
        )

        self.assertIn("Kya main ise AzuraCast par upload karoon? (Haan/Nahi)", res["reply"])
        mock_set_pending.assert_called_once()
        kwargs = mock_set_pending.call_args.kwargs
        self.assertEqual(kwargs.get("action_type"), "send_azuracast")
        self.assertEqual(kwargs.get("payload", {}).get("capsule_id"), 50)

    @patch("services.brain.manager_state.set_pending_action")
    def test_send_azuracast_proactive_chaining(self, mock_set_pending):
        from services.brain.brain import _save_and_return

        factual_packet = {
            "tool": "send_azuracast",
            "status": "ok",
            "capsule_id": 50,
        }

        res = _save_and_return(
            message="upload script",
            reply="Capsule uploaded.",
            require_confirmation=False,
            factual_packet=factual_packet,
        )

        self.assertIn("Kya main ise schedule playlist par lagaoon? (Haan/Nahi)", res["reply"])
        mock_set_pending.assert_called_once()
        kwargs = mock_set_pending.call_args.kwargs
        self.assertEqual(kwargs.get("action_type"), "assign_capsule_to_playlist")
        self.assertEqual(kwargs.get("payload", {}).get("capsule_id"), 50)

    @patch("services.tools.live_ops_executor.try_execute_live_ops")
    @patch("services.brain.manager_state.get_pending_action")
    @patch("services.brain.manager_state.clear_pending_action")
    def test_one_tap_affirmation_proactive_chain(self, mock_clear, mock_get_pending, mock_try_execute):
        # Mock pending action generate_audio is currently armed
        mock_get_pending.return_value = {
            "action_type": "generate_audio",
            "category": "live_ops",
            "protected": True,
            "status": "pending_owner_confirmation",
            "payload": {
                "resume_action": "generate_audio",
                "resume_slots": {"capsule_id": 50},
                "capsule_id": 50,
            }
        }
        mock_try_execute.return_value = {
            "reply": "Audio generated.",
            "action_type": "GENERATE_AUDIO",
            "factual_packet": {
                "tool": "generate_audio",
                "status": "ok",
                "capsule_id": 50,
            }
        }

        from services.brain.brain import process_owner_message

        # User says "haan" to execute the pending generate_audio action
        res = process_owner_message("haan", channel="command_center")

        # It must execute the live ops tool
        mock_try_execute.assert_called_once_with("generate_audio", {"capsule_id": 50, "explicit_push": True, "explicit_approval": True}, owner_message="confirm karo")
        # It must clear the pending action
        mock_clear.assert_called_once()
        # Since it succeeded, it should also proactive-chain next step (send_azuracast)
        self.assertIn("Kya main ise AzuraCast par upload karoon? (Haan/Nahi)", res["reply"])
