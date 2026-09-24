"""Explicit author edits to a fabrication ledger and guided image variants."""
from panelforge.domain import episode_continuity, story_continuity
from panelforge.domain.episodes import DEFAULT_PLAN_MODEL, fingerprint


class EpisodeContinuityActions:
    def _continuity_editable(self, value):
        from .episodes import EpisodeConflict
        self._require_original_fabrication(value)
        identity = value["episode_id"]
        if any(key[0] == identity for key in self._active) or identity in self._active_batches or identity in self._active_video_chains:
            raise EpisodeConflict("La fabrication travaille encore. Modifie la continuité après la fin des traitements.")
        if (value.get("video_chain") or {}).get("status") in {"running", "pausing", "cancelling"}:
            raise EpisodeConflict("La chaîne vidéo travaille encore ; ses références restent figées.")
        for reference in value["references"]:
            if not reference.get("krea_project_id"):
                continue
            try:
                project = self.krea.projects.get(reference["krea_project_id"])
            except (KeyError, FileNotFoundError):
                continue
            if any(getattr(a.status, "value", a.status) in {"queued", "running", "submitting", "cancel_pending"} for a in project.attempts):
                raise EpisodeConflict("Une image de référence est en cours de rendu. Attends sa fin.")
        for scene in value["scenes"]:
            project_id = scene["preparations"][-1].get("render_project_id") if scene["preparations"] else None
            if not project_id:
                continue
            try:
                project = self.render.projects.get(project_id)
            except (KeyError, FileNotFoundError):
                continue
            if any(getattr(a.status, "value", a.status) in {"queued", "running", "submitting", "cancel_pending"} for a in project.attempts):
                raise EpisodeConflict("Un rendu utilise ces références. Attends sa fin pour modifier la continuité.")

    def update_continuity(self, identity, expected_revision, visual_continuity):
        from .episodes import EpisodeConflict
        with self._lock:
            value = self.store.get(identity)
            if value.get("continuity_revision", 1) != expected_revision:
                raise EpisodeConflict("La continuité a changé dans une autre fenêtre. Recharge avant d'enregistrer.")
            self._continuity_editable(value)
            value["scenario"]["visual_continuity"] = story_continuity.normalize(visual_continuity, value["scenario"])
            value["scenario"]["visual_continuity"].pop("warnings", None)
            value.update(continuity_version=1, continuity_revision=expected_revision + 1)
            episode_continuity.sync_references(value, DEFAULT_PLAN_MODEL)
            # No preparation or render is rewritten. Its recorded inputs retain
            # the precise images and states used; new inputs acquire a new hash.
            self.store.save(value)
        return self.get(identity)

    def create_continuity_variant(self, identity, ref_id, expected_revision):
        if self.qwen_edit is None:
            raise ValueError("L'atelier Qwen n'est pas configuré. Tu peux importer une variante dans cette fiche.")
        with self._lock:
            value, ref = self._editable(identity, "references", ref_id, expected_revision)
            self._continuity_editable(value)
            if not ref.get("continuity_state_id"):
                raise ValueError("Choisis une variante d'apparence dans Continuité.")
            base = next((r for r in value["references"] if r["source_id"] == ref["source_id"]
                         and not r.get("continuity_state_id") and r.get("image_asset_id")), None)
            if base is None:
                raise ValueError("Choisis d'abord l'image d'identité du personnage ou de l'objet.")
            signature = fingerprint([base["image_asset_id"], ref["description"]])
            link = ref.get("qwen_variant")
            if link and link["signature"] == signature:
                return dict(project_id=link["project_id"], episode=self.get(identity))
            project = self.qwen_edit.create(name=ref["name"][:120], content=self.assets.read_bytes(base["image_asset_id"]))
            stage = project["stages"][0]
            self.qwen_edit.update(project["id"], stage["id"], revision=stage["revision"], changes=dict(
                draft="Prépare une édition de cette image pour une variante du même personnage ou objet. "
                      "Conserve l'identité, le style et les attributs qui ne changent pas. Modifie seulement l'état demandé :\n"
                      + ref["description"] + "\nUne seule vue, sans texte ni planche avant/après.",
                model_id=ref["model_id"]))
            ref["qwen_variant"] = dict(project_id=project["id"], signature=signature, source_asset_id=base["image_asset_id"])
            ref["revision"] += 1
            self.store.save(value)
        return dict(project_id=project["id"], episode=self.get(identity))

    def continuity_variant_results(self, identity, ref_id):
        value = self.store.get(identity)
        ref = self._item(value, "references", ref_id)
        link = ref.get("qwen_variant")
        if not link or self.qwen_edit is None:
            return dict(results=[])
        project = self.qwen_edit.get(link["project_id"])
        return dict(results=[dict(asset_id=a["output_asset_id"], label=f"Étape {stage['index']} · essai {i + 1}")
            for stage in project["stages"] for i, a in enumerate(stage["attempts"])
            if a["status"] == "succeeded" and a.get("output_asset_id")], project_id=project["id"])

    def select_continuity_variant(self, identity, ref_id, expected_revision, asset_id):
        with self._lock:
            value, ref = self._editable(identity, "references", ref_id, expected_revision)
            self._continuity_editable(value)
            available = self.continuity_variant_results(identity, ref_id)["results"]
            if asset_id not in {a["asset_id"] for a in available}:
                raise ValueError("Choisis un résultat terminé de l'atelier lié à cette variante.")
            if not any(a["asset_id"] == asset_id for a in ref["images"]):
                ref["images"].append(dict(asset_id=asset_id, label="Variante Qwen validée"))
            ref.update(image_asset_id=asset_id, image_style=None, continuity_image_stale=False, revision=ref["revision"] + 1)
            self.store.save(value)
        return self.get(identity)
