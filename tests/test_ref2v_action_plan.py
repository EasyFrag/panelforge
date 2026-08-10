import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from panelforge.application.ref2v_action_plan import (
    RetimingAdjustment,
    canonical_ref2v_action_plan,
    canonical_ref2v_action_plan_v2,
    lint_ref2v_advisory_action_plan,
    lint_ref2v_bounded_action_plan,
    lint_ref2v_elastic_action_plan,
    lint_ref2v_action_plan,
    lint_ref2v_action_plan_v2,
    parse_ref2v_advisory_action_plan,
    parse_ref2v_bounded_action_plan,
    parse_ref2v_elastic_action_plan,
    parse_ref2v_action_plan,
    parse_ref2v_supervised_compiled_plan,
    ref2v_advisory_action_plan_warnings,
    ref2v_advisory_writer_plan,
    ref2v_bounded_action_plan_warnings,
    ref2v_bounded_writer_plan,
    ref2v_elastic_action_plan_warnings,
    ref2v_elastic_writer_plan,
    ref2v_action_plan_warnings_v2,
    ref2v_supervised_action_plan_warnings,
    retime_ref2v_advisory_action_plan,
    retime_ref2v_bounded_action_plan,
    retime_ref2v_action_plan_v2,
    retime_ref2v_repairable_action_plan,
    retime_ref2v_supervised_action_plan,
)


def valid_plan() -> dict:
    return {
        "duration_seconds": 10,
        "reference_policy": {
            "picture_1": "exact_first_frame",
            "picture_2": "appearance_only",
        },
        "scene_setup": "A softly lit cream studio and one adult subject.",
        "beats": [
            {
                "beat_id": "remove_top",
                "start_ms": 0,
                "end_ms": 3500,
                "action": "Remove the top in one continuous motion.",
                "object": "striped top",
                "motion_type": "over_head_removal",
                "hand_contact": "Both hands hold the lower hem until it clears the head.",
                "motion_path": "Hem travels up the torso, shoulders, arms, and head.",
                "required_end_state": "The top rests visibly on the floor to the left.",
                "expression": "Playful eye contact resumes after the fabric clears the face.",
            },
            {
                "beat_id": "remove_skirt",
                "start_ms": 3500,
                "end_ms": 7000,
                "action": "Lower the skirt and step free of it.",
                "object": "black skirt",
                "motion_type": "step_out_removal",
                "hand_contact": "Both hands keep hold of the waistband while lowering it.",
                "motion_path": "Waistband passes the hips and thighs before each foot steps free.",
                "required_end_state": "The skirt lands beside the top.",
                "expression": "The subject keeps a playful expression.",
            },
        ],
        "final_pose": {
            "start_ms": 7000,
            "description": "Shift weight to one leg and hold the requested covering pose.",
            "expression": "Direct playful eye contact.",
            "hold_until_end": True,
        },
        "camera": {
            "start_ms": 7500,
            "end_ms": 9500,
            "movement": "Pedestal down on the frontal axis while tilting upward.",
            "visible_perspective_change": "The lower body becomes more prominent against the rising background.",
            "frontal_axis": True,
            "during": "held_final_pose",
        },
        "overall_soundscape": "Quiet room tone, fabric friction, breathing, and two soft landings.",
        "non_diegetic_music": "N/A",
    }


def valid_plan_v2() -> dict:
    plan = valid_plan()
    for beat in plan["beats"]:
        beat["complexity"] = "simple"
    plan["camera"].pop("frontal_axis")
    plan["camera"]["path_type"] = "pedestal"
    return plan


