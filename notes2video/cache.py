"""Content-hash caching: every output file gets a sidecar `<file>.key` holding the hash of its inputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def content_hash(*parts: Any) -> str:
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, Path):
            h.update(p.read_bytes() if p.is_file() else str(p).encode())
        elif isinstance(p, bytes):
            h.update(p)
        else:
            h.update(json.dumps(p, sort_keys=True, default=str).encode())
        h.update(b"\x00")
    return h.hexdigest()[:20]


def tree_hash(root: Path, suffixes: tuple[str, ...]) -> str:
    """Hash all files under root with the given suffixes (used to invalidate renders when TSX changes)."""
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in suffixes)
    return content_hash(*[str(p.relative_to(root)) for p in files], *files)


def _key_file(out: Path) -> Path:
    return out.with_name(out.name + ".key")


def is_fresh(out: Path, key: str) -> bool:
    kf = _key_file(out)
    return out.exists() and kf.exists() and kf.read_text().strip() == key


def mark(out: Path, key: str) -> None:
    _key_file(out).write_text(key)
