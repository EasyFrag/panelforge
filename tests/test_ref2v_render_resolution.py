"""User-run regressions for independent REF2V resolutions; all services are fakes."""

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from panelforge.application import H3RenderService
from panelforge.domain import H3RenderInputMode, H3RenderAttemptStatus, H3RenderProject, VideoAspectRatio, VideoLabSettings
from panelforge.features.lab.web import H3RenderAttemptBody, serialize_h3_render_project
from panelforge.infrastructure.presets import H3RenderPresetRecipe, Ref2VH3RenderPresetRecipe, VideoLabPresetRecipe, load_h3_render_workflow, load_video_lab_workflow
from panelforge.infrastructure.storage import LocalAssetStore, LocalH3RenderProjectStore
from tests.test_h3_render import CompletedGateway, ImmediateH3Comfy, PNG, RESOLUTION_WORKFLOW_DIRECTORY


ROOT = Path(__file__).resolve().parents[1] / "workflows/video.generate.ref2v/minimax-h3-ref2v"
PROMPT = "Use <Picture 1> only for subject identity.\n\nThe target video is one continuous 9-second shot. The camera holds a static shot.\nShot 1: The subject walks.\noverall_soundscape: Footsteps.\nnon_diegetic_music: N/A"


def recipe(version):
    return Ref2VH3RenderPresetRecipe(VideoLabPresetRecipe(load_video_lab_workflow(ROOT / version)))


class Ref2VComfy(ImmediateH3Comfy):
    def get_history(self, prompt_id):
        outputs = {"5": {"images": [{"filename": "result.mp4", "type": "output"}]}}
        outputs.update({str(20100 + i): {"images": [{"filename": f"frame-{i}.png", "type": "output"}]} for i in range(8)})
        return {prompt_id: {"status": {"status_str": "success", "completed": True}, "outputs": outputs}}


class Ref2VResolutionTest(unittest.TestCase):
    def test_defaults_and_independent_bindings_with_historical_recipe_unchanged(self):
        current, old = recipe("0.2.1"), recipe("0.2.0")
        preset = current.presets["h3-balanced"]
        self.assertEqual((preset.initial_megapixels, preset.megapixels), (0.2, 0.2))
        self.assertTrue(current.supports_initial_megapixels)
        self.assertFalse(old.supports_initial_megapixels)
        self.assertEqual(old.presets["h3-balanced"].megapixels, 1.2)
        body = H3RenderAttemptBody(prompt=PROMPT, aspect_ratio=preset.aspect_ratio.value,
            megapixels=0.2, duration_seconds=9, steps=25)
        self.assertTrue(body.seed_locked)
        self.assertFalse(body.model_copy(update={"seed_locked": False}).seed_locked)
        for initial, output in ((0.2, 0.2), (0.6, 1.2), (1.2, 0.2)):
            settings = VideoLabSettings(aspect_ratio=preset.aspect_ratio, megapixels=output, duration_seconds=9, steps=25, seed=0, seed_locked=True)
            workflow = current.build_workflow(source_images=("first.png", "last.png"), prompt=PROMPT, settings=settings,
                initial_megapixels=initial, output_filename_prefix="video/test", keyframe_indices=())
            self.assertEqual(workflow["20"]["inputs"]["megapixels"], initial)
            self.assertEqual(workflow["23"]["inputs"]["value"], output)
            self.assertEqual(workflow["31"]["inputs"]["noise_seed"], 0)
        self.assertEqual(current.recipe.preset.workflow["20"]["inputs"]["megapixels"], 0.2)
        self.assertEqual(current.recipe.preset.workflow["23"]["inputs"]["value"], 0.2)
        for value in (True, 0, 0.25, 16.1, float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                current.build_workflow(source_images=("first.png",), prompt=PROMPT, settings=settings,
                    initial_megapixels=value, output_filename_prefix="video/test", keyframe_indices=())
        with self.assertRaisesRegex(ValueError, "historique"):
            old.build_workflow(source_images=("first.png",), prompt=PROMPT, settings=settings,
                initial_megapixels=0.6, output_filename_prefix="video/test", keyframe_indices=())

    def test_service_sends_initial_resolution_and_reopens_exact_recipe(self):
        with tempfile.TemporaryDirectory() as directory:
            assets = LocalAssetStore(directory)
            reference = assets.create(PNG, media_type="image/png")
            projects = LocalH3RenderProjectStore(directory)
            projects.create(H3RenderProject(project_id="ref-test", source_session_id="session", source_prompt_revision_id="prompt",
                model_id="fake", input_mode=H3RenderInputMode.REF2VA, current_prompt=PROMPT,
                reference_asset_ids=(reference.asset_id,), reference_labels=("Picture 1",)))
            comfy, gateway = Ref2VComfy(), CompletedGateway("{}")
            current, old = recipe("0.2.1"), recipe("0.2.0")
            service = H3RenderService(gateway=gateway, workflow=H3RenderPresetRecipe(load_h3_render_workflow(RESOLUTION_WORKFLOW_DIRECTORY)),
                ref2v_workflow=current, historical_ref2v_workflows=(old,), comfy=comfy, assets=assets, projects=projects,
                sessions=object(), compositions=object())
            settings = VideoLabSettings(aspect_ratio=VideoAspectRatio.PORTRAIT_WIDESCREEN, megapixels=0.2, duration_seconds=9,
                steps=25, seed=123, seed_locked=True)
            prepared = service.prepare_attempt("ref-test", prompt=PROMPT, settings=settings, initial_megapixels=0.6)
            attempt_id = prepared.attempts[-1].attempt_id
            service.queue_attempt("ref-test", attempt_id)
            result = service.execute_attempt("ref-test", attempt_id)
            self.assertEqual(result.attempt(attempt_id).status, H3RenderAttemptStatus.SUCCEEDED)
            self.assertEqual(comfy.submitted[0]["20"]["inputs"]["megapixels"], 0.6)
            self.assertEqual(comfy.submitted[0]["23"]["inputs"]["value"], 0.2)
            self.assertEqual(comfy.submitted[0]["31"]["inputs"]["noise_seed"], 123)
            reopened = LocalH3RenderProjectStore(directory).get("ref-test")
            self.assertEqual(reopened.attempt(attempt_id).initial_megapixels, 0.6)
            self.assertTrue(reopened.attempt(attempt_id).settings.seed_locked)
            self.assertEqual(serialize_h3_render_project(reopened)["attempts"][0]["initial_megapixels"], 0.6)
            self.assertIs(service.recipe_for_attempt(reopened, reopened.attempt(attempt_id)), current)
            historical = replace(reopened.attempt(attempt_id), recipe=old.reference, initial_megapixels=0.2)
            self.assertIs(service.recipe_for_attempt(reopened, historical), old)
            self.assertNotIn(old, service.recipes_for_mode(H3RenderInputMode.T2VA))
            self.assertEqual(gateway.requests, [])