def valid_supervised_plan() -> dict:
    plan = valid_plan_v2()
    plan["beats"][0]["complexity"] = "multi_step"
    plan["beats"][0]["substeps"] = [
        {
            "substep_id": "grip_and_lift",
            "start_ms": 0,
            "end_ms": 1800,
            "action": "Grip the hem and lift it to the shoulders.",
            "left_hand": "The left hand keeps the left hem under tension.",
            "right_hand": "The right hand keeps the right hem under tension.",
            "object_state_after": "The top is gathered at the shoulders.",
        },
        {
            "substep_id": "clear_and_release",
            "start_ms": 1800,
            "end_ms": 3500,
            "action": "Clear both arms and the head, then release the top.",
            "left_hand": "The left hand releases after the fabric clears the wrist.",
            "right_hand": "The right hand guides the top beside the body.",
            "object_state_after": "The top has left both hands and is settling.",
        },
    ]
    plan["beats"][1]["substeps"] = [
        {
            "substep_id": "lower_and_step_free",
            "start_ms": 3500,
            "end_ms": 7000,
            "action": "Lower the skirt and step free of it.",
            "left_hand": "The left hand holds the left waistband until release.",
            "right_hand": "The right hand holds the right waistband until release.",
            "object_state_after": "The skirt is released and rests beside the top.",
        }
    ]
    plan["continuity_concerns"] = [
        {
            "concern_id": "covered_region",
            "category": "state_visibility_conflict",
            "description": "The requested visible region remains covered by the retained skirt.",
            "proposed_resolution": "Either retain the skirt and remove the visibility request, or add an explicit skirt action.",
            "resolution": None,
        }
    ]
    return plan


