from pathlib import Path
from dataclasses import dataclass
import json
import tempfile
import unittest

from panelforge.application import (
    canonicalize_h3_revision,
    disable_non_diegetic_music,
    H3RenderService,
    extract_plan_cut_times_ms,
    plan_keyframe_timestamps_ms,
)
from panelforge.application.h3_render import (
    compile_h3_revision_camera,
    protect_h3_revision_camera,
)
from panelforge.application.minimax_h3_protocol import (
    extract_compiled_camera_clauses,
)
from panelforge.application.prompt_lab import (
    CompletionResult,
    CompletionStreamEvent,
    StreamEventKind,
    StreamPhase,
)
from panelforge.domain import (
    H3RenderInputMode,
    H3RenderAttemptStatus,
    H3RenderProject,
    H3VideoLoraSelection,
    CompositionRevision,
    CompositionStage,
    CookbookBinding,
    CookbookRef,
    PromptComposition,
    PromptLabSession,
    PromptSessionMode,
    RevisionOrigin,
    StageDocument,
    VideoAspectRatio,
    VideoLabSettings,
)
from panelforge.infrastructure.presets import (
    H3RenderPresetRecipe,
    Ref2VH3RenderPresetRecipe,
    VideoLabPresetRecipe,
    load_h3_render_workflow,
    load_video_lab_workflow,
)
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalH3RenderProjectStore,
    LocalPromptCompositionStore,
    LocalPromptSessionStore,
)


WORKFLOW_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "workflows"
    / "video.generate.h3-base"
    / "minimax-h3-latent-speed"
    / "0.1.2"
)
LEGACY_WORKFLOW_DIRECTORY = WORKFLOW_DIRECTORY.parent / "0.1.1"
REF2V_WORKFLOW_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "workflows"
    / "video.generate.ref2v"
    / "minimax-h3-ref2v"
    / "0.2.0"
)
MP4 = b"\x00\x00\x00\x18ftypisomvideo"
PNG = b"\x89PNG\r\n\x1a\nkeyframe"


@dataclass(frozen=True)
class Uploaded:
    workflow_value: str


class ImmediateH3Comfy:
    def __init__(self) -> None:
        self.submitted = []

    def upload_image(self, content, *, filename, subfolder=""):
        return Uploaded(f"{subfolder}/{filename}")

    def list_lora_models(self):
        return (
            "krea2/ignored.safetensors",
            "minmax_nsfw/MysticXXX_MMH3-V2.safetensors",
        )

    def submit_workflow(self, workflow):
        self.submitted.append(workflow)
        return "execution-1"

    def get_history(self, prompt_id):
        outputs = {
            "4": {"images": [{"filename": "result.mp4", "subfolder": "video", "type": "output"}]}
        }
        for index in range(5):
            outputs[str(9100 + index)] = {
                "images": [{"filename": f"keyframe-{index}.png", "subfolder": "video", "type": "output"}]
            }
        return {
            prompt_id: {
                "status": {"status_str": "success", "completed": True},
                "outputs": outputs,
            }
        }

    def download_output(self, *, filename, subfolder="", folder_type="output"):
        return MP4 if filename.endswith(".mp4") else PNG

    def cancel_execution(self, prompt_id):
        return None


class CompletedGateway:
    def __init__(self, response: str) -> None:
        self.response = response
        self.requests = []

    def stream(self, request):
        self.requests.append(request)
        yield CompletionStreamEvent(
            StreamEventKind.COMPLETED,
            StreamPhase.COMPLETED,
            result=CompletionResult(
                model_id=request.model_id,
                content=self.response,
                call_id="call-1",
            ),
        )


