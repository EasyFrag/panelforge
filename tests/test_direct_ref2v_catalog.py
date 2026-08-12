import json
import unittest
from pathlib import Path

from panelforge.domain import PromptSessionMode, ReferenceEvidencePolicy
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DirectRef2VCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = LocalPromptProfileCatalog(PROJECT_ROOT / "prompt_profiles").get(
            "minimax.h3.ref2v.direct", "0.1.0"
        )
        cls.cookbook = LocalPromptCookbookCatalog(
            PROJECT_ROOT / "prompt_cookbooks"
        ).get("minimax.h3.ref2v.direct", "0.1.0")
        cls.cookbook_v2 = LocalPromptCookbookCatalog(
            PROJECT_ROOT / "prompt_cookbooks"
        ).get("minimax.h3.ref2v.direct", "0.2.0")
        cls.cookbook_v3 = LocalPromptCookbookCatalog(
            PROJECT_ROOT / "prompt_cookbooks"
        ).get("minimax.h3.ref2v.direct", "0.3.0")
        cls.cookbook_compact = LocalPromptCookbookCatalog(
            PROJECT_ROOT / "prompt_cookbooks"
        ).get("minimax.h3.ref2v.direct", "0.3.1")

    def test_profile_loads_as_direct_multimodal(self):
        self.assertEqual(
            self.profile.session_mode,
            PromptSessionMode.DIRECT_MULTIMODAL,
        )
        self.assertIsNone(self.profile.interpretation_system_prompt)
        manifest = json.loads((
            PROJECT_ROOT / "prompt_profiles" / "video.compose"
            / "minimax-h3-ref2v-direct" / "0.1.0" / "manifest.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 4)
        self.assertEqual(len(manifest["prompts"]), 8)

    def test_direct_brief_reads_images_and_keeps_nine_sections(self):
        system = self.profile.brief_system_prompt or ""
        for heading in (
            "INTENTION CENTRALE", "RÉFÉRENCES CITÉES ET RÔLES",
            "SUJETS ET IDENTITÉS À PRÉSERVER", "DÉCOR ET ÉTAT INITIAL",
            "CHRONOLOGIE ET ACTIONS DEMANDÉES",
            "CAMÉRA, LUMIÈRE ET MISE EN SCÈNE", "CONTRAINTES STRICTES",
            "LIBERTÉS AUTORISÉES", "QUESTIONS OU AMBIGUÏTÉS",
        ):
            self.assertIn(heading, system)
        self.assertIn("images natives", system)
        self.assertIn("Relis directement", self.profile.brief_revision_system_prompt)

    def test_cookbook_accepts_one_to_three_references(self):
        cookbook = self.cookbook
        self.assertEqual(cookbook.schema_version, 4)
        self.assertEqual(cookbook.target_mode, "ref2v_direct")
        self.assertEqual(cookbook.stages, ("beat_sheet", "final_prompt"))
        slot = cookbook.slots[0]
        self.assertEqual((slot.minimum_references, slot.maximum_references), (1, 3))
        self.assertEqual(slot.evidence_policy, ReferenceEvidencePolicy.FULL)
        self.assertEqual(slot.required_uses, ())
        self.assertEqual(slot.required_shots, ())
        self.assertIn("motion", slot.accepted_uses)

    def test_writer_keeps_camera_in_the_plan(self):
        self.assertNotIn("camera_directives:", self.cookbook.final_prompt_system_prompt)
        self.assertIn("[[camera:camera_N]]", self.cookbook.final_prompt_system_prompt)
        for placeholder in ("{{BRIEF}}", "{{PLAN}}", "{{REFERENCE_MAPPING}}"):
            self.assertIn(placeholder, self.cookbook.final_prompt_user_prompt)

    def test_v2_cookbook_preserves_slots_and_protocol(self):
        cookbook = self.cookbook_v2

        self.assertEqual(cookbook.schema_version, 4)
        self.assertEqual(cookbook.reference.cookbook_id, "minimax.h3.ref2v.direct")
        self.assertEqual(cookbook.reference.version, "0.2.0")
        self.assertEqual(
            cookbook.reference.engine_contract_id,
            self.cookbook.reference.engine_contract_id,
        )
        self.assertEqual(
            cookbook.reference.engine_contract_version,
            self.cookbook.reference.engine_contract_version,
        )
        self.assertEqual(len(cookbook.slots), len(self.cookbook.slots))
        self.assertEqual(cookbook.slots[0].slot_id, self.cookbook.slots[0].slot_id)
        self.assertEqual(
            cookbook.slots[0].accepted_uses,
            self.cookbook.slots[0].accepted_uses,
        )
        self.assertEqual(
            (
                cookbook.slots[0].minimum_references,
                cookbook.slots[0].maximum_references,
            ),
            (
                self.cookbook.slots[0].minimum_references,
                self.cookbook.slots[0].maximum_references,
            ),
        )
        self.assertEqual(cookbook.target_mode, "ref2v_direct")
        self.assertEqual(cookbook.stages, ("beat_sheet", "final_prompt"))
        self.assertEqual(
            cookbook.output_contract,
            "minimax.h3.ref2v.direct_supervised_h3_v2",
        )
        self.assertEqual(cookbook.preset, "direct-multiref-supervised-h3-v2")

    def test_v2_plan_delegates_final_timing_to_the_application(self):
        prompts = "\n".join((
            self.cookbook_v2.beat_sheet_system_prompt or "",
            self.cookbook_v2.beat_sheet_user_prompt or "",
        ))

        self.assertIn("Do not output duration_seconds", prompts)
        self.assertIn("final_state.final_hold_ms", prompts)
        self.assertIn("application derives the final-state start and total", prompts)
        self.assertIn("technical_adjustments must be an empty array", prompts)
        self.assertIn("one continuous shot", prompts)
        self.assertNotIn("final_state.start_ms", prompts)

    def test_v2_writer_consumes_enriched_plan_without_extra_binding(self):
        system = self.cookbook_v2.final_prompt_system_prompt
        user = self.cookbook_v2.final_prompt_user_prompt

        self.assertIn("derived_timing", system)
        self.assertIn("final_state_start_ms", system)
        self.assertIn("duration_ms", system)
        self.assertIn("duration_seconds", system)
        self.assertIn("[[camera:camera_N]]", system)
        self.assertNotIn("camera_directives:", system)
        self.assertNotIn("{{DERIVED_TIMING}}", system)
        self.assertNotIn("{{DERIVED_TIMING}}", user)
        for placeholder in ("{{BRIEF}}", "{{PLAN}}", "{{REFERENCE_MAPPING}}"):
            self.assertIn(placeholder, user)

    def test_direct_cookbook_versions_remain_independently_loadable(self):
        cookbooks = LocalPromptCookbookCatalog(
            PROJECT_ROOT / "prompt_cookbooks"
        ).list()
        versions = [
            item.reference.version
            for item in cookbooks
            if item.reference.cookbook_id == "minimax.h3.ref2v.direct"
        ]

        self.assertEqual(versions, ["0.1.0", "0.2.0", "0.3.0", "0.3.1"])

    def test_v3_adds_multimodal_risk_arbitration_without_changing_v2_plan(self):
        cookbook = self.cookbook_v3

        self.assertEqual(
            cookbook.output_contract,
            "minimax.h3.ref2v.direct_supervised_h3_v2",
        )
        self.assertEqual(
            cookbook.preset,
            "direct-multiref-supervised-h3-v3-arbitrated",
        )
        self.assertIsNotNone(cookbook.beat_sheet_reconcile_system_prompt)
        self.assertIsNotNone(cookbook.beat_sheet_reconcile_user_prompt)
        reconcile = "\n".join((
            cookbook.beat_sheet_reconcile_system_prompt or "",
            cookbook.beat_sheet_reconcile_user_prompt or "",
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
        self.assertIn("attached native images", reconcile)
        self.assertIn("copy its text exactly", reconcile)
        self.assertIn("final_state.final_hold_ms", reconcile)
        self.assertIsNone(self.cookbook_v2.beat_sheet_reconcile_system_prompt)

    def test_compact_recipe_reuses_v2_contract_with_declared_projection(self):
        compact = self.cookbook_compact

        self.assertEqual(compact.schema_version, 5)
        self.assertEqual(compact.writer_projection, "compact_v1")
        self.assertEqual(compact.output_contract, self.cookbook_v3.output_contract)
        self.assertEqual(compact.stages, self.cookbook_v3.stages)
        self.assertEqual(compact.slots, self.cookbook_v3.slots)
        self.assertIsNotNone(compact.beat_sheet_reconcile_system_prompt)
        self.assertLess(
            len(compact.beat_sheet_system_prompt or ""),
            len(self.cookbook_v3.beat_sheet_system_prompt or ""),
        )
        self.assertLess(
            len(compact.final_prompt_system_prompt),
            len(self.cookbook_v3.final_prompt_system_prompt),
        )
        self.assertEqual(self.cookbook_v3.writer_projection, "full")


if __name__ == "__main__":
    unittest.main()
