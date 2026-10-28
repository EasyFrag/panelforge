"""Shared still-image LoRA catalogue and submission guard, without GPU work."""
from threading import RLock
from time import monotonic

from panelforge.domain.minimax_loras import MAX_LORAS
from panelforge.domain.h3_render import canonical_h3_video_lora_name


class MinimaxLoraSupport:
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._lora_inventory_lock = RLock()
        self._lora_inventory = None
        self._lora_inventory_expires = 0.0

    def lora_inventory(self, *, refresh=False):
        # Explicit ComfyUI inventory, never a local filesystem scan or a render poll.
        with self._lora_inventory_lock:
            if not refresh and self._lora_inventory is not None and monotonic() < self._lora_inventory_expires:
                return dict(self._lora_inventory)
            warning, models = None, {}
            try:
                raw_models = self.comfy.list_lora_models()
                if not isinstance(raw_models, (list, tuple)):
                    raise ValueError("Réponse de catalogue invalide.")
                for raw in raw_models:
                    try:
                        name = canonical_h3_video_lora_name(raw)
                    except (TypeError, ValueError):
                        continue
                    models.setdefault(name.casefold(), name)
            except Exception:
                warning = "Catalogue LoRA MiniMax indisponible. Actualise pour réessayer."
            self._lora_inventory = dict(models=sorted(models.values(), key=str.casefold),
                warning=warning, maximum=MAX_LORAS,
                supported=bool(self.workflow.manifest.get("lora_slots")))
            self._lora_inventory_expires = monotonic() + (5 if warning else 60)
            return dict(self._lora_inventory)

    def queue_attempt(self, project_id, stage_id, *, revision, request_id):
        with self._lock:
            project = self.projects.get(project_id)
            stage = self._editable(project, stage_id)
            # Retrying an acknowledged request must not depend on catalogue availability.
            if not any(a["request_id"] == request_id for a in stage["attempts"]):
                self._editable(project, stage_id, revision)
                active = self.policy.Settings(**stage["settings"]).active_loras
                if active:
                    if not self.workflow.manifest.get("lora_slots"):
                        raise ValueError("Ce workflow MiniMax ne prend pas en charge les LoRA image.")
                    catalogue = self.lora_inventory()
                    if catalogue["warning"]:
                        raise ValueError(catalogue["warning"])
                    missing = [entry.name for entry in active if entry.name not in catalogue["models"]]
                    if missing:
                        raise ValueError("LoRA indisponible dans ComfyUI : " + ", ".join(missing)
                            + ". Actualise le catalogue ou désactive ce LoRA.")
            return super().queue_attempt(project_id, stage_id, revision=revision, request_id=request_id)