class H3RenderWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.recipe = H3RenderPresetRecipe(
            load_h3_render_workflow(WORKFLOW_DIRECTORY)
        )
        self.settings = VideoLabSettings(
            aspect_ratio=VideoAspectRatio.PORTRAIT_WIDESCREEN,
            megapixels=1.2,
            duration_seconds=9.0,
            steps=25,
            seed=123,
        )

    def compile(
        self,
        mode: H3RenderInputMode,
        video_lora: H3VideoLoraSelection | None = None,
    ):
        return self.recipe.build_workflow(
            input_mode=mode,
            first_frame="first.png" if mode in {H3RenderInputMode.I2VA, H3RenderInputMode.FL2VA} else None,
            last_frame="last.png" if mode in {H3RenderInputMode.L2VA, H3RenderInputMode.FL2VA} else None,
            prompt="integrated_multimodal_description:\n[Shot 1] A test.\noverall_soundscape:\nNone.\nnon_diegetic_music:\nN/A",
            settings=self.settings,
            output_filename_prefix="video/h3/test",
            keyframe_indices=(0, 72, 96, 215),
            video_lora=video_lora,
        )

    def test_exact_supplied_workflow_is_versioned(self) -> None:
        self.assertEqual(self.recipe.reference.version, "0.1.2")
        self.assertEqual(
            self.recipe.reference.workflow_sha256,
            "5a7e6e2283ee91764b785e520aa7c7b3f0002de98ba1c48e703c807e5e39c78a",
        )
        workflow = self.recipe.preset.workflow
        self.assertEqual(workflow["9"]["class_type"], "LoadImage")
        self.assertEqual(workflow["10"]["class_type"], "LoadImage")
        self.assertEqual(workflow["16"]["inputs"]["first_frame"], ["9", 0])
        self.assertEqual(workflow["16"]["inputs"]["last_frame"], ["10", 0])
        self.assertEqual(workflow["17"]["inputs"]["preview_fps"], 24)
        self.assertEqual(workflow["36"]["inputs"]["fps"], 24)
        self.assertEqual(self.recipe.presets["h3-latent-speed"].preview_fps, 24)

    def test_published_legacy_workflow_remains_standard_only(self) -> None:
        legacy = H3RenderPresetRecipe(load_h3_render_workflow(LEGACY_WORKFLOW_DIRECTORY))
        self.assertEqual(legacy.reference.version, "0.1.1")
        with self.assertRaisesRegex(ValueError, "does not support video LoRAs"):
            legacy.build_workflow(
                input_mode=H3RenderInputMode.T2VA,
                first_frame=None,
                last_frame=None,
                prompt="integrated_multimodal_description:\n[Shot 1] Test.\noverall_soundscape:\nNone.\nnon_diegetic_music:\nN/A",
                settings=self.settings,
                output_filename_prefix="video/h3/legacy",
                keyframe_indices=(),
                video_lora=H3VideoLoraSelection(
                    name="minmax_nsfw/model.safetensors"
                ),
            )

    def test_compiles_all_four_input_modes_without_synthetic_frames(self) -> None:
        t2v = self.compile(H3RenderInputMode.T2VA)
        first = self.compile(H3RenderInputMode.I2VA)
        last = self.compile(H3RenderInputMode.L2VA)
        both = self.compile(H3RenderInputMode.FL2VA)

        self.assertNotIn("9", t2v)
        self.assertNotIn("10", t2v)
        self.assertNotIn("first_frame", t2v["16"]["inputs"])
        self.assertNotIn("last_frame", t2v["16"]["inputs"])

        self.assertEqual(first["9"]["inputs"]["image"], "first.png")
        self.assertNotIn("10", first)
        self.assertEqual(first["19"]["inputs"]["first_frame"], ["9", 0])
        self.assertNotIn("last_frame", first["19"]["inputs"])

        self.assertNotIn("9", last)
        self.assertEqual(last["10"]["inputs"]["image"], "last.png")
        self.assertNotIn("first_frame", last["16"]["inputs"])
        self.assertEqual(last["16"]["inputs"]["last_frame"], ["10", 0])

        self.assertEqual(both["9"]["inputs"]["image"], "first.png")
        self.assertEqual(both["10"]["inputs"]["image"], "last.png")
        self.assertEqual(both["19"]["inputs"]["first_frame"], ["9", 0])
        self.assertEqual(both["19"]["inputs"]["last_frame"], ["10", 0])

    def test_keyframe_savers_read_the_decoded_video_batch(self) -> None:
        workflow = self.compile(H3RenderInputMode.FL2VA)
        self.assertEqual(workflow["9000"]["inputs"]["image"], ["11", 0])
        self.assertEqual(workflow["9001"]["inputs"]["batch_index"], 72)
        self.assertEqual(workflow["9103"]["inputs"]["images"], ["9003", 0])

    def test_standard_profile_keeps_the_published_graph_unchanged(self) -> None:
        workflow = self.compile(H3RenderInputMode.I2VA)

        self.assertNotIn("9200", workflow)
        self.assertNotIn("9201", workflow)
        self.assertEqual(workflow["42"]["inputs"]["model"], ["34", 0])
        self.assertEqual(workflow["16"]["inputs"]["clip"], ["21", 0])
        self.assertEqual(workflow["19"]["inputs"]["clip"], ["21", 0])

    def test_video_lora_overlay_rewires_only_model_and_clip_consumers(self) -> None:
        selection = H3VideoLoraSelection(
            name="minmax_nsfw/MysticXXX_MMH3-V2.safetensors",
            strength=0.5,
        )
        workflow = self.compile(H3RenderInputMode.I2VA, selection)

        self.assertEqual(workflow["9200"]["class_type"], "Power Lora Loader (rgthree)")
        self.assertEqual(workflow["9200"]["inputs"]["model"], ["34", 0])
        self.assertEqual(workflow["9200"]["inputs"]["clip"], ["21", 0])
        self.assertEqual(
            workflow["9200"]["inputs"]["lora_1"],
            {"on": True, "lora": selection.name, "strength": 0.5},
        )
        self.assertEqual(workflow["42"]["inputs"]["model"], ["9200", 0])
        self.assertEqual(workflow["9201"]["class_type"], "CLIPSetLastLayer")
        self.assertEqual(workflow["9201"]["inputs"]["stop_at_clip_layer"], -2)
        self.assertEqual(workflow["16"]["inputs"]["clip"], ["9201", 0])
        self.assertEqual(workflow["19"]["inputs"]["clip"], ["9201", 0])
        self.assertEqual(workflow["8"]["inputs"]["model"], ["34", 0])

    def test_video_lora_can_keep_the_standard_clip_layers(self) -> None:
        workflow = self.compile(
            H3RenderInputMode.T2VA,
            H3VideoLoraSelection(
                name="minmax_nsfw/MysticXXX_MMH3-V2.safetensors",
                strength=1,
                clip_last_layer=None,
            ),
        )

        self.assertNotIn("9201", workflow)
        self.assertEqual(workflow["16"]["inputs"]["clip"], ["9200", 1])
        self.assertEqual(workflow["19"]["inputs"]["clip"], ["9200", 1])

    def test_video_lora_contract_rejects_unsafe_paths_and_strengths(self) -> None:
        for name in (
            "krea2/not-video.safetensors",
            "minmax_nsfw/../escape.safetensors",
            "minmax_nsfw/not-a-model.txt",
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                H3VideoLoraSelection(name=name)
        for strength in (-0.01, 1.01, True):
            with self.subTest(strength=strength), self.assertRaises(ValueError):
                H3VideoLoraSelection(
                    name="minmax_nsfw/model.safetensors",
                    strength=strength,
                )

    def test_ref2v_adapter_compiles_nine_images_and_keyframes(self) -> None:
        recipe = Ref2VH3RenderPresetRecipe(
            VideoLabPresetRecipe(load_video_lab_workflow(REF2V_WORKFLOW_DIRECTORY))
        )
        settings = VideoLabSettings(
            aspect_ratio=VideoAspectRatio.PORTRAIT_WIDESCREEN,
            megapixels=1.2,
            duration_seconds=9.0,
            steps=31,
            seed=123,
        )
        one_image = recipe.build_workflow(
            source_images=("reference-1.png",),
            prompt="<Picture 1>: subject reference.\n\nA scene.\nShot 1: Motion.\noverall_soundscape: None.\nnon_diegetic_music: N/A",
            settings=settings,
            output_filename_prefix="video/ref2v/one",
            keyframe_indices=(),
        )
        three_images = recipe.build_workflow(
            source_images=("reference-1.png", "reference-2.png", "reference-3.png"),
            prompt="<Picture 1>: subject reference.\n\nA scene.\nShot 1: Motion.\noverall_soundscape: None.\nnon_diegetic_music: N/A",
            settings=settings,
            output_filename_prefix="video/ref2v/three",
            keyframe_indices=(),
        )
        workflow = recipe.build_workflow(
            source_images=tuple(f"reference-{index}.png" for index in range(1, 10)),
            prompt="<Picture 1>: subject reference.\n\nA scene.\nShot 1: Motion.\noverall_soundscape: None.\nnon_diegetic_music: N/A",
            settings=settings,
            output_filename_prefix="video/ref2v/test",
            keyframe_indices=(0, 72),
        )

        self.assertEqual(recipe.reference.version, "0.2.0")
        self.assertEqual(recipe.presets["h3-balanced"].megapixels, 1.2)
        self.assertEqual(recipe.presets["h3-balanced"].duration_seconds, 10.0)
        self.assertNotIn("47", one_image)
        self.assertNotIn("ref_images.ref_image_1", one_image["11"]["inputs"])
        self.assertEqual(three_images["48"]["inputs"]["image"], "reference-3.png")
        self.assertNotIn("20003", three_images)
        self.assertEqual(workflow["48"]["inputs"]["image"], "reference-3.png")
        self.assertEqual(recipe.maximum_reference_images, 9)
        self.assertEqual(workflow["20008"]["inputs"]["image"], "reference-9.png")
        self.assertEqual(workflow["11"]["inputs"]["ref_images.ref_image_8"], ["20008", 0])
        self.assertEqual(workflow["23"]["inputs"]["value"], 1.2)
        self.assertEqual(workflow["24"]["inputs"]["steps"], 31)
        self.assertEqual(workflow["13"]["inputs"]["step"], 31)
        self.assertEqual(workflow["20050"]["inputs"]["image"], ["25", 0])
        self.assertEqual(workflow["20101"]["inputs"]["images"], ["20051", 0])


class H3RenderPromptAndKeyframeTest(unittest.TestCase):
    def test_camera_locked_revision_preserves_compiled_clauses(self) -> None:
        current = (
            "integrated_multimodal_description:\n"
            "[Shot 1] The target video is one continuous 9-second shot. "
            "The camera holds a static shot. The kitten listens. "
            "At 00:02.000, The camera tilts up with small amplitude at slow speed. "
            "The kitten answers.\n"
            "overall_soundscape:\nRoom tone.\n"
            "non_diegetic_music:\nNone."
        )
        clauses = extract_compiled_camera_clauses(current)
        protected = protect_h3_revision_camera(current, clauses)
        candidate = protected.replace("The kitten answers.", "The kitten answers softly.")

        compiled = compile_h3_revision_camera(candidate, clauses, clauses)
        result = canonicalize_h3_revision(
            current,
            compiled,
            H3RenderInputMode.T2VA,
            camera_clauses=clauses,
        )

        self.assertEqual(len(clauses), 2)
        self.assertNotIn("[[camera:", result)
        self.assertIn("The kitten answers softly.", result)
        for clause in clauses:
            self.assertEqual(result.count(clause), 1)

    def test_camera_locked_revision_rejects_static_bypass_prose(self) -> None:
        current = (
            "integrated_multimodal_description:\n"
            "[Shot 1] The target video is one continuous 9-second shot. "
            "The camera holds a static shot. The kitten listens.\n"
            "overall_soundscape:\nRoom tone.\n"
            "non_diegetic_music:\nNone."
        )
        clauses = extract_compiled_camera_clauses(current)
        candidate = current.replace(
            "The kitten listens.",
            "Camera movement: static. The kitten listens.",
        )

        with self.assertRaisesRegex(ValueError, "canonical compiled directive"):
            canonicalize_h3_revision(
                current,
                candidate,
                H3RenderInputMode.T2VA,
                camera_clauses=clauses,
            )

    def test_ref2v_revision_preserves_the_canonical_picture_header(self) -> None:
        current = (
            "Use <Picture 1> only for subject identity.\n\n"
            "The target video is one continuous 9-second shot.\n"
            "Shot 1: The subject walks.\n"
            "overall_soundscape: Footsteps.\n"
            "non_diegetic_music: N/A"
        )
        candidate = current.replace("walks", "walks continuously")

        result = canonicalize_h3_revision(
            current,
            candidate,
            H3RenderInputMode.REF2VA,
        )

        self.assertTrue(result.startswith("Use <Picture 1> only for subject identity."))
        self.assertIn("walks continuously", result)
    def test_multishot_plan_durations_define_intended_cut_boundaries(self) -> None:
        self.assertEqual(
            extract_plan_cut_times_ms(
                '{"shots":[{"duration_ms":3500},{"duration_ms":2500},{"duration_ms":3000}]}'
            ),
            (3500, 6000),
        )

    def test_music_off_changes_only_the_music_field(self) -> None:
        prompt = (
            "How the reference pictures align.\n\n"
            "integrated_multimodal_description:\n[Shot 1] The kitten speaks.\n"
            "overall_soundscape:\nFrench dialogue and room tone.\n"
            "non_diegetic_music:\nA gentle orchestral score."
        )
        result = disable_non_diegetic_music(prompt)
        self.assertIn("[Shot 1] The kitten speaks.", result)
        self.assertIn("French dialogue and room tone.", result)
        self.assertTrue(result.rstrip().endswith("non_diegetic_music:\nN/A"))
        self.assertNotIn("orchestral", result)

    def test_cut_keyframes_use_margin_and_never_the_exact_boundary(self) -> None:
        values = plan_keyframe_timestamps_ms(
            9000,
            (3500, 6500),
            margin_ms=500,
            maximum=8,
        )
        self.assertIn(3000, values)
        self.assertIn(4000, values)
        self.assertIn(6000, values)
        self.assertIn(7000, values)
        self.assertNotIn(3500, values)
        self.assertNotIn(6500, values)
        self.assertEqual(values[0], 0)
        self.assertLess(values[-1], 9000)

    def test_mono_plan_uses_five_evenly_distributed_frames(self) -> None:
        values = plan_keyframe_timestamps_ms(10000, (), margin_ms=500, maximum=8)
        self.assertEqual(len(values), 5)
        self.assertEqual(values[0], 0)
        self.assertGreater(values[-1], 9900)


class H3RenderRevisionVersionTest(unittest.TestCase):
    def prompt(self) -> str:
        return (
            "integrated_multimodal_description:\n"
            "[Shot 1] The target video is one continuous 9-second shot. "
            "The camera holds a static shot. The kitten listens.\n"
            "overall_soundscape:\nRoom tone.\n"
            "non_diegetic_music:\nNone."
        )

    def service(
        self,
        directory: str,
        response: str,
        *,
        prompt: str | None = None,
    ) -> tuple[H3RenderService, CompletedGateway]:
        projects = LocalH3RenderProjectStore(directory)
        projects.create(H3RenderProject(
            project_id="project-1",
            source_session_id="session-1",
            source_prompt_revision_id="prompt-1",
            model_id="qwen-model",
            input_mode=H3RenderInputMode.T2VA,
            current_prompt=prompt or self.prompt(),
        ))
        gateway = CompletedGateway(response)
        service = H3RenderService(
            gateway=gateway,
            workflow=H3RenderPresetRecipe(load_h3_render_workflow(WORKFLOW_DIRECTORY)),
            comfy=object(),
            assets=LocalAssetStore(directory),
            projects=projects,
            sessions=object(),
            compositions=object(),
            turn_id_factory=iter(("turn-user", "turn-assistant")).__next__,
        )
        return service, gateway

    def test_v020_uses_camera_tokens_and_records_the_turn_version(self) -> None:
        response = json.dumps({
            "message": "Le chaton sourit maintenant.",
            "questions": [],
            "prompt": self.prompt().replace(
                "The camera holds a static shot.",
                "[[camera:camera_1]]",
            ).replace("The kitten listens.", "The kitten listens and smiles."),
            "recommendations": [],
            "camera_directives": None,
        })
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = self.service(directory, response)

            terminal = list(service.stream_chat(
                "project-1",
                "Fais sourire le chaton.",
                revision_version="0.2.0",
            ))[-1].project

        self.assertEqual(gateway.requests[0].operation_id, "h3.base.render.revision@0.2.0")
        self.assertIn("[[camera:camera_1]]", gateway.requests[0].user_prompt)
        self.assertIn("listens and smiles", terminal.current_prompt)
        self.assertEqual(terminal.turns[-1].revision_version.value, "0.2.0")
        self.assertIsNone(terminal.revision_error)

    def test_v020_keeps_a_rejected_candidate_without_changing_prompt(self) -> None:
        response = json.dumps({
            "message": "Caméra statique.",
            "questions": [],
            "prompt": self.prompt().replace(
                "The camera holds a static shot.",
                "[[camera:camera_1]] Camera movement: static.",
            ),
            "recommendations": [],
            "camera_directives": None,
        })
        with tempfile.TemporaryDirectory() as directory:
            service, _ = self.service(directory, response)

            terminal_event = list(service.stream_chat(
                "project-1",
                "Ne change rien.",
                revision_version="0.2.0",
            ))[-1]
            terminal = terminal_event.project

        self.assertEqual(terminal.current_prompt, self.prompt())
        self.assertIn("Camera movement: static", terminal.revision_draft)
        self.assertIn("canonical compiled directive", terminal.revision_error)
        self.assertEqual(terminal.revision_draft_version.value, "0.2.0")

    def test_v020_migrates_the_former_static_camera_label_on_next_revision(self) -> None:
        legacy_prompt = self.prompt().replace(
            "The camera holds a static shot.",
            "Camera movement: static.",
        )
        response = json.dumps({
            "message": "Le chaton sourit maintenant.",
            "questions": [],
            "prompt": self.prompt().replace(
                "The camera holds a static shot.",
                "[[camera:camera_1]]",
            ).replace("The kitten listens.", "The kitten listens and smiles."),
            "recommendations": [],
            "camera_directives": None,
        })
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = self.service(directory, response, prompt=legacy_prompt)

            terminal = list(service.stream_chat(
                "project-1",
                "Fais sourire le chaton.",
                revision_version="0.2.0",
            ))[-1].project

        self.assertIn("[[camera:camera_1]]", gateway.requests[0].user_prompt)
        self.assertIn("The camera holds a static shot.", terminal.current_prompt)
        self.assertNotIn("Camera movement: static.", terminal.current_prompt)

    def test_v010_remains_available_for_legacy_revisions(self) -> None:
        response = json.dumps({
            "message": "Le chaton sourit maintenant.",
            "questions": [],
            "prompt": self.prompt().replace(
                "The kitten listens.",
                "The kitten listens and smiles.",
            ),
            "recommendations": [],
        })
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = self.service(directory, response)

            terminal = list(service.stream_chat(
                "project-1",
                "Fais sourire le chaton.",
                revision_version="0.1.0",
            ))[-1].project

        self.assertEqual(gateway.requests[0].operation_id, "h3.base.render.revision@0.1.0")
        self.assertNotIn("[[camera:", gateway.requests[0].user_prompt)
        self.assertIn("listens and smiles", terminal.current_prompt)
        self.assertEqual(terminal.turns[-1].revision_version.value, "0.1.0")


class H3RenderProjectPersistenceTest(unittest.TestCase):
    def test_render_persists_video_keyframes_and_selects_latest_feedback(self) -> None:
        prompt = (
            "integrated_multimodal_description:\n"
            "[Shot 1] The target video is one continuous 9-second shot. "
            "The camera holds a static shot. A kitten walks continuously through the final frame.\n"
            "overall_soundscape:\nQuiet room tone.\n"
            "non_diegetic_music:\nN/A"
        )
        with tempfile.TemporaryDirectory() as directory:
            projects = LocalH3RenderProjectStore(directory)
            projects.create(H3RenderProject(
                project_id="project-1",
                source_session_id="session-1",
                source_prompt_revision_id="prompt-1",
                model_id="qwen-model",
                input_mode=H3RenderInputMode.T2VA,
                current_prompt=prompt,
            ))
            comfy = ImmediateH3Comfy()
            service = H3RenderService(
                gateway=object(),
                workflow=H3RenderPresetRecipe(load_h3_render_workflow(WORKFLOW_DIRECTORY)),
                comfy=comfy,
                assets=LocalAssetStore(directory),
                projects=projects,
                sessions=object(),
                compositions=object(),
                attempt_id_factory=lambda: "attempt-1",
                sleep=lambda _: None,
            )
            prepared = service.prepare_attempt(
                "project-1",
                prompt=prompt,
                settings=VideoLabSettings(
                    aspect_ratio=VideoAspectRatio.PORTRAIT_WIDESCREEN,
                    megapixels=1.2,
                    duration_seconds=9.0,
                    steps=25,
                    seed=42,
                ),
                video_lora=H3VideoLoraSelection(
                    name="minmax_nsfw/MysticXXX_MMH3-V2.safetensors",
                    strength=0.5,
                ),
            )
            service.queue_attempt(prepared.project_id, "attempt-1")
            result = service.execute_attempt(prepared.project_id, "attempt-1")

            attempt = result.attempt("attempt-1")
            self.assertEqual(attempt.status, H3RenderAttemptStatus.SUCCEEDED)
            self.assertEqual(len(attempt.keyframes), 5)
            self.assertEqual(result.feedback_attempt_id, "attempt-1")
            self.assertEqual(attempt.video_lora.name, "minmax_nsfw/MysticXXX_MMH3-V2.safetensors")
            self.assertNotIn("9", comfy.submitted[0])
            self.assertNotIn("10", comfy.submitted[0])
            self.assertEqual(comfy.submitted[0]["42"]["inputs"]["model"], ["9200", 0])
            self.assertEqual(comfy.submitted[0]["14"]["inputs"]["value"].rstrip(), prompt)

            path = Path(directory) / "h3_render_projects" / "project-1" / "project.json"
            legacy = json.loads(path.read_text(encoding="utf-8"))
            legacy["schema_version"] = 1
            legacy["attempts"][0].pop("video_lora", None)
            path.write_text(json.dumps(legacy), encoding="utf-8")
            self.assertIsNone(projects.get("project-1").attempt("attempt-1").video_lora)

    def test_reopening_the_same_prompt_revision_resumes_the_same_project(self) -> None:
        prompt = (
            "integrated_multimodal_description:\n"
            "[Shot 1] One continuous shot.\n"
            "[Shot 2] At 00:03.500, a clean cut reveals the second view.\n"
            "overall_soundscape:\nRoom tone.\n"
            "non_diegetic_music:\nNone."
        )
        with tempfile.TemporaryDirectory() as directory:
            sessions = LocalPromptSessionStore(directory)
            sessions.create(PromptLabSession(
                session_id="session-1",
                model_id="qwen-model",
                profile_id="minimax.h3.fl2va.direct",
                profile_version="0.1.0",
                references=(),
                session_mode=PromptSessionMode.H3_BASE,
            ))
            compositions = LocalPromptCompositionStore(directory)
            compositions.create(PromptComposition(
                source_session_id="session-1",
                cookbook=CookbookRef(
                    cookbook_id="minimax.h3.fl2va.direct",
                    version="0.1.0",
                    engine_contract_id="minimax.h3.base",
                    engine_contract_version="1.0.0",
                ),
                bindings=(CookbookBinding("first_frame", ()),),
                final_prompt=StageDocument(
                    stage=CompositionStage.FINAL_PROMPT,
                    revisions=(CompositionRevision(
                        revision_id="prompt-1",
                        content=prompt,
                        origin=RevisionOrigin.MODEL,
                        source_ids=("plan-1",),
                    ),),
                    active_revision_id="prompt-1",
                    approved_revision_id="prompt-1",
                ),
            ))
            service = H3RenderService(
                gateway=object(),
                workflow=H3RenderPresetRecipe(load_h3_render_workflow(WORKFLOW_DIRECTORY)),
                comfy=object(),
                assets=LocalAssetStore(directory),
                projects=LocalH3RenderProjectStore(directory),
                sessions=sessions,
                compositions=compositions,
                project_id_factory=lambda: "h3-project-1",
            )

            first = service.get_or_create_from_session("session-1")
            reopened = service.get_or_create_from_session("session-1")

            self.assertEqual(first.project_id, reopened.project_id)
            self.assertEqual(first.input_mode, H3RenderInputMode.T2VA)
            self.assertEqual(first.planned_cut_times_ms, (3500,))


if __name__ == "__main__":
    unittest.main()
