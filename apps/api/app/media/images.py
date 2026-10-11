"""Decode bounded still images, strip metadata, and re-encode trusted JPEGs."""

import warnings
from io import BytesIO
from threading import BoundedSemaphore

from app.errors import problem
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 2 * 1024 * 1024
decode_slots = BoundedSemaphore(2)


def jpeg(
    data: bytes, output, size=(960, 960), *, max_bytes=MAX_IMAGE_BYTES, max_dimension=4096, max_pixels=4096**2
):
    if len(data) > max_bytes:
        problem(413, "IMAGE_TOO_LARGE", f"画像は{max_bytes // (1024 * 1024)} MB以下で選んでください。")
    if not decode_slots.acquire(blocking=False):
        problem(429, "IMAGE_BUSY", "画像を準備中です。少し待ってからお試しください。")
    try:
        _jpeg(data, output, size, max_dimension, max_pixels)
    finally:
        decode_slots.release()


def _jpeg(data, output, size, max_dimension, max_pixels):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"} or getattr(image, "n_frames", 1) != 1:
                    raise ValueError()
                if (
                    not 1 <= image.width <= max_dimension
                    or not 1 <= image.height <= max_dimension
                    or image.width * image.height > max_pixels
                ):
                    raise ValueError()
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail(size)
                image.save(output, format="JPEG", quality=85, optimize=True)
    except (
        ValueError,
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        problem(
            415, "INVALID_IMAGE", f"JPEG・PNG・WebPの静止画像（縦横{max_dimension}px以内）を選んでください。"
        )


def read_upload(file, max_bytes=MAX_IMAGE_BYTES):
    return file.file.read(max_bytes + 1)
