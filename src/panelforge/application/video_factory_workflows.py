"""Factory adapter to the existing prompt, H3, DLSS and social application services."""
from copy import deepcopy
from dataclasses import asdict
import time
from uuid import uuid4

from panelforge.domain import (
    CookbookBinding, CompositionStage, CreativeFreedomAxes, ReferenceUse, ReferenceEvidencePolicy,
    VideoAspectRatio, VideoLabSettings, H3RenderProject, H3RenderInputMode, H3VideoLoraSelection,
)
from panelforge.domain.video_preparation import (
    ClassicCinematicSettings, CombatSettings, SensualSettings,
    validate_cinematic_settings, validate_combat_settings, validate_sensual_settings,
)
from panelforge.domain.h3_bunny import H3BunnySettings, bunny_geometry
from panelforge.domain.h3_render import H3VideoLoraStack
from panelforge.domain.h3_render import derive_h3_render_input_mode
from panelforge.domain.prompt_composition import PreparationIntent
from panelforge.domain.prompt_writer import supports_writer_model
from panelforge.domain.dlss import DlssSettings
from panelforge.domain.social_lab import SocialLanguage
from panelforge.domain.episodes import scene_inputs, effective_video_setup, fingerprint as episode_fingerprint
from panelforge.domain.video_factory import configuration, ROLE_USES, readiness, merge_settings
from .prompt_lab import NewReference, StreamEventKind
from .production_resources import llm_compute_resource
from .video_factory import FactoryCancelled, FactoryWait


