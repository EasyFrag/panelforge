"""Bounded Pillow decoding for source-oriented image editing."""

from .krea2_retouch import _read, _png


class PillowEditImages:
    def normalize_source(self, content: bytes) -> bytes:
        # Decode/transpose orientation once, keeping the original asset intact.
        # Resolution reduction still belongs to the versioned Comfy workflow.
        return _png(_read(content, max_pixels=17_000_000))

    def dimensions(self, content: bytes) -> tuple[int, int]:
        # ComfyUI counts a megapixel as 1024² pixels; allow its 16 MP output
        # plus rounding, independently of the retouch tool's source limit.
        return _read(content, max_pixels=17_000_000).size

    def crop(self, content: bytes, *, x: int, y: int, width: int, height: int) -> bytes:
        image = _read(content, max_pixels=17_000_000)
        if (any(type(v) is not int for v in (x, y, width, height))
                or min(x, y) < 0 or min(width, height) < 1
                or x + width > image.width or y + height > image.height):
            raise ValueError("Le rectangle dépasse les limites de l’image.")
        return _png(image.crop((x, y, x + width, y + height)))
