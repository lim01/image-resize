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
