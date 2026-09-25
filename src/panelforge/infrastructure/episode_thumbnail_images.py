"""Versioned deterministic lettering; no video, DLSS or generation side effects."""
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from panelforge.domain.episode_thumbnails import GRID_LAYOUT, badge_geometry, cover_format

FONT = Path(__file__).with_name("fonts") / "Outfit.ttf"
LAYOUT = "outfit-cover-v1"
POSTER_LAYOUT = "poster-cover-v2"
POSTER_FONTS = {"pop": FONT, "cinema": FONT.with_name("BarlowCondensed-Black.ttf")}


def _display_font(size, style):
    font = ImageFont.truetype(str(POSTER_FONTS[style]), size)
    if style == "pop":
        font.set_variation_by_axes([900])
    return font


def _title_lines(draw, title, style, max_height=355):
    for size in range(156, 27, -2):
        font, lines = _display_font(size, style), [""]
        for word in title.upper().split():
            candidate = (lines[-1] + " " + word).strip()
            if draw.textlength(candidate, font=font) > 904 and lines[-1]:
                lines.append(word)
            else:
                lines[-1] = candidate
        if len(lines) <= 3 and len(lines) * int(size * 1.1) <= max_height and max(draw.textlength(line, font=font) for line in lines) <= 904:
            return font, lines, int(size * 1.1)
    raise ValueError("Le titre est trop long pour cette affiche. Raccourcis le titre public.")



def _font(size, weight=800):
    font = ImageFont.truetype(str(FONT), size)
    font.set_variation_by_axes([weight])
    return font


def _image(content):
    with Image.open(BytesIO(content)) as source:
        if source.width * source.height > 40_000_000:
            raise ValueError("L’image du modèle dépasse 40 mégapixels.")
        return ImageOps.exif_transpose(source).convert("RGB")


