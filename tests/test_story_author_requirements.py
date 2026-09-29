"""User-run regressions: redundant single-unit citations, strict multi-unit sources.
Synthetic gateway and temporary stores only; no live LLM or runtime data.
"""
from copy import deepcopy
import json
import unittest

from panelforge.domain import long_stories as narrative, story_contracts as contracts
from panelforge.domain.story_fidelity import author_requirements
from tests import test_story_quality_policy as fixture

BRIEF = "Nabil perd son portefeuille. Mehdi dit : « Je vais me payer une pute. »"
BAD_ROWS = [dict(unit_id="episode-1", quote="Je vais me pay a pute.")]


class StoryAuthorRequirementsTest(unittest.TestCase):
    setUp = fixture.StoryQualityTest.setUp
    settle = fixture.StoryQualityTest.settle
    advance = fixture.StoryQualityTest.advance
    create = fixture.StoryQualityTest.create

    def composing(self, count=1):
        project = self.create(mode="manual", count=count, brief=BRIEF)
        project["job"] = dict(operation="compose", editorial_policy=2, response_contract_version="2.4.0")
        return project

    def response(self, project):
        response = narrative.outline_example(project)
        choices = dict(profile="social", narration="dialogue", ending_type="reversal")
        response["resolved_options"] = {key: value if project["long_options"][key] == "auto"
                                       else project["long_options"][key] for key, value in choices.items()}
        response["series_outline"]["episodes"][-1]["ending_type"] = response["resolved_options"]["ending_type"]
        return response

    def failed_draft(self):
        self.gateway.fail_operation = "compose"
        project = self.advance(self.create(mode="manual", brief=BRIEF))
        self.assertEqual(project["job"]["status"], "failed")
        response = self.response(project)
        response["series_outline"]["author_requirements"] = deepcopy(BAD_ROWS)
        raw = json.dumps(response, ensure_ascii=False)
        project["job"].update(draft=raw, error="Une contrainte d’auteur doit citer un extrait exact.",
                              reasoning="Trace du modèle conservée.")
        project = self.service.store.save(project)
        return project, raw

    def test_schema_requests_attribution_only_for_multiple_units(self):
        for count in (1, 2):
            project = self.composing(count)
            for operation in ("compose", "revise_outline"):
                project["job"]["operation"] = operation
                with self.subTest(count=count, operation=operation):
                    schema = contracts.outline_schema(project)
                    self.assertEqual("author_requirements" in schema["properties"], count > 1)
                    self.assertEqual("author_requirements" in schema["required"], count > 1 and operation == "compose")
            if count == 1:
                project["document"]["series_outline"] = dict(author_requirements=deepcopy(BAD_ROWS))
                self.assertNotIn("author_requirements", contracts.outline_schema(project)["properties"])

    def test_single_draft_keeps_story_and_source_exact_without_trusting_recopied_quotes(self):
        project = self.composing()
        response = self.response(project)
        original_project = deepcopy(project)
        expected = narrative.parse(project, response)
        for redundant in (BAD_ROWS, [dict(unit_id="episode-99", quote="Texte inventé")], None, "ancienne métadonnée"):
            with self.subTest(redundant=redundant):
                received = deepcopy(response)
                received["series_outline"]["author_requirements"] = deepcopy(redundant)
                original_received = deepcopy(received)
                reply, incoming = narrative.parse(project, received)
                self.assertEqual((reply, incoming), expected)
                self.assertEqual(received, original_received)
                self.assertEqual(project, original_project)
                candidate = deepcopy(project)
                narrative.apply_document(candidate, incoming)
                self.assertEqual(author_requirements(candidate, ["episode-1"])[0]["source_excerpts"], [BRIEF])
                self.assertNotIn("author_requirements", candidate["document"]["series_outline"])

    def test_redundant_metadata_never_masks_actual_outline_errors(self):
        project = self.composing()
        for fault in ("unit", "dependency", "extra", "missing"):
            response = self.response(project)
            outline = response["series_outline"]
            outline["author_requirements"] = deepcopy(BAD_ROWS)
            if fault == "unit":
                outline["episodes"][0]["id"] = "episode-99"
            elif fault == "dependency":
                outline["episodes"][0]["events"][0]["depends_on"] = ["event-99"]
            elif fault == "extra":
                outline["invented_field"] = "Unsupported narrative content"
            else:
                outline.pop("contract")
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                narrative.parse(project, response)

    def test_multi_unit_citations_must_still_be_verbatim_and_address_existing_units(self):
        project = self.composing(count=2)
        valid = self.response(project)
        valid["series_outline"]["author_requirements"] = [dict(unit_id="episode-1", quote="Nabil perd son portefeuille.")]
        incoming = narrative.parse(project, valid)[1]
        self.assertEqual(incoming["series_outline"]["author_requirements"], valid["series_outline"]["author_requirements"])
        for bad in (BAD_ROWS, [dict(unit_id="episode-99", quote="Nabil perd son portefeuille.")], None):
            response = deepcopy(valid)
            response["series_outline"]["author_requirements"] = deepcopy(bad)
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                narrative.parse(project, response)
        del valid["series_outline"]["author_requirements"]
        with self.assertRaises(ValueError):
            narrative.parse(project, valid)

    def test_reference_contract_stays_strict_and_old_single_arc_remains_editable(self):
        project = self.composing()
        project["job"]["editorial_policy"] = 1
        response = self.response(project)
        response["series_outline"]["author_requirements"] = deepcopy(BAD_ROWS)
        with self.assertRaises(ValueError):
            narrative.parse(project, response)
        # A saved experimental arc can still be edited after selecting reference prompts.
        project["document"]["series_outline"] = deepcopy(response["series_outline"])
        project["long_options"].update(response["resolved_options"])
        project["job"]["operation"] = "revise_outline"
        response.pop("resolved_options")
        incoming = narrative.parse(project, response)[1]
        self.assertNotIn("author_requirements", incoming["series_outline"])
        direct = narrative.validate_outline(project, response["series_outline"])
        self.assertEqual(direct, incoming["series_outline"])

    def test_recovery_advertised_and_applied_locally_preserves_original_draft(self):
        project, raw = self.failed_draft()
        calls = len(self.gateway.requests)
        reopened = self.service.get(project["project_id"])
        self.assertTrue(reopened["job"]["can_revalidate"], reopened["job"].get("revalidation_error"))
        recovered = self.service.revalidate(project["project_id"], reopened["version"])
        self.assertEqual(len(self.gateway.requests), calls)
        self.assertEqual(recovered["job"]["status"], "succeeded")
        self.assertEqual(recovered["job"]["draft"], raw)
        self.assertEqual(recovered["job"]["original_draft"], raw)
        normalized = json.loads(raw)
        normalized["series_outline"].pop("author_requirements")
        self.assertEqual(json.loads(recovered["job"]["normalized_draft"]), normalized)
        self.assertEqual(recovered["job"]["reasoning"], "Trace du modèle conservée.")
        self.assertTrue(any("Séquence unique" in note for note in recovered["job"]["normalizations"]))
        self.assertEqual(recovered["brief"], BRIEF)
        self.assertEqual(recovered["workflow"]["status"], "paused")
        self.assertEqual(author_requirements(recovered, ["episode-1"])[0]["source_excerpts"], [BRIEF])
        self.assertNotIn("author_requirements", self.gateway.requests[0].output_schema["properties"]["series_outline"]["properties"])

    def test_local_recovery_does_not_apply_an_obsolete_draft(self):
        project, raw = self.failed_draft()
        project["brief"] += " Changement demandé après l’appel."
        project = self.service.store.save(project)
        calls = len(self.gateway.requests)
        reopened = self.service.get(project["project_id"])
        self.assertFalse(reopened["job"]["can_revalidate"])
        with self.assertRaisesRegex(ValueError, "document a changé"):
            self.service.revalidate(project["project_id"], reopened["version"])
        self.assertEqual(len(self.gateway.requests), calls)
        self.assertEqual(self.service.store.get(project["project_id"])["job"]["draft"], raw)

    def test_single_empty_source_never_promotes_a_stored_model_claim(self):
        project = self.composing()
        project["brief"] = ""
        project["document"]["series_outline"] = dict(episodes=[dict(id="episode-1")],
            author_requirements=[dict(unit_id="episode-1", quote="")])
        self.assertEqual(author_requirements(project, ["episode-1"])[0]["source_excerpts"], [])


if __name__ == "__main__":
    unittest.main()
