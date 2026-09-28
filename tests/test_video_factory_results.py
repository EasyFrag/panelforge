"""User-run regression tests: fake services and temporary files only."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.video_factory import VideoFactoryService, FactoryConflict
from panelforge.application.video_factory_workflows import FactoryWorkflows
from panelforge.domain.video_factory import configuration, apply_preset, new_item
from panelforge.domain.video_factory_results import delivery_material, instagram_text, variant_text
from panelforge.domain.h3_render import H3RenderInputMode
from panelforge.domain.video_lab import VideoAspectRatio, VideoLabSettings
from panelforge.features.lab.video_factory_web import video_factory_router
from panelforge.infrastructure.storage import LocalAssetStore
from panelforge.infrastructure.video_factory_outputs import VideoFactoryOutputs
from panelforge.infrastructure.presets import (H3RenderPresetRecipe, load_h3_render_workflow,
    Ref2VH3RenderPresetRecipe, VideoLabPresetRecipe, load_video_lab_workflow)
from tests.test_video_factory import MemoryStore, FakeWorkflows

ROOT = Path(__file__).resolve().parents[1]
VARIANT = dict(hook="Une forêt 🌱", caption="Réparée 👩🏽‍🚒\nÀ nouveau vivante.",
               emojis=["🌱", "👩🏽‍🚒", "🇫🇷", "🇫🇷"], hashtags=["#forêt", "#nature"])


def completed(asset_id="asset-" + "a" * 32):
    config = configuration()
    config.update(preset="custom", preset_origin="little_men")
    item = new_item("Désert / essai", config, {}, "key")
    item["status"] = "succeeded"
    item["steps"]["video"].update(status="succeeded", output={"asset_id": asset_id},
                                    finished_at="2026-09-26T12:00:00+00:00")
    item["steps"]["social"].update(status="succeeded", output={"variants": [deepcopy(VARIANT)]})
    return item


class FactoryResultsTest(unittest.TestCase):
    def test_unicode_text_preserves_lines_and_deduplicates_separate_emojis(self):
        text = variant_text(VARIANT)
        for emoji in ("🌱", "👩🏽‍🚒", "🇫🇷"):
            self.assertEqual(text.count(emoji), 1)
        self.assertIn("👩🏽‍🚒\nÀ nouveau", text)
        self.assertTrue(text.endswith("#forêt #nature"))
        content = instagram_text(completed())
        self.assertEqual(content.encode("utf-8").decode("utf-8"), content)
        self.assertIn("Variante 1", content)

    def test_family_survives_custom_and_story_source_takes_precedence(self):
        item = completed()
        self.assertEqual(delivery_material(item)["family"], "Petits hommes")
        item["source"] = dict(kind="episode", group="La forêt", index=4)
        material = delivery_material(item)
        self.assertEqual(material["family"], "Histoire")
        self.assertIn("scene_05", material["name"])

    def test_wait_for_dlss_but_keep_raw_video_when_dlss_failed(self):
        item = completed()
        item["steps"]["dlss"]["status"] = "running"
        self.assertIsNone(delivery_material(item))
        item["steps"]["dlss"]["status"] = "failed"
        self.assertEqual(delivery_material(item)["stage"], "video")
        item["steps"]["dlss"].update(status="succeeded", output={"asset_id": "asset-" + "b" * 32})
        self.assertEqual(delivery_material(item)["stage"], "dlss")

    def test_preset_defaults_do_not_mutate_the_source(self):
        config = configuration()
        config["references"] = [dict(asset_id="asset-image", role="unassigned")]
        previous = deepcopy(config)
        little = apply_preset(config, "little_men", config)
        self.assertTrue(little["dlss"]["enabled"])
        self.assertTrue(little["social"]["enabled"])
        self.assertEqual((little["social"]["language"], little["social"]["variant_count"]), ("en", 3))
        self.assertEqual(config, previous)
        self.assertTrue(apply_preset(config, "lips", config)["social"]["enabled"])


class FactoryOutputFilesTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.assets = LocalAssetStore(Path(self.temp.name) / "workspace")
        self.asset = self.assets.create(b"immutable video fixture", media_type="video/mp4")
        self.outputs = VideoFactoryOutputs(Path(self.temp.name) / "dlss", self.assets)
        self.item = completed(self.asset.asset_id)
        self.material = delivery_material(self.item)

    def test_publish_is_idempotent_with_base_nested_and_utf8_text_at_date_root(self):
        delivery = self.outputs.plan(self.item, self.material, {})
        saved = self.outputs.publish(delivery, self.material)
        again = self.outputs.publish(delivery, self.material)
        self.assertEqual(saved, again)
        video, text = Path(saved["video_path"]), Path(saved["text_path"])
        self.assertEqual(video.parent.name, "base video")
        self.assertEqual(video.parent.parent, text.parent)
        self.assertEqual(text.parent.parent.name, "Petits hommes")
        self.assertEqual(Path(saved["folder"]), text.parent)
        self.assertFalse((text.parent / video.name).exists())
        self.assertEqual(text.read_text(encoding="utf-8"), self.material["text"])
        self.assertEqual(video.read_bytes(), self.assets.read_bytes(self.asset.asset_id))
        self.assertEqual(list(video.parent.glob(".factory-*")), [])

    def test_delayed_instagram_keeps_the_assigned_folder_and_updates_only_its_text(self):
        material = dict(self.material, text="")
        saved = self.outputs.publish(self.outputs.plan(self.item, material, {}), material)
        later = dict(self.material, completed_at="2026-09-28T12:00:00+00:00")
        delivery = self.outputs.plan(self.item, later, saved)
        self.assertEqual(delivery["folder"], saved["folder"])
        updated = self.outputs.publish(delivery, later)
        self.assertTrue(updated["has_text"])

    def test_existing_user_file_is_not_overwritten(self):
        delivery = self.outputs.plan(self.item, self.material, {})
        target = Path(delivery["video_path"])
        target.parent.mkdir(parents=True)
        target.write_bytes(b"other video")
        with self.assertRaises(ValueError): self.outputs.publish(delivery, self.material)
        self.assertEqual(target.read_bytes(), b"other video")

    def test_modified_instagram_file_is_preserved_on_retry(self):
        saved = self.outputs.publish(self.outputs.plan(self.item, self.material, {}), self.material)
        text = Path(saved["text_path"]); text.write_text("my edits", encoding="utf-8")
        revised = dict(self.material, text=self.material["text"] + "New caption")
        delivery = self.outputs.plan(self.item, revised, saved)
        with self.assertRaises(ValueError): self.outputs.publish(delivery, revised)
        self.assertEqual(text.read_text(encoding="utf-8"), "my edits")

    def test_paths_cannot_escape_the_output_root(self):
        with self.assertRaises(ValueError):
            self.outputs.open_folder({"folder": self.temp.name})
        previous = dict(asset_id=self.asset.asset_id, folder=str(Path(self.temp.name) / "outside"), video_path="bad")
        with self.assertRaises(ValueError): self.outputs.plan(self.item, self.material, previous)

    def test_filesystem_without_cross_volume_link_falls_back_to_copy(self):
        delivery = self.outputs.plan(self.item, self.material, {})
        with patch("panelforge.infrastructure.video_factory_outputs.os.link", side_effect=OSError("different volume")):
            saved = self.outputs.publish(delivery, self.material)
        self.assertEqual(Path(saved["video_path"]).read_bytes(), b"immutable video fixture")

    def test_dlss_after_failed_delivery_keeps_base_nested_and_dlss_at_date_root(self):
        base = self.outputs.publish(self.outputs.plan(self.item, self.material, {}), self.material)
        enhanced = self.assets.create(b"enhanced video fixture", media_type="video/mp4")
        self.item["steps"]["dlss"].update(status="succeeded", output={"asset_id":enhanced.asset_id},
                                        finished_at=self.item["steps"]["video"]["finished_at"])
        material = delivery_material(self.item)
        dlss = self.outputs.publish(self.outputs.plan(self.item, material, base), material)
        self.assertEqual(Path(dlss["video_path"]).parent, Path(dlss["folder"]))
        self.assertEqual(Path(dlss["text_path"]).parent, Path(dlss["folder"]))
        self.assertEqual(Path(base["video_path"]).parent, Path(dlss["folder"]) / "base video")
        self.assertEqual(Path(base["video_path"]).read_bytes(), b"immutable video fixture")
        self.assertEqual(Path(dlss["video_path"]).read_bytes(), b"enhanced video fixture")
        self.assertEqual(list(Path(dlss["folder"]).glob("*_Video.mp4")), [])

    def test_replanning_old_base_export_uses_subfolder_but_keeps_date_and_text_path(self):
        planned = self.outputs.plan(self.item, self.material, {})
        legacy = dict(planned, video_path=str(Path(planned["folder"]) / Path(planned["video_path"]).name))
        moved = self.outputs.plan(self.item, self.material, legacy)
        self.assertEqual(moved["folder"], legacy["folder"])
        self.assertEqual(moved["text_path"], legacy["text_path"])
        self.assertEqual(Path(moved["video_path"]).parent.name, "base video")
        saved = self.outputs.publish(moved, self.material)
        self.assertTrue(Path(saved["video_path"]).exists())
        self.assertFalse(Path(legacy["video_path"]).exists())

    def test_file_occupying_base_folder_fails_without_touching_it(self):
        plan = self.outputs.plan(self.item, self.material, {})
        folder = Path(plan["folder"])
        folder.mkdir(parents=True)
        (folder / "base video").write_bytes(b"user file")
        with self.assertRaises(OSError): self.outputs.publish(plan, self.material)
        self.assertEqual((folder / "base video").read_bytes(), b"user file")


class FactoryPatchServiceTest(unittest.TestCase):
    def test_export_failure_and_retry_never_replay_a_generation(self):
        store, adapter, outputs = MemoryStore(), FakeWorkflows(), Mock()
        item = completed(); store.value["items"] = [item]
        outputs.plan.side_effect = lambda item, material, previous: dict(key=material["key"], status="copying")
        outputs.publish.side_effect = [OSError("disk unavailable"), {"key": delivery_material(item)["key"], "status": "succeeded"}]
        service = VideoFactoryService(store=store, adapter=adapter, outputs=outputs)
        service._start_delivery(); service._delivery_thread.join(2)
        self.assertFalse(service._delivery_thread.is_alive())
        self.assertEqual(service.snapshot()["items"][0]["delivery"]["status"], "failed")
        service._start_delivery()
        self.assertEqual(outputs.publish.call_count, 1)
        service.retry_delivery(item["id"]); service._start_delivery(); service._delivery_thread.join(2)
        self.assertEqual(service.snapshot()["items"][0]["delivery"]["status"], "succeeded")
        self.assertEqual(adapter.calls, [])
        self.assertEqual(service.snapshot()["items"][0]["steps"]["video"]["status"], "succeeded")

    def test_bulk_remove_is_atomic_and_leaves_sources_outside_the_factory(self):
        service = VideoFactoryService(store=MemoryStore(), adapter=FakeWorkflows())
        a, b = [new_item(name, configuration(), {"kind": "image", "id": name}, name) for name in ("a", "b")]
        service._state["items"] = [a, b]
        b["status"] = "queued"
        revisions = {i["id"]: i["revision"] for i in (a, b)}
        with self.assertRaises(FileNotFoundError):
            service.action("remove", [a["id"], "missing"], {**revisions, "missing": 1})
        self.assertEqual(len(service.snapshot()["items"]), 2)
        service.action("remove", list(revisions), revisions)
        self.assertEqual(service.snapshot()["items"], [])
        self.assertEqual(service.adapter.calls, [])

    def test_factory_video_returns_before_any_post_render_cooldown(self):
        attempt = NS(attempt_id="attempt", status=NS(value="queued"), output_asset_id="asset-video", keyframes=[])
        project = NS(project_id="project", input_mode=H3RenderInputMode.I2VA, attempt=lambda identity: attempt)
        render = Mock(run_timeout=1)
        render.projects.get.return_value = project; render.get.return_value = project
        render.execute_attempt.side_effect = lambda *a, **kw: setattr(attempt.status, "value", "succeeded")
        adapter = FactoryWorkflows(prompt_lab=None, composition=None, render=render, dlss=None,
                                   social=None, episodes=None, assets=None, coordinator=None)
        adapter._project = Mock(return_value=project)
        item = completed(); item["runtime"]["attempt_id"] = "attempt"
        output = adapter._video(item, Mock(), lambda: False, Mock())
        self.assertEqual(output["asset_id"], "asset-video")
        self.assertNotIn("post_cooldown_seconds", render.execute_attempt.call_args.kwargs)

    def test_text_download_and_remote_folder_open(self):
        service = VideoFactoryService(store=MemoryStore(), adapter=FakeWorkflows(), outputs=Mock())
        item = completed(); service._state["items"] = [item]
        app = FastAPI(); app.include_router(video_factory_router(service, validate_image=lambda value: "image/png"))
        with TestClient(app) as client:
            response = client.get(f"/api/video-factory/items/{item['id']}/instagram.txt")
            self.assertEqual(response.status_code, 200)
            self.assertIn("charset=utf-8", response.headers["content-type"])
            self.assertIn("👩🏽‍🚒", response.content.decode("utf-8"))
            denied = client.post(f"/api/video-factory/items/{item['id']}/open-folder")
            self.assertEqual(denied.status_code, 403)
            service.outputs.open_folder.assert_not_called()


class BatchPreviewGraphsTest(unittest.TestCase):
    def test_batch_removes_preview_but_preserves_outputs_and_model_dependencies(self):
        settings = VideoLabSettings(VideoAspectRatio.PORTRAIT_WIDESCREEN, .9, 8, 8, 123, True)
        recipes = [
            (H3RenderPresetRecipe(load_h3_render_workflow(ROOT / "workflows/video.generate.h3-base/minimax-h3-latent-speed/0.1.7")),
             dict(input_mode=H3RenderInputMode.T2VA, first_frame=None, last_frame=None)),
            (Ref2VH3RenderPresetRecipe(VideoLabPresetRecipe(load_video_lab_workflow(ROOT / "workflows/video.generate.ref2v/minimax-h3-ref2v/0.2.5"))),
             dict(source_images=["image.png"])),
        ]
        for recipe, inputs in recipes:
            with self.subTest(recipe=recipe.reference.recipe_id):
                arguments = dict(inputs, prompt="A worker repairs a bridge.", settings=settings,
                                 output_filename_prefix="fixture", keyframe_indices=(0, 24))
                manual = recipe.build_workflow(**arguments)
                batch = recipe.build_workflow(**arguments, preview_enabled=False)
                self.assertTrue(any(n["class_type"] == "ModelPreviewOverrideKJ" for n in manual.values()))
                self.assertFalse(any(n["class_type"] == "ModelPreviewOverrideKJ" for n in batch.values()))
                for identity, node in manual.items():
                    if node["class_type"] in {"SaveVideo", "SaveImage"}:
                        self.assertEqual(batch[identity], node)
                for node in batch.values():
                    for value in node.get("inputs", {}).values():
                        if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and type(value[1]) is int:
                            self.assertIn(value[0], batch)
