import json
import unittest

from panelforge.application.direct_ref2v_multishot_plan import (
    canonical_direct_ref2v_multishot_plan,
    direct_ref2v_multishot_camera_directives,
    direct_ref2v_multishot_plan_schema,
    direct_ref2v_multishot_plan_warnings,
    direct_ref2v_multishot_writer_projection,
    lint_direct_ref2v_multishot_plan,
    parse_direct_ref2v_multishot_plan,
)


def multishot_plan() -> dict[str, object]:
    return {
        "scene_setup": "A stable workshop with warm window light.",
        "continuity_invariants": [
            "Subject identity and wardrobe remain stable.",
            "The workshop geometry and daylight direction remain stable.",
        ],
        "shots": [
            {
                "shot_id": "shot_1",
                "duration_ms": 3000,
                "purpose": "Establish the subject and the sealed box.",
                "new_information": "A faint blue light leaks through the box seam.",
                "entry_state": "The subject stands behind the sealed box.",
                "primary_action": "The subject reaches toward the lid.",
                "observable_end_state": "Both hands rest on the closed lid.",
                "active_picture_labels": ["<Picture 1>", "<Picture 2>"],
                "camera": {
                    "motion": "push.in",
                    "amplitude": "small",
                    "speed": "slow",
                    "target_clause": "toward the subject and the sealed box",
                    "visible_change": "The box fills more of the central frame.",
                },
            },
            {
                "shot_id": "shot_2",
                "duration_ms": 4000,
                "purpose": "Reveal the source of the light.",
                "new_information": "A small mechanical bird is inside the box.",
                "entry_state": "Both hands hold the lid at its front edge.",
                "primary_action": "The subject opens the lid and looks inside.",
                "observable_end_state": "The open box reveals the mechanical bird.",
                "active_picture_labels": ["<Picture 1>", "<Picture 3>"],
                "camera": None,
            },
            {
                "shot_id": "shot_3",
                "duration_ms": 5000,
                "purpose": "Resolve the discovery through a closer reaction.",
                "new_information": "The bird wakes and turns toward the subject.",
                "entry_state": "The bird is visible inside the open box.",
                "primary_action": "The bird raises its head as the subject smiles.",
                "observable_end_state": "The subject and bird look at each other.",
                "active_picture_labels": ["<Picture 1>", "<Picture 3>"],
                "camera": {
                    "motion": "pan.right",
                    "amplitude": "small",
                    "speed": "slow",
                    "target_clause": "to the bird turning toward the subject",
                    "visible_change": "The bird and the subject share the frame.",
                },
            },
        ],
        "final_state": {
            "description": "The subject and bird hold mutual eye contact.",
            "final_hold_ms": 1000,
        },
        "risks": [],
        "technical_adjustments": [],
        "overall_soundscape": "Quiet workshop, lid hinges, and soft clockwork clicks.",
        "non_diegetic_music": "N/A",
    }


