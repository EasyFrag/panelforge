from pathlib import Path
from dataclasses import dataclass
import tempfile
import unittest

from panelforge.application import (
    disable_non_diegetic_music,
    H3RenderService,
    extract_plan_cut_times_ms,
    plan_keyframe_timestamps_ms,
)
from panelforge.domain import (
    H3RenderInputMode,
    H3RenderAttemptStatus,
    H3RenderProject,
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
    load_h3_render_workflow,
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
    / "0.1.0"
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

    def compile(self, mode: H3RenderInputMode):
        return self.recipe.build_workflow(
            input_mode=mode,
            first_frame="first.png" if mode in {H3RenderInputMode.I2VA, H3RenderInputMode.FL2VA} else None,
            last_frame="last.png" if mode in {H3RenderInputMode.L2VA, H3RenderInputMode.FL2VA} else None,
            prompt="integrated_multimodal_description:\n[Shot 1] A test.\noverall_soundscape:\nNone.\nnon_diegetic_music:\nN/A",
            settings=self.settings,
            output_filename_prefix="video/h3/test",
            keyframe_indices=(0, 72, 96, 215),
        )

    def test_exact_supplied_workflow_is_versioned(self) -> None:
        self.assertEqual(
            self.recipe.reference.workflow_sha256,
            "b7527b1b9ef5b3cee661c81440274b096652a35d54e36a1f5001b5d75dacac0c",
        )
        workflow = self.recipe.preset.workflow
        self.assertEqual(workflow["9"]["class_type"], "LoadImage")
        self.assertEqual(workflow["10"]["class_type"], "LoadImage")
        self.assertEqual(workflow["16"]["inputs"]["first_frame"], ["9", 0])
        self.assertEqual(workflow["16"]["inputs"]["last_frame"], ["10", 0])

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


class H3RenderPromptAndKeyframeTest(unittest.TestCase):
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
            )
            service.queue_attempt(prepared.project_id, "attempt-1")
            result = service.execute_attempt(prepared.project_id, "attempt-1")

            attempt = result.attempt("attempt-1")
            self.assertEqual(attempt.status, H3RenderAttemptStatus.SUCCEEDED)
            self.assertEqual(len(attempt.keyframes), 5)
            self.assertEqual(result.feedback_attempt_id, "attempt-1")
            self.assertNotIn("9", comfy.submitted[0])
            self.assertNotIn("10", comfy.submitted[0])
            self.assertEqual(comfy.submitted[0]["14"]["inputs"]["value"].rstrip(), prompt)

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
