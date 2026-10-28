"""Assisted MH composition reuses the existing still renderer and scheduler."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from uuid import UUID

from panelforge.domain import mh_assisted as policy
from . import mh_assisted_prompting as prompting
from .qwen_edit import QwenEditService, QwenEditConflict, _id, _now, _attempt


class MhAssistedService(QwenEditService):
    def __init__(self, *, style_source, poses, **kwargs):
        super().__init__(policy=policy, prompting=prompting, **kwargs)
        self.style_source, self.poses = style_source, poses

    def _new_stage(self, *args, **kwargs):
        stage = super()._new_stage(*args, **kwargs)
        stage["creative"] = dict(prompt_language="en", style_preset=None, art_direction=None, pose=None)
        return stage

    def _preset(self, preset_id):
        if not preset_id:
            return None
        return next((p for p in self.style_source.list_style_presets() if p.preset_id == preset_id), None) or self._unknown("Preset")

    @staticmethod
    def _unknown(label):
        raise ValueError(label + " introuvable. Actualise le catalogue.")

    def _art(self, style_id):
        if not style_id:
            return None
        value = next((s for s in self.style_source.list_art_styles() if s.style_id == style_id), None)
        return asdict(value) if value else self._unknown("Direction artistique")

    @staticmethod
    def _required_reference(stage):
        if not policy.render_inputs(stage):
            raise ValueError("Choisis une pose ou ajoute une image de référence pour créer avec MH.")

    def _creative(self, stage, changes):
        allowed = {"prompt_language", "preset_id", "art_style_id", "pose_id"}
        if set(changes) - allowed:
            raise ValueError("Choix créatif inconnu.")
        creative = stage["creative"]
        if "prompt_language" in changes:
            creative["prompt_language"] = policy.language(changes["prompt_language"])
        if "preset_id" in changes:
            preset = self._preset(changes["preset_id"])
            stage["references"] = [r for r in stage["references"] if r["id"] != "mh-style-example"]
            creative["style_preset"] = None
            if preset:
                if not self.assets.get(preset.image_asset_id).media_type.startswith("image/"):
                    raise ValueError("L’image du preset est indisponible.")
                creative["style_preset"] = dict(preset_id=preset.preset_id, revision=preset.revision,
                    name=preset.name, prompt=preset.prompt, image_asset_id=preset.image_asset_id,
                    source_project_id=preset.source_project_id, source_attempt_id=preset.source_attempt_id)
                stage["references"].append(dict(id="mh-style-example", asset_id=preset.image_asset_id,
                    name="Exemple artistique du preset", usage="assistant", active=True,
                    role="Style et traitement visuel uniquement. Conserver les sujets et la pose du projet courant."))
                if "art_style_id" not in changes:
                    creative["art_direction"] = asdict(preset.art_direction) if preset.art_direction else None
        if "art_style_id" in changes:
            creative["art_direction"] = self._art(changes["art_style_id"])
        if "pose_id" in changes:
            identity = changes["pose_id"]
            old = creative.get("pose")
            metadata, content = self.poses.reference(identity) if identity else (None, None)
            unchanged = (old and metadata and old["id"] == identity
                         and old["catalog_revision"] == metadata["catalog_revision"]
                         and old["sha256"] == metadata["sha256"])
            if not unchanged:
                stage["references"] = [r for r in stage["references"] if r["id"] != "mh-pose"]
                creative["pose"] = None
                if identity:
                    asset = self.assets.create(self.images.normalize_source(content), media_type="image/png")
                    creative["pose"] = {**metadata, "asset_id": asset.asset_id, "reference_id": "mh-pose"}
                    stage["references"].insert(0, dict(id="mh-pose", asset_id=asset.asset_id,
                        name="Pose du catalogue · " + metadata["number"], role=policy.POSE_ROLE,
                        usage="render", active=True))
        policy.validate_references(stage["references"])
        self._required_reference(stage)

    def create_assisted(self, *, request_id, name, intention="", model_id="", prompt_language="en",
                        preset_id=None, art_style_id="", pose_id=None, content=None):
        identity = "mh-" + UUID(request_id).hex
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValueError("Donne un nom au projet (120 caractères maximum).")
        if not isinstance(intention, str) or len(intention) > 12000:
            raise ValueError("Intention trop longue (12 000 caractères maximum).")
        if not isinstance(model_id, str) or len(model_id) > 300:
            raise ValueError("Modèle de l’assistant invalide.")
        policy.language(prompt_language)
        if not pose_id and not content:
            raise ValueError("Choisis au moins une pose ou une image de référence.")
        signature = hashlib.sha256(json.dumps(dict(name=name, intention=intention, model=model_id,
            language=prompt_language, preset=preset_id, art=art_style_id, pose=pose_id,
            image=hashlib.sha256(content).hexdigest() if content else None), sort_keys=True).encode()).hexdigest()
        with self._lock:
            try:
                previous = self.projects.get(identity)
            except FileNotFoundError:
                previous = None
            if previous:
                if previous.get("creation_fingerprint") != signature:
                    raise QwenEditConflict("Cette création a déjà été enregistrée avec d’autres choix.")
                return previous
            stage = self._new_stage(1, None, model_id=model_id, mode="composition")
            stage["draft"] = intention.strip() or "Propose une image à partir des références et des choix artistiques sélectionnés."
            if content:
                asset = self.assets.create(self.images.normalize_source(content), media_type="image/png")
                stage["references"].append(dict(id=_id("ref"), asset_id=asset.asset_id, name="Référence sujet",
                    role="Sujet et apparence selon l’intention. La pose du catalogue guide la posture si elle est sélectionnée.",
                    usage="render", active=True))
            self._creative(stage, dict(prompt_language=prompt_language, preset_id=preset_id,
                                       art_style_id=art_style_id, pose_id=pose_id))
            project = dict(schema_version=1, engine=self.engine, id=identity, name=name.strip(), version=0,
                created_at=_now(), updated_at=_now(), active_stage_id=stage["id"], stages=[stage],
                intention=intention, creation_fingerprint=signature, export_path=None, export_error=None)
            return self._save(project)

    def configure(self, project_id, stage_id, *, revision, changes):
        with self._lock:
            project = deepcopy(self.projects.get(project_id))
            stage = self._editable(project, stage_id, revision)
            before = policy.context_fingerprint(stage)
            self._creative(stage, changes)
            if policy.context_fingerprint(stage) != before:
                stage["prompt_fingerprint"] = None
            stage["revision"] += 1
            return self._save(project)

    def update(self, project_id, stage_id, *, revision, changes):
        with self._lock:
            project = self.projects.get(project_id)
            stage = self._editable(project, stage_id, revision)
            if "references" in changes:
                policy.validate_references(changes["references"])
                protected = {r["id"]: r for r in stage["references"] if r["id"].startswith("mh-")}
                supplied = {r["id"]: r for r in changes["references"] if r["id"].startswith("mh-")}
                if protected != supplied:
                    raise ValueError("Modifie la pose ou le preset avec leur sélecteur dédié.")
                self._required_reference({**stage, "references": changes["references"]})
            return super().update(project_id, stage_id, revision=revision, changes=changes)

    def begin_message(self, project_id, stage_id, *, revision, request_id, render_after_prompt=False):
        if render_after_prompt:
            raise ValueError("Le rendu MH se lance après la préparation du prompt.")
        return super().begin_message(project_id, stage_id, revision=revision, request_id=request_id)

    def restore_attempt(self, project_id, stage_id, attempt_id, *, revision):
        with self._lock:
            project = deepcopy(self.projects.get(project_id))
            stage = self._editable(project, stage_id, revision)
            attempt = _attempt(stage, attempt_id)
            stage["references"] = deepcopy(attempt["context"]["references"])
            stage["creative"] = deepcopy(attempt["context"]["creative"])
            stage["settings"] = policy.Settings(**attempt["settings"]).record()
            stage.update(prompt=attempt["prompt"], summary=attempt["summary"], draft="",
                         feedback_attempt_id=attempt_id if attempt["status"] == "succeeded" else None)
            stage["prompt_fingerprint"] = policy.context_fingerprint(stage)
            stage["revision"] += 1
            return self._save(project)

    def list(self):
        with self._lock:
            values = []
            for project in self.projects.list():
                stage = next(s for s in project["stages"] if s["id"] == project["active_stage_id"])
                thumbnail = next((a["output_asset_id"] for a in reversed(stage["attempts"]) if a.get("output_asset_id")), None)
                thumbnail = thumbnail or next((r["asset_id"] for r in stage["references"] if r["active"] and r["usage"] == "render"), None)
                values.append(dict(id=project["id"], name=project["name"], updated_at=project["updated_at"],
                                   thumbnail_asset_id=thumbnail, attempt_count=len(stage["attempts"])))
            return values[:100]
