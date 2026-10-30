from __future__ import annotations

from ..config import Config
from .base import TTSProvider, TTSResult


def get_provider(cfg: Config) -> TTSProvider:
    name = cfg.get_path("tts.provider")
    if name == "kokoro":
        from .kokoro_provider import KokoroProvider

        return KokoroProvider(**cfg.get_path("tts.kokoro", {}))
    if name == "elevenlabs":
        from .elevenlabs_provider import ElevenLabsProvider

        return ElevenLabsProvider(**cfg.get_path("tts.elevenlabs", {}), ffmpeg=str(cfg.path("paths.ffmpeg")))
    raise ValueError(f"unknown tts.provider '{name}'")


__all__ = ["TTSProvider", "TTSResult", "get_provider"]
