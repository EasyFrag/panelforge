"""User-run visual-state regressions; pure fixtures, no inference or rendering."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from panelforge.application.long_stories import request
from panelforge.domain import episode_continuity as production, story_continuity as ledger
from panelforge.domain import long_stories as narrative, story_contracts as contracts, story_visual_states as visual
from panelforge.domain.episodes import scene_inputs
from panelforge.infrastructure.long_story_recipes import LongStoryRecipes
from tests.test_story_visual_continuity import VisualContinuityContractTest, fabrication, change

ROOT = Path(__file__).resolve().parents[1]


class RequiredVisualContractTest(unittest.TestCase):
    setUp = VisualContinuityContractTest.setUp
    wire = VisualContinuityContractTest.wire

    def reviewed(self, operation="review_episode"):
        project, wire = self.wire(visual.CONTRACT_VERSION)
        project["visual_state_policy"] = 1
        _, parsed = narrative.parse(project, wire)
        narrative.apply_document(project, parsed)
        project["job"].update(operation=operation, review_unit_ids=["episode-1"])
        return project

    def patch(self, project):
        person = project["document"]["episode_scenarios"]["episode-1"]["characters"][0]
        return dict(base_hash=narrative.source_hash(project, "episode-1"), elements=[dict(
            id=person["id"], kind="character", name=person["name"], description="Silhouette reconnaissable.",
            reason="Apparence persistante visible.", tracking="reference", scene_indices=[0, 1],
            states=[change("visible-pregnancy", appearance="Ventre de grossesse visiblement arrondi", reference=True)])])

    def test_review_patch_changes_only_ledger_and_review_remains_current(self):
        for operation in ("review_episode", "review_block"):
            with self.subTest(operation=operation):
                project = self.reviewed(operation)
                before = deepcopy(project["document"]["episode_scenarios"]["episode-1"])
                state = deepcopy(project["document"]["episode_states"])
                review = dict(summary="Raccord visuel complété.", issues=[], visual_patch=self.patch(project))
                response = (dict(reply="Relu.", reviews=[dict(unit_id="episode-1", **review)])
                    if operation == "review_block" else dict(reply="Relu.", review=review))
                raw = deepcopy(response)
                _, incoming = narrative.parse(project, response)
                narrative.apply_document(project, incoming)
                after = project["document"]["episode_scenarios"]["episode-1"]
                self.assertEqual({k:v for k,v in before.items() if k != "visual_continuity"},
                                 {k:v for k,v in after.items() if k != "visual_continuity"})
                self.assertEqual(project["document"]["episode_states"], state)
                self.assertEqual(response, raw)
                self.assertEqual(after["visual_continuity"]["elements"][0]["states"][0]["reference"], True)
                saved = project["document"]["reviews"]["episode-1"]
                self.assertEqual(saved["source_hash"], narrative.source_hash(project, "episode-1"))
                self.assertEqual(saved["contract_version"], visual.CONTRACT_VERSION)

    def test_bad_or_stale_patch_preserves_all_visual_states_without_losing_review(self):
        for mode in ("stale", "unknown", "duplicate", "shape"):
            with self.subTest(mode=mode):
                project = self.reviewed()
                patch = self.patch(project)
                if mode == "stale": patch["base_hash"] = "old"
                if mode == "unknown": patch["elements"][0]["id"] = "unknown-person"
                if mode == "duplicate": patch["elements"].append(deepcopy(patch["elements"][0]))
                if mode == "shape": patch["elements"][0]["states"][0]["unexpected"] = True
                before = deepcopy(project["document"]["episode_scenarios"])
                _, incoming = narrative.parse(project, dict(reply="Relu.", review=dict(summary="Lecture conservée.", issues=[], visual_patch=patch)))
                narrative.apply_document(project, incoming)
                self.assertEqual(project["document"]["episode_scenarios"], before)
                self.assertTrue(any(i["severity"] == "warning" and "Suivi visuel" in i["problem"] for i in incoming["review"]["issues"]))

    def test_reader_projection_has_no_secret_or_dramatic_summary_and_no_extra_call(self):
        project = self.reviewed()
        scenario = project["document"]["episode_scenarios"]["episode-1"]
        scenario["visual_continuity"]["elements"] = self.patch(project)["elements"]
        scenario["visual_continuity"]["dramatic_summary"] = "PRIVILEGED_SUMMARY"
        scenario["visual_continuity"]["elements"][0]["reason"] = "PRIVILEGED_REASON"
        project["brief"] = "PRIVILEGED_BRIEF"
        package = LongStoryRecipes(ROOT / "prompt_sources/story.long/2.0.0").snapshot()
        payload = request(project, package, "Français")
        context = json.loads(payload.user_prompt)
        self.assertIn("visual_state_review", context)
        self.assertNotIn("PRIVILEGED", json.dumps(context))
        self.assertEqual(payload.system_prompt.count("CONTRÔLE VISUEL DE FABRICATION"), 1)
        project["job"]["response_contract_version"] = contracts.VERSION
        old = request(project, package, "Français")
        self.assertNotIn("visual_state_review", json.loads(old.user_prompt))
        self.assertNotIn("visual_patch", json.dumps(contracts.response_schema(project)))

    def test_writer_is_opt_in_and_announced_pregnancy_does_not_create_a_state_by_keyword(self):
        package = LongStoryRecipes(ROOT / "prompt_sources/story.long/2.0.0").snapshot()
        for version in ("2.1.0", contracts.VERSION, visual.CONTRACT_VERSION):
            project, wire = self.wire(version)
            request_value = request(project, package, "Français")
            self.assertEqual("ÉTATS VISUELS REQUIS" in request_value.system_prompt, version == visual.CONTRACT_VERSION)
            wire["scenario"]["logline"] = "Elle annonce une grossesse au téléphone, sans changement visible."
            wire["scenario"].pop("visual_continuity", None)
            _, parsed = narrative.parse(project, wire)
            self.assertFalse(ledger.reference_specs(parsed["scenario"]))


class RequiredVisualRoutingTest(unittest.TestCase):
    def episode(self):
        episode = fabrication()
        episode["visual_state_policy"] = 1
        return episode

    def test_missing_state_blocks_only_following_scenes_and_never_falls_back_to_identity(self):
        episode = self.episode()
        variant = next(r for r in episode["references"] if r.get("continuity_state_id"))
        variant["image_asset_id"] = None
        self.assertTrue(scene_inputs(episode, episode["scenes"][1]))  # transformation: existing before-state behavior
        with self.assertRaisesRegex(production.RequiredReferenceMissing, "Référence à préparer"):
            scene_inputs(episode, episode["scenes"][2])
        self.assertEqual(production.required_bindings(episode, episode["scenes"][2]), [variant["id"]])
        episode["scenes"][2]["references"] = [b for b in episode["scenes"][2]["references"] if b["reference_id"] != "character-1"]
        with self.assertRaises(production.RequiredReferenceMissing):
            scene_inputs(episode, episode["scenes"][2])

    def test_voice_only_cast_does_not_require_the_offscreen_visual_variant(self):
        episode = self.episode()
        episode["scenario"]["visual_continuity"]["elements"][0]["scene_indices"] = [0, 1]
        variant = next(r for r in episode["references"] if r.get("continuity_state_id"))
        variant["image_asset_id"] = None
        self.assertEqual(production.required_bindings(episode, episode["scenes"][2]), [])
        self.assertNotIn(variant["id"], [r["reference_id"] for r in scene_inputs(episode, episode["scenes"][2])["references"]])
        self.assertEqual(production.snapshot(episode, episode["scenes"][2]), [])

    def test_replacing_identity_marks_state_stale_without_mutating_old_inputs(self):
        episode = self.episode()
        variant = next(r for r in episode["references"] if r.get("continuity_state_id"))
        variant["continuity_source_signature"] = production.variant_signature(episode, variant)
        recorded = scene_inputs(episode, episode["scenes"][2])
        saved = deepcopy(recorded)
        production.variant_base(episode, variant)["image_asset_id"] = "new-identity"
        self.assertTrue(production.variant_stale(episode, variant))
        with self.assertRaises(production.RequiredReferenceMissing):
            scene_inputs(episode, episode["scenes"][2])
        self.assertEqual(recorded, saved)
        episode.pop("visual_state_policy")
        self.assertFalse(production.variant_stale(episode, variant))  # legacy semantics unchanged
        self.assertTrue(scene_inputs(episode, episode["scenes"][2]))

    def test_inherited_state_keeps_reference_even_if_writer_omits_its_anchor(self):
        original = self.episode()["scenario"]
        inherited = ledger.carry_forward(original, require_references=True)
        next_scenario = deepcopy(original)
        entry = next_scenario["visual_continuity"]["elements"][0]
        baseline = deepcopy(inherited["elements"][0]["states"][0]); baseline.update(id="opening", reference=False)
        entry.update(states=[baseline], tracking="text")
        merged = ledger.inherit(next_scenario, inherited)
        self.assertTrue(merged["visual_continuity"]["elements"][0]["states"][0]["reference"])
        self.assertEqual(len(ledger.reference_specs(merged)), 1)
        self.assertFalse(ledger.carry_forward(original)["elements"][0]["states"][0]["reference"])


if __name__ == "__main__":
    unittest.main()
