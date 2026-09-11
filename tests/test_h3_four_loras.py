"""User-run four-LoRA regressions, with fake transports only."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from panelforge.application.dlss_candidates import DlssCandidates
from panelforge.application.h3_render import _attempt_context
from panelforge.domain.dlss import DlssSettings
from panelforge.domain.h3_render import H3RenderAttemptStatus, H3RenderInputMode, H3VideoLoraSlot, H3VideoLoraStack
from panelforge.features.lab.web import create_app, serialize_h3_render_project
from panelforge.infrastructure.storage import LocalH3RenderProjectStore
from tests import test_h3_multiple_loras as previous


VERSIONS = {
    "h3": ("video.generate.h3-base/minimax-h3-latent-speed", "0.1.6"),
    "ref": ("video.generate.ref2v/minimax-h3-ref2v", "0.2.4"),
    "bunny": ("video.generate.h3-base/minimax-h3-bunny", "0.1.3"),
}
NAMES = (previous.COMBAT, previous.MOTION, "minmax_nsfw/third.safetensors", "minmax_nsfw/fourth.safetensors")


def recipe(kind):
    with patch.object(previous, "VERSIONS", VERSIONS):
        return previous.recipe(kind)


def stack(per_pass=False):
    return H3VideoLoraStack(tuple(H3VideoLoraSlot(name, first, second if per_pass else None)
        for name, first, second in zip(NAMES, (.7, .55, .4, .25), (.15, .3, .2, .1))),
        clip_last_layer=None if per_pass else -2)


def service_fixture(directory, mode):
    with patch.object(previous, "VERSIONS", VERSIONS):
        result = previous.MultipleLoraServiceTest().service(directory, mode)
    result[1].return_value = NAMES
    return result


class FourLoraWorkflowTest(unittest.TestCase):
    def test_basic_four_ordered_files_disabled_slots_and_clip(self):
        for kind, mode in (("h3", H3RenderInputMode.T2VA), ("ref", H3RenderInputMode.REF2VA)):
            for clip in (-2, None):
                for disabled in (False, True):
                    with self.subTest(kind=kind, clip=clip, disabled=disabled):
                        selected = replace(stack(), clip_last_layer=clip)
                        if disabled:
                            selected = replace(selected, entries=tuple(replace(e, enabled=i != 1) for i, e in enumerate(selected.entries)))
                        current = recipe(kind)
                        graph = current.build_workflow(video_loras=selected, **previous.parameters(kind, mode))
                        inputs = graph[current.lora_config["loader_node_id"]]["inputs"]
                        loaded = [inputs[f"lora_{i}"] for i in range(1, len(selected.active_entries) + 1)]
                        self.assertEqual([(v["lora"], v["strength"]) for v in loaded],
                                         [(e.name, e.strength) for e in selected.active_entries])
                        self.assertNotIn(f"lora_{len(loaded) + 1}", inputs)

    def test_bunny_four_per_pass_chains_share_only_the_upstream_model(self):
        current = recipe("bunny")
        for mode in H3RenderInputMode:
            for turbo, preview in ((True, True), (False, False)):
                for checkpoint in (None, previous.EROS):
                    with self.subTest(mode=mode, turbo=turbo, checkpoint=checkpoint):
                        selected = stack(True)
                        graph = current.build_workflow(video_loras=selected, checkpoint=checkpoint,
                            **previous.parameters("bunny", mode, turbo=turbo, preview=preview))
                        paths, upstreams = [], []
                        for pass_index, branch in enumerate(current.lora_config["branches"]):
                            ends = [graph[t["node_id"]]["inputs"][t["input"]] for t in branch["targets"] if t["node_id"] in graph]
                            preview_class = current.manifest["templates"]["preview"]["class_type"]
                            ends = [graph[end[0]]["inputs"]["model"] if graph[end[0]]["class_type"] == preview_class else end for end in ends]
                            self.assertTrue(ends)
                            self.assertTrue(all(end == ends[0] for end in ends))
                            link, path, loaded = ends[0], [], []
                            for _ in range(4):
                                self.assertNotIn(link[0], path)
                                path.append(link[0])
                                inputs = graph[link[0]]["inputs"]
                                loaded.append((inputs["lora_name"], inputs["strength_model"]))
                                link = inputs["model"]
                            self.assertEqual(list(reversed(loaded)), [(e.name, e.strength if pass_index == 0 else e.second_strength) for e in selected.entries])
                            paths.append(set(path)); upstreams.append(link)
                        self.assertFalse(paths[0] & paths[1])
                        self.assertEqual(upstreams[0], upstreams[1])
                        self.assertNotIn(upstreams[0][0], paths[0] | paths[1])

    def test_zero_one_two_and_legacy_stacks_keep_the_previous_graph_and_defaults(self):
        for kind in VERSIONS:
            current, old = recipe(kind), previous.recipe(kind)
            mode = H3RenderInputMode.REF2VA if kind == "ref" else H3RenderInputMode.FL2VA
            args = previous.parameters(kind, mode)
            self.assertEqual(current.video_lora_stack_spec()["maximum"], 4)
            self.assertEqual(old.video_lora_stack_spec()["maximum"], 2)
            new_defaults = current.video_lora_stack_spec()["defaults"]
            old_defaults = old.video_lora_stack_spec()["defaults"]
            self.assertEqual({**new_defaults, "version": "0.1.0"}, old_defaults)
            for count in range(3):
                for version in ("0.1.0", "0.2.0"):
                    selected = replace(stack(kind == "bunny"), entries=stack(kind == "bunny").entries[:count], version=version)
                    with self.subTest(kind=kind, count=count, version=version):
                        self.assertEqual(current.build_workflow(video_loras=selected, **args), old.build_workflow(video_loras=selected, **args))
            with self.assertRaisesRegex(ValueError, "maximum 2"):
                old.build_workflow(video_loras=stack(kind == "bunny"), **args)

    def test_bunny_dependency_validation_covers_third_and_fourth_files(self):
        current = recipe("bunny")
        graph = current.build_workflow(video_loras=stack(True), **previous.parameters("bunny", H3RenderInputMode.I2VA))
        for missing in NAMES[2:]:
            def describe(name):
                fields = {}
                for node in graph.values():
                    if node["class_type"] == name:
                        for key, value in node["inputs"].items():
                            if isinstance(value, str):
                                fields.setdefault(key, [[]])
                                if value != missing:
                                    fields[key][0].append(value)
                return {name: {"input": {"required": fields}}}
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, missing):
                current.validate_dependencies(Mock(describe_node=describe), graph)

    def test_contract_limits_are_versioned(self):
        self.assertEqual(H3VideoLoraStack.from_dict(asdict(stack(True))), stack(True))
        for invalid in (
            {**asdict(stack()), "entries": [*asdict(stack())["entries"], {"name": "minmax_nsfw/fifth.safetensors"}]},
            {**asdict(stack()), "version": "0.1.0"},
            {**asdict(stack()), "version": "unknown"},
            {**asdict(stack()), "entries": [*asdict(stack())["entries"][:3], asdict(stack())["entries"][0]]},
        ):
            with self.assertRaises(ValueError):
                H3VideoLoraStack.from_dict(invalid)


class FourLoraServiceTest(unittest.TestCase):
    def test_prepare_execute_reopen_feedback_and_dlss_preserve_all_four(self):
        for mode in (H3RenderInputMode.T2VA, H3RenderInputMode.REF2VA):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                service, _, _, prompt, settings = service_fixture(directory, mode)
                selected = stack()
                attempt = service.prepare_attempt("two-loras", prompt=prompt, settings=settings, video_loras=selected).attempts[-1]
                service.queue_attempt("two-loras", attempt.attempt_id)
                result = service.execute_attempt("two-loras", attempt.attempt_id).attempt(attempt.attempt_id)
                self.assertEqual(result.status, H3RenderAttemptStatus.SUCCEEDED, result.error)
                project = LocalH3RenderProjectStore(directory).get("two-loras")
                self.assertEqual(project.resume_attempt(attempt.attempt_id).attempt(attempt.attempt_id).video_loras, selected)
                self.assertEqual(H3VideoLoraStack.from_dict(serialize_h3_render_project(project)["attempts"][-1]["video_loras"]), selected)
                self.assertEqual(H3VideoLoraStack.from_dict(json.loads(_attempt_context(result))["video_loras"]), selected)
                adapter = DlssCandidates(edit=None, assisted=None, h3=service)
                owner = "ref2v" if mode is H3RenderInputMode.REF2VA else "h3"
                snapshot = adapter.prepare(owner, "two-loras", attempt.attempt_id, DlssSettings())
                self.assertEqual(H3VideoLoraStack.from_dict(snapshot["generation_video_loras"]), selected)
                self.assertEqual(service.gateway.requests, [])

    def test_http_accepts_four_and_rejects_five_or_an_old_recipe_before_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _, _, prompt, settings = service_fixture(directory, H3RenderInputMode.T2VA)
            service.list_models = Mock(return_value=())
            client = TestClient(create_app(object(), h3_render=service))
            body = dict(prompt=prompt, aspect_ratio=settings.aspect_ratio.value, megapixels=.2,
                        duration_seconds=9, steps=25, seed="42", seed_locked=True, video_loras=asdict(stack()))
            response = client.post("/api/h3-render/projects/two-loras/attempts", json=body)
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(H3VideoLoraStack.from_dict(response.json()["project"]["attempts"][-1]["video_loras"]), stack())
            invalid = deepcopy(body)
            invalid["video_loras"]["entries"].append({"name": "minmax_nsfw/fifth.safetensors"})
            self.assertEqual(client.post("/api/h3-render/projects/two-loras/attempts", json=invalid).status_code, 422)
            with self.assertRaisesRegex(ValueError, "maximum 2"):
                service.validate_video_loras(previous.recipe("h3"), video_loras=stack())
            self.assertEqual(len(service.projects.get("two-loras").attempts), 1)
            self.assertEqual(service.comfy.submitted, [])

    def test_missing_fourth_file_blocks_before_upload_and_disabled_slot_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            service, read, _, prompt, settings = service_fixture(directory, H3RenderInputMode.REF2VA)
            attempt = service.prepare_attempt("two-loras", prompt=prompt, settings=settings, video_loras=stack()).attempts[-1]
            read.return_value = NAMES[:3]
            service.video_lora_inventory(refresh=True)
            service.comfy.upload_image = Mock(side_effect=AssertionError("no upload"))
            service.queue_attempt("two-loras", attempt.attempt_id)
            result = service.execute_attempt("two-loras", attempt.attempt_id).attempt(attempt.attempt_id)
            self.assertEqual(result.status, H3RenderAttemptStatus.FAILED)
            self.assertIn(NAMES[3], result.error)
            service.comfy.upload_image.assert_not_called()
            self.assertEqual(service.comfy.submitted, [])
            disabled = replace(stack(), entries=(*stack().entries[:3], replace(stack().entries[3], enabled=False)))
            saved = service.prepare_attempt("two-loras", prompt=prompt, settings=settings, video_loras=disabled).attempts[-1]
            self.assertEqual(LocalH3RenderProjectStore(directory).get("two-loras").attempt(saved.attempt_id).video_loras, disabled)
