import json
import tempfile
import unittest
from pathlib import Path

from panelforge.application.direct_i2v_prompt import apply_direct_i2v_timing
from panelforge.application.direct_ref2v_plan import (
    canonical_direct_ref2v_action_plan_v4,
    canonical_direct_ref2v_action_plan_v4_late_anchor,
    continuing_motion_final_anchor_errors,
    direct_ref2v_writer_plan_v4_camera_clean,
    direct_ref2v_action_plan_schema_v4,
    direct_ref2v_action_plan_warnings_v4,
    parse_direct_ref2v_action_plan_v4,
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


def camera_contaminated_motion_plan() -> dict:
    plan = motion_plan(final_hold_ms=0)
    plan["scene_setup"] += (
        " The camera orbits continuously around the masked couple."
    )
    plan["continuity_invariants"].append(
        "The ballroom remains stable while the camera orbits around them."
    )
    plan["motion_contract"]["primary_motion"] = (
        "The couple waltzes through three continuous turns while the camera "
        "orbits around them and the gown transforms."
    )
    plan["beats"][0]["steps"][0]["action"] = (
        "The couple starts the first turn as the camera begins a slow arc; "
        "a blue halo ignites over the moving gown."
    )
    plan["beats"][0]["steps"][1]["action"] = (
        "As the orbit carries the background clock across the frame, the gown "
        "opens while the couple keeps waltzing."
    )
    plan["final_state"]["description"] = (
        "The transformed couple remains mid-waltz with the crown visible; "
        "the waltz and the camera orbit are still ongoing."
    )
    plan["camera_directives"] = [
        {
            "directive_id": "camera_1",
            "start_ms": 0,
            "end_ms": 8000,
            "motion": "arc_shot",
            "amplitude": "large",
            "speed": "slow",
            "target_clause": None,
            "visible_change": "The couple remains central against the clock.",
        }
    ]
    return plan


def late_anchor_motion_plan(*, end_behavior: str = "continue_motion") -> dict:
    plan = motion_plan(end_behavior=end_behavior, final_hold_ms=0)
    plan["beats"][-1]["primary_action"] = (
        "The crown assembles while the couple keeps waltzing at a steady tempo."
    )
    plan["beats"][-1]["steps"][-1]["action"] = (
        "The crown assembles during the same uninterrupted waltz rotation."
    )
    plan["beats"][-1]["steps"][-1]["continuity_after"] = (
        "The couple keeps rotating and their clothing continues responding to motion."
    )
    plan["beats"][-1]["observable_end_state"] = (
        "The transformed couple remains visibly mid-rotation."
    )
    plan["final_state"]["description"] = (
        "The transformed gown and crown are fully visible while the couple is mid-rotation."
    )
    return plan


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

    def test_catalog_adds_camera_clean_v4_without_replacing_v3(self):
        cookbooks = LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks")
        previous = cookbooks.get("minimax.h3.fl2va.direct", "0.3.0")
        current = cookbooks.get("minimax.h3.fl2va.direct", "0.3.1")
        self.assertEqual(current.output_contract, previous.output_contract)
        self.assertEqual(current.writer_projection, "camera_clean_v4")
        profiles = LocalPromptProfileCatalog(PROJECT_ROOT / "prompt_profiles")
        profile = profiles.get("minimax.h3.fl2va.direct", "0.3.1")
        self.assertIn("caméra nette", profile.display_name)

    def test_catalog_adds_instantaneous_anchor_v4_without_replacing_camera_clean(self):
        cookbooks = LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks")
        previous = cookbooks.get("minimax.h3.fl2va.direct", "0.3.1")
        current = cookbooks.get("minimax.h3.fl2va.direct", "0.3.2")
        self.assertEqual(
            previous.output_contract,
            "minimax.h3.fl2va.direct_compact_h3_v3",
        )
        self.assertEqual(
            current.output_contract,
            "minimax.h3.fl2va.direct_compact_h3_v4",
        )
        self.assertEqual(current.writer_projection, "camera_clean_v4")
        self.assertIn(
            "changing background parallax",
            current.beat_sheet_system_prompt,
        )
        self.assertIn(
            "Do not split or taper one continuous camera move",
            current.beat_sheet_system_prompt,
        )
        self.assertIn(
            "instantaneous frame sampled from ongoing motion",
            current.final_prompt_system_prompt,
        )
        profiles = LocalPromptProfileCatalog(PROJECT_ROOT / "prompt_profiles")
        profile = profiles.get("minimax.h3.fl2va.direct", "0.3.2")
        self.assertIn("ancre finale instantanée", profile.display_name)
        self.assertIn("impression de sur-place", profile.brief_system_prompt)

    def test_catalog_adds_json_robust_v033_without_replacing_v032(self):
        cookbooks = LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks")
        previous = cookbooks.get("minimax.h3.fl2va.direct", "0.3.2")
        current = cookbooks.get("minimax.h3.fl2va.direct", "0.3.3")

        self.assertEqual(current.output_contract, previous.output_contract)
        self.assertEqual(current.writer_projection, previous.writer_projection)
        self.assertIn("strict JSON syntax pass", current.beat_sheet_system_prompt)
        profiles = LocalPromptProfileCatalog(PROJECT_ROOT / "prompt_profiles")
        self.assertIn(
            "JSON robuste",
            profiles.get("minimax.h3.fl2va.direct", "0.3.3").display_name,
        )

    def test_action_plan_repairs_one_missing_opening_key_quote(self):
        malformed = json.dumps(late_anchor_motion_plan(), indent=2).replace(
            '"risk_id":',
            'risk_id":',
            1,
        )

        parsed = parse_direct_ref2v_action_plan_v4(malformed)

        self.assertEqual(parsed.motion_contract.end_behavior.value, "continue_motion")

    def test_late_anchor_guard_rejects_early_final_frame_convergence(self):
        plan = late_anchor_motion_plan()
        plan["beats"][-1]["steps"][-1]["action"] = (
            "The couple settles into the locked final-frame composition while dancing."
        )

        errors = continuing_motion_final_anchor_errors(json.dumps(plan))

        self.assertTrue(any("must not settle into" in error for error in errors))
        with self.assertRaisesRegex(ValueError, "instantaneous pass-through"):
            canonical_direct_ref2v_action_plan_v4_late_anchor(json.dumps(plan))

    def test_late_anchor_guard_rejects_frame_bookkeeping_in_final_snapshot(self):
        plan = late_anchor_motion_plan()
        plan["final_state"]["description"] = (
            "The moving couple matches the locked final frame."
        )

        with self.assertRaisesRegex(ValueError, "frame matching remains"):
            canonical_direct_ref2v_action_plan_v4_late_anchor(json.dumps(plan))

    def test_late_anchor_guard_rejects_camera_convergence_on_locked_frame(self):
        plan = late_anchor_motion_plan()
        plan["camera_directives"] = [
            {
                "directive_id": "camera_1",
                "start_ms": 0,
                "end_ms": 8000,
                "motion": "tracking_shot",
                "amplitude": "small",
                "speed": "fast",
                "target_clause": None,
                "visible_change": (
                    "The tracking move ends exactly on the locked-frame composition."
                ),
            }
        ]

        with self.assertRaisesRegex(ValueError, "instantaneous pass-through"):
            canonical_direct_ref2v_action_plan_v4_late_anchor(json.dumps(plan))

    def test_late_anchor_guard_accepts_tracking_motion_and_pass_through(self):
        plan = late_anchor_motion_plan()
        plan["beats"][-1]["steps"][-1]["action"] = (
            "The tracked couple passes through the final-frame composition as "
            "background parallax and cloth motion continue."
        )

        canonical = canonical_direct_ref2v_action_plan_v4_late_anchor(
            json.dumps(plan)
        )

        self.assertEqual(continuing_motion_final_anchor_errors(canonical), ())

    def test_late_anchor_guard_accepts_an_explicit_no_convergence_clause(self):
        plan = late_anchor_motion_plan()
        plan["beats"][-1]["steps"][-1]["continuity_after"] = (
            "The couple keeps rotating without settling into the final-frame composition."
        )

        canonical = canonical_direct_ref2v_action_plan_v4_late_anchor(
            json.dumps(plan)
        )

        self.assertEqual(continuing_motion_final_anchor_errors(canonical), ())

    def test_late_anchor_guard_does_not_change_a_requested_natural_settle(self):
        plan = late_anchor_motion_plan(end_behavior="natural_settle")
        plan["final_state"]["final_hold_ms"] = 1000
        plan["beats"][-1]["steps"][-1]["action"] = (
            "The umbrella settles into the final-frame position."
        )

        canonical = canonical_direct_ref2v_action_plan_v4_late_anchor(
            json.dumps(plan)
        )

        self.assertEqual(json.loads(canonical)["final_state"]["final_hold_ms"], 1000)

    def test_late_anchor_guard_does_not_change_a_requested_intentional_hold(self):
        plan = late_anchor_motion_plan(end_behavior="intentional_hold")
        plan["final_state"]["final_hold_ms"] = 1200
        plan["beats"][-1]["steps"][-1]["action"] = (
            "The dancer locks into the explicitly requested final-frame pose."
        )

        canonical = canonical_direct_ref2v_action_plan_v4_late_anchor(
            json.dumps(plan)
        )

        self.assertEqual(json.loads(canonical)["final_state"]["final_hold_ms"], 1200)

    def test_camera_clean_projection_removes_plan_camera_prose_only(self):
        projection = json.loads(
            direct_ref2v_writer_plan_v4_camera_clean(
                json.dumps(camera_contaminated_motion_plan())
            )
        )
        serialized = json.dumps(projection).lower()
        semantic_values = serialized.replace('"camera_landmarks_ms"', '"landmarks_ms"')
        self.assertNotIn("camera", semantic_values)
        self.assertIn("the couple waltzes through three continuous turns", serialized)
        self.assertIn("a blue halo ignites over the moving gown", serialized)
        self.assertEqual(projection["camera_landmarks_ms"], [0])
        self.assertEqual(
            projection["final_state_snapshot"],
            "The transformed couple remains mid-waltz with the crown visible",
        )

    def test_camera_clean_compiler_does_not_reinject_plan_camera_prose(self):
        plan = canonical_direct_ref2v_action_plan_v4(
            json.dumps(camera_contaminated_motion_plan())
        )
        compiled = apply_direct_i2v_timing(
            writer_body().replace("At 00:09.000", "At 00:08.000"),
            plan,
            contract_name="H3 Base",
            dialogue_aware=True,
            motion_aware=True,
            camera_clean=True,
            insert_missing_final_landmark=True,
        )
        self.assertIn(
            "Throughout the entire shot, the couple waltzes through three "
            "continuous turns",
            compiled,
        )
        self.assertIn(
            "the transformed couple remains mid-waltz with the crown visible",
            compiled,
        )
        self.assertNotIn("camera orbit", compiled.lower())

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

    def test_full_camera_clean_generation_accepts_contaminated_approved_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = configured_service(
                directory,
                ("first_frame", "last_frame"),
                source_text="Valse dynamique en un plan de 9 secondes.",
                profile_version="0.3.1",
                cookbook_version="0.3.1",
            )

            def response(request):
                if request.operation_id == "action_plan.generate":
                    return json.dumps(camera_contaminated_motion_plan())
                return writer_body()

            gateway._content = response
            service.generate("h3-base-session", CompositionStage.BEAT_SHEET)
            service.approve("h3-base-session", CompositionStage.BEAT_SHEET)
            completed = service.generate(
                "h3-base-session", CompositionStage.FINAL_PROMPT
            )
            final = completed.final_prompt.active_revision.content
            self.assertEqual(final.count("The camera performs an arc shot"), 1)
            self.assertNotIn("camera orbit", final.lower())
            final_request = gateway.requests[-1]
            writer_input = final_request.user_prompt.lower().replace(
                '"camera_landmarks_ms"', '"landmarks_ms"'
            )
            self.assertNotIn("camera", writer_input)

    def test_full_instantaneous_anchor_generation_uses_v4_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = configured_service(
                directory,
                ("first_frame", "last_frame"),
                source_text="Valse dynamique en un plan de 9 secondes.",
                profile_version="0.3.2",
                cookbook_version="0.3.2",
            )

            def response(request):
                if request.operation_id == "action_plan.generate":
                    return json.dumps(late_anchor_motion_plan())
                return writer_body()

            gateway._content = response
            planned = service.generate(
                "h3-base-session", CompositionStage.BEAT_SHEET
            )
            self.assertEqual(
                continuing_motion_final_anchor_errors(
                    planned.beat_sheet.active_revision.content
                ),
                (),
            )
            service.approve("h3-base-session", CompositionStage.BEAT_SHEET)
            completed = service.generate(
                "h3-base-session", CompositionStage.FINAL_PROMPT
            )

            final = completed.final_prompt.active_revision.content
            self.assertIn("The video ends during the same ongoing motion", final)
            self.assertIn(
                "instantaneous frame sampled from ongoing motion",
                gateway.requests[-1].system_prompt,
            )


if __name__ == "__main__":
    unittest.main()
