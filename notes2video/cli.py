"""CLI: one subcommand per stage, plus build-spec (hand-written spec → video)."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, Optional

import typer

from .config import load_config
from .content import materialize
from .project import Project
from .schemas import VideoSpec
from .stages import stage_align, stage_render, stage_resolve, stage_tts

app = typer.Typer(add_completion=False, help="Study notes → animated explainer video")
log = logging.getLogger("n2v")

POST_SCRIPT_STAGES: list[tuple[str, Callable[[Project], None]]] = [
    ("tts", stage_tts), ("align", stage_align), ("resolve", stage_resolve), ("render", stage_render),
]


def _setup(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
                        datefmt="%H:%M:%S")


def run_stages(p: Project, stages, from_stage: str | None = None) -> None:
    names = [n for n, _ in stages]
    start = names.index(from_stage) if from_stage else 0
    for name, fn in stages[start:]:
        t0 = time.time()
        log.info("── %s", name)
        fn(p)
        log.info("── %s done in %.1fs", name, time.time() - t0)


ProjectOpt = typer.Option(..., "--project", "-p", help="project name (folder under build/)")
SceneOpt = typer.Option(None, "--only-scene", help="limit work to one scene id")


@app.command("build-spec")
def build_spec(spec_file: Path, project: Optional[str] = typer.Option(None, "--project", "-p"),
               from_stage: Optional[str] = typer.Option(None, "--from-stage"), only_scene: Optional[str] = SceneOpt,
               verbose: bool = False):
    """Render a hand-written scene spec (skips ingest/outline/scene_script)."""
    _setup(verbose)
    p = Project(load_config(), project or spec_file.stem, only_scene)
    spec = VideoSpec.model_validate_json(spec_file.read_text())
    for scene in spec.scenes:
        for w in materialize(scene, p.scene_dir(scene.id) / "figures"):
            log.warning(w)
    p.save_spec(spec)
    run_stages(p, POST_SCRIPT_STAGES, from_stage)


def _stage_cmd(name: str, fn: Callable[[Project], None]):
    def cmd(project: str = ProjectOpt, only_scene: Optional[str] = SceneOpt, verbose: bool = False):
        _setup(verbose)
        fn(Project(load_config(), project, only_scene))
    cmd.__doc__ = f"Run the {name} stage."
    app.command(name)(cmd)


for _name, _fn in POST_SCRIPT_STAGES:
    _stage_cmd(_name, _fn)


if __name__ == "__main__":
    app()


@app.command("check-sync")
def check_sync(project: str = ProjectOpt, model: str = "small.en", verbose: bool = False):
    """Measure beat timing against an independent faster-whisper transcription of the audio."""
    from .align import onset_after_pause, whisper_words
    from .resolve import find_anchor, map_words, narration_words

    _setup(verbose)
    p = Project(load_config(), project)
    tl, spec = p.load_timeline(), {s.id: s for s in p.load_spec().scenes}
    fps, lead = tl.fps, p.cfg.get_path("sync.lead_ms") / 1000
    errors = []
    for s in tl.scenes:
        narr = narration_words(spec[s.id].narration)
        heard = map_words(narr, whisper_words(Path(s.audio_file), model))
        pad = s.audio_offset_frames / fps
        cursor = 0
        for b in s.beats:
            first = find_anchor(b.anchor, narr, after=cursor)[0]
            cursor = first
            beat_t = b.start_frame / fps + lead          # where the word was scheduled (lead removed)
            after_pause = first == 0 or narr[first - 1][-1] in ".,:;?!"
            onset = onset_after_pause(Path(s.audio_file), heard[first].start) if after_pause else None
            heard_t = pad + (onset if onset is not None else heard[first].start)  # true onset after a pause, else whisper
            src = "onset" if onset is not None else "whisper"
            err = (beat_t - heard_t) * 1000
            errors.append(abs(err))
            typer.echo(f"{s.id}  {b.target:<16} '{b.anchor[:34]:<34}'  scheduled {beat_t:6.2f}s  heard {heard_t:6.2f}s ({src:<7})  "
                       f"error {err:+5.0f} ms  (visual leads by {lead * 1000 - err:+.0f} ms)")
    if errors:
        typer.echo(f"\n{len(errors)} beats: mean |error| {sum(errors) / len(errors):.0f} ms, max {max(errors):.0f} ms "
                   f"(whisper word starts are themselves ±~50–100 ms)")


@app.command()
def preview(project: str = ProjectOpt, scene: str = typer.Option(..., "--scene"),
            frames: str = typer.Option("60", help="comma-separated frame numbers"), verbose: bool = False):
    """Render still PNGs of chosen frames of one scene."""
    from .render import render_stills

    _setup(verbose)
    for out in render_stills(Project(load_config(), project), scene, [int(f) for f in frames.split(",")]):
        typer.echo(out)
