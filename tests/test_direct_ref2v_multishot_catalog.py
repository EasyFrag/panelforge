import unittest
from pathlib import Path

from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DirectRef2VMultishotCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks")
        cls.multishot = catalog.get(
            "minimax.h3.ref2v.direct.multishot", "0.1.0"
        )
        cls.single_shot = catalog.get("minimax.h3.ref2v.direct", "0.3.2")

    def test_manifest_declares_a_distinct_compact_multishot_contract(self):
        cookbook = self.multishot

        self.assertEqual(cookbook.schema_version, 5)
        self.assertEqual(cookbook.target_mode, "ref2v_direct")
        self.assertEqual(
            cookbook.output_contract,
            "minimax.h3.ref2v.direct_multishot_compact_h3_v1",
        )
        self.assertEqual(cookbook.writer_projection, "compact_multishot_v1")
        self.assertEqual(cookbook.stages, ("beat_sheet", "final_prompt"))
        self.assertIsNotNone(cookbook.beat_sheet_reconcile_system_prompt)
        self.assertIsNotNone(cookbook.beat_sheet_reconcile_user_prompt)

    def test_reference_slot_and_pinned_sources_match_single_shot(self):
        self.assertEqual(self.multishot.slots, self.single_shot.slots)
        self.assertEqual(
            self.multishot.reference.engine_contract_id,
            self.single_shot.reference.engine_contract_id,
        )
        self.assertEqual(
            self.multishot.reference.engine_contract_version,
            self.single_shot.reference.engine_contract_version,
        )

        multishot_manifest = (
            PROJECT_ROOT
            / "prompt_cookbooks"
            / "minimax.h3.ref2v.direct.multishot"
            / "0.1.0"
            / "manifest.json"
        ).read_text(encoding="utf-8")
        single_manifest = (
            PROJECT_ROOT
            / "prompt_cookbooks"
            / "minimax.h3.ref2v.direct"
            / "0.3.2"
            / "manifest.json"
        ).read_text(encoding="utf-8")
        for pinned_source in (
            "05d91ff89f58b665e56424fd66db9ef0351b3015/skills/h3-prompt-writing/SKILL.md",
            "05d91ff89f58b665e56424fd66db9ef0351b3015/skills/h3-prompt-writing/references/ref-en.txt",
        ):
            self.assertIn(pinned_source, multishot_manifest)
            self.assertIn(pinned_source, single_manifest)

    def test_plan_is_exactly_three_hard_cut_shots(self):
        prompts = "\n".join((
            self.multishot.beat_sheet_system_prompt or "",
            self.multishot.beat_sheet_user_prompt or "",
        ))

        self.assertIn("exactly three shots", prompts)
        self.assertIn("hard cuts", prompts)
        self.assertIn("shot_id", prompts)
        self.assertIn("duration_ms", prompts)
        self.assertIn("final_state.final_hold_ms", prompts)
        self.assertIn("Never produce a camera ID", prompts)
        self.assertIn("application assigns camera_<shot number>", prompts)
        self.assertIn("{{REFERENCES}}", prompts)
        self.assertIn("{{ACTION_PLAN_SCHEMA}}", prompts)

    def test_writer_returns_six_internal_fields_without_compiled_syntax(self):
        system = self.multishot.final_prompt_system_prompt
        fields = (
            "scene_setup:",
            "shot_1:",
            "shot_2:",
            "shot_3:",
            "overall_soundscape:",
            "non_diegetic_music:",
        )
        positions = tuple(system.index(field) for field in fields)

        self.assertEqual(positions, tuple(sorted(positions)))
        self.assertIn("application compiles", system)
        self.assertIn("no [Shot N] headings", system)
        self.assertIn("no At MM:SS.mmm", system)
        self.assertIn("never output <scenetrans>", system)
        self.assertIn("first non-whitespace sentence", system)
        for placeholder in ("{{BRIEF}}", "{{PLAN}}", "{{REFERENCE_MAPPING}}"):
            self.assertIn(placeholder, self.multishot.final_prompt_user_prompt)

    def test_revision_and_reconciliation_preserve_three_shot_boundaries(self):
        reconcile = "\n".join((
            self.multishot.beat_sheet_reconcile_system_prompt or "",
            self.multishot.beat_sheet_reconcile_user_prompt or "",
        ))
        revision = "\n".join((
            self.multishot.revision_system_prompt,
            self.multishot.revision_user_prompt,
        ))

        for placeholder in (
            "{{BRIEF}}",
            "{{REFERENCES}}",
            "{{CURRENT_PLAN}}",
            "{{DECISIONS}}",
            "{{GLOBAL_INSTRUCTION}}",
            "{{ACTION_PLAN_SCHEMA}}",
        ):
            self.assertIn(placeholder, reconcile)
        self.assertIn("exactly three shots", reconcile)
        self.assertIn("exactly three shots", revision)
        self.assertIn("hard-cut", revision)


if __name__ == "__main__":
    unittest.main()
