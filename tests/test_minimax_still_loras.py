"""User-run LoRA regressions; only fake model, assistant and render ports."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.domain.minimax_edit import MinimaxEditSettings
from panelforge.domain.mh_assisted import Settings as MhSettings
from panelforge.infrastructure.presets.minimax_edit import load_minimax_edit_workflow
from panelforge.features.lab.minimax_edit_web import minimax_edit_router
from panelforge.features.lab.mh_assisted_web import mh_assisted_router
from test_minimax_edit import MinimaxFixture
from tests.test_mh_assisted import MhFixture

ROOT = Path(__file__).resolve().parents[1] / "workflows/image.edit/minimax-h3-still"
A, B = "minmax_nsfw/style-a.safetensors", "minmax_nsfw/style-b.safetensors"


class MinimaxStillLoraContractTests(unittest.TestCase):
    def test_legacy_settings_defaults_and_json_round_trip_for_both_workshops(self):
        for contract in (MinimaxEditSettings, MhSettings):
            self.assertEqual(contract().active_loras, ())
            selected = contract(loras=[dict(name=A, strength=.375), dict(name=B, enabled=False)])
            self.assertEqual(contract(**json.loads(json.dumps(selected.record()))), selected)
            self.assertEqual([entry.name for entry in selected.active_loras], [A])

    def test_rejects_foreign_paths_duplicates_bad_values_and_excess_slots(self):
        invalid = [None, "bad", [None], [dict(name="flux/style.safetensors")],
            [dict(name="minmax_nsfw/../style.safetensors")], [dict(name=A), dict(name=A.upper())],
            [dict(name=A, enabled=1)], [dict(name=A, strength=True)], [dict(name=A, strength=float("nan"))],
            [dict(name=A, strength=float("inf"))], [dict(name=A, strength=-.1)], [dict(name=A, strength=1.01)],
            [dict(name=f"minmax_nsfw/{i}.safetensors") for i in range(5)]]
        for values in invalid:
            with self.subTest(values=values), self.assertRaises((ValueError, TypeError)):
                MinimaxEditSettings(loras=values)

    def graph(self, workflow, settings, **kwargs):
        return workflow.build(images=["reference.png"], prompt="Use <Picture 1> for composition.",
            settings=settings, dimensions=(1088, 1920), composition=False, output_prefix="fixture", **kwargs)

    def test_disabled_and_zero_strength_match_previous_graph_exactly(self):
        old, new = [load_minimax_edit_workflow(ROOT / version) for version in ("1.3.0", "1.4.0")]
        for settings in (MinimaxEditSettings(), MinimaxEditSettings(loras=[dict(name=A, enabled=False), dict(name=B, strength=0)]),
                         MinimaxEditSettings(resolution="source", reference_mode="native")):
            self.assertEqual(self.graph(old, settings), self.graph(new, settings))

    def test_four_adapters_chain_in_order_after_hybrid_without_changing_clip(self):
        workflow = load_minimax_edit_workflow(ROOT / "1.4.0")
        baseline = deepcopy(workflow.template)
        entries = [dict(name=f"minmax_nsfw/style-{i}.safetensors", strength=(i+1)/4) for i in range(4)]
        graph = self.graph(workflow, MinimaxEditSettings(loras=entries))
        bindings = workflow.manifest["lora_slots"]
        previous = bindings["model_source"]
        for node_id, entry in zip(bindings["node_ids"], entries):
            self.assertEqual(graph[node_id], {"class_type":"LoraLoaderModelOnly", "inputs":{
                "model":previous, "lora_name":entry["name"], "strength_model":entry["strength"]}})
            previous = [node_id, 0]
        for target in bindings["model_targets"]:
            self.assertEqual(graph[target["node_id"]]["inputs"][target["input"]], previous)
        clip = workflow.manifest["components"]["clip"]["node_id"]
        self.assertEqual(graph[clip], baseline[clip])
        self.assertEqual(workflow.template, baseline)
        self.assertFalse(any(n["class_type"] == "CLIPSetLastLayer" for n in graph.values()))
        with self.assertRaisesRegex(ValueError, "LoRA"):
            self.graph(load_minimax_edit_workflow(ROOT / "1.3.0"), MinimaxEditSettings(loras=entries))


class LoraServiceChecks:
    def setUp(self):
        super().setUp()
        self.service.workflow = load_minimax_edit_workflow(ROOT / "1.4.0")
        self.comfy.list_lora_models = Mock(return_value=(B, A, A, "flux/other.safetensors", "minmax_nsfw/../bad.safetensors"))

    def select(self, values):
        self.update(settings={**self.current()["settings"], "loras":values},
                    prompt="Use <Picture 1> for composition.")

    def test_catalogue_filters_caches_refreshes_and_failure_is_explicit(self):
        self.assertEqual(self.service.lora_inventory()["models"], [A, B])
        self.service.lora_inventory()
        self.comfy.list_lora_models.assert_called_once()
        self.comfy.list_lora_models.side_effect = OSError("offline")
        result = self.service.lora_inventory(refresh=True)
        self.assertTrue(result["warning"])
        self.assertEqual(result["models"], [])
        self.select([dict(name=A)])
        with self.assertRaisesRegex(ValueError, "indisponible"):
            self.queue()
        self.assertEqual(self.current()["attempts"], [])

    def test_missing_active_selection_blocks_queue_but_disabled_needs_no_catalogue(self):
        missing = "minmax_nsfw/missing.safetensors"
        self.select([dict(name=missing)])
        with self.assertRaisesRegex(ValueError, "indisponible"):
            self.queue()
        self.comfy.list_lora_models.reset_mock()
        self.select([dict(name=missing, enabled=False)])
        self.queue()
        self.comfy.list_lora_models.assert_not_called()

    def test_queued_attempt_freezes_settings_and_replay_does_not_query_catalogue(self):
        self.select([dict(name=A, strength=.375), dict(name=B, enabled=False)])
        first = deepcopy(self.queue())
        self.select([])
        self.assertEqual(self.current()["attempts"][0]["settings"], first["settings"])
        self.assertEqual(first["recipe"]["version"], "1.4.0")
        self.comfy.list_lora_models.reset_mock()
        self.assertEqual(self.queue()["id"], first["id"])
        self.comfy.list_lora_models.assert_not_called()
        self.service.execute_attempt(self.project_id, self.stage_id, first["id"])
        result = self.current()["attempts"][-1]
        self.assertEqual(result["status"], "succeeded", result["error"])
        nodes = [node for node in self.comfy.submitted[-1].values() if node["class_type"] == "LoraLoaderModelOnly"]
        self.assertEqual([n["inputs"]["lora_name"] for n in nodes], [A])
        self.assertEqual(nodes[0]["inputs"]["strength_model"], .375)
        self.service.restore_attempt(self.project_id, self.stage_id, first["id"], revision=self.current()["revision"])
        self.assertEqual(self.current()["settings"], first["settings"])

    def test_http_catalogue_and_invalid_setting_response(self):
        app = FastAPI()
        app.include_router(self.router(self.service))
        with TestClient(app) as client:
            response = client.get(self.api + "/loras?refresh=true")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["models"], [A, B])
            response = client.patch(f"{self.api}/projects/{self.project_id}/stages/{self.stage_id}", json={
                "revision":self.current()["revision"], "changes":{"settings":{
                    **self.current()["settings"], "loras":[dict(name=A, strength=5)]}}})
            self.assertEqual(response.status_code, 422)


class MinimaxStillLoraServiceTests(LoraServiceChecks, MinimaxFixture):
    router = staticmethod(minimax_edit_router)
    api = "/api/image-lab/minimax-edit"


class MhStillLoraServiceTests(LoraServiceChecks, MhFixture):
    router = staticmethod(mh_assisted_router)
    api = "/api/image-lab/mh-assisted"
