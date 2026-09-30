"""CPU-only scale mock-ups; originals and renderer inputs are never overwritten."""
from PIL import Image
from .krea2_retouch import _read, _png
from panelforge.domain.image_transition_references import placement


class PillowTransitionReferences:
    def normalize_worker(self, content):
        image = _read(content, max_pixels=17_000_000)
        bounds = image.getchannel("A").getbbox()
        if not bounds:
            raise ValueError("L’image de l’ouvrier est entièrement transparente.")
        image = image.crop(bounds)
        image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
        return _png(image), image.size

    def compose(self, scene_content, worker_content, position):
        scene = _read(scene_content, max_pixels=17_000_000)
        worker = _read(worker_content, max_pixels=17_000_000)
        position = placement(position, scene.size, worker.size)
        height = max(1, round(scene.height * position["height"]))
        width = max(1, round(worker.width * height / worker.height))
        worker = worker.resize((width, height), Image.Resampling.LANCZOS)
        left = max(0, min(scene.width - width, round(position["x"] * scene.width - width / 2)))
        top = max(0, min(scene.height - height, round(position["y"] * scene.height - height)))
        scene.alpha_composite(worker, (left, top))
        return _png(scene), scene.size
