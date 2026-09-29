"""Read-only adapters for explicit versions from the three edit workshops."""


class ImageTransitionSources:
    def __init__(self, *, krea=None, qwen=None, minimax=None):
        self.services = dict(krea=krea, qwen=qwen, minimax=minimax)

    def _service(self, engine):
        if engine not in self.services or self.services[engine] is None:
            raise ValueError("Cet atelier n’est pas disponible.")
        return self.services[engine]

    def projects(self, engine):
        service = self._service(engine)
        if engine != "krea":
            return service.list()
        groups = {}
        for source in service.sources.list(2**31 - 1):
            groups.setdefault(source.project_id, dict(id=source.project_id,
                name=source.project_name or source.filename, thumbnail_asset_id=source.source_asset_id))
        return list(groups.values())

    def choices(self, engine, project_id):
        service = self._service(engine)
        result = []
        if engine == "krea":
            stages = sorted((s for s in service.sources.list(2**31 - 1, include_hidden=True)
                             if s.project_id == project_id), key=lambda s: s.stage_index)
            if not stages:
                raise FileNotFoundError("Projet KREA introuvable.")
            for index, stage in enumerate(stages):
                if index == 0:
                    result.append(self._choice(engine, project_id, stage.source_id, "source",
                        stage.source_asset_id, "Image de départ", True, ""))
                for number, attempt in enumerate(stage.attempts, 1):
                    if str(attempt.status) == "succeeded" and attempt.output_asset_id:
                        accepted = attempt.attempt_id == stage.accepted_attempt_id
                        result.append(self._choice(engine, project_id, stage.source_id, attempt.attempt_id,
                            attempt.output_asset_id, f"Étape {stage.stage_index} · essai {number}", accepted,
                            stage.instruction or attempt.prompt))
        else:
            project = service.get(project_id)
            for index, stage in enumerate(project["stages"]):
                if index == 0 and stage["source_asset_id"]:
                    result.append(self._choice(engine, project_id, stage["id"], "source",
                        stage["source_asset_id"], "Image de départ", True, ""))
                for number, attempt in enumerate(stage["attempts"], 1):
                    if attempt["status"] == "succeeded" and attempt.get("output_asset_id"):
                        result.append(self._choice(engine, project_id, stage["id"], attempt["id"],
                            attempt["output_asset_id"], f"{stage['label']} · essai {number}",
                            attempt["id"] == stage["accepted_attempt_id"], attempt.get("prompt", "")))
        return result

    @staticmethod
    def _choice(engine, project_id, stage_id, attempt_id, asset_id, label, accepted, instruction):
        return dict(key=f"{stage_id}:{attempt_id}", asset_id=asset_id, label=label, accepted=accepted,
                    origin=dict(engine=engine, project_id=project_id, stage_id=stage_id,
                                attempt_id=attempt_id, instruction=instruction[:4000]))

    def select(self, engine, project_id, keys):
        choices = {c["key"]: c for c in self.choices(engine, project_id)}
        if not keys or len(keys) != len(set(keys)) or len(keys) > 100:
            raise ValueError("Choisissez de 1 à 100 images distinctes.")
        try:
            return [choices[key] for key in keys]
        except KeyError as error:
            raise ValueError("Une version sélectionnée n’est plus disponible. Actualisez la liste.") from error
