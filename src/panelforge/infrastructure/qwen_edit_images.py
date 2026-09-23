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

    def normalize_mask(self, content, dimensions):
        mask = _read(content, mask=True, max_pixels=17_000_000)
        if mask.size != tuple(dimensions):
            raise ValueError("Le guide doit avoir exactement les dimensions de l’image source.")
        if not mask.getbbox():
            raise ValueError("Peins au moins une zone avant d’enregistrer le guide.")
        return _png(mask)

    def prepare_guide(self, source, mask, dimensions):
        """Embed coverage in inverse alpha, matching ComfyUI LoadImage's mask output."""
        image = _read(source, max_pixels=17_000_000)
        coverage = _read(mask, mask=True, max_pixels=17_000_000)
        if coverage.size != image.size:
            raise ValueError("Le guide ne correspond plus à l’image source.")
        if image.size != tuple(dimensions):
            image = image.resize(dimensions, Image.Resampling.LANCZOS)
            coverage = coverage.resize(dimensions, Image.Resampling.LANCZOS)
        image.putalpha(coverage.point(lambda value: 255 - value))
        return _png(image)
