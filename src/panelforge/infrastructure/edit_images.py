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
