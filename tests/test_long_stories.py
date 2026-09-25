"""User-run V2 regressions. All model calls use an in-memory fake."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from time import monotonic, sleep
import unittest
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.stories import StoryService
from panelforge.application.episodes import EpisodeService
from panelforge.domain import long_stories as narrative
from panelforge.domain.story_contracts import wire_scene
from panelforge.domain.story_visual_states import CONTRACT_VERSION as VERSION
from panelforge.domain.episodes import initial_episode, scene_inputs
from panelforge.features.lab.stories_web import stories_router
from panelforge.infrastructure.long_story_recipes import LongStoryRecipes
from panelforge.infrastructure.storage.stories import LocalStoryStore, LocalStoryRecipeStore
from panelforge.infrastructure.storage.episodes import LocalEpisodeStore
from tests.test_stories import Gateway, SCENARIO, IDEAS

ROOT = Path(__file__).resolve().parents[1]
OPTIONS = dict(profile="suspense", delivery="serial", narration="visual", unit_count=2, ending_type="open")
CLEAR_REVIEW = {"reply": "Relecture terminée.", "review": {"summary": "La causalité et la révélation sont cohérentes.", "issues": []}}


def arc_response(project):
    result = narrative.outline_example(project)
    result["series_outline"]["characters"] = deepcopy(SCENARIO["scenario"]["characters"])
    result["series_outline"]["contract"]["must_keep"] = ["Conserver le secret jusqu’à la dernière unité."]
    result["series_outline"]["secrets"] = [{"id": "secret-1", "truth": "Le témoin a menti.", "known_by": [],
        "reveal_episode_id": f"episode-{project['long_options']['unit_count']}"}]
    result["series_outline"]["world_rules"] = [{"id": "rule-1", "rule": "Une preuve peut être vérifiée.", "limits": "Il faut voir son sceau."}]
    return result


def unit_response(project):
    target = project["document"]["selected_episode_id"]
    example_project = deepcopy(project)
    example_project["job"] = {"operation": "develop"}
    result = narrative.episode_example(example_project)
    result["scenario"] = deepcopy(SCENARIO["scenario"])
    result["scenario"]["scenes"][0]["dialogue"] = []
    result["episode_state"]["scene_events"][0]["reveals"] = [s["id"] for s in project["document"]["series_outline"]["secrets"]
                                                             if s["reveal_episode_id"] == target]
    return result


class LongStoriesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.gateway = Gateway()
        self.store = LocalStoryStore(self.temp.name)
        self.recipes = LocalStoryRecipeStore(self.temp.name, ROOT / "prompt_sources/story.brainrot/1.0.0")
        self.long_recipes = LongStoryRecipes(ROOT / "prompt_sources/story.long/2.0.0")
        self.service = StoryService(gateway=self.gateway, store=self.store, recipes=self.recipes, long_recipes=self.long_recipes)

    def create(self, **changes):
        values = dict(brief="Une preuve retournée révèle un secret à la fin, sans le résoudre.", narrative_format="long",
                      creation_mode="adapt", scene_count=4, clip_seconds=10, long_options=deepcopy(OPTIONS))
        values.update(changes)
        return self.service.create(**values)

    def write(self, project, operation, response, instruction=""):
        response = deepcopy(response)
        if "scenario" in response and "episode_state" in response:
            metadata = response["episode_state"].pop("scene_events")
            scenes = [wire_scene(scene, metadata[i]) for i, scene in enumerate(response["scenario"]["scenes"])]
            if operation == "repair_episode":
                response = dict(reply=response["reply"], base_hash=narrative.source_hash(project, project["document"]["selected_episode_id"]),
                    scene_edits=[dict(scene_index=i, scene=scene) for i, scene in enumerate(scenes)], episode_state=response["episode_state"])
            else:
                response["scenario"].pop("characters", None)
                response["scenario"]["scenes"] = scenes
        self.gateway.response = json.dumps(response, ensure_ascii=False)
        self.service.start(project["project_id"], operation=operation, instruction=instruction, model_id="local::fixture",
                           expected_version=project["version"], request_id=str(uuid4()))
        deadline = monotonic() + 5
        while monotonic() < deadline:
            with self.service._lock:
                active = project["project_id"] in self.service._active
            if not active:
                return self.service.get(project["project_id"])
            sleep(.005)
        self.fail("Le worker fictif n’a pas terminé.")

    def arc(self, **changes):
        project = self.create(**changes)
        project = self.write(project, "outline", arc_response(project))
        self.assertEqual(project["job"]["status"], "succeeded", project["job"].get("error"))
        return project

    def reviewed_arc(self, **changes):
        project = self.arc(**changes)
        project = self.write(project, "review_outline", CLEAR_REVIEW)
        self.assertTrue(project["long_status"]["outline_reviewed"], project["job"].get("error"))
        return project

    def written_unit(self, project=None):
        project = project or self.reviewed_arc()
        project = self.write(project, "develop", unit_response(project))
        self.assertEqual(project["job"]["status"], "succeeded", project["job"].get("error"))
        return project

    def test_normalization_rebuilds_current_diagnostics_without_accumulation(self):
        project = self.written_unit()
        scenario = project["document"]["scenario"]
        scenario["characters"].append(dict(id="c-observer", name="Observateur", description="Un passant."))
        scenario["scenes"][0]["action"] = "Observateur surveille discrètement la porte au fond du couloir."
        project["document"]["episode_scenarios"]["episode-1"] = deepcopy(scenario)
        normalized = self.service._normalize(project)
        expected = deepcopy(normalized["diagnostics"])
        mentions = [d for d in expected if d["code"] == "visible_cast_check"]
        self.assertEqual(len(mentions), 1)
        self.assertEqual(mentions[0]["level"], "warning")
        # Simulate persisted diagnostics from the old append-on-read behavior.
        normalized["diagnostics"].extend(deepcopy(mentions) * 6)
        normalized["diagnostics"].append(dict(code="language_residue", level="warning", message="Ancien texte"))
        for _ in range(5):
            normalized = self.service._normalize(normalized)
            self.assertEqual(normalized["diagnostics"], expected)
        normalized["document"]["scenario"]["scenes"][0]["action"] = "La porte se ferme doucement et laisse le couloir entièrement vide."
        normalized["document"]["episode_scenarios"]["episode-1"] = deepcopy(normalized["document"]["scenario"])
        normalized = self.service._normalize(normalized)
        self.assertFalse(any(d["code"] == "visible_cast_check" for d in normalized["diagnostics"]))

    def test_normalization_uses_selected_format_and_preserves_real_blockers(self):
        project = self.written_unit()
        scenario = project["document"]["scenario"]
        scenario["scenes"][0]["dialogue"] = [dict(speaker_id=scenario["characters"][0]["id"], text="bonjour " * 60)]
        project["document"]["episode_scenarios"]["episode-1"] = deepcopy(scenario)
        project["document"]["episode_formats"]["episode-1"] = dict(clip_seconds=5, scene_count=6)
        normalized = self.service._normalize(project)
        density = next(d for d in normalized["diagnostics"] if d["code"] == "dialogue_density")
        self.assertIn("pour 5 s", density["message"])
        self.assertTrue(any(d["code"] == "clip_load" and d["level"] == "blocking" for d in normalized["diagnostics"]))
        self.assertFalse(any(d["code"] == "scene_count" for d in normalized["diagnostics"]))

    def reviewed_unit(self, project=None):
        project = self.written_unit(project)
        project = self.write(project, "review_episode", CLEAR_REVIEW)
        self.assertTrue(project["long_status"]["fabrication_ready"], project["job"].get("error"))
        return project

    def open_unit(self, project, identity):
        return self.service.select_series_episode(project["project_id"], identity, project["version"],
                                                  scene_count=4, clip_seconds=10)

    def test_complete_serial_workflow_keeps_proofs_dialogues_and_industrial_snapshot(self):
        project = self.reviewed_unit()
        self.assertEqual(len(self.gateway.requests), 4)
        self.assertEqual(len(project["document"]["scenario"]["scenes"]), 1)  # Four is a ceiling.
        self.assertEqual(project["schema_version"], 2)
        episode = initial_episode(project, "episode-" + "c" * 32)
        self.assertEqual(episode["scenes"][0]["duration"], 10)
        self.assertIn("Information indispensable", episode["scenes"][0]["intention"])
        self.assertIn("Information indispensable", scene_inputs(episode, episode["scenes"][0], require_images=False)["source_text"])
        self.assertEqual(episode["scenario"]["scenes"][0]["dialogue"], [])
        project = self.open_unit(project, "episode-2")
        project = self.reviewed_unit(project)
        self.assertEqual(len(self.gateway.requests), 6)
        self.assertEqual(set(project["document"]["episode_scenarios"]), {"episode-1", "episode-2"})
        writer_context = json.loads(self.gateway.requests[-2].user_prompt)
        self.assertEqual(writer_context["canonical_history"][0]["unit_id"], "episode-1")
        self.assertIn("facts", writer_context["canonical_history"][0]["state"])
        self.assertEqual(writer_context["secrets"][0]["reveal_episode_id"], "episode-2")
        self.assertEqual(project["document"]["reviews"]["episode-2"]["call_id"], "call-6")

    def test_arc_review_and_chronological_canon_are_required_server_side(self):
        project = self.arc()
        with self.assertRaisesRegex(ValueError, "Relisez"):
            self.service.start(project["project_id"], operation="develop", instruction="", model_id="local::fixture",
                               expected_version=project["version"], request_id=str(uuid4()))
        project = self.write(project, "review_outline", CLEAR_REVIEW)
        project = self.open_unit(project, "episode-2")
        with self.assertRaisesRegex(ValueError, "précédentes"):
            self.service.start(project["project_id"], operation="develop", instruction="", model_id="local::fixture",
                               expected_version=project["version"], request_id=str(uuid4()))
        self.assertEqual(len(self.gateway.requests), 2)

    def test_fabrication_identity_and_staleness_use_adapted_source_for_its_own_unit(self):
        episodes = EpisodeService(stories=self.service, store=LocalEpisodeStore(self.temp.name), krea=None,
                                  prompt_lab=None, composition=None, render=None, assets=None)
        project = self.reviewed_unit()
        first = episodes.create(project["project_id"], project["version"])
        self.assertFalse(first["story_changed"])
        self.assertEqual(first["episode_id"], episodes.create(project["project_id"], project["version"])["episode_id"])
        project = self.open_unit(project, "episode-2")
        self.assertFalse(episodes.get(first["episode_id"])["story_changed"])
        project = self.open_unit(project, "episode-1")
        project = self.service.edit_scene(project["project_id"], 0, project["version"], {"action": "Le livreur ferme le colis sans le regarder."})
        self.assertTrue(episodes.get(first["episode_id"])["story_changed"])
        with self.assertRaisesRegex(ValueError, "relue"):
            episodes.create(project["project_id"], project["version"])
        self.assertEqual(len(episodes.store.list(project["project_id"])), 1)

    def test_delivery_metadata_survives_fabrication_without_a_fruit_line_quota(self):
        project = self.reviewed_arc()
        response = unit_response(project)
        lines = [{"speaker_id": "c1", "text": "Ce colis était fermé.", "delivery": "thought", "delivery_note": "inquiète"}]
        response["scenario"]["scenes"][0]["dialogue"] = lines
        project = self.write(project, "develop", response)
        project = self.write(project, "review_episode", CLEAR_REVIEW)
        episode = initial_episode(project, "episode-" + "e" * 32)
        self.assertEqual(episode["scenario"]["scenes"][0]["dialogue"], lines)
        self.assertIn("Ce colis était fermé.", scene_inputs(episode, episode["scenes"][0], require_images=False)["source_text"])

    def test_fabrication_is_rejected_until_episode_review_passes(self):
        project = self.written_unit()
        with self.assertRaisesRegex(ValueError, "relue"):
            initial_episode(project, "episode-" + "d" * 32)
        response = deepcopy(CLEAR_REVIEW)
        response["review"]["issues"] = [dict(severity="blocking", target_id="scene-1",
            problem="La preuve est déclarée sans être visible.", suggestion="Montre l’étiquette retournée.")]
        project = self.write(project, "review_episode", response)
        self.assertFalse(project["long_status"]["fabrication_ready"])
        with self.assertRaises(ValueError):
            narrative.fabrication_scenario(project)
        self.assertIn("Information indispensable", self.service.export(project["project_id"])["text"])

    def test_warning_review_is_current_and_allows_fabrication(self):
        project = self.written_unit()
        response = deepcopy(CLEAR_REVIEW)
        response["review"]["issues"] = [dict(severity="warning", target_id="scene-1",
            problem="La réaction pourrait respirer davantage.", suggestion="Ajouter une pause.")]
        project = self.write(project, "review_episode", response)
        self.assertTrue(project["long_status"]["fabrication_ready"])

    def test_editing_previous_episode_invalidates_its_review_and_the_next_provenance(self):
        project = self.reviewed_unit()
        project = self.open_unit(project, "episode-2")
        project = self.reviewed_unit(project)
        project = self.open_unit(project, "episode-1")
        project = self.service.edit_scene(project["project_id"], 0, project["version"], {"ending_state": "La reine conserve maintenant le colis."})
        self.assertFalse(project["long_status"]["fabrication_ready"])
        self.assertFalse(project["long_status"]["reviews"]["episode-1"]["current"])
        self.assertTrue(project["long_status"]["units"]["episode-2"]["stale"])
        self.assertIn("episode-2", project["document"]["episode_scenarios"])  # Never delete old work.
        project = self.write(project, "review_episode", CLEAR_REVIEW)
        project = self.open_unit(project, "episode-2")
        with self.assertRaisesRegex(ValueError, "réécrivez"):
            self.service.start(project["project_id"], operation="review_episode", instruction="", model_id="local::fixture",
                               expected_version=project["version"], request_id=str(uuid4()))
        project = self.reviewed_unit(project)
        self.assertTrue(project["long_status"]["fabrication_ready"])

    def test_future_reveal_rejected_without_overwriting_previous_scenario(self):
        project = self.written_unit()
        original = deepcopy(project["document"])
        response = unit_response(project)
        response["episode_state"]["scene_events"][0]["reveals"] = ["secret-1"]
        project = self.write(project, "revise", response, "Conserve le secret pour la fin.")
        self.assertEqual(project["job"]["status"], "failed")
        self.assertEqual(project["document"], original)
        self.assertIn("secret-1", project["job"]["draft"])

    def test_foreign_or_missing_events_and_unknown_cast_are_rejected(self):
        project = self.reviewed_arc()
        project["job"] = {"operation": "develop"}
        response = unit_response(project)
        for mutation in ("unknown_event", "empty_events", "unknown_cast"):
            bad = deepcopy(response)
            if mutation == "unknown_event":
                bad["episode_state"]["scene_events"][0]["event_ids"] = ["event-2"]
            elif mutation == "empty_events":
                bad["episode_state"]["scene_events"][0]["event_ids"] = []
            else:
                bad["scenario"]["characters"][0]["name"] = "Autre nom"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                narrative.parse(project, bad)

    def test_count_is_a_ceiling_and_action_estimate_is_bounded(self):
        project = self.reviewed_arc()
        project["job"] = {"operation": "develop"}
        response = unit_response(project)
        self.assertEqual(len(narrative.parse(project, response)[1]["scenario"]["scenes"]), 1)
        response["episode_state"]["scene_events"][0]["action_seconds"] = 11
        with self.assertRaisesRegex(ValueError, "action_seconds|estimation"):
            narrative.parse(project, response)
        response = unit_response(project)
        response["scenario"]["scenes"] *= 5
        with self.assertRaisesRegex(ValueError, "scenes|Budget"):
            narrative.parse(project, response)

    def test_budget_does_not_silently_change_after_architecture(self):
        project = self.arc()
        with self.assertRaisesRegex(ValueError, "budget V2"):
            self.service.select_series_episode(project["project_id"], "episode-1", project["version"], scene_count=2, clip_seconds=10)

    def test_bad_review_location_preserves_document_and_review_revalidation_is_bound_to_source(self):
        project = self.written_unit()
        invalid = deepcopy(CLEAR_REVIEW)
        invalid["review"]["issues"] = [dict(severity="blocking", target_id="scene-99", problem="Problème", suggestion="Corriger")]
        project = self.write(project, "review_episode", invalid)
        self.assertEqual(project["job"]["status"], "failed")
        project = self.service.edit_scene(project["project_id"], 0, project["version"], {"action": "Le livreur ouvre lentement le colis et retire la lettre."})
        with self.assertRaisesRegex(ValueError, "document a changé"):
            self.service.revalidate(project["project_id"], project["version"])

    def test_correction_is_one_call_and_requires_a_fresh_review(self):
        project = self.written_unit()
        response = deepcopy(CLEAR_REVIEW)
        response["review"]["issues"] = [dict(severity="blocking", target_id="scene-1", problem="La conséquence manque.", suggestion="Montre le refus.")]
        project = self.write(project, "review_episode", response)
        calls = len(self.gateway.requests)
        correction = unit_response(project)
        correction["scenario"]["scenes"][0]["action"] += " Le livreur refuse de rendre le colis."
        project = self.write(project, "repair_episode", correction)
        self.assertEqual(len(self.gateway.requests), calls + 1)
        self.assertFalse(project["long_status"]["fabrication_ready"])
        context = json.loads(self.gateway.requests[-1].user_prompt)
        self.assertEqual(context["review_to_address"]["issues"][0]["target_id"], "scene-1")
        self.assertEqual(project["job"]["editorial_fingerprint"], self.long_recipes.snapshot()["fingerprint"])
        self.assertEqual(project["revisions"][-1]["editorial_fingerprint"], project["job"]["editorial_fingerprint"])

    def test_arc_can_be_revised_after_a_scenario_and_marks_existing_units_stale(self):
        project = self.reviewed_unit()
        revision = arc_response(project)
        revision["series_outline"]["contract"]["stakes"] = "Le livreur risque désormais son logement."
        project = self.write(project, "revise_outline", revision, "Change uniquement l’enjeu.")
        self.assertEqual(project["job"]["status"], "succeeded")
        self.assertFalse(project["long_status"]["outline_reviewed"])
        self.assertTrue(project["long_status"]["units"]["episode-1"]["stale"])
        self.assertIsNotNone(project["document"]["scenario"])

    def test_discussion_does_not_modify_documents_or_approvals(self):
        project = self.reviewed_unit()
        previous = deepcopy(project["document"])
        project = self.write(project, "revise", {"reply": "Le secret reste réservé à la suite.", "discussion_only": True}, "Explique le choix sans modifier.")
        self.assertEqual(project["document"], previous)
        self.assertTrue(project["long_status"]["fabrication_ready"])

    def test_restore_recovers_a_coherent_document_snapshot(self):
        project = self.reviewed_unit()
        revision = project["revisions"][-1]["revision"]
        project = self.service.edit_scene(project["project_id"], 0, project["version"], {"ending_state": "Le colis brûle."})
        self.assertFalse(project["long_status"]["fabrication_ready"])
        project = self.service.restore(project["project_id"], revision, project["version"])
        self.assertTrue(project["long_status"]["fabrication_ready"])

    def test_variable_unit_count_and_all_profiles_have_versioned_prompts(self):
        for profile in narrative.PROFILES:
            with self.subTest(profile=profile):
                config = {**OPTIONS, "profile": profile, "delivery": "continuous", "unit_count": 5}
                project = self.arc(long_options=config)
                self.assertEqual(len(project["document"]["series_outline"]["episodes"]), 5)
                request = self.gateway.requests[-1]
                self.assertEqual(request.operation_id, f"story.long.outline@{VERSION}")
                self.assertIn(self.long_recipes.snapshot()["profiles"][profile], request.system_prompt)
                self.assertNotIn("UNE ET QUATRE", request.system_prompt)

    def test_outline_rejects_future_dependencies_and_changed_requested_ending(self):
        project = self.create()
        result = arc_response(project)["series_outline"]
        result["episodes"][0]["events"][0]["depends_on"] = ["event-2"]
        with self.assertRaises(ValueError):
            narrative.validate_outline(project, result)
        result = arc_response(project)["series_outline"]
        result["episodes"][-1]["ending_type"] = "resolution"
        with self.assertRaisesRegex(ValueError, "ending_type|fin globale"):
            narrative.validate_outline(project, result)

    def test_adaptation_can_keep_an_author_supplied_name_over_family_defaults(self):
        project = self.create(brief="La reine pêche se nomme Madame Rose. Conserver exactement ce nom.")
        result = arc_response(project)["series_outline"]
        result["characters"][0]["name"] = "Madame Rose"
        self.assertEqual(narrative.validate_outline(project, result)["characters"][0]["name"], "Madame Rose")

    def test_short_and_legacy_long_projects_stay_on_schema_one(self):
        for format in ("short", "long"):
            project = self.service.create(brief="Une reine.", narrative_format=format)
            self.assertEqual(project["schema_version"], 1)
            self.assertFalse(narrative.is_v2(project))
            with self.assertRaisesRegex(ValueError, "V2"):
                self.service.start(project["project_id"], operation="review_outline", instruction="", model_id="local::fixture",
                                   expected_version=project["version"], request_id=str(uuid4()))

    def test_optional_pitches_use_long_recipe_then_select_an_arc(self):
        project = self.create(creation_mode="ideas")
        project = self.write(project, "ideas", {"reply": "Une piste.", "concepts": deepcopy(IDEAS["concepts"][:1])})
        self.assertEqual(project["document"]["selected_id"], "concept-1")
        self.assertEqual(self.gateway.requests[-1].operation_id, f"story.long.ideas@{VERSION}")
        context = json.loads(self.gateway.requests[-1].user_prompt)
        self.assertNotIn("proposal_count", context)
        self.assertEqual(len(context["response_contract"]["concepts"]), 1)
        self.assertIn("une seule histoire", self.gateway.requests[-1].system_prompt)
        project = self.write(project, "outline", arc_response(project))
        self.assertEqual(project["job"]["status"], "succeeded")

    def test_api_validates_options_and_reopens_schema_two_without_persisting_status(self):
        app = FastAPI()
        app.include_router(stories_router(self.service))
        with TestClient(app) as client:
            body = dict(brief="Une histoire fournie.", narrative_format="long", creation_mode="adapt", long_options=OPTIONS)
            response = client.post("/api/stories/projects", json=body)
            self.assertEqual(response.status_code, 201, response.text)
            value = response.json()
            self.assertEqual(value["schema_version"], 2)
            self.assertIn("long_status", value)
            reopened = client.get(f"/api/stories/projects/{value['project_id']}").json()
            self.assertEqual(reopened["narrative_engine"], narrative.ENGINE)
            self.assertNotIn("long_status", self.store.get(value["project_id"]))
            body["long_options"] = {**OPTIONS, "unit_count": True}
            self.assertEqual(client.post("/api/stories/projects", json=body).status_code, 422)

    def test_api_accepts_twelfth_unit_but_writer_requires_all_earlier_units(self):
        project = self.arc(long_options={**OPTIONS, "unit_count": 12})
        project = self.write(project, "review_outline", CLEAR_REVIEW)
        app = FastAPI()
        app.include_router(stories_router(self.service))
        with TestClient(app) as client:
            response = client.post(f"/api/stories/projects/{project['project_id']}/series-episode",
                                   json=dict(episode_id="episode-12", scene_count=4, clip_seconds=10, expected_version=project["version"]))
            self.assertEqual(response.status_code, 200, response.text)
            opened = response.json()
            response = client.post(f"/api/stories/projects/{project['project_id']}/write",
                                   json=dict(operation="develop", model_id="local::fixture", request_id=str(uuid4()), expected_version=opened["version"]))
            self.assertEqual(response.status_code, 422, response.text)
            self.assertIn("précédentes", response.json()["detail"])
