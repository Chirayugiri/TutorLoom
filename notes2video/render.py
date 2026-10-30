"""Render scenes with Remotion (silent), build one sample-exact audio track, concat, normalise, mux."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from . import cache
from .config import ROOT
from .project import Project, write_json
from .schemas import Timeline

log = logging.getLogger("n2v")
VIDEO_DIR = ROOT / "video"


def _run(cmd: list[str], cwd: Path | None = None, quiet: bool = False) -> None:
    log.debug("$ %s", " ".join(cmd))
    res = subprocess.run(cmd, cwd=cwd, text=True, capture_output=quiet)
    if res.returncode != 0:
        raise RuntimeError(f"command failed ({res.returncode}): {' '.join(cmd[:4])} …\n{(res.stderr or '')[-2000:]}")


def ensure_bundle(cfg) -> Path:
    """Bundle the Remotion project once; rebuilt only when TSX/CSS/package files change."""
    key = cache.content_hash(cache.tree_hash(VIDEO_DIR / "src", (".ts", ".tsx", ".css", ".json")),
                             VIDEO_DIR / "package.json", VIDEO_DIR / "remotion.config.ts")
    out = cfg.path("paths.build_dir") / "_bundle"
    marker = out / "index.html"
    if cache.is_fresh(marker, key):
        return out
    log.info("bundling Remotion project")
    if out.exists():
        shutil.rmtree(out)
    _run(["npx", "remotion", "bundle", "src/index.ts", "--out-dir", str(out), "--log", "error"], cwd=VIDEO_DIR, quiet=True)
    cache.mark(marker, key)
    return out


def scene_audio(tl: Timeline, sr: int = 24000) -> np.ndarray:
    """One continuous track: each scene's narration placed at its offset inside an exact-length slot."""
    parts = []
    for s in tl.scenes:
        n = round(s.duration_frames / tl.fps * sr)
        slot = np.zeros(n, dtype=np.float32)
        audio, file_sr = sf.read(s.audio_file, dtype="float32")
        assert file_sr == sr, f"{s.audio_file}: expected {sr} Hz"
        off = round(s.audio_offset_frames / tl.fps * sr)
        audio = audio[: max(0, n - off)]
        slot[off: off + len(audio)] = audio
        parts.append(slot)
    return np.concatenate(parts)


def write_srt(tl: Timeline, path: Path, max_words: int = 9) -> None:
    def ts(t: float) -> str:
        ms = round(t * 1000)
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"

    lines, idx, offset = [], 1, 0.0
    for s in tl.scenes:
        chunk: list = []
        for i, w in enumerate(s.words):
            chunk.append(w)
            ends_sentence = w.text[-1:] in ".?!"
            if len(chunk) >= max_words or ends_sentence or i == len(s.words) - 1:
                lines += [str(idx), f"{ts(offset + chunk[0].start)} --> {ts(offset + chunk[-1].end)}",
                          " ".join(x.text for x in chunk), ""]
                idx += 1
                chunk = []
        offset += s.duration_frames / tl.fps
    path.write_text("\n".join(lines))


def render_video(p: Project) -> Path:
    cfg = p.cfg
    tl = p.load_timeline()
    ffmpeg = str(cfg.path("paths.ffmpeg"))
    bundle = ensure_bundle(cfg)
    bundle_key = (bundle / "index.html.key").read_text()
    durations = [s.duration_frames for s in tl.scenes]
    vcfg = cfg.get_path("video")

    clips = []
    for i, s in enumerate(tl.scenes):
        d = p.scene_dir(s.id)
        props = {"scene": s.model_dump(), "theme": cfg["theme"], "progress": {"durations": durations, "index": i}}
        props["scene"].pop("words")
        clip = d / "render.mp4"
        clips.append(clip)
        key = cache.content_hash(props, bundle_key, VIDEO_DIR / "scripts" / "prepare.mjs", vcfg)
        if cache.is_fresh(clip, key):
            log.info("render %s  cached", s.id)
            continue
        if p.only_scene and p.only_scene != s.id:
            if clip.exists():
                log.warning("render %s  stale but skipped (--only-scene %s)", s.id, p.only_scene)
                continue
        props_file = d / "props.json"
        write_json(props_file, props)
        _run(["node", "scripts/prepare.mjs", str(props_file)], cwd=VIDEO_DIR)
        log.info("render %s  %d frames …", s.id, s.duration_frames)
        _run(["npx", "remotion", "render", str(bundle), "Scene", str(clip), f"--props={props_file}",
              f"--concurrency={vcfg['concurrency']}", "--codec=h264", f"--crf={vcfg['crf']}",
              "--pixel-format=yuv420p", "--muted", "--log=info"], cwd=VIDEO_DIR)
        cache.mark(clip, key)

    work = p.work
    full_wav = work / "narration.wav"
    sf.write(full_wav, scene_audio(tl), 24000, subtype="PCM_16")
    concat_list = work / "concat.txt"
    concat_list.write_text("".join(f"file '{c}'\n" for c in clips))
    silent = work / "video_silent.mp4"
    _run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(silent)])
    out = work / f"{p.name}.mp4"
    _run([ffmpeg, "-y", "-loglevel", "error", "-i", str(silent), "-i", str(full_wav),
          "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
          "-map", "0:v:0", "-map", "1:a:0", "-movflags", "+faststart", str(out)])
    if vcfg.get("captions"):
        write_srt(tl, out.with_suffix(".srt"))
    return out


def render_stills(p: Project, scene_id: str, frames: list[int]) -> list[Path]:
    """Render individual frames of one scene to PNG (fast visual check)."""
    cfg = p.cfg
    tl = p.load_timeline()
    bundle = ensure_bundle(cfg)
    idx = next(i for i, s in enumerate(tl.scenes) if s.id == scene_id)
    s = tl.scenes[idx]
    d = p.scene_dir(s.id)
    props = {"scene": s.model_dump(), "theme": cfg["theme"],
             "progress": {"durations": [x.duration_frames for x in tl.scenes], "index": idx}}
    props["scene"].pop("words")
    props_file = d / "props_still.json"
    write_json(props_file, props)
    _run(["node", "scripts/prepare.mjs", str(props_file)], cwd=VIDEO_DIR)
    outs = []
    for f in frames:
        out = d / "stills" / f"f{f:05d}.png"
        out.parent.mkdir(exist_ok=True)
        _run(["npx", "remotion", "still", str(bundle), "Scene", str(out), f"--props={props_file}", f"--frame={f}",
              "--log=error"], cwd=VIDEO_DIR, quiet=True)
        outs.append(out)
    return outs
