from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from panelforge.domain import (
    CreativeFreedomAxes,
    CompositionStage,
    Krea2AspectRatio,
    Krea2BatchSettings,
    Krea2LoraSelection,
    ProductionConfig,
    ProductionCandidateAssessment,
    ProductionDecision,
    ProductionDecisionKind,
    ProductionDecisionOutcome,
    ProductionEvent,
    ProductionEventLevel,
    ProductionJob,
    ProductionLoraChoice,
    ProductionLoraChoiceSource,
    ProductionLoraPlan,
    ProductionStage,
    ProductionStatus,
    ThermalPolicy,
    ThermalSnapshot,
)
from panelforge.application.production import ProductionService
from panelforge.domain.assets import Asset
from panelforge.domain.h3_render import (
    H3RenderAttempt,
    H3RenderInputMode,
    H3RenderKeyframe,
    H3RenderProject,
    H3VideoLoraSelection,
)
from panelforge.domain.krea2_assisted import (
    Krea2AssistedAttempt,
    Krea2AssistedProject,
)
from panelforge.infrastructure.storage import LocalProductionJobStore


def config() -> ProductionConfig:
    return ProductionConfig(
        model_id="local::qwen",
        image_settings=Krea2BatchSettings(
            model_name="Krea2/model.safetensors",
            aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
            megapixels=2.1,
        ),
        creative_axes=CreativeFreedomAxes(3, 3, 3),
        thermal=ThermalPolicy(
            stop_temperature_c=85,
            resume_temperature_c=40,
            cooldown_seconds=120,
        ),
    )


class ProductionDomainTest(unittest.TestCase):
    def test_defaults_match_the_approved_full_auto_v1(self):
        value = config()

        self.assertEqual(value.creative_freedom, 100)
        self.assertEqual(value.image_attempt_count, 3)
        self.assertEqual(value.video_preview_limit, 3)
        self.assertEqual(value.video_steps, 25)
        self.assertEqual(value.preview_megapixels, 0.2)
        self.assertEqual(value.final_megapixels, 1.2)
        self.assertFalse(value.music_enabled)
        self.assertFalse(value.assisted_lora_selection)
        self.assertFalse(value.creative_direction_enabled)
        self.assertEqual(value.creative_audacity, 2)
        self.assertEqual(value.thermal.stop_temperature_c, 85)
        self.assertEqual(value.thermal.resume_temperature_c, 40)
        self.assertEqual(value.thermal.cooldown_seconds, 120)

    def test_feedback_must_belong_to_the_krea_attempt_history(self):
        with self.assertRaisesRegex(ValueError, "feedback attempts"):
            ProductionJob(
                job_id="job-1",
                name="Test",
                intention="Animate the subject.",
                source_asset_id="asset-source",
                source_filename="source.png",
                config=config(),
                krea_feedback_attempt_ids=("attempt-missing",),
            )

    def test_succeeded_job_requires_the_final_attempt(self):
        with self.assertRaisesRegex(ValueError, "completed final attempt"):
            ProductionJob(
                job_id="job-1",
                name="Test",
                intention="Animate the subject.",
                source_asset_id="asset-source",
                source_filename="source.png",
                config=config(),
                status=ProductionStatus.SUCCEEDED,
                stage=ProductionStage.COMPLETE,
            )


