"""Kokoro-82M (local). Word timestamps come straight from Kokoro's duration predictor."""
from __future__ import annotations

import gc
import logging
import re
import warnings
from pathlib import Path

import numpy as np
import soundfile as sf

from ..schemas import TimedWord
from .base import TTSProvider, TTSResult, apply_pronounce

log = logging.getLogger(__name__)
SR = 24000
_WORDLIKE = re.compile(r"[\w]")


class KokoroProvider(TTSProvider):
    name = "kokoro"

    def __init__(self, voice: str = "am_michael", speed: float = 1.0, lang_code: str = "a"):
        self.voice, self.speed, self.lang_code = voice, speed, lang_code
        self._pipe = None

    def cache_identity(self) -> dict:
        return {"provider": self.name, "voice": self.voice, "speed": self.speed, "lang": self.lang_code}

    def _pipeline(self):
        if self._pipe is None:
            warnings.filterwarnings("ignore")
            from kokoro import KPipeline

            log.info("loading Kokoro (first load takes ~40 s on CPU)")
            self._pipe = KPipeline(lang_code=self.lang_code, repo_id="hexgrad/Kokoro-82M")
        return self._pipe

    def synthesize(self, text: str, out_wav: Path, pronounce: dict[str, str]) -> TTSResult:
        spoken = apply_pronounce(text, pronounce)
        chunks: list[np.ndarray] = []
        words: list[TimedWord] = []
        offset = 0.0
        for res in self._pipeline()(spoken, voice=self.voice, speed=self.speed):
            audio = res.audio.numpy() if hasattr(res.audio, "numpy") else np.asarray(res.audio)
            for tk in res.tokens or []:
                if tk.start_ts is None or tk.end_ts is None or not _WORDLIKE.search(tk.text):
                    continue
                words.append(TimedWord(text=tk.text, start=offset + tk.start_ts, end=offset + tk.end_ts))
            chunks.append(audio)
            offset += len(audio) / SR
        audio = np.concatenate(chunks) if chunks else np.zeros(SR // 2, dtype=np.float32)
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        sf.write(out_wav, audio, SR, subtype="PCM_16")
        return TTSResult(wav_path=out_wav, duration_s=len(audio) / SR, words=words)

    def release(self) -> None:
        self._pipe = None
        gc.collect()
