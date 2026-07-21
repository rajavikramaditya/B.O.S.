"""Unit tests for Neena Local Identity Voice M2."""
from __future__ import annotations

import os
import sys
import unittest
import wave

# Ensure backend path is in sys.path
_WORKSPACE = r"c:\Projects\radio station\radio-ai-manager\backend"
if os.path.isdir(_WORKSPACE):
    sys.path.insert(0, _WORKSPACE)


class TestLocalVoiceM2(unittest.TestCase):
    """M2 Local Voice test suite."""

    def test_ensure_model_downloads_and_loads(self):
        """M2.1: Model files exist or get downloaded, and Piper voice instance loads."""
        from services.voice.local_service import get_local_voice, MODEL_PATH, CONFIG_PATH
        
        voice = get_local_voice()
        self.assertIsNotNone(voice, "Local Piper voice engine could not be initialized.")
        self.assertTrue(os.path.exists(MODEL_PATH), "ONNX model file is missing.")
        self.assertTrue(os.path.exists(CONFIG_PATH), "Model JSON config file is missing.")

    def test_synthesize_local_speech_creates_valid_wav(self):
        """M2.2: Local synthesis generates a valid WAV file with correct headers."""
        from services.voice.local_service import synthesize_local_speech
        
        test_wav = os.path.join(os.path.dirname(__file__), "test_temp_output.wav")
        if os.path.exists(test_wav):
            os.unlink(test_wav)

        try:
            success = synthesize_local_speech("Namaste, main Neena hoon.", test_wav)
            self.assertTrue(success, "Speech synthesis failed.")
            self.assertTrue(os.path.exists(test_wav), "Synthesized WAV file was not created.")
            self.assertTrue(os.path.getsize(test_wav) > 1024, "Generated audio file is too small.")

            # Validate WAV format headers
            with wave.open(test_wav, "rb") as w:
                self.assertEqual(w.getnchannels(), 1, "Expected mono audio channel.")
                self.assertEqual(w.getsampwidth(), 2, "Expected 16-bit sample width (2 bytes).")
                self.assertEqual(w.getframerate(), 22050, "Expected 22050Hz sample rate.")
        finally:
            if os.path.exists(test_wav):
                os.unlink(test_wav)

    def test_enqueue_cockpit_voice_routes_locally(self):
        """M2.3: enqueue_cockpit_voice runs local synthesis and returns audio_url immediately."""
        from services.voice.cockpit_voice import enqueue_cockpit_voice
        
        phrase = "Namaste sir, aap kaise hain?"
        res = enqueue_cockpit_voice(phrase, purpose="owner_cockpit")
        
        self.assertTrue(res.get("ok"), "Voice enqueue failed.")
        self.assertEqual(res.get("mode"), "cached", "Expected cached/instant delivery mode.")
        self.assertEqual(res.get("status"), "succeeded")
        self.assertIsNotNone(res.get("audio_url"), "Audio URL is missing.")
        self.assertTrue(res.get("audio_url").startswith("/api/neena/cockpit-voice/audio/cv_"), "Invalid audio URL pattern.")

        # Test deduplication/caching on second request
        res2 = enqueue_cockpit_voice(phrase, purpose="owner_cockpit")
        self.assertTrue(res2.get("ok"))
        self.assertEqual(res2.get("mode"), "cached")
        self.assertEqual(res2.get("audio_url"), res.get("audio_url"), "Cached audio URL does not match.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
