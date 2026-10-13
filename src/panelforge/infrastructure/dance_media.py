"""CPU-only media preparation, without loading a generation model."""
from pathlib import Path
import io
import json
import math
import subprocess
import tempfile
from threading import BoundedSemaphore
from PIL import Image, ImageOps, UnidentifiedImageError

from panelforge.domain.dance import excerpt_frames


class DanceMedia:
    def __init__(self, *, ffmpeg, ffprobe):
        self.ffmpeg, self.ffprobe = Path(ffmpeg), Path(ffprobe)
        self._slots = BoundedSemaphore(1)

    @property
    def available(self):
        return self.ffmpeg.is_file() and self.ffprobe.is_file()

    def _run(self, args, *, timeout=120):
        try:
            result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=timeout,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except subprocess.TimeoutExpired as error:
            raise ValueError('La préparation du média a dépassé le délai prévu. Essayez un extrait plus court.') from error
        if result.returncode:
            raise ValueError('Lecture ou préparation du média impossible. Vérifiez le fichier vidéo.')
        return result.stdout

    def _probe(self, path):
        if not self.available:
            raise ValueError('FFmpeg et FFprobe sont nécessaires pour préparer les extraits de danse.')
        data = json.loads(self._run([str(self.ffprobe), '-v', 'error', '-show_streams',
                                    '-show_format', '-of', 'json', str(path)], timeout=30))
        video = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
        if video is None:
            raise ValueError('Ce fichier ne contient pas de vidéo.')
        duration = float(data.get('format', {}).get('duration', 0))
        if not math.isfinite(duration) or duration <= 0 or int(video['width']) * int(video['height']) > 40_000_000:
            raise ValueError('Durée ou dimensions de la vidéo invalides.')
        return {'duration_seconds': duration,
                'width': int(video['width']), 'height': int(video['height']),
                'has_audio': any(s.get('codec_type') == 'audio' for s in data['streams'])}

    def inspect(self, content):
        with tempfile.TemporaryDirectory(prefix='panelforge-dance-') as temp:
            path = Path(temp) / 'source.mp4'; path.write_bytes(content)
            return self._probe(path)

    def prepare(self, content, *, start, duration):
        if not self._slots.acquire(blocking=False):
            raise ValueError('Un extrait est déjà en préparation. Réessayez après sa fin.')
        try:
            with tempfile.TemporaryDirectory(prefix='panelforge-dance-') as temp:
                source, target = Path(temp) / 'source.mp4', Path(temp) / 'clip.mp4'
                source.write_bytes(content); info = self._probe(source)
                frames = excerpt_frames(start, duration, info['duration_seconds'])
                seconds = frames / 24
                filters = "fps=24,scale=w='min(1280,iw)':h='min(1280,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1"
                self._run([str(self.ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error',
                           '-threads', '2', '-filter_threads', '2', '-ss', str(start), '-i', str(source), '-t', str(seconds),
                           '-map', '0:v:0', '-map', '0:a:0?', '-vf', filters, '-frames:v', str(frames),
                           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
                           '-threads', '2', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(target)])
                return target.read_bytes(), {**info, 'frame_count': frames, 'duration_seconds': seconds}
        finally:
            self._slots.release()

    @staticmethod
    def image(content):
        if len(content) > 32 * 1024 * 1024:
            raise ValueError('Image trop volumineuse (32 Mio maximum).')
        try:
            with Image.open(io.BytesIO(content)) as source:
                if source.width * source.height > 40_000_000:
                    raise ValueError('Image trop grande.')
                result = ImageOps.exif_transpose(source).convert('RGB')
                result.thumbnail((4096, 4096))
                output = io.BytesIO(); result.save(output, format='PNG')
                return output.getvalue()
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as error:
            raise ValueError('Cette image ne peut pas être lue. Utilisez une image PNG, JPEG ou WebP valide.') from error

    def finish(self, video, clip, *, duration, keep_audio):
        with tempfile.TemporaryDirectory(prefix='panelforge-dance-finish-') as temp:
            source, reference, target = (Path(temp) / n for n in ('render.mp4', 'clip.mp4', 'result.mp4'))
            source.write_bytes(video); reference.write_bytes(clip)
            args = [str(self.ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error',
                    '-i', str(source), '-i', str(reference), '-map', '0:v:0']
            args += ['-map', '1:a:0', '-c:a', 'copy'] if keep_audio else ['-an']
            self._run(args + ['-c:v', 'copy', '-t', str(duration), '-movflags', '+faststart', str(target)])
            return target.read_bytes()
