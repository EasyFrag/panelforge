"""User-run regressions for the Fraisette audit. No model, GPU or live workspace."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from panelforge.application.episode_state_images import EpisodeStateImages
from panelforge.application.long_stories import request
from panelforge.domain import story_continuity as ledger, episode_continuity as production
from panelforge.domain import story_contracts as contracts, long_stories as narrative
from panelforge.domain.episodes import initial_episode, scene_inputs
from panelforge.domain.stories import visual_transition_instruction
from panelforge.infrastructure.long_story_recipes import LongStoryRecipes
from tests.test_episodes import SCENARIO
from tests import test_story_visual_continuity as visual_fixtures
from tests import test_required_state_images as state_fixtures

change = visual_fixtures.change

ROOT = Path(__file__).resolve().parents[1]


def fraisette():
    result = deepcopy(SCENARIO)
    result["characters"] = [dict(id="c1", name="Fraisette", description="Fraise adulte qui portera une grossesse visible."),
                            dict(id="c2", name="Pomito", description="Pomme adulte.")]
    template = result["scenes"][0]
    template.update(character_ids=["c1", "c2"], dialogue=[], action="Ils se prennent la main.")
    result["scenes"] = [deepcopy(template) for _ in range(3)]
    elements = []
    for identity, name in (("c1", "Fraisette"), ("c2", "Pomito")):
        states = []
        for index in range(3):
            body = "Silhouette fine" if identity == "c1" and index == 0 else "Ventre arrondi" if identity == "c1" else "Forme de pomme"
            for at in ("start", "end"):
                states.append(change(f"{identity}-{index}-{at}", index, at,
                    appearance=body, clothing="Robe bleue" if identity == "c1" else None, reference=True))
        elements.append(dict(id=identity, kind="character", name=name,
            description="Fraise rouge adulte." if identity == "c1" else "Pomme rouge adulte.",
            reason="Raccord visuel.", tracking="reference", scene_indices=[0, 1, 2], states=states))
    result["visual_continuity"] = dict(version=1, dramatic_summary="Un couple attend un bébé.", elements=elements)
    return result


def episode(source=None, policy=2, images=True):
    story = dict(project_id="story-" + "a" * 32, clip_seconds=10, visual_state_policy=policy,
        document=dict(scenario=source or fraisette()), revisions=[dict(revision=1)])
    value = initial_episode(story, "episode-" + "b" * 32)
    if images:
        for ref in value["references"]:
            ref["image_asset_id"] = "image-" + ref["id"]
    return value


class SparseReferenceTest(unittest.TestCase):
    def test_twelve_state_anchors_create_one_shared_variant(self):
        value = episode()
        self.assertEqual(len(value["references"]), 4)
        variants = [r for r in value["references"] if r.get("continuity_state_id")]
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0]["source_id"], "c1")
        selected = [[r["reference_id"] for r in scene_inputs(value, scene)["references"] if r["source_id"] == "c1"]
                    for scene in value["scenes"]]
        self.assertEqual(selected, [["character-1"], [variants[0]["id"]], [variants[0]["id"]]])
        self.assertEqual(len(value["scenario"]["visual_continuity"]["elements"][0]["states"]), 6)

    def test_base_prompt_uses_first_appearance_not_the_future_biography(self):
        base = episode()["references"][0]
        self.assertIn("Silhouette fine", base["description"])
        self.assertIn("Robe bleue", base["description"])
        self.assertNotIn("portera une grossesse", base["description"])

    def test_legacy_policy_keeps_all_anchors_and_original_identity(self):
        legacy = episode(policy=1)
        self.assertEqual(len(legacy["references"]), 15)
        self.assertIn("portera une grossesse", legacy["references"][0]["description"])
        self.assertEqual(production.required_bindings(legacy, legacy["scenes"][1])[0],
                         ledger.reference_id("c1", "c1-1-start"))

    def test_return_to_initial_body_reuses_base_and_minor_changes_keep_anchor(self):
        source = fraisette()
        entry = source["visual_continuity"]["elements"][0]
        entry["states"] = [entry["states"][0], entry["states"][2],
            change("return", 2, appearance="silhouette   fine", clothing="Robe bleue", reference=True)]
        value = episode(source)
        self.assertEqual(production.desired_reference(value, "c1", 2), "character-1")
        entry["states"][-1] = change("minor", 2, appearance="Ventre rond, robe plissée", reference=False)
        value = episode(source)
        self.assertEqual(production.desired_reference(value, "c1", 1), production.desired_reference(value, "c1", 2))

    def test_unused_final_and_invisible_states_do_not_request_images(self):
        source = fraisette()
        source["visual_continuity"]["elements"][0]["states"][-1].update(appearance="Nouvelle apparence finale")
        value = episode(source)
        self.assertEqual(len(value["references"]), 4)
        self.assertEqual(ledger.carry_forward(source)["elements"][0]["states"][0]["appearance"], "Nouvelle apparence finale")
        source["visual_continuity"]["elements"][0]["scene_indices"] = [0]
        value = episode(source)
        self.assertFalse([r for r in value["references"] if r.get("continuity_state_id")])

    def test_missing_shared_variant_blocks_both_uses_but_not_initial_scene(self):
        value = episode()
        variant = next(r for r in value["references"] if r.get("continuity_state_id"))
        variant["image_asset_id"] = None
        scene_inputs(value, value["scenes"][0])
        for scene in value["scenes"][1:]:
            with self.assertRaises(production.RequiredReferenceMissing):
                scene_inputs(value, scene)

    def test_reference_ids_survive_state_renaming_and_keep_author_image_choice(self):
        value = episode()
        variant = next(r for r in value["references"] if r.get("continuity_state_id"))
        chosen = variant["image_asset_id"]
        for element in value["scenario"]["visual_continuity"]["elements"]:
            for state in element["states"]:
                state["id"] = "renamed-" + state["id"]
        production.sync_references(value, "fixture")
        self.assertEqual(variant["image_asset_id"], chosen)
        self.assertFalse(variant.get("continuity_archived"))
        self.assertEqual(production.desired_reference(value, "c1", 2), variant["id"])

    def test_author_change_archives_old_variant_without_deleting_its_media(self):
        value = episode()
        old = next(r for r in value["references"] if r.get("continuity_state_id"))
        chosen = old["image_asset_id"]
        for state in value["scenario"]["visual_continuity"]["elements"][0]["states"][2:]:
            state["clothing"] = "Robe rose"
        production.sync_references(value, "fixture")
        self.assertTrue(old["continuity_archived"])
        self.assertEqual(old["image_asset_id"], chosen)
        self.assertNotEqual(production.desired_reference(value, "c1", 1), old["id"])

    def test_distinct_objects_are_not_merged_and_ownership_does_not_change_image(self):
        source = fraisette()
        for identity in ("phone-a", "phone-b"):
            source["visual_continuity"]["elements"].append(dict(id=identity, kind="object", name="Téléphone",
                description="Téléphone rouge.", reason="Objet transmis.", tracking="reference", scene_indices=[0, 1],
                states=[change("start", appearance="Coque rouge", holder_id="c1", reference=True),
                        change("transfer", 1, holder_id="c2", reference=True)]))
        value = episode(source)
        objects = [r for r in value["references"] if r["kind"] == "object"]
        self.assertEqual(len(objects), 2)
        self.assertNotEqual(objects[0]["id"], objects[1]["id"])
        self.assertTrue(all(not r.get("continuity_state_id") for r in objects))

    def test_changed_initial_appearance_requires_explicit_reselection(self):
        value = episode()
        value["scenario"]["visual_continuity"]["elements"][0]["states"][0]["clothing"] = "Robe verte"
        production.sync_references(value, "fixture")
        self.assertTrue(value["references"][0]["continuity_image_stale"])
        with self.assertRaises(production.RequiredReferenceMissing):
            scene_inputs(value, value["scenes"][0])

    def test_inheritance_uses_matching_acquired_state_not_old_identity(self):
        source = episode()
        target_source = fraisette()
        for state in target_source["visual_continuity"]["elements"][0]["states"]:
            state["appearance"] = "Ventre arrondi"
        target_episode = episode(target_source, images=False)
        target = target_episode["references"][0]
        service = SimpleNamespace(_identity_key=lambda text: text.casefold())
        count = EpisodeStateImages._inherit_sparse_image(service, target_episode, target, [(2, 1, "now", True, source)])
        variant = next(r for r in source["references"] if r.get("continuity_state_id"))
        self.assertEqual(count, 1)
        self.assertEqual(target["image_asset_id"], variant["image_asset_id"])
        variant["image_asset_id"] = None
        target["image_asset_id"] = None
        self.assertEqual(EpisodeStateImages._inherit_sparse_image(service, target_episode, target, [(2, 1, "now", True, source)]), 0)


class SparseQueueTest(unittest.TestCase):
    create = state_fixtures.RequiredStateImagesTest.create
    image = state_fixtures.RequiredStateImagesTest.image
    start = state_fixtures.RequiredStateImagesTest.start

    def setUp(self):
        state_fixtures.RequiredStateImagesTest.setUp(self)
        self.story["visual_state_policy"] = 2
        self.story["document"]["scenario"] = fraisette()
        self.story["revisions"][0]["document"] = deepcopy(self.story["document"])
        self.story = self.stories.store.save(self.story)

    def test_one_qwen_attempt_serves_both_scenes_without_prompt_llm(self):
        value = self.create()
        self.assertEqual(len(value["references"]), 4)
        for ref in value["references"]:
            if not ref.get("continuity_state_id"):
                value = self.image(value, ref)
        value = self.start(value)
        self.assertEqual(len(value["reference_batch"]["items"]), 1)
        self.assertEqual(len(self.qwen.queued), 1)
        self.assertEqual(self.krea.calls, [])
        item = value["reference_batch"]["items"][0]
        ref = next(r for r in value["references"] if r["id"] == item["reference_id"])
        selected = self.service.select_image(value["episode_id"], ref["id"], ref["revision"], item["output_asset_id"])
        for scene in selected["scenes"][1:]:
            images = scene_inputs(selected, scene)["references"]
            chosen = next(r for r in images if r["source_id"] == "c1")
            self.assertEqual(chosen["asset_id"], item["output_asset_id"])
        self.service.get(value["episode_id"])
        self.assertEqual(len(self.qwen.queued), 1)


    def test_qwen_waits_for_a_stale_identity_to_be_revalidated(self):
        value = self.create()
        for ref in value["references"]:
            if not ref.get("continuity_state_id"):
                value = self.image(value, ref)
        stored = self.service.store.get(value["episode_id"])
        stored["references"][0]["continuity_image_stale"] = True
        self.service.store.save(stored)
        value = self.start(self.service.get(value["episode_id"]))
        self.assertEqual(value["reference_batch"]["items"][0]["status"], "waiting_source")
        self.assertEqual(self.qwen.queued, [])
        value = self.image(value, value["references"][0])
        self.assertEqual(len(self.qwen.queued), 1)
        self.assertEqual(value["reference_batch"]["items"][0]["status"], "ready_for_review")


class SparsePromptTest(unittest.TestCase):
    setUp = visual_fixtures.VisualContinuityContractTest.setUp
    wire = visual_fixtures.VisualContinuityContractTest.wire

    def reader(self, version="2.4.0"):
        project, value = self.wire(version)
        project["visual_state_policy"] = 2
        _, parsed = narrative.parse(project, value)
        narrative.apply_document(project, parsed)
        project["job"].update(operation="review_block", review_unit_ids=["episode-1"])
        return project

    def test_review_has_one_role_resolved_states_and_no_privileged_facts(self):
        project = self.reader()
        scenario = project["document"]["episode_scenarios"]["episode-1"]
        scenario["visual_continuity"]["dramatic_summary"] = "PRIVILEGED_RESULT"
        character = scenario["characters"][0]
        scenario["visual_continuity"]["elements"] = [dict(id=character["id"], kind="character", name=character["name"],
            description="PRIVILEGED_DESCRIPTION", reason="PRIVILEGED_REASON", tracking="reference", scene_indices=[0],
            states=[change("first", appearance="Veste bleue", reference=True)])]
        scenario["scenes"][0]["visual_transition"] = dict(before="Fin", after="Musclé", trigger="Ellipse",
            visible_change="Muscles", timing="between_scenes")
        package = LongStoryRecipes(ROOT / "prompt_sources/story.long/2.0.0").snapshot()
        current = request(project, package, "Français", "Consigne pour écrire de NOUVELLES répliques")
        data = json.loads(current.user_prompt)
        self.assertNotIn("PRIVILEGED", current.user_prompt)
        self.assertIn("scene_states", data["visual_state_review"][0])
        self.assertEqual(data["reader_units"][0]["scenes"][0]["visual_transition"]["timing"], "between_scenes")
        self.assertNotIn("response_contract", data)
        self.assertEqual(data["response_schema"], current.output_schema)
        self.assertNotIn("NOUVELLES", current.system_prompt)
        self.assertNotIn("Avec une intention minimale", current.system_prompt)
        project["job"]["response_contract_version"] = "2.3.0"
        legacy = request(project, package, "Français")
        self.assertLess(len(current.system_prompt), len(legacy.system_prompt) * .7)
        self.assertEqual(current.max_tokens, legacy.max_tokens)
        self.assertEqual(current.temperature, legacy.temperature)

    def test_timing_is_required_only_in_new_wire_and_survives_storage(self):
        project, value = self.wire("2.4.0")
        transition = dict(before="Fine", trigger="Ellipse de six mois", visible_change="Ventre arrondi", after="Enceinte")
        value["scenario"]["scenes"][0]["visual_transition"] = transition
        self.assertTrue(any(i["path"].endswith("timing") for i in contracts.structural_issues(value, contracts.response_schema(project))))
        transition["timing"] = "between_scenes"
        self.assertEqual(contracts.structural_issues(value, contracts.response_schema(project)), [])
        _, parsed = narrative.parse(project, value)
        self.assertEqual(parsed["scenario"]["scenes"][0]["visual_transition"], transition)
        scene = parsed["scenario"]["scenes"][0]
        instruction = visual_transition_instruction(scene)
        self.assertIn("déjà acquis", instruction)
        self.assertNotIn("TRANSITION VISUELLE À MONTRER", instruction)
        self.assertNotIn("Montre ces quatre temps", instruction)
        scene["visual_transition"]["timing"] = "within_scene"
        self.assertIn("Montre ces quatre temps", visual_transition_instruction(scene))
        scene["visual_transition"].pop("timing")
        self.assertIn("Montre ces quatre temps", visual_transition_instruction(scene))

    def test_new_writer_keeps_dialogue_and_narrative_contract_without_full_example(self):
        project, _ = self.wire("2.4.0")
        package = LongStoryRecipes(ROOT / "prompt_sources/story.long/2.0.0").snapshot()
        current = request(project, package, "Langue cible français")
        context = json.loads(current.user_prompt)
        self.assertNotIn("response_contract", context)
        self.assertIn("Langue cible français", current.system_prompt)
        self.assertIn("between_scenes", current.system_prompt)
        self.assertIn("PERSISTE", current.system_prompt)
        self.assertIn("schema", current.user_prompt)
        self.assertEqual(current.output_schema, contracts.response_schema(project))


if __name__ == "__main__":
    unittest.main()
