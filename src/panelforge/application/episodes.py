"""Coordinate existing KREA2 Assisted and REF2V services for a validated story."""
from copy import deepcopy
from dataclasses import asdict, replace
from threading import RLock, Thread
import time
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
from panelforge.domain.krea2_assisted import Krea2AssistedAttemptStatus
from panelforge.domain.production import ThermalPolicy
from .prompt_lab import NewReference, StreamEventKind


class EpisodeConflict(ValueError):
    pass


class EpisodeService:
    def __init__(self, *, stories, store, krea, prompt_lab, composition, render, assets,
                 work_coordinator=None, sleep=time.sleep):
        self.stories, self.store, self.krea = stories, store, krea
        self.prompt_lab, self.composition, self.render, self.assets = prompt_lab, composition, render, assets
        self.work_coordinator, self._sleep = work_coordinator, sleep
        self._lock, self._active = RLock(), set()
        self._active_batches = set()

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
            value.setdefault("reference_profiles", {})
            value.setdefault("reference_batch", None)
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
            batch = value.get("reference_batch")
            if batch and batch.get("status") in {"running", "rendering", "cancelling"} and identity not in self._active_batches:
                batch.update(status="interrupted", phase="Traitement interrompu", error="Le serveur a redémarré pendant la production en lot.")
                value = self.store.save(value)
            value = self._reconcile_reference_batch(value)
        view = deepcopy(value)
        view.setdefault("visual_revision", 1)
        view.setdefault("style_image", None)
        view.setdefault("style_preset", None)
        view.setdefault("reference_profiles", {})
        view.setdefault("reference_batch", None)
        if self.work_coordinator is not None:
            view["machine_work"] = self.work_coordinator.public_status()
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

    def _reconcile_reference_batch(self, value):
        batch = value.get("reference_batch")
        if not batch:
            return value
        changed = False
        refs = {ref["id"]: ref for ref in value["references"]}
        for item in batch.get("items", []):
            ref = refs.get(item["reference_id"])
            if ref is None:
                continue
            output_id = item.get("output_asset_id")
            selected_asset = ref.get("image_asset_id")
            selection_changed = selected_asset and (
                selected_asset == output_id or selected_asset != item.get("initial_asset_id")
            )
            if selection_changed and item.get("status") in {"ready_for_review", "validated"}:
                selected = selected_asset
                if item.get("status") != "validated" or item.get("selected_asset_id") != selected:
                    item.update(status="validated", selected_asset_id=selected)
                    changed = True
            elif item.get("attempt_id") and ref.get("krea_project_id"):
                try:
                    attempt = self.krea.projects.get(ref["krea_project_id"]).attempt(item["attempt_id"])
                except (KeyError, FileNotFoundError, ValueError):
                    continue
                if attempt.status is Krea2AssistedAttemptStatus.SUCCEEDED:
                    if item.get("status") not in {"ready_for_review", "validated"} or output_id != attempt.output_asset_id:
                        item.update(status="ready_for_review", phase="Image prête à valider",
                                    output_asset_id=attempt.output_asset_id, error=None)
                        changed = True
                elif attempt.status in {Krea2AssistedAttemptStatus.FAILED, Krea2AssistedAttemptStatus.CANCELLED}:
                    if item.get("status") != "failed":
                        item.update(status="failed", phase="Échec", error=attempt.error or "Le rendu a échoué.")
                        changed = True
                elif attempt.status in {Krea2AssistedAttemptStatus.SUBMITTING, Krea2AssistedAttemptStatus.RUNNING,
                                        Krea2AssistedAttemptStatus.CANCEL_PENDING}:
                    if item.get("status") != "rendering":
                        item.update(status="rendering", phase="Rendu KREA2 en cours")
                        changed = True
        statuses = {item.get("status") for item in batch.get("items", [])}
        active = statuses & {"pending", "prompting", "prompt_ready", "queued_render", "rendering"}
        if not active and batch.get("status") in {"running", "rendering", "waiting_review"}:
            target = "completed" if statuses <= {"validated", "skipped"} else (
                "failed" if statuses <= {"failed", "skipped"} else "waiting_review")
            phase = {"completed": "Toutes les références sont validées",
                     "failed": "Aucune image à valider", "waiting_review": "Validation humaine requise"}[target]
            if batch.get("status") != target or batch.get("phase") != phase:
                batch.update(status=target, phase=phase)
                changed = True
        if changed:
            return self.store.save(value)
        return value

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

    @staticmethod
    def _batch_render_settings(settings, seed):
        return dict(
            workflow=asdict(settings.workflow), model_id=settings.model_name,
            aspect_ratio=settings.aspect_ratio.value, megapixels=settings.megapixels,
            seed=str(seed) if seed is not None else None,
            loras=[asdict(value) for value in settings.loras],
            sampling=asdict(settings.sampling),
        )

    def start_reference_batch(self, identity, *, expected_visual_revision, request_id,
                              reference_ids, profiles, thermal):
        """Pipeline one LLM call at a time while KREA2 drains independently."""
        policy = thermal if isinstance(thermal, ThermalPolicy) else ThermalPolicy(**thermal)
        with self._lock:
            value = self.store.get(identity)
            existing = value.get("reference_batch")
            if existing and existing.get("request_id") == request_id:
                return self.get(identity)
            if existing and existing.get("status") in {"running", "rendering", "cancelling"}:
                raise EpisodeConflict("Une production de références est déjà en cours.")
            if value.get("visual_revision", 1) != expected_visual_revision:
                raise EpisodeConflict("Le style ou les réglages ont changé. Actualisez avant le lancement en lot.")
            selected = []
            seen = set()
            for ref_id in reference_ids:
                if ref_id in seen:
                    raise ValueError("Une fiche ne peut apparaître qu’une fois dans le lot.")
                seen.add(ref_id)
                ref = self._item(value, "references", ref_id)
                profile = profiles.get(ref["kind"])
                if profile is None:
                    raise ValueError(f"Le profil {ref['kind']} est manquant.")
                public_settings = self._batch_render_settings(profile["settings"], profile.get("seed"))
                ref.update(model_id=profile["model_id"], render_settings=deepcopy(public_settings),
                           inherit_image_settings=False, revision=ref["revision"] + 1)
                selected.append(ref)
            if not selected:
                raise ValueError("Choisissez au moins un personnage ou un décor.")
            public_profiles = {
                kind: dict(model_id=profile["model_id"],
                           render_settings=self._batch_render_settings(profile["settings"], profile.get("seed")))
                for kind, profile in profiles.items()
            }
            batch_id = f"reference-batch-{uuid4().hex}"
            value["reference_profiles"] = deepcopy(public_profiles)
            value["reference_batch"] = dict(
                batch_id=batch_id, request_id=request_id, status="running", phase="Préparation des prompts",
                error=None, cancel_requested=False, profiles=deepcopy(public_profiles), thermal=asdict(policy),
                items=[dict(reference_id=ref["id"], name=ref["name"], kind=ref["kind"],
                            status="pending", phase="En attente", error=None, attempt_id=None,
                            output_asset_id=None, selected_asset_id=None,
                            initial_asset_id=ref.get("image_asset_id")) for ref in selected],
            )
            self._active_batches.add(identity)
            self.store.save(value)
            if self.work_coordinator is not None:
                self.work_coordinator.configure(policy)
            try:
                Thread(target=self._reference_batch_worker,
                       args=(identity, batch_id, deepcopy(profiles)), daemon=True,
                       name=f"episode-reference-batch-{identity}").start()
            except BaseException:
                self._active_batches.discard(identity)
                raise
        return self.get(identity)

    def cancel_reference_batch(self, identity, batch_id):
        attempts = []
        with self._lock:
            value = self.store.get(identity)
            batch = value.get("reference_batch")
            if not batch or batch.get("batch_id") != batch_id:
                raise KeyError("Production de références introuvable.")
            if batch.get("status") not in {"running", "rendering", "cancelling"}:
                return self.get(identity)
            batch.update(cancel_requested=True, status="cancelling", phase="Annulation demandée")
            refs = {ref["id"]: ref for ref in value["references"]}
            for item in batch["items"]:
                ref = refs.get(item["reference_id"])
                if item.get("attempt_id") and ref and ref.get("krea_project_id"):
                    attempts.append((ref["krea_project_id"], item["attempt_id"]))
            self.store.save(value)
        for project_id, attempt_id in attempts:
            try:
                self.krea.cancel_attempt(project_id, attempt_id)
            except (KeyError, FileNotFoundError, ValueError):
                pass
        return self.get(identity)

    def _batch_change(self, identity, batch_id, change):
        with self._lock:
            value = self.store.get(identity)
            batch = value.get("reference_batch")
            if not batch or batch.get("batch_id") != batch_id:
                raise EpisodeConflict("La production en lot a été remplacée.")
            change(value, batch)
            self.store.save(value)

    def _batch_cancelled(self, identity, batch_id):
        with self._lock:
            value = self.store.get(identity)
            batch = value.get("reference_batch")
            return not batch or batch.get("batch_id") != batch_id or batch.get("cancel_requested", False)

    def _batch_item(self, batch, reference_id):
        return next(item for item in batch["items"] if item["reference_id"] == reference_id)

    def _wait_reference_job(self, identity, ref_id, batch_id):
        while True:
            if self._batch_cancelled(identity, batch_id):
                return None
            with self._lock:
                ref = self._item(self.store.get(identity), "references", ref_id)
            job = ref.get("job") or {}
            if job.get("status") != "running":
                return job
            self._sleep(0.1)

    def _reference_batch_worker(self, identity, batch_id, profiles):
        try:
            batch = self.store.get(identity)["reference_batch"]
            for original in batch["items"]:
                ref_id = original["reference_id"]
                if self._batch_cancelled(identity, batch_id):
                    break
                self._batch_change(identity, batch_id, lambda _value, current, ref_id=ref_id:
                    self._batch_item(current, ref_id).update(status="prompting", phase="Rédaction LLM", error=None))
                current = self._item(self.store.get(identity), "references", ref_id)
                try:
                    self.prepare_reference(identity, ref_id, current["revision"],
                        f"{batch_id}-prompt-{ref_id}", "",
                        expected_visual_revision=self.store.get(identity).get("visual_revision", 1))
                    job = self._wait_reference_job(identity, ref_id, batch_id)
                    if job is None:
                        break
                    if job.get("status") != "succeeded":
                        raise ValueError(job.get("error") or "La rédaction du prompt a échoué.")
                    self._batch_change(identity, batch_id, lambda _value, current, ref_id=ref_id:
                        self._batch_item(current, ref_id).update(status="prompt_ready", phase="Prompt prêt", error=None))
                    current = self._item(self.store.get(identity), "references", ref_id)
                    profile = profiles[current["kind"]]
                    self.render_reference(identity, ref_id, current["revision"],
                        f"{batch_id}-render-{ref_id}", profile["settings"], profile.get("seed"),
                        expected_visual_revision=self.store.get(identity).get("visual_revision", 1))
                    job = self._wait_reference_job(identity, ref_id, batch_id)
                    if job is None:
                        break
                    if job.get("status") != "succeeded":
                        raise ValueError(job.get("error") or "La mise en file du rendu a échoué.")
                    current = self._item(self.store.get(identity), "references", ref_id)
                    attempt_id = current.get("image_runs", [])[-1]["attempt_id"]
                    self._batch_change(identity, batch_id, lambda _value, active, ref_id=ref_id, attempt_id=attempt_id:
                        self._batch_item(active, ref_id).update(status="queued_render", phase="Rendu KREA2 en file",
                                                               attempt_id=attempt_id, error=None))
                except Exception as error:
                    self._batch_change(identity, batch_id, lambda _value, current, ref_id=ref_id, error=error:
                        self._batch_item(current, ref_id).update(status="failed", phase="Échec", error=str(error)))
            if self._batch_cancelled(identity, batch_id):
                self._batch_change(identity, batch_id, lambda _value, current:
                    current.update(status="cancelled", phase="Annulé", error=None))
                return
            self._batch_change(identity, batch_id, lambda _value, current:
                current.update(status="rendering", phase="Rendus KREA2 en cours"))
            while True:
                with self._lock:
                    value = self.store.get(identity)
                    value = self._reconcile_reference_batch(value)
                    current = value["reference_batch"]
                if current.get("status") not in {"running", "rendering"}:
                    return
                if self._batch_cancelled(identity, batch_id):
                    self._batch_change(identity, batch_id, lambda _value, active:
                        active.update(status="cancelled", phase="Annulé", error=None))
                    return
                self._sleep(0.5)
        except Exception as error:
            try:
                self._batch_change(identity, batch_id, lambda _value, current:
                    current.update(status="failed", phase="Échec du lot", error=str(error)))
            except (EpisodeConflict, FileNotFoundError):
                pass
        finally:
            with self._lock:
                self._active_batches.discard(identity)

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
