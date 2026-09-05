from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
from threading import Event
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from panelforge.application import CompletionResult, StreamEventKind, StreamPhase
from panelforge.application.production_v2 import ProductionV2Service, _weighted_model_sample
from panelforge.domain import (
    Asset,
    CompositionStage,
    H3RenderAttemptStatus,
    Krea2AspectRatio,
    Krea2AssistedAttemptStatus,
    Krea2BatchSettings,
    Krea2LoraSelection,
    ProductionV2AnchorRole,
    ProductionV2Candidate,
    ProductionV2CandidateKind,
    ProductionV2CandidateStatus,
    ProductionV2Preference,
    ProductionV2PromptStrategy,
    ProductionV2ReferenceMode,
    ProductionV2Stage,
    VideoAspectRatio,
)
from panelforge.infrastructure.storage import LocalProductionV2Store


class _Assets:
    def __init__(self) -> None:
        self.values = {
            "source": Asset("source", "image/png", "0" * 64, 10, "source.png"),
            "candidate-output": Asset("candidate-output", "image/png", "1" * 64, 10, "candidate.png"),
        }

    def get(self, asset_id):
        return self.values[asset_id]


class _KreaProject:
    def __init__(self, project_id, attempts=()):
        self.project_id = project_id
        self.attempts = attempts

    def attempt(self, attempt_id):
        return next(value for value in self.attempts if value.attempt_id == attempt_id)


class _ImmediateKrea:
    def __init__(self):
        self.stream_calls = []
        self.create_calls = []
        self.prepare_calls = []
        self._attempt_seeds = {}

    def create_project(self, **values):
        self.create_calls.append(values)
        return _KreaProject(f"krea-child-{len(self.create_calls)}")

    def stream_chat(self, project_id, message, **values):
        self.stream_calls.append((project_id, message, values))
        yield SimpleNamespace(
            project=SimpleNamespace(
                current_prompt="Vertical spectral priestess before motion",
                turns=(SimpleNamespace(model_id="local::actual-qwen"),),
            ),
            error=None,
        )

    def prepare_attempt(self, project_id, **values):
        self.prepare_calls.append((project_id, values))
        seed = values.get("seed", 123)
        attempt_id = f"krea-attempt-{len(self.prepare_calls)}"
        self._attempt_seeds[attempt_id] = seed
        attempt = SimpleNamespace(attempt_id=attempt_id, seed=seed)
        return _KreaProject(project_id, (attempt,))

    def queue_attempt(self, project_id, attempt_id):
        return None

    def execute_attempt(self, project_id, attempt_id):
        attempt = SimpleNamespace(
            attempt_id=attempt_id,
            seed=self._attempt_seeds[attempt_id],
            status=Krea2AssistedAttemptStatus.SUCCEEDED,
            output_asset_id="candidate-output",
            error=None,
        )
        return _KreaProject(project_id, (attempt,))


class _LoraGateway:
    def __init__(self):
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return CompletionResult(
            model_id=request.model_id,
            content=(
                '{"variants":['
                '{"additions":[{"name":"wetness.safetensors","strength":0.65,'
                '"expected_effect":"wet surface detail"}],"rationale":"Wet variant"},'
                '{"additions":[{"name":"cinematic.safetensors","strength":-0.4,'
                '"expected_effect":"controlled cinematic contrast"}],"rationale":"Contrast variant"}'
                ']}'
            ),
            finish_reason="stop",
        )


class _LoraResources:
    def list_loras(self):
        return (
            SimpleNamespace(comfy_name="wetness.safetensors", filename="wetness.safetensors", favorite=True, safety=None),
            SimpleNamespace(comfy_name="cinematic.safetensors", filename="cinematic.safetensors", favorite=False, safety=None),
        )


class _LoraMemory:
    def __init__(self):
        self.plans = []
        self.observations = []

    def context(self, names, *, observations_per_lora=3, profile_id=None):
        return tuple({"name": name, "observations": []} for name in names)

    def record_plan(self, **values):
        self.plans.append(values)

    def record_observation(self, **values):
        self.observations.append(values)


class _PromptLab:
    def __init__(self):
        self.session = None
        self.create_values = []
        self.structure_values = []

    def create_session(self, **values):
        self.create_values.append(values)
        references = tuple(SimpleNamespace(
            reference_id=f"ref-{index}", role=item.role,
        ) for index, item in enumerate(values["references"], 1))
        self.session = SimpleNamespace(session_id="prompt-session", references=references)
        return self.session

    def structure_brief(self, *args, **values):
        self.structure_values.append((args, values))
        return self.session

    def stream_structure_brief(self, *args, **values):
        session = self.structure_brief(*args, **values)
        yield SimpleNamespace(
            kind=StreamEventKind.REASONING, phase=StreamPhase.GENERATING,
            text="Analyse du brief", session=None, max_tokens=None,
        )
        yield SimpleNamespace(
            kind=StreamEventKind.DELTA, phase=StreamPhase.GENERATING,
            text="Brief structurÃ©", session=None, max_tokens=None,
        )
        yield SimpleNamespace(
            kind=StreamEventKind.COMPLETED, phase=StreamPhase.COMPLETED,
            text="Brief structurÃ©", session=session, max_tokens=None,
        )

    def approve_brief(self, _session_id):
        return self.session

    def get_session(self, _session_id):
        return self.session


class _BlockingPromptLab(_PromptLab):
    def __init__(self):
        super().__init__()
        self.structure_started = Event()
        self.release_structure = Event()

    def structure_brief(self, *args, **values):
        self.structure_values.append((args, values))
        if len(self.structure_values) == 1:
            self.structure_started.set()
            if not self.release_structure.wait(timeout=3):
                raise TimeoutError("test did not release the first Brief")
        return self.session


