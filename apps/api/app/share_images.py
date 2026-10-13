"""Small, metadata-free JPEGs carried as data, never external image URLs."""

import base64
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, UnidentifiedImageError

from app.media.images import jpeg
from app.storage.service import storage


def validate_image(value):
    if value is None:
        return value
    try:
        data = base64.b64decode(value, validate=True)
        if len(data) > 48 * 1024:
            raise ValueError()
        with Image.open(BytesIO(data)) as image:
            if (
                image.format != "JPEG"
                or getattr(image, "n_frames", 1) != 1
                or not (0 < image.width <= 640 and 0 < image.height <= 640)
            ):
                raise ValueError()
            image.load()
    except (ValueError, OSError, UnidentifiedImageError):
        raise ValueError("Invalid shared JPEG") from None
    return value


def portable_image_data(data):
    try:
        with TemporaryDirectory(prefix="lumvia-share-image-") as directory:
            output = Path(directory) / "small.jpg"
            jpeg(data, output, size=(640, 640), max_bytes=2 * 1024**2)
            with Image.open(output) as image:
                image.thumbnail((480, 480))
                stream = BytesIO()
                image.convert("RGB").save(stream, format="JPEG", quality=65)
            data = stream.getvalue()
            if len(data) > 48 * 1024:
                return None
            return base64.b64encode(data).decode("ascii")
    except (OSError, UnidentifiedImageError):
        return None


def portable_image(key):
    if not key:
        return None
    try:
        with storage.materialize(key) as path:
            return portable_image_data(path.read_bytes())
    except OSError:
        return None


def clean_image(value):
    with TemporaryDirectory(prefix="lumvia-share-image-") as directory:
        output = Path(directory) / "image.jpg"
        jpeg(base64.b64decode(value, validate=True), output, size=(640, 640))
        return output.read_bytes()