class LocalProductionJobStoreTest(unittest.TestCase):
    def test_round_trip_keeps_decisions_events_and_child_ids(self):
        with tempfile.TemporaryDirectory() as root:
            store = LocalProductionJobStore(Path(root))
            job = ProductionJob(
                job_id="job-1",
                name="Night job",
                intention="Turn the portrait into a moving ten-second scene.",
                source_asset_id="asset-source",
                source_filename="source.png",
                config=replace(
                    config(),
                    creative_direction_enabled=True,
                    h3_video_lora=H3VideoLoraSelection(
                        name="minmax_nsfw/model.safetensors",
                        strength=0.4,
                    ),
                ),
                status=ProductionStatus.RUNNING,
                stage=ProductionStage.IMAGE_SELECTION,
                krea_project_id="krea-project",
                krea_attempt_ids=("attempt-1", "attempt-2", "attempt-3"),
                krea_feedback_attempt_ids=("attempt-1", "attempt-2"),
                lora_plan=ProductionLoraPlan(
                    choices=(ProductionLoraChoice(
                        name="krea2/cinematic.safetensors",
                        strength=1.25,
                        source=ProductionLoraChoiceSource.MODEL,
                        expected_effect="Cinematic contrast.",
                    ),),
                    rationale="Useful for this scene.",
                ),
                decisions=(ProductionDecision(
                    decision_id="decision-1",
                    timestamp="2026-08-30T12:00:00Z",
                    kind=ProductionDecisionKind.IMAGE_SELECTION,
                    outcome=ProductionDecisionOutcome.SELECT,
                    attempt_id="attempt-2",
                    score=91,
                    rationale="Best composition.",
                    assessments=(ProductionCandidateAssessment(
                        attempt_id="attempt-2",
                        score=91,
                        summary="Best composition.",
                    ),),
                ),),
                events=(ProductionEvent(
                    event_id="event-1",
                    timestamp="2026-08-30T12:00:00Z",
                    stage=ProductionStage.IMAGE_SELECTION,
                    level=ProductionEventLevel.INFO,
                    message="Three candidates are ready.",
                ),),
            )

            store.create(job)
            loaded = store.get("job-1")
            self.assertEqual(loaded, job)
            self.assertTrue(loaded.config.creative_direction_enabled)

            completed = replace(loaded, status=ProductionStatus.RUNNING)
            store.save(completed)
            self.assertEqual(store.list(1), [completed])

            path = Path(root) / "production_jobs" / "job-1" / "job.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["schema_version"] = 1
            del raw["config"]["creative_audacity"]
            del raw["config"]["h3_video_lora"]
            path.write_text(json.dumps(raw), encoding="utf-8")
            self.assertEqual(store.get("job-1").config.creative_audacity, 1)
            self.assertIsNone(store.get("job-1").config.h3_video_lora)


class MemoryJobs:
    def __init__(self):
        self.values = {}

    def create(self, job):
        self.values[job.job_id] = job
        return job

    save = create

    def get(self, job_id):
        return self.values[job_id]

    def list(self, limit=30):
        return list(self.values.values())[:limit]


class MemoryAssets:
    def __init__(self):
        self.values = {}
        self.create(b"source", "image/png", asset_id="source")

    def create(self, content, media_type, source_run_id=None, asset_id=None):
        asset_id = asset_id or f"asset-{len(self.values) + 1}"
        asset = Asset(
            asset_id=asset_id,
            media_type=media_type,
            content_sha256="0" * 64,
            size_bytes=len(content),
            storage_key=f"assets/{asset_id}/content.bin",
            source_run_id=source_run_id,
        )
        self.values[asset_id] = (asset, content)
        return asset

    def get(self, asset_id):
        return self.values[asset_id][0]

    def read_bytes(self, asset_id):
        return self.values[asset_id][1]


class FakeKrea:
    def __init__(self, assets):
        self.assets = assets
        self.projects = {}
        self.prompt_count = 0
        self.messages = []

    def create_project(self, **values):
        project = Krea2AssistedProject(
            project_id="krea-project",
            name=values["name"],
            intention=values["intention"],
            model_id=values["model_id"],
            reference_asset_id=values["reference_asset_id"],
            reference_filename=values["reference_filename"],
        )
        self.projects[project.project_id] = project
        return project

    def get(self, project_id):
        return self.projects[project_id]

    def stream_chat(self, project_id, _message, **_values):
        self.prompt_count += 1
        self.messages.append(_message)
        project = replace(self.projects[project_id], current_prompt=f"KREA prompt {self.prompt_count} with enough detailed visual language for rendering")
        self.projects[project_id] = project
        yield SimpleNamespace(project=project, error=None)

    def prepare_attempt(self, project_id, *, prompt, settings, seed=None):
        project = self.projects[project_id]
        attempt = Krea2AssistedAttempt(
            attempt_id=f"image-{len(project.attempts) + 1}",
            index=len(project.attempts) + 1,
            prompt=prompt,
            settings=settings,
            seed=100 + len(project.attempts),
        )
        project = project.add_attempt(attempt)
        self.projects[project_id] = project
        return project

    def queue_attempt(self, project_id, attempt_id):
        project = self.projects[project_id]
        project = project.replace_attempt(project.attempt(attempt_id).queue())
        self.projects[project_id] = project
        return project

    def execute_attempt(self, project_id, attempt_id):
        project = self.projects[project_id]
        attempt = project.attempt(attempt_id)
        asset = self.assets.create(b"image", "image/png")
        attempt = attempt.start("exec", "0" * 64).succeed(asset.asset_id)
        project = project.replace_attempt(attempt)
        self.projects[project_id] = project
        return project

    def cancel_attempt(self, project_id, attempt_id):
        return self.projects[project_id]

    def save_image(self, project_id, attempt_id):
        project = self.projects[project_id].accept_attempt(attempt_id)
        self.projects[project_id] = project
        return project


