"""User-run story regressions. Fake LLM only; no rendering, model server or GPU."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from threading import Event
from time import monotonic, sleep
import unittest
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, ModelDescriptor, StreamEventKind, StreamPhase
from panelforge.application.stories import StoryService, StoryConflict
from panelforge.domain.stories import RECIPE_ID, RECIPE_VERSION, decode_story_json, validate_scenario, scene_intention
from panelforge.features.lab.stories_web import stories_router
from panelforge.features.lab.prompt_recipes_web import prompt_recipes_router
from panelforge.infrastructure.storage.stories import LocalStoryStore, LocalStoryRecipeStore
from panelforge.infrastructure.storage.prompt_recipes import LocalPromptRecipeStore
from panelforge.infrastructure.storage.local import _atomic_write, _json_bytes

ROOT = Path(__file__).resolve().parents[1]
IDEAS = {"reply": "Choisis une piste.", "concepts": [dict(title=f"Le mensonge {i}", hook=f"Une reine cache la preuve {i}.",
    protagonist="Un livreur citron", antagonist="Une reine menteuse", escalation="Elle accuse son livreur.",
    reveal="Les étiquettes désignent la reine.", ending="Le livreur récupère son colis.") for i in range(3)]}
SCENARIO = {"reply": "Voici le scénario.", "scenario": {"title": "La reine et les cadeaux", "logline": "Une reine est démasquée par ses cadeaux volés.",
    "characters": [{"id": "c1", "name": "Reine", "description": "Pêche anthropomorphe en robe rouge."},
                   {"id": "c2", "name": "Livreur", "description": "Citron en veste bleue."}],
    "locations": [{"id": "l1", "name": "Place", "description": "Comptoir de cadeaux sous un arbre."}],
    "scenes": [{"title": "Le colis", "location_id": "l1", "character_ids": ["c1", "c2"],
        "opening_state": "Le colis fermé porte une étiquette.", "action": "La reine montre le livreur. Il retourne le colis et découvre le nom.",
        "dialogue": [{"speaker_id": "c1", "text": "C’est lui !"}, {"speaker_id": "c2", "text": "Madame… votre nom est ici."}],
        "ending_state": "L’étiquette désigne la reine."}]}}


class Gateway:
    def __init__(self):
        self.requests = []
        self.response = json.dumps(IDEAS)
        self.entered = Event()
        self.release = Event()
        self.release.set()
        self.truncated = False

    def list_models(self):
        return [ModelDescriptor("local::fixture", "local", "Modèle de test")]

    def stream(self, request):
        self.requests.append(request)
        raw = self.response
        self.entered.set()
        if not self.release.wait(5):
            raise TimeoutError("Test gateway timed out")
        yield CompletionStreamEvent(StreamEventKind.DELTA, StreamPhase.GENERATING, text=raw)
        yield CompletionStreamEvent(StreamEventKind.TRUNCATED if self.truncated else StreamEventKind.COMPLETED,
            StreamPhase.COMPLETED, result=CompletionResult(request.model_id, raw, call_id=f"call-{len(self.requests)}"))


class StoriesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.gateway = Gateway()
        self.store = LocalStoryStore(self.temp.name)
        self.recipes = LocalStoryRecipeStore(self.temp.name, ROOT / "prompt_sources/story.brainrot/1.0.0")
        self.service = StoryService(gateway=self.gateway, store=self.store, recipes=self.recipes)

    def finish(self, project):
        deadline = monotonic() + 5
        while monotonic() < deadline:
            with self.service._lock:
                active = project["project_id"] in self.service._active
            if not active:
                return self.service.get(project["project_id"])
            sleep(.005)
        self.fail("Le worker de test ne s’est pas terminé.")

    def write(self, project, operation, instruction="", request_id=None):
        self.service.start(project["project_id"], operation=operation, instruction=instruction, model_id="local::fixture",
            expected_version=project["version"], request_id=request_id or str(uuid4()))
        return self.finish(project)

    def concepts(self):
        return self.write(self.service.create(brief="Une reine odieuse."), "ideas")

    def scenario(self):
        p = self.concepts()
        p = self.service.select(p["project_id"], "concept-2", p["version"])
        self.gateway.response = json.dumps(SCENARIO)
        return self.write(p, "develop")

    def test_two_calls_selection_persistence_and_exact_dialogue_export(self):
        p = self.scenario()
        self.assertEqual(len(self.gateway.requests), 2)
        self.assertEqual(p["job"]["status"], "succeeded")
        context = json.loads(self.gateway.requests[1].user_prompt)
        self.assertEqual(context["current_document"]["selected_id"], "concept-2")
        self.assertEqual(context["clip_seconds"], 10)
        self.assertFalse(self.gateway.requests[1].images)
        reopened = LocalStoryStore(self.temp.name).get(p["project_id"])
        self.assertEqual(reopened["document"], p["document"])
        export = self.service.export(p["project_id"])
        self.assertIn("Durée cible : 10 secondes.", export["intentions"][0])
        self.assertIn("Livreur : « Madame… votre nom est ici. »", export["intentions"][0])
        self.assertNotIn("Durée cible", self.service.export(p["project_id"], include_duration=False)["intentions"][0])
        self.assertNotIn("Picture", export["text"])

    def test_invalid_response_and_truncation_preserve_previous_scenario_and_raw_draft(self):
        p = self.scenario()
        original = deepcopy(p["document"])
        for raw, truncated in [('Pas un JSON', False), (json.dumps(SCENARIO), True)]:
            self.gateway.response, self.gateway.truncated = raw, truncated
            p = self.write(p, "revise", "Rends la reine plus odieuse.")
            self.assertEqual(p["job"]["status"], "failed")
            self.assertEqual(p["document"], original)
            self.assertEqual(p["job"]["draft"], raw)

    def test_trailing_commas_are_accepted_without_an_extra_llm_call(self):
        self.gateway.response = '{"reply":"Voici les pistes.","concepts":[' + ",".join(
            json.dumps(c)[:-1] + ",}" for c in IDEAS["concepts"]) + ",],}"
        p = self.concepts()
        self.assertEqual(p["job"]["status"], "succeeded")
        self.assertEqual(len(p["document"]["concepts"]), 3)
        self.assertEqual(len(self.gateway.requests), 1)

    def test_trailing_comma_decode_preserves_strings_and_rejects_other_damage(self):
        value = {"text": 'Littéraux ,} et ,] et "guillemets" et antislash \\', "nested": [1, {"ok": True}]}
        raw = json.dumps(value, ensure_ascii=False)
        self.assertEqual(decode_story_json(raw), value)
        self.assertEqual(decode_story_json(raw[:-1] + ",}"), value)
        for broken in ('{"text":"inachevé', '{"a":1', '{,}', '[,]', '[1,,]', '{"a":,}',
                       '{"a":1 "b":2}', '{"a":1} commentaire', "{'a':1}"):
            with self.subTest(broken=broken), self.assertRaises(json.JSONDecodeError):
                decode_story_json(broken)

    def test_discussion_does_not_replace_document_and_restore_appends_revision(self):
        p = self.scenario()
        self.gateway.response = json.dumps({"reply": "On pourrait renforcer sa cupidité.", "discussion_only": True})
        count, doc = len(p["revisions"]), deepcopy(p["document"])
        p = self.write(p, "revise", "Que penses-tu de la fin ?")
        self.assertEqual(len(p["revisions"]), count)
        self.assertEqual(p["document"], doc)
        restored = self.service.restore(p["project_id"], 1, p["version"])
        self.assertIsNone(restored["document"]["scenario"])
        self.assertEqual(len(restored["revisions"]), count + 1)
        self.assertEqual(restored["revisions"][count-1]["document"], doc)
        with self.assertRaises(StoryConflict):
            self.service.restore(p["project_id"], 1, p["version"])

    def test_duplicate_start_cancel_and_restart_recovery(self):
        p = self.service.create()
        self.gateway.release.clear()
        request_id = str(uuid4())
        try:
            started = self.service.start(p["project_id"], operation="ideas", instruction="", model_id="local::fixture",
                expected_version=p["version"], request_id=request_id)
            self.assertTrue(self.gateway.entered.wait(2))
            same = self.service.start(p["project_id"], operation="ideas", instruction="", model_id="local::fixture",
                expected_version=p["version"], request_id=request_id)
            self.assertEqual(same["job"]["request_id"], started["job"]["request_id"])
            with self.assertRaises(StoryConflict):
                self.service.start(p["project_id"], operation="ideas", instruction="", model_id="local::fixture",
                    expected_version=same["version"], request_id=str(uuid4()))
            self.service.cancel(p["project_id"])
        finally:
            self.gateway.release.set()
            done = self.finish(p)
        self.assertEqual(done["job"]["status"], "cancelled")
        self.assertEqual(len(self.gateway.requests), 1)
        self.assertFalse(done["document"]["concepts"])
        done["job"]["status"] = "running"
        self.store.save(done)
        restarted = StoryService(gateway=self.gateway, store=self.store, recipes=self.recipes)
        self.assertEqual(restarted.get(p["project_id"])["job"]["status"], "interrupted")

    def test_editorial_revision_applies_next_call_without_changing_old_trace_context(self):
        p = self.concepts()
        old = self.recipes.get(RECIPE_ID, RECIPE_VERSION)
        fields = {**old["fields"], "revision.system": "Nouvelle consigne pour discuter."}
        updated = self.recipes.save(RECIPE_ID, RECIPE_VERSION, base_revision=old["revision"], expected_active=old["active"], fields=fields)
        self.gateway.response = json.dumps({"reply": "D’accord.", "discussion_only": True})
        p = self.write(p, "revise", "Discutons.")
        self.assertEqual(self.gateway.requests[-1].system_prompt, fields["revision.system"])
        self.assertEqual(self.gateway.requests[0].trace_context["recipe_revision"], old["revision"])
        self.assertEqual(p["job"]["recipe_revision"], updated["revision"])
        self.recipes.activate(RECIPE_ID, RECIPE_VERSION, old["revision"], updated["active"])
        self.assertEqual(self.recipes.get(RECIPE_ID, RECIPE_VERSION)["fields"], old["fields"])

    def test_scenario_revision_accepts_valid_document_envelope_without_losing_scenario(self):
        p = self.scenario()
        response = deepcopy(SCENARIO)
        response["scenario"]["characters"][0]["description"] = "Fraise adulte en robe rouge, reine odieuse."
        response["concepts"] = deepcopy(p["document"]["concepts"])
        response["concepts"][1]["antagonist"] = "La reine fraise"
        response["selected_id"] = "concept-2"
        self.gateway.response = json.dumps(response)
        p = self.write(p, "revise", "Les personnages sont des fruits.")
        self.assertEqual(p["job"]["status"], "succeeded")
        self.assertEqual(p["document"]["scenario"]["characters"][0]["description"], response["scenario"]["characters"][0]["description"])
        self.assertEqual(p["document"]["concepts"][1]["antagonist"], "La reine fraise")
        self.assertEqual(p["document"]["selected_id"], "concept-2")
        preserved = deepcopy(p["document"])
        for changes in ({"selected_id": "concept-3"}, {"concepts": []}, {"extra_unknown": "ignore validation"}):
            self.gateway.response = json.dumps({**response, **changes})
            p = self.write(p, "revise", "Corrige cette histoire.")
            self.assertEqual(p["job"]["status"], "failed")
            self.assertEqual(p["document"], preserved)

    def test_new_pitches_keep_author_feedback_without_reusing_previous_generated_scenario(self):
        p = self.scenario()
        p["turns"].append(dict(role="assistant", text="Ancienne mauvaise direction : jargon_seum_fixture."))
        p["turns"].append(dict(role="user", text="Des fruits adultes, une vraie trahison."))
        p = self.store.save(p)
        self.gateway.response = json.dumps(IDEAS)
        self.write(p, "ideas")
        context = json.loads(self.gateway.requests[-1].user_prompt)
        self.assertIsNone(context["current_document"]["scenario"])
        self.assertFalse(context["current_document"]["concepts"])
        self.assertNotIn("jargon_seum_fixture", self.gateway.requests[-1].user_prompt)
        self.assertIn("Des fruits adultes, une vraie trahison.", self.gateway.requests[-1].user_prompt)
        self.assertTrue(context["recent_concepts_to_avoid"])

    def test_factory_editorial_upgrade_keeps_r1_r2_and_respects_rollback(self):
        # Reconstruct the untouched recipe installed by the first release.
        directory, _ = LocalPromptRecipeStore._ensure(self.recipes, RECIPE_ID, RECIPE_VERSION)
        initial = self.recipes._read_revision(directory, 1)["fields"]
        upgraded = self.recipes.get(RECIPE_ID, RECIPE_VERSION)
        self.assertEqual(upgraded["active"], 3)
        self.assertEqual(self.recipes.get(RECIPE_ID, RECIPE_VERSION, 1)["fields"], initial)
        for revision, previous in ((2, 3), (1, 2)):
            self.recipes.activate(RECIPE_ID, RECIPE_VERSION, revision, previous)
            restarted = LocalStoryRecipeStore(self.temp.name, ROOT / "prompt_sources/story.brainrot/1.0.0")
            self.assertEqual(restarted.get(RECIPE_ID, RECIPE_VERSION)["active"], revision)
            self.assertEqual(len(restarted.history(RECIPE_ID, RECIPE_VERSION)), 3)

    def install_factory_r2(self):
        # An existing workspace from the r2 release, before r3 is loaded.
        directory, _ = LocalPromptRecipeStore._ensure(self.recipes, RECIPE_ID, RECIPE_VERSION)
        initial = self.recipes._read_revision(directory, 1)
        fields = {**initial["fields"], **{field: (ROOT / "prompt_sources/story.brainrot/1.0.0/editorial-r2" / filename).read_text(encoding="utf-8")
            for field, filename in (("plan.system", "concepts.txt"), ("writer.system", "scenario.txt"), ("revision.system", "revision.txt"))}}
        self.recipes._write_revision(directory, 2, fields, initial["templates"], "Mélodrame : fruits, trahison, enjeux et relations cohérentes")
        _atomic_write(directory / "active.json", _json_bytes({"active": 2, "last": 2, "story_editorial_revision": 2}))
        return directory, fields

    def test_existing_factory_r2_upgrades_without_rewriting_its_archive(self):
        directory, r2 = self.install_factory_r2()
        archive = {str(p.relative_to(directory)): p.read_bytes() for p in (directory / "revisions").rglob("*") if p.is_file()}
        current = self.recipes.get(RECIPE_ID, RECIPE_VERSION)
        self.assertEqual(current["active"], 3)
        self.assertEqual(self.recipes.get(RECIPE_ID, RECIPE_VERSION, 2)["fields"], r2)
        for path, payload in archive.items():
            self.assertEqual((directory / path).read_bytes(), payload)
        self.assertEqual(len(self.recipes.history(RECIPE_ID, RECIPE_VERSION)), 3)

    def test_r3_respects_customization_and_prior_rollback_to_factory_r2(self):
        directory, r2 = self.install_factory_r2()
        custom = {**r2, "writer.system": "Mon scénario personnalisé avant r3."}
        self.recipes._write_revision(directory, 3, custom, [], "Modification utilisateur")
        for active in (3, 2, 1):
            _atomic_write(directory / "active.json", _json_bytes({"active": active, "last": 3, "story_editorial_revision": 2}))
            restarted = LocalStoryRecipeStore(self.temp.name, ROOT / "prompt_sources/story.brainrot/1.0.0")
            self.assertEqual(restarted.get(RECIPE_ID, RECIPE_VERSION)["active"], active)
            self.assertEqual(restarted.get(RECIPE_ID, RECIPE_VERSION, 3)["fields"], custom)
            self.assertEqual(len(restarted.history(RECIPE_ID, RECIPE_VERSION)), 3)

    def test_r3_respects_rollback_to_r1_before_upgrade(self):
        directory, _ = self.install_factory_r2()
        _atomic_write(directory / "active.json", _json_bytes({"active": 1, "last": 2, "story_editorial_revision": 2}))
        self.assertEqual(self.recipes.get(RECIPE_ID, RECIPE_VERSION)["active"], 1)
        self.assertEqual(len(self.recipes.history(RECIPE_ID, RECIPE_VERSION)), 2)

    def test_existing_user_recipe_is_not_replaced_by_editorial_upgrade(self):
        directory, _ = LocalPromptRecipeStore._ensure(self.recipes, RECIPE_ID, RECIPE_VERSION)
        initial = self.recipes._read_revision(directory, 1)
        custom = {**initial["fields"], "plan.system": "Mes consignes personnalisées."}
        self.recipes._write_revision(directory, 2, custom, initial["templates"], "Personnalisation antérieure")
        _atomic_write(directory / "active.json", _json_bytes({"active": 2, "last": 2}))
        current = self.recipes.get(RECIPE_ID, RECIPE_VERSION)
        self.assertEqual(current["fields"], custom)
        self.assertEqual(len(self.recipes.history(RECIPE_ID, RECIPE_VERSION)), 2)

    def test_cross_scene_references_and_storage_paths_are_validated(self):
        value = deepcopy(SCENARIO["scenario"])
        value["scenes"][0]["dialogue"][0]["speaker_id"] = "unknown"
        with self.assertRaisesRegex(ValueError, "présent"):
            validate_scenario(value)
        value = deepcopy(SCENARIO["scenario"])
        value["scenes"][0]["location_id"] = "unknown"
        with self.assertRaisesRegex(ValueError, "décor"):
            validate_scenario(value)
        with self.assertRaises(ValueError):
            self.store.get("../escape")

    def test_http_creation_offline_history_and_independent_recipe_catalog(self):
        app = FastAPI()
        app.include_router(stories_router(self.service))
        app.include_router(prompt_recipes_router(None, None, None, None, stories=self.service))
        with TestClient(app) as client:
            result = client.post("/api/stories/projects", json={"brief": "Un citron menteur."})
            self.assertEqual(result.status_code, 201)
            project = result.json()
            self.assertEqual(self.gateway.requests, [])
            self.assertEqual(client.get("/api/stories/projects").json()["projects"][0]["project_id"], project["project_id"])
            self.assertEqual(client.get("/api/prompt-recipes").json()["recipes"][0]["id"], RECIPE_ID)
            package = client.get(f"/api/prompt-recipes/recipe/{RECIPE_ID}/{RECIPE_VERSION}")
            self.assertEqual(package.status_code, 200)
            self.assertEqual(client.post("/api/stories/projects", json={"clip_seconds": True}).status_code, 422)
            result = client.post(f"/api/stories/projects/{project['project_id']}/select", json={"concept_id": "missing", "expected_version": 1})
            self.assertEqual(result.status_code, 422)


if __name__ == "__main__":
    unittest.main()