class EpisodeThumbnailImages:
    def normalize(self, content):
        image = _image(content)
        image.thumbnail((3840, 3840), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    def font_bytes(self, style):
        if style not in POSTER_FONTS:
            raise ValueError("Police de miniature inconnue.")
        return POSTER_FONTS[style].read_bytes()

    def render(self, content, *, title, number, title_mode, layout=LAYOUT, title_style="pop", badge_position=None, include_badge=True):
        if layout in {POSTER_LAYOUT, GRID_LAYOUT}:
            return self._poster(content, title=title, number=number, title_mode=title_mode, title_style=title_style,
                                grid=layout == GRID_LAYOUT, badge_position=badge_position, include_badge=include_badge)
        if layout != LAYOUT:
            raise ValueError("Ce gabarit de miniature n’est pas disponible.")
        image = ImageOps.fit(_image(content), (1080, 1920), method=Image.Resampling.LANCZOS).convert("RGBA")
        overlay = Image.new("RGBA", image.size)
        draw = ImageDraw.Draw(overlay)
        for y in range(1250, 1920):
            draw.line((0, y, 1080, y), fill=(10, 17, 27, round(210 * min(1, (y - 1250) / 460))))
        if title_mode == "overlay":
            for y in range(200, 780):
                alpha = round(175 * max(0, 1 - abs(y - 450) / 350))
                draw.line((0, y, 1080, y), fill=(10, 17, 27, alpha))
        image = Image.alpha_composite(image, overlay)
        draw = ImageDraw.Draw(image)
        if title_mode == "overlay":
            words = title.upper().split()
            for size in range(112, 29, -2):
                font, lines = _font(size), [""]
                for word in words:
                    candidate = (lines[-1] + " " + word).strip()
                    if draw.textlength(candidate, font=font) > 900 and lines[-1]:
                        lines.append(word)
                    else:
                        lines[-1] = candidate
                if len(lines) <= 3 and max(draw.textlength(line, font=font) for line in lines) <= 900:
                    break
            else:
                raise ValueError("Le titre est trop long pour ce gabarit. Raccourcis le titre public.")
            for index, line in enumerate(lines):
                draw.text((540, 380 + index * int(size * 1.2)), line, anchor="mt", font=font,
                          fill="white", stroke_width=2, stroke_fill=(10, 17, 27))
        if include_badge:
            geometry = badge_geometry(layout, badge_position)
            self._draw_badge(draw, number, layout, title_style, geometry["x"], geometry["y"])
        output = BytesIO()
        image.convert("RGB").save(output, format="PNG")
        return output.getvalue()


    def _poster(self, content, *, title, number, title_mode, title_style, grid=False, badge_position=None, include_badge=True):
        if title_style not in POSTER_FONTS:
            raise ValueError("Habillage de miniature inconnu.")
        size = cover_format(GRID_LAYOUT if grid else POSTER_LAYOUT)
        image = ImageOps.fit(_image(content), (size["width"], size["height"]), method=Image.Resampling.LANCZOS).convert("RGBA")
        overlay = Image.new("RGBA", image.size)
        draw = ImageDraw.Draw(overlay)
        bottom_start, bottom_fade = (1080, 260) if grid else (1480, 340)
        for y in range(bottom_start, image.height):
            draw.line((0, y, 1080, y), fill=(10, 17, 27, round(180 * min(1, (y - bottom_start) / bottom_fade))))
        if title_mode == "overlay":
            top_start, top_end, center, fade = (60, 490, 260, 240) if grid else (140, 730, 420, 320)
            for y in range(top_start, top_end):
                alpha = round(185 * max(0, 1 - abs(y - center) / fade))
                draw.line((0, y, 1080, y), fill=(10, 17, 27, alpha))
        image = Image.alpha_composite(image, overlay)
        draw = ImageDraw.Draw(image)
        if title_mode == "overlay":
            title_top, title_height = (130, 285) if grid else (240, 355)
            font, lines, spacing = _title_lines(draw, title, title_style, max_height=title_height)
            y = title_top + (title_height - len(lines) * spacing) // 2
            for line in lines:
                if title_style == "pop":
                    draw.text((548, y + 10), line, anchor="mt", font=font, fill="#e5ff73", stroke_width=9, stroke_fill="#132527")
                    draw.text((540, y), line, anchor="mt", font=font, fill="#fffdf2", stroke_width=7, stroke_fill="#132527")
                else:
                    draw.text((545, y + 8), line, anchor="mt", font=font, fill="#ae6b28", stroke_width=6, stroke_fill="#191e27")
                    draw.text((540, y), line, anchor="mt", font=font, fill="#fff1d3", stroke_width=3, stroke_fill="#191e27")
                y += spacing
        if include_badge:
            layout = GRID_LAYOUT if grid else POSTER_LAYOUT
            geometry = badge_geometry(layout, badge_position)
            self._draw_badge(draw, number, layout, title_style, geometry["x"], geometry["y"])
        output = BytesIO()
        image.convert("RGB").save(output, format="PNG")
        return output.getvalue()


    @staticmethod
    def _draw_badge(draw, number, layout, title_style, x, y):
        if layout == LAYOUT:
            draw.rounded_rectangle((x, y, x + 850, y + 225), radius=40, fill=(244, 255, 168))
            draw.text((x + 45, y + 55), "ÉPISODE", font=_font(56, 700), fill=(12, 26, 27), anchor="lt")
            size = 156 if number < 100 else 124 if number < 1000 else 100
            draw.text((x + 805, y + 30), f"{number:02d}", font=_font(size, 900), fill=(12, 26, 27), anchor="rt")
        else:
            accent = "#e5ff73" if title_style == "pop" else "#fff1d3"
            draw.rounded_rectangle((x, y, x + 500, y + 160), radius=28, fill=accent)
            draw.text((x + 36, y + 55), "ÉPISODE", font=_font(38, 800), fill="#132527", anchor="lt")
            size = 116 if number < 100 else 92 if number < 1000 else 76
            draw.text((x + 465, y + 25), f"{number:02d}", font=_font(size, 900), fill="#132527", anchor="rt")

    def badge(self, *, number, layout, title_style="pop"):
        geometry = badge_geometry(layout)
        image = Image.new("RGBA", (geometry["width"], geometry["height"]))
        self._draw_badge(ImageDraw.Draw(image), number, layout, title_style, 0, 0)
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()
