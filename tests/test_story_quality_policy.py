"""User-run regressions; synthetic gateway only, no LLM, GPU or live projects."""
from copy import deepcopy
import json
import unittest

from panelforge.application.long_stories import request
from panelforge.domain import long_stories as narrative, story_direction as direction
from panelforge.domain import story_contracts as contracts
from panelforge.domain.story_diagnostics import quality_issues, project_quality
from panelforge.domain.episodes import initial_episode, scene_inputs
from panelforge.features.lab.stories_web import StoryCreate
from tests import test_story_workflow as workflow_fixture


class StoryQualityTest(unittest.TestCase):
    setUp = workflow_fixture.StoryWorkflowTest.setUp
    settle = workflow_fixture.StoryWorkflowTest.settle
    advance = workflow_fixture.StoryWorkflowTest.advance

    def create(self, mode="automatic", count=1, **changes):
        fields = dict(brief="Un cireur demande à Piccolo de rendre le portefeuille.", narrative_format="long",
            writing_edition_id="experimental-2026-09-27",
            long_options=dict(profile="auto", delivery="continuous", narration="auto", ending_type="auto", unit_count=count),
            workflow_mode=mode, visual_universe="Humains réalistes et Piccolo en prises de vues réelles",
            architect_model_id="local::qwen-fixture", writer_model_id="local::qwen-fixture")
        fields.update(changes)
        return self.service.create(**fields)

    def operations(self):
        return [json.loads(item.user_prompt)["operation"] for item in self.gateway.requests]

    def test_new_single_sequence_has_three_calls_and_a_real_final_review(self):
        project = self.advance(self.create())
        self.assertEqual(project["workflow"]["status"], "ready", project["job"].get("error"))
        self.assertEqual(self.operations(), ["compose", "develop", "review_block"])
        self.assertNotIn("outline", project["document"]["reviews"])  # No invented LLM review.
        self.assertTrue(narrative.review_current(project, "episode-1"))
        self.assertTrue(project["long_status"]["fabrication_ready"])
        self.assertEqual(project["llm_usage"]["calls"], 3)
        self.assertTrue(all(r.model_id == "local::qwen-fixture" for r in self.gateway.requests))
        self.assertTrue(all(r.max_tokens == 80000 for r in self.gateway.requests))

    def test_gemma_writer_is_used_only_for_writing_and_corrections(self):
        self.advance(self.create(writer_model_id="local::gemma-fixture"))
        self.assertEqual([r.model_id for r in self.gateway.requests],
            ["local::qwen-fixture", "local::gemma-fixture", "local::qwen-fixture"])

    def test_manual_keeps_both_author_checkpoints(self):
        project = self.advance(self.create("manual"))
        self.assertEqual(self.operations(), ["compose"])
        self.assertEqual(project["workflow"]["wait_target"], "outline")
        project = self.advance(project)
        self.assertEqual(self.operations(), ["compose", "develop", "review_block"])
        self.assertEqual(project["workflow"]["wait_target"], "episode-1")
        project = self.advance(project)
        self.assertEqual(project["workflow"]["status"], "ready")
        self.assertEqual(len(self.gateway.requests), 3)

    def test_existing_policy_retains_outline_edit_and_four_calls(self):
        project = self.advance(self.create(story_quality_version=0))
        self.assertNotIn("story_quality_version", project)
        self.assertEqual(self.operations(), ["compose", "edit_outline", "develop", "review_block"])
        self.assertTrue(narrative.review_current(project, "outline"))

    def test_two_units_are_written_then_reviewed_together(self):
        project = self.advance(self.create(count=2))
        self.assertEqual(self.operations(), ["compose", "develop", "develop", "review_block"])
        self.assertTrue(all(unit["ready"] for unit in project["long_status"]["units"].values()))

    def test_large_estimate_alone_does_not_spend_a_repair_call(self):
        self.gateway.overlong = True
        project = self.advance(self.create())
        self.assertEqual(self.operations(), ["compose", "develop", "review_block"])
        estimates = [item for item in project["diagnostics"] if item["code"] == "clip_load"]
        self.assertTrue(estimates)
        self.assertTrue(all(item["level"] == "warning" for item in estimates))
        self.assertEqual(project["workflow"]["status"], "ready")
        self.assertEqual(len(project["document"]["scenario"]["scenes"][0]["dialogue"][0]["text"].split()), 60)

    def test_estimate_category_is_advisory_even_when_model_calls_it_blocking(self):
        project = self.advance(self.create())
        review = dict(summary="Trop de paroles selon le calcul.", issues=[dict(category="speech_estimate",
            severity="blocking", target_id="scene-1", problem="Calcul trop long.", suggestion="Raccourcir.")])
        parsed = narrative.validate_review(project, review, "episode-1")
        self.assertEqual(parsed["issues"][0]["severity"], "warning")
        review["issues"][0]["category"] = "fidelity"
        self.assertEqual(narrative.validate_review(project, review, "episode-1")["issues"][0]["severity"], "blocking")

    def test_actual_story_blocker_gets_only_one_automatic_correction(self):
        self.gateway.blocking = True
        project = self.advance(self.create())
        self.assertEqual(self.operations(), ["compose", "develop", "review_block", "repair_episode", "review_block"])
        self.assertEqual(project["workflow"]["status"], "blocked")
        self.assertEqual(len(self.gateway.requests), 5)
        project = self.advance(project)
        self.assertEqual(len(self.gateway.requests), 5)
        self.assertFalse(project["long_status"]["fabrication_ready"])

    def test_optional_arc_review_blocker_is_not_ignored(self):
        project = self.advance(self.create("manual"))
        review = narrative.validate_review(project, dict(summary="Lien manquant.", issues=[dict(category="clarity",
            severity="blocking", target_id="contract", problem="Lien manquant.", suggestion="Préciser le lien.")]), "outline")
        project["document"]["reviews"]["outline"] = review
        self.assertFalse(narrative.outline_ready(project))
        project = self.advance(self.service.store.save(project))
        self.assertIn("edit_outline", self.operations())
        self.assertEqual(project["workflow"]["wait_target"], "episode-1")

    def test_reader_receives_public_obligations_but_not_future_secrets_or_lines(self):
        project = self.advance(self.create(count=2))
        outline = project["document"]["series_outline"]
        outline["secrets"] = [dict(id="secret-hidden", truth="SECRET-FUTUR-INVISIBLE", known_by=[], reveal_episode_id="episode-2")]
        outline["episodes"][0]["events"][0]["evidence"] = "Le cireur ordonne à Piccolo de rendre le portefeuille."
        outline["episodes"][1]["events"][0]["evidence"] = "RÉPLIQUE-FUTURE-EXACTE"
        project["writing_direction"]["protected_lines"] = ["RÉPLIQUE-FUTURE-EXACTE"]
        project["job"].update(operation="review_block", review_unit_ids=["episode-1"])
        req = request(project, self.service.long_recipes.snapshot(), "Français")
        context = json.loads(req.user_prompt)
        self.assertIn("ordonne", context["unit_requirements"][0]["required_on_screen"][0]["evidence"])
        self.assertNotIn("SECRET-FUTUR-INVISIBLE", req.user_prompt)
        self.assertNotIn("RÉPLIQUE-FUTURE-EXACTE", req.user_prompt)
        for key in ("brief", "secrets", "current_outline", "author_exact_lines", "future_reservations"):
            self.assertNotIn(key, context)
        self.assertEqual(context["speech_budget"]["words_per_second_estimate"], 4.8)

    def test_human_universe_avoids_fruit_pitch_and_naming_instructions(self):
        self.advance(self.create())
        for req in self.gateway.requests:
            context = json.loads(req.user_prompt)
            self.assertNotIn("concept_fields", context.get("visual_family", {}))
            self.assertNotIn("fruit_naming", context)
            self.assertNotIn("Bananito", req.system_prompt)
        writer = self.gateway.requests[1]
        self.assertIn("tracking=reference", writer.system_prompt)
        self.assertIn("Les accessoires banals restent textuels", writer.system_prompt)
        self.assertNotIn("portefeuille", writer.system_prompt)

    def test_exact_lines_are_checked_but_style_examples_are_not(self):
        project = self.advance(self.create())
        line = "Je vais me payer des putes."
        project["writing_direction"].update(protected_lines=[line], dialogue_notes="Exemple de ton : wesh, rends ça.")
        issues = project_quality(project, "episode-1")
        self.assertTrue(any(i["code"] == "required_dialogue_missing" and i["level"] == "blocking" for i in issues))
        scenario = project["document"]["episode_scenarios"]["episode-1"]
        scenario["scenes"][0]["dialogue"].append(dict(speaker_id=scenario["characters"][0]["id"], text=line))
        self.assertFalse(any(i["code"] == "required_dialogue_missing" for i in project_quality(project, "episode-1")))
        self.assertFalse(any("wesh" in i["message"] for i in project_quality(project, "episode-1")))

    def test_fast_budget_and_render_are_carried_to_h3_and_custom_style_wins(self):
        project = self.advance(self.create(writing_direction=dict(dialogue_pace="fast", visual_render="live_action")))
        episode = initial_episode(project, "episode-" + "a" * 32)
        self.assertIn("prises de vues réelles", episode["style"])
        scene = episode["scenes"][0]
        if not episode["scenario"]["scenes"][0]["dialogue"]:
            speaker = episode["scenario"]["characters"][0]["id"]
            episode["scenario"]["scenes"][0]["dialogue"] = [dict(speaker_id=speaker, text="Rends le portefeuille.")]
        inputs = scene_inputs(episode, scene, require_images=False)
        self.assertIn("4,8 mots/s", inputs["source_text"])
        self.assertIn("prises de vues réelles", inputs["source_text"])
        episode["style"] = "Direction personnelle en noir et blanc."
        self.assertIn(episode["style"], scene_inputs(episode, scene, require_images=False)["source_text"])
        self.assertNotIn("Direction visuelle commune : Film", scene_inputs(episode, scene, require_images=False)["source_text"])

    def test_same_text_uses_selected_rate_and_new_natural_mode_stays_advisory(self):
        project = self.advance(self.create())
        scenario = deepcopy(project["document"]["scenario"])
        scenario["scenes"][0]["dialogue"] = [dict(text=" ".join(["mot"] * 27))]
        state = dict(scene_events=[dict(scene_index=0, action_seconds=3)])
        self.assertFalse(any(i["code"] == "clip_load" for i in quality_issues(project, scenario=scenario, state=state, target="episode-1")))
        project["writing_direction"]["dialogue_pace"] = "natural"
        load = next(i for i in quality_issues(project, scenario=scenario, state=state, target="episode-1") if i["code"] == "clip_load")
        self.assertEqual(load["estimated_seconds"], 14.2)
        self.assertEqual(load["level"], "warning")
        project.pop("story_quality_version")
        load = next(i for i in quality_issues(project, scenario=scenario, state=state, target="episode-1") if i["code"] == "clip_load")
        self.assertEqual(load["level"], "warning")  # Legacy threshold remains 3.5 words/s, not 2.4.

    def test_sequel_preserves_direction_without_replaying_old_exact_lines(self):
        project = self.create(writing_direction=dict(dialogue_style="street", visual_render="live_action", protected_lines=["Ancienne réplique."]))
        inherited = direction.for_followup(project)
        self.assertEqual(inherited["dialogue_style"], "street")
        self.assertEqual(inherited["visual_render"], "live_action")
        self.assertEqual(inherited["protected_lines"], [])
        self.assertEqual(project["writing_direction"]["protected_lines"], ["Ancienne réplique."])

    def test_api_round_trip_and_validation(self):
        body = StoryCreate.model_validate(dict(narrative_format="long", writing_direction=dict(dialogue_pace="fast", visual_render="live_action")))
        self.assertEqual(body.model_dump()["writing_direction"]["visual_render"], "live_action")
        for bad in (dict(dialogue_pace="double"), dict(visual_render="photo2"), dict(protected_lines=[" "]), dict(unexpected=True)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                direction.normalize(bad)


if __name__ == "__main__":
    unittest.main()
