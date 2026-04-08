"""Tests for compress_images.py."""
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
