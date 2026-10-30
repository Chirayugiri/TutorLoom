"""TTS provider interface. Providers return audio plus word timings when they have them."""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from ..schemas import TimedWord


@dataclass
class TTSResult:
    wav_path: Path
    duration_s: float
    words: list[TimedWord] = field(default_factory=list)  # empty if the provider has no timestamps

    @property
    def has_timestamps(self) -> bool:
        return bool(self.words)


class TTSProvider(ABC):
    name: str = "base"

    @abstractmethod
    def synthesize(self, text: str, out_wav: Path, pronounce: dict[str, str]) -> TTSResult: ...

    def cache_identity(self) -> dict:
        """Settings that change the audio; part of the TTS cache key."""
        return {"provider": self.name}

    def release(self) -> None:
        """Free model memory between stages."""


def apply_pronounce(text: str, pronounce: dict[str, str]) -> str:
    """Replace whole-word occurrences of tricky terms with their spoken respelling.

    Word timings are mapped back to the original narration words in `resolve`, so the
    respelling never leaks into anchors or captions.
    """
    for term in sorted(pronounce, key=len, reverse=True):
        text = re.sub(rf"(?<![\w-]){re.escape(term)}(?![\w-])", pronounce[term], text)
    return text