class Ref2VActionPlanTest(unittest.TestCase):
    def test_canonical_round_trip(self):
        content = "```json\n" + json.dumps(valid_plan()) + "\n```"

        canonical = canonical_ref2v_action_plan(content)

        self.assertEqual(lint_ref2v_action_plan(canonical), ())
        self.assertEqual(parse_ref2v_action_plan(canonical).duration_seconds, 10)
        self.assertEqual(json.loads(canonical), valid_plan())

    def test_rejects_overlapping_beats(self):
        plan = valid_plan()
        plan["beats"][1]["start_ms"] = 3000

        errors = lint_ref2v_action_plan(json.dumps(plan))

        self.assertTrue(any("non-overlapping" in error for error in errors))

    def test_rejects_an_overhead_removal_shorter_than_three_seconds(self):
        plan = valid_plan()
        plan["beats"][0]["end_ms"] = 2500
        plan["beats"][1]["start_ms"] = 2500

        errors = lint_ref2v_action_plan(json.dumps(plan))

        self.assertTrue(any("too short" in error for error in errors))

    def test_rejects_a_final_pose_held_for_less_than_two_seconds(self):
        plan = valid_plan()
        plan["final_pose"]["start_ms"] = 8500
        plan["camera"]["start_ms"] = 8500

        errors = lint_ref2v_action_plan(json.dumps(plan))

        self.assertTrue(any("at least 2000 ms" in error for error in errors))

    def test_rejects_camera_motion_before_the_final_pose(self):
        plan = valid_plan()
        plan["camera"]["start_ms"] = 6500

        errors = lint_ref2v_action_plan(json.dumps(plan))

        self.assertTrue(any("held final pose" in error for error in errors))

    def test_v2_accepts_an_explicit_orbit_without_a_frontal_axis_contradiction(self):
        plan = valid_plan_v2()
        plan["camera"]["path_type"] = "orbit"
        plan["camera"]["movement"] = "A restrained clockwise orbit around the held pose."

        canonical = canonical_ref2v_action_plan_v2(json.dumps(plan))

        self.assertEqual(lint_ref2v_action_plan_v2(canonical), ())
        self.assertNotIn("frontal_axis", canonical)
        self.assertIn('"path_type": "orbit"', canonical)

    def test_v2_warns_without_rejecting_a_short_multi_step_removal(self):
        plan = valid_plan_v2()
        plan["beats"][0]["complexity"] = "multi_step"

        errors = lint_ref2v_action_plan_v2(json.dumps(plan))
        warnings = ref2v_action_plan_warnings_v2(json.dumps(plan))

        self.assertEqual(errors, ())
        self.assertTrue(any("sans blocage" in warning for warning in warnings))
        self.assertTrue(any("remove_top" in warning for warning in warnings))

    def test_v2_rejects_the_legacy_frontal_axis_field(self):
        plan = valid_plan_v2()
        plan["camera"]["frontal_axis"] = True

        errors = lint_ref2v_action_plan_v2(json.dumps(plan))

        self.assertTrue(any("frontal_axis" in error for error in errors))

    def test_elastic_plan_expands_short_beats_and_shifts_later_timing(self):
        plan = valid_plan_v2()
        plan["beats"][0]["end_ms"] = 1500
        plan["beats"][0]["motion_type"] = "simple_removal"
        plan["beats"][1]["start_ms"] = 1500
        plan["beats"][1]["end_ms"] = 3000
        plan["final_pose"]["start_ms"] = 8000
        plan["camera"]["start_ms"] = 8500

        retimed = retime_ref2v_action_plan_v2(json.dumps(plan))
        parsed = parse_ref2v_elastic_action_plan(retimed)

        self.assertEqual(lint_ref2v_elastic_action_plan(retimed), ())
        self.assertEqual(parsed.requested_duration_seconds, 10)
        self.assertEqual(parsed.duration_seconds, 12)
        self.assertEqual(parsed.beats[0].end_ms, 2000)
        self.assertEqual(parsed.beats[1].start_ms, 2000)
        self.assertEqual(parsed.beats[1].end_ms, 5000)
        self.assertEqual(parsed.final_pose.start_ms, 10000)
        self.assertEqual(parsed.camera.start_ms, 10500)
        self.assertIn("10 s à 12 s", ref2v_elastic_action_plan_warnings(retimed)[0])
        self.assertNotIn("requested_duration_seconds", ref2v_elastic_writer_plan(retimed))

    def test_bounded_plan_uses_final_hold_and_camera_before_extending(self):
        plan = valid_plan_v2()
        plan["duration_seconds"] = 14
        plan["beats"][0]["start_ms"] = 0
        plan["beats"][0]["end_ms"] = 4000
        plan["beats"].insert(
            1,
            {
                "beat_id": "remove_belt",
                "start_ms": 4000,
                "end_ms": 6500,
                "action": "Unfasten and remove the belt.",
                "object": "black belt",
                "motion_type": "simple_removal",
                "hand_contact": "Both hands release the buckle and pull the belt free.",
                "motion_path": "Buckle release, belt through loops, then down to the floor.",
                "required_end_state": "The belt rests on the floor.",
                "expression": "Focused and calm.",
                "complexity": "multi_step",
            },
        )
        plan["beats"][2]["start_ms"] = 6500
        plan["beats"][2]["end_ms"] = 10500
        plan["beats"][2]["complexity"] = "multi_step"
        plan["final_pose"]["start_ms"] = 10500
        plan["camera"]["start_ms"] = 11500
        plan["camera"]["end_ms"] = 14000

        retimed = retime_ref2v_bounded_action_plan(json.dumps(plan))
        parsed = parse_ref2v_bounded_action_plan(retimed)

        self.assertEqual(lint_ref2v_bounded_action_plan(retimed), ())
        self.assertEqual(parsed.requested_duration_seconds, 14)
        self.assertEqual(parsed.duration_seconds, 14)
        self.assertEqual(parsed.beats[0].end_ms, 4000)
        self.assertEqual(parsed.beats[1].start_ms, 4000)
        self.assertEqual(parsed.beats[1].end_ms, 7500)
        self.assertEqual(parsed.beats[2].start_ms, 7500)
        self.assertEqual(parsed.beats[2].end_ms, 12000)
        self.assertEqual(parsed.final_pose.start_ms, 12000)
        self.assertEqual(parsed.camera.start_ms, 12000)
        self.assertEqual(parsed.camera.end_ms, 14000)
        self.assertEqual(
            parsed.timing_adjustments,
            (
                RetimingAdjustment.FINAL_HOLD_REDUCED,
                RetimingAdjustment.CAMERA_RESCHEDULED,
                RetimingAdjustment.CAMERA_SHORTENED,
            ),
        )
        warnings = ref2v_bounded_action_plan_warnings(retimed)
        self.assertTrue(any("pose finale" in warning for warning in warnings))
        self.assertTrue(any("caméra" in warning for warning in warnings))
        writer_plan = ref2v_bounded_writer_plan(retimed)
        self.assertNotIn("requested_duration_seconds", writer_plan)
        self.assertNotIn("timing_adjustments", writer_plan)

    def test_bounded_plan_does_not_expand_a_simple_atomic_motion(self):
        plan = valid_plan_v2()
        plan["beats"][0]["end_ms"] = 500
        plan["beats"][0]["motion_type"] = "other"
        plan["beats"][1]["start_ms"] = 500

        retimed = retime_ref2v_bounded_action_plan(json.dumps(plan))
        parsed = parse_ref2v_bounded_action_plan(retimed)

        self.assertEqual(parsed.beats[0].end_ms, 500)
        self.assertEqual(parsed.beats[1].start_ms, 500)
        self.assertEqual(parsed.duration_seconds, 10)
        self.assertEqual(parsed.timing_adjustments, ())

    def test_bounded_plan_warns_instead_of_failing_at_the_fifteen_second_cap(self):
        plan = valid_plan_v2()
        plan["duration_seconds"] = 15
        plan["beats"][0]["complexity"] = "multi_step"
        plan["final_pose"]["start_ms"] = 13000
        plan["camera"]["start_ms"] = 13000
        plan["camera"]["end_ms"] = 15000

        retimed = retime_ref2v_bounded_action_plan(json.dumps(plan))
        parsed = parse_ref2v_bounded_action_plan(retimed)

        self.assertEqual(lint_ref2v_bounded_action_plan(retimed), ())
        self.assertEqual(parsed.duration_seconds, 15)
        self.assertEqual(parsed.beats[0].end_ms, 3500)
        self.assertIn(RetimingAdjustment.MARGINS_CAPPED, parsed.timing_adjustments)
        self.assertTrue(
            any(
                "sans bloquer" in warning
                for warning in ref2v_bounded_action_plan_warnings(retimed)
            )
        )

    def test_advisory_plan_preserves_pose_to_camera_delay_and_camera_duration(self):
        plan = valid_plan_v2()
        for beat in plan["beats"]:
            beat["complexity"] = "multi_step"

        retimed = retime_ref2v_advisory_action_plan(json.dumps(plan))
        parsed = parse_ref2v_advisory_action_plan(retimed)

        self.assertEqual(lint_ref2v_advisory_action_plan(retimed), ())
        self.assertEqual(parsed.requested_duration_seconds, 10)
        self.assertEqual(parsed.duration_seconds, 12)
        self.assertEqual(parsed.beats[0].end_ms, 4500)
        self.assertEqual(parsed.beats[1].start_ms, 4500)
        self.assertEqual(parsed.beats[1].end_ms, 9000)
        self.assertEqual(parsed.final_pose.start_ms, 9000)
        self.assertEqual(parsed.camera.start_ms, 9500)
        self.assertEqual(parsed.camera.end_ms, 11500)
        self.assertNotIn("requested_duration_seconds", ref2v_advisory_writer_plan(retimed))

    def test_advisory_plan_allows_more_than_fifteen_seconds_with_a_warning(self):
        plan = valid_plan_v2()
        plan["duration_seconds"] = 15
        for beat in plan["beats"]:
            beat["complexity"] = "multi_step"
        plan["final_pose"]["start_ms"] = 13000
        plan["camera"]["start_ms"] = 13500
        plan["camera"]["end_ms"] = 15000

        retimed = retime_ref2v_advisory_action_plan(json.dumps(plan))
        parsed = parse_ref2v_advisory_action_plan(retimed)
        warnings = ref2v_advisory_action_plan_warnings(retimed)

        self.assertEqual(lint_ref2v_advisory_action_plan(retimed), ())
        self.assertEqual(parsed.duration_seconds, 17)
        self.assertIn(RetimingAdjustment.DURATION_OVER_15, parsed.timing_adjustments)
        self.assertTrue(any("dépasse 15 s" in warning for warning in warnings))

    def test_repairable_plan_adds_a_final_hold_when_pose_starts_at_requested_end(self):
        plan = valid_plan_v2()
        plan["beats"][1]["end_ms"] = 10_000
        plan["final_pose"]["start_ms"] = 10_000
        plan["camera"] = None

        retimed = retime_ref2v_repairable_action_plan(json.dumps(plan))
        parsed = parse_ref2v_advisory_action_plan(retimed)
        warnings = ref2v_advisory_action_plan_warnings(retimed)

        self.assertEqual(lint_ref2v_advisory_action_plan(retimed), ())
        self.assertEqual(parsed.requested_duration_seconds, 10)
        self.assertEqual(parsed.duration_seconds, 12)
        self.assertEqual(parsed.final_pose.start_ms, 10_000)
        self.assertIn(
            RetimingAdjustment.FINAL_HOLD_REPAIRED,
            parsed.timing_adjustments,
        )
        self.assertTrue(any("2 s" in warning for warning in warnings))

    def test_supervised_plan_preserves_user_timings_and_exposes_concerns(self):
        plan = valid_supervised_plan()
        plan["beats"][1]["end_ms"] = 10_000
        plan["beats"][1]["substeps"][0]["end_ms"] = 10_000
        plan["final_pose"]["start_ms"] = 10_000
        plan["camera"] = None

        retimed = retime_ref2v_supervised_action_plan(json.dumps(plan))
        parsed = parse_ref2v_supervised_compiled_plan(retimed)
        warnings = ref2v_supervised_action_plan_warnings(retimed)

        self.assertEqual(parsed.requested_duration_seconds, 10)
        self.assertEqual(parsed.duration_seconds, 12)
        self.assertEqual(parsed.beats[0].end_ms, 3500)
        self.assertEqual(parsed.beats[0].substeps[0].end_ms, 1800)
        self.assertIn(RetimingAdjustment.FINAL_HOLD_REPAIRED, parsed.timing_adjustments)
        self.assertTrue(any("state_visibility_conflict" in item for item in warnings))

    def test_supervised_plan_rejects_a_gap_between_substeps(self):
        plan = valid_supervised_plan()
        plan["beats"][0]["substeps"][1]["start_ms"] = 2000

        with self.assertRaisesRegex(ValueError, "substeps must be contiguous"):
            retime_ref2v_supervised_action_plan(json.dumps(plan))

    def test_supervised_plan_warns_instead_of_rejecting_a_short_camera_move(self):
        plan = valid_supervised_plan()
        plan["camera"]["start_ms"] = 7500
        plan["camera"]["end_ms"] = 8000

        compiled = retime_ref2v_supervised_action_plan(json.dumps(plan))
        warnings = ref2v_supervised_action_plan_warnings(compiled)

        self.assertEqual(parse_ref2v_supervised_compiled_plan(compiled).duration_seconds, 10)
        self.assertTrue(any("moins d’une seconde" in item for item in warnings))

    def test_supervised_plan_normalizes_an_explicitly_static_camera(self):
        plan = valid_supervised_plan()
        plan["camera"] = {
            "start_ms": 0,
            "end_ms": 10_000,
            "path_type": "other",
            "movement": "Fixed tripod with no pan, tilt, zoom, or dolly.",
            "visible_perspective_change": "None",
            "during": "held_final_pose",
        }

        compiled = retime_ref2v_supervised_action_plan(json.dumps(plan))
        parsed = parse_ref2v_supervised_compiled_plan(compiled)
        warnings = ref2v_supervised_action_plan_warnings(compiled)

        self.assertIsNone(parsed.camera)
        self.assertIn(
            RetimingAdjustment.STATIC_CAMERA_NORMALIZED,
            parsed.timing_adjustments,
        )
        self.assertTrue(any("camera: null" in item for item in warnings))

    def test_supervised_plan_still_rejects_a_real_camera_move_before_final_pose(self):
        plan = valid_supervised_plan()
        plan["camera"]["start_ms"] = 0
        plan["camera"]["end_ms"] = 6000

        with self.assertRaisesRegex(ValueError, "camera movement must start"):
            retime_ref2v_supervised_action_plan(json.dumps(plan))


if __name__ == "__main__":
    unittest.main()
