import unittest
from pathlib import Path

from panelforge.domain import PromptSessionMode, ReferenceEvidencePolicy
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DirectFL2VACatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = LocalPromptProfileCatalog(
            PROJECT_ROOT / "prompt_profiles"
        ).get("minimax.h3.fl2va.direct", "0.1.0")
        cls.cookbook = LocalPromptCookbookCatalog(
            PROJECT_ROOT / "prompt_cookbooks"
        ).get("minimax.h3.fl2va.direct", "0.1.0")

    def test_profile_is_h3_base_and_keeps_the_brief_compact(self):
        self.assertEqual(self.profile.session_mode, PromptSessionMode.H3_BASE)
        prompts = "\n".join((
            self.profile.brief_system_prompt or "",
            self.profile.brief_user_prompt or "",
        ))
        self.assertIn("T2VA", prompts)
        self.assertIn("I2VA", prompts)
        self.assertIn("L2VA", prompts)
        self.assertIn("FL2VA", prompts)
        self.assertIn("deux phrases courtes", prompts)

    def test_cookbook_has_two_independent_optional_frame_slots(self):
        cookbook = self.cookbook
        self.assertEqual(cookbook.schema_version, 7)
        self.assertEqual(cookbook.target_mode, "fl2va_direct")
        self.assertEqual(
            cookbook.output_contract,
            "minimax.h3.fl2va.direct_compact_h3_v1",
        )
        self.assertEqual(cookbook.stages, ("beat_sheet", "final_prompt"))
        self.assertEqual(
            tuple(slot.slot_id for slot in cookbook.slots),
            ("first_frame", "last_frame"),
        )
        for slot, required_use in zip(
            cookbook.slots,
            ("first_frame", "last_frame"),
            strict=True,
        ):
            self.assertEqual((slot.minimum_references, slot.maximum_references), (0, 1))
            self.assertEqual(slot.evidence_policy, ReferenceEvidencePolicy.FULL)
            self.assertEqual(slot.required_uses, (required_use,))

    def test_compact_writer_receives_the_plan_but_not_the_full_brief(self):
        writer = "\n".join((
            self.cookbook.final_prompt_system_prompt,
            self.cookbook.final_prompt_user_prompt,
        ))
        self.assertIn("{{PLAN}}", writer)
        self.assertIn("{{REFERENCE_MAPPING}}", writer)
        self.assertNotIn("{{BRIEF}}", writer)
        self.assertIn("PanelForge owns the T2VA/I2VA/L2VA/FL2VA header", writer)
        self.assertIn("final_state_start_ms", writer)
        self.assertIn("duration_ms is the final anchor", writer)
        self.assertIn("Never mention a local source filename", writer)

    def test_legacy_i2v_recipe_remains_independently_loadable(self):
        catalog = LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks")
        legacy = catalog.get("minimax.h3.i2v.direct", "0.2.0")
        self.assertEqual(legacy.target_mode, "i2v_direct")
        self.assertNotEqual(legacy.output_contract, self.cookbook.output_contract)


if __name__ == "__main__":
    unittest.main()
