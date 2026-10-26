"""Bounded derivatives of immutable assets; only cache misses read originals."""
from collections import OrderedDict
from concurrent.futures import Future
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from threading import Lock

from PIL import Image, ImageOps, UnidentifiedImageError


@dataclass(frozen=True, slots=True)
class Thumbnail:
    content: bytes
    etag: str


class CachedImageThumbnails:
    VERSION = 1

    def __init__(self, read_verified, *, max_bytes=16 * 1024 * 1024, max_entries=256):
        self.read_verified = read_verified
        self.max_bytes, self.max_entries = max_bytes, max_entries
        self._lock = Lock()
        self._cache = OrderedDict()
        self._pending = {}
        self._bytes = 0

    def get(self, asset_id):
        key = (self.VERSION, asset_id)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            owner = key not in self._pending
            future = self._pending.setdefault(key, Future())
        if not owner:
            return future.result()
        try:
            result = self._make(asset_id)
            with self._lock:
                if len(result.content) <= self.max_bytes and self.max_entries > 0:
                    self._cache[key] = result
                    self._bytes += len(result.content)
                    while self._bytes > self.max_bytes or len(self._cache) > self.max_entries:
                        _, old = self._cache.popitem(last=False)
                        self._bytes -= len(old.content)
                # Publish before clearing the in-flight entry, including uncached results.
                future.set_result(result)
                self._pending.pop(key, None)
            return result
        except BaseException as error:
            with self._lock:
                future.set_exception(error)
                self._pending.pop(key, None)
            raise

    def _make(self, asset_id):
        asset, content = self.read_verified(asset_id)
        if not asset.media_type.startswith("image/"):
            raise ValueError("Cet asset n’est pas une image.")
        try:
            with Image.open(BytesIO(content)) as source:
                preview = ImageOps.exif_transpose(source)
                preview.thumbnail((320, 320), Image.Resampling.LANCZOS)
                preview = preview.convert("RGBA")
                preview.info.clear()  # Do not copy source prompts/metadata into previews.
                output = BytesIO()
                preview.save(output, format="PNG")
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise ValueError("Aperçu indisponible pour cette image.") from error
        encoded = output.getvalue()
        return Thumbnail(encoded, '"' + sha256(encoded).hexdigest() + '"')
