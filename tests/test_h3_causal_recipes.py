"""Offline regressions for H3 1.1.0; executed only by the user."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.application.h3_phase_plan import (
    canonical_h3_phase_plan, lint_h3_phase_plan, h3_phase_plan_warnings,
)
from panelforge.application.prompt_composition import (
    lint_cookbook_document, composition_document_warnings,
)
from panelforge.application.direct_ref2v_plan import canonical_direct_ref2v_action_plan_v4_late_anchor
from panelforge.domain import BriefRevision, BriefReferenceSnapshot, RevisionOrigin, CompositionStage
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.storage import LocalPromptCompositionStore
from tests.test_video_preparation_recipes import preparation_service, DIRECT_BODY


ROOT = Path(__file__).resolve().parents[1]
BASE = "minimax.h3.fl2va.direct"


def wall_plan():
    """Same failed wording/timing as the audited run; no dependency on live logs."""
    phases = [
        ("excavate", 0, 2500, "The worker removes blocks to open the solid wall.", "A rough cavity and fallen blocks are visible."),
        ("clear", 2500, 4000, "He clears loose rubble from the cavity.", "The opening is clear, with some rubble at its base."),
        ("keystone", 4000, 6200, "One decisive staccato thrust seats the keystone, sealing the vault and revealing the dark niche that matches the final frame; a fine dust puff settles on the path.", "Niche complete; worker still in frame at the wall."),
        ("exit", 6200, 7000, "He exits through the bottom edge while fast-forward clouds keep drifting.", "No worker is visible; the completed niche stays stable while clouds drift."),
    ]
    return {
        "scene_setup": "A mountain path beside a solid stone wall.",
        "continuity_invariants": ["Preserve the existing paving, mountain and stone materials."],
        "beats": [{"beat_id": name, "start_ms": start, "end_ms": end,
                   "primary_action": name, "participants": ["worker"], "observable_end_state": result,
                   "steps": [{"step_id": name + "_s1", "start_ms": start, "end_ms": end,
                              "action": action, "continuity_after": result}]}
                  for name, start, end, action, result in phases],
        "final_state": {"description": "The niche matches the last frame while clouds drift across the sky.", "final_hold_ms": 0},
        "camera_directives": [], "risks": [], "technical_adjustments": [],
        "overall_soundscape": "N/A", "non_diegetic_music": "N/A", "dialogue_cues": [],
        "motion_contract": {"primary_motion": "Clouds drift across the sky over the completed niche", "end_behavior": "continue_motion"},
    }


WRITER = (
    "integrated_multimodal_description: [Shot 1] The target video is one continuous 7-second shot. "
    "An empty mountain path runs beside a solid stone wall. The worker enters and removes blocks "
    "to open a rough cavity, then clears the loose rubble. He finishes the inner masonry and arch, "
    "leaving some rubble at its base, then exits while clouds continue drifting.\n"
    "overall_soundscape: N/A\nnon_diegetic_music: N/A"
)


class H3PhaseValidationTest(unittest.TestCase):
    def test_audited_local_completion_passes_without_rewriting_the_plan(self):
        plan = wall_plan()
        content = json.dumps(plan)
        with self.assertRaisesRegex(ValueError, "6200 ms"):
            canonical_direct_ref2v_action_plan_v4_late_anchor(content)
        result = json.loads(canonical_h3_phase_plan(content))
        self.assertEqual(result["beats"], plan["beats"])
        self.assertEqual(result["motion_contract"], plan["motion_contract"])
        self.assertEqual(lint_h3_phase_plan(content), ())
        self.assertTrue(any("keystone_s1" in warning for warning in h3_phase_plan_warnings(content)))

    def test_equivalent_local_result_and_stopped_worker_do_not_stop_clouds(self):
        for action in (
            "The finished niche is identical in form to the last frame.",
            "The worker holds the final pose until the cut while clouds keep drifting.",
            "The worker stops moving; the niche matches the final frame while clouds drift.",
        ):
            with self.subTest(action=action):
                plan = wall_plan()
                plan["beats"][-1]["steps"][0]["action"] = action
                self.assertEqual(lint_h3_phase_plan(json.dumps(plan)), ())

    def test_explicit_stop_of_all_motion_or_remaining_actor_is_rejected(self):
        for action in (
            "The entire scene freezes until the cut.",
            "All visible motion stops at the cut.",
            "The clouds stop moving and stay still until the cut.",
        ):
            with self.subTest(action=action):
                plan = wall_plan()
                plan["beats"][-1]["steps"][0]["action"] = action
                with self.assertRaisesRegex(ValueError, "explicit stop"):
                    canonical_h3_phase_plan(json.dumps(plan))

    def test_earlier_stop_and_negated_stop_are_not_terminal_stops(self):
        for index, action in (
            (0, "The clouds stop moving briefly."),
            (-1, "The clouds do not stop moving; the entire scene never freezes."),
            (-1, "The clouds drift without stopping in the final frame."),
        ):
            plan = wall_plan()
            plan["beats"][index]["steps"][0]["action"] = action
            self.assertEqual(lint_h3_phase_plan(json.dumps(plan)), ())

    def test_sentence_with_continuing_motion_cannot_hide_explicit_terminal_stop(self):
        plan = wall_plan()
        plan["beats"][-1]["steps"][0]["action"] = (
            "Clouds pass through the final frame in motion. The entire scene freezes until the cut."
        )
        self.assertTrue(lint_h3_phase_plan(json.dumps(plan)))

    def test_qualified_global_stillness_or_temporary_stop_is_advisory(self):
        for action in (
            "The whole scene remains still except for rapidly drifting clouds.",
            "The clouds stop moving briefly, then resume drifting before the cut.",
        ):
            plan = wall_plan()
            plan["beats"][-1]["steps"][0]["action"] = action
            content = json.dumps(plan)
            self.assertEqual(lint_h3_phase_plan(content), ())
            self.assertTrue(any("qualifié" in w for w in h3_phase_plan_warnings(content)))

    def test_explicit_settle_and_hold_keep_their_requested_timing(self):
        for behavior in ("natural_settle", "intentional_hold"):
            plan = wall_plan()
            plan["motion_contract"]["end_behavior"] = behavior
            plan["final_state"]["final_hold_ms"] = 500
            plan["final_state"]["description"] = "The entire scene remains still."
            result = json.loads(canonical_h3_phase_plan(json.dumps(plan)))
            self.assertEqual(result["final_state"]["final_hold_ms"], 500)
            self.assertFalse(lint_h3_phase_plan(json.dumps(result)))

    def test_structural_timeline_validation_is_preserved(self):
        plan = wall_plan()
        plan["beats"][1]["steps"][0]["start_ms"] += 1
        with self.assertRaisesRegex(ValueError, "contiguous"):
            canonical_h3_phase_plan(json.dumps(plan))


class H3CausalRecipesTest(unittest.TestCase):
    def test_versioned_decisions_and_shared_writer(self):
        catalog = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        guided, planned, direct = [catalog.get(BASE + "." + r, "1.1.0") for r in ("guided", "planned", "prompt")]
        self.assertEqual((guided.preparation_steps, planned.preparation_steps, direct.preparation_steps), (3, 2, 1))
        self.assertEqual(guided.final_prompt_system_prompt, planned.final_prompt_system_prompt)
        self.assertEqual(guided.final_prompt_user_prompt, planned.final_prompt_user_prompt)
        self.assertIn("PRESERVE THE PLANNED TRANSFORMATION", guided.final_prompt_system_prompt)
        for recipe in (guided, planned, direct):
            self.assertEqual(recipe.profile_version, "0.5.0")
            decisions = recipe.beat_sheet_system_prompt or recipe.final_prompt_system_prompt
            self.assertIn("CAUSAL TRANSFORMATIONS", decisions)
            self.assertIn("PHASES AND ENDING", decisions)
            self.assertIn("CAUSAL TRANSFORMATIONS", recipe.revision_system_prompt)
        self.assertNotIn("CAUSAL TRANSFORMATIONS", catalog.get(BASE + ".prompt", "1.0.0").final_prompt_system_prompt)
        profiles = LocalPromptProfileCatalog(ROOT / "prompt_profiles")
        profile = profiles.get(BASE, "0.5.0")
        self.assertIn("Transformations causales", profile.brief_system_prompt)
        self.assertIn("Transformations causales", profile.brief_revision_system_prompt)
        creative = next(v for v in profile.brief_variants if v.version == "0.3.0")
        self.assertIn("Transformations causales", creative.brief_system_prompt)
        self.assertIn("Transformations causales", creative.brief_revision_system_prompt)

    def test_validation_is_bound_to_recipe_version(self):
        catalog = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        content = json.dumps(wall_plan())
        for route in ("guided", "planned"):
            old, new = [catalog.get(BASE + "." + route, v) for v in ("1.0.0", "1.1.0")]
            self.assertTrue(lint_cookbook_document(old, CompositionStage.BEAT_SHEET, content))
            self.assertFalse(lint_cookbook_document(new, CompositionStage.BEAT_SHEET, content))
            self.assertTrue(composition_document_warnings(new, CompositionStage.BEAT_SHEET, content))

    def test_each_route_uses_only_its_own_stages_and_persists_its_version(self):
        for route in ("guided", "planned", "prompt"):
            with self.subTest(route=route), tempfile.TemporaryDirectory() as directory:
                responses = [DIRECT_BODY] if route == "prompt" else [json.dumps(wall_plan()), WRITER]
                service, gateway, session, _ = preparation_service(
                    directory, "fl2va", route, responses, version="1.1.0",
                    roles=("first_frame", "last_frame"), source_text="Open and finish the wall in 7 seconds.",
                )
                if route == "guided":
                    brief = BriefRevision(
                        "brief-fixture", "Open and finish the wall in 7 seconds.",
                        "In 7 seconds: open the wall, clear rubble, finish its lining, exit while clouds drift.",
                        35, RevisionOrigin.MODEL,
                        tuple(BriefReferenceSnapshot(r.reference_id, None, r.uses) for r in session.references),
                    )
                    service.sessions.save(session.add_brief_revision(brief).approve_brief())
                else:
                    self.assertFalse(service.sessions.get(session.session_id).brief_revisions)
                if route != "prompt":
                    service.generate(session.session_id, CompositionStage.BEAT_SHEET)
                    service.approve(session.session_id, CompositionStage.BEAT_SHEET)
                service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
                service.approve(session.session_id, CompositionStage.FINAL_PROMPT)
                self.assertEqual(len(gateway.requests), 1 if route == "prompt" else 2)
                self.assertEqual(len(gateway.requests[0].images), 2)
                self.assertTrue(all("@1.1.0." in r.operation_id for r in gateway.requests))
                if route != "prompt":
                    self.assertEqual(gateway.requests[-1].images, ())
                    self.assertIn("removes blocks", gateway.requests[-1].user_prompt)
                    self.assertIn("clears loose rubble", gateway.requests[-1].user_prompt)
                reopened = LocalPromptCompositionStore(directory).get(session.session_id)
                self.assertEqual(reopened.cookbook.version, "1.1.0")
                self.assertTrue(reopened.final_prompt.approved_revision_id)
                self.assertEqual(bool(reopened.beat_sheet.revisions), route != "prompt")

    def test_prior_recipe_manifests_are_unchanged(self):
        expected = {
            "guided": "3769185e618f7be1ca2f2a1e10789b464ce8bc11b49f0376aea1f2d5bd573201",
            "planned": "384c4a4a52adb7d5e125030c0aadbbc06173aff8b7d453973a32f59303e524b7",
            "prompt": "05259a87081eb581874ea542c46fda2e46868f8470af691d87a3367b445e6ceb",
        }
        for route, digest in expected.items():
            path = ROOT / f"prompt_cookbooks/{BASE}.{route}/1.0.0/manifest.json"
            self.assertEqual(hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest(), digest)
