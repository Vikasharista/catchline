import base64
import io
from pathlib import Path

from PIL import ExifTags, Image

from app.ingest.router import Chunk, IngestedDoc


def _fix_exif_rotation(image: Image.Image) -> Image.Image:
    try:
        exif = image.getexif()
        orientation_key = next(k for k, v in ExifTags.TAGS.items() if v == "Orientation")
        orientation = exif.get(orientation_key)
    except (AttributeError, KeyError, StopIteration):
        return image

    rotations = {3: 180, 6: 270, 8: 90}
    if orientation in rotations:
        image = image.rotate(rotations[orientation], expand=True)
    return image


def ingest(path: Path) -> IngestedDoc:
    image = Image.open(path)
    image = _fix_exif_rotation(image)

    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    chunk = Chunk(kind="image", content=b64, locator="image")
    return IngestedDoc(filename=path.name, kind="image", chunks=[chunk])
