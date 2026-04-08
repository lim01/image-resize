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
