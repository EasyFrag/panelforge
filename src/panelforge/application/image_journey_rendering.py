"""Small adapter to the existing MiniMax prompter and scheduled render lifecycle."""
from copy import deepcopy
from panelforge.domain.image_journey_masks import dimensions_3mp
from panelforge.domain.minimax_edit import MinimaxEditSettings, journey_child_id
from .image_journey_policies import edit_request


class MinimaxJourneyRenderer:
    def __init__(self, minimax):
        self.minimax = minimax

    def prepare_source(self, content, *, journey_direction="forward"):
        """Capture the fixed 3 MP / 18-step native-reference profile once per journey."""
        if not self.minimax.workflow.manifest['capabilities'].get('native_reference'):
            raise ValueError('Les nouveaux parcours nécessitent le workflow MiniMax 1.2.0.')
        if (journey_direction == "reverse"
                and not self.minimax.workflow.manifest['capabilities'].get('native_multi_reference')):
            raise ValueError('Le parcours à rebours nécessite le workflow MiniMax 1.3.0.')
        dimensions = dimensions_3mp(self.minimax.images.dimensions(content))
        prepared = self.minimax.images.prepare_fixed_source(content, dimensions)
        return prepared, dict(id='fixed-3mp-v1', dimensions=list(dimensions),
            settings=dict(resolution='source', reference_mode='native', steps=18))

    def _stage(self, step):
        project = self.minimax.ensure_journey_step(step)
        stage = project["stages"][0]
        if stage["source_asset_id"] != step["source_asset_id"]:
            raise ValueError("La source MiniMax ne correspond plus à cette étape du parcours.")
        return project, stage

    def prepare(self, step):
        project, stage = self._stage(step)
        message = next((m for m in stage["messages"] if m["request_id"] == step["prompt_request_id"]), None)
        if message is None:
            project = self.minimax.update(project["id"], stage["id"], revision=stage["revision"],
                changes=dict(draft=edit_request(step), model_id=step["prompt_model_id"]))
            stage = project["stages"][0]
            _, message_id = self.minimax.begin_message(project["id"], stage["id"], revision=stage["revision"],
                request_id=step["prompt_request_id"], render_after_prompt=False)
        else:
            message_id = message["id"]
        # Exactly one prompter call. The journey separately queues rendering after a pause check.
        self.minimax.execute_message(project["id"], stage["id"], message_id)
        project = self.minimax.get(project["id"])
        stage = project["stages"][0]
        message = next(m for m in stage["messages"] if m["id"] == message_id)
        if message["status"] != "succeeded" or not message.get("applied"):
            raise ValueError(message.get("error") or "Le prompt MiniMax n’a pas pu être appliqué.")
        return dict(prompt=message["prompt"], prompt_policy_version=message["policy_version"],
                    message_id=message_id, call_id=message.get("call_id"),
                    minimax_project_id=project["id"], minimax_stage_id=stage["id"])

    def queue(self, step):
        project, stage = self._stage(step)
        if stage["prompt"] != step["prompt"]:
            raise ValueError("Le prompt MiniMax a changé en dehors du parcours.")
        project = self.minimax.queue_attempt(project["id"], stage["id"], revision=stage["revision"],
                                             request_id=step["render_request_id"])
        return next(a for a in project["stages"][0]["attempts"] if a["request_id"] == step["render_request_id"])

    def result(self, step):
        project, stage = self._stage(step)
        return next((a for a in stage["attempts"] if a["request_id"] == step["render_request_id"]), None)

    def retry_failed(self, step):
        from panelforge.domain.image_journeys import identity
        project, stage = self._stage(step)
        changes = {}
        message = next((m for m in stage["messages"] if m["request_id"] == step["prompt_request_id"]), None)
        attempt = next((a for a in stage["attempts"] if a["request_id"] == step["render_request_id"]), None)
        if message and message["status"] == "failed":
            changes["prompt_request_id"] = identity("prompt")
        if attempt and attempt["status"] in {"failed", "cancelled"}:
            changes["render_request_id"] = identity("render")
        return changes

    def comparison_snapshot(self, step, reference_megapixels):
        """Use the executed attempt, never the current editable prompt/settings."""
        MinimaxEditSettings(reference_megapixels=reference_megapixels)
        original = self.minimax.get(step["minimax_project_id"])
        stage = next(s for s in original["stages"] if s["id"] == step["minimax_stage_id"])
        attempt = next(a for a in stage["attempts"] if a["id"] == step["attempt_id"])
        if attempt["status"] != "succeeded" or not attempt.get("output_asset_id"):
            raise ValueError("Choisis une édition terminée pour la comparer.")
        context = attempt["context"]
        inputs = context["render_inputs"]
        if (context["mode"] != "edit" or context.get("guide") or len(inputs) != 1
                or inputs[0]["asset_id"] != step["source_asset_id"]
                or attempt["output_asset_id"] != step["output_asset_id"]):
            raise ValueError("Cette édition ne peut pas être comparée avec une référence unique.")
        if attempt["recipe"]["workflow_sha256"] != self.minimax.workflow.reference.workflow_sha256:
            raise ValueError("Le moteur a changé depuis cette édition ; une comparaison à paramètres égaux est impossible.")
        if "reference_megapixels" not in self.minimax.workflow.manifest["inputs"]:
            raise ValueError("La comparaison sera disponible après le prochain démarrage de PanelForge.")
        settings = MinimaxEditSettings(**attempt["settings"])
        source_dimensions = self.minimax.images.dimensions(self.minimax.assets.read_bytes(step["source_asset_id"]))
        if list(settings.dimensions(source_dimensions)) != attempt["dimensions"]:
            raise ValueError("Les dimensions de cette édition ne peuvent pas être reproduites à l’identique.")
        values = settings.record()
        values.update(reference_megapixels=reference_megapixels, reuse_seed=True)
        return dict(source_asset_id=step["source_asset_id"], source_dimensions=list(source_dimensions),
            baseline_asset_id=attempt["output_asset_id"], baseline_attempt_id=attempt["id"],
            baseline_reference_megapixels=settings.reference_megapixels, baseline_recipe=deepcopy(attempt["recipe"]),
            prompt=attempt["prompt"], settings=values, dimensions=list(attempt["dimensions"]),
            prompt_model_id=step["prompt_model_id"], action=deepcopy(step["action"]), index=step["index"])

    def queue_comparison(self, comparison):
        if comparison["settings"].get("reference_mode") == "native":
            actual = self.minimax.images.dimensions(self.minimax.assets.read_bytes(comparison["source_asset_id"]))
            if list(MinimaxEditSettings(**comparison["settings"]).dimensions(actual)) != comparison["dimensions"]:
                raise ValueError("La référence doit conserver les dimensions fixes de cet essai.")
        project, stage = self._stage(comparison)
        attempt = next((a for a in stage["attempts"] if a["request_id"] == comparison["render_request_id"]), None)
        if attempt is None:
            project = self.minimax.update(project["id"], stage["id"], revision=stage["revision"],
                changes=dict(settings=comparison["settings"], prompt=comparison["prompt"], draft=""))
            stage = project["stages"][0]
            project = self.minimax.queue_attempt(project["id"], stage["id"], revision=stage["revision"],
                                                request_id=comparison["render_request_id"])
            attempt = next(a for a in project["stages"][0]["attempts"] if a["request_id"] == comparison["render_request_id"])
        return attempt

    def comparison_result(self, comparison):
        # A GET must not create a child or requeue a missing render after a restart.
        try:
            project = self.minimax.get(journey_child_id(comparison["id"]))
        except FileNotFoundError:
            return None
        stage = project["stages"][0]
        return next((a for a in stage["attempts"] if a["request_id"] == comparison["render_request_id"]), None)
