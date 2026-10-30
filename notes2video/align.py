"""Word-level alignment. 'native' uses TTS timestamps; 'faster_whisper' transcribes the audio."""
from __future__ import annotations

import gc
import logging
from pathlib import Path

from .schemas import TimedWord

log = logging.getLogger(__name__)


def whisper_words(wav: Path, model_name: str = "base.en") -> list[TimedWord]:
    from faster_whisper import WhisperModel

    import numpy as np
    import soundfile as sf

    # Decode ourselves (faster-whisper's PyAV path breaks on some PyAV versions) and resample to 16 kHz.
    audio, sr = sf.read(wav, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != 16000:
        t_out = np.arange(0, len(audio) / sr, 1 / 16000)
        audio = np.interp(t_out, np.arange(len(audio)) / sr, audio).astype(np.float32)
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    try:
        segments, _ = model.transcribe(audio, word_timestamps=True, beam_size=1, vad_filter=False)
        return [
            TimedWord(text=w.word.strip(), start=w.start, end=w.end)
            for seg in segments for w in (seg.words or []) if w.word.strip()
        ]
    finally:
        del model
        gc.collect()


def align(wav: Path, native_words: list[TimedWord], provider: str, whisper_model: str) -> list[TimedWord]:
    if provider == "native" and native_words:
        words = native_words
    else:
        if provider == "native":
            log.warning("TTS returned no timestamps; falling back to faster-whisper")
        words = whisper_words(wav, whisper_model)
    return snap_to_onsets(wav, words)


def snap_to_onsets(wav: Path, words: list[TimedWord], silence: float = 0.004, win_s: float = 0.01,
                   max_shift_s: float = 0.35) -> list[TimedWord]:
    """Move word starts that fall inside a pause forward to where the voice actually begins.

    TTS duration models (and Whisper) tend to place a word's start somewhere in the preceding pause.
    Only words whose timestamp sits in silence are touched; mid-phrase words are left alone.
    """
    import numpy as np
    import soundfile as sf

    audio, sr = sf.read(wav, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    hop = int(win_s * sr)
    rms = np.sqrt(np.convolve(audio ** 2, np.ones(hop) / hop, mode="same"))[::hop]
    out = []
    for w in words:
        i = int(w.start / win_s)
        start = w.start
        if i < len(rms) and rms[i] < silence:
            limit = min(len(rms), i + int(max_shift_s / win_s))
            j = next((k for k in range(i, limit) if rms[k] >= silence), None)
            if j is not None:
                start = min(j * win_s, w.end - 0.03)
        out.append(TimedWord(text=w.text, start=start, end=w.end))
    return out


def onset_after_pause(wav: Path, t: float, min_pause_s: float = 0.12, silence: float = 0.004) -> float | None:
    """Ground-truth onset near t if the word follows a clear pause, else None (used by check-sync)."""
    import numpy as np
    import soundfile as sf

    audio, sr = sf.read(wav, dtype="float32")
    hop = int(0.01 * sr)
    rms = np.sqrt(np.convolve(audio ** 2, np.ones(hop) / hop, mode="same"))[::hop]
    lo, hi = max(0, int((t - 0.4) / 0.01)), min(len(rms), int((t + 0.4) / 0.01))
    for k in range(lo, hi):
        pause = rms[max(0, k - int(min_pause_s / 0.01)):k]
        if rms[k] >= silence and len(pause) and pause.max() < silence:
            return k * 0.01
    return None
