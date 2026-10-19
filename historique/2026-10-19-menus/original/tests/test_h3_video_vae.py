"""User-run regression checks; all generation and storage use local fakes."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from panelforge.application.h3_render import H3RenderService
from panelforge.application.video_lab import VideoLabRunner, VideoLabRunRequest
from panelforge.application.episode_localization import EpisodeLocalizationActions
from panelforge.domain.episode_localization import attempt_setup
from panelforge.domain import (
    H3RenderInputMode, H3RenderProject,
    VideoAspectRatio, VideoLabSettings, VideoLabRunStatus,
)
from panelforge.domain.h3_bunny import H3BunnySettings
from panelforge.domain.h3_render import H3VideoLoraSlot, H3VideoLoraStack
from panelforge.infrastructure.presets import (
    H3RenderPresetRecipe, Ref2VH3RenderPresetRecipe, VideoLabPresetRecipe,
    load_h3_render_workflow, load_video_lab_workflow,
)
from panelforge.infrastructure.presets.h3_bunny import BunnyH3RenderRecipe
from panelforge.infrastructure.presets.h3_checkpoint import CheckpointH3RenderRecipe
from panelforge.infrastructure.presets.h3_loras import MultiLoraH3RenderRecipe
from panelforge.infrastructure.presets.h3_video_vae import H3VideoVaeUpdates
from panelforge.infrastructure.storage import LocalAssetStore, LocalH3RenderProjectStore, LocalVideoRunStore
from test_video_lab_runner import FakeComfy

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "workflows"
MANIFEST = WORKFLOWS / "video.vae/minimax-h3-int8-convrot/1.0.0/manifest.json"
OLD = "minimax_h3_video_vae_fp16.safetensors"
NEW = "minimax_h3_video_vae_int8_convrot.safetensors"
PROMPT = ("integrated_multimodal_description:\n[Shot 1] The target video is one continuous "
          "9-second shot. The camera holds a static shot. The kitten listens.\n"
          "overall_soundscape:\nRoom tone.\nnon_diegetic_music:\nNone.")


def source_recipe(entry):
    directory = WORKFLOWS / entry["source"]["directory"]
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if entry["source"]["recipe_id"] == "minimax-h3-bunny":
        recipe = BunnyH3RenderRecipe(directory)
    elif entry["source"]["recipe_id"] == "minimax-h3-ref2v":
        recipe = Ref2VH3RenderPresetRecipe(VideoLabPresetRecipe(load_video_lab_workflow(directory)))
    else:
        recipe = H3RenderPresetRecipe(load_h3_render_workflow(directory))
    if "video_lora_stack" in manifest:
        recipe = MultiLoraH3RenderRecipe(recipe, directory)
    elif "checkpoint_selection" in manifest:
        recipe = CheckpointH3RenderRecipe(recipe, directory)
    return recipe


def settings(mp=0.9):
    return VideoLabSettings(VideoAspectRatio.PORTRAIT_WIDESCREEN, mp, 9, 25, 2**63 + 5, True)


def parameters(recipe, mode, *, references=3):
    bunny = recipe.reference.recipe_id == "minimax-h3-bunny"
    values = dict(prompt=PROMPT, settings=settings(), output_filename_prefix="video/vae-test",
                  keyframe_indices=(0, 20), initial_megapixels=0.9 if bunny else 0.2)
    if mode is H3RenderInputMode.REF2VA:
        values["source_images"] = tuple(f"image-{i}.png" for i in range(references))
    else:
        values.update(input_mode=mode,
            first_frame="first.png" if mode in (H3RenderInputMode.I2VA, H3RenderInputMode.FL2VA) else None,
            last_frame="last.png" if mode in (H3RenderInputMode.L2VA, H3RenderInputMode.FL2VA) else None)
    if bunny:
        values["bunny"] = H3BunnySettings()
    return values


class H3VideoVaeTest(unittest.TestCase):
    def setUp(self):
        self.updates = H3VideoVaeUpdates(WORKFLOWS, MANIFEST)
        self.entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["recipes"]

    def assert_only_vae_changes(self, source, updated, args, node_id):
        original = source.build_workflow(**args)
        actual = updated.build_workflow(**args)
        self.assertEqual(original[node_id]["inputs"]["vae_name"], OLD)
        self.assertEqual(actual[node_id]["inputs"]["vae_name"], NEW)
        expected = deepcopy(original)
        expected[node_id]["inputs"]["vae_name"] = NEW
        # Whole-graph comparison protects audio, samplers, previews, seeds and wiring.
        self.assertEqual(actual, expected)
        self.assertEqual(source.build_workflow(**args), original)

    def test_every_source_version_and_input_mode_changes_only_the_video_vae(self):
        for entry in self.entries:
            source = source_recipe(entry)
            updated = self.updates.upgrade(source)
            for mode in H3RenderInputMode:
                family = source.reference.recipe_id
                if family == "minimax-h3-latent-speed" and mode is H3RenderInputMode.REF2VA:
                    continue
                if family == "minimax-h3-ref2v" and mode is not H3RenderInputMode.REF2VA:
                    continue
                counts = (1, 3, 9) if mode is H3RenderInputMode.REF2VA else (0,)
                for count in counts:
                    with self.subTest(source=source.reference, mode=mode, count=count):
                        self.assert_only_vae_changes(source, updated,
                            parameters(source, mode, references=count), entry["node_id"])

    def test_checkpoint_loras_and_upscale_choices_survive_the_update(self):
        for entry in self.entries:
            source = source_recipe(entry)
            if not getattr(source, "supports_video_lora_stack", False):
                continue
            updated = self.updates.upgrade(source)
            bunny = source.reference.recipe_id == "minimax-h3-bunny"
            mode = (H3RenderInputMode.REF2VA if source.reference.recipe_id != "minimax-h3-latent-speed"
                    else H3RenderInputMode.FL2VA)
            args = parameters(source, mode)
            args["checkpoint"] = "10Eros_Max_h3_hybrid_beta5.safetensors"
            args["video_loras"] = H3VideoLoraStack((
                H3VideoLoraSlot("minmax_nsfw/H3_Combat_V2.safetensors", .7, .15 if bunny else None),
                H3VideoLoraSlot("minmax_nsfw/Motion_Repair.safetensors", .55, .3 if bunny else None),
            ), clip_last_layer=None if bunny else -2)
            variants = [args]
            if getattr(source, "supports_upscale_bypass", False):
                variants += [{**args, "settings": settings(0.2), "force_upscale": force} for force in (False, True)]
            for variant in variants:
                with self.subTest(source=source.reference, force=variant.get("force_upscale")):
                    self.assert_only_vae_changes(source, updated, variant, entry["node_id"])

    def test_fingerprints_and_bindings_fail_closed(self):
        entry = next(e for e in self.entries if e["source"]["directory"].endswith("latent-speed/0.1.7"))
        recipe = source_recipe(entry)
        for field, wrong in (("workflow_sha256", "0" * 64), ("node_id", "13")):
            with self.subTest(field=field):
                bad = H3VideoVaeUpdates(WORKFLOWS, MANIFEST)
                next(e for e in bad.entries.values() if e["source"] == entry["source"])[field] = wrong
                with self.assertRaises(ValueError):
                    bad.upgrade(recipe)
        unknown = SimpleNamespace(reference=replace(recipe.reference, workflow_sha256="0" * 64))
        with self.assertRaisesRegex(ValueError, "no pinned"):
            self.updates.upgrade(unknown)

    def test_old_project_gets_new_attempt_without_rewriting_pending_history(self):
        entry = next(e for e in self.entries if e["source"]["directory"].endswith("latent-speed/0.1.7"))
        source = source_recipe(entry)
        with tempfile.TemporaryDirectory() as directory:
            projects = LocalH3RenderProjectStore(directory)
            projects.create(H3RenderProject(project_id="project-1", source_session_id="session-1",
                source_prompt_revision_id="prompt-1", model_id="fake", input_mode=H3RenderInputMode.T2VA,
                current_prompt=PROMPT))
            common = dict(gateway=object(), workflow=source, comfy=object(), projects=projects,
                          assets=LocalAssetStore(directory), sessions=object(), compositions=object())
            old_service = H3RenderService(**common)
            project = old_service.prepare_attempt("project-1", prompt=PROMPT, settings=settings())
            old = project.attempts[-1]
            old_service.queue_attempt(project.project_id, old.attempt_id)
            old = projects.get(project.project_id).attempt(old.attempt_id)
            service = H3RenderService(**common, recipe_upgrade=self.updates.upgrade)
            project = service.prepare_attempt("project-1", prompt=PROMPT, settings=settings(),
                recipe_id=source.reference.recipe_id, recipe_version=source.reference.version)
            new = project.attempts[-1]
            self.assertEqual(project.attempt(old.attempt_id), old)
            self.assertIs(service.recipe_for_attempt(project, old), source)
            self.assertIs(service.recipe_for_attempt(project, replace(old, recipe=None)), source)
            self.assertEqual(new.recipe, self.updates.upgrade(source).reference)
            self.assertEqual(new.settings, old.settings)
            self.assertEqual(new.effective_prompt, old.effective_prompt)
            self.assertEqual(service.recipe_for_attempt(project, new).reference, new.recipe)
            self.assertEqual(projects.get(project.project_id).attempts, project.attempts)
            with self.assertRaises(ValueError):
                service.recipe_for_attempt(project, replace(old, recipe=replace(old.recipe, workflow_sha256="0" * 64)))

            # The multilingual setup may still name the old recipe after the new render.
            localized = EpisodeLocalizationActions()
            localized.render = service
            setup = attempt_setup(old, {})
            self.assertTrue(localized._localized_setup_matches(project, setup, old))
            self.assertTrue(localized._localized_setup_matches(project, setup, new))
            self.assertFalse(localized._localized_setup_matches(project, attempt_setup(new, {}), old))
            changed = deepcopy(setup)
            changed["settings"]["seed"] = str(new.settings.seed + 1)
            self.assertFalse(localized._localized_setup_matches(project, changed, new))

    def test_video_lab_keeps_queued_source_run_and_uses_new_vae_for_next_run(self):
        directory = WORKFLOWS / "video.generate.ref2v/minimax-h3-ref2v/0.2.1"
        source = VideoLabPresetRecipe(load_video_lab_workflow(directory))
        with tempfile.TemporaryDirectory() as temporary:
            assets, runs, comfy = LocalAssetStore(temporary), LocalVideoRunStore(temporary), FakeComfy()
            image = assets.create(b"image", media_type="image/png")
            common = dict(comfy=comfy, assets=assets, runs=runs, sleep=lambda _: None)
            request = VideoLabRunRequest(source_asset_ids=(image.asset_id,), prompt="A shot.",
                                        preset_id=next(iter(source.presets)), seed=2**63 + 5)
            previous = VideoLabRunner(recipe=source, **common)
            old = previous.prepare(request)
            previous.queue(old.run_id)
            current = VideoLabRunner(recipe=self.updates.upgrade(source),
                                     historical_recipes=(source,), **common)
            self.assertEqual(current.execute(old.run_id).status, VideoLabRunStatus.SUCCEEDED)
            self.assertEqual(comfy.submitted[-1]["3"]["inputs"]["vae_name"], OLD)
            new = current.prepare(request)
            current.queue(new.run_id)
            self.assertEqual(current.execute(new.run_id).status, VideoLabRunStatus.SUCCEEDED)
            self.assertEqual(comfy.submitted[-1]["3"]["inputs"]["vae_name"], NEW)
            self.assertEqual(runs.get(old.run_id).recipe, source.reference)
            self.assertEqual(new.recipe, current.recipe.reference)
            self.assertEqual(new.settings, old.settings)
