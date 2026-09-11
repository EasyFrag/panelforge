"""User-run regressions: fake transports and temporary stores; no real model calls."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from panelforge.application.dlss_candidates import DlssCandidates
from panelforge.application.h3_render import H3RenderService, _attempt_context
from panelforge.domain.dlss import DlssSettings
from panelforge.domain.h3_bunny import H3BunnySettings
from panelforge.domain.h3_render import (
    H3RenderAttempt, H3RenderAttemptStatus, H3RenderInputMode, H3RenderProject, H3RenderRevisionVersion,
    H3VideoLoraSelection, H3VideoLoraSlot, H3VideoLoraStack,
)
from panelforge.domain.video_lab import VideoAspectRatio, VideoLabSettings
from panelforge.features.lab.web import create_app, serialize_h3_render_project
from panelforge.infrastructure.presets import (
    H3RenderPresetRecipe, Ref2VH3RenderPresetRecipe, VideoLabPresetRecipe,
    load_h3_render_workflow, load_video_lab_workflow,
)
from panelforge.infrastructure.presets.h3_bunny import BunnyH3RenderRecipe
from panelforge.infrastructure.presets.h3_loras import MultiLoraH3RenderRecipe
from panelforge.infrastructure.storage import LocalAssetStore, LocalH3RenderProjectStore
from panelforge.infrastructure.storage.h3_render_projects import _serialize, _deserialize
from tests.test_h3_checkpoints import recipe as previous_recipe, PROMPT, EROS
from tests.test_h3_render import CompletedGateway, ImmediateH3Comfy, PNG
from tests.test_ref2v_render_resolution import Ref2VComfy, PROMPT as REF_PROMPT
from tests import test_h3_ref2v_conversion as conversion_fixtures


ROOT = Path(__file__).resolve().parents[1]
COMBAT = "minmax_nsfw/H3_Combat_V2.safetensors"
MOTION = "minmax_nsfw/Motion_Repair.safetensors"
VERSIONS = {
    "h3": ("video.generate.h3-base/minimax-h3-latent-speed", "0.1.5"),
    "ref": ("video.generate.ref2v/minimax-h3-ref2v", "0.2.3"),
    "bunny": ("video.generate.h3-base/minimax-h3-bunny", "0.1.2"),
}


def recipe(kind):
    folder, version = VERSIONS[kind]
    path = ROOT / "workflows" / folder / version
    if kind == "bunny":
        base = BunnyH3RenderRecipe(path)
    elif kind == "ref":
        base = Ref2VH3RenderPresetRecipe(VideoLabPresetRecipe(load_video_lab_workflow(path)))
    else:
        base = H3RenderPresetRecipe(load_h3_render_workflow(path))
    return MultiLoraH3RenderRecipe(base, path)


def stack(per_pass=False):
    # Deliberately different values to catch accidental sharing/copying of forces.
    return H3VideoLoraStack((H3VideoLoraSlot(COMBAT, .7, .15 if per_pass else None),
                            H3VideoLoraSlot(MOTION, .55, .3 if per_pass else None)),
                           clip_last_layer=None if per_pass else -2)


def parameters(kind, mode, turbo=True, preview=True):
    bunny = H3BunnySettings(preview_enabled=preview) if turbo else H3BunnySettings(False, 30, 25, 5, .2, preview)
    settings = VideoLabSettings(VideoAspectRatio.PORTRAIT_WIDESCREEN, .9, 9,
                                bunny.coarse_steps + bunny.refine_steps if kind == "bunny" else 25,
                                2**63 + 5, True)
    values = dict(prompt=REF_PROMPT if mode is H3RenderInputMode.REF2VA else PROMPT,
                  settings=settings, output_filename_prefix="video/fixture", keyframe_indices=(0, 10),
                  initial_megapixels=.9, spectrum_enabled=False)
    if kind == "bunny":
        values["bunny"] = bunny
    if mode is H3RenderInputMode.REF2VA:
        values["source_images"] = ("a.png", "b.png")
    else:
        values.update(input_mode=mode,
                      first_frame="a.png" if mode in (H3RenderInputMode.I2VA, H3RenderInputMode.FL2VA) else None,
                      last_frame="b.png" if mode in (H3RenderInputMode.L2VA, H3RenderInputMode.FL2VA) else None)
    return values


class MultipleLoraWorkflowTest(unittest.TestCase):
    def test_legacy_and_zero_or_one_active_lora_keep_the_previous_graph(self):
        for kind in VERSIONS:
            current, old = recipe(kind), previous_recipe(kind)
            for mode in H3RenderInputMode:
                if (kind == "h3" and mode is H3RenderInputMode.REF2VA) or (kind == "ref" and mode is not H3RenderInputMode.REF2VA):
                    continue
                with self.subTest(kind=kind, mode=mode):
                    args = parameters(kind, mode)
                    selected = stack(kind == "bunny")
                    for legacy in (None, H3VideoLoraSelection(COMBAT, .7, None)):
                        self.assertEqual(current.build_workflow(video_lora=legacy, **args), old.build_workflow(video_lora=legacy, **args))
                    self.assertEqual(current.build_workflow(video_loras=replace(selected, enabled=False), **args), old.build_workflow(**args))
                    self.assertEqual(current.build_workflow(video_loras=replace(selected, entries=()), **args), old.build_workflow(**args))
                    for index in (0, 1):
                        entries = tuple(replace(e, enabled=i == index) for i, e in enumerate(selected.entries))
                        active = entries[index]
                        expected = dict(args)
                        if kind == "bunny":
                            expected["bunny"] = replace(args["bunny"], lora_second_strength=active.second_strength)
                        legacy = H3VideoLoraSelection(active.name, active.strength, selected.clip_last_layer)
                        self.assertEqual(current.build_workflow(video_loras=replace(selected, entries=entries), **args),
                                         old.build_workflow(video_lora=legacy, **expected))

    def test_shared_loader_order_and_single_clip_switch(self):
        for kind, mode in (("h3", H3RenderInputMode.FL2VA), ("ref", H3RenderInputMode.REF2VA)):
            current = recipe(kind)
            for clip in (None, -2):
                for entries in (stack().entries, tuple(reversed(stack().entries))):
                    with self.subTest(kind=kind, clip=clip, entries=entries):
                        args = parameters(kind, mode)
                        selected = H3VideoLoraStack(entries, clip_last_layer=clip)
                        baseline = current.build_workflow(video_lora=H3VideoLoraSelection(entries[0].name, entries[0].strength, clip), **args)
                        expected = deepcopy(baseline)
                        loader = current.lora_config["loader_node_id"]
                        expected[loader]["inputs"]["lora_2"] = {"on": True, "lora": entries[1].name, "strength": entries[1].strength}
                        self.assertEqual(current.build_workflow(video_loras=selected, **args), expected)
                        self.assertLessEqual(sum(n["class_type"] == "CLIPSetLastLayer" for n in expected.values()), 1)

    def test_bunny_branches_keep_four_independent_forces_with_turbo_preview_and_checkpoint(self):
        current = recipe("bunny")
        for mode in H3RenderInputMode:
            for turbo in (True, False):
                for preview in (True, False):
                    for checkpoint in (None, EROS):
                        with self.subTest(mode=mode, turbo=turbo, preview=preview, checkpoint=checkpoint):
                            args = parameters("bunny", mode, turbo, preview)
                            selected = stack(True)
                            graph = current.build_workflow(video_loras=selected, checkpoint=checkpoint, **args)
                            baseline = current.build_workflow(video_loras=replace(selected, entries=selected.entries[:1]), checkpoint=checkpoint, **args)
                            expected = deepcopy(baseline)
                            upstreams = []
                            for index, branch in enumerate(current.lora_config["branches"]):
                                head, extra = branch["head_node_id"], branch["extra_node_id"]
                                upstreams.append(graph[head]["inputs"]["model"])
                                self.assertEqual(graph[head]["inputs"]["strength_model"], [.7, .15][index])
                                self.assertEqual(graph[extra]["inputs"]["strength_model"], [.55, .3][index])
                                self.assertEqual(graph[extra]["inputs"]["model"], [head, 0])
                                self.assertEqual(graph[extra]["inputs"]["lora_name"], MOTION)
                                expected[extra] = deepcopy(graph[extra])
                                rewired = 0
                                for target in branch["targets"]:
                                    if target["node_id"] in expected:
                                        values = expected[target["node_id"]]["inputs"]
                                        if values.get(target["input"]) == [head, 0]:
                                            values[target["input"]] = [extra, 0]
                                            rewired += 1
                                self.assertGreater(rewired, 0)
                            self.assertEqual(upstreams[0], upstreams[1])
                            self.assertEqual(graph, expected)  # no sampling, latent or Turbo change
                            self.assertEqual(selected, stack(True))  # immutable settings
                            for node in graph.values():
                                for link in node["inputs"].values():
                                    if isinstance(link, list) and len(link) == 2 and isinstance(link[0], str):
                                        self.assertIn(link[0], graph)
                            class Descriptions:
                                def describe_node(self, name):
                                    fields = {}
                                    for node in graph.values():
                                        if node["class_type"] == name:
                                            for key, value in node["inputs"].items():
                                                if isinstance(value, str):
                                                    fields.setdefault(key, [[]])[0].append(value)
                                    return {name: {"input": {"required": fields}}}
                            current.validate_dependencies(Descriptions(), graph)
                            if checkpoint:
                                self.assertFalse(any(n["class_type"] == "MiniMaxH3HybridLoader" for n in graph.values()))

    def test_bunny_dependency_check_includes_second_creative_lora(self):
        current = recipe("bunny")
        graph = current.build_workflow(video_loras=stack(True), **parameters("bunny", H3RenderInputMode.I2VA))
        class Descriptions:
            def describe_node(self, name):
                fields = {}
                for node in graph.values():
                    if node["class_type"] == name:
                        for key, value in node["inputs"].items():
                            if isinstance(value, str):
                                fields.setdefault(key, [[]])
                                if value != MOTION:
                                    fields[key][0].append(value)
                return {name: {"input": {"required": fields}}}
        with self.assertRaisesRegex(ValueError, "Motion_Repair"):
            current.validate_dependencies(Descriptions(), graph)

    def test_reversing_bunny_entries_moves_both_pass_strengths(self):
        current = recipe("bunny")
        selected = replace(stack(True), entries=tuple(reversed(stack(True).entries)))
        graph = current.build_workflow(video_loras=selected, **parameters("bunny", H3RenderInputMode.FL2VA))
        for i, branch in enumerate(current.lora_config["branches"]):
            first = graph[branch["head_node_id"]]["inputs"]
            second = graph[branch["extra_node_id"]]["inputs"]
            self.assertEqual((first["lora_name"], first["strength_model"]), (MOTION, [.55, .3][i]))
            self.assertEqual((second["lora_name"], second["strength_model"]), (COMBAT, [.7, .15][i]))

    def test_contract_rejects_ambiguous_or_invalid_stacks(self):
        for force in (True, float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(force=force), self.assertRaises((ValueError, TypeError)):
                H3VideoLoraSlot(COMBAT, force)
        for entries in ((stack().entries[0],) * 2, stack().entries + (stack().entries[0],)):
            with self.assertRaises(ValueError):
                H3VideoLoraStack(entries)
        for name in ("../bad.safetensors", "Krea2/wrong.safetensors", "C:/model.safetensors"):
            with self.assertRaises(ValueError):
                H3VideoLoraSlot(name)
        with self.assertRaises(ValueError): stack().validate_mode(True)
        with self.assertRaises(ValueError): stack(True).validate_mode(False)
        with self.assertRaises(ValueError): replace(stack(True), clip_last_layer=-2).validate_mode(True)
        with self.assertRaises(ValueError):
            recipe("h3").build_workflow(video_loras=stack(), video_lora=H3VideoLoraSelection(COMBAT), **parameters("h3", H3RenderInputMode.T2VA))


class MultipleLoraServiceTest(unittest.TestCase):
    def service(self, directory, mode=H3RenderInputMode.T2VA):
        assets, projects = LocalAssetStore(directory), LocalH3RenderProjectStore(directory)
        ref = mode is H3RenderInputMode.REF2VA
        image = assets.create(PNG, media_type="image/png")
        prompt = REF_PROMPT if ref else PROMPT
        projects.create(H3RenderProject("two-loras", "session", "revision", "fake", mode, prompt,
            reference_asset_ids=(image.asset_id,) if ref else (), reference_labels=("Reference",) if ref else ()))
        read = Mock(return_value=(COMBAT, MOTION, "krea2/ignored.safetensors"))
        clock = [0.0]
        service = H3RenderService(gateway=CompletedGateway("{}"), workflow=recipe("h3"), ref2v_workflow=recipe("ref"),
            historical_h3_workflows=(previous_recipe("h3"),), historical_ref2v_workflows=(previous_recipe("ref"),),
            additional_workflows=(recipe("bunny"),), comfy=Ref2VComfy() if ref else ImmediateH3Comfy(),
            assets=assets, projects=projects, sessions=object(), compositions=object(),
            list_video_loras=read, monotonic=lambda: clock[0])
        settings = VideoLabSettings(VideoAspectRatio.PORTRAIT_WIDESCREEN, .2, 9, 25, 2**63 + 5, True)
        return service, read, clock, prompt, settings

    def test_prepare_execute_reopen_resume_feedback_and_dlss_keep_order_and_disabled_entries(self):
        for mode in (H3RenderInputMode.T2VA, H3RenderInputMode.REF2VA):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                service, read, _, prompt, settings = self.service(directory, mode)
                selected = stack()
                attempt = service.prepare_attempt("two-loras", prompt=prompt, settings=settings, video_loras=selected).attempts[-1]
                service.queue_attempt("two-loras", attempt.attempt_id)
                result = service.execute_attempt("two-loras", attempt.attempt_id).attempt(attempt.attempt_id)
                self.assertEqual(result.status, H3RenderAttemptStatus.SUCCEEDED, result.error)
                loader = next(n for n in service.comfy.submitted[0].values() if "lora_2" in n["inputs"])
                self.assertEqual(loader["inputs"]["lora_2"]["lora"], MOTION)
                read.assert_called_once()
                project = LocalH3RenderProjectStore(directory).get("two-loras")
                self.assertEqual(project.resume_attempt(attempt.attempt_id).attempt(attempt.attempt_id).video_loras, selected)
                serialized = serialize_h3_render_project(project)["attempts"][-1]["video_loras"]
                self.assertEqual(H3VideoLoraStack.from_dict(serialized), selected)
                self.assertEqual(H3VideoLoraStack.from_dict(json.loads(_attempt_context(result))["video_loras"]), selected)
                adapter = DlssCandidates(edit=None, assisted=None, h3=service)
                owner = "ref2v" if mode is H3RenderInputMode.REF2VA else "h3"
                snapshot = adapter.prepare(owner, "two-loras", attempt.attempt_id, DlssSettings())
                self.assertEqual(H3VideoLoraStack.from_dict(snapshot["generation_video_loras"]), selected)
                job = dict(job_id="dlss-fixture", snapshot=snapshot, report_asset_id="report", output_asset_id="upscaled",
                    output_metadata={"width": 1280, "height": 1920, "fps": 60, "duration_seconds": 9},
                    settings={"size": "1.724"}, keyframes=[], warnings=[])
                candidate_id = adapter.attach(job, None)
                self.assertEqual(service.projects.get("two-loras").attempt(candidate_id).video_loras, selected)
                self.assertEqual(adapter.attach(job, None), candidate_id)
                self.assertEqual(service.gateway.requests, [])
                disabled = replace(selected, entries=(selected.entries[0], replace(selected.entries[1], enabled=False)))
                saved = service.prepare_attempt("two-loras", prompt=prompt, settings=settings, video_loras=disabled).attempts[-1]
                self.assertEqual(LocalH3RenderProjectStore(directory).get("two-loras").attempt(saved.attempt_id).video_loras, disabled)

    def test_cache_refresh_and_missing_models_block_before_upload_and_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            service, read, clock, prompt, settings = self.service(directory, H3RenderInputMode.REF2VA)
            service.prepare_attempt("two-loras", prompt=prompt, settings=settings, video_loras=replace(stack(), enabled=False))
            read.assert_not_called()
            attempt = service.prepare_attempt("two-loras", prompt=prompt, settings=settings, video_loras=stack()).attempts[-1]
            for _ in range(5): service.video_lora_inventory()
            read.assert_called_once()
            read.return_value = (COMBAT,)
            service.video_lora_inventory(refresh=True)
            service.comfy.upload_image = Mock(side_effect=AssertionError("no upload"))
            service.queue_attempt("two-loras", attempt.attempt_id)
            result = service.execute_attempt("two-loras", attempt.attempt_id).attempt(attempt.attempt_id)
            self.assertEqual(result.status, H3RenderAttemptStatus.FAILED)
            self.assertIn("Motion_Repair", result.error)
            self.assertEqual(service.comfy.submitted, [])
            service.comfy.upload_image.assert_not_called()
            read.side_effect = TimeoutError("offline")
            clock[0] = 61
            self.assertIn("offline", service.video_lora_inventory()[1])
            count = read.call_count
            service.video_lora_inventory()
            self.assertEqual(read.call_count, count)
            clock[0] += 6
            service.video_lora_inventory()
            self.assertEqual(read.call_count, count + 1)

    def test_http_spec_defaults_legacy_requests_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            service, read, _, prompt, settings = self.service(directory)
            service.list_models = Mock(return_value=())
            client = TestClient(create_app(object(), h3_render=service))
            for mode in ("h3-base", "ref2va"):
                basic = client.get(f"/api/h3-render/spec?mode={mode}").json()
                self.assertFalse(basic["video_lora_stack"]["defaults"]["enabled"])
                self.assertEqual(basic["video_lora_stack"]["defaults"]["entries"], [])
                self.assertEqual((basic["defaults"]["megapixels"], basic["defaults"]["initial_megapixels"]), (.2, .2))
                bunny = client.get(f"/api/h3-render/spec?mode={mode}&recipe_id=minimax-h3-bunny&recipe_version=0.1.2").json()
                defaults = H3VideoLoraStack.from_dict(bunny["video_lora_stack"]["defaults"])
                self.assertEqual([(e.name, e.strength, e.second_strength) for e in defaults.entries], [(COMBAT, .6, .2), (MOTION, .6, .2)])
            read.assert_called_once()
            body = dict(prompt=prompt, aspect_ratio=settings.aspect_ratio.value, megapixels=.2,
                        duration_seconds=9, steps=25, seed="42", seed_locked=True, video_loras=asdict(stack()))
            response = client.post("/api/h3-render/projects/two-loras/attempts", json=body)
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(H3VideoLoraStack.from_dict(response.json()["project"]["attempts"][-1]["video_loras"]), stack())
            for bad in ({**body, "video_lora": {"name": COMBAT}},
                        {**body, "recipe_id": "minimax-h3-latent-speed", "recipe_version": "0.1.4"},
                        {**body, "video_loras": {"entries": [{"name": COMBAT}] * 3}},
                        {**body, "video_loras": {"entries": [{"name": COMBAT, "strength": True}]}},
                        {**body, "video_loras": {"entries": [{"name": COMBAT, "second_strength": .2}]}}):
                self.assertEqual(client.post("/api/h3-render/projects/two-loras/attempts", json=bad).status_code, 422)
            old_body = {k: v for k, v in body.items() if k != "video_loras"}
            old = client.post("/api/h3-render/projects/two-loras/attempts", json={**old_body, "video_lora": {"name": COMBAT}})
            self.assertEqual(old.status_code, 201, old.text)
            self.assertIsNone(old.json()["project"]["attempts"][-1]["video_loras"])
            client.get("/api/h3-render/video-loras?refresh=true")
            self.assertEqual(read.call_count, 2)

    def test_legacy_schemas_do_not_add_a_second_lora(self):
        args = parameters("h3", H3RenderInputMode.T2VA)
        attempt = H3RenderAttempt("old", 1, PROMPT, PROMPT, args["settings"], False, (),
                                 recipe=previous_recipe("h3").reference, video_lora=H3VideoLoraSelection(COMBAT))
        project = H3RenderProject("old", "session", "revision", "fake", H3RenderInputMode.T2VA, PROMPT,
                                 attempts=(attempt,), revision_version=H3RenderRevisionVersion.CAMERA_LOCKED)
        raw = _serialize(project)
        self.assertEqual(raw["schema_version"], 13)
        for version in range(1, 12):
            with self.subTest(schema=version):
                historical = deepcopy(raw)
                historical["schema_version"] = version
                historical["attempts"][0].pop("video_loras")
                reopened = _deserialize(historical)
                self.assertEqual(reopened, project)
                self.assertIsNone(reopened.attempts[0].video_loras)

    def test_conversion_snapshot_retains_the_stack_without_calling_a_model(self):
        with tempfile.TemporaryDirectory() as directory:
            conversion, source, setup, _ = conversion_fixtures.H3Ref2VConversionTest().service(directory)
            current = recipe("ref")
            setup = replace(setup, recipe=current.reference, video_loras=stack())
            conversion.renders.workflow_for_mode = lambda *args: current
            conversion.renders.validate_video_loras = Mock()
            target = conversion.prepare(source.project_id, request_id="two-lora-conversion", prompt=source.current_prompt, model_id="fake", setup=setup)
            conversion.renders.validate_video_loras.assert_called_once_with(current, None, setup.video_loras)
            reopened = LocalH3RenderProjectStore(directory).get(target.project_id)
            self.assertEqual(reopened.adaptation.render_setup, setup)
            self.assertEqual(conversion.renders.gateway.requests, [])
