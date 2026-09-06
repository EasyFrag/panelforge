"""Offline contracts for opt-in compact recipes; no real model or renderer."""

import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from panelforge.application.direct_i2v_prompt import apply_direct_i2v_timing
from panelforge.application.direct_ref2v_prompt import apply_direct_ref2v_timing_v4
from panelforge.application.direct_ref2v_plan import (
    direct_ref2v_writer_plan_v4_camera_clean,
    direct_ref2v_writer_plan_v5_compact,
)
from panelforge.application.prompt_composition import _validate_bindings, _writer_action_plan
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from tests.test_direct_ref2v_composition import action_plan_v4


ROOT = Path(__file__).resolve().parents[1]
PAIRS = (("minimax.h3.fl2va.direct", "0.3.3", "0.4.0"),
         ("minimax.h3.ref2v.direct", "0.4.0", "0.5.0"))


class ExperimentalMonoTest(unittest.TestCase):
    def test_new_profiles_and_recipes_preserve_contracts_and_select_the_new_projection(self):
        cookbooks = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        profiles = LocalPromptProfileCatalog(ROOT / "prompt_profiles")
        for family, old, new in PAIRS:
            with self.subTest(family=family):
                previous = cookbooks.get(family, old)
                current = cookbooks.get(family, new)
                self.assertEqual(current.output_contract, previous.output_contract)
                self.assertEqual(current.slots, previous.slots)
                self.assertEqual(previous.writer_projection, "camera_clean_v4")
                self.assertEqual(current.writer_projection, "camera_clean_compact_v5")
                self.assertEqual(profiles.get(family, new).version, new)
                plan = json.dumps(action_plan_v4(with_camera=False))
                self.assertEqual(_writer_action_plan(current, plan), direct_ref2v_writer_plan_v5_compact(plan))
                self.assertEqual(_writer_action_plan(previous, plan), direct_ref2v_writer_plan_v4_camera_clean(plan))

    def test_compact_projection_keeps_unique_facts_and_timing_and_does_not_mutate_plan(self):
        plan = action_plan_v4(dialogue_text="Texte exact à conserver.")
        first = plan["beats"][0]
        first["steps"] = first["steps"][:1]
        first["steps"][0]["end_ms"] = first["end_ms"]
        first["primary_action"] = first["steps"][0]["action"]
        first["observable_end_state"] = first["steps"][-1]["continuity_after"]
        source = json.dumps(plan)
        old = json.loads(direct_ref2v_writer_plan_v4_camera_clean(source))
        text = direct_ref2v_writer_plan_v5_compact(source)
        new = json.loads(text)
        self.assertEqual(json.loads(source), plan)
        self.assertEqual(new["camera_landmarks_ms"], old["camera_landmarks_ms"])
        self.assertEqual(new["derived_timing"]["duration_ms"], old["derived_timing"]["duration_ms"])
        self.assertNotIn("primary_action", new["beats"][0])
        self.assertEqual(new["beats"][0]["steps"][0]["action"], old["beats"][0]["steps"][0]["action"])
        self.assertEqual(new["dialogue_cues"], [{"cue_id": "dialogue_1", "start_ms": 2000,
                                              "speaker_id": "S1", "speaker": "Courier"}])
        self.assertNotIn("Texte exact", text)
        self.assertNotIn("final_state_snapshot", new)
        self.assertLess(len(text), len(json.dumps(old, ensure_ascii=False, indent=2)))

    def test_new_compilation_does_not_extend_final_phase_over_the_entire_shot(self):
        plan = action_plan_v4(with_camera=False)
        plan["motion_contract"]["primary_motion"] = "The crystal plant grows upward."
        plan["final_state"]["description"] = "The crystal leaves are open."
        source = json.dumps(plan)
        h3 = ("integrated_multimodal_description: [Shot 1] The target video is one continuous 12-second shot. "
              "A hand plants a seed, releases it and withdraws. The crystal plant starts growing.\n"
              "overall_soundscape: N/A\nnon_diegetic_music: N/A")
        ref = ("The target video is one continuous 12-second shot. A seed rests on soil.\n"
               "Shot 1: A hand plants the seed, releases it and withdraws. The crystal plant starts growing.\n"
               "overall_soundscape: N/A\nnon_diegetic_music: N/A")
        old_h3 = apply_direct_i2v_timing(h3, source, motion_aware=True, camera_clean=True)
        new_h3 = apply_direct_i2v_timing(h3, source, motion_aware=True, camera_clean=True, ending_phase_only=True)
        old_ref = apply_direct_ref2v_timing_v4(ref, source)
        new_ref = apply_direct_ref2v_timing_v4(ref, source, ending_phase_only=True)
        for old, new in ((old_h3, new_h3), (old_ref, new_ref)):
            self.assertIn("Throughout the entire shot", old)
            self.assertNotIn("Throughout the entire shot", new)
            self.assertIn("the crystal plant grows upward", new)
            self.assertIn("releases it and withdraws", new)
            self.assertIn("At 00:12.000", new)

    def test_mixing_an_experimental_plan_with_another_brief_is_rejected_in_both_directions(self):
        catalog = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        for family, old, new in PAIRS:
            for profile_version, cookbook_version in ((old, new), (new, old)):
                session = SimpleNamespace(profile_id=family, profile_version=profile_version)
                with self.assertRaisesRegex(ValueError, "matching Brief profile"):
                    _validate_bindings(session, catalog.get(family, cookbook_version), ())
