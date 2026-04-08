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
