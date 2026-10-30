"""Pipeline stages after the script exists: tts → align → resolve → render."""
from __future__ import annotations

import json
import logging
import time

from . import cache
from .align import align
from .project import Project, write_json
from .render import render_video
from .resolve import resolve_scene
from .schemas import TimedWord, Timeline, TimelineScene
from .tts import get_provider

log = logging.getLogger("n2v")


def stage_tts(p: Project) -> None:
    spec = p.load_spec()
    provider = None
    try:
        for scene in p.selected(spec):
            d = p.scene_dir(scene.id)
            wav, meta = d / "audio.wav", d / "tts.json"
            ident = get_provider(p.cfg).cache_identity() if provider is None else provider.cache_identity()
            key = cache.content_hash(scene.narration, scene.pronounce, ident)
            if cache.is_fresh(meta, key) and wav.exists():
                log.info("tts  %s  cached", scene.id)
                continue
            provider = provider or get_provider(p.cfg)
            t0 = time.time()
            res = provider.synthesize(scene.narration, wav, scene.pronounce)
            write_json(meta, {"duration_s": res.duration_s, "words": [w.model_dump() for w in res.words]})
            cache.mark(meta, key)
            log.info("tts  %s  %.1fs audio in %.1fs", scene.id, res.duration_s, time.time() - t0)
    finally:
        if provider:
            provider.release()  # free model memory before the next stage


def stage_align(p: Project) -> None:
    spec = p.load_spec()
    prov, model = p.cfg.get_path("align.provider"), p.cfg.get_path("align.whisper_model")
    for scene in p.selected(spec):
        d = p.scene_dir(scene.id)
        meta, out = d / "tts.json", d / "words.json"
        key = cache.content_hash(meta, prov, model, "onset-v1")
        if cache.is_fresh(out, key):
            log.info("align %s  cached", scene.id)
            continue
        native = [TimedWord(**w) for w in json.loads(meta.read_text())["words"]]
        words = align(d / "audio.wav", native, prov, model)
        write_json(out, [w.model_dump() for w in words])
        cache.mark(out, key)
        log.info("align %s  %d words (%s)", scene.id, len(words), prov)


def stage_resolve(p: Project) -> None:
    """Always runs (it is fast). Writes timeline.json for all scenes."""
    spec = p.load_spec()
    cfg = p.cfg
    fps = cfg.get_path("video.fps")
    sync = cfg.get_path("sync")
    scenes: list[TimelineScene] = []
    for scene in spec.scenes:
        d = p.scene_dir(scene.id)
        audio_s = json.loads((d / "tts.json").read_text())["duration_s"]
        timed = [TimedWord(**w) for w in json.loads((d / "words.json").read_text())]
        beats, words, frames, warns = resolve_scene(
            scene, timed, audio_s, fps, sync["lead_ms"], sync["pad_start_ms"], sync["pad_end_ms"],
            sync.get("max_hold_ms", 10000))
        for w in warns:
            log.warning(w)
        scenes.append(TimelineScene(
            id=scene.id, template=scene.template, section_label=scene.section_label, subtitle=scene.subtitle,
            title=scene.title, content=scene.content, beats=beats, duration_frames=frames,
            audio_offset_frames=round(sync["pad_start_ms"] / 1000 * fps), audio_file=str(d / "audio.wav"), words=words,
        ))
        log.info("resolve %s  %d/%d beats, %.1fs", scene.id, len(beats), len(scene.beats), frames / fps)
    tl = Timeline(title=spec.title, fps=fps, width=cfg.get_path("video.width"), height=cfg.get_path("video.height"), scenes=scenes)
    p.timeline_path.write_text(tl.model_dump_json(indent=2))


def stage_render(p: Project) -> None:
    out = render_video(p)
    log.info("video  %s", out)
