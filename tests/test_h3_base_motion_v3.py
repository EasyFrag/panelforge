import json
import tempfile
import unittest
from pathlib import Path

from panelforge.application.direct_i2v_prompt import apply_direct_i2v_timing
from panelforge.application.direct_ref2v_plan import (
    canonical_direct_ref2v_action_plan_v4,
    direct_ref2v_action_plan_schema_v4,
    direct_ref2v_action_plan_warnings_v4,
)
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.domain import CompositionStage
from tests.test_direct_fl2va_composition import configured_service
from tests.test_direct_i2v_composition import action_plan


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def motion_plan(
    *,
    end_behavior: str = "continue_motion",
    final_hold_ms: int = 1000,
) -> dict:
    plan = action_plan(with_camera=False)
    plan["dialogue_cues"] = []
    plan["motion_contract"] = {
        "primary_motion": "The couple waltzes at a steady tempo.",
        "end_behavior": end_behavior,
    }
    plan["final_state"]["final_hold_ms"] = final_hold_ms
    plan["final_state"]["description"] = (
        "The couple occupies the final-frame ballroom arrangement with the "
        "transformed gown and crown fully visible."
    )
    plan["beats"][-1]["primary_action"] = (
        "The crown appears as the couple eases into a held final pose."
    )
    plan["beats"][-1]["steps"][-1]["action"] = (
        "The crown assembles while the couple eases into a held final pose."
    )
    plan["beats"][-1]["steps"][-1]["continuity_after"] = (
        "The couple is stationary in the final pose."
    )
    plan["beats"][-1]["observable_end_state"] = (
        "The transformed couple remains centered in the ballroom."
    )
    return plan


def writer_body() -> str:
    return (
        "integrated_multimodal_description:\n"
        "[Shot 1] The target video is one continuous 12-second shot. "
        "A cool blue Gothic ballroom surrounds the masked couple. "
        "While they rotate, a luminous halo travels down the gown and forms "
        "a crown. At 00:09.000, the couple holds the final pose.\n"
        "overall_soundscape:\n"
        "Continuous ballroom ambience and rhythmic dance steps.\n"
        "non_diegetic_music:\n"
        "A steady orchestral waltz in 3/4 time."
    )


class H3BaseMotionV3Test(unittest.TestCase):
    def test_catalog_keeps_v2_and_adds_motion_aware_v3(self):
        cookbooks = LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks")
        legacy = cookbooks.get("minimax.h3.fl2va.direct", "0.2.0")
        current = cookbooks.get("minimax.h3.fl2va.direct", "0.3.0")
        self.assertEqual(legacy.output_contract, "minimax.h3.fl2va.direct_compact_h3_v2")
        self.assertEqual(current.output_contract, "minimax.h3.fl2va.direct_compact_h3_v3")
        self.assertEqual(current.writer_projection, "compact_motion_v3")
        profiles = LocalPromptProfileCatalog(PROJECT_ROOT / "prompt_profiles")
        profile = profiles.get("minimax.h3.fl2va.direct", "0.3.0")
        self.assertIn("dernière frame est un instant visuel", profile.brief_system_prompt)
        self.assertIn("motion_contract", current.beat_sheet_system_prompt)
        self.assertIn("while, during or as", current.final_prompt_system_prompt)

    def test_schema_exposes_three_explicit_end_behaviors(self):
        schema = json.loads(direct_ref2v_action_plan_schema_v4())
        behavior = schema["$defs"]["DirectMotionEndBehavior"]["enum"]
        self.assertEqual(
            behavior,
            ["continue_motion", "natural_settle", "intentional_hold"],
        )

    def test_continuing_motion_absorbs_hold_without_creating_a_step(self):
        canonical = json.loads(
            canonical_direct_ref2v_action_plan_v4(json.dumps(motion_plan()))
        )
        self.assertEqual(canonical["final_state"]["final_hold_ms"], 0)
        self.assertEqual(canonical["beats"][-1]["end_ms"], 9000)
        self.assertEqual(canonical["beats"][-1]["steps"][-1]["end_ms"], 9000)
        self.assertEqual(len(canonical["beats"][-1]["steps"]), 2)
        self.assertIn(
            "continuing_motion_absorbed_final_hold:1000",
            canonical["technical_adjustments"],
        )
        warnings = direct_ref2v_action_plan_warnings_v4(json.dumps(canonical))
        self.assertTrue(any("immobilite" in warning for warning in warnings))

    def test_compiler_replaces_a_static_final_sentence_for_continuing_motion(self):
        plan = canonical_direct_ref2v_action_plan_v4(json.dumps(motion_plan()))
        compiled = apply_direct_i2v_timing(
            writer_body(),
            plan,
            contract_name="H3 Base",
            dialogue_aware=True,
            motion_aware=True,
            insert_missing_final_landmark=True,
        )
        self.assertIn(
            "Throughout the entire shot, the couple waltzes at a steady tempo; "
            "this primary motion continues without interruption through the final frame.",
            compiled,
        )
        self.assertIn(
            "At 00:09.000, while the couple waltzes at a steady tempo,",
            compiled,
        )
        self.assertIn("The video ends during the same ongoing motion", compiled)
        self.assertNotIn("the couple holds the final pose", compiled)
        self.assertEqual(compiled.count("At 00:09.000,"), 1)

    def test_natural_settle_does_not_receive_the_no_freeze_guard(self):
        plan = motion_plan(end_behavior="natural_settle", final_hold_ms=1000)
        plan["final_state"]["description"] = "The umbrella rests fully open."
        canonical = canonical_direct_ref2v_action_plan_v4(json.dumps(plan))
        compiled = apply_direct_i2v_timing(
            writer_body().replace("At 00:09.000", "At 00:08.000"),
            canonical,
            contract_name="H3 Base",
            dialogue_aware=True,
            motion_aware=True,
            insert_missing_final_landmark=True,
        )
        self.assertIn("At 00:08.000, the umbrella rests fully open.", compiled)
        self.assertNotIn("without a pause, freeze, or held pose", compiled)
        self.assertNotIn("Throughout the entire shot", compiled)

    def test_full_mono_generation_uses_v3_and_compiles_motion_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = configured_service(
                directory,
                ("first_frame", "last_frame"),
                source_text="Valse dynamique en un plan de 9 secondes.",
                profile_version="0.3.0",
                cookbook_version="0.3.0",
            )

            def response(request):
                if request.operation_id == "action_plan.generate":
                    return json.dumps(motion_plan())
                return writer_body()

            gateway._content = response
            planned = service.generate(
                "h3-base-session",
                CompositionStage.BEAT_SHEET,
            )
            plan = json.loads(planned.beat_sheet.active_revision.content)
            self.assertEqual(plan["motion_contract"]["end_behavior"], "continue_motion")
            self.assertEqual(plan["final_state"]["final_hold_ms"], 0)
            service.approve("h3-base-session", CompositionStage.BEAT_SHEET)
            completed = service.generate(
                "h3-base-session",
                CompositionStage.FINAL_PROMPT,
            )
            final = completed.final_prompt.active_revision.content
            self.assertIn("How the reference pictures align", final)
            self.assertIn("The video ends during the same ongoing motion", final)
            self.assertNotIn("the couple holds the final pose", final)


if __name__ == "__main__":
    unittest.main()
