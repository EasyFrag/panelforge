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
from panelforge.domain.stories import SILENT_CATS_RECIPE_ID, SILENT_CATS_RECIPE_VERSION
from panelforge.domain.krea2_sampling import Krea2AssistedSettings, Krea2AssistedSampling
from panelforge.domain.krea2_batch import Krea2AspectRatio, Krea2LoraSelection
from panelforge.domain.krea2_assisted_workflows import KREA2_FLUX_KLEIN_WORKFLOW
from panelforge.domain.krea2_assisted import Krea2AssistedAttemptStatus
from panelforge.domain.h3_render import H3RenderAttemptStatus
from panelforge.domain.production import ThermalPolicy
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


class EpisodeDialogueDeliveryTest(unittest.TestCase):
    def test_scene_inputs_preserve_structured_voice_over(self):
        story = dict(project_id="story-" + "a" * 32, clip_seconds=10,
                     document={"scenario": deepcopy(SCENARIO)}, revisions=[{"revision": 1}])
        story["document"]["scenario"]["scenes"][0]["dialogue"][0].update(
            dialogue_id="dialogue-1", delivery="voice_over", delivery_note="VOIX OFF")
        episode = initial_episode(story, "episode-" + "b" * 32)
        text = scene_inputs(episode, episode["scenes"][0], require_images=False)["source_text"]
        self.assertIn("Victor — VOIX OFF : « Vous avez pris mon portefeuille ! »", text)
        self.assertIn("Respecte exactement les modes de restitution indiqués", text)
        self.assertNotIn("Sans voix off", text)

    def test_scene_inputs_carry_the_story_language_to_the_ref2v_plan(self):
        scenario = deepcopy(SCENARIO)
        scenario["scenes"][0]["dialogue"][0]["text"] = "제 지갑을 가져갔어요!"
        scenario["scenes"][0]["dialogue"][1]["text"] = "주머니에서 보여요."
        story = dict(project_id="story-" + "a" * 32, clip_seconds=10, dialogue_language="Korean",
                     document={"scenario": scenario}, revisions=[{"revision": 1}])
        episode = initial_episode(story, "episode-" + "b" * 32)
        text = scene_inputs(episode, episode["scenes"][0], require_images=False)["source_text"]
        self.assertEqual(episode["dialogue_language"], "Korean")
        self.assertIn("Langue parlée obligatoire : 한국어 · Coréen", text)
        self.assertIn("spoken_languages correspondant à ces répliques contient exactement Korean", text)
        self.assertIn("Victor : « 제 지갑을 가져갔어요! »", text)

    def test_story_visual_transition_is_conditional_and_stronger_for_silent_cats(self):
        plain_story = dict(project_id="story-" + "a" * 32, clip_seconds=10,
            document={"scenario": deepcopy(SCENARIO)}, revisions=[{"revision": 1}])
        plain_episode = initial_episode(plain_story, "episode-" + "b" * 32)
        plain_text = scene_inputs(plain_episode, plain_episode["scenes"][0], require_images=False)["source_text"]
        self.assertNotIn("TRANSITION VISUELLE", plain_text)

        cats_story = deepcopy(plain_story)
        cats_story["recipe"] = {"id": SILENT_CATS_RECIPE_ID, "version": SILENT_CATS_RECIPE_VERSION}
        scene = cats_story["document"]["scenario"]["scenes"][0]
        scene.update(dialogue=[],
            relationship_state="Le chat roux tente de rassurer le chat blanc.",
            appearance_state="Le chat blanc porte une compresse et reste sous une couverture verte.",
            visual_transition={
                "before": "Le chat blanc est tassé sous la couverture, compresse sur le front.",
                "trigger": "Le chat roux lui montre une liasse de billets.",
                "visible_change": "Le chat blanc se redresse, écarquille les yeux et enlève la compresse.",
                "after": "Le chat blanc se tient debout, souriant et alerte, sans compresse.",
            })
        cats_episode = initial_episode(cats_story, "episode-" + "c" * 32)
        text = scene_inputs(cats_episode, cats_episode["scenes"][0], require_images=False)["source_text"]
        self.assertEqual(cats_episode["story_recipe"]["id"], SILENT_CATS_RECIPE_ID)
        self.assertIn("TRANSITION VISUELLE À MONTRER DANS CE CLIP", text)
        self.assertIn("Changement observable : Le chat blanc se redresse", text)
        self.assertIn("La transformation doit être comprise sans parole", text)


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
        project.attempts.append(NS(attempt_id=f"image-attempt-{len(self.render_calls)}", seed=seed or 123,
            output_asset_id=f"batch-output-{len(self.render_calls)}", status=Krea2AssistedAttemptStatus.SUCCEEDED, error=None))
        project.attempt = lambda attempt_id: next(value for value in project.attempts if value.attempt_id == attempt_id)
        return project
    def start_render_worker(self): pass


