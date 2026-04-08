"""Recursively re-encode images to reduce file size without changing dimensions."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from PIL import Image

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


def compress_one(
    src: Path, dst: Path, quality: int, png_optimize: bool
) -> tuple[int, int]:
    """Re-encode `src` into `dst` using format-appropriate options.

    Returns (original_bytes, new_bytes). Caller is responsible for keep-larger logic.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix.lower()

    with Image.open(src) as img:
        if suffix in (".jpg", ".jpeg"):
            save_kwargs = {
                "format": "JPEG",
                "quality": quality,
                "optimize": True,
                "progressive": True,
            }
            exif = img.info.get("exif")
            if exif:
                save_kwargs["exif"] = exif
            # JPEG cannot store alpha; convert if needed
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(dst, **save_kwargs)
        elif suffix == ".png":
            img.save(
                dst,
                format="PNG",
                optimize=png_optimize,
                compress_level=9,
            )
        elif suffix == ".webp":
            img.save(dst, format="WEBP", quality=quality, method=6)
        else:
            raise ValueError(f"Unsupported extension: {suffix}")

    return src.stat().st_size, dst.stat().st_size
