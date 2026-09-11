"""Combat 1.1 offline fixtures, prepared for user execution. No model or render calls."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.application import combat_sequence as sequence
from panelforge.application.direct_ref2v_prompt import direct_reference_header_for_roles
from panelforge.application.h3_ref2v_conversion import compile_conversion, conversion_document
from panelforge.application.h3_render import canonicalize_h3_revision
from panelforge.application.prompt_lab import PromptLabService, StreamEventKind
from panelforge.domain import CompositionStage, CreativeFreedomAxes
from panelforge.domain.h3_render import H3RenderInputMode, H3RenderRevisionVersion
from panelforge.domain.video_preparation import CombatSettings, VideoPreparationRef
from panelforge.infrastructure.combat_preparation import load_combat_revision_policy
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.storage import LocalH3RenderProjectStore, LocalPromptSessionStore
from tests.test_combat_preparation import BRIEF, INTENT, OPENING, ACTION, END, ROOT
from tests.test_video_preparation_recipes import preparation_service
from tests import test_combat_preparation as combat_fixtures
from tests import test_h3_ref2v_conversion as conversion_fixtures


MODERN = VideoPreparationRef("combat", "1.1.0")


def candidate(count=3, *, planned=False):
    value = {
        "shots": [{"duration_ms": 1000 + index * 250, "camera_motion": "static_shot",
                   "opening_composition": OPENING, "end_state": END,
                   "transition": "Continue the advancing counter through the cut." if index < count - 1 else "The counter remains underway.",
                   ("exchanges" if planned else "description"): [ACTION] if planned else ACTION}
                  for index in range(count)],
        "overall_soundscape": "Blade contacts, steps and shield impacts.", "non_diegetic_music": "N/A",
    }
    if planned:
        value.update(continuity_invariants=["The same two fighters retain their weapons."], spoken_lines=[])
    return value


def writer(count=3):
    return json.dumps({"shots": [ACTION] * count, "overall_soundscape": "Blade contacts and steps.", "non_diegetic_music": "N/A"})


def context(mode="ref2va", count=3, action=1):
    return {"mode": mode, "header": direct_reference_header_for_roles(("subject_reference",)) if mode == "ref2va" else "",
            "duration_ms": 8000, "settings": CombatSettings(action, count).as_dict(),
            "dialogues": [], "dialogue_level": 0, "source_text": INTENT,
            "preparation": MODERN.as_dict()}


def compile_fixture(mode="ref2va", count=3, action=1):
    return sequence.compile_result(json.dumps(candidate(count)), sequence.encode_context(context(mode, count, action)), "final_prompt")


class CombatSequenceContractTest(unittest.TestCase):
    def test_logged_four_shot_answer_preserves_timed_camera_sentences(self):
        # Rejected after a successful model response on 2026-09-10: the reader
        # includes each cut timestamp, whereas Combat originally saved bare cameras.
        value = json.loads((ROOT / "tests/fixtures/combat_1_1_four_shot_response.json").read_text(encoding="utf-8"))
        cameras = [
            "The camera performs a tracking shot.",
            "At 00:02.300, The camera performs an arc shot.",
            "At 00:04.200, The camera performs a tracking shot.",
            "At 00:06.100, The camera pushes in.",
        ]
        for mode in ("ref2va", "fl2va"):
            for planned in (False, True):
                with self.subTest(mode=mode, planned=planned):
                    data = context(mode, 4)
                    content = json.dumps(value)
                    if planned:
                        data["plan"] = {
                            "continuity_invariants": ["Same two fighters and weapons."],
                            "shots": [{**{k: v for k, v in shot.items() if k != "description"}, "exchanges": [shot["description"]]} for shot in value["shots"]],
                            "spoken_lines": [], "overall_soundscape": value["overall_soundscape"],
                            "non_diegetic_music": value["non_diegetic_music"],
                        }
                        content = json.dumps({"shots": [shot["description"] for shot in value["shots"]],
                                              "overall_soundscape": value["overall_soundscape"], "non_diegetic_music": value["non_diegetic_music"]})
                    result, saved = sequence.compile_result(content, sequence.encode_context(data), "final_prompt")
                    restored = sequence.decode_context(saved)
                    self.assertEqual(restored["cameras"], cameras)
                    self.assertEqual(restored["shot_starts_ms"], [0, 2300, 4200, 6100])
                    sequence.validate_final(result, restored)
                    # Keep strict protection: changing or moving a camera is still rejected.
                    changed = result.replace("The camera performs an arc shot.", "The camera pushes in.", 1)
                    with self.assertRaisesRegex(ValueError, "directives"):
                        sequence.validate_final(changed, restored)
                    moved = result.replace("[Shot 2] At 00:02.300,", "[Shot 2] At 00:02.301,", 1)
                    with self.assertRaises(ValueError):
                        sequence.validate_final(moved, restored)

    def test_independent_controls_and_auto(self):
        for action in range(4):
            for count in (1, 3, 6):
                with self.subTest(action=action, count=count):
                    result, saved = compile_fixture(count=count, action=action)
                    data = sequence.decode_context(saved)
                    self.assertEqual(len(data["shot_starts_ms"]), count)
                    self.assertEqual(data["settings"], CombatSettings(action, count).as_dict())
                    self.assertEqual(sequence.prompt_errors(result, "ref2va"), ())
            data = context(count=None, action=action)
            result, saved = sequence.compile_result(json.dumps(candidate(5)), sequence.encode_context(data), "final_prompt")
            self.assertIsNone(sequence.decode_context(saved)["settings"]["shot_count"])
            self.assertEqual(len(sequence.decode_context(saved)["shot_starts_ms"]), 5)

    def test_six_shots_support_every_native_anchor_mode(self):
        for mode in ("t2va", "i2va", "l2va", "fl2va"):
            result, saved = compile_fixture(mode, 6)
            self.assertEqual(sequence.prompt_errors(result, mode), ())
            header = sequence.decode_context(saved)["compiled_header"]
            if mode in {"l2va", "fl2va"}:
                self.assertIn("Shot 6", header)
                self.assertIn("8.00-second", header)
            if mode == "t2va":
                self.assertEqual(header, "")

    def test_duration_weights_are_normalized_once_and_writer_preserves_structure(self):
        data = context(count=6)
        plan = json.loads(sequence.canonical_plan(json.dumps(candidate(6, planned=True)), data))
        self.assertEqual(sum(s["duration_ms"] for s in plan["shots"]), 8000)
        data["plan"] = plan
        result, saved = sequence.compile_result(writer(6), sequence.encode_context(data), "final_prompt")
        self.assertIn("The target video lasts 8 seconds.", result)
        starts = sequence.decode_context(saved)["shot_starts_ms"]
        self.assertEqual(starts, [sum(s["duration_ms"] for s in plan["shots"][:n]) for n in range(6)])
        with self.assertRaisesRegex(ValueError, "tous les plans"):
            sequence.compile_result(writer(5), sequence.encode_context(data), "final_prompt")

    def test_rejects_wrong_counts_and_context_changes(self):
        data = context(count=3)
        with self.assertRaisesRegex(ValueError, "3 plan"):
            sequence.compile_result(json.dumps(candidate(1)), sequence.encode_context(data), "final_prompt")
        result, saved = compile_fixture()
        data = sequence.decode_context(saved)
        for changed in (result.replace("<Picture 1>", "<Picture 2>"), result.replace("lasts 8 seconds", "lasts 10 seconds"),
                        result.replace("[Shot 2]", "[Shot 4]"), result.replace(data["cameras"][0], "", 1)):
            with self.assertRaises(ValueError):
                sequence.validate_final(changed, data)
        with self.assertRaisesRegex(ValueError, "contredit"):
            sequence.check_intention("Caméra mobile, en un seul plan.", CombatSettings(3, 3))
        sequence.check_intention("Invente plusieurs combinaisons.", CombatSettings(3, 1))
        auto = context(count=None)
        auto["source_text"] = "Un duel en trois plans, sur huit secondes."
        with self.assertRaisesRegex(ValueError, "3 plan"):
            sequence.compile_result(json.dumps(candidate(2)), sequence.encode_context(auto), "final_prompt")
        for values in ((True, 1), (4, 2), (1, 7), (1, False)):
            with self.assertRaises(ValueError):
                CombatSettings(*values)

    def test_no_added_speech_without_permission(self):
        value = candidate(1)
        value["shots"][0]["description"] += ' The swordswoman says <d>[English] Watch out!</d>'
        with self.assertRaisesRegex(ValueError, "répliques"):
            sequence.compile_result(json.dumps(value), sequence.encode_context(context(count=1)), "final_prompt")

    def test_conversion_and_render_revision_preserve_six_cuts(self):
        h3, _ = compile_fixture("fl2va", 6)
        document = conversion_document(h3)
        ref = compile_conversion(json.dumps({"shots": document["shots"]}), h3, ("first_frame", "last_frame"), combat_sequence=True)
        self.assertEqual(sequence.prompt_errors(ref, "ref2va"), ())
        self.assertIn("[Shot 6]", ref)
        self.assertEqual(canonicalize_h3_revision(ref, ref, H3RenderInputMode.REF2VA, combat_sequence=True), ref)
        with self.assertRaises(ValueError):
            canonicalize_h3_revision(ref, ref.replace("[Shot 6]", "[Shot 7]"), H3RenderInputMode.REF2VA, combat_sequence=True)


class CombatSequenceIntegrationTest(unittest.TestCase):
    def test_six_recipes_support_sync_and_stream_without_hidden_calls(self):
        for streamed in (False, True):
            for mode in ("fl2va", "ref2v"):
                for route, calls in (("prompt", 1), ("planned", 2), ("guided", 3)):
                    with self.subTest(streamed=streamed, mode=mode, route=route), tempfile.TemporaryDirectory() as directory:
                        responses = ([BRIEF] if calls == 3 else []) + ([json.dumps(candidate())] if calls == 1 else [json.dumps(candidate(planned=True)), writer()])
                        service, gateway, session, _ = preparation_service(directory, mode, route, responses,
                            version="1.1.0", preparation_family="combat", combat_settings=CombatSettings(2, 3), source_text=INTENT,
                            roles=("first_frame", "last_frame") if mode == "fl2va" else ("subject_reference",))
                        if calls == 3:
                            lab = PromptLabService(gateway=gateway, profiles=LocalPromptProfileCatalog(ROOT / "prompt_profiles"), assets=service.assets, sessions=service.sessions)
                            if streamed:
                                list(lab.stream_structure_brief(session.session_id, INTENT, 0, CreativeFreedomAxes(0, 0, 0), creative_audacity=2))
                            else:
                                lab.structure_brief(session.session_id, INTENT, 0, CreativeFreedomAxes(0, 0, 0), creative_audacity=2)
                            lab.approve_brief(session.session_id)
                        stages = ([CompositionStage.BEAT_SHEET] if calls > 1 else []) + [CompositionStage.FINAL_PROMPT]
                        for stage in stages:
                            if streamed:
                                events = list(service.stream_generate(session.session_id, stage))
                                self.assertEqual(events[-1].kind, StreamEventKind.COMPLETED)
                                self.assertFalse(any(sequence.MARKER in event.text for event in events))
                            else:
                                service.generate(session.session_id, stage)
                            service.approve(session.session_id, stage)
                        self.assertEqual(len(gateway.requests), calls)
                        self.assertTrue(all("ACTION QUANTITY: INTENSE" in request.system_prompt for request in gateway.requests))
                        self.assertEqual(len(gateway.requests[0].images), len(session.references))
                        if calls > 1:
                            self.assertEqual(gateway.requests[-1].images, ())
                        reopened = LocalPromptSessionStore(directory).get(session.session_id)
                        self.assertEqual(reopened.combat_settings, CombatSettings(2, 3))
                        renders = combat_fixtures.CombatRenderTest().service(directory)
                        renders.sessions, renders.compositions = service.sessions, service.compositions
                        project = renders.get_or_create_from_session(session.session_id)
                        self.assertEqual(project.combat_settings, reopened.combat_settings)
                        self.assertEqual(project.revision_version, H3RenderRevisionVersion.COMBAT_1_1)
                        self.assertEqual(len(project.planned_cut_times_ms), 2)
                        self.assertEqual(project.attempts, ())
                        self.assertEqual(LocalH3RenderProjectStore(directory).get(project.project_id), project)

    def test_direct_revisions_use_writer_and_preserve_auto_choice(self):
        for streamed in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                service, gateway, session, _ = preparation_service(directory, "ref2v", "prompt", [json.dumps(candidate(6)), writer(6)],
                    version="1.1.0", preparation_family="combat", combat_settings=CombatSettings(3, None), source_text=INTENT)
                first = service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
                if streamed:
                    list(service.stream_revise(session.session_id, CompositionStage.FINAL_PROMPT, "Rends la parade plus lisible."))
                else:
                    service.revise(session.session_id, CompositionStage.FINAL_PROMPT, "Rends la parade plus lisible.")
                current = service.get(session.session_id).final_prompt.active_revision
                previous = sequence.decode_context(first.final_prompt.active_revision.compiler_context)
                self.assertEqual(sequence.decode_context(current.compiler_context)["shot_starts_ms"], previous["shot_starts_ms"])
                self.assertEqual(len(gateway.requests), 2)
                self.assertIn("WRITER OWNERSHIP", gateway.requests[-1].system_prompt)
                self.assertNotIn("ONE-CALL OWNERSHIP", gateway.requests[-1].system_prompt)
                self.assertEqual(gateway.requests[-1].images, ())

    def test_fork_keeps_settings_and_legacy_target_drops_them(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, session, _ = preparation_service(directory, "fl2va", "prompt", [], version="1.1.0",
                preparation_family="combat", combat_settings=CombatSettings(3, 6))
            lab = PromptLabService(gateway=gateway, profiles=LocalPromptProfileCatalog(ROOT / "prompt_profiles"), assets=service.assets, sessions=service.sessions)
            same = lab.fork_session(session.session_id)
            self.assertEqual(same.combat_settings, CombatSettings(3, 6))
            legacy = lab.fork_session(session.session_id, profile_id=session.profile_id, profile_version="1.0.0")
            self.assertEqual(legacy.preparation, VideoPreparationRef("combat", "1.0.0"))
            self.assertIsNone(legacy.combat_settings)
            self.assertEqual(gateway.requests, [])

    def test_exact_post_render_policy_and_legacy_assets_are_preserved(self):
        modern = load_combat_revision_policy(ROOT / "prompt_cookbooks/_blocks", "1.1.0")
        old = load_combat_revision_policy(ROOT / "prompt_cookbooks/_blocks", "1.0.0")
        self.assertIn("POST-RENDER REVISION 1.1.0", modern.system_prompt)
        self.assertIn("POST-RENDER REVISION 1.0.0", old.system_prompt)
        catalog = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        recipes = [recipe for recipe in catalog.list() if recipe.preparation == MODERN]
        self.assertEqual(len(recipes), 6)
        baseline = json.loads((ROOT / "tests/fixtures/pre_combat_1_1_assets.json").read_text(encoding="utf-8"))
        for path, expected in baseline.items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected, path)

    def test_post_render_and_conversion_keep_modern_settings_without_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            service, source, setup, _ = conversion_fixtures.H3Ref2VConversionTest().service(directory)
            prompt, _ = compile_fixture("fl2va", 6, 3)
            source = replace(source, preparation=MODERN, combat_settings=CombatSettings(3, 6),
                             revision_version=H3RenderRevisionVersion.COMBAT_1_1, current_prompt=prompt)
            service.renders.projects.save(source)
            renders = combat_fixtures.CombatRenderTest().service(directory)
            modern = load_combat_revision_policy(ROOT / "prompt_cookbooks/_blocks", "1.1.0")
            renders.combat_revision_policies[MODERN] = modern
            request = renders._completion_request(source, "Clarifie le contact du bouclier.", include_reasoning=False, creative_audacity=2)
            self.assertIn("ACTION QUANTITY: UNLEASHED", request.system_prompt)
            self.assertIn("POST-RENDER REVISION 1.1.0", request.system_prompt)
            with self.assertRaises(ValueError):
                source.select_revision_version(H3RenderRevisionVersion.COMBAT)
            target = service.prepare(source.project_id, request_id="modern-conversion", prompt=prompt, model_id="fixture", setup=setup)
            target = list(service.stream(target.project_id))[-1].project
            self.assertEqual(target.adaptation.status, "ready")
            self.assertEqual(target.preparation, MODERN)
            self.assertEqual(target.combat_settings, CombatSettings(3, 6))
            self.assertEqual(target.revision_version, H3RenderRevisionVersion.COMBAT_1_1)
            self.assertEqual(target.reference_asset_ids, (source.first_frame_asset_id, source.last_frame_asset_id))
            self.assertEqual(target.adaptation.render_setup, setup)
            self.assertEqual(len(service.renders.gateway.requests), 1)
            self.assertEqual(len(target.planned_cut_times_ms), 5)
            self.assertEqual(target.attempts, ())

    def test_schema_ten_session_and_seven_render_keep_combat_one(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _, session, _ = preparation_service(directory, "fl2va", "prompt", [json.dumps({
                "camera_motion": "static_shot", "integrated_multimodal_description": ACTION,
                "overall_soundscape": "N/A", "non_diegetic_music": "N/A"})], preparation_family="combat", source_text=INTENT)
            service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            path = Path(directory) / "prompt_sessions" / session.session_id / "session.json"
            raw = json.loads(path.read_text(encoding="utf-8")); raw["schema_version"] = 10; raw.pop("combat_settings"); raw.pop("cinematic_settings"); raw.pop("sensual_settings")
            path.write_text(json.dumps(raw), encoding="utf-8")
            self.assertEqual(service.sessions.get(session.session_id), session)
            renders = combat_fixtures.CombatRenderTest().service(directory)
            renders.sessions, renders.compositions = service.sessions, service.compositions
            project = renders.get_or_create_from_session(session.session_id)
            path = next((Path(directory) / "h3_render_projects").rglob("project.json"))
            raw = json.loads(path.read_text(encoding="utf-8")); raw["schema_version"] = 7; raw.pop("combat_settings"); raw.pop("cinematic_settings")
            path.write_text(json.dumps(raw), encoding="utf-8")
            reopened = renders.projects.get(project.project_id)
            self.assertEqual(reopened, project)
            self.assertIsNone(reopened.combat_settings)
