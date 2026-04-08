"""Recursively re-encode images to reduce file size without changing dimensions."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def iter_images(root: Path) -> Iterator[Path]:
    """Yield image files under `root` whose extension is supported."""
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def mirror_path(src: Path, in_root: Path, out_root: Path) -> Path:
    """Compute the destination path under `out_root` mirroring `src`'s relative location."""
    relative = src.relative_to(in_root)
    return out_root / relative
