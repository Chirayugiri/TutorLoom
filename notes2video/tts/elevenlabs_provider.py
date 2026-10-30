"""ElevenLabs via the /with-timestamps endpoint (character alignment folded into words)."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.request
from pathlib import Path

from ..schemas import TimedWord
from .base import TTSProvider, TTSResult, apply_pronounce


class ElevenLabsProvider(TTSProvider):
    name = "elevenlabs"

    def __init__(self, voice_id: str, model_id: str, api_key_env: str, ffmpeg: str):
        self.voice_id, self.model_id, self.ffmpeg = voice_id, model_id, ffmpeg
        self.api_key = os.environ.get(api_key_env, "")

    def cache_identity(self) -> dict:
        return {"provider": self.name, "voice": self.voice_id, "model": self.model_id}

    def synthesize(self, text: str, out_wav: Path, pronounce: dict[str, str]) -> TTSResult:
        if not self.api_key or not self.voice_id:
            raise RuntimeError("ElevenLabs needs tts.elevenlabs.voice_id and an API key in the environment")
        body = json.dumps({"text": apply_pronounce(text, pronounce), "model_id": self.model_id}).encode()
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/with-timestamps",
            data=body, headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        mp3 = out_wav.with_suffix(".mp3")
        mp3.write_bytes(base64.b64decode(data["audio_base64"]))
        subprocess.run([self.ffmpeg, "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "24000", "-ac", "1", str(out_wav)], check=True)
        al = data["alignment"]
        words, cur, start, end = [], "", 0.0, 0.0
        for ch, s, e in zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]):
            if ch.isspace():
                if cur:
                    words.append(TimedWord(text=cur, start=start, end=end))
                cur = ""
                continue
            if not cur:
                start = s
            cur, end = cur + ch, e
        if cur:
            words.append(TimedWord(text=cur, start=start, end=end))
        import soundfile as sf

        return TTSResult(wav_path=out_wav, duration_s=sf.info(out_wav).duration, words=words)
