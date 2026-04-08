# Image Compression Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that re-encodes JPEG/PNG/WebP files in a folder (recursively) without changing image dimensions, writing the smaller files to a separate output folder that mirrors the input structure.

**Architecture:** Single-file CLI (`compress_images.py`) using Pillow. Pure functions for path mirroring, file iteration, and per-file compression. `main()` parses CLI args, walks the input tree, calls the compress function per file, and prints aggregate stats. Pytest-based tests with fixtures generated dynamically via Pillow.

**Tech Stack:** Python 3.9+, Pillow, pytest, argparse, pathlib (stdlib).

---

## File Structure

| Path | Responsibility |
|---|---|
| `compress_images.py` | CLI entry point + all compression logic (single file due to small scope) |
| `requirements.txt` | Pinned runtime + dev dependencies (Pillow, pytest) |
| `tests/conftest.py` | Pytest fixtures: dynamically generates sample JPEG/PNG/WebP/broken/unsupported files in tmp dirs |
| `tests/test_compress_images.py` | All unit + integration tests |
| `README.md` | Usage and install instructions |
| `.gitignore` | Python ignores |

---

## Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: Create `.gitignore`**

Write `.gitignore`:
```
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/
*.egg-info/
.idea/
.vscode/
```

- [ ] **Step 2: Create `requirements.txt`**

Write `requirements.txt`:
```
Pillow>=10.0.0
pytest>=7.0.0
```

- [ ] **Step 3: Create `README.md`**

Write `README.md`:
````markdown
# image-resize

Recursively compress JPEG/PNG/WebP images in a folder without changing dimensions.

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
python compress_images.py <input_dir> [-o <output_dir>] [-q 85] [--dry-run] [-v]
```

Default output folder: `<input_dir>_compressed`.

## Test

```bash
pytest -v
```
````

- [ ] **Step 4: Install dependencies and verify**

Run: `pip install -r requirements.txt`
Expected: Pillow and pytest install successfully.

Run: `python -c "import PIL; import pytest; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add .gitignore requirements.txt README.md
git commit -m "chore: project scaffolding (deps, gitignore, readme)"
```

---

## Task 2: Test fixtures (conftest.py)

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create empty `tests/__init__.py`**

Write empty file `tests/__init__.py`.

- [ ] **Step 2: Create `tests/conftest.py` with fixtures**

Write `tests/conftest.py`:
```python
"""Shared pytest fixtures for image compression tests."""
from pathlib import Path

import pytest
from PIL import Image


def _make_jpeg(path: Path, size=(800, 600), color=(200, 100, 50)) -> None:
    img = Image.new("RGB", size, color)
    img.save(path, "JPEG", quality=100)


def _make_png(path: Path, size=(400, 300), color=(50, 150, 200)) -> None:
    img = Image.new("RGBA", size, (*color, 255))
    img.save(path, "PNG")


def _make_webp(path: Path, size=(500, 400), color=(100, 200, 100)) -> None:
    img = Image.new("RGB", size, color)
    img.save(path, "WEBP", quality=100)


@pytest.fixture
def sample_tree(tmp_path: Path) -> Path:
    """Create a nested input folder with various image types."""
    root = tmp_path / "input"
    root.mkdir()
    sub = root / "sub"
    sub.mkdir()
    nested = sub / "deep"
    nested.mkdir()

    _make_jpeg(root / "a.jpg")
    _make_jpeg(root / "b.jpeg")
    _make_png(sub / "c.png")
    _make_webp(nested / "d.webp")
    # unsupported file should be ignored
    (root / "notes.txt").write_text("ignore me")
    return root


@pytest.fixture
def broken_image_tree(tmp_path: Path) -> Path:
    """Folder containing one valid and one corrupt JPEG."""
    root = tmp_path / "input"
    root.mkdir()
    _make_jpeg(root / "good.jpg")
    (root / "bad.jpg").write_bytes(b"this is not a jpeg")
    return root
```

- [ ] **Step 3: Verify fixtures import**

Run: `python -c "from tests.conftest import _make_jpeg; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add tests/__init__.py tests/conftest.py
git commit -m "test: add pytest fixtures for sample image trees"
```

---

## Task 3: `iter_images` — recursive file discovery

**Files:**
- Create: `compress_images.py`
- Create: `tests/test_compress_images.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_compress_images.py`:
```python
"""Tests for compress_images.py."""
from pathlib import Path

import pytest

import compress_images as ci


