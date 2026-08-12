import unittest
from pathlib import Path

from panelforge.domain import PromptSessionMode, ReferenceEvidencePolicy
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DirectI2VCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = LocalPromptProfileCatalog(
            PROJECT_ROOT / "prompt_profiles"
        ).get("minimax.h3.i2v.direct", "0.1.0")
        cls.cookbook = LocalPromptCookbookCatalog(
            PROJECT_ROOT / "prompt_cookbooks"
        ).get("minimax.h3.i2v.direct", "0.1.0")

    def test_profile_is_direct_multimodal_and_first_frame_only(self):
        self.assertEqual(
            self.profile.session_mode,
            PromptSessionMode.DIRECT_MULTIMODAL,
        )
        self.assertIsNone(self.profile.interpretation_system_prompt)
        system = self.profile.brief_system_prompt or ""
        self.assertIn("une et une seule image native", system)
        self.assertIn("<Image 1>", system)
        self.assertIn("première frame exacte", system)
        self.assertIn("Relis directement l’unique première frame", self.profile.brief_revision_system_prompt)

    def test_cookbook_exposes_one_strict_first_frame_slot(self):
        cookbook = self.cookbook
        self.assertEqual(cookbook.schema_version, 5)
        self.assertEqual(cookbook.target_mode, "i2v_direct")
        self.assertEqual(
            cookbook.output_contract,
            "minimax.h3.i2va.direct_supervised_h3_v1",
        )
        self.assertEqual(cookbook.stages, ("beat_sheet", "final_prompt"))
        self.assertEqual(cookbook.writer_projection, "compact_v1")
        slot = cookbook.slots[0]
        self.assertEqual(slot.slot_id, "first_frame")
        self.assertEqual((slot.minimum_references, slot.maximum_references), (1, 1))
        self.assertEqual(slot.evidence_policy, ReferenceEvidencePolicy.FULL)
        self.assertEqual(slot.required_uses, ("first_frame",))
        self.assertEqual(slot.required_shots, (1,))

    def test_plan_uses_derived_timing_and_native_image_evidence(self):
        prompts = "\n".join((
            self.cookbook.beat_sheet_system_prompt or "",
            self.cookbook.beat_sheet_user_prompt or "",
        ))
        self.assertIn("exactly one native first-frame image", prompts)
        self.assertIn("Do not output duration_seconds", prompts)
        self.assertIn("final_state.final_hold_ms", prompts)
        self.assertIn("{{REFERENCES}}", prompts)
        self.assertIn("{{ACTION_PLAN_SCHEMA}}", prompts)
        self.assertIsNotNone(self.cookbook.beat_sheet_reconcile_system_prompt)

    def test_writer_targets_only_the_three_official_i2va_fields(self):
        system = self.cookbook.final_prompt_system_prompt
        expected = (
            "integrated_multimodal_description:",
            "overall_soundscape:",
            "non_diegetic_music:",
        )
        positions = tuple(system.index(field) for field in expected)
        self.assertEqual(positions, tuple(sorted(positions)))
        self.assertNotIn("scene_setup:\nshot_1:", system)
        self.assertNotIn("camera_directives:", system)
        self.assertIn("official 0.00-second <Picture 1> instruction", system)
        self.assertIn("[Shot 1] The target video is one continuous N-second shot.", system)
        for placeholder in ("{{BRIEF}}", "{{PLAN}}", "{{REFERENCE_MAPPING}}"):
            self.assertIn(placeholder, self.cookbook.final_prompt_user_prompt)


if __name__ == "__main__":
    unittest.main()
