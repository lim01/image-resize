"""Recursively re-encode images to reduce file size without changing dimensions."""
from __future__ import annotations

import argparse
import glob
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


def is_already_processed(path: Path) -> bool:
    """True if `path` looks like it has already been compressed by this tool.

    A file is considered already processed if either:
    - its stem ends with ``_origin`` (it IS a backup), or
    - a sibling ``<stem>_origin<ext>`` backup file already exists next to it.
    """
    if path.stem.endswith("_origin"):
        return True
    sibling = path.parent / f"{path.stem}_origin{path.suffix}"
    return sibling.exists()


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
    p.add_argument(
        "input_paths",
        type=str,
        nargs="+",
        help=(
            "One or more image files, folders, or glob patterns "
            "(e.g. '*.jpg'). Patterns are expanded by the program, so they "
            "work on shells that don't auto-expand wildcards (Windows cmd)."
        ),
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "Output folder (for folder input, default: <input>_compressed) "
            "or output file path (for single file input, default: "
            "<input_stem>_compressed<ext> next to source)"
        ),
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

    if not 1 <= args.quality <= 100:
        logger.error("--quality must be between 1 and 100")
        return 1

    # Expand glob patterns (Windows shell does not auto-expand) and dedupe.
    # For glob-expanded paths only, skip files that look already-processed:
    #   - the file itself is a backup (stem ends with _origin)
    #   - a sibling <stem>_origin<ext> backup already exists
    expanded: list[Path] = []
    seen: set[Path] = set()
    for raw in args.input_paths:
        from_glob = glob.has_magic(raw)
        if from_glob:
            matches = glob.glob(raw, recursive=True)
            if not matches:
                logger.error("No files matched pattern: %s", raw)
                return 1
            candidates = [Path(m) for m in matches]
        else:
            candidates = [Path(raw)]
        for c in candidates:
            if from_glob and c.is_file() and is_already_processed(c):
                logger.info("Skipping already-processed file: %s", c)
                continue
            try:
                key = c.resolve()
            except OSError:
                key = c
            if key not in seen:
                seen.add(key)
                expanded.append(c)

    # If glob expansion filtered everything out, there's nothing to do.
    if not expanded:
        print("Nothing to do: all matched files already processed.")
        return 0

    # Folder mode: exactly one input that resolves to a directory.
    if len(expanded) == 1 and expanded[0].is_dir():
        in_path: Path = expanded[0]
    elif all(p.is_file() for p in expanded):
        # File mode (one or more files).
        if args.output is not None and len(expanded) > 1:
            logger.error("--output cannot be combined with multiple input files")
            return 1
        sources: list[tuple[Path, Path, bool]] = []
        for in_file in expanded:
            if in_file.suffix.lower() not in SUPPORTED_EXTENSIONS:
                logger.error("Unsupported file extension: %s", in_file.suffix)
                return 1
            if args.output is not None:
                sources.append((in_file, args.output, False))
                continue
            origin_file = in_file.parent / f"{in_file.stem}_origin{in_file.suffix}"
            if origin_file.exists():
                logger.error(
                    "Backup file already exists: %s (refusing to overwrite)",
                    origin_file,
                )
                return 1
            if args.dry_run:
                sources.append((in_file, in_file, False))
            else:
                try:
                    shutil.move(str(in_file), str(origin_file))
                except OSError as exc:
                    logger.error("Failed to set up in-place compression: %s", exc)
                    return 1
                sources.append((origin_file, in_file, False))
        # Skip the folder branch entirely.
        in_path = None  # type: ignore[assignment]
    else:
        for p in expanded:
            if not p.exists():
                logger.error("Input path does not exist: %s", p)
                return 1
        logger.error("Cannot mix files and directories in a single invocation")
        return 1

    if in_path is not None and in_path.is_dir():
        if args.output is not None:
            # explicit output dir: leave original folder untouched
            out_root: Path = args.output
            src_root: Path = in_path
            if not args.dry_run:
                try:
                    out_root.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    logger.error("Failed to create output folder %s: %s", out_root, exc)
                    return 1
            sources = [
                (src, mirror_path(src, src_root, out_root), is_already_processed(src))
                for src in iter_images(src_root)
            ]
        else:
            origin_root = in_path.parent / f"{in_path.name}_origin"
            if origin_root.exists():
                # RESUME MODE: per-file backup for files not yet processed.
                sources = []
                for src in iter_images(in_path):
                    relative = src.relative_to(in_path)
                    backup = origin_root / relative
                    if backup.exists() or is_already_processed(src):
                        # already processed in a prior run -- leave in place
                        sources.append((src, src, True))
                        continue
                    if args.dry_run:
                        sources.append((src, src, False))
                        continue
                    try:
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, backup)
                    except OSError as exc:
                        logger.warning("Failed to back up %s: %s", src, exc)
                        sources.append((src, src, True))
                        continue
                    # compress_one will read from backup and write back to src
                    sources.append((backup, src, False))
            else:
                # FIRST-RUN MODE: rename folder, write back to in_path
                if args.dry_run:
                    src_root = in_path
                    out_root = in_path
                else:
                    try:
                        shutil.move(str(in_path), str(origin_root))
                        in_path.mkdir(parents=True, exist_ok=True)
                    except OSError as exc:
                        logger.error("Failed to set up in-place compression: %s", exc)
                        return 1
                    src_root = origin_root
                    out_root = in_path
                sources = [
                    (src, mirror_path(src, src_root, out_root), is_already_processed(src))
                    for src in iter_images(src_root)
                ]

    processed = 0
    skipped = 0
    passed_through = 0
    total_original = 0
    total_new = 0

    for src, dst, passthrough in sources:
        if args.dry_run:
            if passthrough:
                logger.debug("Would pass through %s -> %s", src, dst)
                passed_through += 1
            else:
                logger.debug("Would compress %s -> %s", src, dst)
                processed += 1
            continue
        if passthrough:
            if src.resolve() != dst.resolve():
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                except OSError as exc:
                    logger.warning("Failed to pass through %s: %s", src, exc)
                    skipped += 1
                    continue
            logger.info("Passed through (already processed): %s", src.name)
            passed_through += 1
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
        msg = f"Dry run: {processed} file(s) would be processed."
        if passed_through:
            msg += f" {passed_through} would be passed through."
        print(msg)
    else:
        saved = total_original - total_new
        pct = (saved / total_original * 100) if total_original else 0.0
        print(f"Processed: {processed} files")
        if passed_through:
            print(f"Passed through (already processed): {passed_through} files")
        print(f"Skipped:   {skipped} files")
        print(f"Original size:   {_format_bytes(total_original)}")
        print(f"Compressed size: {_format_bytes(total_new)}")
        print(f"Saved:           {_format_bytes(saved)} ({pct:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
