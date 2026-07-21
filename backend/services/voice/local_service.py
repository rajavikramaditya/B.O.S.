"""M2 Local Identity Voice Service using Piper TTS with bilingual female voice model."""
from __future__ import annotations

import os
import logging
import urllib.request
import wave
from typing import Optional

logger = logging.getLogger(__name__)

_VOICE_INSTANCE = None
_VOICE_MODEL_NAME = "hi_IN-priyamvada-medium"

# Local directories setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_VOICES_DIR = os.path.join(BASE_DIR, "playout", "local_voices")
os.makedirs(LOCAL_VOICES_DIR, exist_ok=True)

MODEL_PATH = os.path.join(LOCAL_VOICES_DIR, f"{_VOICE_MODEL_NAME}.onnx")
CONFIG_PATH = os.path.join(LOCAL_VOICES_DIR, f"{_VOICE_MODEL_NAME}.onnx.json")

MODEL_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/priyamvada/medium/{_VOICE_MODEL_NAME}.onnx"
CONFIG_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/priyamvada/medium/{_VOICE_MODEL_NAME}.onnx.json"


def ensure_model_files() -> None:
    """Download ONNX voice models if not present locally."""
    if not os.path.exists(MODEL_PATH):
        logger.info("[LOCAL_VOICE] Downloading Piper voice model: %s", MODEL_URL)
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    if not os.path.exists(CONFIG_PATH):
        logger.info("[LOCAL_VOICE] Downloading Piper voice config: %s", CONFIG_URL)
        urllib.request.urlretrieve(CONFIG_URL, CONFIG_PATH)


def get_local_voice() -> Optional[object]:
    """Retrieve or initialize the cached local voice instance."""
    global _VOICE_INSTANCE
    if _VOICE_INSTANCE is not None:
        return _VOICE_INSTANCE

    ensure_model_files()

    try:
        from piper.voice import PiperVoice
        logger.info("[LOCAL_VOICE] Loading voice model: %s", MODEL_PATH)
        _VOICE_INSTANCE = PiperVoice.load(MODEL_PATH, config_path=CONFIG_PATH)
        return _VOICE_INSTANCE
    except Exception as e:
        logger.error("[LOCAL_VOICE] Failed to load Piper engine: %s", e)
        return None


def synthesize_local_speech(text: str, output_path: str) -> bool:
    """Synthesize text to speech using local Piper engine and save as WAV."""
    voice = get_local_voice()
    if not voice:
        logger.error("[LOCAL_VOICE] Local voice engine not available.")
        return False

    try:
        # Create WAV output
        with wave.open(output_path, "wb") as wav_file:
            initialized = False
            for chunk in voice.synthesize(text):
                if not initialized:
                    wav_file.setnchannels(chunk.sample_channels)
                    wav_file.setsampwidth(chunk.sample_width)
                    wav_file.setframerate(chunk.sample_rate)
                    initialized = True
                wav_file.writeframes(chunk.audio_int16_bytes)
        logger.info("[LOCAL_VOICE] Successfully synthesized speech to %s", output_path)
        return True
    except Exception as e:
        logger.error("[LOCAL_VOICE] Synthesis error: %s", e)
        return False
