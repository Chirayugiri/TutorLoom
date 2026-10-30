"""Run code blocks from the notes in a sandboxed subprocess and capture real output.

Sandbox (soft, unprivileged): isolated interpreter (-I), empty temp cwd and HOME, scrubbed env,
socket module disabled, memory/CPU/file-size rlimits, wall-clock timeout. Ubuntu blocks
unprivileged network namespaces, so network isolation is enforced in-process, not by the kernel.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

HARNESS = r'''
import io, json, os, resource, socket, sys, contextlib
resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
resource.setrlimit(resource.RLIMIT_CPU, (int(sys.argv[3]), int(sys.argv[3])))
resource.setrlimit(resource.RLIMIT_FSIZE, (50 << 20, 50 << 20))
def _blocked(*a, **k):
    raise OSError("network access is disabled in the notes sandbox")
class _NoSocket:
    def __init__(self, *a, **k): _blocked()
socket.socket = _NoSocket
socket.create_connection = socket.getaddrinfo = socket.socketpair = _blocked
os.environ["MPLBACKEND"] = "Agg"
src, out_dir = sys.argv[1], sys.argv[2]
g = {"__name__": "__main__"}
buf = io.StringIO()
err = None
try:
    with contextlib.redirect_stdout(buf):
        exec(compile(open(src).read(), "<notes>", "exec"), g)
except BaseException as e:
    err = f"{type(e).__name__}: {e}"
def _plain(v, depth=0):
    if depth > 3: raise TypeError
    if v is None or isinstance(v, (bool, int, float, str)): return v
    if hasattr(v, "tolist"): return _plain(v.tolist(), depth + 1)
    if isinstance(v, (list, tuple)) and len(v) <= 1000: return [_plain(x, depth + 1) for x in v]
    if isinstance(v, dict) and len(v) <= 200: return {str(k): _plain(x, depth + 1) for k, x in v.items()}
    raise TypeError
vars_ = {}
for k, v in g.items():
    if k.startswith("_") or callable(v) or type(v).__name__ == "module": continue
    try: vars_[k] = _plain(v)
    except Exception: pass
figs = []
if "matplotlib.pyplot" in sys.modules:
    plt = sys.modules["matplotlib.pyplot"]
    for n in plt.get_fignums():
        p = os.path.join(out_dir, f"fig{n}.png")
        plt.figure(n).savefig(p, dpi=150, facecolor="#0A0A0B")
        figs.append(p)
json.dump({"stdout": buf.getvalue(), "error": err, "vars": vars_, "figures": figs}, open(os.path.join(out_dir, "result.json"), "w"))
'''


@dataclass
class ExecResult:
    ok: bool
    stdout: str
    error: str | None = None
    vars: dict = field(default_factory=dict)
    figures: list[str] = field(default_factory=list)


def run_code(code: str, timeout_s: int = 20, figures_dir: Path | None = None, python: str | None = None) -> ExecResult:
    with tempfile.TemporaryDirectory(prefix="n2v-exec-") as tmp:
        t = Path(tmp)
        (t / "snippet.py").write_text(code)
        (t / "harness.py").write_text(HARNESS)
        env = {"PATH": "/usr/bin:/bin", "HOME": tmp, "MPLBACKEND": "Agg", "PYTHONHASHSEED": "0", "LANG": "C.UTF-8"}
        try:
            proc = subprocess.run(
                [python or sys.executable, "-I", str(t / "harness.py"), str(t / "snippet.py"), tmp, str(timeout_s)],
                cwd=tmp, env=env, capture_output=True, text=True, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(ok=False, stdout="", error=f"timed out after {timeout_s}s")
        result_file = t / "result.json"
        if not result_file.exists():
            return ExecResult(ok=False, stdout=proc.stdout, error=(proc.stderr.strip().splitlines() or ["crashed"])[-1])
        data = json.loads(result_file.read_text())
        figs = []
        if figures_dir and data["figures"]:
            figures_dir.mkdir(parents=True, exist_ok=True)
            for f in data["figures"]:
                dst = figures_dir / Path(f).name
                dst.write_bytes(Path(f).read_bytes())
                figs.append(str(dst))
        return ExecResult(ok=data["error"] is None, stdout=data["stdout"], error=data["error"], vars=data["vars"], figures=figs)