class FakeDlss:
    def __init__(self):
        self.calls = []
        self.jobs = []

    def list(self, owner=None, owner_id=None):
        return [job for job in self.jobs
                if (owner is None or job["snapshot"]["owner"] == owner)
                and (owner_id is None or job["snapshot"]["owner_id"] == owner_id)]

    def queue(self, *, owner, owner_id, attempt_id, settings, request_id):
        self.calls.append(dict(owner=owner, owner_id=owner_id, attempt_id=attempt_id,
                               settings=settings, request_id=request_id))
        job = {
            "job_id": f"dlss-{len(self.jobs) + 1}",
            "status": "queued",
            "error": None,
            "snapshot": {"owner": owner, "owner_id": owner_id, "root_attempt_id": attempt_id},
            "request": {"attempt_id": attempt_id, "settings": asdict(settings)},
        }
        self.jobs.append(job)
        return job

    def cancel_queued(self, job_id):
        job = next(value for value in self.jobs if value["job_id"] == job_id)
        if job["status"] == "queued" and not job.get("execution_id"):
            job["status"] = "cancelled"
        return job

    def retry(self, job_id):
        job = next(value for value in self.jobs if value["job_id"] == job_id)
        if job["status"] == "cancelled":
            job["status"] = "queued"
        return job


class EpisodeTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        recipes = NS(list=lambda: [dict(id="story.brainrot", version="1.0.0")])
        self.stories = StoryService(gateway=None, recipes=recipes, store=LocalStoryStore(root))
        story = self.stories.create(title="Test")
        story["document"]["scenario"] = deepcopy(SCENARIO)
        story["revisions"] = [dict(revision=1, document=deepcopy(story["document"]))]
        self.story = self.stories.store.save(story)
        self.assets, self.prompt = FakeAssets(), FakePromptLab()
        self.composition = FakeComposition(self.prompt)
        self.rendered = {}
        def create_render(session_id):
            project = NS(project_id=f"render-{session_id}", attempts=[], current_prompt="Generated video prompt")
            project.attempt = lambda attempt_id: next(value for value in project.attempts if value.attempt_id == attempt_id)
            self.rendered[project.project_id] = project
            return project
        def prepare_render(identity, **values):
            project = self.rendered[identity]
            attempt = NS(attempt_id=f"video-attempt-{len(project.attempts) + 1}", index=len(project.attempts) + 1,
                status=H3RenderAttemptStatus.CREATED, output_asset_id=None, error=None, dlss=None, **values)
            project.attempts.append(attempt)
            return project
        def queue_render(identity, attempt_id, **_options):
            self.rendered[identity].attempt(attempt_id).status = H3RenderAttemptStatus.QUEUED
        def execute_render(identity, attempt_id, **_options):
            attempt = self.rendered[identity].attempt(attempt_id)
            attempt.status = H3RenderAttemptStatus.SUCCEEDED
            attempt.output_asset_id = f"video-output-{attempt_id}"
        def cancel_render(identity, attempt_id):
            project = self.rendered[identity]
            project.attempt(attempt_id).status = H3RenderAttemptStatus.CANCELLED
            return project
        self.krea, self.dlss = FakeKrea(), FakeDlss()
        self.service = EpisodeService(stories=self.stories, store=LocalEpisodeStore(root),
            krea=self.krea, prompt_lab=self.prompt,
            composition=self.composition, render=NS(get_or_create_from_session=create_render,
                prepare_attempt=prepare_render, queue_attempt=queue_render, execute_attempt=execute_render,
                cancel_attempt=cancel_render,
                new_seed=lambda: 987654321,
                projects=NS(get=lambda key: self.rendered[key])), assets=self.assets, dlss=self.dlss)
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
        scene = first["scenes"][0]
        self.assertEqual(scene["audacity"], 3)
        self.assertEqual(scene["creative_axes"], {
            "scene_life": 3, "camera": 3, "extra_motion": 3, "dialogue": 1,
        })
        self.assertEqual(first["video_defaults"]["settings"]["megapixels"], 0.9)
        self.assertEqual(first["video_defaults"]["initial_megapixels"], 0.9)
        self.story["document"]["scenario"]["title"] = "Autre version"
        self.stories.store.save(self.story)
        view = self.service.get(first["episode_id"])
        self.assertTrue(view["story_changed"])
        self.assertEqual(view["scenario"]["title"], "La poche")

    def test_next_story_preselects_matching_character_images_only(self):
        parent = self.create()
        selected = self.service.import_image(
            parent["episode_id"], "character-1", parent["references"][0]["revision"],
            b"portrait", "image/png", "reine.png")
        inherited_asset = selected["references"][0]["image_asset_id"]

        child = self.stories.create(title="Suite", parent_story_id=self.story["project_id"])
        child_scenario = deepcopy(SCENARIO)
        child_scenario["characters"][0]["id"] = "heroine-reine"
        child_scenario["characters"][1]["id"] = "livreur-suite"
        child_scenario["characters"][2]["id"] = "temoin-suite"
        child_scenario["scenes"][0]["character_ids"] = ["heroine-reine", "livreur-suite", "temoin-suite"]
        child_scenario["scenes"][0]["dialogue"][0]["speaker_id"] = "livreur-suite"
        child_scenario["scenes"][0]["dialogue"][1]["speaker_id"] = "heroine-reine"
        child["document"]["scenario"] = child_scenario
        child["revisions"] = [dict(revision=1, document=deepcopy(child["document"]))]
        child = self.stories.store.save(child)

        episode = self.service.create(child["project_id"], child["version"])
        queen = next(reference for reference in episode["references"] if reference["name"] == "Lila")
        # In the fixture character-1 is Lila; the renamed source id proves that
        # continuation inheritance matches the stable name rather than a local c1 id.
        self.assertEqual(queen["image_asset_id"], inherited_asset)
        self.assertEqual(queen["images"][0]["label"], "Référence héritée · Lila")
        self.assertEqual(queen["inherited_image"]["episode_id"], parent["episode_id"])
        self.assertEqual(queen["prompt"], "")
        self.assertIsNone(queen["render_settings"])
        self.assertFalse(any(reference["image_asset_id"] for reference in episode["references"]
                             if reference["kind"] == "location"))

    def test_continuation_casting_walks_the_full_parent_chain(self):
        first = self.create()
        first = self.service.import_image(
            first["episode_id"], "character-1", first["references"][0]["revision"],
            b"portrait", "image/png", "lila.png")
        asset_id = first["references"][0]["image_asset_id"]

        middle = self.stories.create(title="Épisode intermédiaire",
                                     parent_story_id=self.story["project_id"])
        middle["document"]["scenario"] = deepcopy(SCENARIO)
        middle["revisions"] = [dict(revision=1, document=deepcopy(middle["document"]))]
        middle = self.stories.store.save(middle)
        # No Fabrication is created for the middle episode: the next one must
        # still find the casting selected in the older ancestor.
        latest = self.stories.create(title="Troisième épisode",
                                     parent_story_id=middle["project_id"])
        latest["document"]["scenario"] = deepcopy(SCENARIO)
        latest["revisions"] = [dict(revision=1, document=deepcopy(latest["document"]))]
        latest = self.stories.store.save(latest)

        inherited = self.service.create(latest["project_id"], latest["version"])
        self.assertEqual(inherited["references"][0]["image_asset_id"], asset_id)
        self.assertEqual(inherited["references"][0]["inherited_image"]["episode_id"], first["episode_id"])

    def test_next_episode_in_a_long_story_reuses_the_previous_casting(self):
        story = self.stories.store.get(self.story["project_id"])
        story["narrative_format"] = "long"
        story["document"].update(
            selected_episode_id="episode-1",
            series_outline={"episodes": [{"id": f"episode-{index}"} for index in range(1, 5)]},
            episode_scenarios={"episode-1": deepcopy(SCENARIO)},
            episode_formats={f"episode-{index}": {"scene_count": 1, "clip_seconds": 10}
                             for index in range(1, 5)},
        )
        story = self.stories.store.save(story)
        first = self.service.create(story["project_id"], story["version"])
        first = self.service.import_image(first["episode_id"], "character-1", 1,
                                          b"portrait", "image/png", "lila.png")
        asset_id = first["references"][0]["image_asset_id"]

        story = self.stories.store.get(story["project_id"])
        second_scenario = deepcopy(SCENARIO)
        second_scenario["title"] = "La poche · épisode 2"
        story["document"].update(selected_episode_id="episode-2", scenario=second_scenario)
        story["document"]["episode_scenarios"]["episode-2"] = deepcopy(second_scenario)
        story["revisions"].append(dict(revision=2, document=deepcopy(story["document"])))
        story = self.stories.store.save(story)
        second = self.service.create(story["project_id"], story["version"])
        self.assertNotEqual(second["episode_id"], first["episode_id"])
        self.assertEqual(second["series_episode_index"], 2)
        self.assertEqual(second["references"][0]["image_asset_id"], asset_id)
        self.assertEqual(second["references"][0]["inherited_image"]["episode_id"], first["episode_id"])

    def test_reference_batch_snapshots_two_profiles_and_stops_for_human_review(self):
        value = self.create(); identity = value["episode_id"]
        first = value["references"][0]
        value = self.service.import_image(identity, first["id"], first["revision"], b"old", "image/png", "old.png")
        character = Krea2AssistedSettings("characters.safetensors", Krea2AspectRatio.PORTRAIT_WIDESCREEN, 2.1,
            workflow=KREA2_FLUX_KLEIN_WORKFLOW)
        location = Krea2AssistedSettings("sets.safetensors", Krea2AspectRatio.WIDESCREEN, 2.1)
        profiles = {
            "character": dict(model_id="local::character-llm", settings=character, seed=11),
            "location": dict(model_id="local::set-llm", settings=location, seed=22),
        }
        value = self.service.start_reference_batch(identity, expected_visual_revision=value["visual_revision"],
            request_id="reference-batch-request", reference_ids=["character-1", "location-1"],
            profiles=profiles, thermal=ThermalPolicy(pause_when_unavailable=False, cooldown_seconds=0))
        batch = value["reference_batch"]
        self.assertEqual(batch["status"], "waiting_review")
        self.assertEqual([item["status"] for item in batch["items"]], ["ready_for_review", "ready_for_review"])
        self.assertEqual(batch["items"][0]["initial_asset_id"], value["references"][0]["image_asset_id"])
        self.assertEqual([call[0].model_name for call in self.krea.render_calls],
                         ["characters.safetensors", "sets.safetensors"])
        self.assertEqual(value["reference_profiles"]["character"]["render_settings"]["workflow"]["recipe_id"],
                         "krea2-flux-klein")
        self.assertEqual(value["references"][0]["model_id"], "local::character-llm")
        self.assertEqual(value["references"][-1]["model_id"], "local::set-llm")
        self.assertEqual(len(self.krea.calls), 2)

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
        self.assertEqual(scene["preparations"][0]["prompt_stages"], {"plan": "ready", "writer": "ready"})
        self.assertEqual(self.composition.calls, [(CompositionStage.BEAT_SHEET, scene["plan_model_id"]),
                                                (CompositionStage.FINAL_PROMPT, scene["writer_model_id"])])
        self.service.prepare_scene(identity, "scene-1", 1, "request-0001")
        self.assertEqual(len(self.composition.calls), 2, "duplicate request must not launch new model calls")
        setup = scene["render_setup"]
        self.assertEqual(setup["recipe"], {"id": "minimax-h3-bunny", "version": "0.1.3"})
        self.assertEqual([l["name"] for l in setup["video_loras"]["entries"]], ["minmax_nsfw/Motion_Repair.safetensors"])
        self.assertEqual(setup["settings"]["duration_seconds"], 10)

    def test_video_defaults_are_inherited_until_a_scene_is_customized(self):
        value = self.create(); identity = value["episode_id"]
        common = deepcopy(value["video_defaults"]); common["settings"]["megapixels"] = 1.4
        revisions = self.service.save_video_defaults(identity, value["video_revision"], common)
        value = self.service.get(identity); scene = value["scenes"][0]
        self.assertEqual(scene["effective_render_setup"]["settings"]["megapixels"], 1.4)
        self.assertEqual(scene["effective_render_setup"]["settings"]["duration_seconds"], scene["duration"])
        self.assertEqual(scene["render_revision"], revisions["render_revisions"][scene["id"]])

        value = self.service.set_scene_video_inheritance(identity, scene["id"], scene["render_revision"], False)
        scene = value["scenes"][0]; custom = deepcopy(scene["effective_render_setup"])
        custom["settings"]["megapixels"] = 2.2
        self.service.save_render_setup(identity, scene["id"], scene["render_revision"], custom)
        latest = self.service.get(identity); next_common = deepcopy(latest["video_defaults"])
        next_common["settings"]["megapixels"] = 0.8
        self.service.save_video_defaults(identity, latest["video_revision"], next_common)
        scene = self.service.get(identity)["scenes"][0]
        self.assertFalse(scene["inherit_video_settings"])
        self.assertEqual(scene["effective_render_setup"]["settings"]["megapixels"], 2.2)

    def test_prompt_status_waits_for_admission_and_ignores_a_local_prefix(self):
        value = self.ready(); identity = value["episode_id"]
        original = self.composition.stream_generate
        observed = []
        def stream(session, stage):
            stage_key = "plan" if stage is CompositionStage.BEAT_SHEET else "writer"
            for kind, phase in ((StreamEventKind.DELTA, "generating"), (StreamEventKind.STATUS, "queued"),
                                (StreamEventKind.STATUS, "starting"), (StreamEventKind.STATUS, "generating")):
                yield NS(kind=kind, phase=phase, text="Local prefix" if kind is StreamEventKind.DELTA else "Progress")
                saved = self.service.store.get(identity)
                observed.append(saved["scenes"][0]["preparations"][-1]["prompt_stages"][stage_key])
            yield from original(session, stage)
        self.composition.stream_generate = stream
        result = self.service.prepare_scene(identity, "scene-1", 1, "queued-prompt")
        self.assertEqual(observed, ["queued", "queued", "starting", "running"] * 2)
        self.assertEqual(result["scenes"][0]["preparations"][-1]["prompt_stages"], {"plan": "ready", "writer": "ready"})

    def test_failed_plan_does_not_leave_the_writer_in_the_queue(self):
        value = self.ready()
        def fail(_session, _stage):
            raise ValueError("Rejected plan")
        self.composition.stream_generate = fail
        result = self.service.prepare_scene(value["episode_id"], "scene-1", 1, "failed-plan")
        preparation = result["scenes"][0]["preparations"][-1]
        self.assertEqual(preparation["status"], "failed")
        self.assertEqual(preparation["prompt_stages"], {"plan": "failed", "writer": "pending"})

    def test_render_duration_survives_scene_saves_and_is_used_without_rewriting_prompt(self):
        value = self.ready(); identity = value["episode_id"]
        value = self.service.prepare_scene(identity, "scene-1", 1, "prepare-original")
        scene = value["scenes"][0]
        original_inputs = deepcopy(scene["preparations"][0]["inputs"])
        original_project = self.rendered[scene["preparations"][0]["render_project_id"]]
        setup = deepcopy(scene["effective_render_setup"])
        setup["settings"]["duration_seconds"] = 8
        self.service.save_render_setup(identity, scene["id"], scene["render_revision"], setup)
        value = self.service.update_scene(identity, scene["id"], scene["revision"], duration=10)
        scene = value["scenes"][0]
        self.assertEqual(scene["duration"], 10)
        self.assertFalse(scene["inherit_video_settings"])
        self.assertEqual(scene["effective_render_setup"]["settings"]["duration_seconds"], 8)
        self.assertEqual(scene["preparations"][0]["inputs"], original_inputs)
        self.assertFalse(scene["stale"])
        before_calls = list(self.composition.calls)
        result = self.service.start_video_chain(identity, expected_video_revision=value["video_revision"],
            request_id="custom-duration", scene_ids=[scene["id"]])
        self.assertEqual(result["video_chain"]["items"][0]["render_setup"]["settings"]["duration_seconds"], 8)
        self.assertEqual(self.composition.calls, before_calls)
        self.assertEqual(original_project.current_prompt, "Generated video prompt")
        self.assertEqual(original_project.attempts[-1].settings.duration_seconds, 8)

    def test_video_chain_prepares_prompt_renders_and_unlocks_manual_dlss(self):
        value = self.ready(); identity = value["episode_id"]
        result = self.service.start_video_chain(identity, expected_video_revision=value["video_revision"],
            request_id="video-chain-request", scene_ids=["scene-1"])
        self.assertEqual(result["video_chain"]["status"], "completed")
        self.assertEqual(result["video_chain"]["inter_video_cooldown_seconds"], 30)
        self.assertEqual(result["video_chain"]["items"][0]["status"], "succeeded")
        self.assertTrue(result["video_chain"]["prompts_complete"])
        self.assertTrue(result["scenes"][0]["dlss_ready"])
        self.assertEqual(result["scenes"][0]["video_status"], "succeeded")
        self.assertEqual(self.dlss.calls, [])

    def test_global_video_chain_queues_quick_dlss_once_after_video_success(self):
        value = self.ready(); identity = value["episode_id"]
        result = self.service.start_video_chain(
            identity,
            expected_video_revision=value["video_revision"],
            request_id="video-chain-with-dlss",
            scene_ids=["scene-1"],
            auto_dlss=True,
        )

        item = result["video_chain"]["items"][0]
        self.assertTrue(result["video_chain"]["auto_dlss"])
        self.assertEqual(item["status"], "succeeded")
        self.assertEqual(item["dlss_job_id"], "dlss-1")
        self.assertEqual(item["dlss_status"], "queued")
        self.assertEqual(len(self.dlss.calls), 1)
        call = self.dlss.calls[0]
        self.assertEqual(call["owner"], "ref2v")
        self.assertEqual(call["owner_id"], item["render_project_id"])
        self.assertEqual(call["attempt_id"], item["attempt_id"])
        self.assertEqual(asdict(call["settings"]), {
            "size": "1.724", "intensity": 0.2, "tone": 0, "structure": 0.2,
            "skin": 0, "style": "Natural", "detail": 1,
            "strict_neural": False, "interpolate": True, "hdr": False,
            "codec": "H.264 (NVIDIA NVENC)",
        })

        self.service._queue_chain_dlss(
            identity, result["video_chain"]["chain_id"], "scene-1",
            item["render_project_id"], item["attempt_id"],
        )
        self.assertEqual(len(self.dlss.calls), 1)

    def test_single_scene_chain_can_attach_to_an_already_running_prompt(self):
        value = self.ready(); identity = value["episode_id"]
        prepared = self.service.prepare_scene(identity, "scene-1", 1, "manual-prompt")
        stored = self.service.store.get(identity)
        stored_scene = stored["scenes"][0]
        stored_scene["preparations"][-1]["status"] = "running"
        stored_scene["job"] = {"request_id": "manual-prompt", "status": "running", "error": None}
        self.service.store.save(stored)
        self.service._active.add((identity, "scenes", "scene-1"))
        self.addCleanup(self.service._active.discard, (identity, "scenes", "scene-1"))

        with patch.object(self.service, "_video_chain_worker") as worker:
            armed = self.service.start_video_chain(
                identity, expected_video_revision=stored["video_revision"],
                request_id="armed-render", scene_ids=["scene-1"],
            )
        self.assertEqual(armed["video_chain"]["phase"], "Prompt en cours · rendu armé")
        self.assertEqual(armed["video_chain"]["items"][0]["status"], "prompting")
        worker.assert_called_once()

        finished_scene = deepcopy(prepared["scenes"][0])
        finished_scene["preparations"][-1]["status"] = "ready"
        with patch.object(self.service, "_wait_scene_job",
                          return_value=(finished_scene, {"status": "succeeded"})), \
             patch.object(self.service, "prepare_scene") as launch:
            result = self.service._prepare_chain_prompt(
                identity, armed["video_chain"]["chain_id"], "scene-1",
            )
        self.assertEqual(result["status"], "ready")
        launch.assert_not_called()

    def test_video_chain_resume_retries_only_the_rejected_stage_with_a_new_request(self):
        value = self.ready(); identity = value["episode_id"]
        self.composition.fail_writer = True
        failed = self.service.start_video_chain(identity, expected_video_revision=value["video_revision"],
            request_id="video-chain-retry", scene_ids=["scene-1"])

        self.assertEqual(failed["video_chain"]["status"], "completed_with_errors")
        self.assertEqual(failed["video_chain"]["items"][0]["status"], "prompt_failed")
        self.assertEqual(failed["scenes"][0]["preparations"][0]["prompt_stages"],
                         {"plan": "ready", "writer": "failed"})
        self.assertEqual([stage for stage, _model in self.composition.calls],
                         [CompositionStage.BEAT_SHEET, CompositionStage.FINAL_PROMPT])

        resumed = self.service.resume_video_chain(identity, failed["video_chain"]["chain_id"])

        self.assertEqual(resumed["video_chain"]["status"], "completed")
        self.assertEqual(resumed["video_chain"]["items"][0]["status"], "succeeded")
        self.assertEqual(resumed["scenes"][0]["preparations"][0]["prompt_stages"],
                         {"plan": "ready", "writer": "ready"})
        self.assertEqual(len(resumed["scenes"][0]["preparations"]), 1)
        self.assertEqual([stage for stage, _model in self.composition.calls],
                         [CompositionStage.BEAT_SHEET, CompositionStage.FINAL_PROMPT,
                          CompositionStage.FINAL_PROMPT])

    def test_manual_prompt_and_video_retry_reconcile_the_failed_chain_card(self):
        value = self.ready(); identity = value["episode_id"]
        self.composition.fail_writer = True
        failed = self.service.start_video_chain(identity, expected_video_revision=value["video_revision"],
            request_id="video-chain-manual", scene_ids=["scene-1"])
        scene = failed["scenes"][0]

        corrected = self.service.prepare_scene(
            identity, scene["id"], scene["revision"], "manual-prompt-retry", resume=True,
        )
        item = corrected["video_chain"]["items"][0]
        self.assertEqual(item["status"], "prompt_ready")
        self.assertIsNone(item["error"])
        self.assertEqual(item["preparation_id"], corrected["scenes"][0]["preparations"][-1]["id"])

        project_id = corrected["scenes"][0]["preparations"][-1]["render_project_id"]
        project = self.service.render.prepare_attempt(project_id, manual=True)
        attempt = project.attempts[-1]
        attempt.status = H3RenderAttemptStatus.RUNNING
        running = self.service.get(identity)
        self.assertEqual(running["video_chain"]["items"][0]["status"], "rendering")
        self.assertEqual(running["video_chain"]["phase"], "Relance manuelle en cours")

        attempt.status = H3RenderAttemptStatus.SUCCEEDED
        attempt.output_asset_id = "manual-video-output"
        completed = self.service.get(identity)
        self.assertEqual(completed["video_chain"]["status"], "completed")
        self.assertEqual(completed["video_chain"]["items"][0]["status"], "succeeded")
        self.assertTrue(completed["scenes"][0]["dlss_ready"])

    def test_video_chain_delegates_inter_video_rest_to_the_global_remote_lane(self):
        second = deepcopy(self.story["document"]["scenario"]["scenes"][0])
        second["title"] = "Le dénouement"
        self.story["document"]["scenario"]["scenes"].append(second)
        self.story = self.stories.store.save(self.story)
        value = self.ready(); identity = value["episode_id"]
        original = self.service.render.execute_attempt
        calls = []

        def execute(project_id, attempt_id, **options):
            calls.append(options)
            original(project_id, attempt_id)

        self.service.render.execute_attempt = execute
        self.service.work_coordinator = NS(
            settings=NS(remote_video_cooldown_seconds=17),
            public_status=lambda: {},
        )
        result = self.service.start_video_chain(
            identity,
            expected_video_revision=value["video_revision"],
            request_id="video-chain-cooldown",
            scene_ids=["scene-1", "scene-2"],
        )

        self.assertEqual(result["video_chain"]["inter_video_cooldown_seconds"], 17)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all("post_cooldown_seconds" not in call for call in calls))
        self.assertTrue(all(call["operation_label"].startswith("H3 / REF2V") for call in calls))
        self.assertIsNone(result["video_chain"]["cooldown_until"])
        self.assertEqual(result["video_chain"]["status"], "completed")

    def test_video_chain_prepares_every_prompt_without_waiting_for_prior_videos(self):
        for index in range(2, 4):
            scene = deepcopy(self.story["document"]["scenario"]["scenes"][0])
            scene["title"] = f"Scène {index}"
            self.story["document"]["scenario"]["scenes"].append(scene)
        self.story = self.stories.store.save(self.story)
        value = self.ready()
        identity = value["episode_id"]
        events = []

        def prepare(_identity, _chain_id, scene_id):
            events.append(f"prompt:{scene_id}")
            return {"id": f"preparation-{scene_id}", "render_project_id": f"render-{scene_id}"}

        def start(_identity, _chain_id, scene_id, _preparation, _setup, **_options):
            events.append(f"video:{scene_id}")
            return f"render-{scene_id}", f"attempt-{scene_id}", scene_id

        def wait(_identity, current_chain_id, active):
            scene_id = active[2]
            events.append(f"wait:{scene_id}")
            self.service._video_chain_change(identity, current_chain_id, lambda _value, chain:
                self.service._video_item(chain, scene_id).update(
                    status="succeeded", phase="Vidéo terminée"))

        with patch.object(self.service, "_prepare_chain_prompt", side_effect=prepare), \
             patch.object(self.service, "_start_chain_video", side_effect=start), \
             patch.object(self.service, "_wait_chain_video", side_effect=wait):
            result = self.service.start_video_chain(
                identity,
                expected_video_revision=value["video_revision"],
                request_id="video-chain-overlap",
                scene_ids=["scene-1", "scene-2", "scene-3"],
            )

        self.assertEqual(events, [
            "prompt:scene-1", "video:scene-1",
            "prompt:scene-2", "video:scene-2",
            "prompt:scene-3", "video:scene-3",
            "wait:scene-1", "wait:scene-2", "wait:scene-3",
        ])
        self.assertEqual(result["video_chain"]["status"], "completed")

    def test_pause_after_active_cancels_only_queued_chain_work_and_resume_keeps_prompts(self):
        value = self.ready(); identity = value["episode_id"]
        prepared = self.service.prepare_scene(identity, "scene-1", 1, "prepare-before-pause")
        preparation = prepared["scenes"][0]["preparations"][-1]
        project = self.service.render.prepare_attempt(preparation["render_project_id"], manual=True)
        attempt = project.attempts[-1]
        self.service.render.queue_attempt(project.project_id, attempt.attempt_id)
        dlss = self.dlss.queue(owner="ref2v", owner_id=project.project_id,
            attempt_id=attempt.attempt_id, settings=self.service._automatic_video_dlss_settings(),
            request_id="queued-dlss-before-pause")
        with patch.object(self.service, "_video_chain_worker"):
            chain_view = self.service.start_video_chain(identity,
                expected_video_revision=prepared["video_revision"], request_id="pause-chain-request",
                scene_ids=["scene-1"], auto_dlss=True)
        chain_id = chain_view["video_chain"]["chain_id"]
        stored = self.service.store.get(identity)
        stored["video_chain"]["items"][0].update(status="rendering", phase="Rendu vidéo en cours",
            preparation_id=preparation["id"], render_project_id=project.project_id,
            attempt_id=attempt.attempt_id, dlss_job_id=dlss["job_id"], dlss_status="queued")
        self.service.store.save(stored)

        paused = self.service.pause_video_chain(identity, chain_id, mode="after_active")
        item = paused["video_chain"]["items"][0]
        self.assertEqual(paused["video_chain"]["phase"], "Pause après les traitements actifs")
        self.assertEqual(project.attempt(attempt.attempt_id).status, H3RenderAttemptStatus.CANCELLED)
        self.assertEqual(item["status"], "prompt_ready")
        self.assertIsNone(item["attempt_id"])
        self.assertEqual(item["dlss_status"], "cancelled")
        self.assertTrue(item["dlss_resume_pending"])
        self.assertEqual(paused["scenes"][0]["preparations"][-1]["prompt_stages"],
                         {"plan": "ready", "writer": "ready"})

    def test_pause_after_queue_keeps_existing_reservations(self):
        value = self.ready(); identity = value["episode_id"]
        with patch.object(self.service, "_video_chain_worker"):
            chain_view = self.service.start_video_chain(identity,
                expected_video_revision=value["video_revision"], request_id="drain-chain-request",
                scene_ids=["scene-1"])
        chain_id = chain_view["video_chain"]["chain_id"]
        paused = self.service.pause_video_chain(identity, chain_id, mode="after_queue")
        self.assertEqual(paused["video_chain"]["phase"], "Pause après la file réservée")
        self.assertEqual(paused["video_chain"]["items"][0]["status"], "pending")

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
                      sampling=asdict(Krea2AssistedSampling()), workflow=asdict(KREA2_FLUX_KLEIN_WORKFLOW))
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
        self.assertEqual(actual.workflow, KREA2_FLUX_KLEIN_WORKFLOW)
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
