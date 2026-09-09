"""Offline fixtures only. The user runs these tests; no external model/render."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.application import StreamEventKind
from panelforge.application.direct_fl2va_multishot_plan import parse_direct_fl2va_multishot_plan
from panelforge.application.direct_fl2va_multishot_prompt import (
    compile_direct_fl2va_multishot_document, decode_direct_fl2va_multishot_context,
    encode_direct_fl2va_multishot_context, rehydrate_direct_fl2va_multishot_document,
)
from panelforge.application.h3_multishot_preparation import (
    align_state_multishot_duration, compile_compact_multishot,
    multishot_state_warnings, validate_compact_multishot,
)
from panelforge.domain import BriefReferenceSnapshot, BriefRevision, CompositionStage, RevisionOrigin
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.storage import LocalPromptCompositionStore
from tests.test_h3_base_multishot import multishot_plan
from tests.test_video_preparation_recipes import preparation_service


ROOT = Path(__file__).resolve().parents[1]
BASE = "minimax.h3.fl2va.direct.multishot"
INTENTION = "In 8 seconds, she pours pink gel, then spreads it across the floor with a diamond squeegee. Keep the same framing."
FINAL = "A continuous glossy pink layer covers the floor while her hands keep moving"
OPENING = "The same woman in a pink dress stands in the same room, seen from the same fixed frontal framing"
COMPACT = {
    "shots": [
        {"duration_ms": 4000, "opening_composition": OPENING,
         "camera_motion": "static_shot", "description": "She pours pink gel from a bucket, forming a broad pool."},
        {"duration_ms": 4000, "opening_composition": OPENING + "; moments later she holds a diamond squeegee over the existing pool",
         "camera_motion": "static_shot", "description": "She spreads the existing pool into a continuous layer across the floor."},
    ],
    "final_state": FINAL, "dialogue_cues": [],
    "overall_soundscape": "Thick gel pouring and the soft scrape of the squeegee.",
    "non_diegetic_music": "N/A",
}
WRITER = "\n\n".join([
    *(f"shot_{i}:\n{shot['description']}" for i, shot in enumerate(COMPACT["shots"], 1)),
    f"overall_soundscape:\n{COMPACT['overall_soundscape']}", "non_diegetic_music:\nN/A",
])


def state_plan():
    value = multishot_plan()
    value.update(scene_setup="A woman in a pink dress transforms a floor with pink gel.",
                 continuity_invariants=["Same woman, dress, room, light and framing."],
                 dialogue_cues=[], overall_soundscape=COMPACT["overall_soundscape"])
    value["final_state"] = {"description": FINAL, "final_hold_ms": 0}
    for index, shot in enumerate(value["shots"]):
        shot.update(duration_ms=4000, opening_composition=OPENING,
                    purpose="Pour gel" if index == 0 else "Spread gel",
                    new_information="A broad pool forms" if index == 0 else "The existing pool becomes an even layer",
                    continuity_from_previous=None if index == 0 else "Same framing and existing gel pool; an incidental tool change occurs between shots.",
                    actions=[COMPACT["shots"][index]["description"]],
                    observable_end_state="A pool of pink gel lies on the floor" if index == 0 else FINAL,
                    camera={"motion": "static_shot", "amplitude": None, "speed": None,
                            "target_clause": None, "visible_change": "The framing stays fixed."})
    return value


def fixture(directory, route, responses, roles=("first_frame",), source=INTENTION):
    result = preparation_service(directory, "fl2va", route, responses, roles=roles,
                                 source_text=source, multishot=True)
    service, _, session, _ = result
    if route == "guided":
        brief = BriefRevision("brief-fixture", source, INTENTION, 35, RevisionOrigin.MODEL,
                              tuple(BriefReferenceSnapshot(r.reference_id, None, r.uses) for r in session.references))
        service.sessions.save(session.add_brief_revision(brief).approve_brief())
    return result


class H3MultiShotPreparationTest(unittest.TestCase):
    def test_three_pinned_routes_share_writer_and_have_stage_specific_decisions(self):
        catalog = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        guided, planned, direct = [catalog.get(BASE + "." + route, "1.0.0") for route in ("guided", "planned", "prompt")]
        self.assertEqual((guided.preparation_steps, planned.preparation_steps, direct.preparation_steps), (3, 2, 1))
        self.assertEqual(guided.final_prompt_system_prompt, planned.final_prompt_system_prompt)
        self.assertEqual(guided.final_prompt_user_prompt, planned.final_prompt_user_prompt)
        self.assertIn("approved Brief already owns", guided.beat_sheet_system_prompt)
        self.assertIn("no generated Brief", planned.beat_sheet_system_prompt)
        self.assertIn("No separate Brief or detailed Plan exists", direct.final_prompt_system_prompt)
        for recipe in (guided, planned, direct):
            self.assertEqual((recipe.profile_id, recipe.profile_version), (BASE, "0.2.0"))
            self.assertIn("same camera position", recipe.revision_system_prompt)
            self.assertTrue(all(slot.minimum_references == 0 for slot in recipe.slots))
        profile = LocalPromptProfileCatalog(ROOT / "prompt_profiles").get(BASE, "0.2.0")
        self.assertIn("First seule", profile.brief_system_prompt)
        self.assertTrue(any(v.version == "0.3.0" for v in profile.brief_variants))

    def test_all_three_routes_with_first_last_both_or_no_frame(self):
        for route in ("guided", "planned", "prompt"):
            for roles, mode in [((), "t2va"), (("first_frame",), "i2va"),
                                (("last_frame",), "l2va"), (("first_frame", "last_frame"), "fl2va")]:
                with self.subTest(route=route, mode=mode), tempfile.TemporaryDirectory() as directory:
                    responses = [json.dumps(COMPACT)] if route == "prompt" else [json.dumps(state_plan()), WRITER]
                    service, gateway, session, _ = fixture(directory, route, responses, roles)
                    if route != "prompt":
                        service.generate(session.session_id, CompositionStage.BEAT_SHEET)
                        service.approve(session.session_id, CompositionStage.BEAT_SHEET)
                    service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
                    service.approve(session.session_id, CompositionStage.FINAL_PROMPT)
                    saved = LocalPromptCompositionStore(directory).get(session.session_id)
                    final = saved.final_prompt.active_revision
                    context = decode_direct_fl2va_multishot_context(final.compiler_context)
                    self.assertEqual(context.mode.value, mode)
                    self.assertEqual((context.shot_count, context.duration_ms, context.cut_policy), (2, 8000, "neutral"))
                    self.assertIn("[Shot 2] At 00:04.000, the camera cuts.", final.content)
                    self.assertNotIn("cuts to a new view", final.content)
                    self.assertIn("continuous layer", final.content)
                    self.assertEqual(len(gateway.requests), 1 if route == "prompt" else 2)
                    self.assertEqual(len(gateway.requests[0].images), len(roles))
                    if route != "prompt":
                        self.assertEqual(gateway.requests[1].images, ())
                    self.assertTrue(all("{{" not in request.user_prompt for request in gateway.requests))
                    self.assertEqual(bool(saved.beat_sheet.revisions), route != "prompt")
                    self.assertEqual(saved.cookbook.cookbook_id, BASE + "." + route)
                    if "last_frame" in roles:
                        self.assertIn("from Shot 2" if mode == "fl2va" else "from [Shot 2]", context.header)

    def test_revisions_and_manual_edits_keep_the_saved_compiler_context(self):
        for route in ("planned", "prompt"):
            with self.subTest(route=route), tempfile.TemporaryDirectory() as directory:
                updated = WRITER.replace("soft scrape", "gentle scraping")
                responses = ([json.dumps(COMPACT)] if route == "prompt" else [json.dumps(state_plan()), WRITER]) + [updated]
                service, gateway, session, _ = fixture(directory, route, responses)
                if route != "prompt":
                    service.generate(session.session_id, CompositionStage.BEAT_SHEET)
                    service.approve(session.session_id, CompositionStage.BEAT_SHEET)
                initial = service.generate(session.session_id, CompositionStage.FINAL_PROMPT).final_prompt.active_revision
                revised = service.revise(session.session_id, CompositionStage.FINAL_PROMPT, "Make the scraping sound gentler.").final_prompt.active_revision
                self.assertEqual(initial.compiler_context, revised.compiler_context)
                self.assertIn("gentle scraping", revised.content)
                if route == "prompt":
                    self.assertNotIn("COMPACT APPROVED PLAN", gateway.requests[-1].user_prompt)
                with self.assertRaises(ValueError):
                    service.edit(session.session_id, CompositionStage.FINAL_PROMPT, revised.content.replace("00:04.000", "00:05.000"))
                self.assertEqual(service.get(session.session_id).final_prompt.active_revision, revised)

    def test_streamed_direct_generation_has_no_plan_and_failed_retry_keeps_previous_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _, session, _ = fixture(directory, "prompt", [json.dumps(COMPACT), '{"shots": []}'])
            events = list(service.stream_generate(session.session_id, CompositionStage.FINAL_PROMPT))
            self.assertEqual(events[-1].kind, StreamEventKind.COMPLETED)
            saved = service.get(session.session_id)
            self.assertFalse(saved.beat_sheet.revisions)
            with self.assertRaises(ValueError):
                list(service.stream_generate(session.session_id, CompositionStage.FINAL_PROMPT))
            self.assertEqual(service.get(session.session_id), saved)

    def test_direct_regeneration_can_change_shot_count_without_inheriting_previous_context(self):
        value = deepcopy(COMPACT)
        value["shots"].append(dict(value["shots"][-1], description="She deposits diamonds across the pink layer."))
        with tempfile.TemporaryDirectory() as directory:
            service, _, session, _ = fixture(directory, "prompt", [json.dumps(COMPACT), json.dumps(value)])
            first = service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            second = service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            self.assertEqual(decode_direct_fl2va_multishot_context(first.final_prompt.active_revision.compiler_context).shot_count, 2)
            self.assertEqual(decode_direct_fl2va_multishot_context(second.final_prompt.active_revision.compiler_context).shot_count, 3)

    def test_duration_alignment_does_not_invent_a_hold_or_warn_about_same_framing(self):
        for duration in (6000, 10000):
            content = align_state_multishot_duration(json.dumps(state_plan()), duration)
            plan = parse_direct_fl2va_multishot_plan(content)
            self.assertEqual(plan.duration_ms, duration)
            self.assertEqual(plan.final_state.final_hold_ms, 0)
            self.assertFalse(any("tenue" in warning or "meme composition" in warning for warning in multishot_state_warnings(content)))
        value = state_plan()
        value["final_state"]["final_hold_ms"] = 2000
        aligned = parse_direct_fl2va_multishot_plan(align_state_multishot_duration(json.dumps(value), 5000))
        self.assertEqual(aligned.final_state.final_hold_ms, 1000)

    def test_compiler_context_versions_round_trip_and_legacy_cut_is_unchanged(self):
        source = json.dumps({"mode": "i2va", "duration_ms": 8000, "dialogues": []})
        content, encoded = compile_compact_multishot(json.dumps(COMPACT), source)
        context = decode_direct_fl2va_multishot_context(encoded)
        editable = rehydrate_direct_fl2va_multishot_document(content, encoded)
        self.assertEqual(compile_direct_fl2va_multishot_document(editable, encoded), content)
        old = replace(context, cut_policy="new_view")
        legacy = encode_direct_fl2va_multishot_context(old)
        self.assertNotIn('"cut_policy"', legacy)
        self.assertEqual(decode_direct_fl2va_multishot_context(legacy), old)
        self.assertIn("cuts to a new view", compile_direct_fl2va_multishot_document(editable, old))
        with self.assertRaises(ValueError):
            validate_compact_multishot(content.replace("<Picture 1>", "<Picture 2>"), encoded, source)

    def test_direct_dialogue_is_exact_and_extra_speech_is_rejected(self):
        value = deepcopy(COMPACT)
        value["dialogue_cues"] = [{"cue_id": "dialogue_1", "speaker_id": "S1", "speaker": "the woman",
                                    "start_ms": 5000, "language": "French", "delivery": "softly", "text": "Bonjour."}]
        source = json.dumps({"mode": "i2va", "duration_ms": 8000, "dialogues": ["Bonjour."]})
        content, encoded = compile_compact_multishot(json.dumps(value), source)
        self.assertIn("<d>[French] Bonjour.</d>", content)
        with self.assertRaises(ValueError):
            validate_compact_multishot(content.replace("Bonjour.", "Bonsoir."), encoded, source)
        value["shots"][0]["description"] += " She says: <d>[French] Extra.</d>"
        with self.assertRaises(ValueError):
            compile_compact_multishot(json.dumps(value), source)

    def test_compact_schema_rejects_invalid_camera_count_or_empty_duration(self):
        source = json.dumps({"mode": "t2va", "duration_ms": 8000, "dialogues": []})
        for mutation in (lambda v: v["shots"].pop(),
                         lambda v: v["shots"][0].update(duration_ms=0),
                         lambda v: v["shots"][0].update(camera_motion="invented")):
            value = deepcopy(COMPACT)
            mutation(value)
            with self.assertRaises(ValueError):
                compile_compact_multishot(json.dumps(value), source)
