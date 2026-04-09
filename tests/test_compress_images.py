"""Tests for compress_images.py."""
import subprocess
import sys as _sys
from pathlib import Path

import pytest
from PIL import Image

import compress_images as ci


def test_iter_images_finds_supported_extensions(sample_tree: Path) -> None:
    found = sorted(p.name for p in ci.iter_images(sample_tree))
    assert found == ["a.jpg", "b.jpeg", "c.png", "d.webp"]


def test_iter_images_skips_unsupported(sample_tree: Path) -> None:
    found = [p.name for p in ci.iter_images(sample_tree)]
    assert "notes.txt" not in found


def test_iter_images_skips_symlinks(tmp_path: Path) -> None:
    real = tmp_path / "real.jpg"
    Image.new("RGB", (100, 100), (10, 20, 30)).save(real, "JPEG")
    link = tmp_path / "link.jpg"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported in this environment")

    found = [p.name for p in ci.iter_images(tmp_path)]
    assert "real.jpg" in found
    assert "link.jpg" not in found


def test_module_sets_explicit_decompression_bomb_limit() -> None:
    # The module should pin its own explicit limit, not rely on Pillow defaults.
    assert ci.MAX_IMAGE_PIXELS_LIMIT == 100_000_000
    assert Image.MAX_IMAGE_PIXELS == ci.MAX_IMAGE_PIXELS_LIMIT


def test_compress_one_rejects_decompression_bomb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "big.jpg"
    Image.new("RGB", (200, 200), (10, 20, 30)).save(src, "JPEG")
    # Lower the limit so the 200x200 image counts as a "bomb"
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)

    dst = tmp_path / "out.jpg"
    with pytest.raises(Image.DecompressionBombError):
        ci.compress_one(src, dst, quality=85, png_optimize=True)


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


