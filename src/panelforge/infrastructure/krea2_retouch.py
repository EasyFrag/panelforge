"""Bounded CPU-only composition; never invokes a renderer or modifies an original."""

from io import BytesIO

from panelforge.application.krea2_retouch import ComposedRetouch, PreparedRetouch
from panelforge.domain.krea2_edit import validate_retouch_harmonization


MAX_BYTES = 25 * 1024 * 1024
MAX_PIXELS = 16_000_000


def _pillow():
    try:
        from PIL import Image, ImageOps
    except ImportError as error:
        raise ValueError("Pillow est nécessaire pour la retouche. Installer les dépendances du projet.") from error
    return Image, ImageOps


def _read(content: bytes, *, mask: bool = False, max_pixels: int = MAX_PIXELS):
    Image, ImageOps = _pillow()
    if not isinstance(content, bytes) or not content or len(content) > MAX_BYTES:
        raise ValueError("Image ou masque vide, ou supérieur à 25 Mio.")
    try:
        with Image.open(BytesIO(content), formats=("PNG",) if mask else ("PNG", "JPEG", "WEBP")) as image:
            if image.width * image.height > max_pixels:
                raise ValueError(f"L’image dépasse la limite de {max_pixels / 1_000_000:g} MP décodés.")
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("La retouche nécessite une image fixe.")
            if mask:
                # Browser brush canvas: white RGB, coverage in alpha. Saved masks: L.
                if image.mode not in {"L", "RGBA"}:
                    raise ValueError("Le masque doit être un PNG gris ou RGBA (couverture dans l’alpha).")
                if image.getexif().get(274, 1) != 1:
                    raise ValueError("Le masque ne doit pas contenir de rotation EXIF.")
                result = image.getchannel("A") if image.mode == "RGBA" else image.copy()
            else:
                result = ImageOps.exif_transpose(image).convert("RGBA")
            result.load()
            # Canonical untagged 8-bit RGBA/gray, identical inputs for Canvas and export.
            result.info.clear()
            return result
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError("Image ou masque invalide pour la retouche.") from error


def _png(image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class PillowRetouchCompositor:
    def _harmonized(self, before, after):
        # Reinhard mean/std transfer in encoded Lab, using Pillow's local LittleCMS.
        # Intensity is subsequently mixed in RGBA8, identically to the browser.
        from PIL import Image, ImageCms, ImageStat

        rgb, lab = ImageCms.createProfile("sRGB"), ImageCms.createProfile("LAB")
        to_lab = ImageCms.buildTransformFromOpenProfiles(rgb, lab, "RGB", "LAB")
        to_rgb = ImageCms.buildTransformFromOpenProfiles(lab, rgb, "LAB", "RGB")
        reference = ImageCms.applyTransform(before.convert("RGB"), to_lab)
        target = ImageCms.applyTransform(after.convert("RGB"), to_lab)
        reference_stats, target_stats = ImageStat.Stat(reference), ImageStat.Stat(target)
        channels = []
        for index, channel in enumerate(target.split()):
            deviation = target_stats.stddev[index]
            gain = reference_stats.stddev[index] / deviation if deviation > 1e-6 else 1.0
            offset = reference_stats.mean[index] - target_stats.mean[index] * gain
            lut = [max(0, min(255, int(value * gain + offset + 0.5))) for value in range(256)]
            channels.append(channel.point(lut))
        corrected = ImageCms.applyTransform(Image.merge("LAB", channels), to_rgb).convert("RGBA")
        corrected.putalpha(after.getchannel("A"))
        corrected.info.clear()
        return corrected

    def _pair(self, source: bytes, generated: bytes):
        Image, _ = _pillow()
        before, after = _read(source), _read(generated)
        ratio_error = abs((after.width * before.height) / (after.height * before.width) - 1)
        if ratio_error > 0.01 + 1e-12:
            raise ValueError("Les proportions diffèrent de plus de 1 %. Choisis un rendu au même ratio que la source.")
        if after.size != before.size:
            after = after.resize(before.size, resample=Image.Resampling.LANCZOS)
        return before, after

    def prepare(self, source: bytes, generated: bytes) -> PreparedRetouch:
        before, after = self._pair(source, generated)
        return PreparedRetouch(_png(before), _png(after), *before.size, _png(self._harmonized(before, after)))

    def compose(self, source: bytes, generated: bytes, mask: bytes, *,
                harmonize: bool = False, harmonize_strength: int = 100) -> ComposedRetouch:
        validate_retouch_harmonization(harmonize, harmonize_strength)
        Image, _ = _pillow()
        before, after = self._pair(source, generated)
        coverage = _read(mask, mask=True)
        if coverage.size != before.size:
            raise ValueError("Le masque doit avoir exactement les dimensions de la source.")
        if harmonize and harmonize_strength:
            level = (harmonize_strength * 255 + 50) // 100
            after = Image.composite(self._harmonized(before, after), after, Image.new("L", before.size, level))
        result = Image.composite(after, before, coverage)
        return ComposedRetouch(_png(coverage), _png(result), *before.size)
