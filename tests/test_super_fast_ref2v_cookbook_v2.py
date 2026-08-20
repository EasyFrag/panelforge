import unittest
from pathlib import Path

from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COOKBOOK_ID = "minimax.h3.ref2v.direct.multishot.superfast"


class SuperFastRef2VDirectCookbookV2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks")
        cls.v1 = catalog.get(COOKBOOK_ID, "0.1.0")
        cls.v2 = catalog.get(COOKBOOK_ID, "0.2.0")

    def test_v2_is_an_internal_final_only_direct_prompt_recipe(self):
        cookbook = self.v2

        self.assertEqual(cookbook.schema_version, 6)
        self.assertEqual(cookbook.target_mode, "ref2v_direct")
        self.assertEqual(cookbook.visibility, "internal")
        self.assertEqual(cookbook.execution_mode, "super_fast_ref2v_direct_v2")
        self.assertEqual(cookbook.stages, ("final_prompt",))
        self.assertEqual(cookbook.writer_projection, "full")
        self.assertEqual(
            cookbook.output_contract,
            "minimax.h3.ref2v.direct_multishot_prompt_h3_v1",
        )
        self.assertIsNone(cookbook.beat_sheet_system_prompt)
        self.assertIsNone(cookbook.beat_sheet_user_prompt)

    def test_v1_plan_recipe_remains_distinct_and_unchanged_in_catalog(self):
        self.assertEqual(self.v1.reference.version, "0.1.0")
        self.assertEqual(self.v1.stages, ("beat_sheet", "final_prompt"))
        self.assertEqual(
            self.v1.writer_projection,
            "compact_multishot_v2_camera_owned",
        )
        self.assertNotEqual(self.v1.output_contract, self.v2.output_contract)
        self.assertIn(
            "one JSON object",
            self.v1.beat_sheet_system_prompt or "",
        )

    def test_v2_direct_call_uses_brief_and_native_reference_evidence_without_plan(self):
        system = self.v2.final_prompt_system_prompt
        user = self.v2.final_prompt_user_prompt
        prompts = system + "\n" + user

        self.assertIn("sole multimodal director", system)
        self.assertIn("return the final H3 body in one response", system)
        self.assertIn("Do not output a Plan, JSON", system)
        self.assertIn("{{BRIEF}}", user)
        self.assertIn("{{REFERENCES}}", user)
        self.assertNotIn("{{PLAN}}", prompts)
        self.assertNotIn("{{ACTION_PLAN_SCHEMA}}", prompts)

    def test_v2_prompt_keeps_permissive_h3_multishot_shape_and_continuity(self):
        system = self.v2.final_prompt_system_prompt

        self.assertIn("minimum sufficient two-to-six-shot sequence", system)
        self.assertIn("[Shot 1]", system)
        self.assertIn("[Shot N] At MM:SS.mmm,", system)
        self.assertIn("Reference count does not determine shot count", system)
        self.assertIn("materially different and readable opening composition", system)
        self.assertIn("A hard cut changes the view, not physical reality", system)
        self.assertIn("overall_soundscape:", system)
        self.assertIn("non_diegetic_music:", system)
        self.assertIn("The camera shakes slightly", system)
        self.assertNotIn("{{ACTION_PLAN_SCHEMA}}", system)

    def test_v2_keeps_one_to_three_reference_slot_and_pinned_h3_sources(self):
        self.assertEqual(self.v2.slots, self.v1.slots)
        self.assertEqual(self.v2.reference.engine_contract_id, "minimax.h3.protocol")
        self.assertEqual(self.v2.reference.engine_contract_version, "0.1.0")

        manifest = (
            PROJECT_ROOT
            / "prompt_cookbooks"
            / COOKBOOK_ID
            / "0.2.0"
            / "manifest.json"
        ).read_text(encoding="utf-8")
        for pinned_source in (
            "05d91ff89f58b665e56424fd66db9ef0351b3015/skills/h3-prompt-writing/SKILL.md",
            "05d91ff89f58b665e56424fd66db9ef0351b3015/skills/h3-prompt-writing/references/ref-en.txt",
        ):
            self.assertIn(pinned_source, manifest)

    def test_v2_revision_operates_on_the_final_prompt_without_plan_context(self):
        revision = self.v2.revision_system_prompt + "\n" + self.v2.revision_user_prompt

        self.assertIn("{{STAGE_CONTRACT}}", revision)
        self.assertIn("{{CURRENT}}", revision)
        self.assertIn("{{INSTRUCTION}}", revision)
        self.assertNotIn("{{PLAN}}", revision)
        self.assertIn("Return the whole body", revision)


if __name__ == "__main__":
    unittest.main()
