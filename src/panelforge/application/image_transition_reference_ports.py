"""Image preparation port for deterministic, inspectable scale references."""
from typing import Protocol


class TransitionReferenceImages(Protocol):
    def normalize_worker(self, content: bytes) -> tuple[bytes, tuple[int, int]]: ...
    def compose(self, scene_content: bytes, worker_content: bytes,
                position: dict) -> tuple[bytes, tuple[int, int]]: ...
