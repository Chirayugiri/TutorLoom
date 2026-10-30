"""Turn anchor phrases into frame ranges using word timestamps.

Steps: (1) map timed words (TTS/Whisper) onto the narration's own words, (2) locate each beat's
anchor in the narration (exact, then fuzzy), (3) convert to frames with a small lead, (4) decide
how long each focus effect holds (until the next focus in the same channel).
"""
from __future__ import annotations

import logging
import math
import re
from difflib import SequenceMatcher

from rapidfuzz import fuzz

from .schemas import PERSISTENT_ACTIONS, ResolvedBeat, Scene, TimedWord, valid_targets

log = logging.getLogger(__name__)
FUZZY_MIN_SCORE = 82


def norm(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", word.lower())


def narration_words(narration: str) -> list[str]:
    return [w for w in narration.split() if norm(w)]


def map_words(narr: list[str], timed: list[TimedWord]) -> list[TimedWord]:
    """Give every narration word a time, using the timed words wherever they line up."""
    a, b = [norm(w) for w in narr], [norm(t.text) for t in timed]
    out: list[TimedWord | None] = [None] * len(narr)
    for tag, i1, i2, j1, j2 in SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                t = timed[j1 + k]
                out[i1 + k] = TimedWord(text=narr[i1 + k], start=t.start, end=t.end)
        elif tag == "replace":
            # e.g. "ReLU" spoken as "ray loo": spread the timed span over the narration words by length.
            s, e = timed[j1].start, timed[j2 - 1].end
            lens = [max(len(a[i]), 1) for i in range(i1, i2)]
            total, acc = sum(lens), 0
            for k, i in enumerate(range(i1, i2)):
                ws = s + (e - s) * acc / total
                acc += lens[k]
                out[i] = TimedWord(text=narr[i], start=ws, end=s + (e - s) * acc / total)
    # Words the TTS skipped entirely: interpolate between neighbours.
    for i, w in enumerate(out):
        if w is None:
            prev_end = next((out[k].end for k in range(i - 1, -1, -1) if out[k]), 0.0)
            next_start = next((out[k].start for k in range(i + 1, len(out)) if out[k]), prev_end)
            out[i] = TimedWord(text=narr[i], start=prev_end, end=max(prev_end, next_start))
    return out  # type: ignore[return-value]


def find_anchor(anchor: str, words: list[str], after: int = 0) -> tuple[int, int, str] | None:
    """Return (first_word_idx, last_word_idx, how) for an anchor phrase, preferring matches at/after `after`."""
    target = [norm(w) for w in anchor.split() if norm(w)]
    if not target:
        return None
    normed = [norm(w) for w in words]
    n = len(target)
    exact = [i for i in range(len(normed) - n + 1) if normed[i:i + n] == target]
    if exact:
        i = next((i for i in exact if i >= after), exact[0])
        return i, i + n - 1, "exact"
    joined = " ".join(target)
    best: tuple[float, int, int] | None = None
    for size in {max(1, n - 1), n, n + 1}:
        for i in range(len(normed) - size + 1):
            score = fuzz.ratio(joined, " ".join(normed[i:i + size]))
            if i < after:
                score -= 3  # mild preference for keeping beats in narration order
            if best is None or score > best[0]:
                best = (score, i, i + size - 1)
    if best and best[0] >= FUZZY_MIN_SCORE:
        return best[1], best[2], f"fuzzy({best[0]:.0f})"
    return None


def channel(template: str, target: str) -> str:
    """Focus effects in the same channel replace each other; different channels can coexist."""
    kind = target.split(":", 1)[0]
    if template == "code":
        return {"line": "code", "token": "code", "output": "output", "bar": "chart", "series": "chart"}.get(kind, kind)
    if template == "compare_cards":
        return "dot" if kind == "dot" else "cards"
    return "main"


def interrupts(template: str, cur: str, nxt: str) -> bool:
    """Does a later focus beat on `nxt` end the focus on `cur`?"""
    cc, nc = channel(template, cur), channel(template, nxt)
    if template == "code":
        # Code focus gives way to anything; output and chart can be discussed together.
        return cc == nc or "code" in (cc, nc)
    if template == "compare_cards" and cc == "dot":
        # A moving dot belongs to its card: it goes when another dot moves or another card takes focus.
        return nc == "dot" or nxt.split(":", 1)[1] != cur.split(":", 1)[1]
    return cc == nc


def resolve_scene(scene: Scene, timed: list[TimedWord], audio_s: float, fps: int,
                  lead_ms: int, pad_start_ms: int, pad_end_ms: int,
                  max_hold_ms: int = 10000) -> tuple[list[ResolvedBeat], list[TimedWord], int, list[str]]:
    """Returns (beats, narration words with times relative to scene start, duration_frames, warnings)."""
    warnings: list[str] = []
    narr = narration_words(scene.narration)
    words = map_words(narr, timed)
    pad = pad_start_ms / 1000
    duration = math.ceil((pad + audio_s + pad_end_ms / 1000) * fps)
    targets = valid_targets(scene.template, scene.content)

    raw: list[tuple[int, int, ResolvedBeat]] = []
    cursor = 0
    for i, b in enumerate(scene.beats):
        if b.target not in targets:
            warnings.append(f"{scene.id} beat {i}: dropped, invalid target '{b.target}'")
            continue
        hit = find_anchor(b.anchor, narr, after=cursor)
        if hit is None:
            warnings.append(f"{scene.id} beat {i}: dropped, anchor not found: '{b.anchor}'")
            continue
        first, last, how = hit
        if how != "exact":
            warnings.append(f"{scene.id} beat {i}: anchor '{b.anchor}' fixed {how} -> '{' '.join(narr[first:last + 1])}'")
        cursor = first
        start = max(0, round((pad + words[first].start - lead_ms / 1000) * fps))
        rb = ResolvedBeat(action=b.action, target=b.target, anchor=" ".join(narr[first:last + 1]),
                          start_frame=start, end_frame=duration,
                          in_frames=max(3, round(b.duration_ms / 1000 * fps)), params=b.params)
        raw.append((start, i, rb))

    raw.sort(key=lambda x: (x[0], x[1]))
    beats = [rb for _, _, rb in raw]
    for k, rb in enumerate(beats):
        if rb.action in PERSISTENT_ACTIONS:
            continue
        nxt = next((o.start_frame for o in beats[k + 1:]
                    if o.action not in PERSISTENT_ACTIONS and o.start_frame > rb.start_frame
                    and interrupts(scene.template, rb.target, o.target)), None)
        if nxt is not None:
            rb.end_frame = nxt
        if rb.action == "move_dot":
            rb.end_frame = max(rb.end_frame, min(duration, rb.start_frame + rb.in_frames))
        else:
            hold = int(rb.params.get("hold_ms", max_hold_ms))
            rb.end_frame = min(rb.end_frame, rb.start_frame + round(hold / 1000 * fps))

    scene_words = [TimedWord(text=w.text, start=w.start + pad, end=w.end + pad) for w in words]
    return beats, scene_words, duration, warnings
