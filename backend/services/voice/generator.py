"""
Legacy voice module — prefer services.voice.gen_service for all TTS.

synthesize_script_to_speech() is deprecated; active path is voice_gen_service.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Re-export for existing imports (neena_brain, etc.)
from services.voice.gen_service import get_elevenlabs_key  # noqa: F401


def synthesize_script_to_speech(script_text: str, filename_prefix: str = "neena_script") -> str:
    """DEPRECATED — use voice_gen_service.generate_capsule_audio or render_approved_script."""
    logger.warning("synthesize_script_to_speech is deprecated; use voice_gen_service")
    from services.voice.gen_service import render_script_audio

    result = render_script_audio(
        script_id=0,
        text=script_text,
        filename_stem=filename_prefix,
        link_capsule=False,
    )
    return result.get("audio_file_path") or ""
