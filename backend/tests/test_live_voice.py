"""Unit tests for Neena Live Voice WebSocket endpoint."""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import json
import base64
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from main import app

class TestLiveVoiceWebSocket(unittest.TestCase):
    @patch("services.brain.live_voice.load_recent_turns_context")
    @patch("services.llm.provider_router.get_gemini_api_key")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_live_voice_websocket_flow(self, mock_ws_connect, mock_get_api_key, mock_load_context):
        mock_get_api_key.return_value = "mock_api_key"
        mock_load_context.return_value = []

        # Setup mock Google WebSocket
        mock_google_ws = AsyncMock()
        mock_ws_connect.return_value.__aenter__.return_value = mock_google_ws

        # Mock messages returned by Google Live API to our backend
        # Note: We must simulate Google sending text/json messages first, and then closing
        import aiohttp
        msg = MagicMock()
        msg.type = aiohttp.WSMsgType.TEXT
        msg.data = json.dumps({
            "serverContent": {
                "modelTurn": {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "audio/pcm;rate=24000",
                                "data": base64.b64encode(b"dummy_pcm_response").decode("utf-8")
                            }
                        }
                    ]
                }
            }
        })
        google_messages = [msg]
        
        async def mock_aiter(*args, **kwargs):
            for m in google_messages:
                yield m

        mock_google_ws.__aiter__ = mock_aiter

        client = TestClient(app)
        
        # Test connecting to FastAPI WebSocket endpoint
        with client.websocket_connect("/api/neena/live-voice") as websocket:
            # Send dummy mic raw bytes (PCM) from browser client
            websocket.send_bytes(b"dummy_pcm_mic_data")
            
            # Receive binary PCM chunks forwarded by backend
            resp_data = websocket.receive_bytes()
            self.assertEqual(resp_data, b"dummy_pcm_response")

        # Verify backend initialized connection with Bidi setup message
        mock_google_ws.send_json.assert_any_call({
            "setup": {
                "model": "models/gemini-2.5-flash-native-audio-latest",
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": "Kore"
                            }
                        }
                    }
                },
                "systemInstruction": {
                    "parts": [
                        {
                            "text": "You are Neena Gupta, the AI assistant of Orai Radio. Keep your responses short, conversational, and directly in Hindi. Speak immediately without explaining your thinking or using preambles."
                        }
                    ]
                }
            }
        })

        # Verify clientContent greeting turn was sent
        mock_google_ws.send_json.assert_any_call({
            "clientContent": {
                "turns": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": "Hello Neena! Greet the owner right now in Hindi by saying exactly: 'Sir, ab main live hoon. Batayein kya karna hai?'"
                            }
                        ]
                    }
                ],
                "turnComplete": True
            }
        })
