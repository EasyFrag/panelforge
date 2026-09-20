"""Coordinate existing KREA2 Assisted and REF2V services for a validated story."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import re
from threading import RLock, Thread
import time
import unicodedata
from uuid import uuid4

from panelforge.domain.episodes import (
    REF2V_PROFILE, REFERENCE_ROLES, DEFAULT_CREATIVE_AXES, fingerprint, initial_episode, scene_inputs,
    effective_image_settings, image_defaults, inherits_images, style_context,
    effective_video_setup, inherits_video_settings, video_defaults,
)
from panelforge.domain.dlss import DlssSettings
from panelforge.domain.krea2_batch import Krea2LoraSelection
from panelforge.domain.krea2_sampling import sampling_from_dict
from panelforge.domain.krea2_assisted_workflows import workflow_selection_from_dict
from panelforge.domain.prompt_composition import CookbookBinding, CompositionStage, PreparationIntent
from panelforge.domain.prompt_lab import CreativeFreedomAxes, ReferenceUse
from panelforge.domain.stories import DEFAULT_DIALOGUE_LANGUAGE
from panelforge.domain.video_preparation import ClassicCinematicSettings
from panelforge.domain.krea2_assisted import Krea2AssistedAttemptStatus
from panelforge.domain.production import ThermalPolicy
from panelforge.domain.video_lab import VideoLabSettings, VideoAspectRatio
from panelforge.domain.h3_bunny import H3BunnySettings
from panelforge.domain.h3_render import (
    H3RenderAttemptStatus, H3VideoLoraSelection, H3VideoLoraStack,
)
from .prompt_lab import NewReference, StreamEventKind


class EpisodeConflict(ValueError):
    pass


class EpisodeService:
    def __init__(self, *, stories, store, krea, prompt_lab, composition, render, assets,
                 dlss=None, work_coordinator=None, sleep=time.sleep):
        self.stories, self.store, self.krea = stories, store, krea
        self.prompt_lab, self.composition, self.render, self.assets = prompt_lab, composition, render, assets
        self.dlss = dlss
        self.work_coordinator, self._sleep = work_coordinator, sleep
        self._lock, self._active = RLock(), set()
        self._active_batches = set()
        self._active_video_chains = set()

    @staticmethod
    def _identity_key(value):
        folded = unicodedata.normalize("NFKD", value or "")
        return re.sub(r"[^a-z0-9]+", "", folded.encode("ascii", "ignore").decode().casefold())

    def _inherit_character_images(self, episode, story):
        """Carry accepted casting forward without copying prompts or technical settings."""
        sources = []
        current_index = episode.get("series_episode_index")
        for summary in self.store.list(story["project_id"]):
            try:
                candidate = self.store.get(summary["episode_id"])
            except (FileNotFoundError, ValueError):
                continue
            candidate_index = candidate.get("series_episode_index")
            if current_index is not None and candidate_index is not None and candidate_index >= current_index:
                continue
            sources.append((2, candidate_index or 0, summary["updated_at"], True, candidate))
        ancestor_id = story.get("parent_story_id")
        seen_story_ids = {story["project_id"]}
        depth = 1
        while ancestor_id and ancestor_id not in seen_story_ids:
            seen_story_ids.add(ancestor_id)
            try:
                ancestor = self.stories.store.get(ancestor_id)
            except (FileNotFoundError, ValueError):
                break
            for summary in self.store.list(ancestor_id):
                try:
                    # Prefer the immediate parent to older ancestors, while still
                    # carrying a casting through a chain whose middle episode was
                    # never sent to Fabrication.
                    sources.append((1, -depth, summary["updated_at"], False,
                                    self.store.get(summary["episode_id"])))
                except (FileNotFoundError, ValueError):
                    continue
            ancestor_id = ancestor.get("parent_story_id")
            depth += 1
        sources.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        inherited = 0
        for target in episode["references"]:
            if target["kind"] != "character" or target.get("image_asset_id"):
                continue
            target_name = self._identity_key(target["name"])
            chosen = None
            for _, _, _, same_story, source in sources:
                matches = [reference for reference in source.get("references", [])
                           if reference.get("kind") == "character" and reference.get("image_asset_id")
                           and ((same_story and reference.get("source_id") == target.get("source_id"))
                                or self._identity_key(reference.get("name")) == target_name)]
                if len(matches) == 1:
                    chosen = (source, matches[0])
                    break
            if chosen is None:
                continue
            source, reference = chosen
            asset_id = reference["image_asset_id"]
            target["images"] = [{"asset_id": asset_id,
                                 "label": f"Référence héritée · {reference['name']}"}]
            target["image_asset_id"] = asset_id
            target["image_style"] = deepcopy(reference.get("image_style"))
            target["inherited_image"] = {
                "episode_id": source["episode_id"],
                "reference_id": reference["id"],
                "name": reference["name"],
            }
            inherited += 1
        return inherited

    def create(self, story_id, expected_version):
        with self._lock:
            story = self.stories.get(story_id)
            if story["version"] != expected_version or (story.get("job") or {}).get("status") in {"running", "cancelling"}:
                raise EpisodeConflict("L’histoire a changé ou son écriture est en cours. Rechargez-la avant de la valider.")
            if not story["document"].get("scenario"):
                raise ValueError("Développez et validez un scénario avant la fabrication.")
            series_episode_id = story["document"].get("selected_episode_id")
            digest = fingerprint([series_episode_id, story["document"]["scenario"]]
                                 if series_episode_id else story["document"]["scenario"])
            for existing in self.store.list(story_id):
                if existing["source_hash"] == digest:
                    return self.get(existing["episode_id"])
            value = initial_episode(story, f"episode-{uuid4().hex}")
            self._inherit_character_images(value, story)
            self.store.save(value)
            return self.get(value["episode_id"])

    def get(self, identity):
        with self._lock:
            value = self.store.get(identity)
            value.setdefault("reference_profiles", {})
            value.setdefault("reference_batch", None)
            value.setdefault("dialogue_language", DEFAULT_DIALOGUE_LANGUAGE)
            value.setdefault("video_defaults", video_defaults(value))
            value.setdefault("video_revision", 1)
            value.setdefault("video_chain", None)
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
            chain = value.get("video_chain")
            if chain:
                chain.setdefault("auto_dlss", False)
                chain.setdefault("inter_video_cooldown_seconds", 30)
                chain.setdefault("cooldown_until", None)
                chain.setdefault("cooldown_scene_id", None)
                for item in chain.get("items", []):
                    item.setdefault("dlss_job_id", None)
                    item.setdefault("dlss_status", None)
                    item.setdefault("dlss_error", None)
            if chain and chain.get("status") in {"running", "pausing"} and identity not in self._active_video_chains:
                chain.update(status="interrupted", phase="Chaîne interrompue", error="Le serveur a redémarré pendant la production vidéo.")
                value = self.store.save(value)
            if chain and chain.get("status") == "interrupted" and (chain.get("cooldown_until") or chain.get("cooldown_scene_id")):
                chain.update(cooldown_until=None, cooldown_scene_id=None)
                value = self.store.save(value)
            value = self._reconcile_video_chain(value)
        view = deepcopy(value)
        view.setdefault("visual_revision", 1)
        view.setdefault("style_image", None)
        view.setdefault("style_preset", None)
        view.setdefault("reference_profiles", {})
        view.setdefault("reference_batch", None)
        view.setdefault("dialogue_language", DEFAULT_DIALOGUE_LANGUAGE)
        view.setdefault("video_defaults", video_defaults(value))
        view.setdefault("video_revision", 1)
        view.setdefault("video_chain", None)
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
            series_episode_id = value.get("series_episode_id")
            source_scenario = ((story["document"].get("episode_scenarios") or {}).get(series_episode_id)
                               if series_episode_id else story["document"].get("scenario"))
            source_value = [series_episode_id, source_scenario] if series_episode_id else source_scenario
            view["story_changed"] = fingerprint(source_value) != value["source_hash"]
        except FileNotFoundError:
            view["story_changed"] = True
        for scene in view["scenes"]:
            scene["inherit_video_settings"] = inherits_video_settings(scene)
            scene["effective_render_setup"] = effective_video_setup(value, scene)
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
                    attempts = [attempt for attempt in project.attempts if getattr(attempt, "dlss", None) is None]
                    latest = attempts[-1] if attempts else None
                    scene["video_status"] = latest.status.value if latest else None
                    scene["video_attempt"] = (dict(attempt_id=latest.attempt_id, index=latest.index,
                        status=latest.status.value, output_asset_id=getattr(latest, "output_asset_id", None),
                        error=getattr(latest, "error", None), label=f"Scène {scene['index'] + 1} · {scene['title']}") if latest else None)
                except (KeyError, FileNotFoundError):
                    scene["video_status"] = None
                    scene["video_attempt"] = None
            else:
                scene["video_attempt"] = None
        chain = view.get("video_chain")
        prompts_complete = bool(chain and chain.get("items") and all(
            item.get("status") in {"prompt_ready", "rendering", "succeeded", "video_failed"}
            for item in chain["items"]))
        if chain is not None:
            chain["prompts_complete"] = prompts_complete
        for scene in view["scenes"]:
            scene["dlss_ready"] = bool(prompts_complete and scene.get("video_status") == "succeeded")
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

    def _reconcile_video_chain(self, value):
        chain = value.get("video_chain")
        if not chain:
            return value
        changed = False
        scenes = {scene["id"]: scene for scene in value["scenes"]}
        for item in chain.get("items", []):
            scene = scenes.get(item.get("scene_id"))
            if scene is None:
                continue
            latest = scene.get("preparations", [])[-1] if scene.get("preparations") else None
            latest_is_current = False
            if latest is not None:
                try:
                    latest_is_current = latest.get("input_hash") == fingerprint(scene_inputs(value, scene))
                except ValueError:
                    latest_is_current = False
            recoverable = item.get("status") in {
                "prompt_failed", "prompting", "prompt_ready", "video_failed",
            }
            if recoverable and latest_is_current:
                latest_status = latest.get("status")
                if latest_status == "running" and item.get("status") == "prompt_failed":
                    item.update(status="prompting", phase="Rédaction du prompt", error=None)
                    changed = True
                elif latest_status in {"failed", "interrupted"} and item.get("status") == "prompting":
                    interrupted = latest_status == "interrupted"
                    item.update(status="prompt_failed",
                                phase="Prompt interrompu" if interrupted else "Échec du prompt",
                                error=latest.get("error") or (
                                    "La préparation du prompt a été interrompue."
                                    if interrupted else "La préparation du prompt a échoué."
                                ))
                    changed = True
                elif latest_status == "ready" and (
                    item.get("status") in {"prompt_failed", "prompting"}
                    or item.get("preparation_id") != latest.get("id")
                ):
                    item.update(status="prompt_ready", phase="Prompt corrigé · vidéo à démarrer",
                                error=None, preparation_id=latest.get("id"),
                                render_project_id=latest.get("render_project_id"),
                                attempt_id=None, output_asset_id=None)
                    changed = True

            project_id = item.get("render_project_id")
            attempt_id = item.get("attempt_id")
            if recoverable and latest_is_current and latest and latest.get("status") == "ready" and project_id:
                try:
                    project = self.render.projects.get(project_id)
                    attempts = [candidate for candidate in project.attempts
                                if getattr(candidate, "dlss", None) is None]
                    candidate = attempts[-1] if attempts else None
                except (KeyError, FileNotFoundError, ValueError):
                    candidate = None
                if candidate is not None and (
                    not attempt_id
                    or (
                        item.get("status") in {"prompt_ready", "video_failed"}
                        and candidate.attempt_id != attempt_id
                    )
                ):
                    item.update(attempt_id=candidate.attempt_id, output_asset_id=None)
                    attempt_id = candidate.attempt_id
                    changed = True

            if not attempt_id or not project_id:
                continue
            try:
                attempt = self.render.projects.get(project_id).attempt(attempt_id)
            except (KeyError, FileNotFoundError, ValueError):
                continue
            if attempt.status is H3RenderAttemptStatus.SUCCEEDED and item.get("status") != "succeeded":
                item.update(status="succeeded", phase="Vidéo terminée", error=None,
                            output_asset_id=attempt.output_asset_id)
                changed = True
            elif attempt.status in {H3RenderAttemptStatus.FAILED, H3RenderAttemptStatus.CANCELLED} and item.get("status") != "video_failed":
                item.update(status="video_failed", phase="Échec vidéo",
                            error=attempt.error or "Le rendu vidéo a échoué.")
                changed = True
            elif attempt.status is H3RenderAttemptStatus.CREATED and item.get("status") != "prompt_ready":
                item.update(status="prompt_ready", phase="Prompt prêt · vidéo à démarrer")
                changed = True
            elif attempt.status in {H3RenderAttemptStatus.QUEUED, H3RenderAttemptStatus.RUNNING,
                                    H3RenderAttemptStatus.CANCEL_PENDING} and item.get("status") != "rendering":
                item.update(status="rendering", phase="Rendu vidéo en cours")
                changed = True
        if chain.get("status") in {"completed", "completed_with_errors"}:
            statuses = {item.get("status") for item in chain.get("items", [])}
            if statuses and statuses == {"succeeded"}:
                if chain.get("status") != "completed" or chain.get("phase") != "Toutes les vidéos sont terminées":
                    chain.update(status="completed", phase="Toutes les vidéos sont terminées", error=None)
                    changed = True
            elif statuses & {"prompting", "rendering"}:
                if chain.get("phase") != "Relance manuelle en cours":
                    chain.update(status="completed_with_errors", phase="Relance manuelle en cours", error=None)
                    changed = True
            elif "prompt_ready" in statuses:
                phase = "Correction prête · relance des scènes incomplètes disponible"
                if chain.get("status") != "completed_with_errors" or chain.get("phase") != phase:
                    chain.update(status="completed_with_errors", phase=phase, error=None)
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
            scene["inherit_video_settings"] = False
            scene["render_revision"] += 1
            self.store.save(value)
            return {"render_revision": scene["render_revision"]}

    def save_video_defaults(self, identity, expected_revision, setup):
        with self._lock:
            value = self.store.get(identity)
            if value.get("video_revision", 1) != expected_revision:
                raise EpisodeConflict("Les réglages vidéo communs ont changé. Rechargez la fabrication.")
            value["video_defaults"] = deepcopy(setup)
            value["video_revision"] = expected_revision + 1
            revisions = {}
            for scene in value["scenes"]:
                if not inherits_video_settings(scene):
                    continue
                scene["render_setup"] = effective_video_setup(value, scene)
                scene["render_revision"] += 1
                revisions[scene["id"]] = scene["render_revision"]
            self.store.save(value)
            return {"video_revision": value["video_revision"], "render_revisions": revisions}

    def set_scene_video_inheritance(self, identity, scene_id, expected_revision, inherit):
        with self._lock:
            value = self.store.get(identity)
            scene = self._item(value, "scenes", scene_id)
            if scene["render_revision"] != expected_revision:
                raise EpisodeConflict("Les réglages vidéo ont changé dans un autre onglet. Rechargez la scène.")
            current = effective_video_setup(value, scene)
            scene["inherit_video_settings"] = bool(inherit)
            scene["render_setup"] = effective_video_setup(value, scene) if inherit else current
            scene["render_revision"] += 1
            self.store.save(value)
        return self.get(identity)

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
        policy = (
            self.work_coordinator.policy
            if self.work_coordinator is not None
            else thermal if isinstance(thermal, ThermalPolicy) else ThermalPolicy(**thermal)
        )
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
                           inherit_technical=bool(profile.get("inherit_technical", False)),
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

    def start_video_chain(
        self,
        identity,
        *,
        expected_video_revision,
        request_id,
        scene_ids,
        inter_video_cooldown_seconds=30,
        auto_dlss=False,
    ):
        if type(auto_dlss) is not bool:
            raise ValueError("auto_dlss must be a boolean")
        if auto_dlss and self.dlss is None:
            raise ValueError("Le DLSS local n'est pas configuré.")
        if self.work_coordinator is not None:
            inter_video_cooldown_seconds = self.work_coordinator.settings.remote_video_cooldown_seconds
        elif (
            type(inter_video_cooldown_seconds) is not int
            or not 0 <= inter_video_cooldown_seconds <= 3600
        ):
            raise ValueError("inter_video_cooldown_seconds must be between 0 and 3600")
        with self._lock:
            value = self.store.get(identity)
            existing = value.get("video_chain")
            if existing and existing.get("request_id") == request_id:
                return self.get(identity)
            if existing and existing.get("status") in {"running", "pausing"}:
                raise EpisodeConflict("Une chaîne vidéo est déjà en cours.")
            if value.get("video_revision", 1) != expected_video_revision:
                raise EpisodeConflict("Les réglages vidéo communs ont changé. Rechargez avant le lancement.")
            requested_scene_ids = list(scene_ids)
            chosen = []
            seen = set()
            for scene_id in requested_scene_ids:
                if scene_id in seen:
                    raise ValueError("Une scène ne peut apparaître qu’une fois dans la chaîne.")
                seen.add(scene_id)
                scene = self._item(value, "scenes", scene_id)
                if ((scene.get("job") or {}).get("status") == "running" and len(requested_scene_ids) != 1):
                    raise EpisodeConflict(f"Le prompt de la scène {scene['index'] + 1} est déjà en cours.")
                scene_inputs(value, scene)
                chosen.append(scene)
            if not chosen:
                raise ValueError("Choisissez au moins une scène.")
            chain_id = f"video-chain-{uuid4().hex}"
            attached_prompt = (chosen[0].get("job") or {}).get("status") == "running"
            value["video_chain"] = dict(chain_id=chain_id, request_id=request_id, status="running",
                phase="Prompt en cours · rendu armé" if attached_prompt else "Préparation des prompts",
                error=None, pause_requested=False, auto_dlss=auto_dlss,
                inter_video_cooldown_seconds=inter_video_cooldown_seconds,
                cooldown_until=None, cooldown_scene_id=None,
                items=[dict(scene_id=scene["id"], index=scene["index"], title=scene["title"],
                    status="prompting" if (scene.get("job") or {}).get("status") == "running" else "pending",
                    phase="Prompt en cours · rendu armé" if (scene.get("job") or {}).get("status") == "running" else "En attente",
                    error=None, preparation_id=None,
                    render_project_id=None, attempt_id=None, output_asset_id=None, prompt_attempt=0,
                    dlss_job_id=None, dlss_status=None, dlss_error=None,
                    render_setup=effective_video_setup(value, scene)) for scene in chosen])
            self.store.save(value)
            self._active_video_chains.add(identity)
            try:
                Thread(target=self._video_chain_worker, args=(identity, chain_id), daemon=True,
                       name=f"episode-video-chain-{identity}").start()
            except BaseException:
                self._active_video_chains.discard(identity)
                raise
        return self.get(identity)

    def pause_video_chain(self, identity, chain_id):
        with self._lock:
            value = self.store.get(identity)
            chain = value.get("video_chain")
            if not chain or chain.get("chain_id") != chain_id:
                raise KeyError("Chaîne vidéo introuvable.")
            if chain.get("status") == "running":
                chain.update(status="pausing", phase="Pause après les tâches en cours", pause_requested=True)
                self.store.save(value)
        return self.get(identity)

    def resume_video_chain(self, identity, chain_id):
        with self._lock:
            value = self.store.get(identity)
            value = self._reconcile_video_chain(value)
            chain = value.get("video_chain")
            if not chain or chain.get("chain_id") != chain_id:
                raise KeyError("Chaîne vidéo introuvable.")
            if chain.get("status") in {"running", "pausing"}:
                return self.get(identity)
            if identity in self._active_video_chains:
                raise EpisodeConflict("La chaîne vidéo termine encore une tâche.")
            if any(item.get("status") in {"prompting", "rendering"} for item in chain.get("items", [])):
                raise EpisodeConflict("Une relance manuelle est déjà en cours pour cette chaîne.")
            chain.update(status="running", phase="Reprise de la chaîne", error=None, pause_requested=False)
            for item in chain.get("items", []):
                if item.get("status") == "prompt_failed":
                    item.update(status="pending", phase="À reprendre", error=None,
                                prompt_attempt=int(item.get("prompt_attempt", 0)) + 1)
                elif item.get("status") == "video_failed":
                    item.update(status="prompt_ready", phase="Prompt prêt · vidéo à reprendre", error=None,
                                attempt_id=None, output_asset_id=None)
            self.store.save(value)
            self._active_video_chains.add(identity)
            try:
                Thread(target=self._video_chain_worker, args=(identity, chain_id), daemon=True,
                       name=f"episode-video-chain-{identity}").start()
            except BaseException:
                self._active_video_chains.discard(identity)
                raise
        return self.get(identity)

    def _video_chain_change(self, identity, chain_id, change):
        with self._lock:
            value = self.store.get(identity)
            chain = value.get("video_chain")
            if not chain or chain.get("chain_id") != chain_id:
                raise EpisodeConflict("La chaîne vidéo a été remplacée.")
            change(value, chain)
            self.store.save(value)

    def _video_chain_snapshot(self, identity, chain_id):
        with self._lock:
            value = self.store.get(identity)
            chain = value.get("video_chain")
            if not chain or chain.get("chain_id") != chain_id:
                raise EpisodeConflict("La chaîne vidéo a été remplacée.")
            return deepcopy(value), deepcopy(chain)

    def _video_chain_paused(self, identity, chain_id):
        _value, chain = self._video_chain_snapshot(identity, chain_id)
        return bool(chain.get("pause_requested"))

    def _video_item(self, chain, scene_id):
        return next(item for item in chain["items"] if item["scene_id"] == scene_id)

    def _wait_scene_job(self, identity, scene_id, chain_id):
        while True:
            with self._lock:
                scene = self._item(self.store.get(identity), "scenes", scene_id)
            job = scene.get("job") or {}
            if job.get("status") != "running":
                return deepcopy(scene), deepcopy(job)
            self._sleep(0.1)

    def _prepare_chain_prompt(self, identity, chain_id, scene_id):
        with self._lock:
            value = self.store.get(identity)
            scene = self._item(value, "scenes", scene_id)
            chain = value.get("video_chain")
            if not chain or chain.get("chain_id") != chain_id:
                raise EpisodeConflict("La chaîne vidéo a été remplacée.")
            item = self._video_item(chain, scene_id)
            inputs_hash = fingerprint(scene_inputs(value, scene))
            latest = scene["preparations"][-1] if scene["preparations"] else None
            if latest and latest.get("status") == "ready" and latest.get("input_hash") == inputs_hash:
                return latest
            attached_job = (scene.get("job") or {}).get("status") == "running"
            if attached_job:
                self._video_item(chain, scene_id).update(
                    status="prompting", phase="Prompt en cours · rendu armé", error=None,
                    preparation_id=latest.get("id") if latest else None,
                )
                self.store.save(value)
            resume = bool(latest and latest.get("input_hash") == inputs_hash
                          and latest.get("status") in {"failed", "interrupted"})
            revision = scene["revision"]
            prompt_attempt = int(item.get("prompt_attempt", 0))
        if attached_job:
            scene, job = self._wait_scene_job(identity, scene_id, chain_id)
            latest = scene["preparations"][-1] if scene["preparations"] else None
            if job.get("status") != "succeeded" or not latest or latest.get("status") != "ready":
                raise ValueError(job.get("error") or "La préparation du prompt a échoué ; le rendu programmé est annulé.")
            if latest.get("input_hash") != fingerprint(scene_inputs(self.store.get(identity), scene)):
                raise ValueError("Les entrées de la scène ont changé ; le rendu programmé est annulé.")
            return latest
        self._video_chain_change(identity, chain_id, lambda _value, chain:
            self._video_item(chain, scene_id).update(status="prompting", phase="Rédaction du prompt", error=None))
        self.prepare_scene(identity, scene_id, revision,
                           f"{chain_id}-prompt-{scene_id}-{prompt_attempt}", resume=resume)
        scene, job = self._wait_scene_job(identity, scene_id, chain_id)
        latest = scene["preparations"][-1] if scene["preparations"] else None
        if job.get("status") != "succeeded" or not latest or latest.get("status") != "ready":
            raise ValueError(job.get("error") or "La préparation du prompt a échoué.")
        return latest

    def _video_attempt_settings(self, setup):
        raw = setup["settings"]
        bunny = H3BunnySettings(**setup["bunny"]) if setup.get("bunny") else None
        video_loras = H3VideoLoraStack.from_dict(setup.get("video_loras")) if setup.get("video_loras") else None
        video_lora = H3VideoLoraSelection(**setup["video_lora"]) if setup.get("video_lora") else None
        # Historical episode setups already stored a deterministic per-scene
        # seed before this flag existed; preserve their former reuse behavior.
        seed_locked = bool(setup.get("seed_locked", True))
        seed = int(raw.get("seed") or 0) if seed_locked else self.render.new_seed()
        settings = VideoLabSettings(aspect_ratio=VideoAspectRatio(raw["aspect_ratio"]),
            megapixels=raw["megapixels"], duration_seconds=raw["duration_seconds"],
            steps=raw["steps"], seed=seed, seed_locked=seed_locked)
        return settings, bunny, video_loras, video_lora

    def _start_chain_video(
        self,
        identity,
        chain_id,
        scene_id,
        preparation,
        setup,
        *,
        cooldown_after,
    ):
        project_id = preparation["render_project_id"]
        project = self.render.projects.get(project_id)
        item = self._video_item(self._video_chain_snapshot(identity, chain_id)[1], scene_id)
        attempt = None
        if item.get("attempt_id"):
            try:
                candidate = project.attempt(item["attempt_id"])
                if candidate.status in {H3RenderAttemptStatus.CREATED, H3RenderAttemptStatus.QUEUED,
                                         H3RenderAttemptStatus.RUNNING, H3RenderAttemptStatus.CANCEL_PENDING,
                                         H3RenderAttemptStatus.SUCCEEDED}:
                    attempt = candidate
            except (KeyError, ValueError):
                pass
        if attempt is None:
            settings, bunny, video_loras, video_lora = self._video_attempt_settings(setup)
            project = self.render.prepare_attempt(project_id, prompt=project.current_prompt, settings=settings,
                music_enabled=bool(setup.get("music_enabled", False)),
                spectrum_enabled=bool(setup.get("spectrum_enabled", False)),
                initial_megapixels=setup.get("initial_megapixels", 0.2),
                force_upscale=bool(setup.get("force_upscale", False)),
                recipe_id=setup["recipe"]["id"], recipe_version=setup["recipe"]["version"],
                bunny=bunny, checkpoint=setup.get("checkpoint"), video_loras=video_loras,
                video_lora=video_lora)
            attempt = project.attempts[-1]
            self._video_chain_change(identity, chain_id, lambda _value, chain:
                self._video_item(chain, scene_id).update(render_project_id=project_id,
                    attempt_id=attempt.attempt_id, status="prompt_ready", phase="Prompt prêt"))
        if attempt.status is not H3RenderAttemptStatus.CREATED:
            self._video_chain_change(identity, chain_id, lambda _value, chain:
                self._video_item(chain, scene_id).update(status="rendering", phase="Rendu vidéo en cours", error=None))
            return project_id, attempt.attempt_id, scene_id
        while True:
            if self._video_chain_paused(identity, chain_id):
                return None
            try:
                self.render.queue_attempt(
                    project_id,
                    attempt.attempt_id,
                    operation_label=f"H3 / REF2V · {item['index'] + 1} · {item['title']}",
                )
                break
            except ValueError as error:
                if "déjà actif" not in str(error):
                    raise
                self._sleep(0.5)
        self._video_chain_change(identity, chain_id, lambda _value, chain:
            self._video_item(chain, scene_id).update(status="rendering", phase="Rendu vidéo en cours", error=None))
        Thread(target=self._execute_chain_attempt,
               args=(identity, chain_id, scene_id, project_id, attempt.attempt_id, cooldown_after), daemon=True,
               name=f"episode-video-{scene_id}").start()
        return project_id, attempt.attempt_id, scene_id

    def _execute_chain_attempt(
        self,
        identity,
        chain_id,
        scene_id,
        project_id,
        attempt_id,
        cooldown_after,
    ):
        # Inter-video rest is now enforced by the global remote lane before the
        # next video, independently of the workshop that submitted it.
        value = self.store.get(identity)
        scene = self._item(value, "scenes", scene_id)
        project = self.render.execute_attempt(
            project_id,
            attempt_id,
            operation_label=f"H3 / REF2V · {scene['index'] + 1} · {scene['title']}",
        )
        project = project or self.render.projects.get(project_id)
        attempt = project.attempt(attempt_id)
        if attempt.status is H3RenderAttemptStatus.SUCCEEDED:
            self._queue_chain_dlss(identity, chain_id, scene_id, project_id, attempt_id)

    @staticmethod
    def _automatic_video_dlss_settings():
        # Keep this identical to the quick H3 / REF2V action in dlss-lab.js.
        return DlssSettings(
            size="1.724", intensity=0.2, tone=0, structure=0.2, skin=0,
            detail=1, style="Natural", strict_neural=False, interpolate=True,
            hdr=False, codec="H.264 (NVIDIA NVENC)",
        )

    def _queue_chain_dlss(self, identity, chain_id, scene_id, project_id, attempt_id):
        try:
            _value, chain = self._video_chain_snapshot(identity, chain_id)
            item = self._video_item(chain, scene_id)
            if not chain.get("auto_dlss") or item.get("dlss_job_id") or self.dlss is None:
                return
            jobs = self.dlss.list(owner="ref2v", owner_id=project_id)
            job = next((candidate for candidate in jobs if (
                (candidate.get("snapshot") or {}).get("root_attempt_id") == attempt_id
                or (candidate.get("request") or {}).get("attempt_id") == attempt_id
            )), None)
            if job is None:
                request_key = f"{chain_id}:{scene_id}:{attempt_id}"
                request_id = "episode-" + hashlib.sha256(request_key.encode()).hexdigest()[:32]
                job = self.dlss.queue(
                    owner="ref2v",
                    owner_id=project_id,
                    attempt_id=attempt_id,
                    settings=self._automatic_video_dlss_settings(),
                    request_id=request_id,
                )
            self._video_chain_change(identity, chain_id, lambda _value, current:
                self._video_item(current, scene_id).update(
                    dlss_job_id=job["job_id"], dlss_status=job.get("status"),
                    dlss_error=job.get("error"),
                ))
        except EpisodeConflict:
            return
        except Exception as error:
            try:
                self._video_chain_change(identity, chain_id, lambda _value, current:
                    self._video_item(current, scene_id).update(
                        dlss_status="failed", dlss_error=str(error) or type(error).__name__,
                    ))
            except EpisodeConflict:
                pass

    def _wait_chain_video(self, identity, chain_id, active):
        if active is None:
            return
        project_id, attempt_id, scene_id = active
        while True:
            attempt = self.render.projects.get(project_id).attempt(attempt_id)
            if attempt.status not in {H3RenderAttemptStatus.CREATED, H3RenderAttemptStatus.QUEUED,
                                      H3RenderAttemptStatus.RUNNING, H3RenderAttemptStatus.CANCEL_PENDING}:
                break
            self._sleep(0.2)
        if attempt.status is H3RenderAttemptStatus.SUCCEEDED:
            self._video_chain_change(identity, chain_id, lambda _value, chain:
                self._video_item(chain, scene_id).update(status="succeeded", phase="Vidéo terminée",
                    output_asset_id=attempt.output_asset_id, error=None))
            # The execution thread normally queues it first; this is the
            # idempotent fallback if completion was reconciled a little later.
            self._queue_chain_dlss(identity, chain_id, scene_id, project_id, attempt_id)
        else:
            self._video_chain_change(identity, chain_id, lambda _value, chain:
                self._video_item(chain, scene_id).update(status="video_failed", phase="Échec vidéo",
                    error=attempt.error or "Le rendu vidéo a échoué."))

    def _pause_video_chain_now(self, identity, chain_id):
        self._video_chain_change(identity, chain_id, lambda _value, chain:
            chain.update(status="paused", phase="Chaîne en pause", pause_requested=False, error=None))

    def _video_chain_worker(self, identity, chain_id):
        active_videos = []
        try:
            _value, initial = self._video_chain_snapshot(identity, chain_id)
            for original in initial["items"]:
                scene_id = original["scene_id"]
                _value, current_chain = self._video_chain_snapshot(identity, chain_id)
                current = self._video_item(current_chain, scene_id)
                if current.get("status") == "succeeded":
                    continue
                if self._video_chain_paused(identity, chain_id):
                    for active_video in active_videos:
                        self._wait_chain_video(identity, chain_id, active_video)
                    self._pause_video_chain_now(identity, chain_id)
                    return
                try:
                    preparation = self._prepare_chain_prompt(identity, chain_id, scene_id)
                    self._video_chain_change(identity, chain_id, lambda _value, chain:
                        self._video_item(chain, scene_id).update(status="prompt_ready", phase="Prompt prêt",
                            preparation_id=preparation["id"], render_project_id=preparation["render_project_id"], error=None))
                except Exception as error:
                    self._video_chain_change(identity, chain_id, lambda _value, chain, error=error:
                        self._video_item(chain, scene_id).update(status="prompt_failed", phase="Échec du prompt", error=str(error)))
                    continue
                if self._video_chain_paused(identity, chain_id):
                    for active_video in active_videos:
                        self._wait_chain_video(identity, chain_id, active_video)
                    self._pause_video_chain_now(identity, chain_id)
                    return
                try:
                    value, refreshed_chain = self._video_chain_snapshot(identity, chain_id)
                    refreshed = self._video_item(refreshed_chain, scene_id)
                    active_video = self._start_chain_video(identity, chain_id, scene_id, preparation,
                        refreshed.get("render_setup") or effective_video_setup(value, self._item(value, "scenes", scene_id)),
                        cooldown_after=0)
                    if active_video is not None:
                        active_videos.append(active_video)
                except Exception as error:
                    self._video_chain_change(identity, chain_id, lambda _value, chain, error=error:
                        self._video_item(chain, scene_id).update(status="video_failed", phase="Échec vidéo", error=str(error)))
            for active_video in active_videos:
                self._wait_chain_video(identity, chain_id, active_video)
            if self._video_chain_paused(identity, chain_id):
                self._pause_video_chain_now(identity, chain_id)
                return
            _value, chain = self._video_chain_snapshot(identity, chain_id)
            failed = any(item["status"] in {"prompt_failed", "video_failed"} for item in chain["items"])
            self._video_chain_change(identity, chain_id, lambda _value, current:
                current.update(status="completed_with_errors" if failed else "completed",
                    phase="Chaîne terminée avec des erreurs" if failed else "Toutes les vidéos sont terminées",
                    error=None, pause_requested=False))
        except Exception as error:
            try:
                self._video_chain_change(identity, chain_id, lambda _value, chain:
                    chain.update(status="failed", phase="Échec de la chaîne", error=str(error), pause_requested=False))
            except EpisodeConflict:
                pass
        finally:
            with self._lock:
                self._active_video_chains.discard(identity)

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
                    render_setup=effective_video_setup(value, scene))
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
