"""CPU image preparation, with the same orientation and bounds as the mask editor."""

from panelforge.application.krea2_edit_upscale import UpscaleInput
from .krea2_retouch import _read, _png


class PillowUpscaleImages:
    def prepare(self, source: bytes, generated: bytes) -> UpscaleInput:
        before, after = _read(source), _read(generated)
        if abs((after.width * before.height) / (after.height * before.width) - 1) > 0.01 + 1e-12:
            raise ValueError("Les proportions diffèrent de plus de 1 %. Choisis un rendu au même ratio que la source.")
        # Preserve the native generation resolution before neural upscaling.
        return UpscaleInput(_png(after), before.width, before.height)

    def normalize_output(self, content: bytes, width: int, height: int) -> bytes:
        image = _read(content)
        if image.size != (width, height):
            raise ValueError("L’upscaler n’a pas renvoyé les dimensions de la source.")
        return _png(image)
