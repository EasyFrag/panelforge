import copy
import json
import unittest

from panelforge.application.direct_ref2v_multishot_plan_v2 import (
    canonical_direct_ref2v_multishot_plan_v2,
    direct_ref2v_multishot_camera_directives_v2,
    direct_ref2v_multishot_plan_schema_v2,
    direct_ref2v_multishot_plan_warnings_v2,
    direct_ref2v_multishot_writer_projection_v2,
    lint_direct_ref2v_multishot_plan_v2,
    parse_direct_ref2v_multishot_plan_v2,
)


def _continuity(label: str) -> dict[str, str]:
    return {
        "spatial_anchor": f"The blue crate remains {label} of frame.",
        "subject_position": "The runner remains centered on the wet lane.",
        "travel_direction": "The runner continues toward screen right.",
        "motion_phase": "The next shot resumes the same forward stride.",
    }


def _shot(
    number: int,
    duration_ms: int,
    *,
    camera: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "duration_ms": duration_ms,
        "opening_composition": {
            "scale": "wide shot" if number == 1 else "medium shot",
            "angle": "eye level",
            "axis": "camera remains on the runner's left side",
            "perspective": "street-level perspective with clear depth",
        },
        "purpose": f"Advance the chase in visual phase {number}.",
        "new_information": f"Obstacle {number} becomes visible.",
        "continuity_from_previous": None if number == 1 else _continuity("left"),
        "actions": [
            f"The runner approaches obstacle {number}.",
            f"The runner clears obstacle {number}.",
        ],
        "observable_end_state": f"Obstacle {number} is behind the runner.",
        "active_picture_labels": ["<Picture 1>", "<Picture 2>"],
        "camera": camera,
    }


def multishot_plan_v2() -> dict[str, object]:
    camera_one = {
        "motion": "push.in",
        "amplitude": "small",
        "speed": "slow",
        "target_clause": "toward the runner entering the wet lane",
        "visible_change": "The runner occupies more of the central frame.",
    }
    camera_four = {
        "motion": "pan.right",
        "amplitude": "small",
        "speed": "fast",
        "target_clause": "with the runner clearing the last obstacle",
        "visible_change": "The runner remains centered through the landing.",
    }
    return {
        "scene_setup": "A rain-soaked alley with a stable line of blue crates.",
        "continuity_invariants": [
            "The runner's identity and armor remain stable.",
            "Travel continues toward screen right across every hard cut.",
        ],
        "shots": [
            _shot(1, 2500, camera=camera_one),
            _shot(2, 3000),
            _shot(3, 3500),
            _shot(4, 4000, camera=camera_four),
        ],
        "final_state": {
            "description": "The runner lands beyond the last blue crate.",
            "final_hold_ms": 1000,
        },
        "risks": [],
        "technical_adjustments": [],
        "overall_soundscape": "Rain, footfalls, armor movement, and crate impacts.",
        "non_diegetic_music": "N/A",
    }