def test_iter_images_finds_supported_extensions(sample_tree: Path) -> None:
    found = sorted(p.name for p in ci.iter_images(sample_tree))
    assert found == ["a.jpg", "b.jpeg", "c.png", "d.webp"]


def test_iter_images_skips_unsupported(sample_tree: Path) -> None:
    found = [p.name for p in ci.iter_images(sample_tree)]
    assert "notes.txt" not in found
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_compress_images.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'compress_images'`

- [ ] **Step 3: Create `compress_images.py` with `iter_images`**

Write `compress_images.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_compress_images.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add compress_images.py tests/test_compress_images.py
git commit -m "feat: add iter_images for recursive supported-file discovery"
```

---

## Task 4: `mirror_path` — output path computation

**Files:**
- Modify: `compress_images.py`
- Modify: `tests/test_compress_images.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_compress_images.py`:
```python
def test_mirror_path_top_level(tmp_path: Path) -> None:
    in_root = tmp_path / "in"
    out_root = tmp_path / "out"
    src = in_root / "a.jpg"
    assert ci.mirror_path(src, in_root, out_root) == out_root / "a.jpg"


def test_mirror_path_nested(tmp_path: Path) -> None:
    in_root = tmp_path / "in"
    out_root = tmp_path / "out"
    src = in_root / "sub" / "deep" / "d.webp"
    expected = out_root / "sub" / "deep" / "d.webp"
    assert ci.mirror_path(src, in_root, out_root) == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_compress_images.py -v`
Expected: 2 new tests FAIL — `AttributeError: module 'compress_images' has no attribute 'mirror_path'`

- [ ] **Step 3: Implement `mirror_path`**

Append to `compress_images.py` (after `iter_images`):
```python
def mirror_path(src: Path, in_root: Path, out_root: Path) -> Path:
    """Compute the destination path under `out_root` mirroring `src`'s relative location."""
    relative = src.relative_to(in_root)
    return out_root / relative
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_compress_images.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add compress_images.py tests/test_compress_images.py
git commit -m "feat: add mirror_path for output path computation"
```

---

## Task 5: `compress_one` — single-file compression (JPEG)

**Files:**
- Modify: `compress_images.py`
- Modify: `tests/test_compress_images.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_compress_images.py`:
```python
from PIL import Image


def test_compress_one_jpeg_reduces_or_keeps_size(tmp_path: Path) -> None:
    src = tmp_path / "a.jpg"
    # high-entropy gradient compresses noticeably at quality 85
    img = Image.new("RGB", (1000, 1000))
    pixels = img.load()
    for x in range(1000):
        for y in range(1000):
            pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    img.save(src, "JPEG", quality=100)

    dst = tmp_path / "out" / "a.jpg"
    dst.parent.mkdir()
    original_size, new_size = ci.compress_one(src, dst, quality=85, png_optimize=True)

    assert dst.exists()
    assert original_size == src.stat().st_size
    assert new_size == dst.stat().st_size
    assert new_size < original_size


def test_compress_one_preserves_dimensions(tmp_path: Path) -> None:
    src = tmp_path / "a.jpg"
    Image.new("RGB", (640, 480), (10, 20, 30)).save(src, "JPEG", quality=100)
    dst = tmp_path / "out" / "a.jpg"
    dst.parent.mkdir()
    ci.compress_one(src, dst, quality=85, png_optimize=True)
    with Image.open(dst) as out_img:
        assert out_img.size == (640, 480)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_compress_images.py -v`
Expected: New tests FAIL — `AttributeError: module 'compress_images' has no attribute 'compress_one'`

- [ ] **Step 3: Implement `compress_one`**

Append to `compress_images.py`:
```python
from PIL import Image


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_compress_images.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add compress_images.py tests/test_compress_images.py
git commit -m "feat: add compress_one with format-specific encoding"
```

---

## Task 6: `compress_one` — PNG and WebP coverage

**Files:**
- Modify: `tests/test_compress_images.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_compress_images.py`:
```python
def test_compress_one_png_writes_output(tmp_path: Path) -> None:
    src = tmp_path / "a.png"
    Image.new("RGBA", (300, 200), (50, 150, 200, 255)).save(src, "PNG")
    dst = tmp_path / "out" / "a.png"
    dst.parent.mkdir()
    original_size, new_size = ci.compress_one(src, dst, quality=85, png_optimize=True)
    assert dst.exists()
    assert new_size > 0
    with Image.open(dst) as out_img:
        assert out_img.size == (300, 200)


