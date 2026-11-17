import io
import warnings
from pathlib import Path, PurePosixPath
from uuid import uuid4

from ..runtime import settings
from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import ImageTooLarge, InvalidImage, UnsupportedMediaType
from .timeutil import today_local

ALLOWED = {'image/jpeg': 'JPEG', 'image/png': 'PNG', 'image/webp': 'WEBP'}


def save_upload(file_storage):
    maximum = settings()['UPLOAD_MAX_BYTES']
    raw = file_storage.stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ImageTooLarge('Image exceeds the configured upload limit.')
    if file_storage.mimetype not in ALLOWED:
        raise UnsupportedMediaType('Only JPEG, PNG and WebP are allowed.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as original:
                if original.format != ALLOWED[file_storage.mimetype]:
                    raise InvalidImage('Image content does not match its media type.')
                original.verify()
            with Image.open(io.BytesIO(raw)) as original:
                original.load()
                image = ImageOps.exif_transpose(original).convert('RGB')
                side = settings()['UPLOAD_MAX_SIDE']
                image.thumbnail((side, side))
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise InvalidImage('The uploaded file is not a valid supported image.') from None
    year, month, _ = today_local().split('-')
    relative = PurePosixPath('uploads', year, month, uuid4().hex + '.jpg')
    destination = Path(settings()['UPLOAD_ROOT']) / str(relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # A new RGB image avoids copying EXIF or other source metadata.
    clean = Image.new('RGB', image.size)
    clean.paste(image)
    try:
        clean.save(destination, format='JPEG', quality=85, optimize=True)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return relative.as_posix()


def is_safe_image_path(rel_path):
    if not isinstance(rel_path, str) or '\\' in rel_path or ':' in rel_path or '\x00' in rel_path:
        return False
    parts = rel_path.split('/')
    if len(parts) < 2 or parts[0] != 'uploads' or any(p in ('', '.', '..') for p in parts):
        return False
    root = (Path(settings()['UPLOAD_ROOT']) / 'uploads').resolve()
    try:
        target = (Path(settings()['UPLOAD_ROOT']) / rel_path).resolve()
        return target.is_relative_to(root) and target.is_file()
    except (OSError, ValueError):
        return False
