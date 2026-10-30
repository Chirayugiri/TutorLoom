"""Deterministic content preparation: run code, bind chart data to real captured variables."""
from __future__ import annotations

import logging
from pathlib import Path

from .executor import run_code
from .schemas import Scene

log = logging.getLogger(__name__)


def fmt_label(v) -> str:
    return f"{v:.1f}" if isinstance(v, float) else str(v)


def materialize(scene: Scene, figures_dir: Path | None = None) -> list[str]:
    """Fill code-scene output/chart values from a real run. Returns warnings."""
    warnings: list[str] = []
    c = scene.content
    if scene.template != "code" or not c.get("code"):
        return warnings
    res = run_code(c["code"], figures_dir=figures_dir)
    c["output"] = res.stdout.rstrip("\n")
    if not res.ok:
        warnings.append(f"{scene.id}: code failed: {res.error}")
        c["output"] = (c["output"] + "\n" if c["output"] else "") + str(res.error)
    chart = c.get("chart")
    if chart:
        if "labels_var" in chart:
            labels = res.vars.get(chart["labels_var"])
            if isinstance(labels, list):
                chart["labels"] = [fmt_label(v) for v in labels]
            else:
                warnings.append(f"{scene.id}: chart labels variable '{chart['labels_var']}' not found")
        for s in chart.get("series", []):
            if "var" in s:
                vals = res.vars.get(s["var"])
                if isinstance(vals, list) and all(isinstance(v, (int, float)) for v in vals):
                    s["values"] = [float(v) for v in vals]
                else:
                    warnings.append(f"{scene.id}: chart series variable '{s['var']}' missing or not numeric")
                    s["values"] = []
        chart.setdefault("labels", [])
    return warnings
