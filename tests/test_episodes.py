"""User-run fabrication checks. All model and rendering services are fakes."""
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from panelforge.application.episodes import EpisodeConflict, EpisodeService
from panelforge.application.stories import StoryService
from panelforge.application.prompt_lab import StreamEventKind
from panelforge.domain.episodes import initial_episode, scene_inputs, fingerprint, style_context
from panelforge.domain.krea2_sampling import Krea2AssistedSettings, Krea2AssistedSampling
from panelforge.domain.krea2_batch import Krea2AspectRatio, Krea2LoraSelection
from panelforge.domain.krea2_style_presets import Krea2StylePreset
from panelforge.domain.prompt_composition import CompositionStage
from panelforge.infrastructure.storage.episodes import LocalEpisodeStore
from panelforge.infrastructure.storage.stories import LocalStoryStore


SCENARIO = dict(title="La poche", logline="Une accusation démentie par un portefeuille visible.",
    characters=[dict(id=f"c{i}", name=name, description=f"Personnage fruit : {name}.")
                for i, name in enumerate(("Lila", "Victor", "Témoin"), 1)],
    locations=[dict(id="lieu", name="Épicerie", description="Un comptoir bleu et une porte verte.")],
    scenes=[dict(title="L’accusation", location_id="lieu", character_ids=["c1", "c2", "c3"],
        opening_state="Le portefeuille dépasse.", action="Victor accuse Lila ; elle indique sa poche.",
        dialogue=[dict(speaker_id="c2", text="Vous avez pris mon portefeuille !"),
                  dict(speaker_id="c1", text="Il dépasse de votre poche.")], ending_state="Victor regarde sa poche.")])


class InlineThread:
    def __init__(self, *, target, args, **_): self.target, self.args = target, args
    def start(self): self.target(*self.args)


class FakeAssets:
    def __init__(self): self.values = {}
    def create(self, content, *, media_type, source_run_id=None):
        asset = NS(asset_id=f"asset-{len(self.values) + 1}", media_type=media_type)
        self.values[asset.asset_id] = asset
        return asset
    def get(self, identity): return self.values[identity]


class FakeComposition:
    def __init__(self, prompt_lab):
        self.values, self.calls, self.configs = {}, [], {}
        self.fail_writer = False
        self.prompt_lab = prompt_lab
    def configure(self, identity, *args, **kwargs):
        self.configs[identity] = (args, kwargs)
        if identity not in self.values:
            documents = {s: NS(approved_revision_id=None, active_revision=None) for s in CompositionStage}
            self.values[identity] = NS(document=lambda stage: documents[stage])
    def get(self, identity): return self.values[identity]
    def stream_generate(self, identity, stage):
        writer = self.configs[identity][1]["writer_model_id"]
        self.calls.append((stage, writer if stage is CompositionStage.FINAL_PROMPT else self.prompt_lab.sessions[identity].model_id))
        if stage is CompositionStage.FINAL_PROMPT and self.fail_writer:
            self.fail_writer = False
            raise ValueError("Échec simulé du rédacteur")
        self.get(identity).document(stage).active_revision = NS(revision_id="accepted")
        yield NS(kind=StreamEventKind.COMPLETED)
    def approve(self, identity, stage): self.get(identity).document(stage).approved_revision_id = "accepted"


class FakePromptLab:
    def __init__(self): self.sessions = {}
    def create_session(self, **kwargs):
        identity = f"prompt-{len(self.sessions) + 1}"
        session = NS(session_id=identity, **kwargs)
        session.references = tuple(NS(reference_id=f"ref-{i}", **r.__dict__) if hasattr(r, "__dict__") else
            NS(reference_id=f"ref-{i}", asset_id=r.asset_id, role=r.role, label=r.label) for i, r in enumerate(kwargs["references"]))
        self.sessions[identity] = session
        return session
    def get_session(self, identity): return self.sessions[identity]