class _Composition:
    def __init__(self):
        self.configured = None
        self.generated = []

    def configure(self, *values):
        self.configured = values
        return SimpleNamespace()

    def generate(self, _session_id, stage):
        self.generated.append(stage)
        return SimpleNamespace()

    def stream_generate(self, session_id, stage, **_values):
        composition = self.generate(session_id, stage)
        yield SimpleNamespace(
            kind=StreamEventKind.REASONING, phase=StreamPhase.GENERATING,
            text=f"Analyse {stage.value}", composition=None, max_tokens=None,
        )
        yield SimpleNamespace(
            kind=StreamEventKind.DELTA, phase=StreamPhase.GENERATING,
            text=f"Document {stage.value}", composition=None, max_tokens=None,
        )
        yield SimpleNamespace(
            kind=StreamEventKind.COMPLETED, phase=StreamPhase.COMPLETED,
            text=f"Document {stage.value}", composition=composition,
            max_tokens=None,
        )

    def approve(self, _session_id, _stage):
        return SimpleNamespace()


class _H3Project:
    def __init__(self):
        self.project_id = "h3-project"
        self.current_prompt = (
            "integrated_multimodal_description:\n"
            "[Shot 1] The target video is one continuous 6-second shot."
        )
        self.attempts = []

    def attempt(self, attempt_id):
        return next(value for value in self.attempts if value.attempt_id == attempt_id)


class _H3:
    def __init__(self):
        self.project = _H3Project()
        self.prepare_calls = []

    def new_seed(self):
        return 999

    def get_or_create_from_session(self, _session_id):
        return self.project

    def get(self, _project_id):
        return self.project

    def prepare_attempt(self, project_id, **values):
        self.prepare_calls.append((project_id, values))
        self.project.attempts.append(SimpleNamespace(
            attempt_id=f"attempt-{len(self.project.attempts) + 1}",
            index=len(self.project.attempts) + 1,
            status=H3RenderAttemptStatus.CREATED,
            error=None,
        ))
        return self.project

    def queue_attempt(self, _project_id, attempt_id):
        self.project.attempt(attempt_id).status = H3RenderAttemptStatus.QUEUED

    def execute_attempt(self, _project_id, attempt_id):
        self.project.attempt(attempt_id).status = H3RenderAttemptStatus.SUCCEEDED
        return self.project


class _RevisionH3:
    def __init__(self):
        self.stream_calls = []
        self.prepare_calls = []

    def stream_chat(self, project_id, instruction, **values):
        self.stream_calls.append((project_id, instruction, values))
        yield SimpleNamespace(project=SimpleNamespace(project_id=project_id), error=None)


