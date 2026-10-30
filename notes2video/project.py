"""Project workspace: where every stage reads and writes its files."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .schemas import Timeline, VideoSpec


@dataclass
class Project:
    cfg: Config
    name: str
    only_scene: str | None = None

    @property
    def work(self) -> Path:
        p = self.cfg.path("paths.build_dir") / self.name
        p.mkdir(parents=True, exist_ok=True)
        return p

    def scene_dir(self, scene_id: str) -> Path:
        p = self.work / "scenes" / scene_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def spec_path(self) -> Path:
        return self.work / "spec.json"

    @property
    def timeline_path(self) -> Path:
        return self.work / "timeline.json"

    def load_spec(self) -> VideoSpec:
        if not self.spec_path.exists():
            raise FileNotFoundError(f"{self.spec_path} missing — run the earlier stages first")
        return VideoSpec.model_validate_json(self.spec_path.read_text())

    def save_spec(self, spec: VideoSpec) -> None:
        self.spec_path.write_text(spec.model_dump_json(indent=2))

    def load_timeline(self) -> Timeline:
        return Timeline.model_validate_json(self.timeline_path.read_text())

    def selected(self, spec: VideoSpec):
        return [s for s in spec.scenes if self.only_scene in (None, s.id)]


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
