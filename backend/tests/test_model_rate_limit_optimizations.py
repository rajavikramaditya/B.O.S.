"""Unit tests for model rate limit and token optimizations (bypassing embedding recall and intent classification)."""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from unittest.mock import MagicMock, patch

class TestModelOptimizations(unittest.TestCase):
    @patch("services.memory.facade.recall")
    @patch("services.brain.command_interpreter.interpret_owner_command")
    @patch("services.brain.conversation.generate_conversational_reply")
    def test_casual_greeting_bypasses_embedding_and_interpreter(self, mock_conversation, mock_interpret, mock_recall):
        from services.brain.brain import process_owner_message

        mock_conversation.return_value = "Hello Sir, kaise hain aap?"

        # 1. When owner says "hello" (a casual greeting)
        res = process_owner_message("hello", channel="command_center")

        # It must NOT call memory facade recall (bypasses embedding recall)
        mock_recall.assert_not_called()
        # It must NOT call command interpreter model
        mock_interpret.assert_not_called()
        # It must call the conversation model to reply
        mock_conversation.assert_called_once()
        self.assertEqual(res["reply"], "Hello Sir, kaise hain aap?")

    @patch("services.memory.facade.recall")
    def test_confirmation_bypasses_embedding_recall(self, mock_recall):
        from services.brain.brain import _process_owner_message_inner

        # Factual packet dummy
        with patch("services.brain.brain._handle_pre_intent_guards") as mock_guard:
            mock_guard.return_value = {
                "reply": "Confirm kiya gaya",
                "command_triggered": None,
                "require_confirmation": False,
                "action_type": "confirm",
            }
            
            _process_owner_message_inner("haan")
            # Since "haan" is a simple confirmation, we bypass memory recall
            mock_recall.assert_not_called()
