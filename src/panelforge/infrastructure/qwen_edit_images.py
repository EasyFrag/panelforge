"""Prepare oriented references at bounded, explicit multiples of 32."""

from PIL import Image
from .krea2_retouch import _read, _png


class PillowQwenEditImages:
    def normalize_source(self, content):
        return _png(_read(content, max_pixels=17_000_000))

    def dimensions(self, content):
        return _read(content, max_pixels=17_000_000).size

    def prepare(self, content, dimensions):
        image = _read(content, max_pixels=17_000_000)
        if image.size != dimensions:
            image = image.resize(dimensions, Image.Resampling.LANCZOS)
        return _png(image)
