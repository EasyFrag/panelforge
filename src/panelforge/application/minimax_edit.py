"""MiniMax workshop using the same project lifecycle as Qwen."""
from panelforge.domain import minimax_edit as policy
from . import minimax_edit_assistance as assistance
from .qwen_edit import QwenEditService


class MinimaxEditService(QwenEditService):
    def __init__(self, **kwargs):
        super().__init__(policy=policy, prompting=assistance, **kwargs)

    def ensure_journey_step(self, step):
        """Idempotent child project sharing the existing prompt and GPU queue services."""
        from .qwen_edit import _now
        identity = policy.journey_child_id(step["id"])
        with self._lock:
            try:
                project = self.projects.get(identity)
            except FileNotFoundError:
                project = None
            if project:
                if project.get("journey_step_id") != step["id"] or project["stages"][0]["source_asset_id"] != step["source_asset_id"]:
                    raise ValueError("Le projet MiniMax ne correspond pas à cette étape du parcours.")
                return project
            source = self.assets.get(step["source_asset_id"])
            if not source.media_type.startswith("image/"):
                raise ValueError("La source du parcours doit être une image.")
            stage = self._new_stage(1, step["source_asset_id"], model_id=step["prompt_model_id"])
            stage["source_dimensions"] = list(self.images.dimensions(self.assets.read_bytes(step["source_asset_id"])))
            project = dict(schema_version=1, engine=self.engine, id=identity, version=0,
                name=f"Parcours · {step['index']} · {step['action']['title']}"[:120],
                created_at=_now(), updated_at=_now(), active_stage_id=stage["id"], stages=[stage],
                managed_by="image-journey", journey_id=step["journey_id"], journey_step_id=step["id"],
                export_path=None, export_error=None)
            return self._save(project)

    def list(self):
        # Managed steps are visible in their journey, not as unrelated manual projects.
        with self._lock:
            managed = {p["id"] for p in self.projects.list() if p.get("managed_by") == "image-journey"}
            return [p for p in super().list() if p["id"] not in managed]
