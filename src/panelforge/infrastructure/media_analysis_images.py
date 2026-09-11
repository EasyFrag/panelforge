"""Decode image evidence and prepare bounded, oriented vision inputs."""
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError


class MediaAnalysisImages:
    def prepare(self, content: bytes) -> tuple[str, bytes]:
        try:
            with Image.open(BytesIO(content)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"} or getattr(source, "is_animated", False):
                    raise ValueError("Utilisez une image PNG, JPEG ou WebP fixe.")
                if source.width * source.height > 40_000_000:
                    raise ValueError("L’image dépasse 40 mégapixels.")
                media_type = Image.MIME[source.format]
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
                output = BytesIO()
                image.save(output, format="JPEG", quality=90)
                return media_type, output.getvalue()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise ValueError("Image illisible ou trop grande.") from error
