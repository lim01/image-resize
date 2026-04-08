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