class FakeKrea:
    def __init__(self):
        self.values, self.calls, self.render_calls, self.preset_values = {}, [], [], {}
        self.projects = NS(get=lambda key: self.values[key])
        self.presets = NS(get=lambda key: self.preset_values[key])
        self.on_stream = None
    def create_project(self, **kwargs):
        project = NS(project_id=f"krea-{len(self.values) + 1}", attempts=[], current_prompt="", **kwargs)
        self.values[project.project_id] = project
        return project
    def stream_chat(self, identity, message, **kwargs):
        self.calls.append((message, kwargs))
        if self.on_stream: self.on_stream()
        self.values[identity].current_prompt = "Generated reference prompt"
        yield NS(error=None)
    def prepare_attempt(self, identity, *, prompt, settings, seed, enqueue):
        project = self.values[identity]
        self.render_calls.append((settings, seed, enqueue))
        project.attempts.append(NS(attempt_id=f"image-attempt-{len(self.render_calls)}", seed=seed or 123, output_asset_id=None))
        return project
    def start_render_worker(self): pass


class EpisodeTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.stories = StoryService(gateway=None, recipes=None, store=LocalStoryStore(root))
        story = self.stories.create(title="Test")
        story["document"]["scenario"] = deepcopy(SCENARIO)
        story["revisions"] = [dict(revision=1, document=deepcopy(story["document"]))]
        self.story = self.stories.store.save(story)
        self.assets, self.prompt = FakeAssets(), FakePromptLab()
        self.composition = FakeComposition(self.prompt)
        self.rendered = {}
        def create_render(session_id):
            project = NS(project_id=f"render-{session_id}", attempts=[])
            self.rendered[project.project_id] = project
            return project
        self.krea = FakeKrea()
        self.service = EpisodeService(stories=self.stories, store=LocalEpisodeStore(root),
            krea=self.krea, prompt_lab=self.prompt,
            composition=self.composition, render=NS(get_or_create_from_session=create_render,
                projects=NS(get=lambda key: self.rendered[key])), assets=self.assets)
        self.thread = patch("panelforge.application.episodes.Thread", InlineThread)
        self.thread.start(); self.addCleanup(self.thread.stop)

    def create(self):
        return self.service.create(self.story["project_id"], self.story["version"])

    def ready(self):
        value = self.create()
        for ref in value["references"]:
            value = self.service.import_image(value["episode_id"], ref["id"], ref["revision"], b"fake", "image/png", "reference.png")
        return value

    def test_validation_snapshots_without_launching_models_and_is_idempotent(self):
        first = self.create()
        self.assertEqual(self.create()["episode_id"], first["episode_id"])
        self.assertEqual(len(first["scenes"][0]["references"]), 4)
        self.assertEqual(self.composition.calls, [])
        self.assertEqual(self.prompt.sessions, {})
        self.story["document"]["scenario"]["title"] = "Autre version"
        self.stories.store.save(self.story)
        view = self.service.get(first["episode_id"])
        self.assertTrue(view["story_changed"])
        self.assertEqual(view["scenario"]["title"], "La poche")

    def test_reordering_keeps_named_dialogue_and_all_four_images(self):
        value = self.ready(); scene = value["scenes"][0]
        scene["references"].reverse()
        inputs = scene_inputs(value, scene)
        self.assertEqual(inputs["references"][0]["name"], "Épicerie")
        self.assertIn("<Picture 1> : Épicerie.", inputs["source_text"])
        self.assertIn("Victor : « Vous avez pris mon portefeuille ! »", inputs["source_text"])
        self.assertNotIn("Personnage fruit", inputs["source_text"])
        self.assertEqual(len(inputs["references"]), 4)

    def test_missing_images_block_preparation_before_any_call(self):
        value = self.create()
        with self.assertRaisesRegex(ValueError, "Choisissez une image"):
            self.service.prepare_scene(value["episode_id"], "scene-1", 1, "request-0001")
        self.assertFalse(self.prompt.sessions)

    def test_two_calls_use_separate_models_and_only_motion_repair(self):
        value = self.ready(); identity = value["episode_id"]
        ready = self.service.prepare_scene(identity, "scene-1", 1, "request-0001")
        scene = ready["scenes"][0]
        self.assertEqual(scene["preparations"][0]["status"], "ready")
        self.assertEqual(self.composition.calls, [(CompositionStage.BEAT_SHEET, scene["plan_model_id"]),
                                                (CompositionStage.FINAL_PROMPT, scene["writer_model_id"])])
        self.service.prepare_scene(identity, "scene-1", 1, "request-0001")
        self.assertEqual(len(self.composition.calls), 2, "duplicate request must not launch new model calls")
        setup = scene["render_setup"]
        self.assertEqual(setup["recipe"], {"id": "minimax-h3-bunny", "version": "0.1.3"})
        self.assertEqual([l["name"] for l in setup["video_loras"]["entries"]], ["minmax_nsfw/Motion_Repair.safetensors"])
        self.assertEqual(setup["settings"]["duration_seconds"], 10)

    def test_failed_writer_resumes_without_regenerating_accepted_plan(self):
        value = self.ready(); identity = value["episode_id"]
        self.composition.fail_writer = True
        failed = self.service.prepare_scene(identity, "scene-1", 1, "request-0001")
        self.assertEqual(failed["scenes"][0]["preparations"][0]["status"], "failed")
        succeeded = self.service.prepare_scene(identity, "scene-1", 1, "request-0002", resume=True)
        self.assertEqual(succeeded["scenes"][0]["preparations"][0]["status"], "ready")
        self.assertEqual([stage for stage, _ in self.composition.calls], [CompositionStage.BEAT_SHEET,
            CompositionStage.FINAL_PROMPT, CompositionStage.FINAL_PROMPT])
        self.assertEqual(len(self.prompt.sessions), 1)

    def test_new_reference_marks_prompt_stale_without_mutating_its_inputs(self):
        value = self.ready(); identity = value["episode_id"]
        value = self.service.prepare_scene(identity, "scene-1", 1, "request-0001")
        prior = deepcopy(value["scenes"][0]["preparations"][0])
        ref = value["references"][0]
        value = self.service.import_image(identity, ref["id"], ref["revision"], b"new", "image/png", "new.png")
        self.assertTrue(value["scenes"][0]["stale"])
        self.assertEqual(prior, value["scenes"][0]["preparations"][0])
        with self.assertRaises(ValueError):
            self.service.prepare_scene(identity, "scene-1", 1, "request-0002", resume=True)

    def test_stale_edits_and_cross_reference_image_selection_are_rejected(self):
        value = self.ready(); first, second = value["references"][:2]
        with self.assertRaises(EpisodeConflict):
            self.service.select_image(value["episode_id"], first["id"], 1, first["image_asset_id"])
        with self.assertRaises(ValueError):
            self.service.select_image(value["episode_id"], first["id"], first["revision"], second["image_asset_id"])

    def test_more_than_nine_is_not_silently_truncated(self):
        story = deepcopy(self.story)
        scenario = story["document"]["scenario"]
        scenario["characters"] = [dict(id=f"c{i}", name=f"Personnage {i}", description="Description") for i in range(1, 10)]
        scenario["scenes"][0]["character_ids"] = [c["id"] for c in scenario["characters"]]
        value = initial_episode(story, "episode-" + "a" * 32)
        self.assertEqual(len(value["scenes"][0]["references"]), 10)
        with self.assertRaisesRegex(ValueError, "neuf"):
            scene_inputs(value, value["scenes"][0], require_images=False)

    def test_disk_roundtrip_and_path_rejection(self):
        value = self.create()
        fresh = LocalEpisodeStore(self.temp.name)
        self.assertEqual(fresh.get(value["episode_id"])["scenario"], SCENARIO)
        with self.assertRaises(ValueError): fresh.get("../outside")

    def test_style_image_is_prompt_guidance_and_changes_leave_selected_assets_untouched(self):
        value = self.ready(); identity = value["episode_id"]; ref = value["references"][0]
        value = self.service.select_style_image(identity, 1, ref["id"])
        style_image = value["style_image"]["asset_id"]
        value = self.service.prepare_reference(identity, ref["id"], ref["revision"], "image-prompt-1", "")
        self.assertEqual(len(self.krea.calls), 1)
        message, kwargs = self.krea.calls[0]
        self.assertEqual(kwargs["guidance_asset_id"], style_image)
        self.assertIn("uniquement le STYLE VISUEL", message)
        self.assertIn("Ne copie ni le sujet", message)
        self.assertFalse(value["references"][0]["prompt_style_stale"])
        before = deepcopy(value["references"][0]["prompt_style"])
        changed = self.service.update_visual(identity, value["visual_revision"], "Animation pastel", value["image_defaults"])
        self.assertTrue(changed["references"][0]["prompt_style_stale"])
        self.assertEqual(changed["references"][0]["image_asset_id"], ref["image_asset_id"])
        self.assertEqual(changed["references"][0]["prompt_style"], before)
        with self.assertRaises(EpisodeConflict):
            self.service.select_style_image(identity, value["visual_revision"], None)

    def test_shared_defaults_override_only_inheriting_fiches_and_are_snapshotted_at_render(self):
        value = self.create(); identity = value["episode_id"]
        common = dict(model_id="common.safetensors", loras=[dict(name="style.safetensors", strength=0.45)],
                      sampling=asdict(Krea2AssistedSampling()))
        value = self.service.update_visual(identity, 1, "Style commun", common)
        custom = dict(model_id="custom.safetensors", aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN.value,
                      megapixels=2.1, loras=[], sampling=asdict(Krea2AssistedSampling()), seed=456)
        for ref in value["references"][:2]:
            value = self.service.update_reference(identity, ref["id"], ref["revision"], description=ref["description"],
                prompt="Manual image prompt", model_id=ref["model_id"], render_settings=custom,
                inherit_image_settings=ref["id"] == "character-1")
        first, second = value["references"][:2]
        self.assertEqual(first["effective_image_settings"]["model_id"], "common.safetensors")
        self.assertEqual(second["effective_image_settings"]["model_id"], "custom.safetensors")
        self.assertEqual(first["effective_image_settings"]["seed"], 456)
        settings = Krea2AssistedSettings("custom.safetensors", Krea2AspectRatio.PORTRAIT_WIDESCREEN, 2.1)
        value = self.service.render_reference(identity, first["id"], first["revision"], "render-request-1", settings, 456,
                                              expected_visual_revision=value["visual_revision"])
        actual = self.krea.render_calls[0][0]
        self.assertEqual(actual.model_name, "common.safetensors")
        self.assertEqual(actual.loras, (Krea2LoraSelection("style.safetensors", 0.45),))
        record = deepcopy(value["references"][0]["image_runs"][0])
        self.assertEqual(record["seed"], 456)
        value = self.service.update_visual(identity, value["visual_revision"], "Nouveau style", {**common, "loras": []})
        self.assertEqual(value["references"][0]["image_runs"][0], record)
        value = self.service.update_reference(identity, second["id"], second["revision"], description=second["description"],
            prompt=second["prompt"], model_id=second["model_id"], render_settings=custom, inherit_image_settings=True)
        self.assertEqual(value["references"][1]["effective_image_settings"]["model_id"], common["model_id"])

    def test_preset_revision_stays_frozen_until_explicitly_applied_and_prompt_is_bounded(self):
        value = self.ready(); identity = value["episode_id"]
        self.krea.preset_values["style-1"] = Krea2StylePreset("style-1", 1, "Pastel", "Pastel textures " * 2000,
            value["references"][0]["image_asset_id"], Krea2AssistedSettings("pastel.safetensors", Krea2AspectRatio.PORTRAIT_WIDESCREEN, 2.1),
            "source-project", "source-attempt", 123)
        value = self.service.apply_style_preset(identity, 1, "style-1")
        self.krea.preset_values["style-1"] = replace(self.krea.preset_values["style-1"], revision=2, name="Pastel v2")
        self.assertEqual(self.service.get(identity)["style_preset"]["revision"], 1)
        ref = value["references"][0]
        value = self.service.prepare_reference(identity, ref["id"], ref["revision"], "image-prompt-1", "")
        self.assertLessEqual(len(self.krea.calls[0][0]), 12000)
        self.assertIn("Extrait du prompt", self.krea.calls[0][0])
        self.assertEqual(value["references"][0]["prompt_style"]["preset"]["revision"], 1)
        value = self.service.apply_style_preset(identity, value["visual_revision"], "style-1")
        self.assertEqual(value["style_preset"]["revision"], 2)
        self.assertTrue(value["references"][0]["prompt_style_stale"])

    def test_style_edited_during_prompt_keeps_actual_input_provenance(self):
        value = self.create(); identity = value["episode_id"]; ref = value["references"][0]
        initial_style = style_context(value)
        self.krea.on_stream = lambda: self.service.update_visual(identity, 1, "Style changé pendant l’appel", value["image_defaults"])
        value = self.service.prepare_reference(identity, ref["id"], ref["revision"], "image-prompt-1", "")
        self.assertEqual(value["references"][0]["prompt_style"], initial_style)
        self.assertTrue(value["references"][0]["prompt_style_stale"])

    def test_retained_image_keeps_its_old_style_after_a_new_prompt_is_prepared(self):
        value = self.create(); identity = value["episode_id"]; ref = value["references"][0]
        value = self.service.prepare_reference(identity, ref["id"], ref["revision"], "image-prompt-1", "")
        ref = value["references"][0]
        settings = Krea2AssistedSettings("krea.safetensors", Krea2AspectRatio.PORTRAIT_WIDESCREEN, 2.1)
        value = self.service.render_reference(identity, ref["id"], ref["revision"], "image-render-1", settings)
        ref = value["references"][0]
        asset = self.assets.create(b"rendered", media_type="image/png")
        self.krea.values[ref["krea_project_id"]].attempts[-1].output_asset_id = asset.asset_id
        value = self.service.select_image(identity, ref["id"], ref["revision"], asset.asset_id)
        self.assertEqual(value["references"][0]["image_style_status"], "current")
        value = self.service.update_visual(identity, value["visual_revision"], "Autre direction", value["image_defaults"])
        ref = value["references"][0]
        value = self.service.prepare_reference(identity, ref["id"], ref["revision"], "image-prompt-2", "")
        self.assertFalse(value["references"][0]["prompt_style_stale"])
        self.assertEqual(value["references"][0]["image_style_status"], "outdated")
        self.assertEqual(value["references"][0]["image_asset_id"], asset.asset_id)

    def test_creative_axes_reach_ref2v_independently_and_invalidate_only_current_preparation(self):
        value = self.ready(); identity = value["episode_id"]
        axes = dict(scene_life=3, camera=0, extra_motion=2, dialogue=0)
        value = self.service.update_scene(identity, "scene-1", 1, creative_axes=axes, audacity=3)
        value = self.service.prepare_scene(identity, "scene-1", 2, "scene-prompt-1")
        previous = deepcopy(value["scenes"][0]["preparations"][0])
        intent = self.composition.configs[previous["session_id"]][1]["preparation_intent"]
        self.assertEqual(asdict(intent.creative_axes), axes)
        self.assertEqual(intent.creative_audacity, 3)
        self.assertEqual(intent.creative_freedom, 52)
        self.assertIn("Sans dialogue supplémentaire", intent.source_text)
        value = self.service.update_scene(identity, "scene-1", 2, creative_axes={**axes, "dialogue": 2})
        self.assertTrue(value["scenes"][0]["stale"])
        self.assertEqual(value["scenes"][0]["preparations"][0], previous)
        self.assertIn("Victor : « Vous avez pris mon portefeuille ! »", value["scenes"][0]["resolved_intention"])
        self.assertNotIn("Sans dialogue supplémentaire", value["scenes"][0]["resolved_intention"])

    def test_legacy_personal_settings_and_accepted_plan_keep_their_meaning(self):
        value = self.ready(); identity = value["episode_id"]
        value["references"][0].pop("inherit_image_settings")
        value["references"][0]["render_settings"] = {"model_id": "legacy.safetensors"}
        value["scenes"][0].pop("creative_axes")
        self.service.store.save(value)
        value = self.service.prepare_scene(identity, "scene-1", 1, "scene-prompt-1")
        self.assertFalse(value["scenes"][0]["stale"])
        self.assertNotIn("creative_axes", value["scenes"][0]["preparations"][0]["inputs"])
        self.assertFalse(value["references"][0]["inherit_image_settings"])
        self.assertEqual(value["references"][0]["effective_image_settings"]["model_id"], "legacy.safetensors")


if __name__ == "__main__":
    unittest.main()
