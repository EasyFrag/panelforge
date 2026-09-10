"""Prepared for user execution only: pure graphs and fake Comfy/LLM ports."""

from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from panelforge.application.h3_render import H3RenderService, _attempt_context
from panelforge.domain.h3_bunny import BUNNY_RECIPE_ID, H3BunnySettings, bunny_geometry
from panelforge.domain.h3_render import H3RenderInputMode, H3RenderProject, H3VideoLoraSelection
from panelforge.domain.video_lab import VideoAspectRatio, VideoLabSettings
from panelforge.features.lab.web import create_app, serialize_h3_render_project
from panelforge.infrastructure.presets.h3_bunny import BunnyH3RenderRecipe
from panelforge.infrastructure.presets import (
    H3RenderPresetRecipe, load_h3_render_workflow,
    Ref2VH3RenderPresetRecipe, VideoLabPresetRecipe, load_video_lab_workflow,
)
from panelforge.infrastructure.storage import LocalAssetStore, LocalH3RenderProjectStore

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "workflows/video.generate.h3-base/minimax-h3-bunny/0.1.0"
PROMPT = "integrated_multimodal_description:\n[Shot 1] A worker lays stones.\noverall_soundscape:\nWind.\nnon_diegetic_music:\nN/A"
LORA = "minmax_nsfw/Motion_Repair.safetensors"


class Gateway:
    def list_models(self):
        return ()

    def stream(self, *args, **kwargs):
        raise AssertionError("No LLM calls in rendering tests")


class FakeComfy:
    def __init__(self):
        self.graphs = {}
        self.uploads = []
        self.description_calls = []
        self.missing = None
        self.original = json.loads((DIRECTORY / "workflow_api.json").read_text(encoding="utf-8"))

    def list_lora_models(self):
        return (LORA,)

    def upload_image(self, content, *, filename, subfolder=""):
        from types import SimpleNamespace
        self.uploads.append(filename)
        return SimpleNamespace(workflow_value=f"{subfolder}/{filename}")

    def describe_node(self, name):
        self.description_calls.append(name)
        if name == self.missing:
            return {}
        fields = {}
        for node in self.original.values():
            if node["class_type"] == name:
                fields.update({field: ["STRING"] for field in node["inputs"]})
        fields["tiny_vae"] = [["taeh3.safetensors"]]
        return {name: {"input": {"required": fields}}}

    def submit_workflow(self, graph):
        execution = f"execution-{len(self.graphs) + 1}"
        self.graphs[execution] = graph
        return execution

    def get_history(self, execution):
        graph = self.graphs[execution]
        outputs = {}
        for node_id, node in graph.items():
            if node["class_type"] in {"SaveVideo", "SaveImage"}:
                extension = "mp4" if node["class_type"] == "SaveVideo" else "png"
                outputs[node_id] = {"images": [{"filename": f"{execution}-{node_id}.{extension}", "subfolder": "video", "type": "output"}]}
        return {execution: {"status": {"completed": True, "status_str": "success"}, "outputs": outputs}}

    def download_output(self, *, filename, **kwargs):
        return b"\x00\x00\x00\x18ftypisomvideo" if filename.endswith("mp4") else b"\x89PNG\r\n\x1a\n" + filename.encode()

    def cancel_execution(self, execution):
        raise AssertionError("Successful fake renders must not be cancelled")


