"""Small cached previews; source assets remain immutable."""
from functools import lru_cache
from io import BytesIO
from PIL import Image, ImageOps


class PillowBatchThumbnails:
    def __init__(self, assets):
        self.assets = assets
        self._cached = lru_cache(maxsize=128)(self._render)

    def __call__(self, asset_id, *, size=420):
        if size not in {420, 840}:
            raise ValueError("Taille d’aperçu invalide.")
        return self._cached(asset_id, size)

    def _render(self, asset_id, size):
        with Image.open(BytesIO(self.assets.read_bytes(asset_id))) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((size, size))
            output = BytesIO()
            image.convert("RGB").save(output, format="JPEG", quality=85)
            return output.getvalue()