class FakePromptLab:
    def __init__(self):
        self.sessions = {}
        self.create_values = []
        self.structure_values = []

    def create_session(self, **values):
        self.create_values.append(values)
        session = SimpleNamespace(
            session_id="prompt-session",
            references=(SimpleNamespace(reference_id="reference-1"),),
            active_brief_revision=None,
            brief_complete=False,
            brief_variant_id=values.get("brief_variant_id"),
            brief_variant_version=values.get("brief_variant_version"),
        )
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id):
        return self.sessions[session_id]

    def structure_brief(self, session_id, *_args, **kwargs):
        self.structure_values.append(kwargs)
        session = self.sessions[session_id]
        session.active_brief_revision = SimpleNamespace(
            content="brief",
            creative_audacity=kwargs.get("creative_audacity", 0),
        )
        return session

    def approve_brief(self, session_id):
        session = self.sessions[session_id]
        session.brief_complete = True
        return session


class FakeComposition:
    def __init__(self):
        self.value = None
        self.generated_stages = []
        self.approved_stages = []

    def get(self, _session_id):
        if self.value is None:
            raise FileNotFoundError
        return self.value

    def configure(self, *_args):
        documents = {
            stage: SimpleNamespace(active_revision=None, active_revision_id=None, approved_revision_id=None)
            for stage in ("beat_sheet", "final_prompt")
        }
        self.value = SimpleNamespace(document=lambda stage: documents[stage.value])
        return self.value

    def generate(self, _session_id, stage):
        if stage is CompositionStage.FINAL_PROMPT and self.value.document(CompositionStage.BEAT_SHEET).approved_revision_id is None:
            raise ValueError("approve a current beat_sheet first")
        self.generated_stages.append(stage)
        document = self.value.document(stage)
        document.active_revision = SimpleNamespace(content=f"{stage.value} content")
        document.active_revision_id = f"{stage.value}-revision-{len(self.generated_stages)}"
        return self.value

    def approve(self, _session_id, stage):
        self.approved_stages.append(stage)
        document = self.value.document(stage)
        document.approved_revision_id = document.active_revision_id
        return self.value


class RetryPlanComposition(FakeComposition):
    def __init__(self):
        super().__init__()
        self.rejected_once = False

    def approve(self, session_id, stage):
        if stage is CompositionStage.BEAT_SHEET and not self.rejected_once:
            self.rejected_once = True
            raise ValueError("invalid first Plan candidate")
        return super().approve(session_id, stage)


