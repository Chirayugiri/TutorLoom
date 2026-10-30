from notes2video.resolve import find_anchor, map_words, narration_words, resolve_scene
from notes2video.schemas import Scene, TimedWord


def _timed(words, step=0.5):
    return [TimedWord(text=w, start=i * step, end=i * step + 0.4) for i, w in enumerate(words)]


def test_exact_anchor_prefers_after_cursor():
    words = "the dot moves and then the dot stops".split()
    assert find_anchor("the dot", words)[:2] == (0, 1)
    assert find_anchor("the dot", words, after=2)[:2] == (5, 6)


def test_fuzzy_anchor_fixes_small_typos_and_rejects_garbage():
    words = narration_words("Negative inputs become zero, positive inputs pass through.")
    first, last, how = find_anchor("negative input becomes zero", words)
    assert (first, last) == (0, 3) and how.startswith("fuzzy")
    assert find_anchor("completely unrelated phrase", words) is None


def test_map_words_handles_respelled_terms():
    narr = narration_words("And ReLU is simple.")
    timed = _timed(["And", "ray", "loo", "is", "simple"])
    mapped = map_words(narr, timed)
    assert [w.text for w in mapped] == narr
    assert mapped[1].start == timed[1].start and mapped[1].end == timed[2].end
    assert mapped[2].start == timed[3].start


def _scene(beats):
    return Scene(
        id="s01", template="compare_cards", title="t",
        narration="The step function is old. The sigmoid is smooth. Watch the dot move.",
        content={"cards": [{"name": "step", "fn": "step"}, {"name": "sigmoid", "fn": "sigmoid"}]},
        beats=beats,
    )


def test_resolve_frames_channels_and_dropped_beats():
    scene = _scene([
        {"anchor": "The step function", "action": "highlight", "target": "card:step"},
        {"anchor": "The sigmoid", "action": "highlight", "target": "card:sigmoid"},
        {"anchor": "Watch the dot", "action": "move_dot", "target": "dot:sigmoid", "duration_ms": 1000},
        {"anchor": "nowhere to be found at all", "action": "highlight", "target": "card:step"},
        {"anchor": "The step", "action": "highlight", "target": "card:bogus"},
    ])
    timed = _timed(narration_words(scene.narration))
    beats, words, frames, warns = resolve_scene(scene, timed, audio_s=7.0, fps=30, lead_ms=100, pad_start_ms=500, pad_end_ms=500)
    assert len(beats) == 3 and len(warns) == 2
    step, sig, dot = beats
    # "The" is word 0 at t=0 → 0.5 s pad − 0.1 s lead = 0.4 s = frame 12
    assert step.start_frame == 12
    # same channel → step's focus ends exactly when sigmoid's starts
    assert step.end_frame == sig.start_frame
    # dot is its own channel → holds to scene end
    assert dot.end_frame == frames == 240
    assert words[0].start == 0.5
