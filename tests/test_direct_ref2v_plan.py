import json
import unittest

from panelforge.application.direct_ref2v_plan import (
    canonical_direct_ref2v_action_plan,
    canonical_direct_ref2v_action_plan_v2,
    direct_ref2v_action_plan_schema,
    direct_ref2v_action_plan_schema_v2,
    direct_ref2v_action_plan_warnings,
    direct_ref2v_action_plan_warnings_v2,
    direct_ref2v_camera_directives,
    direct_ref2v_camera_directives_v2,
    direct_ref2v_writer_plan_v2,
    lint_direct_ref2v_action_plan,
    lint_direct_ref2v_action_plan_v2,
    parse_direct_ref2v_action_plan,
    parse_direct_ref2v_action_plan_v2,
)


PLAN = {
    "duration_seconds": 12,
    "scene_setup": "One continuous room with stable geometry and light.",
    "continuity_invariants": ["The room and subject identity remain stable."],
    "beats": [
        {
            "beat_id": "beat_1",
            "start_ms": 0,
            "end_ms": 8000,
            "primary_action": "The subject walks to the table and places the cup.",
            "participants": ["subject_1", "cup_1", "table_1"],
            "observable_end_state": "The cup rests on the table and both hands are free.",
            "steps": [
                {
                    "step_id": "step_1",
                    "start_ms": 0,
                    "end_ms": 5000,
                    "action": "The subject carries the cup to the table.",
                    "continuity_after": "The right hand still supports cup_1.",
                },
                {
                    "step_id": "step_2",
                    "start_ms": 5000,
                    "end_ms": 8000,
                    "action": "The subject sets the cup down and releases it.",
                    "continuity_after": "Cup_1 is supported by table_1.",
                },
            ],
        }
    ],
    "final_state": {
        "start_ms": 9000,
        "description": "The subject looks at the cup while it remains on the table.",
        "hold_until_end": True,
    },
    "camera_directives": [
        {
            "directive_id": "camera_1",
            "start_ms": 0,
            "end_ms": 8000,
            "motion": "tracking_shot",
            "amplitude": "small",
            "speed": "slow",
            "target_clause": "following the subject toward the table",
            "visible_change": "A centered medium shot follows the same room geometry.",
        }
    ],
    "risks": [],
    "technical_adjustments": [],
    "overall_soundscape": "Quiet room tone, footsteps and a soft cup contact.",
    "non_diegetic_music": "N/A",
}


def plan_v2() -> dict[str, object]:
    plan = json.loads(json.dumps(PLAN))
    del plan["duration_seconds"]
    plan["final_state"] = {
        "description": "The subject looks at the cup while it remains on the table.",
        "final_hold_ms": 2000,
    }
    return plan


