"""User-run checkpoint regressions; temporary stores and fake ComfyUI only."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from fastapi.testclient import TestClient

from panelforge.application.h3_checkpoints import CachedH3Checkpoints
from panelforge.application.h3_render import H3RenderService
from panelforge.domain.h3_bunny import H3BunnySettings
from panelforge.domain.h3_checkpoint import H3ModelLoading, validate_h3_checkpoint
from panelforge.domain.h3_render import H3RenderAttempt, H3RenderAttemptStatus, H3RenderInputMode, H3RenderProject
from panelforge.domain.h3_render import H3VideoLoraSelection
from panelforge.domain.video_lab import VideoAspectRatio, VideoLabSettings
from panelforge.features.lab.web import H3RenderAttemptBody, create_app, serialize_h3_render_project
from panelforge.infrastructure.presets import (H3RenderPresetRecipe, Ref2VH3RenderPresetRecipe,
    VideoLabPresetRecipe, load_h3_render_workflow, load_video_lab_workflow)
from panelforge.infrastructure.presets.h3_bunny import BunnyH3RenderRecipe
from panelforge.infrastructure.presets.h3_checkpoint import CheckpointH3RenderRecipe
from panelforge.infrastructure.storage import LocalAssetStore, LocalH3RenderProjectStore
from panelforge.infrastructure.storage.h3_render_projects import _serialize, _deserialize
from tests.test_h3_render import CompletedGateway, ImmediateH3Comfy, PNG
from tests.test_ref2v_render_resolution import Ref2VComfy, PROMPT as REF_PROMPT


ROOT = Path(__file__).resolve().parents[1]
EROS = "10Eros_Max_h3_hybrid_beta5.safetensors"
ENTRIES = tuple(json.loads((ROOT / "src/panelforge/infrastructure/presets/h3_checkpoints.json").read_text(encoding="utf-8")))
LORA = "minmax_nsfw/MysticXXX_MMH3-V2.safetensors"
PROMPT = ("integrated_multimodal_description:\n[Shot 1] The target video is one continuous 9-second shot. "
          "The camera holds a static shot. A kitten walks continuously through the final frame.\n"
          "overall_soundscape:\nQuiet room tone.\nnon_diegetic_music:\nN/A")
VERSIONS = {
    "h3": ("video.generate.h3-base/minimax-h3-latent-speed", "0.1.3", "0.1.4"),
    "ref": ("video.generate.ref2v/minimax-h3-ref2v", "0.2.1", "0.2.2"),
    "bunny": ("video.generate.h3-base/minimax-h3-bunny", "0.1.0", "0.1.1"),
}


def recipe(kind, *, old=False):
    folder, previous, current = VERSIONS[kind]
    path = ROOT / "workflows" / folder / (previous if old else current)
    if kind == "bunny":
        base = BunnyH3RenderRecipe(path)
    elif kind == "ref":
        base = Ref2VH3RenderPresetRecipe(VideoLabPresetRecipe(load_video_lab_workflow(path)))
    else:
        base = H3RenderPresetRecipe(load_h3_render_workflow(path))
    return base if old else CheckpointH3RenderRecipe(base, path)


class H3CheckpointWorkflowTest(unittest.TestCase):
    def test_defaults_are_identical_and_alternate_changes_only_the_shared_source(self):
        for kind in VERSIONS:
            current, old = recipe(kind), recipe(kind, old=True)
            for mode in H3RenderInputMode:
                if kind == "h3" and mode is H3RenderInputMode.REF2VA:
                    continue
                if kind == "ref" and mode is not H3RenderInputMode.REF2VA:
                    continue
                for turbo in ((True, False) if kind == "bunny" else (True,)):
                    for lora in (None, H3VideoLoraSelection(LORA, 0.6, None)):
                        with self.subTest(kind=kind, mode=mode, turbo=turbo, lora=lora):
                            bunny = H3BunnySettings() if turbo else H3BunnySettings(False, 30, 25, 5, .2, False)
                            settings = VideoLabSettings(VideoAspectRatio.PORTRAIT_WIDESCREEN, .9, 9,
                                bunny.coarse_steps + bunny.refine_steps if kind == "bunny" else 25, 2**63 + 5, True)
                            kwargs = dict(prompt=REF_PROMPT if mode is H3RenderInputMode.REF2VA else PROMPT,
                                settings=settings, output_filename_prefix="video/test", keyframe_indices=(0, 10),
                                initial_megapixels=.9, video_lora=lora, spectrum_enabled=False)
                            if kind == "bunny":
                                kwargs["bunny"] = bunny
                            if mode is H3RenderInputMode.REF2VA:
                                kwargs["source_images"] = ("a.png", "b.png")
                            else:
                                kwargs.update(input_mode=mode,
                                    first_frame="a.png" if mode in (H3RenderInputMode.I2VA, H3RenderInputMode.FL2VA) else None,
                                    last_frame="b.png" if mode in (H3RenderInputMode.L2VA, H3RenderInputMode.FL2VA) else None)
                            expected = old.build_workflow(**kwargs)
                            self.assertEqual(current.build_workflow(**kwargs), expected)
                            before = deepcopy(expected)
                            selected = current.build_workflow(checkpoint=EROS, **kwargs)
                            key = "ref2va" if mode is H3RenderInputMode.REF2VA else "h3-base"
                            source = current.config["sources"][key]["node_id"]
                            replacement = deepcopy(current.config["direct_loader"])
                            replacement["inputs"][current.config["direct_checkpoint_input"]] = EROS
                            expected[source] = replacement
                            self.assertEqual(selected, expected)
                            self.assertFalse(any(n["class_type"] == "MiniMaxH3HybridLoader" for n in selected.values()))
                            self.assertEqual(current.build_workflow(**kwargs), before)
                            self.assertEqual(current.model_loading(mode, EROS), H3ModelLoading(EROS))
                            if kind == "bunny":
                                class FakeDescriptions:
                                    def describe_node(self, name):
                                        fields = {}
                                        for node in selected.values():
                                            if node["class_type"] == name:
                                                for key, value in node["inputs"].items():
                                                    if isinstance(value, str):
                                                        fields.setdefault(key, [[]])[0].append(value)
                                        return {name: {"input": {"required": fields}}}
                                current.validate_dependencies(FakeDescriptions(), selected)

    def test_recipe_defaults_remain_mode_specific(self):
        h3, ref, bunny = recipe("h3"), recipe("ref"), recipe("bunny")
        self.assertEqual(h3.model_loading(H3RenderInputMode.FL2VA).strategy, "direct")
        self.assertEqual(ref.model_loading(H3RenderInputMode.REF2VA).strategy, "hybrid")
        self.assertEqual(bunny.model_loading(H3RenderInputMode.REF2VA), ref.model_loading(H3RenderInputMode.REF2VA))
        for current in (h3, ref):
            self.assertTrue(all((p.initial_megapixels, p.megapixels) == (.2, .2) for p in current.presets.values()))
        self.assertEqual((bunny.presets["bunny"].initial_megapixels, bunny.presets["bunny"].megapixels), (.9, .9))


class H3CheckpointCatalogTest(unittest.TestCase):
    def test_turbo_eros_is_available_in_both_workshops_only_when_installed(self):
        turbo = "10Eros_Max_h3_TURBO-hybrid_beta5.safetensors"
        read = Mock(return_value=(EROS, turbo))
        catalog = CachedH3Checkpoints(read, ENTRIES, monotonic=lambda: 1.0)
        read.assert_not_called()
        for mode in H3RenderInputMode:
            with self.subTest(mode=mode):
                models = catalog.inventory(mode)["models"]
                self.assertEqual([model["name"] for model in models], [EROS, turbo])
                self.assertIn("Turbo intégré", models[1]["label"])
                catalog.validate(turbo, mode)
        read.assert_called_once()
        read.return_value = (EROS,)
        self.assertEqual([m["name"] for m in catalog.inventory(H3RenderInputMode.REF2VA, refresh=True)["models"]], [EROS])
        with self.assertRaisesRegex(ValueError, "absent"):
            catalog.validate(turbo, H3RenderInputMode.REF2VA)

    def test_cached_inventory_filters_modes_refreshes_and_never_falls_back(self):
        clock = [0.0]
        read = Mock(return_value=(EROS, "minimax_h3_fl2va_bf16.safetensors", "unrelated.safetensors"))
        catalog = CachedH3Checkpoints(read, ENTRIES, monotonic=lambda: clock[0])
        read.assert_not_called()
        self.assertEqual(len(catalog.inventory(H3RenderInputMode.FL2VA)["models"]), 2)
        self.assertEqual([m["name"] for m in catalog.inventory(H3RenderInputMode.REF2VA)["models"]], [EROS])
        catalog.validate(EROS, H3RenderInputMode.REF2VA)
        read.assert_called_once()
        with self.assertRaisesRegex(ValueError, "compatible"):
            catalog.validate("minimax_h3_fl2va_bf16.safetensors", H3RenderInputMode.REF2VA)
        read.return_value = ()
        catalog.inventory(H3RenderInputMode.REF2VA, refresh=True)
        with self.assertRaisesRegex(ValueError, "absent"):
            catalog.validate(EROS, H3RenderInputMode.REF2VA)
        read.side_effect = TimeoutError("offline")
        clock[0] = 61
        with self.assertRaisesRegex(ValueError, "offline"):
            catalog.validate(EROS, H3RenderInputMode.REF2VA)
        self.assertEqual(read.call_count, 3)

    def test_unsafe_ids_and_inconsistent_snapshot_are_rejected(self):
        for name in ("", "../x.safetensors", "/x.safetensors", "D:/x.safetensors", "x\\y.safetensors", True, "x\n.safetensors"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_h3_checkpoint(name)
        with self.assertRaises(ValueError):
            H3ModelLoading(EROS, "hybrid")


class H3CheckpointServiceTest(unittest.TestCase):
    def service(self, directory, mode=H3RenderInputMode.T2VA):
        assets, projects = LocalAssetStore(directory), LocalH3RenderProjectStore(directory)
        ref = mode is H3RenderInputMode.REF2VA
        image = assets.create(PNG, media_type="image/png")
        prompt = REF_PROMPT if ref else PROMPT
        projects.create(H3RenderProject("checkpoint-test", "session", "revision", "fake", mode, prompt,
            reference_asset_ids=(image.asset_id,) if ref else (), reference_labels=("Reference",) if ref else ()))
        read = Mock(return_value=(EROS,))
        service = H3RenderService(gateway=CompletedGateway("{}"), workflow=recipe("h3"), ref2v_workflow=recipe("ref"),
            historical_h3_workflows=(recipe("h3", old=True),), historical_ref2v_workflows=(recipe("ref", old=True),),
            comfy=Ref2VComfy() if ref else ImmediateH3Comfy(), assets=assets, projects=projects,
            sessions=object(), compositions=object(), checkpoints=CachedH3Checkpoints(read, ENTRIES))
        settings = VideoLabSettings(VideoAspectRatio.PORTRAIT_WIDESCREEN, .2, 9, 25, 42, True)
        return service, read, prompt, settings

    def test_selected_checkpoint_reaches_compiled_graph_storage_resume_and_web(self):
        for mode in (H3RenderInputMode.T2VA, H3RenderInputMode.REF2VA):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                service, read, prompt, settings = self.service(directory, mode)
                default = service.prepare_attempt("checkpoint-test", prompt=prompt, settings=settings).attempts[-1]
                read.assert_not_called()
                self.assertIsNone(default.checkpoint)
                self.assertIsNotNone(default.model_loading)
                selected = service.prepare_attempt("checkpoint-test", prompt=prompt, settings=settings,
                    checkpoint=EROS, initial_megapixels=.6).attempts[-1]
                service.queue_attempt("checkpoint-test", selected.attempt_id)
                result = service.execute_attempt("checkpoint-test", selected.attempt_id)
                self.assertEqual(result.attempt(selected.attempt_id).status, H3RenderAttemptStatus.SUCCEEDED)
                self.assertIn(EROS, [n["inputs"].get("unet_name") for n in service.comfy.submitted[0].values()])
                reopened = LocalH3RenderProjectStore(directory).get("checkpoint-test")
                saved = reopened.attempt(selected.attempt_id)
                self.assertEqual((saved.checkpoint, saved.model_loading, saved.settings, saved.initial_megapixels),
                                 (EROS, H3ModelLoading(EROS), settings, .6))
                self.assertEqual(reopened.resume_attempt(saved.attempt_id).attempt(saved.attempt_id), saved)
                payload = serialize_h3_render_project(reopened)["attempts"][-1]
                self.assertEqual(payload["checkpoint"], EROS)
                self.assertEqual(payload["model_loading"]["strategy"], "direct")
                self.assertEqual(service.gateway.requests, [])
                read.assert_called_once()
                old = service.workflow_for_mode(mode, saved.recipe.recipe_id, "0.2.1" if mode is H3RenderInputMode.REF2VA else "0.1.3")
                with self.assertRaisesRegex(ValueError, "historique"):
                    service.prepare_attempt("checkpoint-test", prompt=prompt, settings=settings, checkpoint=EROS,
                        recipe_id=old.reference.recipe_id, recipe_version=old.reference.version)

    def test_removed_model_fails_before_upload_or_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            service, read, prompt, settings = self.service(directory, H3RenderInputMode.REF2VA)
            selected = service.prepare_attempt("checkpoint-test", prompt=prompt, settings=settings, checkpoint=EROS).attempts[-1]
            read.return_value = ()
            service.checkpoints.inventory(H3RenderInputMode.REF2VA, refresh=True)
            service.comfy.upload_image = Mock(side_effect=AssertionError("must fail before upload"))
            service.queue_attempt("checkpoint-test", selected.attempt_id)
            result = service.execute_attempt("checkpoint-test", selected.attempt_id).attempt(selected.attempt_id)
            self.assertEqual(result.status, H3RenderAttemptStatus.FAILED)
            self.assertIn("absent", result.error)
            self.assertEqual(service.comfy.submitted, [])
            service.comfy.upload_image.assert_not_called()

    def test_legacy_schema_ten_does_not_invent_a_checkpoint(self):
        settings = VideoLabSettings(VideoAspectRatio.PORTRAIT_WIDESCREEN, .2, 9, 25, 42, True)
        attempt = H3RenderAttempt("attempt", 1, PROMPT, PROMPT, settings, False, (), recipe=recipe("h3", old=True).reference)
        project = H3RenderProject("project", "session", "revision", "fake", H3RenderInputMode.T2VA, PROMPT, attempts=(attempt,))
        raw = _serialize(project)
        self.assertEqual(raw["schema_version"], 13)
        raw["schema_version"] = 10
        raw["attempts"][0].pop("checkpoint")
        raw["attempts"][0].pop("model_loading")
        self.assertEqual(_deserialize(raw), project)
        body = H3RenderAttemptBody(prompt=PROMPT, aspect_ratio=settings.aspect_ratio.value, megapixels=.2, duration_seconds=9, steps=25)
        self.assertIsNone(body.checkpoint)
        self.assertTrue(body.seed_locked)
        with self.assertRaises(ValueError):
            replace(attempt, checkpoint=EROS)

    def test_http_inventory_lazy_selection_validation_and_conversion_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            service, read, prompt, settings = self.service(directory)
            service.list_models = Mock(return_value=())
            client = TestClient(create_app(object(), h3_render=service))
            spec = client.get("/api/h3-render/spec").json()
            self.assertTrue(spec["checkpoint_selection"]["supported"])
            read.assert_not_called()
            historical = client.get("/api/h3-render/spec?recipe_id=minimax-h3-latent-speed&recipe_version=0.1.3").json()
            self.assertFalse(historical["checkpoint_selection"]["supported"])
            read.assert_not_called()
            self.assertEqual(client.get("/api/h3-render/checkpoints?mode=ref2va").json()["models"][0]["name"], EROS)
            body = dict(prompt=prompt, aspect_ratio=settings.aspect_ratio.value, megapixels=.2,
                        duration_seconds=9, steps=25, seed="42", seed_locked=True, initial_megapixels=.2,
                        checkpoint=EROS)
            response = client.post("/api/h3-render/projects/checkpoint-test/attempts", json=body)
            self.assertEqual(response.status_code, 201, response.text)
            saved = response.json()["project"]["attempts"][-1]
            self.assertEqual(saved["checkpoint"], EROS)
            invalid = client.post("/api/h3-render/projects/checkpoint-test/attempts", json={**body, "checkpoint": "../bad.safetensors"})
            self.assertEqual(invalid.status_code, 422)
            self.assertEqual(len(service.projects.get("checkpoint-test").attempts), 1)
            image = service.assets.create(PNG, media_type="image/png")
            conversion = client.post("/api/h3-render/projects/checkpoint-test/adapt-ref2v", json={**body,
                "request_id": "checkpoint-conversion", "model_id": "fake", "extra_reference_asset_id": image.asset_id})
            self.assertEqual(conversion.status_code, 201, conversion.text)
            target = conversion.json()["project"]
            setup = target["adaptation"]["render_setup"]
            self.assertEqual(setup["checkpoint"], EROS)
            self.assertEqual(setup["model_loading"]["strategy"], "direct")
            reopened = LocalH3RenderProjectStore(directory).get(target["project_id"])
            self.assertEqual(reopened.adaptation.render_setup.model_loading, H3ModelLoading(EROS))
            self.assertEqual(service.gateway.requests, [])
            self.assertEqual(service.comfy.submitted, [])
            read.assert_called_once()
