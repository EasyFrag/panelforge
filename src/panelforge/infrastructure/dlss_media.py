"""Bounded local media preparation and metadata/frames for DLSS results."""

from io import BytesIO
import json
import math
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageOps


class DlssMedia:
    def __init__(self, *, ffmpeg, ffprobe):
        self.ffmpeg, self.ffprobe = str(ffmpeg), str(ffprobe)

    def image(self, content):
        if len(content) > 100 * 1024**2:
            raise ValueError("Image DLSS trop volumineuse (100 Mio maximum).")
        with Image.open(BytesIO(content)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"} or getattr(image, "is_animated", False):
                raise ValueError("Choisis une image PNG, JPEG ou WebP fixe.")
            if image.width * image.height > 34_000_000:
                raise ValueError("L’image dépasse la limite de décodage DLSS.")
            return ImageOps.exif_transpose(image).convert("RGB")

    def png(self, content, size=None):
        image = self.image(content)
        if size is not None and image.size != tuple(size):
            image = image.resize(tuple(size), Image.Resampling.LANCZOS)
        stream = BytesIO()
        image.save(stream, format="PNG")
        return stream.getvalue()

    def dimensions(self, content):
        return self.image(content).size

    def _run(self, command, timeout=60):
        try:
            return subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        except subprocess.CalledProcessError as error:
            message = (error.stderr or b"").decode("utf-8", errors="replace")[-2000:]
            raise ValueError("Lecture du média DLSS impossible : " + message) from error
        except subprocess.TimeoutExpired as error:
            raise TimeoutError("La lecture du média DLSS a dépassé son délai.") from error

    def probe(self, content):
        with tempfile.TemporaryDirectory(prefix="panelforge-dlss-") as directory:
            path = Path(directory) / "video.mp4"
            path.write_bytes(content)
            data = json.loads(self._run([self.ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
        video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
        if video is None:
            raise ValueError("Le fichier ne contient pas de vidéo.")
        num, den = map(float, video.get("avg_frame_rate", "0/1").split("/"))
        fps = num / den if den else 0
        duration = float(video.get("duration") or data.get("format", {}).get("duration", 0))
        if not math.isfinite(fps) or fps <= 0 or not math.isfinite(duration) or duration <= 0:
            raise ValueError("Durée ou cadence vidéo indéterminée.")
        return {"width": int(video["width"]), "height": int(video["height"]), "fps": fps, "duration_seconds": duration,
                "audio": any(s["codec_type"] == "audio" for s in data["streams"])}

    def frames(self, content, timestamps):
        with tempfile.TemporaryDirectory(prefix="panelforge-dlss-frames-") as directory:
            path = Path(directory) / "video.mp4"
            path.write_bytes(content)
            results = []
            for milliseconds in timestamps:
                image = self._run([self.ffmpeg, "-v", "error", "-i", str(path), "-ss", f"{milliseconds / 1000:.6f}",
                                   "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "pipe:1"])
                self.dimensions(image)
                results.append(image)
            return results

    def target(self, dimensions, settings, *, video=False, source_size=None):
        width, height = dimensions
        if min(width, height) < 64:
            raise ValueError("DLSS nécessite au moins 64 pixels sur chaque axe.")
        native = (int(math.floor(width * settings.factor / 2 + 0.5)) * 2, int(math.floor(height * settings.factor / 2 + 0.5)) * 2)
        if max(native) > 7680 or min(native) > 4320:
            raise ValueError("La sortie DLSS dépasse 7680 × 4320 (portrait accepté). Choisis un facteur inférieur.")
        final = tuple(source_size) if settings.size == "source" else native
        if not video and final[0] * final[1] > 16_000_000:
            raise ValueError("La sortie dépasse les 16 MP pris en charge par les ateliers image. Choisis un facteur inférieur.")
        return native, final