def test_compress_one_webp_writes_output(tmp_path: Path) -> None:
    src = tmp_path / "a.webp"
    Image.new("RGB", (500, 400), (100, 200, 100)).save(src, "WEBP", quality=100)
    dst = tmp_path / "out" / "a.webp"
    dst.parent.mkdir()
    _, new_size = ci.compress_one(src, dst, quality=85, png_optimize=True)
    assert dst.exists()
    assert new_size > 0


def test_compress_one_preserves_jpeg_exif(tmp_path: Path) -> None:
    import piexif  # optional; if not installed, skip

    src = tmp_path / "a.jpg"
    Image.new("RGB", (200, 200), (10, 20, 30)).save(src, "JPEG", quality=100)
    # write a minimal EXIF block
    exif_dict = {"0th": {piexif.ImageIFD.Make: b"TestCam"}}
    exif_bytes = piexif.dump(exif_dict)
    Image.open(src).save(src, "JPEG", exif=exif_bytes, quality=100)

    dst = tmp_path / "out" / "a.jpg"
    dst.parent.mkdir()
    ci.compress_one(src, dst, quality=85, png_optimize=True)

    with Image.open(dst) as out_img:
        assert out_img.info.get("exif"), "EXIF should be preserved"
```

Note: the EXIF test uses `piexif`. If unavailable, mark with `pytest.importorskip`:

Replace the EXIF test with:
```python
def test_compress_one_preserves_jpeg_exif(tmp_path: Path) -> None:
    piexif = pytest.importorskip("piexif")
    src = tmp_path / "a.jpg"
    Image.new("RGB", (200, 200), (10, 20, 30)).save(src, "JPEG", quality=100)
    exif_dict = {"0th": {piexif.ImageIFD.Make: b"TestCam"}}
    exif_bytes = piexif.dump(exif_dict)
    Image.open(src).save(src, "JPEG", exif=exif_bytes, quality=100)

    dst = tmp_path / "out" / "a.jpg"
    dst.parent.mkdir()
    ci.compress_one(src, dst, quality=85, png_optimize=True)

    with Image.open(dst) as out_img:
        assert out_img.info.get("exif"), "EXIF should be preserved"
```

- [ ] **Step 2: Run tests to verify PNG/WebP tests pass and EXIF skips (or passes)**

Run: `pytest tests/test_compress_images.py -v`
Expected: PNG and WebP tests PASS. EXIF test PASSES if piexif installed, otherwise SKIPPED.

(No implementation change needed — `compress_one` already supports these formats.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_compress_images.py
git commit -m "test: cover PNG/WebP compression and JPEG EXIF preservation"
```

---

## Task 7: `main()` — CLI argument parsing and orchestration

**Files:**
- Modify: `compress_images.py`
- Modify: `tests/test_compress_images.py`

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_compress_images.py`:
```python
def test_main_compresses_tree_to_default_output(
    sample_tree: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["compress_images.py", str(sample_tree)])
    exit_code = ci.main()
    assert exit_code == 0

    out_root = sample_tree.parent / f"{sample_tree.name}_compressed"
    assert (out_root / "a.jpg").exists()
    assert (out_root / "b.jpeg").exists()
    assert (out_root / "sub" / "c.png").exists()
    assert (out_root / "sub" / "deep" / "d.webp").exists()
    # unsupported file must NOT be copied
    assert not (out_root / "notes.txt").exists()

    captured = capsys.readouterr().out
    assert "Processed" in captured