class FactoryWorkflows:
    def __init__(self, *, prompt_lab, composition, render, dlss, social, episodes, assets, coordinator):
        self.prompt_lab, self.composition, self.render = prompt_lab, composition, render
        self.dlss, self.social, self.episodes, self.assets = dlss, social, episodes, assets
        self.coordinator = coordinator
        self.machines = {}

    @staticmethod
    def input_mode(config):
        if config["mode"] == "ref2v":
            return H3RenderInputMode.REF2VA
        roles = {ref["role"] for ref in config["references"]}
        return derive_h3_render_input_mode("first_frame" in roles, "last_frame" in roles)

    def validate(self, config, launching=False):
        for ref in config["references"]:
            if not self.assets.get(ref["asset_id"]).media_type.startswith("image/"):
                raise ValueError("Les références doivent être des images.")
        setup = config["render"]
        settings = setup["settings"]
        validated_settings = VideoLabSettings(aspect_ratio=VideoAspectRatio(settings["aspect_ratio"]),
                         megapixels=settings["megapixels"], duration_seconds=settings["duration_seconds"],
                         steps=settings["steps"], seed=int(settings.get("seed", 0)),
                         seed_locked=bool(setup.get("seed_locked", True)))
        if setup.get("bunny"):
            H3BunnySettings(**setup["bunny"])
            bunny_geometry(validated_settings, setup["initial_megapixels"])
        if setup.get("video_loras"):
            H3VideoLoraStack.from_dict(setup["video_loras"]).validate_mode(bool(setup.get("bunny")))
        if launching:
            if readiness(config):
                raise ValueError("La préparation est incomplète.")
            mode = self.input_mode(config)
            self.render.workflow_for_mode(mode, setup["recipe"]["id"], setup["recipe"]["version"])
            profile = config["profile"]
            profile_spec = self.prompt_lab.get_profile(profile["id"], profile["version"])
            for key, cls, check in (
                ("cinematic_settings", ClassicCinematicSettings, validate_cinematic_settings),
                ("combat_settings", CombatSettings, validate_combat_settings),
                ("sensual_settings", SensualSettings, validate_sensual_settings),
            ):
                check(profile_spec.preparation, cls(**config[key]) if config.get(key) else None)
            CreativeFreedomAxes(**config["creative_axes"])
            book = config["cookbook"]
            book_spec = self.composition.cookbooks.get(book["id"], book["version"])
            expected = getattr(book_spec, "profile_id", None)
            if expected and expected != profile_spec.profile_id:
                raise ValueError("Le profil ne correspond pas au parcours de préparation.")
            if config["dlss"]["enabled"] and self.dlss is None:
                raise ValueError("DLSS indisponible.")
            if config["social"]["enabled"] and self.social is None:
                raise ValueError("Texte Instagram indisponible.")

    def source_issues(self, item):
        return list(item.get("source_issues", []))

    def available_lanes(self):
        if self.coordinator is None:
            self.machines = {}
            return ("local_gpu", "remote_gpu")
        status = self.coordinator.public_status()
        self.machines = {key: {field: value.get(field) for field in
                         ("state", "paused", "queue_count", "operation", "cooldown_remaining_seconds")}
                         for key, value in status["machines"].items()}
        return tuple(key for key, value in status["machines"].items()
                     if not value["paused"] and value["state"] == "idle" and not value["queue_count"])

    @staticmethod
    def recoverable(item, stage):
        return (item.get("recover_stage") == stage and
                bool(item["runtime"].get("attempt_id" if stage == "video" else "dlss_job_id"))
                and stage in {"video", "dlss"})

    def lane(self, item, stage):
        if stage == "video":
            return "remote_gpu"
        if stage == "dlss":
            return "local_gpu"
        config = item["config"]
        model = config["social"]["model_id"] if stage == "social" else config[
            "plan_model_id" if stage == "plan" else "writer_model_id"]
        return llm_compute_resource(model).value

    def capture_session(self, identity, overrides=None):
        session = self.prompt_lab.get_session(identity)
        try:
            composition = self.composition.get(identity)
        except (KeyError, FileNotFoundError):
            composition = None
        ref2v = "ref2v" in session.profile_id
        config = configuration("ref2v" if ref2v else "h3")
        config.update(profile={"id": session.profile_id, "version": session.profile_version},
                      cookbook={"id": composition.cookbook.cookbook_id, "version": composition.cookbook.version} if composition else config["cookbook"],
                      plan_model_id=session.model_id, writer_model_id=(composition.writer_model_id if composition else None) or session.model_id,
                      references=[dict(asset_id=ref.asset_id, role=ref.role, label=ref.label,
                                       evidence_policy=ref.evidence_policy.value) for ref in session.references])
        for key in ("cinematic_settings", "sensual_settings", "combat_settings"):
            value = getattr(session, key, None)
            config[key] = asdict(value) if value else None
            if value:
                config["shot_count"] = value.shot_count
        intent = composition.preparation_intent if composition else None
        if intent:
            config.update(intention=intent.source_text, creative_freedom=intent.creative_freedom,
                          creative_axes=asdict(intent.creative_axes) if intent.creative_axes else config["creative_axes"],
                          creative_audacity=intent.creative_audacity)
        elif session.active_brief_revision:
            config["intention"] = session.active_brief_revision.source_text
        config["brief_variant_id"] = session.brief_variant_id
        config["brief_variant_version"] = session.brief_variant_version
        runtime, outputs = {"source_session_id": identity}, {}
        plan = composition.document(CompositionStage.BEAT_SHEET).active_revision if composition else None
        if plan:
            runtime["saved_plan"] = plan.content
            book = self.composition.cookbooks.get(config["cookbook"]["id"], config["cookbook"]["version"])
            if book.preparation_steps < 3:
                outputs["plan"] = {"text": plan.content}
        reference_plan = composition.document(CompositionStage.REFERENCE_PLAN).active_revision if composition else None
        if reference_plan:
            runtime["saved_reference_plan"] = reference_plan.content
        final = composition.document(CompositionStage.FINAL_PROMPT).active_revision if composition else None
        if final:
            config["final_prompt"] = final.content
            outputs["prompt"] = {"text": final.content}
            project = self.render.projects.find_source_revision(identity, final.revision_id)
            if project:
                attempt = next((attempt for attempt in reversed(project.attempts)
                                if attempt.status.value == "succeeded" and not attempt.dlss), None)
                latest = project.attempts[-1] if project.attempts else None
                if latest:
                    config["render"] = self.setup_from_attempt(latest, config["render"])
                if attempt:
                    outputs["video"] = self.video_output(project, attempt)
                    runtime.update(render_project_id=project.project_id, attempt_id=attempt.attempt_id)
        if overrides:
            updated = merge_settings(config, overrides)
            changed = {key for key in updated if updated[key] != config.get(key)}
            inputs_changed = changed - {"render", "final_prompt", "dlss", "social", "preset", "preset_origin"}
            if inputs_changed:
                runtime, outputs = {}, {}
                if updated["final_prompt"] == config["final_prompt"]:
                    updated["final_prompt"] = ""
            if changed & {"render", "final_prompt"}:
                outputs.pop("video", None)
                runtime.pop("render_project_id", None)
                runtime.pop("attempt_id", None)
            if "final_prompt" in changed:
                outputs.pop("prompt", None)
            config = updated
        return dict(name=config["intention"].split("\n")[0][:100] or "Parcours vidéo",
                    config=config, source={"kind": "session", "id": identity,
                    "view": "ref2v-direct" if ref2v else "i2v-direct"}, runtime=runtime, outputs=outputs)

    @staticmethod
    def setup_from_attempt(attempt, base):
        setup = deepcopy(base)
        setup["settings"] = asdict(attempt.settings)
        setup["settings"]["aspect_ratio"] = attempt.settings.aspect_ratio.value
        setup["settings"]["seed"] = str(attempt.settings.seed)
        if attempt.recipe:
            setup["recipe"] = {"id": attempt.recipe.recipe_id, "version": attempt.recipe.version}
        for key in ("music_enabled", "spectrum_enabled", "initial_megapixels", "force_upscale", "checkpoint"):
            setup[key] = getattr(attempt, key)
        for key in ("bunny", "video_loras", "video_lora"):
            value = getattr(attempt, key)
            setup[key] = asdict(value) if value else None
        setup["seed_locked"] = attempt.settings.seed_locked
        return setup

    def capture_episode(self, identity, scene_ids=None, auto_dlss=None):
        episode = self.episodes.store.get(identity)
        entries = []
        for scene in episode["scenes"]:
            if scene_ids is not None and scene["id"] not in scene_ids:
                continue
            issues = []
            try:
                inputs = scene_inputs(episode, scene)
            except ValueError as error:
                issues.append(str(error))
                try:
                    inputs = scene_inputs(episode, scene, require_images=False)
                except ValueError:
                    inputs = dict(source_text=scene["intention"], references=[], shot_count=scene["shot_count"],
                                  plan_model_id=scene["plan_model_id"], writer_model_id=scene["writer_model_id"],
                                  audacity=scene["audacity"], cookbook=episode["cookbook"],
                                  creative_axes=scene.get("creative_axes", configuration()["creative_axes"]))
            config = configuration("ref2v")
            config.update(intention=inputs["source_text"], plan_model_id=inputs["plan_model_id"],
                          writer_model_id=inputs["writer_model_id"], shot_count=inputs["shot_count"],
                          cinematic_settings={"shot_count": inputs["shot_count"]},
                          creative_axes=inputs.get("creative_axes", config["creative_axes"]),
                          creative_audacity=inputs["audacity"], cookbook=deepcopy(inputs["cookbook"]),
                          references=[dict(asset_id=ref["asset_id"], role=ref["role"], label=ref["name"])
                                      for ref in inputs["references"] if ref.get("asset_id")],
                          render=effective_video_setup(episode, scene))
            config["render"]["settings"]["seed"] = str(config["render"]["settings"].get("seed", 0))
            axes = config["creative_axes"]
            levels = (0, 35, 65, 90)
            config["creative_freedom"] = round(sum(levels[axes[key]] for key in ("scene_life", "camera", "extra_motion")) / 3)
            config["dlss"]["enabled"] = bool(auto_dlss if auto_dlss is not None else
                                            (episode.get("video_chain") or {}).get("auto_dlss", True))
            runtime, outputs = {}, {}
            preparation = next((p for p in reversed(scene.get("preparations", []))
                                if p.get("input_hash") == episode_fingerprint(inputs) and p.get("session_id")), None)
            if preparation and not issues:
                saved = self.capture_session(preparation["session_id"])
                runtime, outputs = saved["runtime"], saved["outputs"]
                if saved["config"]["render"] != config["render"]:
                    outputs.pop("video", None)
                    runtime.pop("render_project_id", None)
                    runtime.pop("attempt_id", None)
                if saved["config"].get("final_prompt"):
                    config["final_prompt"] = saved["config"]["final_prompt"]
            runtime["episode_inputs"] = deepcopy(inputs)
            runtime["episode_preparation_id"] = scene["preparations"][-1]["id"] if scene.get("preparations") else None
            entries.append(dict(name=scene["title"], config=config, issues=issues, runtime=runtime, outputs=outputs,
                                source=dict(kind="episode", id=identity, scene_id=scene["id"],
                                            group=episode["title"], index=scene["index"],
                                            story_id=episode["story_id"], view="stories")))
        if not entries:
            raise ValueError("Aucune scène sélectionnée.")
        return entries

    def run(self, item, stage, checkpoint, cancelled, progress):
        if cancelled():
            self.cancel(item)
            raise FactoryCancelled()
        output = getattr(self, "_" + stage)(item, checkpoint, cancelled, progress)
        if stage == "video" and item["source"].get("kind") == "episode":
            inputs = item["runtime"].get("episode_inputs")
            source = item["source"]
            if inputs:
                try:
                    linked = self.episodes.register_factory_video(source["id"], source["scene_id"],
                        factory_id=item["id"], inputs=inputs, expected_preparation_id=item["runtime"].get("episode_preparation_id"),
                        session_id=item["runtime"].get("session_id") or item["runtime"].get("source_session_id"),
                        project_id=output["project_id"], render_setup=item["config"]["render"])
                    if not linked:
                        output["source_warning"] = "L’histoire a changé depuis l’envoi. Cette vidéo reste disponible dans l’usine."
                except (FileNotFoundError, KeyError, ValueError) as error:
                    output["source_warning"] = "Vidéo terminée ; rattachement à l’histoire à vérifier : " + str(error)
        return output

    @staticmethod
    def _consume(stream, cancelled, progress):
        try:
            for event in stream:
                if cancelled():
                    raise FactoryCancelled()
                if event.kind is StreamEventKind.TRUNCATED:
                    raise ValueError("Réponse tronquée : l’étape doit être reprise.")
                if event.kind is StreamEventKind.STATUS:
                    progress(getattr(event, "text", "") or "Préparation en cours",
                             getattr(event, "progress", None))
                if getattr(event, "error", None):
                    raise ValueError(event.error)
        finally:
            close = getattr(stream, "close", None)
            if close:
                close()

    def _session(self, item, checkpoint, cancelled, progress):
        config, runtime = item["config"], item["runtime"]
        if runtime.get("session_id"):
            session = self.prompt_lab.get_session(runtime["session_id"])
        else:
            def settings(key, cls):
                return cls(**config[key]) if config.get(key) else None
            session = self.prompt_lab.create_session(
                model_id=config["plan_model_id"], profile_id=config["profile"]["id"],
                profile_version=config["profile"]["version"],
                references=tuple(NewReference(asset_id=ref["asset_id"], role=ref["role"],
                    label=ref.get("label") or "Image", uses=(ReferenceUse(ROLE_USES[ref["role"]]),),
                    evidence_policy=ReferenceEvidencePolicy(ref.get("evidence_policy", "full")))
                    for ref in config["references"]),
                cinematic_settings=settings("cinematic_settings", ClassicCinematicSettings),
                combat_settings=settings("combat_settings", CombatSettings),
                sensual_settings=settings("sensual_settings", SensualSettings),
                brief_variant_id=config.get("brief_variant_id"), brief_variant_version=config.get("brief_variant_version"))
            checkpoint(session_id=session.session_id)
            runtime["session_id"] = session.session_id
        book = self.composition.cookbooks.get(config["cookbook"]["id"], config["cookbook"]["version"])
        steps = getattr(book, "preparation_steps", 3)
        intent = PreparationIntent(source_text=config["intention"] or config["final_prompt"],
                                  creative_axes=CreativeFreedomAxes(**config["creative_axes"]),
                                  creative_audacity=config["creative_audacity"],
                                  creative_freedom=config["creative_freedom"])
        if steps == 3 and session.approved_brief_revision_id is None:
            if session.active_brief_revision is None:
                self._consume(self.prompt_lab.stream_structure_brief(session.session_id, intent.source_text,
                    intent.creative_freedom, creative_axes=intent.creative_axes,
                    creative_audacity=intent.creative_audacity), cancelled, progress)
            self.prompt_lab.approve_brief(session.session_id)
        bindings = tuple(CookbookBinding(slot.slot_id, tuple(ref.reference_id for ref in session.references
                            if slot.slot_id == "references" or ref.role == slot.slot_id)) for slot in book.slots)
        self.composition.configure(session.session_id, config["cookbook"]["id"], config["cookbook"]["version"],
                                   bindings, preparation_intent=intent if steps < 3 else None,
                                   writer_model_id=config["writer_model_id"] if supports_writer_model(
                                       config["cookbook"]["id"], config["cookbook"]["version"]) else None)
        return session, book

    def _plan(self, item, checkpoint, cancelled, progress):
        session, book = self._session(item, checkpoint, cancelled, progress)
        for stage in (CompositionStage.REFERENCE_PLAN, CompositionStage.BEAT_SHEET):
            if stage.value not in book.stages:
                continue
            document = self.composition.get(session.session_id).document(stage)
            if document.approved_revision_id:
                continue
            if document.active_revision is None:
                saved = item["runtime"].get("saved_plan" if stage is CompositionStage.BEAT_SHEET else "saved_reference_plan")
                if saved:
                    self.composition.edit(session.session_id, stage, saved)
                else:
                    self._consume(self.composition.stream_generate(session.session_id, stage), cancelled, progress)
            if cancelled():
                raise FactoryCancelled()
            self.composition.approve(session.session_id, stage)
        document = self.composition.get(session.session_id).document(CompositionStage.BEAT_SHEET)
        return dict(session_id=session.session_id, text=document.active_revision.content if document.active_revision else "",
                    note=None if document.active_revision else "Recette sans plan intermédiaire")

    def _prompt(self, item, checkpoint, cancelled, progress):
        session, book = self._session(item, checkpoint, cancelled, progress)
        saved = item["runtime"].get("saved_plan")
        plan = self.composition.get(session.session_id).document(CompositionStage.BEAT_SHEET)
        if saved and CompositionStage.BEAT_SHEET.value in book.stages and not plan.approved_revision_id:
            if plan.active_revision is None:
                self.composition.edit(session.session_id, CompositionStage.BEAT_SHEET, saved)
            self.composition.approve(session.session_id, CompositionStage.BEAT_SHEET)
        document = self.composition.get(session.session_id).document(CompositionStage.FINAL_PROMPT)
        if not document.approved_revision_id:
            if document.active_revision is None:
                stream = (self.composition.stream_generate_super_fast(session.session_id)
                          if getattr(book, "execution_mode", "supervised") != "supervised" else
                          self.composition.stream_generate(session.session_id, CompositionStage.FINAL_PROMPT))
                self._consume(stream, cancelled, progress)
            if cancelled():
                raise FactoryCancelled()
            self.composition.approve(session.session_id, CompositionStage.FINAL_PROMPT)
        final = self.composition.get(session.session_id).document(CompositionStage.FINAL_PROMPT).active_revision
        return dict(text=final.content, session_id=session.session_id)

    def _project(self, item, checkpoint, cancelled, progress):
        runtime, config = item["runtime"], item["config"]
        if runtime.get("render_project_id"):
            return self.render.get(runtime["render_project_id"])
        prompt = item["steps"]["prompt"]["output"].get("text") or config["final_prompt"]
        if runtime.get("session_id") and not config["final_prompt"]:
            project = self.render.get_or_create_from_session(runtime["session_id"])
        else:
            # Direct final prompts retain their own explicit asset mapping and provenance.
            profile = self.prompt_lab.get_profile(config["profile"]["id"], config["profile"]["version"])
            refs = config["references"]
            first = next((r for r in refs if r["role"] == "first_frame"), None)
            last = next((r for r in refs if r["role"] == "last_frame"), None)
            mode = self.input_mode(config)
            project = H3RenderProject(
                project_id=f"h3-render-{uuid4().hex}", source_session_id=runtime.get("session_id") or runtime.get("source_session_id") or item["id"],
                source_prompt_revision_id=f"{item['id']}:{item['revision']}", model_id=config["writer_model_id"],
                input_mode=mode, current_prompt=prompt,
                first_frame_asset_id=first["asset_id"] if first and mode is not H3RenderInputMode.REF2VA else None,
                first_frame_label=first.get("label", "Première frame") if first and mode is not H3RenderInputMode.REF2VA else None,
                last_frame_asset_id=last["asset_id"] if last and mode is not H3RenderInputMode.REF2VA else None,
                last_frame_label=last.get("label", "Dernière frame") if last and mode is not H3RenderInputMode.REF2VA else None,
                reference_asset_ids=tuple(r["asset_id"] for r in refs) if mode is H3RenderInputMode.REF2VA else (),
                reference_labels=tuple(r.get("label") or "Image" for r in refs) if mode is H3RenderInputMode.REF2VA else (),
                preparation=profile.preparation, revision_version=self.render.default_revision_version(mode, profile.preparation),
                cinematic_settings=ClassicCinematicSettings(**config["cinematic_settings"]) if config["cinematic_settings"] else None,
                combat_settings=CombatSettings(**config["combat_settings"]) if config["combat_settings"] else None,
                sensual_settings=SensualSettings(**config["sensual_settings"]) if config["sensual_settings"] else None,
                dialogue_level=config["creative_axes"]["dialogue"])
            project = self.render.projects.create(project)
        checkpoint(render_project_id=project.project_id)
        runtime["render_project_id"] = project.project_id
        return project

    @staticmethod
    def video_output(project, attempt):
        return dict(asset_id=attempt.output_asset_id, project_id=project.project_id, attempt_id=attempt.attempt_id,
                    owner="ref2v" if project.input_mode is H3RenderInputMode.REF2VA else "h3",
                    keyframes=[frame.asset_id for frame in attempt.keyframes])

    def _video(self, item, checkpoint, cancelled, progress):
        runtime, config = item["runtime"], item["config"]
        project = self._project(item, checkpoint, cancelled, progress)
        attempt = project.attempt(runtime["attempt_id"]) if runtime.get("attempt_id") else None
        if attempt and attempt.status.value in {"failed", "cancelled"}:
            if not runtime.get("explicit_retry"):
                raise ValueError(attempt.error or "Rendu interrompu. Reprenez explicitement cette étape.")
            checkpoint(previous_attempt_id=attempt.attempt_id, attempt_id=None, explicit_retry=False)
            runtime.update(attempt_id=None, explicit_retry=False)
            attempt = None
        if attempt is None:
            setup = config["render"]
            raw = setup["settings"]
            seed = int(raw.get("seed", 0)) if setup.get("seed_locked", True) else self.render.new_seed()
            settings = VideoLabSettings(aspect_ratio=VideoAspectRatio(raw["aspect_ratio"]), megapixels=raw["megapixels"],
                duration_seconds=raw["duration_seconds"], steps=raw["steps"], seed=seed,
                seed_locked=bool(setup.get("seed_locked", True)))
            project = self.render.prepare_attempt(project.project_id,
                prompt=item["steps"]["prompt"]["output"].get("text") or config["final_prompt"], settings=settings,
                music_enabled=setup.get("music_enabled", False), spectrum_enabled=setup.get("spectrum_enabled", False),
                initial_megapixels=setup.get("initial_megapixels", .2), force_upscale=setup.get("force_upscale", False),
                recipe_id=setup["recipe"]["id"], recipe_version=setup["recipe"]["version"],
                checkpoint=setup.get("checkpoint"),
                bunny=H3BunnySettings(**setup["bunny"]) if setup.get("bunny") else None,
                video_loras=H3VideoLoraStack.from_dict(setup["video_loras"]) if setup.get("video_loras") else None,
                video_lora=H3VideoLoraSelection(**setup["video_lora"]) if setup.get("video_lora") else None)
            attempt = project.attempts[-1]
            checkpoint(attempt_id=attempt.attempt_id)
            runtime["attempt_id"] = attempt.attempt_id
        if cancelled():
            self.render.cancel_attempt(project.project_id, attempt.attempt_id)
            raise FactoryCancelled()
        if attempt.status.value == "created":
            try:
                self.render.queue_attempt(project.project_id, attempt.attempt_id, operation_label=f"Usine · {item['name']}")
            except ValueError as error:
                if "déjà actif" in str(error):
                    raise FactoryWait(str(error)) from error
                raise
        if self.render.projects.get(project.project_id).attempt(attempt.attempt_id).status.value == "queued":
            cooldown = self.coordinator.settings.remote_video_cooldown_seconds if self.coordinator else 0
            self.render.execute_attempt(project.project_id, attempt.attempt_id,
                                        post_cooldown_seconds=cooldown, operation_label=f"Usine · {item['name']}")
        deadline = time.monotonic() + self.render.run_timeout
        while True:
            project = self.render.get(project.project_id)
            attempt = project.attempt(attempt.attempt_id)
            if attempt.status.value == "succeeded":
                return self.video_output(project, attempt)
            if attempt.status.value in {"failed", "cancelled"}:
                if cancelled() or attempt.status.value == "cancelled":
                    raise FactoryCancelled()
                raise ValueError(attempt.error or "Échec du rendu.")
            if cancelled():
                self.render.cancel_attempt(project.project_id, attempt.attempt_id)
            if time.monotonic() > deadline:
                raise ValueError("Rendu toujours actif : vérifier son état avant de reprendre.")
            progress("Rendu vidéo · " + attempt.status.value)
            time.sleep(1)

    def _dlss(self, item, checkpoint, cancelled, progress):
        video = item["steps"]["video"]["output"]
        job_id = item["runtime"].get("dlss_job_id")
        if job_id:
            job = self.dlss.jobs.get(job_id)
            if job["status"] in {"failed", "cancelled", "unconfirmed"} and item["runtime"].get("explicit_retry"):
                job = self.dlss.retry(job_id)
            else:
                self.dlss.wake()
        else:
            settings = DlssSettings(size="1.724", intensity=.2, tone=0, structure=.2, skin=0,
                detail=1, style="Natural", strict_neural=False, interpolate=True, hdr=False, codec="H.264 (NVIDIA NVENC)")
            job = self.dlss.queue(owner=video["owner"], owner_id=video["project_id"], attempt_id=video["attempt_id"],
                                  settings=settings, request_id=f"factory-{item['id']}-{video['attempt_id']}")
            job_id = job["job_id"]
            checkpoint(dlss_job_id=job_id)
        while job["status"] not in {"succeeded", "failed", "cancelled", "unconfirmed"}:
            if cancelled():
                self.dlss.cancel(job_id)
            progress("DLSS · " + job["status"], job.get("progress"))
            time.sleep(1)
            job = self.dlss.jobs.get(job_id)
        if job["status"] == "cancelled":
            raise FactoryCancelled()
        if job["status"] != "succeeded":
            raise ValueError(job.get("error") or "DLSS à reprendre.")
        return dict(asset_id=job["output_asset_id"], job_id=job_id)

    def _social(self, item, checkpoint, cancelled, progress):
        runtime, settings = item["runtime"], item["config"]["social"]
        identity = runtime.get("social_project_id")
        if identity:
            project = self.social.get_project(identity)
        else:
            video = item["steps"]["video"]["output"]
            frames = video.get("keyframes", [])
            if len(frames) >= 4:
                frames = [frames[round(i * (len(frames) - 1) / 3)] for i in range(4)]
            else:
                content = self.assets.read_bytes(video["asset_id"])
                metadata = self.dlss.media.probe(content)
                duration = metadata["duration_seconds"] * 1000
                frames = [self.assets.create(content, media_type="image/png").asset_id
                          for content in self.dlss.media.frames(content, [int(duration * ratio) for ratio in (.05, .35, .65, .95)])]
            if cancelled():
                raise FactoryCancelled()
            project = self.social.create_project(name=item["name"][:120], model_id=settings["model_id"],
                language=SocialLanguage(settings["language"]), variant_count=settings["variant_count"],
                video_asset_id=video["asset_id"], video_filename=item["name"][:120] + ".mp4", keyframe_asset_ids=tuple(frames))
            identity = project.project_id
            checkpoint(social_project_id=identity)
        if not any(turn.variants for turn in project.turns):
            self._consume(self.social.stream_chat(identity,
                "Propose les premières variantes Instagram à partir de cette vidéo et du brief éditorial."),
                cancelled, progress)
        project = self.social.get_project(identity)
        variants = [asdict(variant) for turn in project.turns if turn.variants for variant in turn.variants]
        if not variants:
            raise ValueError("Aucune variante Instagram reçue.")
        return dict(project_id=identity, variants=variants[-settings["variant_count"]:])

    def cancel(self, item):
        runtime = item["runtime"]
        if item["steps"]["video"]["status"] == "running" and runtime.get("attempt_id"):
            self.render.cancel_attempt(runtime["render_project_id"], runtime["attempt_id"])
        if item["steps"]["dlss"]["status"] == "running" and runtime.get("dlss_job_id"):
            self.dlss.cancel(runtime["dlss_job_id"])
