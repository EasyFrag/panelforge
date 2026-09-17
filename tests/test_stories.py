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
from panelforge.domain.stories import (
    EXPLICIT_RECIPE_ID, EXPLICIT_RECIPE_VERSION, RECIPE_ID, RECIPE_VERSION,
    SENSUAL_RECIPE_ID, SENSUAL_RECIPE_VERSION,
    decode_story_json, extract_script_dialogue_cues, extract_script_dialogues, parse_response, validate_concepts,
    validate_scenario, validate_script_dialogue_coverage, response_contract, scene_intention,
)
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
        self.reasoning = ""

    def list_models(self):
        return [ModelDescriptor("local::fixture", "local", "Modèle de test")]

    def stream(self, request):
        self.requests.append(request)
        raw = self.response
        self.entered.set()
        if not self.release.wait(5):
            raise TimeoutError("Test gateway timed out")
        if self.reasoning:
            yield CompletionStreamEvent(StreamEventKind.REASONING, StreamPhase.GENERATING, text=self.reasoning)
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

    def test_story_reply_accepts_144000_characters_and_rejects_more(self):
        response = deepcopy(IDEAS)
        response["reply"] = "x" * 144_000
        reply, document = parse_response(response, "ideas", False)
        self.assertEqual(len(reply), 144_000)
        self.assertEqual(len(document["concepts"]), 3)
        response["reply"] += "x"
        with self.assertRaisesRegex(ValueError, "maximum 144000"):
            parse_response(response, "ideas", False)

    def test_story_requests_and_preserves_live_model_reasoning(self):
        self.gateway.reasoning = "Je pose les enjeux, puis je distingue trois fins."
        project = self.concepts()
        self.assertTrue(self.gateway.requests[-1].include_reasoning)
        self.assertEqual(project["job"]["reasoning"], self.gateway.reasoning)
        self.assertEqual(project["job"]["draft"], self.gateway.response)

    def test_one_or_two_proposals_use_the_requested_contract_and_one_is_auto_selected(self):
        for count in (1, 2):
            with self.subTest(count=count):
                response = {"reply": "Voici.", "concepts": deepcopy(IDEAS["concepts"][:count])}
                self.gateway.response = json.dumps(response)
                project = self.service.create(proposal_count=count)
                project = self.write(project, "ideas")
                self.assertEqual(project["job"]["status"], "succeeded")
                self.assertEqual(len(project["document"]["concepts"]), count)
                self.assertEqual(project["document"]["selected_id"], "concept-1" if count == 1 else None)
                request = self.gateway.requests[-1]
                context = json.loads(request.user_prompt)
                self.assertEqual(context["proposal_count"], count)
                self.assertEqual(len(context["response_contract"]["concepts"]), count)
                self.assertIn(f"exactement {count} proposition", request.system_prompt)

    def test_dialogue_register_is_opt_in_and_script_fidelity_forces_current_behavior(self):
        current = self.service.create()
        current_request = self.service._request({**current, "model_id": "local::fixture",
            "job": {"operation": "ideas", "request_id": "fixture-request"}}, self.recipes.get(RECIPE_ID, RECIPE_VERSION))
        self.assertEqual(current["dialogue_register"], 0)
        self.assertNotIn("dialogue_register", json.loads(current_request.user_prompt))
        self.assertNotIn("REGISTRE DES DIALOGUES", current_request.system_prompt)

        project = self.service.create(dialogue_register=2)
        project = self.write(project, "ideas")
        project = self.service.select(project["project_id"], "concept-1", project["version"])
        self.gateway.response = json.dumps(SCENARIO)
        project = self.write(project, "develop")
        request = self.gateway.requests[-1]
        self.assertEqual(json.loads(request.user_prompt)["dialogue_register"], 2)
        self.assertIn("REGISTRE DES DIALOGUES — CRU", request.system_prompt)
        self.assertIn("ça pue", request.system_prompt)

        script = self.service.create(brief="LÉA\nBonjour.\n", creation_mode="script", dialogue_register=3)
        self.assertEqual(script["dialogue_register"], 0)

    def test_script_mode_skips_concepts_and_requires_every_source_dialogue_verbatim(self):
        script = """TITRE : LA REINE\n\nSCÈNE 1 — SUR LA PLACE\n\nREINE\nC’est lui !\n\nLIVREUR — À VOIX BASSE\nMadame… votre nom est ici.\n\nFIN\n"""
        self.assertEqual(extract_script_dialogues(script), ["C’est lui !", "Madame… votre nom est ici."])
        self.gateway.response = json.dumps(SCENARIO, ensure_ascii=False)
        project = self.service.create(brief=script, creation_mode="script",
            architect_model_id="local::architect", writer_model_id="local::writer")
        self.service.start(project["project_id"], operation="script", instruction="", model_id=None,
            expected_version=project["version"], request_id=str(uuid4()))
        project = self.finish(project)
        self.assertEqual(project["job"]["status"], "succeeded")
        self.assertFalse(project["document"]["concepts"])
        dialogue = project["document"]["scenario"]["scenes"][0]["dialogue"]
        self.assertEqual([line["text"] for line in dialogue], [line["text"] for line in SCENARIO["scenario"]["scenes"][0]["dialogue"]])
        self.assertEqual(dialogue[0], {**SCENARIO["scenario"]["scenes"][0]["dialogue"][0],
                                      "dialogue_id": "dialogue-1", "delivery": "spoken"})
        self.assertEqual(dialogue[1], {**SCENARIO["scenario"]["scenes"][0]["dialogue"][1],
                                      "dialogue_id": "dialogue-2", "delivery": "spoken",
                                      "delivery_note": "À VOIX BASSE"})
        request = self.gateway.requests[-1]
        self.assertEqual(request.model_id, "local::writer")
        self.assertEqual(request.temperature, .35)
        self.assertIn("MODE SCRIPT FIDÈLE", request.system_prompt)
        context = json.loads(request.user_prompt)
        self.assertEqual(context["creation_mode"], "script")
        self.assertEqual(context["brief"], script.strip())
        self.assertEqual(context["source_dialogues"][1]["dialogue_id"], "dialogue-2")
        self.assertEqual(context["source_dialogues"][1]["delivery_note"], "À VOIX BASSE")
        self.assertIn("dialogues mot pour mot", context["contract_notes"])

        broken = deepcopy(SCENARIO)
        broken["scenario"]["scenes"][0]["dialogue"].pop()
        self.gateway.response = json.dumps(broken, ensure_ascii=False)
        retry = self.service.create(brief=script, creation_mode="script", writer_model_id="local::writer")
        self.service.start(retry["project_id"], operation="script", instruction="", model_id=None,
            expected_version=retry["version"], request_id=str(uuid4()))
        retry = self.finish(retry)
        self.assertEqual(retry["job"]["status"], "failed")
        self.assertIn("intégralité des dialogues", retry["job"]["error"])
        self.assertIsNone(retry["document"]["scenario"])

    def test_script_delivery_notations_are_canonicalized_without_changing_spoken_words(self):
        script = """SCÈNE 1

LÉA — VOIX OFF
Je réfléchis.

TOM [O.S.]
Léa ?

LÉA (V.O.)
Je réponds.

VOICE OVER DE TOM
Je conclus.

FIN
"""
        cues = extract_script_dialogue_cues(script)
        self.assertEqual([cue["delivery"] for cue in cues],
                         ["voice_over", "off_screen", "voice_over", "voice_over"])
        self.assertEqual([cue["dialogue_id"] for cue in cues],
                         ["dialogue-1", "dialogue-2", "dialogue-3", "dialogue-4"])
        scenario = validate_scenario({
            "title": "Essai", "logline": "Une conversation.",
            "characters": [{"id": "lea", "name": "LÉA", "description": "Une femme."},
                           {"id": "tom", "name": "TOM", "description": "Un homme."}],
            "locations": [{"id": "lieu", "name": "Pièce", "description": "Une pièce."}],
            "scenes": [{"title": "Conversation", "location_id": "lieu", "character_ids": ["lea", "tom"],
                "opening_state": "Ils sont séparés.", "action": "Leurs voix se répondent.",
                "dialogue": [{"speaker_id": "lea", "text": "(Voix off) Je réfléchis."},
                             {"speaker_id": "tom", "text": "[O.S.] Léa ?"},
                             {"speaker_id": "lea", "text": "Je réponds."},
                             {"speaker_id": "tom", "text": "Je conclus."}],
                "ending_state": "La conversation prend fin."}]})
        validate_script_dialogue_coverage(script, scenario)
        dialogue = scenario["scenes"][0]["dialogue"]
        self.assertEqual([line["text"] for line in dialogue],
                         ["Je réfléchis.", "Léa ?", "Je réponds.", "Je conclus."])
        self.assertEqual([line["delivery"] for line in dialogue],
                         ["voice_over", "off_screen", "voice_over", "voice_over"])
        self.assertEqual(dialogue[1]["delivery_note"], "O.S.")
        changed = deepcopy(scenario)
        changed["scenes"][0]["dialogue"][2]["text"] = "Je ne réponds pas."
        with self.assertRaisesRegex(ValueError, "intégralité des dialogues"):
            validate_script_dialogue_coverage(script, changed)

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

    def test_structured_scene_edit_is_versioned_without_an_llm_call(self):
        project = self.scenario()
        calls = len(self.gateway.requests)
        source = project["document"]["scenario"]["scenes"][0]
        changes = {key: deepcopy(source[key]) for key in ("title", "opening_state", "action", "dialogue", "ending_state")}
        changes["action"] = "La reine déchire l’étiquette ; le livreur ramasse les deux morceaux et les rapproche."
        edited = self.service.edit_scene(project["project_id"], 0, project["version"], changes)
        self.assertEqual(len(self.gateway.requests), calls)
        self.assertEqual(edited["document"]["scenario"]["scenes"][0]["action"], changes["action"])
        self.assertEqual(edited["revisions"][-1]["label"], "Édition manuelle de la scène 1")
        self.assertIn("diagnostics", edited)

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
            self.assertEqual(client.post("/api/stories/projects", json={"proposal_count": 0}).status_code, 422)
            self.assertEqual(client.post("/api/stories/projects", json={"dialogue_register": 4}).status_code, 422)
            self.assertEqual(client.post("/api/stories/projects", json={"creation_mode": "script", "brief": ""}).status_code, 422)
            result = client.post(f"/api/stories/projects/{project['project_id']}/select", json={"concept_id": "missing", "expected_version": 1})
            self.assertEqual(result.status_code, 422)

    def test_sensual_family_has_an_independent_contract_recipe_and_models(self):
        recipes = LocalStoryRecipeStore(self.temp.name, {
            (RECIPE_ID, RECIPE_VERSION): ROOT / "prompt_sources/story.brainrot/1.0.0",
            (SENSUAL_RECIPE_ID, SENSUAL_RECIPE_VERSION): ROOT / "prompt_sources/story.sensual-light/1.0.0",
            (EXPLICIT_RECIPE_ID, EXPLICIT_RECIPE_VERSION): ROOT / "prompt_sources/story.explicit-hard/1.0.0",
        })
        self.service = StoryService(gateway=self.gateway, store=self.store, recipes=recipes)
        specs = {item["id"]: item for item in self.service.recipe_specs()}
        self.assertEqual(set(specs), {RECIPE_ID, SENSUAL_RECIPE_ID, EXPLICIT_RECIPE_ID})
        self.assertIn("sexual_state", {field["id"] for field in specs[EXPLICIT_RECIPE_ID]["scene_fields"]})
        fruit = recipes.get(RECIPE_ID, RECIPE_VERSION)
        sensual = recipes.get(SENSUAL_RECIPE_ID, SENSUAL_RECIPE_VERSION)
        self.assertNotEqual(fruit["fields"], sensual["fields"])
        changed = {**sensual["fields"], "plan.system": sensual["fields"]["plan.system"] + "\nVariation locale."}
        recipes.save(SENSUAL_RECIPE_ID, SENSUAL_RECIPE_VERSION, base_revision=1, expected_active=1, fields=changed)
        self.assertEqual(recipes.get(RECIPE_ID, RECIPE_VERSION)["active"], fruit["active"])

        concepts = [{"id": f"concept-{index}", "title": f"Après minuit {index}", "hook": "Deux collègues prolongent un verre.",
            "characters_and_dynamic": "Deux adultes attirés l’un par l’autre.", "desire": "Ils veulent cesser de se retenir.",
            "obstacle": "Ils craignent de compliquer leur travail.", "sensual_escalation": "Leurs mains se frôlent puis restent jointes.",
            "turning_point": "Elle lui demande de rester.", "ending": "Ils s’embrassent et referment la porte."}
            for index in range(1, 4)]
        self.gateway.response = json.dumps({"reply": "Trois pistes.", "concepts": concepts})
        project = self.service.create(recipe_id=SENSUAL_RECIPE_ID, recipe_version=SENSUAL_RECIPE_VERSION,
            architect_model_id="local::architect", writer_model_id="local::writer")
        self.service.start(project["project_id"], operation="ideas", instruction="", model_id=None,
            expected_version=project["version"], request_id=str(uuid4()))
        project = self.finish(project)
        self.assertEqual(self.gateway.requests[-1].model_id, "local::architect")
        self.assertEqual(self.gateway.requests[-1].trace_context["cookbook_id"], SENSUAL_RECIPE_ID)
        self.assertEqual(project["document"]["concepts"], validate_concepts(concepts, SENSUAL_RECIPE_ID))

        project = self.service.select(project["project_id"], "concept-1", project["version"])
        scenario = deepcopy(SCENARIO["scenario"])
        for character in scenario["characters"]:
            character["adult"] = True
        scenario["scenes"][0].update(relationship_state="Ils assument enfin leur attirance réciproque.",
            appearance_state="Leurs tenues de soirée restent intactes et clairement décrites.")
        self.gateway.response = json.dumps({"reply": "Voici le scénario.", "scenario": scenario})
        self.service.start(project["project_id"], operation="develop", instruction="", model_id=None,
            expected_version=project["version"], request_id=str(uuid4()))
        project = self.finish(project)
        self.assertEqual(self.gateway.requests[-1].model_id, "local::writer")
        self.assertEqual(project["document"]["scenario"]["characters"][0]["adult"], True)

        with self.assertRaisesRegex(ValueError, "adulte"):
            validate_scenario(SCENARIO["scenario"], SENSUAL_RECIPE_ID)

    def test_explicit_family_is_independent_and_requires_physical_continuity(self):
        recipes = LocalStoryRecipeStore(self.temp.name, {
            (RECIPE_ID, RECIPE_VERSION): ROOT / "prompt_sources/story.brainrot/1.0.0",
            (SENSUAL_RECIPE_ID, SENSUAL_RECIPE_VERSION): ROOT / "prompt_sources/story.sensual-light/1.0.0",
            (EXPLICIT_RECIPE_ID, EXPLICIT_RECIPE_VERSION): ROOT / "prompt_sources/story.explicit-hard/1.0.0",
        })
        self.service = StoryService(gateway=self.gateway, store=self.store, recipes=recipes)
        fruit = recipes.get(RECIPE_ID, RECIPE_VERSION)
        sensual = recipes.get(SENSUAL_RECIPE_ID, SENSUAL_RECIPE_VERSION)
        explicit = recipes.get(EXPLICIT_RECIPE_ID, EXPLICIT_RECIPE_VERSION)
        self.assertNotEqual(explicit["fields"], fruit["fields"])
        self.assertNotEqual(explicit["fields"], sensual["fields"])
        changed = {**explicit["fields"], "writer.system": explicit["fields"]["writer.system"] + "\nVariation Cru locale."}
        recipes.save(EXPLICIT_RECIPE_ID, EXPLICIT_RECIPE_VERSION, base_revision=1,
            expected_active=1, fields=changed)
        self.assertEqual(recipes.get(RECIPE_ID, RECIPE_VERSION)["active"], fruit["active"])
        self.assertEqual(recipes.get(SENSUAL_RECIPE_ID, SENSUAL_RECIPE_VERSION)["active"], sensual["active"])

        concept = {"id": "concept-1", "title": "Après la fermeture", "hook": "Deux adultes prolongent la nuit.",
            "participants_and_dynamic": "Deux partenaires adultes.", "explicit_premise": "Un acte sexuel explicite.",
            "acts_and_progression": "Approche, contact, changement de position et acte principal.",
            "physical_escalation": "Les mouvements deviennent plus soutenus.",
            "turning_point": "Ils changent volontairement de position.", "ending": "Ils restent enlacés sur le lit."}
        self.assertEqual(validate_concepts([concept], EXPLICIT_RECIPE_ID, expected_count=1)[0]["id"], "concept-1")

        scenario = deepcopy(SCENARIO["scenario"])
        for character in scenario["characters"]:
            character["adult"] = True
        scenario["scenes"][0].update(
            relationship_state="Les deux partenaires adultes poursuivent la scène ensemble.",
            appearance_state="Leurs vêtements sont retirés et restent au pied du lit.",
            sexual_state="Ils sont allongés face à face, sans contact sexuel encore établi.")
        validated = validate_scenario(scenario, EXPLICIT_RECIPE_ID)
        self.assertEqual(validated["scenes"][0]["sexual_state"], scenario["scenes"][0]["sexual_state"])
        self.assertIn("Position et contacts sexuels au début", scene_intention(validated, 0, 10))
        contract = response_contract("develop", False, EXPLICIT_RECIPE_ID, EXPLICIT_RECIPE_VERSION)
        self.assertIn("sexual_state", contract["scenario"]["scenes"][0])
        del scenario["scenes"][0]["sexual_state"]
        with self.assertRaisesRegex(ValueError, "sexual_state"):
            validate_scenario(scenario, EXPLICIT_RECIPE_ID)


if __name__ == "__main__":
    unittest.main()