def test_main_compresses_tree_in_place_with_origin_backup(
    sample_tree: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # capture original sizes before mutation
    orig_a_size = (sample_tree / "a.jpg").stat().st_size

    monkeypatch.setattr("sys.argv", ["compress_images.py", str(sample_tree)])
    exit_code = ci.main()
    assert exit_code == 0

    origin_root = sample_tree.parent / f"{sample_tree.name}_origin"

    # compressed files now sit at the original input path
    assert (sample_tree / "a.jpg").exists()
    assert (sample_tree / "b.jpeg").exists()
    assert (sample_tree / "sub" / "c.png").exists()
    assert (sample_tree / "sub" / "deep" / "d.webp").exists()
    # unsupported file should be preserved at the original path location too
    # (it lives in the origin backup; not required at output path)

    # originals preserved in <name>_origin with identical structure
    assert (origin_root / "a.jpg").exists()
    assert (origin_root / "b.jpeg").exists()
    assert (origin_root / "sub" / "c.png").exists()
    assert (origin_root / "sub" / "deep" / "d.webp").exists()
    assert (origin_root / "notes.txt").exists()

    # the compressed a.jpg should be smaller than (or equal to) the original
    assert (sample_tree / "a.jpg").stat().st_size <= orig_a_size
    # and the origin copy should match the captured original size
    assert (origin_root / "a.jpg").stat().st_size == orig_a_size

    captured = capsys.readouterr().out
    assert "Processed" in captured


def test_main_folder_in_place_skips_already_processed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "input"
    root.mkdir()
    # pre-existing already-processed pair
    a = root / "a.jpg"
    a_origin = root / "a_origin.jpg"
    Image.new("RGB", (320, 240), (10, 20, 30)).save(a, "JPEG", quality=85)
    Image.new("RGB", (320, 240), (10, 20, 30)).save(a_origin, "JPEG", quality=100)
    a_size = a.stat().st_size
    a_origin_size = a_origin.stat().st_size

    # fresh file that should actually get compressed
    b = root / "b.jpg"
    img = Image.new("RGB", (600, 600))
    pixels = img.load()
    for x in range(600):
        for y in range(600):
            pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    img.save(b, "JPEG", quality=100)
    b_orig_size = b.stat().st_size

    monkeypatch.setattr("sys.argv", ["compress_images.py", str(root)])
    assert ci.main() == 0

    origin_root = tmp_path / "input_origin"
    # backup contains all originals
    assert (origin_root / "a.jpg").exists()
    assert (origin_root / "a_origin.jpg").exists()
    assert (origin_root / "b.jpg").exists()

    # output (= input path) contains all files (passthrough preserved)
    assert (root / "a.jpg").exists()
    assert (root / "a_origin.jpg").exists()
    assert (root / "b.jpg").exists()

    # a.jpg and a_origin.jpg passed through unchanged
    assert (root / "a.jpg").stat().st_size == a_size
    assert (root / "a_origin.jpg").stat().st_size == a_origin_size

    # b.jpg actually compressed
    assert (root / "b.jpg").stat().st_size < b_orig_size


def test_main_folder_resume_processes_only_new_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    in_root = tmp_path / "photos"
    in_root.mkdir()
    origin_root = tmp_path / "photos_origin"
    origin_root.mkdir()

    # previously-processed pair: photos/a.jpg + photos_origin/a.jpg
    a = in_root / "a.jpg"
    a_backup = origin_root / "a.jpg"
    Image.new("RGB", (320, 240), (10, 20, 30)).save(a, "JPEG", quality=85)
    Image.new("RGB", (320, 240), (10, 20, 30)).save(a_backup, "JPEG", quality=100)
    a_size_before = a.stat().st_size
    a_backup_size_before = a_backup.stat().st_size

    # newly-added file with no backup yet
    b = in_root / "b.jpg"
    img = Image.new("RGB", (600, 600))
    pixels = img.load()
    for x in range(600):
        for y in range(600):
            pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    img.save(b, "JPEG", quality=100)
    b_orig_size = b.stat().st_size

    monkeypatch.setattr("sys.argv", ["compress_images.py", str(in_root)])
    assert ci.main() == 0

    # previously-processed file untouched
    assert a.stat().st_size == a_size_before
    assert a_backup.stat().st_size == a_backup_size_before

    # new file: backed up + compressed in place
    assert (origin_root / "b.jpg").exists()
    assert (origin_root / "b.jpg").stat().st_size == b_orig_size
    assert b.stat().st_size < b_orig_size


def test_main_folder_resume_with_no_new_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    in_root = tmp_path / "photos"
    in_root.mkdir()
    origin_root = tmp_path / "photos_origin"
    origin_root.mkdir()
    Image.new("RGB", (100, 100), (10, 20, 30)).save(
        in_root / "a.jpg", "JPEG", quality=85
    )
    Image.new("RGB", (100, 100), (10, 20, 30)).save(
        origin_root / "a.jpg", "JPEG", quality=100
    )
    a_size_before = (in_root / "a.jpg").stat().st_size

    monkeypatch.setattr("sys.argv", ["compress_images.py", str(in_root)])
    assert ci.main() == 0
    assert (in_root / "a.jpg").stat().st_size == a_size_before


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
    orig_size = (sample_tree / "a.jpg").stat().st_size
    monkeypatch.setattr(
        "sys.argv",
        ["compress_images.py", str(sample_tree), "--dry-run"],
    )
    assert ci.main() == 0
    origin_root = sample_tree.parent / f"{sample_tree.name}_origin"
    assert not origin_root.exists()
    # original file untouched
    assert (sample_tree / "a.jpg").stat().st_size == orig_size


def test_main_skips_broken_images(
    broken_image_tree: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.argv", ["compress_images.py", str(broken_image_tree)])
    assert ci.main() == 0

    origin_root = broken_image_tree.parent / f"{broken_image_tree.name}_origin"
    # good was compressed in place; bad was skipped (not present at output path)
    assert (broken_image_tree / "good.jpg").exists()
    assert not (broken_image_tree / "bad.jpg").exists()
    # both originals preserved
    assert (origin_root / "good.jpg").exists()
    assert (origin_root / "bad.jpg").exists()

    captured = capsys.readouterr().out
    assert "Processed: 1 files" in captured
    assert "Skipped:   1 files" in captured


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


def test_main_single_file_in_place_with_origin_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "photo.jpg"
    # high-entropy content so compression actually shrinks the file
    img = Image.new("RGB", (1000, 1000))
    pixels = img.load()
    for x in range(1000):
        for y in range(1000):
            pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    img.save(src, "JPEG", quality=100)
    orig_size = src.stat().st_size

    monkeypatch.setattr("sys.argv", ["compress_images.py", str(src), "-q", "85"])
    assert ci.main() == 0

    backup = tmp_path / "photo_origin.jpg"
    assert backup.exists()
    assert backup.stat().st_size == orig_size

    # original path now holds the compressed (smaller) version with same dims
    assert src.exists()
    assert src.stat().st_size < orig_size
    with Image.open(src) as out_img:
        assert out_img.size == (1000, 1000)


def test_main_single_file_errors_if_origin_already_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "photo.jpg"
    Image.new("RGB", (320, 240), (10, 20, 30)).save(src, "JPEG", quality=100)
    (tmp_path / "photo_origin.jpg").write_bytes(b"existing backup")
    orig_size = src.stat().st_size

    monkeypatch.setattr("sys.argv", ["compress_images.py", str(src)])
    assert ci.main() == 1
    # source untouched
    assert src.stat().st_size == orig_size


def test_main_single_file_with_explicit_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "photo.jpg"
    Image.new("RGB", (320, 240), (10, 20, 30)).save(src, "JPEG", quality=100)
    out_file = tmp_path / "out" / "tiny.jpg"

    monkeypatch.setattr(
        "sys.argv",
        ["compress_images.py", str(src), "-o", str(out_file)],
    )
    assert ci.main() == 0
    assert out_file.exists()


def test_main_single_file_unsupported_extension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "notes.txt"
    src.write_text("hello")

    monkeypatch.setattr("sys.argv", ["compress_images.py", str(src)])
    assert ci.main() == 1


def test_main_single_file_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "photo.jpg"
    Image.new("RGB", (320, 240), (10, 20, 30)).save(src, "JPEG", quality=100)
    orig_size = src.stat().st_size

    monkeypatch.setattr(
        "sys.argv", ["compress_images.py", str(src), "--dry-run"]
    )
    assert ci.main() == 0
    assert not (tmp_path / "photo_origin.jpg").exists()
    assert src.stat().st_size == orig_size


def test_main_wildcard_expands_and_compresses_each(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    names = ["a.jpg", "b.jpg", "c.jpg"]
    orig_sizes = {}
    for name in names:
        p = tmp_path / name
        img = Image.new("RGB", (400, 400))
        pixels = img.load()
        for x in range(400):
            for y in range(400):
                pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
        img.save(p, "JPEG", quality=100)
        orig_sizes[name] = p.stat().st_size

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["compress_images.py", "*.jpg"])
    assert ci.main() == 0

    for name in names:
        stem = Path(name).stem
        backup = tmp_path / f"{stem}_origin.jpg"
        compressed = tmp_path / name
        assert backup.exists(), f"missing backup for {name}"
        assert backup.stat().st_size == orig_sizes[name]
        assert compressed.exists()
        assert compressed.stat().st_size < orig_sizes[name]


def test_main_multiple_explicit_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    Image.new("RGB", (320, 240), (10, 20, 30)).save(a, "JPEG", quality=100)
    Image.new("RGB", (320, 240), (10, 20, 30)).save(b, "JPEG", quality=100)

    monkeypatch.setattr(
        "sys.argv", ["compress_images.py", str(a), str(b)]
    )
    assert ci.main() == 0
    assert (tmp_path / "a_origin.jpg").exists()
    assert (tmp_path / "b_origin.jpg").exists()


def test_main_wildcard_skips_already_processed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # a.jpg already has a backup (simulating a previous run)
    a = tmp_path / "a.jpg"
    a_origin = tmp_path / "a_origin.jpg"
    Image.new("RGB", (320, 240), (10, 20, 30)).save(a, "JPEG", quality=85)
    Image.new("RGB", (320, 240), (10, 20, 30)).save(a_origin, "JPEG", quality=100)

    # b.jpg is fresh and should get processed
    b = tmp_path / "b.jpg"
    img = Image.new("RGB", (600, 600))
    pixels = img.load()
    for x in range(600):
        for y in range(600):
            pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    img.save(b, "JPEG", quality=100)
    b_orig_size = b.stat().st_size
    a_size_before = a.stat().st_size
    a_origin_size_before = a_origin.stat().st_size

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["compress_images.py", "*.jpg"])
    assert ci.main() == 0

    # a.jpg and a_origin.jpg both untouched
    assert a.stat().st_size == a_size_before
    assert a_origin.stat().st_size == a_origin_size_before

    # b.jpg processed: backup created and original shrunk
    assert (tmp_path / "b_origin.jpg").exists()
    assert (tmp_path / "b_origin.jpg").stat().st_size == b_orig_size
    assert b.stat().st_size < b_orig_size


def test_main_wildcard_all_skipped_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # only an _origin file exists; pattern matches it but it should be skipped
    Image.new("RGB", (100, 100), (10, 20, 30)).save(
        tmp_path / "x_origin.jpg", "JPEG", quality=100
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["compress_images.py", "*.jpg"])
    assert ci.main() == 0


def test_main_wildcard_no_matches_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["compress_images.py", "*.png"])
    assert ci.main() == 1


def test_main_multiple_files_with_output_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    Image.new("RGB", (320, 240), (10, 20, 30)).save(a, "JPEG", quality=100)
    Image.new("RGB", (320, 240), (10, 20, 30)).save(b, "JPEG", quality=100)

    monkeypatch.setattr(
        "sys.argv",
        ["compress_images.py", str(a), str(b), "-o", str(tmp_path / "x.jpg")],
    )
    assert ci.main() == 1


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
