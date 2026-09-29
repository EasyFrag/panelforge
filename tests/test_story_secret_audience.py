"""User-run regressions for spectator metadata; no models, media or live projects."""
from copy import deepcopy
import unittest

from panelforge.domain import long_stories as narrative
from panelforge.domain.story_contracts import StoryValidationError


class SecretAudienceTest(unittest.TestCase):
    def setUp(self):
        self.project = dict(writing_edition=dict(policy_version=3),
            recipe=dict(id="story.brainrot", version="1.0.0"), document=dict(series_outline=None),
            long_options=dict(profile="melodrama", delivery="continuous", narration="dialogue",
                              unit_count=2, ending_type="reversal"))
        self.outline = narrative.outline_example(self.project)["series_outline"]
        self.character_id = self.outline["characters"][0]["id"]
        self.outline["secrets"] = [dict(id="secret-1", truth="Le témoin a menti.",
            known_by=["spectateur", self.character_id], reveal_episode_id="episode-2")]

    def test_audience_is_preserved_without_informing_another_character(self):
        original = deepcopy(self.outline)
        parsed = narrative.validate_outline(self.project, self.outline)
        secret = parsed["secrets"][0]
        self.assertEqual(secret["known_by"], [self.character_id])
        self.assertTrue(secret["truth"].startswith(original["secrets"][0]["truth"]))
        self.assertIn("Le spectateur connaît cette vérité.", secret["truth"])
        self.assertEqual(secret["reveal_episode_id"], "episode-2")
        self.assertEqual(self.outline, original)

    def test_normalization_is_idempotent_and_keeps_all_other_fields(self):
        normalized, notes = narrative.normalize_secret_audience(self.project, self.outline)
        self.assertEqual(len(notes), 1)
        again, repeated = narrative.normalize_secret_audience(self.project, normalized)
        self.assertEqual(again, normalized)
        self.assertEqual(repeated, [])
        for key in self.outline.keys() - {"secrets"}:
            self.assertEqual(normalized[key], self.outline[key])

    def test_only_explicit_audience_aliases_are_recovered(self):
        for label in ("spectateur", "public", "Le spectateur", "AUDIENCE", " viewers "):
            with self.subTest(label=label):
                value = deepcopy(self.outline)
                value["secrets"][0]["known_by"] = [label]
                parsed = narrative.validate_outline(self.project, value)
                self.assertEqual(parsed["secrets"][0]["known_by"], [])
        for identifiers in (["spectateur", "char-inconnu"],
                            ["spectateur", self.character_id, self.character_id],
                            ["narrateur"], ["spectateur", 42]):
            with self.subTest(identifiers=identifiers):
                value = deepcopy(self.outline)
                value["secrets"][0]["known_by"] = identifiers
                with self.assertRaises(StoryValidationError):
                    narrative.validate_outline(self.project, value)

    def test_real_character_named_spectateur_is_not_removed(self):
        self.outline["characters"][0]["id"] = "spectateur"
        self.outline["secrets"][0]["known_by"] = ["spectateur"]
        normalized, notes = narrative.normalize_secret_audience(self.project, self.outline)
        self.assertIs(normalized, self.outline)
        self.assertEqual(notes, [])
        self.outline["characters"][0]["id"] = "char-observateur"
        self.outline["characters"][0]["name"] = "Spectateur"
        normalized, notes = narrative.normalize_secret_audience(self.project, self.outline)
        self.assertIs(normalized, self.outline)
        self.assertEqual(notes, [])

    def test_legacy_and_producing_job_policy_are_preserved(self):
        for project in (dict(self.project, writing_edition=dict(policy_version=2)),
                        dict(self.project, job=dict(editorial_policy=2))):
            with self.subTest(project=project):
                normalized, notes = narrative.normalize_secret_audience(project, self.outline)
                self.assertIs(normalized, self.outline)
                self.assertEqual(notes, [])
                with self.assertRaises(StoryValidationError):
                    narrative.validate_outline(project, self.outline)

    def test_invalid_or_overlong_truth_is_never_replaced_or_truncated(self):
        for truth in (None, "", " ", "a" * 3000):
            with self.subTest(truth_length=len(truth or "")):
                value = deepcopy(self.outline)
                value["secrets"][0]["truth"] = truth
                normalized, notes = narrative.normalize_secret_audience(self.project, value)
                self.assertIs(normalized, value)
                self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