class DirectRef2VMultiShotPlanTest(unittest.TestCase):
    def test_valid_plan_derives_one_non_redundant_timeline(self):
        content = json.dumps(multishot_plan())
        plan = parse_direct_ref2v_multishot_plan(content)

        self.assertEqual(plan.shot_starts_ms, (0, 3000, 7000))
        self.assertEqual(plan.hard_cut_times_ms, (3000, 7000))
        self.assertEqual(plan.final_state_start_ms, 12000)
        self.assertEqual(plan.duration_ms, 13000)
        self.assertEqual(lint_direct_ref2v_multishot_plan(content), ())

    def test_schema_is_closed_requires_exactly_three_shots_and_no_clocks(self):
        schema = json.loads(direct_ref2v_multishot_plan_schema())
        shot_schema = schema["$defs"]["DirectRef2VMultiShot"]
        camera_schema = schema["$defs"]["DirectRef2VMultiShotCamera"]

        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(shot_schema["additionalProperties"])
        self.assertFalse(camera_schema["additionalProperties"])
        self.assertEqual(schema["properties"]["shots"]["minItems"], 3)
        self.assertEqual(schema["properties"]["shots"]["maxItems"], 3)
        self.assertNotIn("start_ms", shot_schema["properties"])
        self.assertNotIn("end_ms", shot_schema["properties"])
        self.assertNotIn("cut_time_ms", shot_schema["properties"])
        self.assertNotIn("directive_id", camera_schema["properties"])
        self.assertEqual(
            set(schema["properties"]),
            {
                "scene_setup",
                "continuity_invariants",
                "shots",
                "final_state",
                "risks",
                "technical_adjustments",
                "overall_soundscape",
                "non_diegetic_music",
            },
        )

    def test_canonical_plan_persists_only_authored_fields(self):
        source = multishot_plan()
        canonical = json.loads(canonical_direct_ref2v_multishot_plan(json.dumps(source)))

        self.assertEqual(canonical, source)
        self.assertNotIn("derived_timing", canonical)
        self.assertNotIn("start_ms", canonical["shots"][1])
        self.assertNotIn("hard_cut_before", canonical["shots"][1])

    def test_json_fence_is_accepted_but_non_object_is_rejected(self):
        content = "```json\n" + json.dumps(multishot_plan()) + "\n```"
        self.assertEqual(parse_direct_ref2v_multishot_plan(content).duration_ms, 13000)
        with self.assertRaisesRegex(ValueError, "one JSON object"):
            parse_direct_ref2v_multishot_plan("[]")

    def test_two_or_four_shots_are_hard_structure_errors(self):
        plan = multishot_plan()
        plan["shots"] = plan["shots"][:2]
        self.assertTrue(lint_direct_ref2v_multishot_plan(json.dumps(plan)))

        plan = multishot_plan()
        plan["shots"].append(json.loads(json.dumps(plan["shots"][2])))
        self.assertTrue(lint_direct_ref2v_multishot_plan(json.dumps(plan)))

    def test_authored_clocks_transitions_and_camera_ids_are_forbidden(self):
        for field, value in (
            ("start_ms", 0),
            ("end_ms", 3000),
            ("transition", "dissolve"),
        ):
            plan = multishot_plan()
            plan["shots"][0][field] = value
            self.assertTrue(
                lint_direct_ref2v_multishot_plan(json.dumps(plan)),
                field,
            )

        plan = multishot_plan()
        plan["shots"][0]["camera"]["directive_id"] = "camera_1"
        self.assertTrue(lint_direct_ref2v_multishot_plan(json.dumps(plan)))

    def test_duration_and_required_semantics_are_structural(self):
        plan = multishot_plan()
        plan["shots"][0]["duration_ms"] = 0
        self.assertTrue(lint_direct_ref2v_multishot_plan(json.dumps(plan)))

        plan = multishot_plan()
        plan["shots"][0]["new_information"] = "   "
        self.assertTrue(lint_direct_ref2v_multishot_plan(json.dumps(plan)))

    def test_picture_labels_must_be_known_unique_and_ordered(self):
        for labels in (
            ["<Picture 4>"],
            ["<Picture 1>", "<Picture 1>"],
            ["<Picture 2>", "<Picture 1>"],
            [],
        ):
            plan = multishot_plan()
            plan["shots"][0]["active_picture_labels"] = labels
            self.assertTrue(
                lint_direct_ref2v_multishot_plan(json.dumps(plan)),
                labels,
            )

    def test_invalid_camera_protocol_is_a_structure_error(self):
        plan = multishot_plan()
        plan["shots"][0]["camera"]["target_clause"] = "camera moves to the box"
        self.assertTrue(lint_direct_ref2v_multishot_plan(json.dumps(plan)))

        plan = multishot_plan()
        plan["shots"][0]["camera"].update(
            {
                "motion": "static_shot",
                "amplitude": "small",
                "speed": "slow",
            }
        )
        self.assertTrue(lint_direct_ref2v_multishot_plan(json.dumps(plan)))

    def test_camera_ids_are_derived_from_shot_number_and_preserve_gaps(self):
        directives = direct_ref2v_multishot_camera_directives(
            json.dumps(multishot_plan())
        )

        self.assertEqual(
            tuple(item.directive_id for item in directives),
            ("camera_1", "camera_3"),
        )
        self.assertEqual(directives[0].motion.value, "push.in")
        self.assertEqual(directives[1].motion.value, "pan.right")

    def test_no_camera_is_valid_and_produces_no_directives(self):
        plan = multishot_plan()
        for shot in plan["shots"]:
            shot["camera"] = None

        self.assertEqual(
            direct_ref2v_multishot_camera_directives(json.dumps(plan)),
            (),
        )
        projection = json.loads(
            direct_ref2v_multishot_writer_projection(json.dumps(plan))
        )
        self.assertTrue(all(shot["camera"] is None for shot in projection["shots"]))

    def test_writer_projection_derives_headings_hard_cuts_and_camera_windows(self):
        projection = json.loads(
            direct_ref2v_multishot_writer_projection(json.dumps(multishot_plan()))
        )
        shots = projection["shots"]

        self.assertEqual(shots[0]["heading"], "[Shot 1]")
        self.assertIsNone(shots[0]["hard_cut_before"])
        self.assertEqual(shots[1]["heading"], "[Shot 2] At 00:03.000,")
        self.assertEqual(
            shots[1]["hard_cut_before"],
            {"type": "hard_cut", "at_ms": 3000},
        )
        self.assertEqual(shots[2]["heading"], "[Shot 3] At 00:07.000,")
        self.assertEqual(shots[0]["camera"]["placeholder"], "[[camera:camera_1]]")
        self.assertEqual(shots[0]["camera"]["start_ms"], 0)
        self.assertEqual(shots[0]["camera"]["end_ms"], 3000)
        self.assertEqual(shots[2]["camera"]["placeholder"], "[[camera:camera_3]]")
        self.assertEqual(shots[2]["camera"]["start_ms"], 7000)
        self.assertNotIn("motion", shots[0]["camera"])
        self.assertNotIn("amplitude", shots[0]["camera"])

    def test_writer_projection_contains_derived_duration_but_no_risks(self):
        plan = multishot_plan()
        plan["risks"] = [
            {
                "risk_id": "risk_1",
                "category": "temporal",
                "description": "The reveal may be rushed.",
                "recommendation": "Keep Shot 2 readable.",
                "resolution": "Accepted.",
            }
        ]
        projection = json.loads(
            direct_ref2v_multishot_writer_projection(json.dumps(plan))
        )

        self.assertNotIn("risks", projection)
        self.assertNotIn("technical_adjustments", projection)
        self.assertEqual(
            projection["derived_timing"],
            {
                "shot_starts_ms": [0, 3000, 7000],
                "hard_cut_times_ms": [3000, 7000],
                "final_state_start_ms": 12000,
                "duration_ms": 13000,
                "duration_seconds": 13.0,
            },
        )
        self.assertEqual(
            projection["final_state"],
            {
                "description": "The subject and bird hold mutual eye contact.",
                "start_ms": 12000,
                "final_hold_ms": 1000,
                "end_ms": 13000,
            },
        )

    def test_long_duration_and_unresolved_risks_are_warnings_not_errors(self):
        plan = multishot_plan()
        plan["shots"][2]["duration_ms"] = 9000
        plan["risks"] = [
            {
                "risk_id": "risk_time",
                "category": "temporal",
                "description": "The total duration is long.",
                "recommendation": "Confirm the target engine accepts it.",
                "resolution": None,
            }
        ]
        content = json.dumps(plan)
        warnings = direct_ref2v_multishot_plan_warnings(content)

        self.assertEqual(lint_direct_ref2v_multishot_plan(content), ())
        self.assertTrue(any("15" in warning for warning in warnings))
        self.assertTrue(any("risk_time" in warning for warning in warnings))

    def test_short_or_zero_final_hold_is_warning_only(self):
        plan = multishot_plan()
        plan["final_state"]["final_hold_ms"] = 0
        content = json.dumps(plan)
        self.assertEqual(lint_direct_ref2v_multishot_plan(content), ())
        self.assertTrue(
            any("Aucune tenue finale" in item for item in direct_ref2v_multishot_plan_warnings(content))
        )

        plan["final_state"]["final_hold_ms"] = 500
        content = json.dumps(plan)
        self.assertEqual(lint_direct_ref2v_multishot_plan(content), ())
        self.assertTrue(
            any("1 seconde" in item for item in direct_ref2v_multishot_plan_warnings(content))
        )

    def test_resolved_risk_does_not_warn_and_duplicate_risk_ids_fail(self):
        plan = multishot_plan()
        risk = {
            "risk_id": "risk_1",
            "category": "other",
            "description": "A concern.",
            "recommendation": "Review it.",
            "resolution": "Accepted.",
        }
        plan["risks"] = [risk]
        self.assertEqual(
            direct_ref2v_multishot_plan_warnings(json.dumps(plan)),
            (),
        )

        plan["risks"] = [risk, dict(risk)]
        self.assertTrue(lint_direct_ref2v_multishot_plan(json.dumps(plan)))

    def test_duplicate_continuity_invariants_are_rejected(self):
        plan = multishot_plan()
        plan["continuity_invariants"] = ["Same room.", "Same room."]
        self.assertTrue(lint_direct_ref2v_multishot_plan(json.dumps(plan)))

    def test_shot_ids_are_required_and_exactly_ordered(self):
        plan = multishot_plan()
        del plan["shots"][0]["shot_id"]
        self.assertTrue(lint_direct_ref2v_multishot_plan(json.dumps(plan)))

        plan = multishot_plan()
        plan["shots"][0]["shot_id"] = "shot_2"
        plan["shots"][1]["shot_id"] = "shot_1"
        errors = lint_direct_ref2v_multishot_plan(json.dumps(plan))
        self.assertTrue(any("exactly shot_1" in error for error in errors))

    def test_only_invalid_optional_camera_target_is_recovered(self):
        plan = multishot_plan()
        plan["shots"][2]["camera"]["target_clause"] = (
            "camera pans right toward the subject"
        )
        content = json.dumps(plan)
        with self.assertRaises(ValueError):
            canonical_direct_ref2v_multishot_plan(content)

        canonical = canonical_direct_ref2v_multishot_plan(
            content,
            recover_invalid_target=True,
        )
        recovered = json.loads(canonical)
        self.assertIsNone(recovered["shots"][2]["camera"]["target_clause"])
        self.assertEqual(recovered["shots"][2]["camera"]["motion"], "pan.right")
        self.assertEqual(
            recovered["technical_adjustments"],
            ["camera_target_dropped:camera_3"],
        )
        warnings = direct_ref2v_multishot_plan_warnings(canonical)
        self.assertTrue(any("camera_3" in warning for warning in warnings))

    def test_recovery_does_not_relax_invalid_motion_or_modifiers(self):
        plan = multishot_plan()
        camera = plan["shots"][2]["camera"]
        camera.update({"motion": "static_shot", "amplitude": "small"})
        with self.assertRaises(ValueError):
            canonical_direct_ref2v_multishot_plan(
                json.dumps(plan),
                recover_invalid_target=True,
            )

    def test_planner_cannot_forge_technical_adjustments(self):
        plan = multishot_plan()
        plan["technical_adjustments"] = ["trust me"]
        with self.assertRaisesRegex(ValueError, "application-owned"):
            canonical_direct_ref2v_multishot_plan(
                json.dumps(plan),
                recover_invalid_target=True,
            )


if __name__ == "__main__":
    unittest.main()
