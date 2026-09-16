"""Coordinate existing KREA2 Assisted and REF2V services for a validated story."""
from copy import deepcopy
from dataclasses import asdict, replace
from threading import RLock, Thread
from uuid import uuid4

from panelforge.domain.episodes import (
    REF2V_PROFILE, REFERENCE_ROLES, DEFAULT_CREATIVE_AXES, fingerprint, initial_episode, scene_inputs,
    effective_image_settings, image_defaults, inherits_images, style_context,
)
from panelforge.domain.krea2_batch import Krea2LoraSelection
from panelforge.domain.krea2_sampling import sampling_from_dict
from panelforge.domain.krea2_assisted_workflows import workflow_selection_from_dict
from panelforge.domain.prompt_composition import CookbookBinding, CompositionStage, PreparationIntent
from panelforge.domain.prompt_lab import CreativeFreedomAxes, ReferenceUse
from panelforge.domain.video_preparation import ClassicCinematicSettings
from .prompt_lab import NewReference, StreamEventKind


class EpisodeConflict(ValueError):
    pass


class EpisodeService:
    def __init__(self, *, stories, store, krea, prompt_lab, composition, render, assets):
        self.stories, self.store, self.krea = stories, store, krea
        self.prompt_lab, self.composition, self.render, self.assets = prompt_lab, composition, render, assets
        self._lock, self._active = RLock(), set()

    def create(self, story_id, expected_version):
        with self._lock:
            story = self.stories.get(story_id)
            if story["version"] != expected_version or (story.get("job") or {}).get("status") in {"running", "cancelling"}:
                raise EpisodeConflict("L’histoire a changé ou son écriture est en cours. Rechargez-la avant de la valider.")
            if not story["document"].get("scenario"):
                raise ValueError("Développez et validez un scénario avant la fabrication.")
            digest = fingerprint(story["document"]["scenario"])
            for existing in self.store.list(story_id):
                if existing["source_hash"] == digest:
                    return self.get(existing["episode_id"])
            value = initial_episode(story, f"episode-{uuid4().hex}")
            self.store.save(value)
            return self.get(value["episode_id"])

    def get(self, identity):
        with self._lock:
            value = self.store.get(identity)
            interrupted = False
            for collection in ("references", "scenes"):
                for item in value[collection]:
                    if ((item.get("job") or {}).get("status") == "running"
                            and (identity, collection, item["id"]) not in self._active):
                        item["job"].update(status="interrupted", error="Traitement interrompu. Vous pouvez le reprendre.")
                        if collection == "scenes" and item["preparations"]:
                            item["preparations"][-1]["status"] = "interrupted"
                        interrupted = True
            if interrupted:
                value = self.store.save(value)
        view = deepcopy(value)
        view.setdefault("visual_revision", 1)
        view.setdefault("style_image", None)
        view.setdefault("style_preset", None)
        view["image_defaults"] = image_defaults(value)
        for ref in view["references"]:
            ref["inherit_image_settings"] = inherits_images(ref)
            ref["effective_image_settings"] = effective_image_settings(value, ref)
            previous = ref.get("prompt_style")
            active_style = style_context(value)
            ref["prompt_style_stale"] = bool(ref["prompt"] and (
                fingerprint(previous) != fingerprint(active_style) if previous is not None
                else any(active_style.values())))
            image_style = ref.get("image_style")
            ref["image_style_status"] = ("unknown" if image_style is None else
                "current" if fingerprint(image_style) == fingerprint(active_style) else "outdated")
        try:
            story = self.stories.store.get(value["story_id"])
            view["story_changed"] = fingerprint(story["document"].get("scenario")) != value["source_hash"]
        except FileNotFoundError:
            view["story_changed"] = True
        for scene in view["scenes"]:
            try:
                inputs = scene_inputs(value, scene)
                scene["resolved_intention"] = inputs["source_text"]
                scene["input_error"] = None
                scene["stale"] = bool(scene["preparations"] and scene["preparations"][-1]["input_hash"] != fingerprint(inputs))
            except ValueError as error:
                scene["resolved_intention"] = ""
                scene["input_error"] = str(error)
                scene["stale"] = bool(scene["preparations"])
            project_id = scene["preparations"][-1].get("render_project_id") if scene["preparations"] else None
            if project_id:
                try:
                    project = self.render.projects.get(project_id)
                    scene["video_status"] = project.attempts[-1].status.value if project.attempts else None
                except (KeyError, FileNotFoundError):
                    scene["video_status"] = None
        return view

    @staticmethod
    def _item(value, collection, item_id):
        item = next((r for r in value[collection] if r["id"] == item_id), None)
        if item is None:
            raise KeyError("Fiche ou scène introuvable.")
        return item

    def _editable(self, identity, collection, item_id, expected_revision):
        if (identity, collection, item_id) in self._active:
            raise EpisodeConflict("Un traitement est en cours sur cette fiche ou cette scène.")
        value = self.store.get(identity)
        item = self._item(value, collection, item_id)
        if item["revision"] != expected_revision:
            raise EpisodeConflict("Cette fiche ou scène a changé. Rechargez-la avant d’enregistrer.")
        return value, item

    def update_reference(self, identity, ref_id, expected_revision, *, description, prompt, model_id, render_settings,
                         inherit_image_settings=None):
        with self._lock:
            value, ref = self._editable(identity, "references", ref_id, expected_revision)
            if prompt != ref["prompt"]:
                ref["prompt_manually_edited"] = True
            ref.update(description=description, prompt=prompt, model_id=model_id, render_settings=render_settings,
                       revision=ref["revision"] + 1)
            if inherit_image_settings is not None:
                ref["inherit_image_settings"] = inherit_image_settings
            self.store.save(value)
        return self.get(identity)

    def update_scene(self, identity, scene_id, expected_revision, **changes):
        with self._lock:
            value, scene = self._editable(identity, "scenes", scene_id, expected_revision)
            scene.update(changes)
            scene_inputs(value, scene, require_images=False)
            if scene["shot_count"] is not None and not 1 <= scene["shot_count"] <= 6:
                raise ValueError("Choisissez Auto ou un à six plans.")
            scene["render_setup"]["settings"]["duration_seconds"] = scene["duration"]
            scene["render_revision"] += 1
            scene["revision"] += 1
            self.store.save(value)
        return self.get(identity)

    def save_render_setup(self, identity, scene_id, expected_revision, setup):
        with self._lock:
            value = self.store.get(identity)
            scene = self._item(value, "scenes", scene_id)
            if scene["render_revision"] != expected_revision:
                raise EpisodeConflict("Les réglages vidéo ont changé dans un autre onglet. Rechargez la scène.")
            scene["render_setup"] = deepcopy(setup)
            scene["render_revision"] += 1
            self.store.save(value)
            return {"render_revision": scene["render_revision"]}

    def set_style(self, identity, style, expected_style):
        with self._lock:
            value = self.store.get(identity)
            if value["style"] != expected_style:
                raise EpisodeConflict("Le style commun a changé. Rechargez la fabrication.")
            value["style"] = style
            value["visual_revision"] = value.get("visual_revision", 1) + 1
            self.store.save(value)
        return self.get(identity)

    def _visual_edit(self, identity, expected_revision):
        value = self.store.get(identity)
        if value.get("visual_revision", 1) != expected_revision:
            raise EpisodeConflict("Le style ou les réglages communs ont changé. Actualisez la fabrication.")
        value["visual_revision"] = expected_revision + 1
        return value

    def update_visual(self, identity, expected_revision, style, settings):
        with self._lock:
            value = self._visual_edit(identity, expected_revision)
            value.update(style=style, image_defaults=deepcopy(settings))
            self.store.save(value)
        return self.get(identity)

    def apply_style_preset(self, identity, expected_revision, preset_id):
        with self._lock:
            value = self._visual_edit(identity, expected_revision)
            if preset_id is None:
                value.update(style_preset=None, style_image=None)
            else:
                if self.krea.presets is None:
                    raise ValueError("Le catalogue de presets KREA2 n’est pas configuré.")
                preset = self.krea.presets.get(preset_id)
                image = self.assets.get(preset.image_asset_id)
                if not image.media_type.startswith("image/"):
                    raise ValueError("L’image de ce preset est indisponible.")
                value["style_preset"] = dict(preset_id=preset.preset_id, revision=preset.revision,
                    name=preset.name, prompt=preset.prompt, source_project_id=preset.source_project_id,
                    source_attempt_id=preset.source_attempt_id)
                value["style_image"] = dict(asset_id=preset.image_asset_id, filename=preset.name)
                common = image_defaults(value)
                common.update(model_id=preset.settings.model_name,
                    loras=[dict(name=l.name, strength=l.strength) for l in preset.settings.loras])
                value["image_defaults"] = common
            self.store.save(value)
        return self.get(identity)

    def import_style_image(self, identity, expected_revision, content, media_type, filename):
        with self._lock:
            value = self._visual_edit(identity, expected_revision)
            asset = self.assets.create(content, media_type=media_type, source_run_id=identity)
            value.update(style_image=dict(asset_id=asset.asset_id, filename=filename), style_preset=None)
            self.store.save(value)
        return self.get(identity)

    def select_style_image(self, identity, expected_revision, reference_id):
        with self._lock:
            value = self._visual_edit(identity, expected_revision)
            image = None
            if reference_id is not None:
                ref = self._item(value, "references", reference_id)
                if not ref["image_asset_id"]:
                    raise ValueError("Choisissez d’abord une image pour cette fiche.")
                image = dict(asset_id=ref["image_asset_id"], filename=ref["name"])
            value.update(style_image=image, style_preset=None)
            self.store.save(value)
        return self.get(identity)

    def select_image(self, identity, ref_id, expected_revision, asset_id):
        asset = self.assets.get(asset_id)
        if not asset.media_type.startswith("image/"):
            raise ValueError("Une image est requise.")
        with self._lock:
            value, ref = self._editable(identity, "references", ref_id, expected_revision)
            available = {i["asset_id"] for i in ref["images"]}
            selected_attempt = None
            if ref["krea_project_id"]:
                project = self.krea.projects.get(ref["krea_project_id"])
                available.update(a.output_asset_id for a in project.attempts if a.output_asset_id)
                selected_attempt = next((a for a in project.attempts if a.output_asset_id == asset_id), None)
            if asset_id not in available:
                raise ValueError("Cette image n’appartient pas à cette fiche. Importez-la d’abord.")
            ref.update(image_asset_id=asset_id, revision=ref["revision"] + 1)
            record = next((r for r in ref.get("image_runs", []) if selected_attempt and r["attempt_id"] == selected_attempt.attempt_id), None)
            ref["image_style"] = deepcopy(record.get("prompt_style")) if record else None
            self.store.save(value)
        return self.get(identity)

    def import_image(self, identity, ref_id, expected_revision, content, media_type, filename):
        with self._lock:
            value, ref = self._editable(identity, "references", ref_id, expected_revision)
            asset = self.assets.create(content, media_type=media_type, source_run_id=identity)
            ref["images"].append(dict(asset_id=asset.asset_id, label=filename))
            ref.update(image_asset_id=asset.asset_id, image_style=None, revision=ref["revision"] + 1)
            self.store.save(value)
        return self.get(identity)

    def reference_project(self, identity, ref_id):
        ref = self._item(self.store.get(identity), "references", ref_id)
        return self.krea.get(ref["krea_project_id"]) if ref["krea_project_id"] else None

    def _launch(self, identity, collection, item_id, request_id, work):
        key = (identity, collection, item_id)
        value = self.store.get(identity)
        item = self._item(value, collection, item_id)
        item["job"] = dict(status="running", phase="Préparation…", error=None, request_id=request_id)
        self._active.add(key)
        self.store.save(value)
        try:
            Thread(target=self._worker, args=(key, work), daemon=True, name=f"episode-{item_id}").start()
        except BaseException:
            self._active.discard(key)
            raise

    def _change(self, key, change):
        with self._lock:
            value = self.store.get(key[0])
            change(self._item(value, key[1], key[2]))
            self.store.save(value)

    def _worker(self, key, work):
        try:
            work(key)
            self._change(key, lambda item: item["job"].update(status="succeeded", phase="Terminé", error=None))
        except Exception as error:
            def fail(item):
                item["job"].update(status="failed", phase="Échec", error=str(error))
                if key[1] == "scenes" and item["preparations"]:
                    item["preparations"][-1].update(status="failed", error=str(error))
            self._change(key, fail)
        finally:
            with self._lock:
                self._active.discard(key)

    def prepare_reference(self, identity, ref_id, expected_revision, request_id, instruction, expected_visual_revision=None):
        with self._lock:
            value = self.store.get(identity)
            ref = self._item(value, "references", ref_id)
            if (ref.get("job") or {}).get("request_id") == request_id:
                return self.get(identity)
            value, ref = self._editable(identity, "references", ref_id, expected_revision)
            if expected_visual_revision is not None and value.get("visual_revision", 1) != expected_visual_revision:
                raise EpisodeConflict("Le style commun a changé. Actualisez avant de préparer le prompt.")
            snapshot = deepcopy(ref)
            visual = style_context(value)
            brief = (f"Crée une image de référence pour un épisode. {ref['name']} : {ref['description']}\n"
                     + ("Personnage seul, entier et lisible, apparence et tenue stables, fond neutre simple. "
                        if ref["kind"] == "character" else "Décor seul, sans personnage, repères spatiaux lisibles. ")
                     + f"Sans texte ni planche multiple. Style commun actuel : {value['style'] or 'Respecter la description de la fiche.'}\n{instruction}"
                     + "\nCette direction visuelle remplace les consignes et exemples de style des échanges précédents.")
            if visual["image"] or visual["preset"]:
                brief += ("\nL’image de guidage et l’exemple ci-dessous définissent uniquement le STYLE VISUEL commun : "
                          "stylisation, palette, matières, lumière et qualité de rendu. Décris ces attributs dans un prompt autonome. "
                          "Ne copie ni le sujet, ni sa tenue, ni sa pose, ni le décor ou le cadrage de l’exemple. "
                          "Le sujet et son apparence sont ceux de la fiche. Cette direction remplace les anciens exemples de style.")
            if len(brief) > 11800:
                raise ValueError("La description, le style et le retour sont trop longs ensemble. Raccourcissez-les avant de préparer le prompt.")
            if visual["preset"]:
                heading = f"\nExtrait du prompt du preset {visual['preset']['name']} (inspiration de style uniquement) :\n"
                available = 12000 - len(brief) - len(heading)
                if available > 0:
                    brief += heading + visual["preset"]["prompt"][:available]
            def work(key):
                project_id = snapshot["krea_project_id"]
                if not project_id:
                    project = self.krea.create_project(name=snapshot["name"][:120], intention=brief,
                        model_id=snapshot["model_id"], assistance_recipe_version="3.0.0")
                    project_id = project.project_id
                    self._change(key, lambda r: r.update(krea_project_id=project_id))
                self._change(key, lambda r: r["job"].update(phase="KREA2 Assisted · rédaction du prompt…"))
                guidance = visual["image"]
                for event in self.krea.stream_chat(project_id, brief, model_id=snapshot["model_id"],
                        current_prompt=snapshot["prompt"] or None,
                        guidance_asset_id=guidance["asset_id"] if guidance else None,
                        guidance_filename=guidance["filename"] if guidance else None):
                    if event.error:
                        raise ValueError(event.error)
                project = self.krea.projects.get(project_id)
                if not project.current_prompt:
                    raise ValueError("Le modèle n’a pas proposé de prompt. Précisez la fiche et relancez.")
                self._change(key, lambda r: r.update(prompt=project.current_prompt, prompt_style=visual, prompt_manually_edited=False,
                                                    revision=r["revision"] + 1))
            self._launch(identity, "references", ref_id, request_id, work)
        return self.get(identity)

    def render_reference(self, identity, ref_id, expected_revision, request_id, settings, seed=None,
                         expected_visual_revision=None):
        with self._lock:
            value = self.store.get(identity)
            ref = self._item(value, "references", ref_id)
            if (ref.get("job") or {}).get("request_id") == request_id:
                return self.get(identity)
            value, ref = self._editable(identity, "references", ref_id, expected_revision)
            if expected_visual_revision is not None and value.get("visual_revision", 1) != expected_visual_revision:
                raise EpisodeConflict("Les réglages communs ont changé. Actualisez avant de générer l’image.")
            common = image_defaults(value)
            if inherits_images(ref) and common["model_id"]:
                settings = replace(settings, model_name=common["model_id"],
                    loras=tuple(Krea2LoraSelection(**l) for l in common["loras"]),
                    sampling=sampling_from_dict(common["sampling"]),
                    workflow=workflow_selection_from_dict(common.get("workflow")))
            if not ref["prompt"].strip():
                raise ValueError("Préparez ou écrivez le prompt de la fiche avant de générer l’image.")
            snapshot = deepcopy(ref)
            def work(key):
                project_id = snapshot["krea_project_id"]
                if not project_id:
                    project_id = self.krea.create_project(name=snapshot["name"][:120],
                        intention=snapshot["description"], model_id=snapshot["model_id"],
                        assistance_recipe_version="3.0.0").project_id
                    self._change(key, lambda r: r.update(krea_project_id=project_id))
                project = self.krea.prepare_attempt(project_id, prompt=snapshot["prompt"], settings=settings, seed=seed, enqueue=True)
                attempt = project.attempts[-1]
                def remember(r):
                    r.setdefault("image_runs", []).append(dict(attempt_id=attempt.attempt_id,
                        prompt=snapshot["prompt"], prompt_style=deepcopy(snapshot.get("prompt_style")),
                        prompt_manually_edited=snapshot.get("prompt_manually_edited", False),
                        settings=asdict(settings), seed=attempt.seed,
                        visual_revision=value.get("visual_revision", 1)))
                self._change(key, remember)
                self.krea.start_render_worker()
                self._change(key, lambda r: r.update(revision=r["revision"] + 1))
            self._launch(identity, "references", ref_id, request_id, work)
        return self.get(identity)

    def prepare_scene(self, identity, scene_id, expected_revision, request_id, resume=False):
        with self._lock:
            value = self.store.get(identity)
            scene = self._item(value, "scenes", scene_id)
            if (scene.get("job") or {}).get("request_id") == request_id:
                return self.get(identity)
            value, scene = self._editable(identity, "scenes", scene_id, expected_revision)
            inputs = scene_inputs(value, scene)
            for ref in inputs["references"]:
                if not self.assets.get(ref["asset_id"]).media_type.startswith("image/"):
                    raise ValueError("Référence non visuelle.")
            latest = scene["preparations"][-1] if scene["preparations"] else None
            if resume:
                if not latest or latest["input_hash"] != fingerprint(inputs) or latest["status"] not in {"failed", "interrupted"}:
                    raise ValueError("Cette préparation ne peut pas être reprise : les entrées ont changé.")
                preparation = latest
                preparation.update(status="running", error=None)
            else:
                preparation = dict(id=f"prep-{uuid4().hex}", inputs=inputs, input_hash=fingerprint(inputs),
                    session_id=None, render_project_id=None, status="running", error=None,
                    render_setup=deepcopy(scene["render_setup"]))
                scene["preparations"].append(preparation)
            self.store.save(value)
            saved = deepcopy(preparation)
            self._launch(identity, "scenes", scene_id, request_id, lambda key: self._prepare_scene(key, saved))
        return self.get(identity)

    def _prepare_scene(self, key, preparation):
        inputs = preparation["inputs"]
        session_id = preparation["session_id"]
        if not session_id:
            session = self.prompt_lab.create_session(model_id=inputs["plan_model_id"],
                profile_id=REF2V_PROFILE[0], profile_version=REF2V_PROFILE[1],
                cinematic_settings=ClassicCinematicSettings(shot_count=inputs["shot_count"]),
                references=tuple(NewReference(asset_id=r["asset_id"], role=r["role"], label=r["name"],
                    uses=(ReferenceUse(REFERENCE_ROLES[r["role"]]),)) for r in inputs["references"]))
            session_id = session.session_id
            self._change(key, lambda s: s["preparations"][-1].update(session_id=session_id))
        else:
            session = self.prompt_lab.get_session(session_id)
        axes = CreativeFreedomAxes(**inputs.get("creative_axes", DEFAULT_CREATIVE_AXES))
        anchors = (0, 35, 65, 90)
        freedom = round(sum(anchors[v] for v in (axes.scene_life, axes.camera, axes.extra_motion)) / 3)
        self.composition.configure(session_id, inputs["cookbook"]["id"], inputs["cookbook"]["version"],
            (CookbookBinding("references", tuple(r.reference_id for r in session.references)),),
            preparation_intent=PreparationIntent(source_text=inputs["source_text"], creative_audacity=inputs["audacity"],
                creative_axes=axes, creative_freedom=freedom if "creative_axes" in inputs else 35),
            writer_model_id=inputs["writer_model_id"])
        for stage, label in ((CompositionStage.BEAT_SHEET, "1/2 · Plan REF2V"), (CompositionStage.FINAL_PROMPT, "2/2 · Rédaction du prompt")):
            document = self.composition.get(session_id).document(stage)
            if document.approved_revision_id:
                continue
            self._change(key, lambda s: s["job"].update(phase=label))
            if document.active_revision is None:
                for event in self.composition.stream_generate(session_id, stage):
                    if event.kind is StreamEventKind.TRUNCATED:
                        raise ValueError(f"{label} : réponse tronquée. Le brouillon reste dans les échanges LLM.")
                if self.composition.get(session_id).document(stage).active_revision is None:
                    raise ValueError(f"{label} : aucun document accepté. Le brouillon reste dans les échanges LLM.")
            self.composition.approve(session_id, stage)
        project = self.render.get_or_create_from_session(session_id)
        self._change(key, lambda s: s["preparations"][-1].update(status="ready", render_project_id=project.project_id, error=None))
