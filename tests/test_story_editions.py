"""User-run edition/fidelity regressions. Fake gateway only; never use live projects."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.domain import long_stories as narrative, story_contracts as contracts
from panelforge.domain.story_fidelity import author_requirements, compact_visual, validate_requirements
from panelforge.infrastructure.story_editions import StoryEditions
from tests import test_story_quality_policy as fixture
from tests.test_story_workflow import WorkflowGateway

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = "reference-2026-09-27"
EXPERIMENTAL = "experimental-2026-09-27"
LATEST = "experimental-2026-09-28"
BAD_LINE = "La coupe est ratée. But you should pay me now."


class LanguageGateway(WorkflowGateway):
    def stream(self, request):
        context = json.loads(request.user_prompt)
        for event in super().stream(request):
            if event.kind != StreamEventKind.COMPLETED:
                yield event
                continue
            value = json.loads(event.result.content)
            if context["operation"] == "develop":
                scene = value["scenario"]["scenes"][0]
                scene["dialogue"] = [dict(speaker_id=scene["character_ids"][0], text=BAD_LINE)]
            if context["operation"] == "review_block":
                for review in value["reviews"]:
                    review["issues"] = [dict(category="dialogue_language", severity="warning", target_id="scene-1",
                        dialogue_quote=BAD_LINE, problem="Une proposition anglaise involontaire dans une réplique française.",
                        suggestion="Corriger uniquement la langue de cette réplique.")]
            yield CompletionStreamEvent(kind=StreamEventKind.COMPLETED, phase=StreamPhase.COMPLETED,
                result=CompletionResult(model_id="local::fixture", content=json.dumps(value), finish_reason="stop"))


class StoryEditionsTest(unittest.TestCase):
    setUp = fixture.StoryQualityTest.setUp
    settle = fixture.StoryQualityTest.settle
    advance = fixture.StoryQualityTest.advance
    create = fixture.StoryQualityTest.create
    operations = fixture.StoryQualityTest.operations

    def test_default_pins_latest_and_reference_stays_independent_of_mutable_sources(self):
        project = self.create(writing_edition_id="latest")
        self.assertEqual(project["writing_edition"]["id"], LATEST)
        reference = self.service.long_recipes.editions.get(REFERENCE)
        self.assertEqual(reference["fingerprint"], self.service.long_recipes.snapshot()["fingerprint"])
        self.assertNotEqual(reference["fingerprint"], project["writing_edition"]["fingerprint"])
        self.assertEqual(reference["policy_version"], 1)
        self.assertNotIn("dialogue_language, severity=blocking", reference["quality_prompts"]["review"])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(ROOT / "prompt_sources/story.long/2.0.0/editions", root / "editions")
            archived = StoryEditions(root / "editions")
            first = archived.get(REFERENCE)
            (root / "mutable-prompt.txt").write_text("A new instruction outside the archive.")
            self.assertEqual(first, archived.get(REFERENCE))
            with (root / "editions/reference-2026-09-27.json").open("a", encoding="utf-8") as file:
                file.write(" ")
            with self.assertRaisesRegex(ValueError, "archivée"):
                archived.get(REFERENCE)

    def test_reference_and_experiment_keep_three_calls_and_record_provenance(self):
        for identity in (REFERENCE, EXPERIMENTAL):
            with self.subTest(identity=identity):
                start = len(self.gateway.requests)
                project = self.advance(self.create(writing_edition_id=identity))
                self.assertEqual(project["workflow"]["status"], "ready", project["job"].get("error"))
                calls = self.gateway.requests[start:]
                self.assertEqual([json.loads(r.user_prompt)["operation"] for r in calls], ["compose", "develop", "review_block"])
                self.assertTrue(all(r.trace_context["writing_edition_id"] == identity for r in calls))
                self.assertTrue(all(r["writing_edition"]["id"] == identity for r in project["revisions"] if r.get("model_id")))
                reader = json.loads(calls[-1].user_prompt)
                writer = json.loads(calls[1].user_prompt)
                self.assertEqual("author_requirements" in reader, identity == EXPERIMENTAL)
                self.assertEqual("required_on_screen" in writer["unit_requirements"], identity == REFERENCE)
                if identity == EXPERIMENTAL:
                    self.assertEqual(reader["author_requirements"][0]["source_excerpts"], [project["brief"]])

    def test_switch_does_not_call_model_rewrite_or_invalidate_completed_media_inputs(self):
        project = self.advance(self.create(writing_edition_id=REFERENCE))
        document = deepcopy(project["document"])
        source = narrative.source_hash(project, "episode-1")
        count = len(self.gateway.requests)
        updated = self.service.editions.select(project["project_id"], expected_version=project["version"], edition_id=EXPERIMENTAL)
        self.assertEqual(updated["document"], document)
        self.assertEqual(narrative.source_hash(updated, "episode-1"), source)
        self.assertEqual(len(self.gateway.requests), count)
        self.assertTrue(updated["long_status"]["fabrication_ready"])
        self.assertEqual(updated["writing_edition_info"]["selected"]["id"], EXPERIMENTAL)
        self.assertEqual(updated["writing_edition_info"]["result_edition"]["id"], REFERENCE)
        self.assertEqual(self.service.get(project["project_id"])["writing_edition"]["id"], EXPERIMENTAL)

    def test_running_chain_locks_version_and_resume_does_not_reset_repair_allowance(self):
        project = self.create(writing_edition_id=REFERENCE)
        project["workflow"]["status"] = "running"
        project = self.service.store.save(project)
        with self.assertRaisesRegex(ValueError, "chaîne"):
            self.service.editions.select(project["project_id"], expected_version=project["version"], edition_id=EXPERIMENTAL)
        self.assertEqual(self.gateway.requests, [])

    def test_old_story_is_identified_by_fingerprint_only(self):
        project = self.advance(self.create(writing_edition_id=REFERENCE))
        project.pop("writing_edition")
        project = self.service.store.save(project)
        self.assertEqual(self.service.get(project["project_id"])["writing_edition_info"]["selected"]["id"], REFERENCE)
        project["job"]["editorial_fingerprint"] = "unknown-historical-prompts"
        project["job"]["recipe_revision"] = 8
        project = self.service.store.save(project)
        opened = self.service.get(project["project_id"])
        self.assertIsNone(opened["writing_edition_info"]["selected"])
        with self.assertRaisesRegex(ValueError, "historique"):
            self.service.editions.package(opened)

    def test_retry_cannot_silently_adopt_new_prompts(self):
        self.gateway.fail_operation = "compose"
        project = self.advance(self.create(writing_edition_id=REFERENCE))
        failed_job = deepcopy(project["job"])
        self.assertEqual(failed_job["status"], "failed")
        self.assertEqual(self.service.editions.package(project, retry_job=failed_job)["edition"]["id"], REFERENCE)
        selected = self.service.editions.select(project["project_id"], expected_version=project["version"], edition_id=EXPERIMENTAL)
        with self.assertRaisesRegex(ValueError, "sélectionnée a changé"):
            self.service.editions.package(selected, retry_job=failed_job)
        self.gateway.fail_operation = None
        resumed = self.advance(selected)  # An explicit new operation uses the new choice.
        self.assertEqual(resumed["workflow"]["status"], "ready", resumed["job"].get("error"))
        self.assertEqual(resumed["job"]["writing_edition"]["id"], EXPERIMENTAL)

    def test_language_fault_gets_one_targeted_correction_then_stops_if_still_present(self):
        self.gateway = LanguageGateway()
        self.gateway.story_store = self.service.store
        self.service.gateway = self.gateway
        project = self.advance(self.create())
        self.assertEqual(self.operations(), ["compose", "develop", "review_block", "repair_episode", "review_block"])
        self.assertEqual(project["workflow"]["status"], "blocked")
        self.assertFalse(project["long_status"]["fabrication_ready"])
        correction = json.loads(self.gateway.requests[3].user_prompt)
        self.assertEqual([i["category"] for i in correction["review_to_address"]["issues"]], ["dialogue_language"])
        self.advance(project)
        self.assertEqual(len(self.gateway.requests), 5)

    def test_language_evidence_must_exist_and_author_exact_words_are_not_rewritten(self):
        project = self.advance(self.create())
        scene = project["document"]["episode_scenarios"]["episode-1"]["scenes"][0]
        scene["dialogue"] = [dict(speaker_id=scene["character_ids"][0], text=BAD_LINE)]
        item = dict(category="dialogue_language", severity="warning", target_id="scene-1", dialogue_quote=BAD_LINE,
                    problem="Phrase hybride.", suggestion="Corriger la langue seulement.")
        review = dict(summary="Défaut de livraison identifié.", issues=[item])
        self.assertEqual(narrative.validate_review(project, review, "episode-1")["issues"][0]["severity"], "blocking")
        project["writing_direction"]["protected_lines"] = [BAD_LINE]
        self.assertEqual(narrative.validate_review(project, review, "episode-1")["issues"][0]["severity"], "warning")
        item["dialogue_quote"] = "Une citation inventée par le lecteur."
        with self.assertRaisesRegex(ValueError, "exactement"):
            narrative.validate_review(project, review, "episode-1")
        project["job"]["editorial_policy"] = 1
        self.assertTrue(contracts.structural_issues(review, contracts.review_schema(project, "episode-1")))

    def test_legacy_received_draft_uses_its_original_contract_after_selection_changes(self):
        project = self.create(count=2)
        project["job"] = dict(operation="compose", response_contract_version="2.4.0",
                              editorial_fingerprint=self.service.long_recipes.editions.get(REFERENCE)["fingerprint"])
        schema = contracts.response_schema(project)["properties"]["series_outline"]
        self.assertNotIn("author_requirements", schema["properties"])
        project["job"]["editorial_policy"] = 2
        schema = contracts.response_schema(project)["properties"]["series_outline"]
        self.assertIn("author_requirements", schema["required"])

    def test_style_and_duration_are_still_advisory(self):
        project = self.advance(self.create())
        for category in ("style", "speech_estimate"):
            review = dict(summary="Suggestion seulement.", issues=[dict(category=category, severity="blocking", target_id="scene-1", problem="Préférence.", suggestion="Une autre approche.")])
            self.assertEqual(narrative.validate_review(project, review, "episode-1")["issues"][0]["severity"], "warning")

    def test_author_excerpts_do_not_leak_future_revelation_or_generated_facts(self):
        project = self.create(count=2, brief="Le client croit au succès. Le mensonge est révélé dans le deuxième épisode.")
        project["document"]["series_outline"] = dict(episodes=[dict(id="episode-1"), dict(id="episode-2")],
            author_requirements=[dict(unit_id="episode-1", quote="Le client croit au succès."),
                                 dict(unit_id="episode-2", quote="Le mensonge est révélé dans le deuxième épisode.")])
        rows = project["document"]["series_outline"]["author_requirements"]
        self.assertEqual(validate_requirements(project, rows), rows)
        first = author_requirements(project, ["episode-1"])[0]
        self.assertEqual(first["source_excerpts"], ["Le client croit au succès."])
        self.assertNotIn("deuxième", json.dumps(first, ensure_ascii=False))
        with self.assertRaisesRegex(ValueError, "extrait exact"):
            validate_requirements(project, [dict(unit_id="episode-1", quote="La coupe est réellement réparée.")])
        with self.assertRaisesRegex(ValueError, "extrait exact"):
            validate_requirements(project, [dict(unit_id="episode-12", quote="Le client croit au succès.")])

    def test_api_selection_is_saved_without_generation_and_checks_revision(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from panelforge.features.lab.stories_web import stories_router
        project = self.create(writing_edition_id=REFERENCE)
        app = FastAPI()
        app.include_router(stories_router(self.service))
        with TestClient(app) as client:
            spec = client.get("/api/stories/spec").json()["writing_editions"]
            self.assertEqual(spec["latest"], LATEST)
            url = f"/api/stories/projects/{project['project_id']}/writing-edition"
            body = dict(expected_version=project["version"], edition_id=EXPERIMENTAL)
            response = client.put(url, json=body)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["writing_edition"]["id"], EXPERIMENTAL)
            self.assertEqual(client.put(url, json=body).status_code, 409)
            body.update(expected_version=response.json()["version"], edition_id="not-installed")
            self.assertEqual(client.put(url, json=body).status_code, 422)
            self.assertEqual(self.gateway.requests, [])

    def test_followup_shows_and_pins_edition_before_creating_new_project(self):
        project = self.advance(self.create(writing_edition_id=REFERENCE))
        draft = self.service.followups.open(project["project_id"], expected_version=project["version"])
        self.assertIsNone(draft["context"]["next_unit"])
        self.assertEqual(draft["settings"]["writing_edition_id"], LATEST)
        updated = self.service.followups.update(draft["id"], expected_revision=draft["revision"],
            direction=dict(start="Le client revient.", beats="", ending="", constraints=""), model_id="local::fixture",
            settings=dict(draft["settings"], writing_edition_id=REFERENCE))
        self.assertEqual(updated["settings"]["writing_edition_id"], REFERENCE)
        self.assertEqual(self.service.followups._edition(updated)["followup_prompt"],
                         self.service.long_recipes.editions.get(REFERENCE)["followup_prompt"])
        self.assertEqual(len(self.gateway.requests), 3)  # Opening and editing cause no calls.
        reopened = self.service.followups.get(draft["id"])
        self.assertEqual(reopened["settings"]["writing_edition_id"], REFERENCE)

    def test_visual_compaction_preserves_transformations_without_mutation(self):
        values = [dict(identity_states=[dict(element_id="a", state="initial")], elements=[dict(id="a", states=[])], scene_states=[dict(scene_index=0,element_id="a",start="thin",end="thin"),dict(scene_index=1,element_id="a",start="thin",end="pregnant")])]
        before = deepcopy(values)
        compact = compact_visual(values)
        self.assertEqual(values, before)
        self.assertEqual(compact[0]["scene_states"][0]["state"], "thin")
        self.assertEqual(compact[0]["scene_states"][1], values[0]["scene_states"][1])
        self.assertEqual(compact[0]["identity_states"], values[0]["identity_states"])
        self.assertLess(len(json.dumps(compact)), len(json.dumps(values)))


if __name__ == "__main__":
    unittest.main()
