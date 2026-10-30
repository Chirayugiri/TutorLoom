"""Scene spec schema (mirrored in video/src/types.ts) and per-template target rules."""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Template = Literal[
    "title", "bullets", "equation", "code", "chart_bars",
    "figure_callout", "compare_cards", "diagram", "image_filter_demo",
]
Action = Literal["highlight", "reveal", "circle", "box", "zoom", "dim_others", "draw", "move_dot"]

# Actions whose effect persists to the end of the scene once triggered.
PERSISTENT_ACTIONS = {"reveal", "draw"}
# Built-in plot functions for compare_cards (computed in TypeScript, never by the LLM).
PLOT_FUNCTIONS = {"step", "sigmoid", "tanh", "relu", "leaky_relu", "gelu", "softplus", "identity"}


class Beat(BaseModel):
    anchor: str = Field(min_length=1, description="exact phrase from the narration")
    action: Action
    target: str
    duration_ms: int = Field(default=600, ge=100, le=8000)
    params: dict[str, Any] = Field(default_factory=dict)


class Scene(BaseModel):
    id: str = Field(pattern=r"^s\d{2,3}$")
    template: Template
    section_label: str = ""
    subtitle: str = ""
    title: str
    narration: str = Field(min_length=10)
    pronounce: dict[str, str] = Field(default_factory=dict)
    content: dict[str, Any] = Field(default_factory=dict)
    beats: list[Beat] = Field(default_factory=list)

    @field_validator("narration")
    @classmethod
    def _clean(cls, v: str) -> str:
        return re.sub(r"\s+", " ", v).strip()


class VideoSpec(BaseModel):
    title: str
    scenes: list[Scene]


# ---------------------------------------------------------------- resolved timeline

class TimedWord(BaseModel):
    text: str
    start: float  # seconds, relative to narration audio start
    end: float


class ResolvedBeat(BaseModel):
    action: Action
    target: str
    anchor: str
    start_frame: int
    end_frame: int          # focus actions end when the next focus begins; persistent = scene end
    in_frames: int          # animation-in length (from duration_ms)
    params: dict[str, Any] = Field(default_factory=dict)


class TimelineScene(BaseModel):
    id: str
    template: Template
    section_label: str
    subtitle: str
    title: str
    content: dict[str, Any]
    beats: list[ResolvedBeat]
    duration_frames: int
    audio_offset_frames: int
    audio_file: str
    words: list[TimedWord]  # for captions / debugging


class Timeline(BaseModel):
    title: str
    fps: int
    width: int
    height: int
    scenes: list[TimelineScene]


# ---------------------------------------------------------------- valid targets

def _code_tokens(code: str) -> set[str]:
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?", code))


def valid_targets(template: str, content: dict[str, Any]) -> set[str]:
    """Every element id a beat may target for this template + content."""
    t: set[str] = set()
    if template == "compare_cards":
        for c in content.get("cards", []):
            n = c["name"]
            t |= {f"card:{n}", f"formula:{n}", f"plot:{n}", f"dot:{n}"}
    elif template == "code":
        code = content.get("code", "")
        t |= {f"line:{i}" for i in range(1, len(code.splitlines()) + 1)}
        t |= {f"token:{tok}" for tok in _code_tokens(code)}
        t |= {f"output:{i}" for i in range(1, len(content.get("output", "").splitlines()) + 1)}
        t |= {"panel:code", "panel:output"}
        chart = content.get("chart")
        if chart:
            t.add("panel:chart")
            t |= {f"bar:{lab}" for lab in chart.get("labels", [])}
            t |= {f"series:{s['name']}" for s in chart.get("series", [])}
    elif template == "chart_bars":
        t |= {f"bar:{lab}" for lab in content.get("labels", [])}
        t |= {f"series:{s['name']}" for s in content.get("series", [])}
        t.add("axis:y")
    elif template == "bullets":
        t |= {f"item:{i}" for i in range(1, len(content.get("items", [])) + 1)}
    elif template == "equation":
        t |= {f"term:{term['id']}" for term in content.get("terms", [])}
        t.add("equation")
    elif template == "figure_callout":
        t |= {f"region:{r['id']}" for r in content.get("regions", [])}
        t.add("figure")
    elif template == "diagram":
        t |= {f"node:{n['id']}" for n in content.get("nodes", [])}
        t |= {f"edge:{e['id']}" for e in content.get("edges", [])}
    elif template == "image_filter_demo":
        t |= {"panel:input", "panel:kernel", "panel:output", "zoom:region"}
        t |= {f"weight:{r},{c}" for r in range(3) for c in range(3)}
    elif template == "title":
        t |= {"title", "subtitle"}
    return t


def invalid_beats(scene: Scene) -> list[str]:
    targets = valid_targets(scene.template, scene.content)
    return [f"beat {i}: unknown target '{b.target}'" for i, b in enumerate(scene.beats) if b.target not in targets]