class DirectRef2VMultiShotPlanV2Test(unittest.TestCase):
    def test_dynamic_timeline_and_ids_are_derived_from_array_order(self):
        content = json.dumps(multishot_plan_v2())
        plan = parse_direct_ref2v_multishot_plan_v2(content)

        self.assertEqual(plan.shot_ids, ("shot_1", "shot_2", "shot_3", "shot_4"))
        self.assertEqual(plan.shot_starts_ms, (0, 2500, 5500, 9000))
        self.assertEqual(plan.hard_cut_times_ms, (2500, 5500, 9000))
        self.assertEqual(plan.final_state_start_ms, 13000)
        self.assertEqual(plan.duration_ms, 14000)
        self.assertEqual(lint_direct_ref2v_multishot_plan_v2(content), ())

    def test_schema_is_closed_flexible_and_contains_no_redundant_identifiers(self):
        schema = json.loads(direct_ref2v_multishot_plan_schema_v2())
        shot_schema = schema["$defs"]["DirectRef2VMultiShotV2"]
        camera_schema = schema["$defs"]["DirectRef2VMultiShotCameraV2"]
        opening_schema = schema["$defs"]["DirectRef2VMultiShotOpeningCompositionV2"]
        continuity_schema = schema["$defs"]["DirectRef2VMultiShotContinuityV2"]

        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(shot_schema["additionalProperties"])
        self.assertEqual(schema["properties"]["shots"]["minItems"], 2)
        self.assertEqual(schema["properties"]["shots"]["maxItems"], 6)
        for forbidden in (
            "shot_id",
            "start_ms",
            "end_ms",
            "cut_time_ms",
            "transition",
        ):
            self.assertNotIn(forbidden, shot_schema["properties"])
        self.assertNotIn("directive_id", camera_schema["properties"])
        self.assertEqual(
            set(opening_schema["required"]),
            {"scale", "angle", "axis", "perspective"},
        )
        self.assertEqual(
            set(continuity_schema["required"]),
            {
                "spatial_anchor",
                "subject_position",
                "travel_direction",
                "motion_phase",
            },
        )

    def test_two_through_six_shots_are_valid_but_product_limits_are_structural(self):
        source = multishot_plan_v2()
        two = copy.deepcopy(source)
        two["shots"] = two["shots"][:2]
        self.assertEqual(lint_direct_ref2v_multishot_plan_v2(json.dumps(two)), ())

        six = copy.deepcopy(source)
        six["shots"].extend([_shot(5, 1000), _shot(6, 1000)])
        self.assertEqual(lint_direct_ref2v_multishot_plan_v2(json.dumps(six)), ())

        one = copy.deepcopy(source)
        one["shots"] = one["shots"][:1]
        self.assertTrue(lint_direct_ref2v_multishot_plan_v2(json.dumps(one)))

        seven = copy.deepcopy(six)
        seven["shots"].append(_shot(7, 1000))
        self.assertTrue(lint_direct_ref2v_multishot_plan_v2(json.dumps(seven)))

    def test_first_continuity_must_be_null_and_later_continuity_is_required(self):
        source = multishot_plan_v2()
        source["shots"][0]["continuity_from_previous"] = _continuity("left")
        errors = lint_direct_ref2v_multishot_plan_v2(json.dumps(source))
        self.assertTrue(any("Shot 1" in error for error in errors))

        source = multishot_plan_v2()
        source["shots"][2]["continuity_from_previous"] = None
        errors = lint_direct_ref2v_multishot_plan_v2(json.dumps(source))
        self.assertTrue(any("Shot 3" in error for error in errors))

    def test_authored_ids_clocks_and_transitions_are_forbidden(self):
        for field, value in (
            ("shot_id", "shot_1"),
            ("start_ms", 0),
            ("end_ms", 2500),
            ("transition", "dissolve"),
        ):
            source = multishot_plan_v2()
            source["shots"][0][field] = value
            self.assertTrue(lint_direct_ref2v_multishot_plan_v2(json.dumps(source)), field)

        source = multishot_plan_v2()
        source["shots"][0]["camera"]["directive_id"] = "camera_1"
        self.assertTrue(lint_direct_ref2v_multishot_plan_v2(json.dumps(source)))

    def test_opening_composition_actions_and_duration_are_structural(self):
        for mutate in (
            lambda value: value["shots"][0].update({"duration_ms": 0}),
            lambda value: value["shots"][0]["opening_composition"].update(
                {"perspective": ""}
            ),
            lambda value: value["shots"][0].update({"actions": []}),
            lambda value: value["shots"][0].update(
                {"actions": ["Repeated action.", "Repeated action."]}
            ),
        ):
            source = multishot_plan_v2()
            mutate(source)
            self.assertTrue(lint_direct_ref2v_multishot_plan_v2(json.dumps(source)))

    def test_picture_labels_are_known_unique_and_ordered(self):
        for labels in (
            ["<Picture 4>"],
            ["<Picture 1>", "<Picture 1>"],
            ["<Picture 2>", "<Picture 1>"],
            [],
        ):
            source = multishot_plan_v2()
            source["shots"][0]["active_picture_labels"] = labels
            self.assertTrue(
                lint_direct_ref2v_multishot_plan_v2(json.dumps(source)),
                labels,
            )

    def test_camera_protocol_is_strict_and_ids_preserve_shot_gaps(self):
        directives = direct_ref2v_multishot_camera_directives_v2(
            json.dumps(multishot_plan_v2())
        )
        self.assertEqual(
            tuple(directive.directive_id for directive in directives),
            ("camera_1", "camera_4"),
        )
        self.assertEqual(directives[0].motion.value, "push.in")
        self.assertEqual(directives[1].motion.value, "pan.right")

        source = multishot_plan_v2()
        source["shots"][0]["camera"]["target_clause"] = "camera moves to the runner"
        self.assertTrue(lint_direct_ref2v_multishot_plan_v2(json.dumps(source)))

        source = multishot_plan_v2()
        source["shots"][0]["camera"].update(
            {"motion": "static_shot", "amplitude": "small", "speed": "slow"}
        )
        self.assertTrue(lint_direct_ref2v_multishot_plan_v2(json.dumps(source)))

    def test_no_camera_is_valid_and_projection_contains_no_camera_information(self):
        source = multishot_plan_v2()
        for shot in source["shots"]:
            shot["camera"] = None
        content = json.dumps(source)

        self.assertEqual(direct_ref2v_multishot_camera_directives_v2(content), ())
        projection_text = direct_ref2v_multishot_writer_projection_v2(content)
        self.assertNotIn('"camera"', projection_text)
        self.assertNotIn('"motion"', projection_text)
        self.assertNotIn('"visible_change"', projection_text)
        self.assertNotIn("[[", projection_text)

    def test_writer_projection_derives_dynamic_headings_cuts_and_timing(self):
        projection_text = direct_ref2v_multishot_writer_projection_v2(
            json.dumps(multishot_plan_v2())
        )
        projection = json.loads(projection_text)
        shots = projection["shots"]

        self.assertEqual(len(shots), 4)
        self.assertEqual(shots[0]["shot_id"], "shot_1")
        self.assertEqual(shots[0]["heading"], "[Shot 1]")
        self.assertIsNone(shots[0]["hard_cut_before"])
        self.assertEqual(shots[1]["heading"], "[Shot 2] At 00:02.500,")
        self.assertEqual(
            shots[1]["hard_cut_before"],
            {"type": "hard_cut", "at_ms": 2500},
        )
        self.assertEqual(shots[3]["heading"], "[Shot 4] At 00:09.000,")
        self.assertEqual(shots[3]["actions"][1], "The runner clears obstacle 4.")
        for shot in shots:
            self.assertNotIn("camera", shot)
        self.assertNotIn("risks", projection)
        self.assertNotIn("technical_adjustments", projection)
        self.assertEqual(
            projection["derived_timing"],
            {
                "shot_ids": ["shot_1", "shot_2", "shot_3", "shot_4"],
                "shot_starts_ms": [0, 2500, 5500, 9000],
                "hard_cut_times_ms": [2500, 5500, 9000],
                "final_state_start_ms": 13000,
                "duration_ms": 14000,
                "duration_seconds": 14.0,
            },
        )

    def test_canonical_plan_persists_authored_fields_only(self):
        source = multishot_plan_v2()
        canonical = json.loads(
            canonical_direct_ref2v_multishot_plan_v2(json.dumps(source))
        )

        self.assertEqual(canonical, source)
        self.assertNotIn("derived_timing", canonical)
        self.assertNotIn("shot_id", canonical["shots"][0])

    def test_json_fence_is_accepted_but_non_object_is_rejected(self):
        source = multishot_plan_v2()
        fenced = "```json\n" + json.dumps(source) + "\n```"
        self.assertEqual(parse_direct_ref2v_multishot_plan_v2(fenced).duration_ms, 14000)
        with self.assertRaisesRegex(ValueError, "one JSON object"):
            parse_direct_ref2v_multishot_plan_v2("[]")

    def test_long_duration_short_hold_and_unresolved_risks_are_warning_only(self):
        source = multishot_plan_v2()
        source["shots"][3]["duration_ms"] = 7000
        source["final_state"]["final_hold_ms"] = 500
        source["risks"] = [
            {
                "risk_id": "risk_time",
                "category": "temporal",
                "description": "The sequence may be long.",
                "recommendation": "Confirm the target engine duration.",
                "resolution": None,
            }
        ]
        content = json.dumps(source)
        warnings = direct_ref2v_multishot_plan_warnings_v2(content)

        self.assertEqual(lint_direct_ref2v_multishot_plan_v2(content), ())
        self.assertTrue(any("15" in warning for warning in warnings))
        self.assertTrue(any("1 seconde" in warning for warning in warnings))
        self.assertTrue(any("risk_time" in warning for warning in warnings))

    def test_zero_hold_is_warning_only(self):
        source = multishot_plan_v2()
        source["final_state"]["final_hold_ms"] = 0
        content = json.dumps(source)

        self.assertEqual(lint_direct_ref2v_multishot_plan_v2(content), ())
        self.assertTrue(
            any(
                "Aucune tenue finale" in warning
                for warning in direct_ref2v_multishot_plan_warnings_v2(content)
            )
        )

    def test_exactly_repeated_composition_and_new_information_are_warnings(self):
        source = multishot_plan_v2()
        source["shots"][1]["opening_composition"] = source["shots"][0][
            "opening_composition"
        ].copy()
        source["shots"][1]["new_information"] = source["shots"][0][
            "new_information"
        ]

        warnings = direct_ref2v_multishot_plan_warnings_v2(json.dumps(source))

        self.assertTrue(any("meme composition" in warning for warning in warnings))
        self.assertTrue(
            any("meme information nouvelle" in warning for warning in warnings)
        )

    def test_duplicate_invariants_and_risk_ids_are_rejected(self):
        source = multishot_plan_v2()
        source["continuity_invariants"] = ["Same alley.", "Same alley."]
        self.assertTrue(lint_direct_ref2v_multishot_plan_v2(json.dumps(source)))

        source = multishot_plan_v2()
        risk = {
            "risk_id": "risk_1",
            "category": "other",
            "description": "A concern.",
            "recommendation": "Review it.",
            "resolution": "Accepted.",
        }
        source["risks"] = [risk, copy.deepcopy(risk)]
        self.assertTrue(lint_direct_ref2v_multishot_plan_v2(json.dumps(source)))

    def test_only_invalid_optional_camera_target_is_recovered(self):
        source = multishot_plan_v2()
        source["shots"][3]["camera"]["target_clause"] = (
            "camera pans right toward the runner"
        )
        content = json.dumps(source)
        with self.assertRaises(ValueError):
            canonical_direct_ref2v_multishot_plan_v2(content)

        recovered = json.loads(
            canonical_direct_ref2v_multishot_plan_v2(
                content,
                recover_invalid_target=True,
            )
        )
        self.assertIsNone(recovered["shots"][3]["camera"]["target_clause"])
        self.assertEqual(recovered["shots"][3]["camera"]["motion"], "pan.right")
        self.assertEqual(
            recovered["technical_adjustments"],
            ["camera_target_dropped:camera_4"],
        )
        self.assertTrue(
            any(
                "camera_4" in warning
                for warning in direct_ref2v_multishot_plan_warnings_v2(
                    json.dumps(recovered)
                )
            )
        )

    def test_recovery_does_not_relax_motion_and_planner_cannot_forge_adjustments(self):
        source = multishot_plan_v2()
        source["shots"][3]["camera"].update(
            {"motion": "static_shot", "amplitude": "small"}
        )
        with self.assertRaises(ValueError):
            canonical_direct_ref2v_multishot_plan_v2(
                json.dumps(source),
                recover_invalid_target=True,
            )

        source = multishot_plan_v2()
        source["technical_adjustments"] = ["trust me"]
        with self.assertRaisesRegex(ValueError, "application-owned"):
            canonical_direct_ref2v_multishot_plan_v2(
                json.dumps(source),
                recover_invalid_target=True,
            )


if __name__ == "__main__":
    unittest.main()
