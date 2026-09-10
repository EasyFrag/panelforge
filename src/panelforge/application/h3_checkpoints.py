"""Small cached catalog. Inventory calls neither load weights nor submit a render."""
import time
from threading import RLock
from typing import Callable, Protocol

from panelforge.domain.h3_checkpoint import validate_h3_checkpoint
from panelforge.domain.h3_render import H3RenderInputMode


class H3CheckpointInventory(Protocol):
    def inventory(self, mode: H3RenderInputMode, *, refresh: bool = False) -> dict: ...
    def validate(self, name: str, mode: H3RenderInputMode) -> None: ...


class CachedH3Checkpoints:
    def __init__(self, list_models: Callable[[], tuple[str, ...]], entries: tuple[dict, ...],
                 *, ttl: float = 60, monotonic: Callable[[], float] = time.monotonic):
        self._list_models = list_models
        self._entries = entries
        self._ttl = ttl
        self._clock = monotonic
        self._expires = 0.0
        self._names: set[str] = set()
        self._warning: str | None = None
        self._lock = RLock()
        for entry in entries:
            validate_h3_checkpoint(entry["name"])
            if not entry["modes"] or any(mode not in {"h3-base", "ref2va"} for mode in entry["modes"]):
                raise ValueError("Invalid checkpoint modes")
        if len({e["name"] for e in entries}) != len(entries):
            raise ValueError("Duplicate checkpoint registration")

    @staticmethod
    def _mode(mode):
        return "ref2va" if mode is H3RenderInputMode.REF2VA else "h3-base"

    def inventory(self, mode, *, refresh=False):
        with self._lock:
            if refresh or self._clock() >= self._expires:
                try:
                    names = self._list_models()
                    if not isinstance(names, (list, tuple)) or any(not isinstance(n, str) for n in names):
                        raise ValueError("Inventaire ComfyUI invalide")
                    self._names = {n.replace("\\", "/") for n in names}
                    self._warning = None
                except Exception as error:
                    self._names = set()
                    self._warning = f"Impossible de lire les checkpoints sur ComfyUI : {error}"
                self._expires = self._clock() + (min(self._ttl, 5) if self._warning else self._ttl)
            return {"models": [dict(e) for e in self._entries
                               if self._mode(mode) in e["modes"] and e["name"] in self._names],
                    "warning": self._warning}

    def validate(self, name, mode):
        validate_h3_checkpoint(name)
        if not any(e["name"] == name and self._mode(mode) in e["modes"] for e in self._entries):
            raise ValueError("Checkpoint non enregistré pour ce mode vidéo. Choisissez un modèle compatible.")
        inventory = self.inventory(mode)
        if inventory["warning"]:
            raise ValueError(inventory["warning"])
        if not any(e["name"] == name for e in inventory["models"]):
            raise ValueError(f"Checkpoint absent de ComfyUI : {name}. Actualisez la liste des modèles.")