class ProductionV2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = LocalProductionV2Store(Path(self.temporary.name))
        self.service = ProductionV2Service(
            assets=_Assets(), store=self.store, krea2=object(),
            prompt_lab=object(), composition=object(), h3_render=object(),
            project_id_factory=lambda: "production-v2-test",
            candidate_id_factory=lambda: "candidate-test",
            revision_id_factory=lambda: "recipe-test",
            event_id_factory=lambda: "event-test",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def settings() -> Krea2BatchSettings:
        return Krea2BatchSettings(
            model_name="Krea2_Test_BF16.safetensors",
            aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
            megapixels=2.1,
            loras=(Krea2LoraSelection(name="mood.safetensors", strength=0.7),),
        )

    def create_project(self):
        return self.service.create_project(
            name="Fantasy", intention="A priestess becomes a blue ghost.",
            source_asset_id="source", source_filename="source.png",
            initial_model_id="local::qwen", memory_profile_id="sfw",
        )

    def wait_until_idle(self, project_id):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and self.service.get(project_id).status.value == "busy":
            time.sleep(0.01)
        return self.service.get(project_id)

    def completed_candidate(self, project):
        candidate = ProductionV2Candidate(
            candidate_id="candidate-test", index=1, round_index=1,
            role=ProductionV2AnchorRole.CALIBRATION, memory_profile_id="sfw",
            requested_model_id="local::qwen", actual_model_id="local::qwen",
            settings=self.settings(), status=ProductionV2CandidateStatus.SUCCEEDED,
            child_project_id="krea-child", child_attempt_id="attempt-child",
            prompt="Vertical fantasy portrait", seed=42,
            output_asset_id="candidate-output",
        )
        return self.store.save_project(replace(project, candidates=(candidate,)))

    def test_default_memory_profiles_and_project_round_trip(self) -> None:
        self.assertEqual({value.profile_id for value in self.service.list_profiles()}, {"sfw", "nsfw"})
        project = self.create_project()
        stored = self.service.get(project.project_id)
        self.assertEqual(stored.source_asset_id, "source")
        self.assertEqual(stored.duration_seconds, 6.0)
        self.assertEqual(stored.creative_audacity, 3)
        self.assertEqual(stored.revision_audacity, 3)
        self.assertEqual(stored.effective_video_compile_model_id, "local::qwen")
        self.assertEqual(stored.stage, ProductionV2Stage.IMAGE_CALIBRATION)

    def test_model_exploration_is_random_weighted_and_avoids_batch_duplicates(self) -> None:
        selected = _weighted_model_sample(
            ("frequent_BF16.safetensors", "rare_a_BF16.safetensors", "rare_b_BF16.safetensors"),
            {
                "frequent_bf16.safetensors": 10,
                "rare_a_bf16.safetensors": 0,
                "rare_b_bf16.safetensors": 0,
            },
            2,
            draw=lambda _maximum: 1,
        )
        self.assertEqual(selected, ("rare_a_BF16.safetensors", "rare_b_BF16.safetensors"))
        self.assertEqual(len(selected), len(set(selected)))

    def test_model_exploration_uses_durable_profile_history_and_bf16_catalog(self) -> None:
        project = self.completed_candidate(self.create_project())
        self.service.krea2 = SimpleNamespace(resources=SimpleNamespace(list_models=lambda: (
            SimpleNamespace(comfy_name="Krea2_Test_BF16.safetensors", filename="Krea2_Test_BF16.safetensors", precision="bf16"),
            SimpleNamespace(comfy_name="Rare_A_BF16.safetensors", filename="Rare_A_BF16.safetensors", precision="bf16"),
            SimpleNamespace(comfy_name="Rare_B_BF16.safetensors", filename="Rare_B_BF16.safetensors", precision="bf16"),
            SimpleNamespace(comfy_name="Ignored_INT8.safetensors", filename="Ignored_INT8.safetensors", precision="int8"),
        )))
        with patch("panelforge.application.production_v2.secrets.randbelow", return_value=1):
            selected = self.service._exploratory_model_names(
                project.memory_profile_id,
                2,
                fallback=(project.candidate("candidate-test").settings.model_name,),
            )
        self.assertEqual(selected, ("Rare_A_BF16.safetensors", "Rare_B_BF16.safetensors"))

    def test_model_exploration_keeps_selected_checkpoint_for_first_candidate(self) -> None:
        project = self.completed_candidate(self.create_project())
        self.service.krea2 = SimpleNamespace(resources=SimpleNamespace(list_models=lambda: (
            SimpleNamespace(comfy_name="Krea2_Test_BF16.safetensors", filename="Krea2_Test_BF16.safetensors", precision="bf16"),
            SimpleNamespace(comfy_name="Rare_A_BF16.safetensors", filename="Rare_A_BF16.safetensors", precision="bf16"),
            SimpleNamespace(comfy_name="Rare_B_BF16.safetensors", filename="Rare_B_BF16.safetensors", precision="bf16"),
        )))
        with patch("panelforge.application.production_v2.secrets.randbelow", return_value=0):
            selected = self.service._exploratory_model_names(
                project.memory_profile_id,
                3,
                fallback=("Krea2_Test_BF16.safetensors",) * 3,
                first_model="Krea2_Test_BF16.safetensors",
            )
        self.assertEqual(selected[0], "Krea2_Test_BF16.safetensors")
        self.assertEqual(set(selected[1:]), {
            "Rare_A_BF16.safetensors", "Rare_B_BF16.safetensors",
        })

    def test_exploratory_batch_uses_selected_checkpoint_for_first_candidate(self) -> None:
        krea = _ImmediateKrea()
        krea.resources = SimpleNamespace(list_models=lambda: (
            SimpleNamespace(comfy_name="Selected_BF16.safetensors", filename="Selected_BF16.safetensors", precision="bf16"),
            SimpleNamespace(comfy_name="Rare_A_BF16.safetensors", filename="Rare_A_BF16.safetensors", precision="bf16"),
            SimpleNamespace(comfy_name="Rare_B_BF16.safetensors", filename="Rare_B_BF16.safetensors", precision="bf16"),
        ))
        self.service.krea2 = krea
        project = self.completed_candidate(self.create_project())
        identifiers = iter(("candidate-selected", "candidate-random-a", "candidate-random-b"))
        self.service._candidate_id = lambda: next(identifiers)
        selected = replace(
            self.settings(), model_name="Selected_BF16.safetensors", megapixels=0.8,
        )
        with patch("panelforge.application.production_v2.secrets.randbelow", return_value=0):
            self.service.queue_candidates(
                project.project_id,
                role=ProductionV2AnchorRole.CALIBRATION,
                instruction="",
                model_id="local::unused-for-preserved-prompt",
                settings=(selected, selected, selected),
                feedback_parent_id="candidate-test",
                prompt_strategy=ProductionV2PromptStrategy.PRESERVE_CURRENT,
                preserve_seed=True,
                explore_models=True,
            )
        project = self.wait_until_idle(project.project_id)

        models = tuple(
            project.candidate(candidate_id).settings.model_name
            for candidate_id in (
                "candidate-selected", "candidate-random-a", "candidate-random-b",
            )
        )
        self.assertEqual(models, (
            "Selected_BF16.safetensors",
            "Rare_A_BF16.safetensors",
            "Rare_B_BF16.safetensors",
        ))

    def test_visual_recipe_is_versioned_and_used_by_promoted_anchor(self) -> None:
        project = self.completed_candidate(self.create_project())
        project = self.service.validate_visual_recipe(project.project_id, "candidate-test")
        self.assertEqual(project.active_recipe.settings, self.settings())
        self.assertEqual(project.stage, ProductionV2Stage.ANCHOR_WORKSHOP)
        project = self.service.promote_anchor(
            project.project_id,
            role=ProductionV2AnchorRole.FIRST_FRAME,
            candidate_id="candidate-test",
        )
        self.assertEqual(project.route.value, "i2va")
        self.assertEqual(project.anchors[0].recipe_revision_id, "recipe-test")

    def test_memory_feedback_is_isolated_in_candidate_profile(self) -> None:
        project = self.completed_candidate(self.create_project())
        self.service.review_candidate(
            project.project_id, "candidate-test",
            preference=ProductionV2Preference.LIKE,
            comment="Keep the blue spectral fabric.",
        )
        sfw = self.store.get_profile("sfw")
        nsfw = self.store.get_profile("nsfw")
        self.assertEqual(len(sfw.observations), 1)
        self.assertEqual(sfw.observations[0].comment, "Keep the blue spectral fabric.")
        self.assertEqual(nsfw.observations, ())

    def test_narrative_memory_is_role_local_but_resource_preferences_are_global(self) -> None:
        project = self.completed_candidate(self.create_project())
        last = replace(
            project.candidate("candidate-test"),
            candidate_id="candidate-last",
            role=ProductionV2AnchorRole.LAST_FRAME,
        )
        first = replace(
            project.candidate("candidate-test"),
            candidate_id="candidate-first",
            role=ProductionV2AnchorRole.FIRST_FRAME,
        )
        self.store.save_project(replace(project, candidates=(last, first)))
        self.service.review_candidate(
            project.project_id, "candidate-last",
            preference=ProductionV2Preference.LIKE,
            comment="Keep the blood-covered hands.",
        )
        self.service.review_candidate(
            project.project_id, "candidate-first",
            preference=ProductionV2Preference.LIKE,
            comment="Hands must still be intact.",
        )
        context = self.service._memory_context("sfw", ProductionV2AnchorRole.FIRST_FRAME)
        self.assertIn("checkpoint Krea2_Test_BF16.safetensors", context)
        self.assertIn("Hands must still be intact.", context)
        self.assertNotIn("Keep the blood-covered hands.", context)
        self.assertNotIn("last_frame", context)

    def test_ref2v_and_h3_base_anchor_families_cannot_be_mixed(self) -> None:
        project = self.completed_candidate(self.create_project())
        self.service.validate_visual_recipe(project.project_id, "candidate-test")
        project = self.service.promote_anchor(
            project.project_id, role=ProductionV2AnchorRole.REFERENCE,
            candidate_id="candidate-test",
        )
        self.assertEqual(project.route.value, "ref2va")
        with self.assertRaisesRegex(ValueError, "remove Ref2V references"):
            self.service.promote_anchor(
                project.project_id, role=ProductionV2AnchorRole.FIRST_FRAME,
                use_source=True,
            )

    def test_recalibration_archives_downstream_video_ids(self) -> None:
        project = self.completed_candidate(self.create_project())
        project = self.store.save_project(replace(
            project,
            prompt_session_id="old-session",
            h3_project_id="old-h3",
            preview_attempt_ids=("old-preview",),
        ))
        project = self.service.validate_visual_recipe(project.project_id, "candidate-test")
        self.assertIsNone(project.h3_project_id)
        self.assertEqual(project.archived_prompt_session_ids, ("old-session",))
        self.assertEqual(project.archived_h3_project_ids, ("old-h3",))

    def test_default_human_batch_runs_one_prompt_for_its_single_candidate(self) -> None:
        krea = _ImmediateKrea()
        self.service.krea2 = krea
        project = self.create_project()
        self.service.queue_candidates(
            project.project_id,
            role=ProductionV2AnchorRole.CALIBRATION,
            instruction="Make the atmosphere more frightening.",
            model_id="local::requested-qwen",
            settings=(self.settings(),),
        )
        project = self.wait_until_idle(project.project_id)
        self.assertEqual(project.status.value, "ready")
        self.assertEqual(project.candidates[0].status, ProductionV2CandidateStatus.SUCCEEDED)
        self.assertEqual(project.candidates[0].actual_model_id, "local::actual-qwen")
        self.assertEqual(len(krea.stream_calls), 1)
        self.assertIn("Video intention", krea.stream_calls[0][1])

    def test_rewrite_once_shares_one_prompt_across_the_batch(self) -> None:
        krea = _ImmediateKrea()
        self.service.krea2 = krea
        project = self.create_project()
        identifiers = iter(("candidate-a", "candidate-b", "candidate-c"))
        self.service._candidate_id = lambda: next(identifiers)
        self.service.queue_candidates(
            project.project_id,
            role=ProductionV2AnchorRole.CALIBRATION,
            instruction="Find a frightening visual base.",
            model_id="local::requested-qwen",
            settings=(self.settings(), self.settings(), self.settings()),
            prompt_strategy=ProductionV2PromptStrategy.REWRITE_ONCE,
            preserve_seed=True,
        )
        project = self.wait_until_idle(project.project_id)
        candidates = [project.candidate(value) for value in ("candidate-a", "candidate-b", "candidate-c")]
        self.assertEqual(len(krea.stream_calls), 1)
        self.assertEqual({value.prompt for value in candidates}, {"Vertical spectral priestess before motion"})
        self.assertEqual(len({value.seed for value in candidates}), 1)
        self.assertEqual(len(project.llm_traces), 1)
        self.assertEqual(project.llm_traces[0].status.value, "succeeded")

    def test_evolve_between_renders_sequentially_from_the_previous_image(self) -> None:
        krea = _ImmediateKrea()
        self.service.krea2 = krea
        project = self.create_project()
        identifiers = iter(("candidate-a", "candidate-b", "candidate-c"))
        self.service._candidate_id = lambda: next(identifiers)
        self.service.queue_candidates(
            project.project_id,
            role=ProductionV2AnchorRole.CALIBRATION,
            instruction="Push the direction after every image.",
            model_id="local::requested-qwen",
            settings=(self.settings(), self.settings(), self.settings()),
            prompt_strategy=ProductionV2PromptStrategy.EVOLVE_BETWEEN,
            reference_mode=ProductionV2ReferenceMode.NONE,
        )
        project = self.wait_until_idle(project.project_id)
        candidates = [project.candidate(value) for value in ("candidate-a", "candidate-b", "candidate-c")]
        self.assertEqual(len(krea.stream_calls), 3)
        self.assertIsNone(candidates[0].feedback_parent_id)
        self.assertEqual(candidates[1].feedback_parent_id, "candidate-a")
        self.assertEqual(candidates[2].feedback_parent_id, "candidate-b")
        self.assertEqual(candidates[1].guidance_candidate_id, "candidate-a")
        self.assertEqual(krea.stream_calls[1][2]["guidance_asset_id"], "candidate-output")
        self.assertEqual([value.sequence for value in project.llm_traces], [1, 2, 3])

    def test_cross_role_image_requires_explicit_guidance_not_a_feedback_parent(self) -> None:
        krea = _ImmediateKrea()
        self.service.krea2 = krea
        project = self.completed_candidate(self.create_project())
        with self.assertRaisesRegex(ValueError, "same role"):
            self.service.queue_candidates(
                project.project_id,
                role=ProductionV2AnchorRole.FIRST_FRAME,
                instruction="Start cleanly before the action.",
                model_id="local::qwen",
                settings=(self.settings(),),
                feedback_parent_id="candidate-test",
                prompt_strategy=ProductionV2PromptStrategy.REWRITE_ONCE,
            )
        self.service._candidate_id = lambda: "candidate-first"
        self.service.queue_candidates(
            project.project_id,
            role=ProductionV2AnchorRole.FIRST_FRAME,
            instruction="Start cleanly before the action.",
            model_id="local::qwen",
            settings=(self.settings(),),
            prompt_strategy=ProductionV2PromptStrategy.REWRITE_ONCE,
            reference_mode=ProductionV2ReferenceMode.RECIPE_AND_GUIDANCE,
            guidance_candidate_id="candidate-test",
        )
        project = self.wait_until_idle(project.project_id)
        candidate = project.candidate("candidate-first")
        self.assertIsNone(candidate.feedback_parent_id)
        self.assertEqual(candidate.guidance_candidate_id, "candidate-test")
        self.assertEqual(krea.stream_calls[0][2]["guidance_asset_id"], "candidate-output")

    def test_validated_base_preselects_but_does_not_lock_next_candidate_settings(self) -> None:
        krea = _ImmediateKrea()
        self.service.krea2 = krea
        project = self.completed_candidate(self.create_project())
        project = self.service.validate_visual_recipe(project.project_id, "candidate-test")
        self.service._candidate_id = lambda: "candidate-next"
        alternative = Krea2BatchSettings(
            model_name="Another_Krea2_BF16.safetensors",
            aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
            megapixels=0.8,
            loras=(),
        )
        self.service.queue_candidates(
            project.project_id,
            role=ProductionV2AnchorRole.FIRST_FRAME,
            instruction="Create the calm frame before action.",
            model_id="local::qwen",
            settings=(alternative,),
        )
        project = self.wait_until_idle(project.project_id)
        candidate = project.candidate("candidate-next")
        self.assertEqual(candidate.settings, alternative)
        self.assertEqual(krea.create_calls[0]["reference_asset_id"], "candidate-output")

    def test_resolution_clone_reuses_prompt_seed_checkpoint_and_loras(self) -> None:
        krea = _ImmediateKrea()
        self.service.krea2 = krea
        project = self.completed_candidate(self.create_project())
        parent = replace(project.candidate("candidate-test"), settings=replace(self.settings(), megapixels=0.8))
        self.store.save_project(project.replace_candidate(parent))
        self.service._candidate_id = lambda: "candidate-high"
        self.service.queue_resolution_clone(project.project_id, "candidate-test", megapixels=2.1)
        project = self.wait_until_idle(project.project_id)
        clone = project.candidate("candidate-high")
        self.assertEqual(clone.generation_kind, ProductionV2CandidateKind.RESOLUTION_CLONE)
        self.assertEqual(clone.prompt, parent.prompt)
        self.assertEqual(clone.seed, parent.seed)
        self.assertEqual(clone.settings.model_name, parent.settings.model_name)
        self.assertEqual(clone.settings.loras, parent.settings.loras)
        self.assertEqual(clone.settings.megapixels, 2.1)
        self.assertEqual(krea.stream_calls, [])
        self.assertEqual(krea.prepare_calls[0][1]["seed"], 42)

    def test_resolution_clone_accepts_four_megapixels(self) -> None:
        krea = _ImmediateKrea()
        self.service.krea2 = krea
        project = self.completed_candidate(self.create_project())
        self.service._candidate_id = lambda: "candidate-four-mp"

        self.service.queue_resolution_clone(
            project.project_id, "candidate-test", megapixels=4.0,
        )
        project = self.wait_until_idle(project.project_id)

        clone = project.candidate("candidate-four-mp")
        self.assertEqual(clone.settings.megapixels, 4.0)
        self.assertEqual(clone.prompt, "Vertical fantasy portrait")
        self.assertEqual(clone.seed, 42)

    def test_assisted_lora_batch_uses_one_planner_call_and_controlled_variants(self) -> None:
        krea = _ImmediateKrea()
        gateway = _LoraGateway()
        memory = _LoraMemory()
        self.service.krea2 = krea
        self.service.gateway = gateway
        self.service.lora_resources = _LoraResources()
        self.service.lora_memory = memory
        project = self.completed_candidate(self.create_project())
        identifiers = iter(("candidate-baseline", "candidate-wet", "candidate-contrast"))
        self.service._candidate_id = lambda: next(identifiers)
        baseline = replace(self.settings(), megapixels=2.1)
        self.service.queue_candidates(
            project.project_id,
            role=ProductionV2AnchorRole.CALIBRATION,
            instruction="",
            model_id="local::qwen",
            settings=(baseline, baseline, baseline),
            feedback_parent_id="candidate-test",
            technical_comparison=True,
            assisted_lora_selection=True,
            lora_instruction="Include wetness in one useful variant.",
        )
        project = self.wait_until_idle(project.project_id)
        variants = [project.candidate(value) for value in (
            "candidate-baseline", "candidate-wet", "candidate-contrast",
        )]
        self.assertEqual(len(gateway.requests), 1)
        self.assertEqual(krea.stream_calls, [])
        self.assertTrue(all(value.prompt == "Vertical fantasy portrait" for value in variants))
        self.assertTrue(all(value.seed == 42 for value in variants))
        self.assertEqual(variants[0].settings.loras, baseline.loras)
        self.assertEqual(variants[1].assisted_lora_names, ("wetness.safetensors",))
        self.assertEqual(variants[2].assisted_lora_names, ("cinematic.safetensors",))
        self.assertEqual(variants[1].settings.loras[-1].strength, 0.65)
        self.assertEqual(variants[2].settings.loras[-1].strength, -0.4)
        self.assertEqual(len(memory.plans), 2)
        self.assertEqual(len(project.llm_traces), 1)
        self.assertEqual(project.llm_traces[0].purpose, "lora_plan")
        self.assertEqual(project.llm_traces[0].status.value, "succeeded")
        self.assertIn('"variants"', project.llm_traces[0].output)

    def test_frozen_prompt_and_seed_can_still_explore_checkpoints(self) -> None:
        krea = _ImmediateKrea()
        self.service.krea2 = krea
        project = self.completed_candidate(self.create_project())
        identifiers = iter(("candidate-a", "candidate-b", "candidate-c"))
        self.service._candidate_id = lambda: next(identifiers)
        settings = tuple(replace(
            self.settings(), model_name=f"Krea2_Explore_{index}_BF16.safetensors",
            megapixels=0.8,
        ) for index in range(1, 4))
        self.service.queue_candidates(
            project.project_id,
            role=ProductionV2AnchorRole.CALIBRATION,
            instruction="Keep the composition identical.",
            model_id="local::unused-for-frozen-prompt",
            settings=settings,
            feedback_parent_id="candidate-test",
            freeze_prompt_seed=True,
        )
        project = self.wait_until_idle(project.project_id)
        candidates = [project.candidate(value) for value in ("candidate-a", "candidate-b", "candidate-c")]
        self.assertEqual(krea.stream_calls, [])
        self.assertEqual([value.settings.model_name for value in candidates], [
            value.model_name for value in settings
        ])
        self.assertTrue(all(value.prompt == "Vertical fantasy portrait" for value in candidates))
        self.assertTrue(all(value.seed == 42 for value in candidates))

    def test_video_configuration_requires_explicit_recompile_for_contract_changes(self) -> None:
        project = self.create_project()
        project = self.store.save_project(replace(
            project,
            prompt_session_id="old-session",
            h3_project_id="old-h3",
            preview_attempt_ids=("old-preview",),
            selected_preview_attempt_id="old-preview",
        ))
        values = dict(
            video_intention="A much more frightening hand transformation.",
            aspect_ratio=VideoAspectRatio.PORTRAIT_WIDESCREEN,
            duration_seconds=6.0,
            preview_megapixels=0.2,
            final_megapixels=1.2,
            steps=25,
            seed_locked=True,
            spectrum_enabled=True,
            music_enabled=False,
            video_lora=None,
        )
        with self.assertRaisesRegex(ValueError, "recompile Brief"):
            self.service.configure_video(project.project_id, **values)
        project = self.service.configure_video(
            project.project_id, **values, invalidate_compilation=True,
        )
        self.assertIsNone(project.h3_project_id)
        self.assertEqual(project.preview_attempt_ids, ())
        self.assertEqual(project.archived_h3_project_ids, ("old-h3",))
        self.assertEqual(project.archived_prompt_session_ids, ("old-session",))
        self.assertEqual(project.video_steps, 25)
        self.assertTrue(project.spectrum_enabled)

    def test_duration_change_keeps_compilation_and_emits_a_warning(self) -> None:
        self.service.h3_render = _H3()
        project = self.store.save_project(replace(
            self.create_project(),
            prompt_session_id="current-session",
            h3_project_id="h3-project",
            preview_attempt_ids=("old-preview",),
            selected_preview_attempt_id="old-preview",
        ))

        project = self.service.configure_video(
            project.project_id,
            video_intention=project.intention,
            aspect_ratio=VideoAspectRatio.PORTRAIT_WIDESCREEN,
            duration_seconds=10.0,
            preview_megapixels=0.2,
            final_megapixels=1.2,
            steps=25,
            seed_locked=True,
            spectrum_enabled=True,
            music_enabled=False,
            video_lora=None,
        )

        self.assertEqual(project.duration_seconds, 10.0)
        self.assertEqual(project.h3_project_id, "h3-project")
        self.assertEqual(project.preview_attempt_ids, ("old-preview",))
        self.assertIn("Prompt compilé pour 6 s", project.events[-1].message)
        self.assertEqual(project.events[-1].level, "warning")

    def test_compile_audacity_invalidates_but_revision_audacity_does_not(self) -> None:
        project = self.store.save_project(replace(
            self.create_project(),
            prompt_session_id="current-session",
            h3_project_id="current-h3",
        ))
        values = dict(
            video_intention=project.intention,
            aspect_ratio=VideoAspectRatio.PORTRAIT_WIDESCREEN,
            duration_seconds=6.0,
            preview_megapixels=0.2,
            final_megapixels=1.2,
            steps=25,
            seed_locked=True,
            spectrum_enabled=True,
            music_enabled=False,
            video_lora=None,
        )

        project = self.service.configure_video(
            project.project_id,
            **values,
            creative_audacity=3,
            revision_audacity=1,
        )
        self.assertEqual(project.h3_project_id, "current-h3")
        self.assertEqual(project.revision_audacity, 1)
        with self.assertRaisesRegex(ValueError, "recompile Brief"):
            self.service.configure_video(
                project.project_id,
                **values,
                creative_audacity=2,
                revision_audacity=1,
            )

    def test_compile_model_is_persisted_without_changing_initial_model(self) -> None:
        project = self.create_project()
        project = self.service.configure_video(
            project.project_id,
            video_intention=project.intention,
            compile_model_id="server::brief-plan-prompt",
            aspect_ratio=VideoAspectRatio.PORTRAIT_WIDESCREEN,
            duration_seconds=6.0,
            preview_megapixels=0.2,
            final_megapixels=1.2,
            steps=25,
            seed_locked=True,
            spectrum_enabled=True,
            music_enabled=False,
            video_lora=None,
        )

        self.assertEqual(project.initial_model_id, "local::qwen")
        self.assertEqual(project.effective_video_compile_model_id, "server::brief-plan-prompt")
        self.assertEqual(
            self.service.get(project.project_id).video_compile_model_id,
            "server::brief-plan-prompt",
        )

    def test_video_chat_revision_does_not_start_a_render(self) -> None:
        h3 = _RevisionH3()
        self.service.h3_render = h3
        project = self.store.save_project(replace(
            self.create_project(), h3_project_id="h3-project",
            stage=ProductionV2Stage.VIDEO_PREVIEW,
        ))
        self.service.queue_video_revision(
            project.project_id,
            instruction="Make the transformation more readable.",
            model_id="local::revision-model",
            revision_audacity=3,
        )
        project = self.wait_until_idle(project.project_id)
        self.assertEqual(project.status.value, "ready")
        self.assertEqual(len(h3.stream_calls), 1)
        self.assertEqual(h3.stream_calls[0][2]["model_id"], "local::revision-model")
        self.assertEqual(h3.stream_calls[0][2]["creative_audacity"], 3)
        self.assertEqual(project.revision_audacity, 3)
        self.assertEqual(h3.prepare_calls, [])

    def test_zero_revision_audacity_uses_the_historical_chat_contract(self) -> None:
        h3 = _RevisionH3()
        self.service.h3_render = h3
        project = self.store.save_project(replace(
            self.create_project(), h3_project_id="h3-project",
            stage=ProductionV2Stage.VIDEO_PREVIEW,
        ))
        self.service.queue_video_revision(
            project.project_id,
            instruction="Keep the same scene and make the action clearer.",
            revision_audacity=0,
        )
        project = self.wait_until_idle(project.project_id)
        self.assertIsNone(h3.stream_calls[0][2]["creative_audacity"])
        self.assertEqual(project.revision_audacity, 0)
        self.assertIn("standard historique", project.events[-2].message)
        self.assertEqual(h3.prepare_calls, [])

    def test_rejected_video_revision_is_retried_only_when_explicitly_requested(self) -> None:
        h3 = _RevisionH3()
        self.service.h3_render = h3
        project = self.store.save_project(replace(
            self.create_project(), h3_project_id="h3-project",
            stage=ProductionV2Stage.VIDEO_PREVIEW,
        ))

        self.service.queue_video_revision(
            project.project_id,
            instruction="",
            model_id="local::repair-model",
            revision_audacity=0,
            repair_rejected=True,
        )
        project = self.wait_until_idle(project.project_id)

        self.assertEqual(len(h3.stream_calls), 1)
        self.assertTrue(h3.stream_calls[0][2]["repair_rejected"])
        self.assertIn("Corrige la structure", h3.stream_calls[0][1])
        self.assertTrue(any("1 appel LLM" in event.message for event in project.events))
        self.assertEqual(h3.prepare_calls, [])

    def test_candidate_can_be_used_as_direct_ref2v_base(self) -> None:
        project = self.completed_candidate(self.create_project())
        project = self.service.use_candidate_as_direct_reference(project.project_id, "candidate-test")
        self.assertEqual(project.route.value, "ref2va")
        self.assertEqual(project.active_recipe.source_candidate_id, "candidate-test")
        self.assertEqual(project.anchors[0].role, ProductionV2AnchorRole.REFERENCE)

    def test_cancelled_compile_must_release_its_worker_before_an_eight_second_retry(self) -> None:
        prompt_lab = _BlockingPromptLab()
        h3 = _H3()
        self.service.prompt_lab = prompt_lab
        self.service.composition = _Composition()
        self.service.h3_render = h3
        project = self.completed_candidate(self.create_project())
        self.service.validate_visual_recipe(project.project_id, "candidate-test")
        project = self.service.promote_anchor(
            project.project_id,
            role=ProductionV2AnchorRole.FIRST_FRAME,
            candidate_id="candidate-test",
        )

        first = self.service.queue_video_compile(project.project_id)
        self.assertIsNotNone(first.active_operation_id)
        self.assertTrue(prompt_lab.structure_started.wait(timeout=1))
        cancelled = self.service.cancel(project.project_id)
        self.assertIsNone(cancelled.active_operation_id)
        project = self.service.configure_video(
            project.project_id,
            video_intention=project.intention,
            aspect_ratio=VideoAspectRatio.PORTRAIT_WIDESCREEN,
            duration_seconds=8.0,
            preview_megapixels=0.2,
            final_megapixels=1.2,
            steps=25,
            seed_locked=True,
            spectrum_enabled=True,
            music_enabled=False,
            video_lora=None,
        )
        with self.assertRaisesRegex(ValueError, "Annulation en cours"):
            self.service.queue_video_compile(project.project_id)

        prompt_lab.release_structure.set()
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline and project.project_id in self.service._claimed:
            time.sleep(0.01)
        self.assertNotIn(project.project_id, self.service._claimed)

        self.service.queue_video_compile(project.project_id, render_preview=True)
        project = self.wait_until_idle(project.project_id)
        sources = [value[0][1] for value in prompt_lab.structure_values]
        self.assertIn("Create a 6-second video", sources[0])
        self.assertIn("Create a 8-second video", sources[1])
        self.assertNotIn("Create a 6-second video", sources[1])
        self.assertEqual(project.duration_seconds, 8.0)
        self.assertEqual(h3.prepare_calls[-1][1]["settings"].duration_seconds, 8.0)
        self.assertIsNone(project.active_operation_id)

    def test_cancelled_worker_that_has_not_started_cannot_claim_a_new_operation(self) -> None:
        prompt_lab = _PromptLab()
        self.service.prompt_lab = prompt_lab
        self.service.composition = _Composition()
        self.service.h3_render = _H3()
        operation_ids = iter(("operation-old", "operation-new"))
        self.service._operation_id = lambda: next(operation_ids)
        project = self.completed_candidate(self.create_project())
        self.service.validate_visual_recipe(project.project_id, "candidate-test")
        project = self.service.promote_anchor(
            project.project_id,
            role=ProductionV2AnchorRole.FIRST_FRAME,
            candidate_id="candidate-test",
        )
        workers = []

        class _DeferredThread:
            def __init__(self, *, target, args, daemon):
                self.target = target
                self.args = args

            def start(self):
                workers.append((self.target, self.args))

        with patch("panelforge.application.production_v2.Thread", _DeferredThread):
            self.service.queue_video_compile(project.project_id)
            self.service.cancel(project.project_id)
            project = self.service.configure_video(
                project.project_id,
                video_intention=project.intention,
                aspect_ratio=VideoAspectRatio.PORTRAIT_WIDESCREEN,
                duration_seconds=8.0,
                preview_megapixels=0.2,
                final_megapixels=1.2,
                steps=25,
                seed_locked=True,
                spectrum_enabled=True,
                music_enabled=False,
                video_lora=None,
            )
            self.service.queue_video_compile(project.project_id)

        workers[0][0](*workers[0][1])
        self.assertEqual(prompt_lab.structure_values, [])
        workers[1][0](*workers[1][1])
        self.assertEqual(len(prompt_lab.structure_values), 1)
        self.assertIn("Create a 8-second video", prompt_lab.structure_values[0][0][1])
        project = self.service.get(project.project_id)
        self.assertEqual(project.status.value, "ready")
        self.assertIsNone(project.active_operation_id)

    def test_h3_base_compile_runs_brief_plan_and_final_prompt(self) -> None:
        prompt_lab = _PromptLab()
        composition = _Composition()
        self.service.prompt_lab = prompt_lab
        self.service.composition = composition
        self.service.h3_render = _H3()
        project = self.completed_candidate(self.create_project())
        self.service.validate_visual_recipe(project.project_id, "candidate-test")
        project = self.service.promote_anchor(
            project.project_id,
            role=ProductionV2AnchorRole.FIRST_FRAME,
            candidate_id="candidate-test",
        )
        project = self.store.save_project(replace(
            project, video_compile_model_id="local::brief-plan-prompt",
        ))
        self.service.queue_video_compile(project.project_id)
        project = self.wait_until_idle(project.project_id)
        self.assertEqual(project.status.value, "ready")
        self.assertEqual(project.h3_project_id, "h3-project")
        self.assertEqual(project.video_seed, 999)
        self.assertEqual(prompt_lab.create_values[0]["brief_variant_id"], "creative-direction")
        self.assertEqual(prompt_lab.create_values[0]["brief_variant_version"], "0.2.0")
        self.assertEqual(prompt_lab.create_values[0]["model_id"], "local::brief-plan-prompt")
        self.assertEqual(prompt_lab.structure_values[0][1]["creative_audacity"], 3)
        self.assertEqual(composition.generated, [
            CompositionStage.BEAT_SHEET,
            CompositionStage.FINAL_PROMPT,
        ])
        bindings = composition.configured[3]
        self.assertEqual(bindings[0].slot_id, "first_frame")
        self.assertEqual(bindings[0].reference_ids, ("ref-1",))
        self.assertEqual(
            [trace.purpose for trace in project.llm_traces],
            ["video_brief", "video_beat_sheet", "video_final_prompt"],
        )
        self.assertTrue(all(trace.status.value == "succeeded" for trace in project.llm_traces))
        self.assertTrue(all(trace.total == 3 for trace in project.llm_traces))
        self.assertIn("Analyse du brief", project.llm_traces[0].thinking)
        self.assertIn("Brief structur", project.llm_traces[0].output)

    def test_ref2v_compile_uses_its_creative_variant_at_maximum_audacity(self) -> None:
        prompt_lab = _PromptLab()
        composition = _Composition()
        self.service.prompt_lab = prompt_lab
        self.service.composition = composition
        self.service.h3_render = _H3()
        project = self.completed_candidate(self.create_project())
        project = self.service.use_candidate_as_direct_reference(
            project.project_id,
            "candidate-test",
        )

        self.service.queue_video_compile(project.project_id)
        project = self.wait_until_idle(project.project_id)

        self.assertEqual(project.status.value, "ready")
        self.assertEqual(
            prompt_lab.create_values[0]["profile_id"],
            "minimax.h3.ref2v.direct",
        )
        self.assertEqual(prompt_lab.create_values[0]["brief_variant_id"], "creative-direction")
        self.assertEqual(prompt_lab.structure_values[0][1]["creative_audacity"], 3)

    def test_video_compile_can_continue_directly_into_a_preview(self) -> None:
        prompt_lab = _PromptLab()
        composition = _Composition()
        h3 = _H3()
        self.service.prompt_lab = prompt_lab
        self.service.composition = composition
        self.service.h3_render = h3
        project = self.completed_candidate(self.create_project())
        self.service.validate_visual_recipe(project.project_id, "candidate-test")
        project = self.service.promote_anchor(
            project.project_id,
            role=ProductionV2AnchorRole.FIRST_FRAME,
            candidate_id="candidate-test",
        )

        self.service.queue_video_compile(project.project_id, render_preview=True)
        project = self.wait_until_idle(project.project_id)

        self.assertEqual(project.status.value, "ready")
        self.assertEqual(project.active_operation, None)
        self.assertEqual(project.preview_attempt_ids, ("attempt-1",))
        self.assertEqual(project.selected_preview_attempt_id, "attempt-1")
        self.assertEqual(len(h3.prepare_calls), 1)
        self.assertEqual(h3.prepare_calls[0][1]["settings"].megapixels, 0.2)
        self.assertTrue(h3.prepare_calls[0][1]["spectrum_enabled"])
        self.assertIn("validation humaine attendue", project.events[-1].message)


if __name__ == "__main__":
    unittest.main()
