"""Recursively re-encode images to reduce file size without changing dimensions."""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path
from typing import Iterator

from PIL import Image

logger = logging.getLogger("compress_images")

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


def _format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Recursively compress images in a folder without changing dimensions.",
    )
    p.add_argument("input_dir", type=Path, help="Folder containing images to compress")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output folder (default: <input_dir>_compressed)",
    )
    p.add_argument(
        "-q",
        "--quality",
        type=int,
        default=85,
        help="JPEG/WebP quality 1-100 (default: 85)",
    )
    p.add_argument(
        "--no-png-optimize",
        dest="png_optimize",
        action="store_false",
        help="Disable PNG optimize",
    )
    p.add_argument(
        "--no-keep-larger",
        dest="keep_larger",
        action="store_false",
        help="Do not fall back to original when compression yields a larger file",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without writing files",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    p.set_defaults(png_optimize=True, keep_larger=True)
    return p


def main() -> int:
    args = _build_parser().parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    in_root: Path = args.input_dir
    if not in_root.is_dir():
        logger.error("Input folder does not exist: %s", in_root)
        return 1

    if not 1 <= args.quality <= 100:
        logger.error("--quality must be between 1 and 100")
        return 1

    out_root: Path = args.output or in_root.parent / f"{in_root.name}_compressed"

    if not args.dry_run:
        try:
            out_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.error("Failed to create output folder %s: %s", out_root, exc)
            return 1

    processed = 0
    skipped = 0
    total_original = 0
    total_new = 0

    for src in iter_images(in_root):
        dst = mirror_path(src, in_root, out_root)
        if args.dry_run:
            logger.debug("Would compress %s -> %s", src, dst)
            processed += 1
            continue
        try:
            original, new = compress_one(
                src, dst, quality=args.quality, png_optimize=args.png_optimize
            )
        except Exception as exc:
            logger.warning("Skipping %s: %s", src, exc)
            skipped += 1
            continue

        if args.keep_larger and new > original:
            logger.debug("Compressed file larger; copying original for %s", src)
            shutil.copy2(src, dst)
            new = dst.stat().st_size

        total_original += original
        total_new += new
        processed += 1
        logger.debug(
            "Compressed %s: %s -> %s",
            src.name,
            _format_bytes(original),
            _format_bytes(new),
        )

    if args.dry_run:
        print(f"Dry run: {processed} file(s) would be processed.")
    else:
        saved = total_original - total_new
        pct = (saved / total_original * 100) if total_original else 0.0
        print(f"Processed: {processed} files")
        print(f"Skipped:   {skipped} files")
        print(f"Original size:   {_format_bytes(total_original)}")
        print(f"Compressed size: {_format_bytes(total_new)}")
        print(f"Saved:           {_format_bytes(saved)} ({pct:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
