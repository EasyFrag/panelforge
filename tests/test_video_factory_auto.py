"""User-run Auto preset regressions, with no model or generation calls."""
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from panelforge.application.video_factory import VideoFactoryService
from panelforge.application.video_factory_workflows import FactoryWorkflows
from panelforge.domain.video_factory import (
    apply_preset, configuration, new_item, preparation_text, validate_shape,
)
from tests.test_video_factory import FakeWorkflows, MemoryStore


def image_config():
    source = configuration()
    source["references"] = [dict(asset_id="asset-jewels", role="unassigned", label="Bijoux")]
    return source


class FactoryAutoTest(unittest.TestCase):
    def test_auto_replaces_previous_preset_and_can_restore_source(self):
        source = image_config()
        previous = apply_preset(source, "little_men_experimental", source)
        previous["final_prompt"] = "Previously prepared prompt"
        previous["little_men_language"] = "Korean"
        before = deepcopy(previous)
        config = apply_preset(previous, "auto", source)
        validate_shape(config)
        self.assertEqual(previous, before)
        self.assertEqual((config["mode"], config["preset_origin"]), ("h3", "auto"))
        self.assertEqual(config["shot_count"], 1)
        self.assertEqual(config["cinematic_settings"], {"shot_count": 1})
        self.assertEqual(config["render"]["settings"]["duration_seconds"], 9)
        self.assertTrue(config["dlss"]["enabled"])
        self.assertFalse(config["social"]["enabled"])
        self.assertEqual(config["final_prompt"], "")
        self.assertEqual(config["creative_axes"]["dialogue"], 0)
        self.assertEqual(config["little_men_language"], "auto")
        self.assertEqual(config["references"][0]["asset_id"], "asset-jewels")
        self.assertEqual(config["references"][0]["role"], "first_frame")
        self.assertNotIn("main géante", config["intention"])
        self.assertEqual(apply_preset(config, "source", source), source)

    def test_auto_passes_image_and_effective_duration_to_visual_preparation(self):
        source = image_config()
        config = apply_preset(source, "auto", source)
        for duration in (9, 7.5):
            with self.subTest(duration=duration):
                config["render"]["settings"]["duration_seconds"] = duration
                config["preset"] = "custom"
                before = deepcopy(config)
                prompt_lab, composition = Mock(), Mock()
                prompt_lab.create_session.return_value = NS(session_id="session", references=[])
                composition.cookbooks.get.return_value = NS(preparation_steps=2, slots=[])
                adapter = FactoryWorkflows(prompt_lab=prompt_lab, composition=composition,
                    render=None, dlss=None, social=None, episodes=None, assets=None, coordinator=None)
                item = new_item("Bijoux", config, {"kind": "image"}, "key")
                adapter._session(item, Mock(), lambda: False, Mock())
                settings = prompt_lab.create_session.call_args.kwargs
                self.assertEqual(settings["cinematic_settings"].shot_count, 1)
                self.assertEqual(len(settings["references"]), 1)
                ref = settings["references"][0]
                self.assertEqual((ref.asset_id, ref.role), ("asset-jewels", "first_frame"))
                self.assertEqual(ref.evidence_policy.value, "full")
                intent = composition.configure.call_args.kwargs["preparation_intent"]
                self.assertIn(f"{duration:g} secondes", intent.source_text)
                self.assertTrue(intent.source_text.endswith(config["intention"]))
                self.assertIsNone(intent.speech_policy)
                self.assertIsNone(intent.speech_language)
                self.assertEqual(config, before)
                prompt_lab.stream_structure_brief.assert_not_called()

    def test_auto_invalidates_prepared_content_and_undo_restores_it(self):
        source = image_config()
        source.update(intention="Old scene", final_prompt="Old prompt")
        store, adapter = MemoryStore(), FakeWorkflows()
        service = VideoFactoryService(store=store, adapter=adapter)
        item = service.receive([dict(name="Bijoux", config=source, source={"kind": "image"})])["state"]["items"][0]
        result = service.update([item["id"]], {item["id"]: item["revision"]}, preset="auto")
        changed = result["state"]["items"][0]
        self.assertEqual(changed["status"], "preparation")
        for stage in ("plan", "prompt", "video", "dlss"):
            self.assertEqual(changed["steps"][stage]["status"], "pending")
        self.assertEqual(changed["source_config"], source)
        self.assertEqual(adapter.calls, [])
        service = VideoFactoryService(store=store, adapter=adapter)
        self.assertEqual(service.snapshot()["items"][0]["config"], changed["config"])
        restored = service.update([item["id"]], result["revisions"], replacements=result["undo"])
        self.assertEqual(restored["state"]["items"][0]["config"], source)
        self.assertEqual(restored["state"]["items"][0]["steps"]["prompt"]["status"], "succeeded")

    def test_bulk_auto_is_atomic_with_an_incompatible_reference_count(self):
        for count in (0, 2):
            with self.subTest(count=count):
                source = image_config()
                invalid = image_config()
                invalid["references"] = [dict(asset_id=f"asset-{i}", role="unassigned") for i in range(count)]
                service = VideoFactoryService(store=MemoryStore(), adapter=FakeWorkflows())
                items = service.receive([
                    dict(name="Good", config=source, source={"kind": "image", "id": "good"}),
                    dict(name="Other", config=invalid, source={"kind": "image", "id": "other"}),
                ])["state"]["items"]
                before = service.snapshot()
                with self.assertRaises(ValueError):
                    service.update([i["id"] for i in items], {i["id"]: i["revision"] for i in items}, preset="auto")
                self.assertEqual(service.snapshot(), before)

    def test_retired_little_men_records_remain_readable_and_unchanged(self):
        source = image_config()
        legacy = apply_preset(source, "little_men", source)
        expected = deepcopy(legacy)
        store = MemoryStore()
        service = VideoFactoryService(store=store, adapter=FakeWorkflows())
        service.receive([dict(name="Legacy", config=legacy, source={"kind": "image"})])
        snapshot = VideoFactoryService(store=store, adapter=FakeWorkflows()).snapshot()
        self.assertEqual(snapshot["items"][0]["config"], expected)
        self.assertNotIn("little_men", snapshot["presets"])
        self.assertEqual(snapshot["presets"]["little_men_experimental"], "Petits hommes")
        self.assertEqual(preparation_text(expected), expected["intention"])