class BunnyGraphTest(unittest.TestCase):
    def setUp(self):
        self.recipe = BunnyH3RenderRecipe(DIRECTORY)
        self.settings = VideoLabSettings(VideoAspectRatio.PORTRAIT_WIDESCREEN, 0.9, 10, 9, 123, True)
        self.nodes = self.recipe.manifest["nodes"]

    def build(self, **changes):
        args = dict(input_mode=H3RenderInputMode.T2VA, prompt=PROMPT,
                    settings=self.settings, output_filename_prefix="video/test", keyframe_indices=(0, 60, 242),
                    bunny=H3BunnySettings(), initial_megapixels=0.9)
        args.update(changes)
        return self.recipe.build_workflow(**args)

    def test_modes_wire_both_passes_and_only_one_loader(self):
        for mode, images in [
            (H3RenderInputMode.T2VA, {}),
            (H3RenderInputMode.I2VA, {"first_frame": "first.png"}),
            (H3RenderInputMode.L2VA, {"last_frame": "last.png"}),
            (H3RenderInputMode.FL2VA, {"first_frame": "first.png", "last_frame": "last.png"}),
            (H3RenderInputMode.REF2VA, {"source_images": tuple(f"ref-{i}.png" for i in range(9))}),
        ]:
            with self.subTest(mode=mode):
                graph = self.build(input_mode=mode, **images)
                is_ref = mode is H3RenderInputMode.REF2VA
                self.assertIn(self.nodes["hybrid_model"] if is_ref else self.nodes["plain_model"], graph)
                self.assertNotIn(self.nodes["plain_model"] if is_ref else self.nodes["hybrid_model"], graph)
                for node_id in self.nodes["conditionings"]:
                    inputs = graph[node_id]["inputs"]
                    self.assertEqual(inputs["task_type"], self.recipe.manifest["tasks"][mode.value])
                    for role in ["first_frame", "last_frame"]:
                        self.assertEqual(role in inputs, role in images)
                        if role in images:
                            self.assertEqual(graph[inputs[role][0]]["inputs"]["image"], images[role])
                    self.assertEqual(len([k for k in inputs if k.startswith("ref_images.")]), 9 if is_ref else 0)
                for node in graph.values():
                    for value in node["inputs"].values():
                        if isinstance(value, list):
                            self.assertIn(value[0], graph)

    def test_turbo_bypass_does_not_disable_or_accumulate_creative_lora(self):
        config = H3BunnySettings(False, 30, 25, 5, 0.2, False)
        graph = self.build(bunny=config, video_lora=H3VideoLoraSelection(LORA, 0.6, None))
        self.assertNotIn(self.nodes["turbo"], graph)
        self.assertFalse(any(n["class_type"] == "ModelPreviewOverrideKJ" for n in graph.values()))
        for node_id, force in zip(self.nodes["loras"], (0.6, 0.2)):
            self.assertEqual(graph[node_id]["inputs"]["lora_name"], LORA)
            self.assertEqual(graph[node_id]["inputs"]["strength_model"], force)
            self.assertEqual(graph[node_id]["inputs"]["model"], [self.nodes["attention"], 0])
        self.assertEqual(graph[self.nodes["plan"]]["inputs"]["coarse_steps"], 25)
        no_lora = self.build()
        self.assertTrue(all(node_id not in no_lora for node_id in self.nodes["loras"]))
        self.assertIn(self.nodes["turbo"], no_lora)
        self.assertEqual(len([n for n in no_lora.values() if n["class_type"] == "ModelPreviewOverrideKJ"]), 2)

    def test_geometry_x1_and_larger_preserve_both_passes(self):
        same = bunny_geometry(self.settings, 0.9)
        self.assertEqual((same["width"], same["height"]), self.settings.resolution)
        self.assertEqual(same["scale"], 1)
        bigger = bunny_geometry(replace(self.settings, megapixels=2.0), 0.9)
        self.assertGreater(bigger["width"], same["width"])
        self.assertGreater(bigger["height"], same["height"])
        with self.assertRaises(ValueError):
            bunny_geometry(replace(self.settings, megapixels=0.2), 0.9)
        graph = self.build()
        self.assertEqual(len([n for n in graph.values() if n["class_type"] == "SamplerCustomAdvanced"]), 2)
        self.assertEqual(graph[self.nodes["upscale"]]["inputs"]["size_mode"], "target_dimensions")
        self.assertEqual(graph[self.nodes["output"]]["inputs"]["filename_prefix"], "video/test")

    def test_invalid_controls_and_missing_resources(self):
        for kwargs in ({"coarse_steps": 9}, {"refine_steps": 6}, {"base_steps": True}, {"turbo_enabled": 1}, {"lora_second_strength": float("nan")}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                H3BunnySettings(**kwargs)
        with self.assertRaises(ValueError):
            self.build(input_mode=H3RenderInputMode.FL2VA, source_images=("first.png", "last.png"))
        with self.assertRaises(ValueError):
            self.build(spectrum_enabled=True)
        with self.assertRaises(ValueError):
            self.build(video_lora=H3VideoLoraSelection(LORA))
        comfy = FakeComfy()
        comfy.missing = "MiniMaxH3LearnedTwoPassParityPlanT8Advanced"
        with self.assertRaisesRegex(ValueError, "manquant"):
            self.recipe.validate_dependencies(comfy, self.build())
        self.assertEqual(comfy.graphs, {})


class BunnyServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.assets = LocalAssetStore(self.temp.name)
        self.store = LocalH3RenderProjectStore(self.temp.name)
        self.comfy = FakeComfy()
        self.recipe = BunnyH3RenderRecipe(DIRECTORY)
        self.service = H3RenderService(
            gateway=Gateway(), comfy=self.comfy, assets=self.assets, projects=self.store,
            workflow=H3RenderPresetRecipe(load_h3_render_workflow(ROOT / "workflows/video.generate.h3-base/minimax-h3-latent-speed/0.1.3")),
            ref2v_workflow=Ref2VH3RenderPresetRecipe(VideoLabPresetRecipe(load_video_lab_workflow(ROOT / "workflows/video.generate.ref2v/minimax-h3-ref2v/0.2.0"))),
            additional_workflows=(self.recipe,), sessions=None, compositions=None,
        )
        self.settings = VideoLabSettings(VideoAspectRatio.PORTRAIT_WIDESCREEN, 0.9, 10, 9, 321, True)
        self.store.create(H3RenderProject("project", "session", "revision", "fake-model", H3RenderInputMode.T2VA, PROMPT))

    def prepare(self, project="project", **kwargs):
        return self.service.prepare_attempt(project, prompt=self.store.get(project).current_prompt, settings=self.settings,
            initial_megapixels=0.9, recipe_id=BUNNY_RECIPE_ID, recipe_version="0.1.0", **kwargs)

    def test_roundtrip_execution_feedback_and_resume_bind_the_recipe(self):
        prepared = self.prepare(bunny=H3BunnySettings(False, 30, 25, 5, 0.4, False), video_lora=H3VideoLoraSelection(LORA, 0.6, None))
        attempt = prepared.attempts[-1]
        self.assertEqual(attempt.settings.steps, 30)
        self.assertEqual(attempt.recipe, self.recipe.reference)
        self.service.queue_attempt("project", attempt.attempt_id)
        complete = self.service.execute_attempt("project", attempt.attempt_id)
        result = complete.attempt(attempt.attempt_id)
        self.assertEqual(result.status.value, "succeeded", result.error)
        self.assertEqual(complete.feedback_attempt_id, attempt.attempt_id)
        self.assertEqual(result.keyframes[-1].timestamp_ms, result.keyframe_timestamps_ms[-1])
        loaded = LocalH3RenderProjectStore(self.temp.name).get("project")
        self.assertEqual(loaded, complete)
        self.assertEqual(self.service.recipe_for_attempt(loaded, result).reference, self.recipe.reference)
        self.assertEqual(json.loads(_attempt_context(result))["bunny"]["coarse_steps"], 25)
        payload = serialize_h3_render_project(loaded)["attempts"][-1]
        self.assertEqual(payload["bunny"]["lora_second_strength"], 0.4)
        self.assertEqual(payload["recipe"]["recipe_id"], BUNNY_RECIPE_ID)
        self.assertTrue(all(frame["content_url"].endswith("/content") for frame in payload["keyframes"]))
        self.assertEqual(self.service.resume_attempt("project", attempt.attempt_id).current_prompt, result.prompt)
        self.assertEqual([p.expected_steps for p in self.service.progress_for_attempt(loaded, result).phases if p.tracks_steps], [25, 5])

    def test_detached_completion_uses_bunny_outputs_even_with_legacy_default(self):
        prepared = self.prepare()
        attempt = prepared.attempts[-1]
        graph = self.recipe.build_workflow(prompt=PROMPT, settings=attempt.settings, bunny=attempt.bunny,
            initial_megapixels=0.9, input_mode=H3RenderInputMode.T2VA, output_filename_prefix="video/detached",
            keyframe_indices=tuple(round(ms * 24 / 1000) for ms in attempt.keyframe_timestamps_ms))
        digest = self.store.save_compiled_workflow("project", attempt.attempt_id, graph)
        execution = self.comfy.submit_workflow(graph)
        self.store.save(prepared.replace_attempt(attempt.queue().start(execution, digest)))
        self.assertNotEqual(self.service.workflow.reference.recipe_id, BUNNY_RECIPE_ID)
        finished = self.service.get("project").attempt(attempt.attempt_id)
        self.assertEqual(finished.status.value, "succeeded", finished.error)
        self.assertTrue(finished.output_asset_id)
        self.assertEqual(len(finished.keyframes), len(attempt.keyframe_timestamps_ms))

    def test_ref2v_routes_to_hybrid_and_keeps_reference_order(self):
        refs = tuple(self.assets.create(b"fake-png" + bytes([i]), media_type="image/png").asset_id for i in range(2))
        prompt = ("<Picture 1>: worker reference.\n<Picture 2>: room reference.\n\n"
                  "Shot 1: A worker lays stones.\noverall_soundscape: Wind.\nnon_diegetic_music: N/A")
        self.store.create(H3RenderProject("refs", "source", "rev", "fake-model", H3RenderInputMode.REF2VA, prompt,
            reference_asset_ids=refs, reference_labels=("worker", "room")))
        prepared = self.prepare("refs")
        attempt = prepared.attempts[-1]
        self.service.queue_attempt("refs", attempt.attempt_id)
        result = self.service.execute_attempt("refs", attempt.attempt_id).attempt(attempt.attempt_id)
        self.assertEqual(result.status.value, "succeeded", result.error)
        graph = self.comfy.graphs[result.execution_id]
        self.assertIn(self.recipe.manifest["nodes"]["hybrid_model"], graph)
        for node_id in self.recipe.manifest["nodes"]["conditionings"]:
            self.assertIn(refs[0], graph[graph[node_id]["inputs"]["ref_images.ref_image_0"][0]]["inputs"]["image"])
        self.assertEqual(len(self.comfy.uploads), 2)

    def test_unknown_recipe_and_wrong_parameters_do_not_create_attempts(self):
        with self.assertRaises(ValueError):
            self.service.prepare_attempt("project", prompt=PROMPT, settings=self.settings, recipe_id=BUNNY_RECIPE_ID, recipe_version="missing")
        with self.assertRaises(ValueError):
            self.service.prepare_attempt("project", prompt=PROMPT, settings=self.settings, bunny=H3BunnySettings())
        self.assertEqual(self.store.get("project").attempts, ())
        self.assertEqual(self.comfy.graphs, {})

    def test_legacy_schemas_remain_readable_and_default_stays_legacy(self):
        old = self.service.prepare_attempt("project", prompt=PROMPT, settings=self.settings)
        path = Path(self.temp.name) / "h3_render_projects/project/project.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 6)
        for version in range(1, 5):
            data["schema_version"] = version
            for item in data["attempts"]:
                item.pop("recipe", None); item.pop("bunny", None)
            path.write_text(json.dumps(data), encoding="utf-8")
            loaded = self.store.get("project")
            self.assertIsNone(loaded.attempts[-1].bunny)
            self.assertEqual(self.service.recipe_for_attempt(loaded, loaded.attempts[-1]), self.service.workflow)
        self.assertNotEqual(old.attempts[-1].recipe.recipe_id, BUNNY_RECIPE_ID)

    def test_missing_node_fails_without_submit_and_keeps_candidate_prompt(self):
        self.comfy.missing = "MiniMaxH3LearnedLatentUpscaleT8Advanced"
        attempt = self.prepare().attempts[-1]
        self.service.queue_attempt("project", attempt.attempt_id)
        result = self.service.execute_attempt("project", attempt.attempt_id).attempt(attempt.attempt_id)
        self.assertEqual(result.status.value, "failed")
        self.assertIn("manquant", result.error)
        self.assertEqual(result.prompt, PROMPT)
        self.assertFalse(self.comfy.graphs)

    def test_http_catalog_defaults_and_attempt_contract(self):
        with TestClient(create_app(None, h3_render=self.service)) as client:
            old = client.get("/api/h3-render/spec").json()
            self.assertEqual(old["defaults"]["megapixels"], 0.2)
            self.assertEqual(len(old["render_recipes"]), 2)
            for mode in ("h3-base", "ref2va"):
                spec = client.get("/api/h3-render/spec", params={"mode": mode, "recipe_id": BUNNY_RECIPE_ID, "recipe_version": "0.1.0"})
                self.assertEqual(spec.status_code, 200, spec.text)
                value = spec.json()
                self.assertEqual(value["defaults"]["initial_megapixels"], 0.9)
                self.assertEqual(value["defaults"]["megapixels"], 0.9)
                self.assertTrue(value["defaults"]["seed_locked"])
                self.assertEqual(value["bunny"]["default_lora"], LORA)
                self.assertEqual("Hybride" in value["bunny"]["model_label"], mode == "ref2va")
            self.assertEqual(client.get("/api/h3-render/spec?recipe_id=unknown&recipe_version=0.1.0").status_code, 422)
            body = dict(prompt=PROMPT, aspect_ratio=self.settings.aspect_ratio.value, megapixels=0.9,
                initial_megapixels=0.9, duration_seconds=10, steps=9, seed="321", seed_locked=True,
                recipe_id=BUNNY_RECIPE_ID, recipe_version="0.1.0", bunny=asdict(H3BunnySettings()))
            bad = {**body, "bunny": {**body["bunny"], "coarse_steps": 9}}
            self.assertEqual(client.post("/api/h3-render/projects/project/attempts", json=bad).status_code, 422)
            response = client.post("/api/h3-render/projects/project/attempts", json=body)
            self.assertEqual(response.status_code, 201, response.text)
            attempt = response.json()["project"]["attempts"][-1]
            self.assertEqual(attempt["recipe"]["recipe_id"], BUNNY_RECIPE_ID)
            self.assertEqual(attempt["bunny_geometry"]["scale"], 1)
            self.assertEqual(attempt["initial_megapixels"], 0.9)
            self.assertFalse(self.comfy.graphs)

    def test_dlss_variant_retains_recipe_and_selected_frame_provenance(self):
        from panelforge.domain.dlss import DlssResult, DlssSettings
        from panelforge.application.dlss_candidates import DlssCandidates
        attempt = self.prepare().attempts[-1]
        self.service.queue_attempt("project", attempt.attempt_id)
        complete = self.service.execute_attempt("project", attempt.attempt_id)
        original = complete.attempt(attempt.attempt_id)
        snapshot = DlssCandidates(edit=None, assisted=None, h3=self.service).prepare(
            "h3", "project", original.attempt_id, DlssSettings(size="1.5"))
        self.assertEqual(snapshot["generation_recipe"], asdict(original.recipe))
        self.assertEqual(snapshot["generation_bunny"], asdict(original.bunny))
        media = self.assets.create(b"\x00\x00\x00\x18ftypisomdlss", media_type="video/mp4")
        info = DlssResult("job", original.attempt_id, original.attempt_id, original.output_asset_id,
                          "report", 1024, 1792, "1.5", 60, 10)
        variant = replace(original, attempt_id="dlss-attempt", dlss=info, output_asset_id=media.asset_id,
                          execution_id=None, compiled_workflow_sha256=None)
        self.store.save(replace(complete, attempts=(*complete.attempts, variant), feedback_attempt_id=variant.attempt_id))
        loaded = self.store.get("project")
        selected = loaded.attempt(loaded.feedback_attempt_id)
        self.assertEqual(selected.recipe, original.recipe)
        self.assertEqual(selected.bunny, original.bunny)
        self.assertEqual(selected.output_asset_id, media.asset_id)
        self.assertIsNone(selected.execution_id)
        payload = serialize_h3_render_project(loaded)["attempts"][-1]
        self.assertEqual(payload["output_url"], f"/api/assets/{media.asset_id}/content")
        self.assertEqual(payload["keyframes"][-1]["asset_id"], selected.keyframes[-1].asset_id)
