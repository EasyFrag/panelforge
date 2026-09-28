"""User-run v3 regressions. Synthetic stories only; no live model/media/service."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from panelforge.application.episode_state_images import EpisodeStateImages
from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.domain import story_contracts as contracts, story_continuity as ledger
from panelforge.domain import story_exact_lines as exact, story_history, long_stories as narrative
from panelforge.domain import story_reference_plan as references, story_visual_states
from panelforge.domain.episodes import initial_episode, scene_inputs
from panelforge.domain.stories import validate_scenario, response_contract
from panelforge.domain.story_diagnostics import quality_issues
from panelforge.domain.episode_continuity import variant_base, variant_source_ready
from panelforge.infrastructure.story_editions import StoryEditions
from tests.test_story_workflow import WorkflowGateway
from tests.test_story_quality_policy import StoryQualityTest

ROOT = Path(__file__).resolve().parents[1]
V3 = "experimental-2026-09-28"
V2 = "experimental-2026-09-27"
LINE = "Je vais me payer des putes."


class ReferenceGateway(WorkflowGateway):
    def stream(self, request):
        context = json.loads(request.user_prompt)
        for event in super().stream(request):
            if event.kind != StreamEventKind.COMPLETED:
                yield event
                continue
            value = json.loads(event.result.content)
            if context["operation"] == "compose" and context.get("author_lines"):
                outline = value["series_outline"]
                outline["author_line_assignments"] = [dict(line_id=row["id"],
                    unit_id=outline["episodes"][i % len(outline["episodes"])]["id"],
                    event_id=outline["episodes"][i % len(outline["episodes"])]["events"][0]["id"],
                    speaker_id=outline["characters"][0]["id"])
                    for i, row in enumerate(context["author_lines"])]
            if context["operation"] == "develop" and context.get("author_lines"):
                value["scenario"]["scenes"][0]["dialogue"] = [dict(speaker_id=row["speaker_id"],
                    line_ref=row["line_id"], delivery="spoken") for row in context["author_lines"]]
            yield CompletionStreamEvent(kind=StreamEventKind.COMPLETED, phase=StreamPhase.COMPLETED,
                result=CompletionResult(model_id="local::fixture", content=json.dumps(value), finish_reason="stop"))


class WritingV3Test(unittest.TestCase):
    settle = StoryQualityTest.settle
    advance = StoryQualityTest.advance
    create = StoryQualityTest.create

    def setUp(self):
        StoryQualityTest.setUp(self)
        self.gateway = ReferenceGateway()
        self.gateway.story_store = self.service.store
        self.service.gateway = self.gateway

    def written(self, *, protected=False, count=1):
        project = self.create(writing_edition_id=V3, count=count,
            writing_direction=dict(protected_lines=[LINE] if protected else []))
        project = self.advance(project)
        self.assertEqual(project["workflow"]["status"], "ready", project["job"].get("error"))
        return project

    def test_three_calls_and_source_text_hydrated_before_review(self):
        project = self.written(protected=True)
        calls = self.gateway.requests
        self.assertEqual([json.loads(r.user_prompt)["operation"] for r in calls], ["compose", "develop", "review_block"])
        self.assertTrue(all(r.max_tokens == 80000 for r in calls))
        self.assertTrue(all(r.operation_id.endswith("@2.5.0") for r in calls))
        writer = json.loads(calls[1].user_prompt)
        self.assertNotIn("author_exact_lines", writer)
        self.assertNotIn("protected_lines", writer["unit_requirements"])
        line = project["document"]["scenario"]["scenes"][0]["dialogue"][0]
        self.assertEqual(line["text"], LINE)
        self.assertTrue(line["dialogue_id"].startswith("author-line-"))
        self.assertNotIn("line_ref", line)
        reader = json.loads(calls[-1].user_prompt)
        self.assertEqual(reader["reader_units"][0]["scenes"][0]["dialogue"][0]["text"], LINE)
        episode = initial_episode(project, "episode-" + "c" * 32)
        self.assertIn(LINE, scene_inputs(episode, episode["scenes"][0], require_images=False)["source_text"])

    def test_assignments_are_scoped_and_source_edits_are_rejected(self):
        project = self.written(protected=True, count=2)
        self.assertEqual(exact.for_unit(project, "episode-2"), [])
        outline = project["document"]["series_outline"]
        bad = deepcopy(outline)
        bad["author_line_assignments"][0]["event_id"] = bad["episodes"][1]["events"][0]["id"]
        with self.assertRaises(ValueError):
            exact.validate_assignments(project, bad)
        bad = deepcopy(outline)
        bad["author_line_assignments"].append(deepcopy(bad["author_line_assignments"][0]))
        with self.assertRaises(ValueError):
            exact.validate_assignments(project, bad)
        project["writing_direction"]["protected_lines"] = [LINE.replace("payer", "paye")]
        with self.assertRaisesRegex(ValueError, "périmée"):
            exact.for_unit(project, "episode-1")

    def test_source_edit_can_be_reassigned_through_existing_outline_patch(self):
        project = self.written(protected=True)
        previous = deepcopy(project["document"]["series_outline"])
        project["writing_direction"]["protected_lines"] = ["Nouvelle réplique décidée par l’auteur."]
        project["job"].update(operation="edit_outline")
        row = dict(previous["author_line_assignments"][0], line_id=exact.catalog(project)[0]["id"])
        wire = dict(reply="Attribution actualisée.", base_hash=narrative.source_hash(project, "outline"),
            edits=[dict(path="outline/author_line_assignments", value=[row])],
            review=dict(summary="Réplique source actualisée.", issues=[]))
        self.assertEqual(contracts.structural_issues(wire, contracts.response_schema(project)), [])
        result = contracts.canonical_response(project, wire)
        self.assertEqual(narrative.validate_outline(project, result["series_outline"])["author_line_assignments"], [row])
        self.assertEqual(project["document"]["series_outline"], previous)

    def test_free_text_cannot_spoof_protected_source_and_reference_has_speaker(self):
        project = self.written(protected=True)
        scenario = deepcopy(project["document"]["scenario"])
        state = project["document"]["episode_states"]["episode-1"]
        scenario["scenes"][0]["dialogue"][0]["text"] = LINE.replace("payer", "paye")
        with self.assertRaisesRegex(ValueError, "reformulée"):
            exact.hydrate(project, scenario, state, "episode-1")
        scenario = deepcopy(project["document"]["scenario"])
        scenario["scenes"][0]["dialogue"][0].pop("dialogue_id")
        with self.assertRaisesRegex(ValueError, "manque"):
            exact.hydrate(project, scenario, state, "episode-1")
        scenario = deepcopy(project["document"]["scenario"])
        scenario["scenes"][0]["dialogue"][0]["speaker_id"] = "unknown"
        with self.assertRaisesRegex(ValueError, "attribution"):
            exact.hydrate(project, scenario, state, "episode-1")

    def test_null_memory_local_patch_keeps_state_and_source_guard(self):
        project = self.written(protected=True)
        project["job"].update(operation="repair_episode", feedback_target=dict(unit_id="episode-1"))
        previous = deepcopy(project["document"]["episode_states"]["episode-1"])
        wire = contracts.wire_example(project, {})
        self.assertIsNone(wire["episode_state"])
        parsed = contracts.canonical_response(project, wire)
        self.assertEqual(parsed["episode_state"], previous)
        self.assertEqual(validate_scenario(parsed["scenario"]), project["document"]["scenario"])
        wire["base_hash"] = "old"
        with self.assertRaises(contracts.StoryValidationError):
            contracts.canonical_response(project, wire)

    def test_language_only_repair_freezes_memory_but_narrative_edit_can_update(self):
        project = self.written()
        project["job"].update(operation="repair_episode", feedback_target=dict(unit_id="episode-1"))
        project["document"]["reviews"]["episode-1"]["issues"] = [dict(severity="blocking", category="dialogue_language")]
        schema = contracts.response_schema(project)
        self.assertEqual(schema["properties"]["episode_state"], {"type": "null"})
        wire = contracts.wire_example(project, {})
        parsed = contracts.canonical_response(project, wire)
        self.assertEqual(parsed["episode_state"], project["document"]["episode_states"]["episode-1"])
        project["document"]["reviews"]["episode-1"]["issues"][0]["category"] = "fidelity"
        self.assertIn("anyOf", contracts.response_schema(project)["properties"]["episode_state"])
        wire["episode_state"] = {k: deepcopy(v) for k,v in parsed["episode_state"].items() if k != "scene_events"}
        wire["episode_state"]["open_threads"].append("Question nouvelle explicitement écrite.")
        changed = contracts.canonical_response(project, wire)
        self.assertIn("Question nouvelle explicitement écrite.", changed["episode_state"]["open_threads"])

    def test_english_residue_in_internal_memory_is_only_advisory(self):
        project = self.written()
        state = deepcopy(project["document"]["episode_states"]["episode-1"])
        state["open_threads"] = ["They leave the house with their box because the owner was behind them."]
        rows = quality_issues(project, scenario=project["document"]["scenario"], state=state, target="episode-1")
        issue = next(row for row in rows if row["code"] == "language_residue" and "episode_state" in row["path"])
        self.assertEqual(issue["level"], "warning")

    def test_review_salvages_independent_object_and_keeps_character_identity(self):
        project = self.written()
        project["job"].update(operation="review_block", review_unit_ids=["episode-1"])
        obj = element("wallet", kind="object")
        bad = element("char-invented")
        response = dict(reviews=[dict(unit_id="episode-1", visual_patch=dict(
            base_hash=narrative.source_hash(project, "episode-1"), elements=[bad, obj]))])
        changes, warnings = story_visual_states.extract_review_patches(project, response)
        self.assertEqual([e["id"] for e in changes["episode-1"]["elements"]], ["wallet"])
        self.assertIn("episode-1", warnings)

    def test_assembled_sequel_request_deduplicates_history_and_removes_old_copy_rules(self):
        from panelforge.application.long_stories import request
        project = self.written()
        past = deepcopy(project["document"]["scenario"])
        past["scenes"][0]["action"] += " Geste déjà accompli dans l’épisode précédent." * 100
        project["prior_story"] = json.dumps(dict(latest_scenario=past, written_episodes=[]))
        project["document"]["prior_story_snapshot"] = deepcopy(past)
        project["job"].update(operation="develop")
        package = self.service.long_recipes.editions.get(V3)
        newer = request(project, package, "Langue : français.")
        project["job"].update(editorial_policy=2, response_contract_version="2.4.0")
        older = request(project, self.service.long_recipes.editions.get(V2), "Langue : français.")
        self.assertLess(len(newer.system_prompt) + len(newer.user_prompt), len(older.system_prompt) + len(older.user_prompt))
        context = json.loads(newer.user_prompt)
        self.assertIn("same_content_as", context["previous_episode_read_only"])
        self.assertIn("line_ref", newer.system_prompt)
        self.assertNotIn("citées exactement dans evidence", newer.system_prompt)
        self.assertNotIn("author_exact_lines", context)
        self.assertEqual(newer.max_tokens, older.max_tokens)

    def test_selected_v3_does_not_reinterpret_received_v2_job(self):
        from panelforge.domain.story_editions import refined
        project = self.written()
        project["job"].update(editorial_policy=2, response_contract_version="2.4.0")
        self.assertFalse(refined(project))
        self.assertEqual(project["writing_edition"]["id"], V3)


def scenario():
    value = response_contract("develop", False)["scenario"]
    value["characters"] = [dict(id="nino", name="Nino", description="Homme adulte."),
                           dict(id="sacha", name="Sacha", description="Femme adulte.")]
    value["scenes"][0].update(character_ids=["nino", "sacha"], dialogue=[])
    return value


def element(identity, *, kind="character", index=0, state_id="initial", appearance="Apparence stable."):
    return dict(id=identity, kind=kind, name=identity, description="Identité stable.", reason="Reconnaissance.",
                tracking="reference", scene_indices=[index], states=[dict(id=state_id, scene_index=index,
                    at="start", appearance=appearance, clothing=None, holder_id=None, reference=True)])


class PresenceAndVisualV3Test(unittest.TestCase):
    def test_silent_visible_person_keeps_presence_but_mentions_do_not_add_people(self):
        value = scenario()
        value["presence_policy"] = 1
        value["scenes"][0]["dialogue"] = [dict(speaker_id="nino", text="Sacha, regarde.", delivery="spoken")]
        normalized = validate_scenario(value)
        self.assertEqual(ledger.present_ids(normalized, 0), ["nino", "sacha"])
        value["scenes"][0]["character_ids"] = ["nino"]
        self.assertEqual(ledger.present_ids(validate_scenario(value), 0), ["nino"])

    def test_fabrication_references_follow_visible_people_not_speakers(self):
        value = scenario()
        value["presence_policy"] = 1
        value["scenes"][0]["dialogue"] = [dict(speaker_id="nino", text="Regarde.", delivery="spoken")]
        story = dict(project_id="synthetic-story", revisions=[dict(revision=1)], clip_seconds=10,
                     document=dict(scenario=value), visual_state_policy=2)
        episode = initial_episode(story, "synthetic-episode")
        visible = scene_inputs(episode, episode["scenes"][0], require_images=False)["references"]
        self.assertEqual({r["source_id"] for r in visible if r["kind"] == "character"}, {"nino", "sacha"})
        value["scenes"][0].update(character_ids=["nino"],
            dialogue=[dict(speaker_id="sacha", text="Je suis dehors.", delivery="off_screen")])
        episode = initial_episode(story, "synthetic-episode")
        inputs = scene_inputs(episode, episode["scenes"][0], require_images=False)
        self.assertEqual({r["source_id"] for r in inputs["references"] if r["kind"] == "character"}, {"nino"})
        self.assertIn("Je suis dehors.", inputs["source_text"])
        value["scenes"][0]["character_ids"] = []
        episode = initial_episode(story, "synthetic-episode")
        self.assertFalse(any(r["kind"] == "character" for r in scene_inputs(
            episode, episode["scenes"][0], require_images=False)["references"]))

    def test_offscreen_known_voice_is_not_a_visible_reference_or_unknown_voice(self):
        value = scenario()
        value["presence_policy"] = 1
        value["scenes"][0].update(character_ids=["nino"],
            dialogue=[dict(speaker_id="sacha", text="Je suis derrière la porte.", delivery="off_screen")])
        self.assertEqual(ledger.present_ids(validate_scenario(value), 0), ["nino"])
        for delivery in ("spoken", "unknown"):
            bad = deepcopy(value)
            bad["scenes"][0]["dialogue"][0]["delivery"] = delivery
            with self.assertRaises(ValueError): validate_scenario(bad)
        bad = deepcopy(value)
        bad["scenes"][0]["dialogue"][0]["speaker_id"] = "unknown"
        with self.assertRaises(ValueError): validate_scenario(bad)
        value.pop("presence_policy")
        with self.assertRaises(ValueError): validate_scenario(value)

    def test_late_inherited_sacha_is_idempotent_and_not_inserted_at_scene_zero(self):
        value = scenario()
        value["scenes"] = [deepcopy(value["scenes"][0]) for _ in range(5)]
        for scene in value["scenes"][:3]: scene["character_ids"] = ["nino"]
        identity = "inherited-9dc0436464755f52"
        old = element("sacha", state_id=identity, appearance="Boucles d'oreilles.")
        current = element("sacha", index=3, state_id=identity, appearance="Boucles d’oreilles.")
        current["scene_indices"] = [3,4]
        value["visual_continuity"] = dict(version=1, dramatic_summary="", elements=[current])
        previous = dict(elements=[old])
        result = ledger.inherit(value, previous)
        self.assertEqual(ledger.inherit(result, previous), result)
        states = result["visual_continuity"]["elements"][0]["states"]
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]["scene_index"], 3)
        self.assertEqual(states[0]["appearance"], old["states"][0]["appearance"])
        self.assertNotIn("sacha", ledger.present_ids(result, 0))
        self.assertIn("sacha", ledger.present_ids(result, 4))

    def test_conflicting_inherited_id_is_reported_without_losing_other_entities(self):
        value = scenario()
        bad = element("sacha", state_id="inherited-sacha", appearance="Robe rouge.")
        value["visual_continuity"] = dict(version=1, dramatic_summary="", elements=[bad])
        previous = dict(elements=[element("sacha", state_id="inherited-sacha", appearance="Robe verte."), element("wallet", kind="object")])
        result = ledger.inherit_independent(value, previous)
        self.assertEqual({e["id"] for e in result["visual_continuity"]["elements"]}, {"sacha", "wallet"})
        self.assertTrue(result["visual_continuity"]["warnings"])
        self.assertEqual(result["visual_continuity"]["elements"][0], bad)

    def test_partial_ledger_keeps_valid_wallet_without_guessing_character_suffix(self):
        value = scenario()
        original = dict(version=1, dramatic_summary="", elements=[element("nino-base"), element("wallet", kind="object")])
        saved = deepcopy(original)
        result, warning = ledger.salvage(original, value)
        self.assertEqual([e["id"] for e in result["elements"]], ["wallet"])
        self.assertIn("nino-base", warning)
        self.assertEqual(original, saved)

    def test_invalid_holder_and_duplicate_ids_keep_previous_valid_replacements(self):
        value = scenario()
        old = element("wallet", kind="object")
        previous = dict(version=1, dramatic_summary="", elements=[old])
        bad = deepcopy(old)
        bad["states"][0]["holder_id"] = "nino-base"
        result, warning = ledger.salvage(dict(version=1, dramatic_summary="", elements=[bad]), value, previous)
        self.assertEqual(result["elements"], [old])
        self.assertIn("Détenteur", warning)
        result, warning = ledger.salvage(dict(version=1, dramatic_summary="", elements=[bad, old]), value, previous)
        self.assertEqual(result["elements"], [old])
        self.assertIn("ambigu", warning)

    def test_schema_restricts_people_and_holders_objects_keep_separate_ids(self):
        schema = ledger.schema(1, character_ids=["nino", "sacha"])
        good = dict(version=1, dramatic_summary="", elements=[element("nino"), element("wallet", kind="object")])
        self.assertEqual(contracts.structural_issues(good, schema), [])
        good["elements"][0]["id"] = "nino-base"
        self.assertTrue(contracts.structural_issues(good, schema))
        good["elements"].pop(0)
        good["elements"][0]["states"][0]["holder_id"] = "nino-base"
        self.assertTrue(contracts.structural_issues(good, schema))
        collision = dict(version=1, dramatic_summary="", elements=[element("nino", kind="object")])
        with self.assertRaises(ValueError): ledger.normalize(collision, scenario())

    def test_typographic_inheritance_does_not_change_persistent_image_ids(self):
        straight = dict(appearance="Boucles d'oreilles", clothing=None)
        curly = dict(appearance="Boucles d’oreilles", clothing=None)
        self.assertEqual(references.inheritance_appearance_key(straight), references.inheritance_appearance_key(curly))
        self.assertNotEqual(references.appearance_key(straight), references.appearance_key(curly))
        self.assertNotEqual(references.image_id("sacha", straight), references.image_id("sacha", curly))
        self.assertNotEqual(references.inheritance_appearance_key(curly), references.inheritance_appearance_key(dict(appearance="Robe rouge")))

    def test_changed_carton_uses_existing_edit_source_without_selecting_an_image(self):
        target = dict(id="current-box", source_id="box", kind="object", name="Carton", image_asset_id=None,
                      description="Carton ouvert.", continuity_state_id=None,
                      continuity_appearance=dict(appearance="Carton ouvert.", clothing=None))
        source_ref = dict(id="previous-box", source_id="box", kind="object", name="Carton",
                          image_asset_id="validated-asset", continuity_appearance=dict(appearance="Carton fermé.", clothing=None))
        source = dict(episode_id="previous", visual_state_policy=2, scenario=scenario(), references=[source_ref])
        current = dict(visual_state_policy=2, continuity_version=1, scenario=scenario(), references=[target])
        current["scenario"]["presence_policy"] = 1
        current["scenario"]["visual_continuity"] = dict(version=1, dramatic_summary="", elements=[element("box",kind="object")])
        service = EpisodeStateImages()
        self.assertEqual(service._inherit_sparse_image(current, target, [(1, 0, "", False, source)]), 0)
        self.assertIsNone(target["image_asset_id"])
        self.assertTrue(service._is_state_image(current, target))
        self.assertTrue(variant_source_ready(current, target))
        self.assertEqual(variant_base(current, target)["image_asset_id"], "validated-asset")
        target["image_asset_id"] = "manual-import"
        before = deepcopy(target)
        service._inherit_sparse_image(current, target, [(1, 0, "", False, source)])
        self.assertEqual(target, before)


class HistoryAndArchiveV3Test(unittest.TestCase):
    def test_history_compaction_is_lossless_scoped_and_does_not_parse_dialogues(self):
        scene = dict(character_ids=["sacha"], dialogue=[dict(speaker_id="sacha", text='{"previous_history": "dialogue literal"}')], action="Action. " * 80)
        previous = dict(source_story_id="parent", latest_scenario=dict(scenes=[scene]),
                        written_episodes=[dict(unit_id="episode-1", state=dict(facts=["Fait acquis."]))])
        context = dict(previous_story_read_only=json.dumps(previous),
            previous_episode_read_only=deepcopy(previous["latest_scenario"]),
            story_id_scope=dict(current_project_id="child", previous_project_id="parent", current_unit_ids=["episode-1"]))
        before = deepcopy(context)
        result = story_history.compact(context)
        self.assertEqual(context, before)
        self.assertEqual(result["story_id_scope"], before["story_id_scope"])
        alias = result["previous_episode_read_only"]["same_content_as"]
        self.assertEqual(alias, "#/previous_story_read_only/latest_scenario")
        self.assertEqual(result["previous_story_read_only"]["latest_scenario"]["scenes"][0]["dialogue"], scene["dialogue"])
        self.assertLess(len(json.dumps(result)), len(json.dumps(context)))

    def test_catalogs_allow_loaded_legacy_reader_and_new_reader_to_coexist(self):
        folder = ROOT / "prompt_sources/story.long/2.0.0/editions"
        self.assertEqual(json.loads((folder / "catalog.json").read_text(encoding="utf-8"))["latest"], V2)
        archive = StoryEditions(folder)
        self.assertEqual(archive.catalog()["latest"], V3)
        self.assertEqual(archive.get()["policy_version"], 3)
        for row in archive.catalog()["editions"]:
            self.assertEqual(hashlib.sha256((folder / row["file"]).read_bytes()).hexdigest(), row["sha256"])
        for name, digest in {
            "experimental-2026-09-27.json": "bef8c25a969aadfc63d0594b0bdf426ba76b6193fa4f228793bf3fa5003b99f6",
            "reference-2026-09-27.json": "8d621abde56c4075f9044eef82a7503cd58ec4c1f5fdd5e064f5d49a38700df4",
        }.items():
            self.assertEqual(hashlib.sha256((folder / name).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
