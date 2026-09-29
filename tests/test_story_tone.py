"""User-run regression checks for opt-in tone, prompt routing and old hashes."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from panelforge.application.long_stories import request
from panelforge.application.story_prompting import build
from panelforge.domain import long_stories as narrative, story_direction as direction
from panelforge.features.lab.stories_web import StoryCreate
from panelforge.infrastructure.long_story_recipes import LongStoryRecipes
from tests import test_story_quality_policy as quality_fixture

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "black_comedy_street_v1"


class StoryToneTest(unittest.TestCase):
    setUp = quality_fixture.StoryQualityTest.setUp
    settle = quality_fixture.StoryQualityTest.settle
    advance = quality_fixture.StoryQualityTest.advance
    create = quality_fixture.StoryQualityTest.create
    operations = quality_fixture.StoryQualityTest.operations

    def test_tone_uses_three_roles_but_glossary_only_reaches_writer(self):
        lexicon = "Zulima = une expression imaginaire pour demander du calme."
        project = self.advance(self.create(dialogue_register=3, writing_direction=dict(
            tone_profile=PROFILE, dialogue_style="street", glossary=lexicon)))
        self.assertEqual(project["workflow"]["status"], "ready")
        self.assertEqual(self.operations(), ["compose", "develop", "review_block"])
        for index, req in enumerate(self.gateway.requests):
            self.assertIn("AMBIANCE : comédie noire", req.system_prompt)
            context = json.loads(req.user_prompt)
            self.assertEqual(context.get("dialogue_lexicon"), lexicon if index == 1 else None)
            self.assertEqual(lexicon in req.user_prompt, index == 1)
            for anchor in ("NFT", "portefeuille", "Piccolo", "payer une pute", "wesh", "schlingue", "propre facture"):
                self.assertNotIn(anchor, req.system_prompt)
        saved = self.service.store.get(project["project_id"])
        self.assertEqual(saved["writing_direction"]["glossary"], lexicon)
        self.assertEqual(saved["writing_direction"]["tone_profile"], PROFILE)
        self.assertEqual(saved["writing_direction"]["protected_lines"], [])

    def test_explicit_overrides_are_not_replaced_by_profile_defaults(self):
        self.advance(self.create(dialogue_register=1, dialogue_language="English", writing_direction=dict(
            tone_profile=PROFILE, dialogue_style="natural", dialogue_pace="natural", dialogue_notes="Très sec.")))
        for req in self.gateway.requests:
            context = json.loads(req.user_prompt)
            self.assertEqual(context["dialogue_direction"]["dialogue_style"], "natural")
            self.assertEqual(context["speech_budget"]["pace"], "natural")
        writer = json.loads(self.gateway.requests[1].user_prompt)
        self.assertEqual(writer["dialogue_language"], "English")
        self.assertEqual(writer["dialogue_register"], 1)

    def test_old_direction_keeps_dependency_and_review_hashes(self):
        project = self.advance(self.create())
        saved = project["writing_direction"]
        saved.pop("tone_profile"); saved.pop("glossary")
        doc = project["document"]
        old_dependency = narrative.fingerprint(dict(outline=doc["series_outline"], options=project["long_options"],
            format=doc.get("episode_formats", {}).get("episode-1"), previous=[], writing_direction=saved))
        old_source = narrative.fingerprint([old_dependency, doc["episode_scenarios"]["episode-1"],
            doc["episode_states"]["episode-1"]])
        doc["reviews"]["episode-1"]["source_hash"] = old_source
        self.assertEqual(narrative.dependency_hash(project, "episode-1"), old_dependency)
        self.assertTrue(narrative.review_current(project, "episode-1"))
        before = deepcopy(project)
        package = self.service.long_recipes.snapshot()
        package.pop("tone_profiles")  # Old captured packages are still readable without a tone.
        req = request(project, package, "Français")
        self.assertNotIn("AMBIANCE : comédie noire", req.system_prompt)
        self.assertEqual(project, before)

    def test_followup_keeps_tone_and_meanings_but_not_previous_exact_lines(self):
        project = self.create(writing_direction=dict(tone_profile=PROFILE, glossary="Zulima = calme.",
            protected_lines=["Phrase de l’épisode précédent."]))
        followup = direction.for_followup(project)
        self.assertEqual(followup["tone_profile"], PROFILE)
        self.assertEqual(followup["glossary"], "Zulima = calme.")
        self.assertEqual(followup["protected_lines"], [])
        self.assertTrue(project["writing_direction"]["protected_lines"])

    def test_silent_prompt_never_receives_spoken_tone_or_glossary(self):
        project = self.create(writing_direction=dict(tone_profile=PROFILE, glossary="Zulima = calme."))
        project["job"] = dict(operation="develop")
        system, context = build(project, self.service.long_recipes.snapshot(),
            dict(selected_unit={"id": "episode-1"}, visual_family={"dialogue_policy": "forbidden"}),
            reader_mode=False, language_policy="", register_policy="")
        self.assertNotIn("AMBIANCE : comédie noire", system)
        self.assertNotIn("dialogue_lexicon", context)

    def test_api_validates_profile_and_glossary_without_adding_protected_lines(self):
        raw = dict(narrative_format="long", writing_direction=dict(tone_profile=PROFILE, glossary="Zulima = calme."))
        body = StoryCreate.model_validate(raw).model_dump()["writing_direction"]
        self.assertEqual(body["tone_profile"], PROFILE)
        self.assertEqual(direction.normalize(body)["protected_lines"], [])
        for bad in (dict(tone_profile="unknown"), dict(glossary="a" * 2001)):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    StoryCreate.model_validate(dict(writing_direction=bad))
                with self.assertRaises(ValueError):
                    direction.normalize(bad)

    def test_tone_sources_are_in_snapshot_fingerprint_and_cannot_escape_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "recipe"
            shutil.copytree(ROOT / "prompt_sources/story.long/2.0.0", root)
            recipes = LongStoryRecipes(root)
            first = recipes.snapshot()
            filename = root / "tone-black-comedy-v1-write.txt"
            filename.write_text(filename.read_text(encoding="utf-8") + "Une nuance supplémentaire.", encoding="utf-8")
            second = recipes.snapshot()
            self.assertEqual(first["revision"], 8)
            self.assertNotEqual(first["fingerprint"], second["fingerprint"])
            self.assertNotEqual(first["tone_profiles"], second["tone_profiles"])
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            manifest["tone_profiles"][PROFILE]["write"] = "../outside.txt"
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hors de la recette"):
                recipes.snapshot()


if __name__ == "__main__":
    unittest.main()
