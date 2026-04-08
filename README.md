# image-resize

Recursively compress JPEG/PNG/WebP images in a folder without changing dimensions.

Managed with [uv](https://docs.astral.sh/uv/).

## Install

```bash
uv sync
```

## Usage

```bash
uv run python compress_images.py <input_dir> [-o <output_dir>] [-q 85] [--dry-run] [-v]
```

Default output folder: `<input_dir>_compressed`.

## Test

```bash
uv run pytest -v
```