class FakeH3:
    def __init__(self, assets):
        self.assets = assets
        self.project = None

    def get_or_create_from_session(self, _session_id):
        if self.project is None:
            self.project = H3RenderProject(
                project_id="h3-project",
                source_session_id="prompt-session",
                source_prompt_revision_id="final-revision",
                model_id="local::qwen",
                input_mode=H3RenderInputMode.I2VA,
                current_prompt="integrated_multimodal_description: detailed H3 prompt",
                first_frame_asset_id="asset-3",
                first_frame_label="selected",
            )
        return self.project

    def get(self, _project_id):
        return self.project

    def new_seed(self):
        return 4242

    def prepare_attempt(self, _project_id, *, prompt, settings, music_enabled, video_lora=None):
        attempt = H3RenderAttempt(
            attempt_id=f"video-{len(self.project.attempts) + 1}",
            index=len(self.project.attempts) + 1,
            prompt=prompt,
            effective_prompt=prompt,
            settings=settings,
            music_enabled=music_enabled,
            keyframe_timestamps_ms=(0, 5000, 9950),
            video_lora=video_lora,
        )
        self.project = self.project.add_attempt(attempt)
        return self.project

    def queue_attempt(self, _project_id, attempt_id):
        self.project = self.project.replace_attempt(self.project.attempt(attempt_id).queue())
        return self.project

    def execute_attempt(self, _project_id, attempt_id):
        attempt = self.project.attempt(attempt_id)
        video = self.assets.create(b"video", "video/mp4")
        frames = tuple(
            H3RenderKeyframe(
                asset_id=self.assets.create(b"frame", "image/png").asset_id,
                timestamp_ms=value,
                label=f"frame {value}",
            )
            for value in (0, 5000, 9950)
        )
        attempt = attempt.start("exec", "0" * 64).succeed(video.asset_id, frames)
        self.project = self.project.replace_attempt(attempt).use_feedback(attempt_id)
        return self.project

    def cancel_attempt(self, _project_id, _attempt_id):
        return self.project

    def resume_attempt(self, _project_id, attempt_id):
        self.project = self.project.resume_attempt(attempt_id)
        return self.project

    def stream_chat(self, *_args, **_kwargs):
        self.project = replace(self.project, current_prompt=self.project.current_prompt + " revised")
        yield SimpleNamespace(project=self.project, error=None)


class FakeGateway:
    def __init__(self):
        self.operation_ids = []

    def complete(self, request):
        self.operation_ids.append(request.operation_id)
        if request.operation_id == "production.lora_select@0.2.0":
            content = (
                '{"selections":[{"name":"krea2/cinematic.safetensors","strength":1.25,'
                '"expected_effect":"Adds cinematic contrast and controlled highlights."}],'
                '"rationale":"One complementary LoRA is sufficient."}'
            )
        elif request.operation_id == "production.image_select@0.2.2":
            content = (
                '{"recommended_candidate":2,"candidates":['
                '{"candidate":1,"score":72,"summary":"Faithful but flat."},'
                '{"candidate":2,"score":93,"summary":"Strongest frame."},'
                '{"candidate":3,"score":84,"summary":"Dynamic but less faithful."}'
                '],"rationale":"Candidate 2 has the best balance."}'
            )
        else:
            content = '{"decision":"accept","score":91,"rationale":"Faithful result.","revision_instruction":""}'
        return SimpleNamespace(content=content)


class TruncatedImageSelectionGateway(FakeGateway):
    def __init__(self):
        super().__init__()
        self.requests = []
        self.image_selection_calls = 0

    def complete(self, request):
        self.requests.append(request)
        if request.operation_id == "production.image_select@0.2.2":
            self.image_selection_calls += 1
            if self.image_selection_calls == 1:
                self.operation_ids.append(request.operation_id)
                return SimpleNamespace(
                    content='{"recommended_candidate":2,"candidates":[',
                    finish_reason="length",
                )
        return super().complete(request)


class SafeThermal:
    def snapshot(self):
        return ThermalSnapshot(local_temperature_c=30, remote_temperature_c=30)


class FakeLoraResources:
    def list_loras(self):
        return (
            SimpleNamespace(
                comfy_name="krea2/cinematic.safetensors",
                filename="cinematic.safetensors",
                favorite=True,
                safety=SimpleNamespace(value="sfw"),
            ),
            SimpleNamespace(
                comfy_name="krea2/detail.safetensors",
                filename="detail.safetensors",
                favorite=False,
                safety=SimpleNamespace(value="sfw"),
            ),
        )


