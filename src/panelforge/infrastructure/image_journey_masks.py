"""Rasterize semantic contours and preserve source pixels outside the soft mask."""
from dataclasses import dataclass

from panelforge.domain.image_journey_masks import validate_plan
from .krea2_retouch import PillowRetouchCompositor, _read, _png


@dataclass(frozen=True)
class ProtectedImage:
    image_png: bytes
    mask_png: bytes
    coverage: float


class PillowJourneyMasks:
    def compose(self, source, generated, plan):
        from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

        validate_plan(plan)
        before, after = _read(source), _read(generated)
        if before.size != after.size:
            raise ValueError('La protection du décor nécessite une source et un rendu de mêmes dimensions.')
        width, height = before.size
        mask = Image.new('L', before.size, 0)

        def pixels(points):
            return [(round(p['x'] * (width - 1) / 1000), round(p['y'] * (height - 1) / 1000)) for p in points]

        for region in plan['regions']:
            layer = Image.new('L', before.size, 0)
            draw = ImageDraw.Draw(layer)
            draw.polygon(pixels(region['outline']), fill=255)
            for hole in region['holes']:
                draw.polygon(pixels(hole), fill=0)
            mask = ImageChops.lighter(mask, layer)
        # Small bounded seam; GaussianBlur produces a finite 8-bit support, leaving true zeros.
        margin = max(1, min(12, round(min(before.size) * 0.003)))
        mask = mask.filter(ImageFilter.MaxFilter(2 * margin + 1)).filter(ImageFilter.GaussianBlur(margin))
        coverage = ImageStat.Stat(mask).mean[0] / 255
        result = PillowRetouchCompositor().compose(source, generated, _png(mask))
        return ProtectedImage(result.output_png, result.mask_png, coverage)
