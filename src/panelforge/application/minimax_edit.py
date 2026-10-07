"""MiniMax workshop using the same project lifecycle as Qwen."""
from panelforge.domain import minimax_edit as policy
from . import minimax_edit_assistance as assistance
from . import image_journey_reference_prompting as journey_references
from . import image_journey_realistic_prompting as realistic
from panelforge.domain.image_journeys import journey_preset, finished_label
from .qwen_edit import QwenEditService


class MinimaxEditService(QwenEditService):
    def __init__(self, **kwargs):
        super().__init__(policy=policy, prompting=assistance, **kwargs)

    def begin_message(self, project_id, stage_id, *, revision, request_id, render_after_prompt=False):
        with self._lock:
            project, message_id = super().begin_message(project_id, stage_id, revision=revision,
                request_id=request_id, render_after_prompt=render_after_prompt)
            stage = next(s for s in project["stages"] if s["id"] == stage_id)
            message = next(m for m in stage["messages"] if m["id"] == message_id)
            if (project.get("managed_by") == "image-journey" and journey_preset(project) == "realistic"
                    and message["status"] == "queued" and not message.get("journey_realistic_policy")):
                message.update(journey_realistic_policy=realistic.VERSION,
                    policy_version=assistance.VERSION + "+journey-realistic-" + realistic.VERSION,
                    system_prompt=message["system_prompt"] + "\n" + realistic.PROMPTER_SYSTEM)
                self._save(project)
            elif (project.get("managed_by") == "image-journey" and journey_preset(project) != "realistic" and message["status"] == "queued"
                    and not message.get("journey_reference_policy") and journey_references.supports(message["context"])):
                message.update(journey_reference_policy=journey_references.VERSION,
                    policy_version=assistance.VERSION + "+journey-reference-" + journey_references.VERSION,
                    system_prompt=message["system_prompt"] + "\n" + journey_references.SYSTEM)
                self._save(project)
            return project, message_id

    def _decode_message(self, message, raw):
        if message.get("journey_realistic_policy") == realistic.VERSION:
            reply, prompt = realistic.decode_prompt(raw, message["context"])
            return reply, prompt, None
        if message.get("journey_reference_policy") == journey_references.VERSION:
            reply, prompt = journey_references.decode(raw, message["context"])
            return reply, prompt, None
        return super()._decode_message(message, raw)

    def ensure_journey_step(self, step):
        """Idempotent child project sharing the existing prompt and GPU queue services."""
        from .qwen_edit import _now
        identity = policy.journey_child_id(step["id"])
        finished = step.get("finished_reference_asset_id")
        references = []
        if finished and finished != step["source_asset_id"]:
            references = [dict(id="journey-finished", asset_id=finished, name=finished_label(step),
                role="Référence permanente de forme, proportions et matériaux des parties restantes. "
                     "Ne pas rétablir les éléments retirés hors demande explicite ni copier les positions des personnages.",
                usage="render", active=True)]
            if journey_preset(step) == "realistic":
                references[0]["role"] = ("Lieu aménagé terminé : référence des volumes et matières des parties conservées. "
                    "Ne pas restaurer les aménagements retirés, ni copier de personnages. Préserver le lieu qui les accueille.")
        with self._lock:
            try:
                project = self.projects.get(identity)
            except FileNotFoundError:
                project = None
            if project:
                if (project.get("journey_step_id") != step["id"] or project["stages"][0]["source_asset_id"] != step["source_asset_id"]
                        or journey_preset(project) != journey_preset(step)):
                    raise ValueError("Le projet MiniMax ne correspond pas à cette étape du parcours.")
                if finished and project["stages"][0]["references"] != references:
                    raise ValueError("La référence du bâtiment terminé ne correspond plus à cette étape.")
                return project
            source = self.assets.get(step["source_asset_id"])
            if not source.media_type.startswith("image/"):
                raise ValueError("La source du parcours doit être une image.")
            stage = self._new_stage(1, step["source_asset_id"], model_id=step["prompt_model_id"])
            stage["source_dimensions"] = list(self.images.dimensions(self.assets.read_bytes(step["source_asset_id"])))
            profile = step.get('render_profile')
            if profile:
                if stage['source_dimensions'] != profile['dimensions']:
                    raise ValueError('La source ne respecte plus les dimensions fixes du parcours.')
                stage['settings'] = policy.Settings(**{**stage['settings'], **profile['settings']}).record()
            for reference in references:
                if not self.assets.get(reference["asset_id"]).media_type.startswith("image/"):
                    raise ValueError("La référence du bâtiment terminé doit être une image.")
                dimensions = self.images.dimensions(self.assets.read_bytes(reference["asset_id"]))
                if profile and list(dimensions) != profile["dimensions"]:
                    raise ValueError("La référence terminée doit garder les dimensions fixes du parcours.")
            stage["references"] = references
            policy.validate_references(references)
            policy.render_inputs(stage)
            project = dict(schema_version=1, engine=self.engine, id=identity, version=0,
                name=f"Parcours · {step['index']} · {step['action']['title']}"[:120],
                created_at=_now(), updated_at=_now(), active_stage_id=stage["id"], stages=[stage],
                managed_by="image-journey", journey_id=step["journey_id"], journey_step_id=step["id"],
                export_path=None, export_error=None)
            if "journey_preset" in step:
                project["journey_preset"] = journey_preset(step)
            return self._save(project)

    def queue_attempt(self, project_id, stage_id, *, revision, request_id):
        with self._lock:
            project = self.projects.get(project_id)
            stage = next(s for s in project["stages"] if s["id"] == stage_id)
            settings = policy.Settings(**stage["settings"])
            if settings.reference_mode == "native":
                inputs = policy.render_inputs(stage)
                if len(inputs) > 1 and not self.workflow.manifest["capabilities"].get("native_multi_reference"):
                    raise ValueError("Les références natives multiples nécessitent le workflow MiniMax 1.3.0.")
                for reference in inputs:
                    dimensions = self.images.dimensions(self.assets.read_bytes(reference["asset_id"]))
                    if any(v < 64 or v > 4096 or v % 32 for v in dimensions):
                        raise ValueError("Chaque référence native doit être alignée aux dimensions MiniMax.")
            return super().queue_attempt(project_id, stage_id, revision=revision, request_id=request_id)

    def list(self):
        # Managed steps are visible in their journey, not as unrelated manual projects.
        with self._lock:
            managed = {p["id"] for p in self.projects.list() if p.get("managed_by") == "image-journey"}
            return [p for p in super().list() if p["id"] not in managed]
