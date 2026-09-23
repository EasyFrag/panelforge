"""User-run regressions for the Citron, silent Banane and Kiwina failure modes."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from panelforge.application.long_stories import request
from panelforge.domain import episode_continuity as production
from panelforge.domain import long_stories as narrative
from panelforge.domain import story_continuity as ledger
from panelforge.domain import story_contracts as contracts
from panelforge.domain.episodes import initial_episode, scene_inputs, fingerprint
from panelforge.domain.story_diagnostics import normalize_scene_state
from panelforge.infrastructure.long_story_recipes import LongStoryRecipes
from tests.test_episodes import SCENARIO

ROOT = Path(__file__).resolve().parents[1]


def change(identity, index=0, at="start", **values):
    return dict(id=identity, scene_index=index, at=at, appearance=values.get("appearance"),
                clothing=values.get("clothing"), holder_id=values.get("holder_id"), reference=values.get("reference", False))


def character():
    return dict(id="c1", kind="character", name="Citron", description="Citron jaune adulte, visage reconnaissable.",
        reason="Sa transformation persiste après le clip.", tracking="reference", scene_indices=[0, 1, 2], states=[
            change("initial", appearance="Silhouette fine", clothing="Débardeur bleu intact"),
            change("muscles", 1, "end", appearance="Carrure très musclée", clothing="Débardeur bleu déchiré", reference=True)])


def scenario():
    result = deepcopy(SCENARIO)
    result["characters"][0]["name"] = "Citron"
    result["characters"][1]["name"] = "Banane"
    result["scenes"] = [deepcopy(result["scenes"][0]) for _ in range(3)]
    for i, scene in enumerate(result["scenes"]):
        scene.update(title=f"Scène {i + 1}", action="Citron prend la main de Banane.", dialogue=[])
    result["visual_continuity"] = dict(version=1, dramatic_summary="Un rapprochement devient réciproque.", elements=[character()])
    return result


def fabrication(source=None):
    story = dict(project_id="story-" + "a" * 32, clip_seconds=10,
        document=dict(scenario=source or scenario()), revisions=[dict(revision=1)])
    result = initial_episode(story, "episode-" + "b" * 32)
    for ref in result["references"]:
        ref["image_asset_id"] = "image-" + ref["id"]
    return result


class VisualContinuityTest(unittest.TestCase):
    def test_end_transformation_applies_to_next_clip_without_replaying_it(self):
        value = fabrication()
        during, following = value["scenes"][1:]
        first = scene_inputs(value, during)
        second = scene_inputs(value, following)
        variant = ledger.reference_id("c1", "muscles")
        self.assertIn("Silhouette fine", first["source_text"])
        self.assertIn("Changement raconté dans ce clip", first["source_text"])
        self.assertEqual(sum(r["source_id"] == "c1" for r in second["references"]), 1)
        self.assertEqual(next(r["reference_id"] for r in second["references"] if r["source_id"] == "c1"), variant)
        self.assertIn("Débardeur bleu déchiré", second["source_text"])
        self.assertIn("Ne rejoue pas cette acquisition", second["source_text"])
        self.assertNotIn("Changement raconté dans ce clip", second["source_text"])
        self.assertNotEqual(during["references"][0]["reference_id"], variant)  # Derived, never pinned by a read.

    def test_a_body_only_change_keeps_torn_clothing_and_the_closest_visual_anchor(self):
        value = character()
        value["states"].append(change("larger", 2, appearance="Épaules encore plus larges"))
        state = ledger.state_at(value, 2)
        self.assertEqual(state["clothing"], "Débardeur bleu déchiré")
        self.assertEqual(state["reference_state_id"], "muscles")
        following = scenario()
        following["visual_continuity"]["elements"] = [value]
        inherited = ledger.carry_forward(following)
        next_episode = scenario()
        next_episode["visual_continuity"] = ledger.empty()
        restored = ledger.inherit(next_episode, inherited)
        opening = ledger.state_at(restored["visual_continuity"]["elements"][0], 0)
        self.assertEqual(opening["appearance"], "Épaules encore plus larges")
        self.assertEqual(opening["clothing"], "Débardeur bleu déchiré")

    def test_distinct_objects_are_not_merged_and_only_the_anchor_needs_an_image(self):
        source = scenario()
        invention = dict(id="invention", kind="object", name="Invention de Kiwina",
            description="Disque vert plat, rainure dorée unique.", reason="Reconnaître l'objet volé.",
            tracking="reference", scene_indices=[0, 1], states=[change("intact", appearance="Disque intact", holder_id="c1"),
                change("stolen", 1, "end", holder_id="c3")])
        chip = dict(id="chip", kind="object", name="Puce cassée", description="Petit fragment électronique gris.",
            reason="L'objet reçu en échange est différent.", tracking="text", scene_indices=[1, 2],
            states=[change("broken", 1, appearance="Fragment cassé", holder_id="c1"), change("dropped", 2, holder_id="none")])
        source["visual_continuity"]["elements"] = [invention, chip]
        value = fabrication(source)
        objects = [r for r in value["references"] if r["kind"] == "object"]
        self.assertEqual([r["source_id"] for r in objects], ["invention"])
        ids = [r["reference_id"] for r in production.bindings(value, value["scenes"][1])]
        self.assertIn(objects[0]["id"], ids)
        self.assertNotIn(objects[0]["id"], [r["reference_id"] for r in production.bindings(value, value["scenes"][2])])
        self.assertEqual(ledger.state_at(invention, 2)["holder_id"], "c3")
        self.assertEqual(ledger.state_at(chip, 2)["holder_id"], "none")

    def test_silent_presence_requires_an_explicit_declaration_not_name_guessing(self):
        source = scenario()
        source["scenes"][1]["character_ids"].remove("c2")
        self.assertEqual([c["id"] for c in ledger.missing_mentions(source, 1)], ["c2"])
        banane = deepcopy(character())
        banane.update(id="c2", name="Banane", tracking="text", states=[change("pink", clothing="Haut rose et jean bleu")])
        source["visual_continuity"]["elements"].append(banane)
        value = fabrication(source)
        images = scene_inputs(value, value["scenes"][1])["references"]
        self.assertEqual(sum(r["source_id"] == "c2" for r in images), 1)
        self.assertEqual(ledger.missing_mentions(source, 1), [])

    def test_ignoring_a_tracked_element_archives_the_card_but_preserves_its_image(self):
        value = fabrication()
        variant_id = ledger.reference_id("c1", "muscles")
        previous = next(r for r in value["references"] if r["id"] == variant_id)["image_asset_id"]
        value["scenario"]["visual_continuity"]["elements"][0]["enabled"] = False
        production.sync_references(value, "model")
        archived = next(r for r in value["references"] if r["id"] == variant_id)
        self.assertTrue(archived["continuity_archived"])
        self.assertEqual(archived["image_asset_id"], previous)
        self.assertNotIn(variant_id, [b["reference_id"] for b in production.bindings(value, value["scenes"][2])])

    def test_existing_fabrication_inputs_are_unchanged_until_explicit_activation(self):
        source = scenario(); source.pop("visual_continuity")
        value = fabrication(source)
        original = fingerprint(scene_inputs(value, value["scenes"][0]))
        value["scenario"]["visual_continuity"] = scenario()["visual_continuity"]
        production.sync_references(value, "model")
        self.assertEqual(original, fingerprint(scene_inputs(value, value["scenes"][0])))
        self.assertNotIn("continuity_version", value)
        self.assertEqual(ledger.normalize(ledger.empty(), source), ledger.empty())

    def test_changed_visual_anchor_requires_a_new_explicit_image_choice(self):
        value = fabrication()
        value["scenario"]["visual_continuity"]["elements"][0]["states"][1]["clothing"] = "Veste rouge neuve"
        production.sync_references(value, "model")
        with self.assertRaisesRegex(ValueError, "Confirmez ou remplacez"):
            scene_inputs(value, value["scenes"][2])
        # Review and editing remain available even while the new image is missing.
        self.assertIn("Veste rouge neuve", scene_inputs(value, value["scenes"][2], require_images=False)["source_text"])

    def test_explicit_variant_does_not_send_the_initial_body_as_a_second_person(self):
        value = fabrication()
        variant = ledger.reference_id("c1", "muscles")
        scene = value["scenes"][2]
        scene["references"].append(dict(reference_id=variant, role="subject_reference"))
        selected = scene_inputs(value, scene)["references"]
        self.assertEqual([r["reference_id"] for r in selected if r["source_id"] == "c1"], [variant])


class VisualContinuityContractTest(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((ROOT / "tests/fixtures/long_stories/development_failures_2026_09_22.json").read_text(encoding="utf-8"))

    def wire(self, version):
        project = deepcopy(self.fixture["project"])
        project["job"]["response_contract_version"] = version
        value = json.loads(self.fixture["reaction_draft"])
        value["episode_state"], _ = normalize_scene_state(project, value["scenario"], value["episode_state"])
        return project, contracts.wire_example(project, value)

    def test_archived_v21_and_new_v22_remain_recoverable_without_a_ledger(self):
        for version in ("2.1.0", contracts.VERSION):
            with self.subTest(version=version):
                project, value = self.wire(version)
                value["scenario"].pop("visual_continuity", None)
                self.assertEqual(contracts.structural_issues(value, contracts.response_schema(project)), [])
                _, parsed = narrative.parse(project, value)
                self.assertEqual("visual_continuity" in parsed["scenario"], version == contracts.VERSION)

    def test_new_ledger_survives_local_scene_correction_without_model_copies(self):
        project, value = self.wire(contracts.VERSION)
        value["scenario"]["visual_continuity"] = dict(version=1, dramatic_summary="Le public comprend le mensonge.", elements=[])
        _, parsed = narrative.parse(project, value); narrative.apply_document(project, parsed)
        project["job"].update(operation="revise", feedback_target=dict(unit_id="episode-1", scene_index=4))
        edit = contracts.wire_example(project, {})
        edit.pop("visual_continuity")
        edit["scene_edits"][0]["scene"]["action"] += " Il sourit."
        _, changed = narrative.parse(project, edit)
        self.assertEqual(changed["scenario"]["visual_continuity"], parsed["scenario"]["visual_continuity"])

    def test_invalid_optional_visual_metadata_does_not_discard_the_story_or_change_received_draft(self):
        for malformed in ({"unexpected": "field"}, {"version": 1, "dramatic_summary": "", "elements": [character()]}):
            with self.subTest(malformed=malformed):
                project, value = self.wire(contracts.VERSION)
                value["scenario"]["visual_continuity"] = malformed
                original = deepcopy(value)
                _, parsed = narrative.parse(project, value)
                visual = parsed["scenario"]["visual_continuity"]
                self.assertTrue(visual["warnings"])
                self.assertEqual(visual["elements"], [])
                self.assertEqual(value, original)
                self.assertEqual(parsed["scenario"]["scenes"][0]["action"], original["scenario"]["scenes"][0]["action"])

    def test_spectator_review_sees_words_and_actions_without_privileged_conclusions(self):
        project, value = self.wire(contracts.VERSION)
        _, parsed = narrative.parse(project, value); narrative.apply_document(project, parsed)
        project["brief"] = "PRIVILEGED_BRIEF"
        project["prior_story"] = "OLD_COMMAND_DO_NOT_REPLAY"
        project["document"]["series_outline"]["secrets"][0]["truth"] = "PRIVILEGED_SECRET"
        unit = project["document"]["selected_episode_id"]
        saved = project["document"]["episode_scenarios"][unit]
        saved["logline"] = "PRIVILEGED_LOGLINE"
        saved["scenes"][0]["ending_state"] = "PRIVILEGED_CONCLUSION"
        saved["visual_continuity"]["dramatic_summary"] = "PRIVILEGED_LEDGER"
        project["job"].update(operation="review_episode")
        package = LongStoryRecipes(ROOT / "prompt_sources/story.long/2.0.0").snapshot()
        context = json.loads(request(project, package, "Français").user_prompt)
        self.assertIn("reader_units", context)
        self.assertEqual(context["reader_units"][0]["scenes"][0]["dialogue"], saved["scenes"][0]["dialogue"])
        self.assertNotIn("PRIVILEGED", json.dumps(context))
        self.assertNotIn("OLD_COMMAND_DO_NOT_REPLAY", json.dumps(context))
        self.assertNotIn("episode_state", context)


if __name__ == "__main__":
    unittest.main()