class DirectRef2VPlanTest(unittest.TestCase):
    def test_valid_plan_round_trips_and_exposes_camera(self):
        content = json.dumps(PLAN)
        parsed = parse_direct_ref2v_action_plan(content)
        self.assertEqual(parsed.duration_seconds, 12)
        self.assertEqual(lint_direct_ref2v_action_plan(content), ())
        canonical = canonical_direct_ref2v_action_plan(content)
        self.assertEqual(json.loads(canonical), PLAN)
        directives = direct_ref2v_camera_directives(canonical)
        self.assertEqual(directives[0].directive_id, "camera_1")

    def test_schema_is_closed_and_has_generic_fields(self):
        schema = json.loads(direct_ref2v_action_plan_schema())
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("continuity_invariants", schema["properties"])
        self.assertIn("camera_directives", schema["properties"])
        self.assertEqual(
            schema["properties"]["technical_adjustments"]["maxItems"],
            0,
        )

    def test_rejects_gaps_inside_a_beat(self):
        plan = json.loads(json.dumps(PLAN))
        plan["beats"][0]["steps"][1]["start_ms"] = 5500
        errors = lint_direct_ref2v_action_plan(json.dumps(plan))
        self.assertTrue(any("contiguous" in error for error in errors))

    def test_rejects_blank_participant_and_invariant(self):
        plan = json.loads(json.dumps(PLAN))
        plan["beats"][0]["participants"] = ["   "]
        self.assertTrue(lint_direct_ref2v_action_plan(json.dumps(plan)))
        plan = json.loads(json.dumps(PLAN))
        plan["continuity_invariants"] = ["   "]
        self.assertTrue(lint_direct_ref2v_action_plan(json.dumps(plan)))

    def test_does_not_impose_a_gesture_duration_minimum(self):
        plan = json.loads(json.dumps(PLAN))
        plan["beats"][0]["end_ms"] = 1
        plan["beats"][0]["steps"] = [{
            "step_id": "step_1",
            "start_ms": 0,
            "end_ms": 1,
            "action": "A deliberately instantaneous visual cue occurs.",
            "continuity_after": "The scene remains coherent.",
        }]
        plan["final_state"]["start_ms"] = 1
        self.assertEqual(lint_direct_ref2v_action_plan(json.dumps(plan)), ())

    def test_accepts_a_short_video_and_many_major_beats(self):
        plan = json.loads(json.dumps(PLAN))
        plan["duration_seconds"] = 1
        plan["beats"] = []
        for index in range(12):
            start_ms = index * 50
            end_ms = start_ms + 50
            plan["beats"].append({
                "beat_id": f"beat_{index + 1}",
                "start_ms": start_ms,
                "end_ms": end_ms,
                "primary_action": f"Major action {index + 1}.",
                "participants": ["subject_1"],
                "observable_end_state": f"State {index + 1} is visible.",
                "steps": [{
                    "step_id": f"step_{index + 1}",
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "action": f"Action {index + 1} occurs.",
                    "continuity_after": f"Continuity {index + 1} holds.",
                }],
            })
        plan["final_state"]["start_ms"] = 600
        plan["camera_directives"] = []
        self.assertEqual(lint_direct_ref2v_action_plan(json.dumps(plan)), ())

    def test_duration_and_unresolved_risks_are_warnings(self):
        plan = json.loads(json.dumps(PLAN))
        plan["duration_seconds"] = 18
        plan["risks"] = [
            {
                "risk_id": "risk_1",
                "category": "temporal",
                "description": "The requested action may be rushed.",
                "recommendation": "Use the full planned duration.",
                "resolution": None,
            }
        ]
        warnings = direct_ref2v_action_plan_warnings(json.dumps(plan))
        self.assertTrue(any("15" in warning for warning in warnings))
        self.assertTrue(any("risk_1" in warning for warning in warnings))

    def test_only_invalid_optional_camera_target_is_dropped(self):
        plan = json.loads(json.dumps(PLAN))
        plan["camera_directives"][0]["target_clause"] = (
            "moving backward and tilting down"
        )
        with self.assertRaises(ValueError):
            canonical_direct_ref2v_action_plan(json.dumps(plan))
        canonical = canonical_direct_ref2v_action_plan(
            json.dumps(plan), recover_invalid_target=True
        )
        decoded = json.loads(canonical)
        self.assertIsNone(decoded["camera_directives"][0]["target_clause"])
        self.assertEqual(
            decoded["technical_adjustments"],
            ["camera_target_dropped:camera_1"],
        )
        warning = direct_ref2v_action_plan_warnings(canonical)
        self.assertTrue(any("camera_1" in item for item in warning))

    def test_planner_cannot_forge_technical_adjustments(self):
        plan = json.loads(json.dumps(PLAN))
        plan["technical_adjustments"] = ["trust me"]
        with self.assertRaisesRegex(ValueError, "application-owned"):
            canonical_direct_ref2v_action_plan(
                json.dumps(plan), recover_invalid_target=True
            )