class FakeLoraMemory:
    def __init__(self):
        self.plans = []
        self.observations = []

    def context(self, names, *, observations_per_lora=3):
        return tuple({"name": name, "recent_observations": []} for name in names)

    def record_plan(self, **values):
        self.plans.append(values)

    def record_observation(self, **values):
        self.observations.append(values)


class ProductionServiceTest(unittest.TestCase):
    def test_new_jobs_reject_manual_lora_strengths_outside_minus_one_to_one(self):
        assets = MemoryAssets()
        service = ProductionService(
            gateway=FakeGateway(),
            assets=assets,
            jobs=MemoryJobs(),
            krea2=FakeKrea(assets),
            prompt_lab=FakePromptLab(),
            composition=FakeComposition(),
            h3_render=FakeH3(assets),
            thermal_monitor=SafeThermal(),
            monitor_interval=0.001,
        )
        value = replace(
            config(),
            image_settings=replace(
                config().image_settings,
                loras=(Krea2LoraSelection("krea2/too-strong.safetensors", 1.01),),
            ),
        )

        with self.assertRaisesRegex(ValueError, "between -1 and 1"):
            service.create_job(
                name="Unsafe LoRA",
                intention="Animate the portrait.",
                source_asset_id="source",
                source_filename="source.png",
                config=value,
            )

    def test_cancel_marks_a_global_stop_before_any_later_stage_runs(self):
        assets = MemoryAssets()
        jobs = MemoryJobs()
        service = ProductionService(
            gateway=FakeGateway(),
            assets=assets,
            jobs=jobs,
            krea2=FakeKrea(assets),
            prompt_lab=FakePromptLab(),
            composition=FakeComposition(),
            h3_render=FakeH3(assets),
            thermal_monitor=SafeThermal(),
            monitor_interval=0.001,
        )
        job = service.create_job(
            name="Stop test",
            intention="Animate the portrait.",
            source_asset_id="source",
            source_filename="source.png",
            config=config(),
        )

        cancelled = service.cancel(job.job_id)
        repeated = service.cancel(job.job_id)

        self.assertTrue(cancelled.cancel_requested)
        self.assertEqual(cancelled.status, ProductionStatus.CANCELLED)
        self.assertEqual(cancelled, repeated)
        self.assertEqual(
            sum("Arrêt global demandé" in event.message for event in cancelled.events),
            1,
        )

    def test_full_auto_job_reaches_one_point_two_megapixel_final(self):
        assets = MemoryAssets()
        jobs = MemoryJobs()
        krea = FakeKrea(assets)
        h3 = FakeH3(assets)
        composition = FakeComposition()
        service = ProductionService(
            gateway=FakeGateway(),
            assets=assets,
            jobs=jobs,
            krea2=krea,
            prompt_lab=FakePromptLab(),
            composition=composition,
            h3_render=h3,
            thermal_monitor=SafeThermal(),
            monitor_interval=0.001,
        )
        value = config()
        value = replace(value, thermal=replace(value.thermal, cooldown_seconds=0))
        job = service.create_job(
            name="Automatic test",
            intention="Animate the portrait with a strong cinematic movement.",
            source_asset_id="source",
            source_filename="source.png",
            config=value,
        )
        jobs.save(replace(job, status=ProductionStatus.QUEUED))

        result = service.run(job.job_id)

        self.assertEqual(result.status, ProductionStatus.SUCCEEDED)
        self.assertEqual(result.stage, ProductionStage.COMPLETE)
        self.assertEqual(len(result.krea_attempt_ids), 3)
        self.assertEqual(result.selected_image_attempt_id, "image-2")
        image_decision = next(value for value in result.decisions if value.kind is ProductionDecisionKind.IMAGE_SELECTION)
        self.assertEqual([value.score for value in image_decision.assessments], [72, 93, 84])
        self.assertEqual(len(result.preview_attempt_ids), 1)
        self.assertIsNotNone(result.final_attempt_id)
        final = h3.get("h3-project").attempt(result.final_attempt_id)
        self.assertEqual(final.settings.megapixels, 1.2)
        self.assertEqual(final.settings.steps, 25)
        self.assertEqual(final.settings.seed, 4242)
        self.assertIn("pre-action state", krea.messages[0])
        self.assertIn("previous rendered image", krea.messages[1])
        self.assertIn("pre-action state", krea.messages[1])
        self.assertEqual(
            composition.generated_stages,
            [CompositionStage.BEAT_SHEET, CompositionStage.FINAL_PROMPT],
        )
        self.assertEqual(
            composition.approved_stages,
            [CompositionStage.BEAT_SHEET, CompositionStage.FINAL_PROMPT],
        )
        messages = [event.message for event in result.events]
        self.assertTrue(any("Contrat d'entrée H3" in message for message in messages))
        self.assertTrue(any("first frame = Essai 2" in message for message in messages))
        self.assertTrue(any("last frame = aucune" in message for message in messages))
        self.assertTrue(any("ratio 9:16" in message for message in messages))
        self.assertTrue(any("Brief H3 · thinking" in message for message in messages))
        self.assertTrue(any("Plan JSON H3 · thinking" in message for message in messages))
        self.assertTrue(any("Prompt final H3 · thinking" in message for message in messages))

        audit = service.h3_audit(result.job_id)
        self.assertEqual(audit["profile"], {
            "id": "minimax.h3.fl2va.direct",
            "version": "0.3.3",
        })
        self.assertEqual(audit["input"]["mode"], H3RenderInputMode.I2VA.value)
        self.assertEqual(audit["input"]["first_frame"]["attempt_index"], 2)
        self.assertIsNone(audit["input"]["last_frame"])
        self.assertIn("9:16", audit["input"]["aspect_ratio"])
        self.assertEqual(audit["input"]["steps"], value.video_steps)
        self.assertEqual(audit["documents"]["brief"]["content"], "brief")
        self.assertEqual(audit["documents"]["beat_sheet"]["content"], "beat_sheet content")
        self.assertEqual(audit["documents"]["final_prompt"]["content"], "final_prompt content")
        self.assertEqual(
            audit["current_prompt"],
            "integrated_multimodal_description: detailed H3 prompt",
        )

    def test_h3_video_lora_is_locked_across_preview_and_final(self):
        assets = MemoryAssets()
        jobs = MemoryJobs()
        h3 = FakeH3(assets)
        service = ProductionService(
            gateway=FakeGateway(),
            assets=assets,
            jobs=jobs,
            krea2=FakeKrea(assets),
            prompt_lab=FakePromptLab(),
            composition=FakeComposition(),
            h3_render=h3,
            thermal_monitor=SafeThermal(),
            monitor_interval=0.001,
        )
        selection = H3VideoLoraSelection(
            name="minmax_nsfw/MysticXXX_MMH3-V2.safetensors",
            strength=0.65,
        )
        value = replace(
            config(),
            h3_video_lora=selection,
            thermal=replace(config().thermal, cooldown_seconds=0),
        )
        job = service.create_job(
            name="H3 LoRA test",
            intention="Animate the portrait.",
            source_asset_id="source",
            source_filename="source.png",
            config=value,
        )
        jobs.save(replace(job, status=ProductionStatus.QUEUED))

        result = service.run(job.job_id)

        self.assertEqual(result.status, ProductionStatus.SUCCEEDED)
        attempts = h3.get("h3-project").attempts
        self.assertGreaterEqual(len(attempts), 2)
        self.assertTrue(all(attempt.video_lora == selection for attempt in attempts))
        self.assertEqual(service.h3_audit(result.job_id)["input"]["h3_video_lora"]["strength"], 0.65)
        self.assertTrue(any("LoRA vidéo H3" in event.message for event in result.events))
    def test_creative_direction_selects_only_the_versioned_brief_variant(self):
        assets = MemoryAssets()
        jobs = MemoryJobs()
        prompt_lab = FakePromptLab()
        composition = FakeComposition()
        service = ProductionService(
            gateway=FakeGateway(),
            assets=assets,
            jobs=jobs,
            krea2=FakeKrea(assets),
            prompt_lab=prompt_lab,
            composition=composition,
            h3_render=FakeH3(assets),
            thermal_monitor=SafeThermal(),
            monitor_interval=0.001,
        )
        value = replace(
            config(),
            creative_direction_enabled=True,
            creative_audacity=3,
            thermal=replace(config().thermal, cooldown_seconds=0),
        )
        job = service.create_job(
            name="Creative direction",
            intention="Make the dark priestess frightening and visually surprising.",
            source_asset_id="source",
            source_filename="source.png",
            config=value,
        )
        jobs.save(replace(job, status=ProductionStatus.QUEUED))

        result = service.run(job.job_id)

        self.assertEqual(result.status, ProductionStatus.SUCCEEDED)
        created = prompt_lab.create_values[0]
        self.assertEqual(created["profile_version"], "0.3.3")
        self.assertEqual(created["brief_variant_id"], "creative-direction")
        self.assertEqual(created["brief_variant_version"], "0.2.0")
        self.assertEqual(prompt_lab.structure_values[0]["creative_audacity"], 3)
        self.assertEqual(
            composition.generated_stages,
            [CompositionStage.BEAT_SHEET, CompositionStage.FINAL_PROMPT],
        )
        messages = [event.message for event in result.events]
        self.assertTrue(any("Direction créative 0.2.0 activée · audace 3/3" in value for value in messages))
        audit = service.h3_audit(result.job_id)
        self.assertEqual(audit["brief_variant"], {
            "id": "creative-direction",
            "version": "0.2.0",
        })
        self.assertEqual(audit["brief_audacity"], 3)

    def test_truncated_image_selection_retries_without_a_client_output_limit(self):
        assets = MemoryAssets()
        jobs = MemoryJobs()
        gateway = TruncatedImageSelectionGateway()
        service = ProductionService(
            gateway=gateway,
            assets=assets,
            jobs=jobs,
            krea2=FakeKrea(assets),
            prompt_lab=FakePromptLab(),
            composition=FakeComposition(),
            h3_render=FakeH3(assets),
            thermal_monitor=SafeThermal(),
            monitor_interval=0.001,
        )
        value = replace(config(), thermal=replace(config().thermal, cooldown_seconds=0))
        job = service.create_job(
            name="Truncated selection",
            intention="Animate the portrait.",
            source_asset_id="source",
            source_filename="source.png",
            config=value,
        )
        jobs.save(replace(job, status=ProductionStatus.QUEUED))

        result = service.run(job.job_id)

        self.assertEqual(result.status, ProductionStatus.SUCCEEDED)
        selection_requests = [
            request for request in gateway.requests
            if request.operation_id == "production.image_select@0.2.2"
        ]
        self.assertEqual([request.max_tokens for request in selection_requests], [None, None])
        self.assertIn('"candidate":3', selection_requests[0].user_prompt)
        self.assertIn("under 240 characters", selection_requests[0].user_prompt)
        self.assertIn("must not compress", selection_requests[0].user_prompt)

    def test_h3_plan_validation_failure_regenerates_only_the_plan_once(self):
        assets = MemoryAssets()
        jobs = MemoryJobs()
        krea = FakeKrea(assets)
        composition = RetryPlanComposition()
        service = ProductionService(
            gateway=FakeGateway(),
            assets=assets,
            jobs=jobs,
            krea2=krea,
            prompt_lab=FakePromptLab(),
            composition=composition,
            h3_render=FakeH3(assets),
            thermal_monitor=SafeThermal(),
            monitor_interval=0.001,
        )
        value = replace(config(), thermal=replace(config().thermal, cooldown_seconds=0))
        job = service.create_job(
            name="Plan retry",
            intention="Animate the portrait.",
            source_asset_id="source",
            source_filename="source.png",
            config=value,
        )
        jobs.save(replace(job, status=ProductionStatus.QUEUED))

        result = service.run(job.job_id)

        self.assertEqual(result.status, ProductionStatus.SUCCEEDED)
        self.assertEqual(composition.generated_stages.count(CompositionStage.BEAT_SHEET), 2)
        self.assertEqual(composition.generated_stages.count(CompositionStage.FINAL_PROMPT), 1)

    def test_retry_failed_requeues_the_same_stage_and_preserves_children(self):
        assets = MemoryAssets()
        jobs = MemoryJobs()
        service = ProductionService(
            gateway=FakeGateway(),
            assets=assets,
            jobs=jobs,
            krea2=FakeKrea(assets),
            prompt_lab=FakePromptLab(),
            composition=FakeComposition(),
            h3_render=FakeH3(assets),
            thermal_monitor=SafeThermal(),
            monitor_interval=0.001,
        )
        failed = ProductionJob(
            job_id="job-failed",
            name="Failed H3",
            intention="Animate the selected image.",
            source_asset_id="source",
            source_filename="source.png",
            config=config(),
            status=ProductionStatus.FAILED,
            stage=ProductionStage.H3_PROMPT,
            krea_project_id="krea-project",
            krea_attempt_ids=("image-1", "image-2", "image-3"),
            krea_feedback_attempt_ids=("image-1", "image-2"),
            selected_image_attempt_id="image-3",
            selected_image_asset_id="asset-3",
            prompt_session_id="prompt-session",
            error="approve a current beat_sheet first",
        )
        jobs.create(failed)

        with patch("panelforge.application.production.Thread") as thread:
            resumed = service.retry_failed(failed.job_id)

        self.assertEqual(resumed.status, ProductionStatus.QUEUED)
        self.assertEqual(resumed.stage, ProductionStage.H3_PROMPT)
        self.assertEqual(resumed.krea_attempt_ids, failed.krea_attempt_ids)
        self.assertEqual(resumed.selected_image_attempt_id, "image-3")
        self.assertEqual(resumed.prompt_session_id, "prompt-session")
        self.assertIsNone(resumed.error)
        thread.assert_called_once()
        thread.return_value.start.assert_called_once_with()

    def test_experimental_lora_plan_pins_manual_choice_and_fills_one_slot_once(self):
        assets = MemoryAssets()
        jobs = MemoryJobs()
        krea = FakeKrea(assets)
        h3 = FakeH3(assets)
        gateway = FakeGateway()
        memory = FakeLoraMemory()
        service = ProductionService(
            gateway=gateway,
            assets=assets,
            jobs=jobs,
            krea2=krea,
            prompt_lab=FakePromptLab(),
            composition=FakeComposition(),
            h3_render=h3,
            thermal_monitor=SafeThermal(),
            lora_resources=FakeLoraResources(),
            lora_memory=memory,
            monitor_interval=0.001,
        )
        value = replace(
            config(),
            image_settings=replace(
                config().image_settings,
                loras=(Krea2LoraSelection("krea2/manual.safetensors", 0.8),),
            ),
            assisted_lora_selection=True,
            thermal=replace(config().thermal, cooldown_seconds=0),
        )
        job = service.create_job(
            name="LoRA experiment",
            intention="Create a dramatic spectral portrait.",
            source_asset_id="source",
            source_filename="source.png",
            config=value,
        )
        jobs.save(replace(job, status=ProductionStatus.QUEUED))

        result = service.run(job.job_id)

        self.assertEqual(result.status, ProductionStatus.SUCCEEDED)
        self.assertEqual(gateway.operation_ids.count("production.lora_select@0.2.0"), 1)
        self.assertEqual(
            [(value.name, value.strength, value.source) for value in result.lora_plan.choices],
            [
                ("krea2/manual.safetensors", 0.8, ProductionLoraChoiceSource.MANUAL),
                ("krea2/cinematic.safetensors", 1.0, ProductionLoraChoiceSource.MODEL),
            ],
        )
        self.assertIn("hard -1..1 safety limit", result.lora_plan.rationale)
        rendered_stacks = [
            [(value.name, value.strength) for value in attempt.settings.loras]
            for attempt in krea.get("krea-project").attempts
        ]
        self.assertEqual(len(rendered_stacks), 3)
        self.assertTrue(all(value == rendered_stacks[0] for value in rendered_stacks))
        self.assertTrue(all(-1 <= strength <= 1 for _, strength in rendered_stacks[0]))
        self.assertEqual(len(memory.plans), 1)
        self.assertGreaterEqual(len(memory.observations), 1)


if __name__ == "__main__":
    unittest.main()