def test_main_respects_custom_output_dir(
    sample_tree: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir = tmp_path / "custom_out"
    monkeypatch.setattr(
        "sys.argv",
        ["compress_images.py", str(sample_tree), "-o", str(out_dir)],
    )
    assert ci.main() == 0
    assert (out_dir / "a.jpg").exists()


def test_main_dry_run_creates_no_files(
    sample_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["compress_images.py", str(sample_tree), "--dry-run"],
    )
    assert ci.main() == 0
    out_root = sample_tree.parent / f"{sample_tree.name}_compressed"
    assert not out_root.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_compress_images.py -v`
Expected: New tests FAIL — `AttributeError: module 'compress_images' has no attribute 'main'`

- [ ] **Step 3: Implement `main()` and supporting logic**

Append to `compress_images.py`:
```python
import argparse
import logging
import shutil
import sys

logger = logging.getLogger("compress_images")


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_compress_images.py -v`
Expected: All tests PASS (PNG, WebP, JPEG, mirror_path, iter_images, main x3, dimensions, EXIF skipped or pass).

- [ ] **Step 5: Commit**

```bash
git add compress_images.py tests/test_compress_images.py
git commit -m "feat: add main() with CLI parsing, traversal, and stats"
```

---

## Task 8: Broken-image resilience

**Files:**
- Modify: `tests/test_compress_images.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_compress_images.py`:
```python
def test_main_skips_broken_images(
    broken_image_tree: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.argv", ["compress_images.py", str(broken_image_tree)])
    assert ci.main() == 0

    out_root = broken_image_tree.parent / f"{broken_image_tree.name}_compressed"
    assert (out_root / "good.jpg").exists()
    assert not (out_root / "bad.jpg").exists()

    captured = capsys.readouterr().out
    assert "Processed: 1 files" in captured
    assert "Skipped:   1 files" in captured
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_compress_images.py::test_main_skips_broken_images -v`
Expected: PASS (the existing try/except in `main()` already covers this case).

If it fails, the failure message will show whether the issue is in the assertions or in error handling — fix in `main()` accordingly without weakening other behavior.

- [ ] **Step 3: Commit**

```bash
git add tests/test_compress_images.py
git commit -m "test: verify broken images are skipped without aborting the run"
```

---

## Task 9: Missing input folder + invalid quality

**Files:**
- Modify: `tests/test_compress_images.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_compress_images.py`:
```python
def test_main_returns_error_for_missing_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nonexistent = tmp_path / "nope"
    monkeypatch.setattr("sys.argv", ["compress_images.py", str(nonexistent)])
    assert ci.main() == 1


def test_main_returns_error_for_invalid_quality(
    sample_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["compress_images.py", str(sample_tree), "-q", "150"],
    )
    assert ci.main() == 1
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_compress_images.py -v`
Expected: All previous + 2 new tests PASS (existing validation in `main()` handles both).

- [ ] **Step 3: Commit**

```bash
git add tests/test_compress_images.py
git commit -m "test: verify error handling for missing input and bad quality"
```

---

## Task 10: End-to-end smoke test via subprocess

**Files:**
- Modify: `tests/test_compress_images.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_compress_images.py`:
```python
import subprocess
import sys as _sys


def test_cli_smoke_via_subprocess(sample_tree: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "smoke_out"
    result = subprocess.run(
        [
            _sys.executable,
            "compress_images.py",
            str(sample_tree),
            "-o",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (out_dir / "a.jpg").exists()
    assert (out_dir / "sub" / "c.png").exists()
    assert "Processed" in result.stdout
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_compress_images.py::test_cli_smoke_via_subprocess -v`
Expected: PASS.

- [ ] **Step 3: Run the full test suite**

Run: `pytest -v`
Expected: All tests pass. Note any skipped EXIF test (acceptable if `piexif` not installed).

- [ ] **Step 4: Commit**

```bash
git add tests/test_compress_images.py
git commit -m "test: end-to-end CLI smoke test via subprocess"
```

---

## Task 11: Manual sanity check

- [ ] **Step 1: Create a small real-world test folder**

```bash
mkdir -p sandbox/photos/sub
python -c "from PIL import Image; \
Image.new('RGB',(1600,1200),(120,80,40)).save('sandbox/photos/p1.jpg', quality=100); \
Image.new('RGB',(800,600),(40,80,120)).save('sandbox/photos/sub/p2.jpg', quality=100)"
```

- [ ] **Step 2: Run the tool**

Run: `python compress_images.py sandbox/photos -v`
Expected:
- Output folder `sandbox/photos_compressed/` exists
- Contains `p1.jpg` and `sub/p2.jpg`
- Stats line shows non-zero `Saved`

- [ ] **Step 3: Clean up sandbox**

```bash
rm -rf sandbox
```

- [ ] **Step 4: Commit (if any tracked changes were produced — otherwise skip)**

No commit expected; sandbox is gitignored implicitly. If `git status` shows nothing, skip.

---

## Done

At this point:
- All spec sections (5–10 of the design doc) are covered by tasks
- Test suite covers iteration, path mirroring, per-format compression, dimension preservation, EXIF preservation, full CLI flow, dry-run, broken-file resilience, error exits, and end-to-end subprocess invocation
- Single-file implementation matches the module-composition table in spec section 6