class DirectRef2VPlanV2Test(unittest.TestCase):
    def test_valid_plan_derives_timing_and_round_trips_without_it(self):
        content = json.dumps(plan_v2())
        parsed = parse_direct_ref2v_action_plan_v2(content)

        self.assertEqual(parsed.final_start_ms, 8000)
        self.assertEqual(parsed.duration_ms, 10000)
        self.assertEqual(lint_direct_ref2v_action_plan_v2(content), ())
        canonical = canonical_direct_ref2v_action_plan_v2(content)
        self.assertEqual(json.loads(canonical), plan_v2())
        self.assertNotIn("duration_ms", json.loads(canonical))
        self.assertEqual(
            direct_ref2v_camera_directives_v2(canonical)[0].directive_id,
            "camera_1",
        )

    def test_schema_excludes_application_derived_fields(self):
        schema = json.loads(direct_ref2v_action_plan_schema_v2())
        properties = schema["properties"]

        self.assertFalse(schema["additionalProperties"])
        self.assertNotIn("duration_seconds", properties)
        self.assertEqual(properties["technical_adjustments"]["maxItems"], 0)
        final_schema = schema["$defs"]["DirectFinalStateV2"]
        self.assertEqual(
            set(final_schema["properties"]),
            {"description", "final_hold_ms"},
        )
        self.assertEqual(final_schema["properties"]["final_hold_ms"]["minimum"], 0)

    def test_rejects_v1_timing_fields_from_the_planner(self):
        plan = plan_v2()
        plan["duration_seconds"] = 10
        self.assertTrue(lint_direct_ref2v_action_plan_v2(json.dumps(plan)))

        plan = plan_v2()
        plan["final_state"]["start_ms"] = 8000
        plan["final_state"]["hold_until_end"] = True
        self.assertTrue(lint_direct_ref2v_action_plan_v2(json.dumps(plan)))

    def test_camera_may_use_the_hold_but_not_exceed_derived_duration(self):
        plan = plan_v2()
        plan["camera_directives"][0]["end_ms"] = 10000
        self.assertEqual(lint_direct_ref2v_action_plan_v2(json.dumps(plan)), ())

        plan["camera_directives"][0]["end_ms"] = 10001
        errors = lint_direct_ref2v_action_plan_v2(json.dumps(plan))
        self.assertTrue(any("derived duration" in error for error in errors))

    def test_final_hold_and_long_derived_duration_are_warnings_only(self):
        plan = plan_v2()
        plan["final_state"]["final_hold_ms"] = 0
        warnings = direct_ref2v_action_plan_warnings_v2(json.dumps(plan))
        self.assertTrue(any("finale" in warning for warning in warnings))
        self.assertEqual(lint_direct_ref2v_action_plan_v2(json.dumps(plan)), ())

        plan["final_state"]["final_hold_ms"] = 500
        warnings = direct_ref2v_action_plan_warnings_v2(json.dumps(plan))
        self.assertTrue(any("1 seconde" in warning for warning in warnings))

        plan["final_state"]["final_hold_ms"] = 7001
        warnings = direct_ref2v_action_plan_warnings_v2(json.dumps(plan))
        self.assertTrue(any("15" in warning for warning in warnings))
        self.assertEqual(lint_direct_ref2v_action_plan_v2(json.dumps(plan)), ())

    def test_writer_copy_contains_derived_timing_but_persisted_json_does_not(self):
        canonical = canonical_direct_ref2v_action_plan_v2(json.dumps(plan_v2()))
        persisted = json.loads(canonical)
        writer_plan = json.loads(direct_ref2v_writer_plan_v2(canonical))

        self.assertNotIn("derived_timing", persisted)
        self.assertEqual(
            writer_plan["derived_timing"],
            {
                "final_state_start_ms": 8000,
                "duration_ms": 10000,
                "duration_seconds": 10.0,
            },
        )
        self.assertEqual(json.loads(canonical), persisted)

    def test_writer_exposes_fractional_derived_duration_seconds(self):
        plan = plan_v2()
        plan["final_state"]["final_hold_ms"] = 2250
        writer_plan = json.loads(direct_ref2v_writer_plan_v2(json.dumps(plan)))

        self.assertEqual(writer_plan["derived_timing"]["duration_ms"], 10250)
        self.assertEqual(writer_plan["derived_timing"]["duration_seconds"], 10.25)

    def test_invalid_optional_camera_target_is_fail_soft_when_requested(self):
        plan = plan_v2()
        plan["camera_directives"][0]["target_clause"] = (
            "moving backward and tilting down"
        )
        with self.assertRaises(ValueError):
            canonical_direct_ref2v_action_plan_v2(json.dumps(plan))

        canonical = canonical_direct_ref2v_action_plan_v2(
            json.dumps(plan), recover_invalid_target=True
        )
        decoded = json.loads(canonical)
        self.assertIsNone(decoded["camera_directives"][0]["target_clause"])
        self.assertEqual(
            decoded["technical_adjustments"],
            ["camera_target_dropped:camera_1"],
        )
        warnings = direct_ref2v_action_plan_warnings_v2(canonical)
        self.assertTrue(any("camera_1" in warning for warning in warnings))

    def test_v1_contract_is_unchanged(self):
        schema = json.loads(direct_ref2v_action_plan_schema())
        self.assertIn("duration_seconds", schema["properties"])
        canonical = canonical_direct_ref2v_action_plan(json.dumps(PLAN))
        self.assertEqual(json.loads(canonical), PLAN)


if __name__ == "__main__":
    unittest.main()
