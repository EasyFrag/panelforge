"""User-run regressions for Combat 1.3. Scripted gateways, no real LLM/render."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.application import PromptLabService, StreamEventKind
from panelforge.application import combat_sequence as sequence
from panelforge.application.combat_cinematic import Camera, Plan, camera_layout
from panelforge.application.combat_cinematic_examples import example
from panelforge.application.combat_cinematic_policy import action_policy, demonstration, example_key
from panelforge.application.h3_render import canonicalize_h3_revision, protect_h3_revision_camera, _revision_camera_clauses
from panelforge.application.h3_ref2v_conversion import compile_conversion, conversion_document
from panelforge.domain import CompositionStage
from panelforge.domain.h3_render import H3RenderInputMode, H3RenderRevisionVersion
from panelforge.domain.video_preparation import CombatSettings, VideoPreparationRef, validate_combat_settings
from panelforge.infrastructure.combat_preparation import load_combat_revision_policy
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.storage import LocalH3RenderProjectStore, LocalPromptSessionStore
from tests.test_combat_identity import identity_context
from tests.test_combat_preparation import ROOT, CombatRenderTest
from tests.test_video_preparation_recipes import preparation_service
from tests.test_h3_ref2v_conversion import H3Ref2VConversionTest


PREPARATION = VideoPreparationRef("combat", "1.3.0")


def fixture(mode="ref2va", count=2, key="powers", unleashed=True):
    sample = example(key, unleashed=unleashed)
    plan, writer = sample["plan"], sample["writer"]
    plan["shots"] = [deepcopy(plan["shots"][i % 2]) for i in range(count)]
    writer["shots"] = [deepcopy(writer["shots"][i % 2]) for i in range(count)]
    context = identity_context(count, mode=mode)
    context.update(preparation=PREPARATION.as_dict(), settings=CombatSettings(3, count, "magic").as_dict(),
        source_text="A fantasy encounter lasting 8 seconds.", duration_ms=8000)
    return plan, writer, context


def compiled(mode="ref2va", count=2):
    plan, writer, context = fixture(mode, count)
    context["plan"] = json.loads(sequence.canonical_plan(json.dumps(plan), context))
    prompt, encoded = sequence.compile_result(json.dumps(writer), sequence.encode_context(context), "final_prompt")
    return prompt, sequence.decode_context(encoded)


class CinematicContractTest(unittest.TestCase):
    def test_all_examples_compile_in_both_intensities_and_all_input_modes(self):
        for key in ("powers", "heavy_weapons", "fast_weapons", "aerial_fantasy", "hand_to_hand"):
            for unleashed in (False, True):
                for mode in ("ref2va", "t2va", "i2va", "l2va", "fl2va"):
                    with self.subTest(key=key, unleashed=unleashed, mode=mode):
                        plan, writer, context = fixture(mode, key=key, unleashed=unleashed)
                        context["plan"] = json.loads(sequence.canonical_plan(json.dumps(plan), context))
                        prompt, encoded = sequence.compile_result(json.dumps(writer), sequence.encode_context(context), "final_prompt")
                        saved = sequence.decode_context(encoded)
                        self.assertEqual(sequence.prompt_errors(prompt, mode, "1.3.0"), ())
                        self.assertEqual(tuple(map(len, camera_layout(prompt))), (2, 2) if unleashed else (1, 1))
                        self.assertEqual(saved["shot_starts_ms"], [0, 4000])
                        for shot in plan["shots"]:
                            for field in ("opening_composition", "pacing", "end_state", "transition"):
                                self.assertIn(shot[field], prompt)
                            for phase in shot["phases"]:
                                self.assertIn(phase["cue"], prompt)
                                self.assertIn(phase["camera"]["target_clause"], prompt)
                        self.assertEqual(saved["sequence_plan"]["shots"][0]["phases"][0]["exchanges"], writer["shots"][0]["phases"][:1])
                        sequence.validate_final(prompt, saved)

    def test_up_to_six_shots_and_twelve_camera_phases_without_extra_cuts(self):
        for count in (1, 2, 6):
            prompt, context = compiled(count=count)
            self.assertEqual(len(context["cameras"]), count * 2)
            self.assertEqual(len(context["shot_starts_ms"]), count)
            self.assertEqual(len(camera_layout(prompt)), count)
            self.assertEqual(sequence.prompt_errors(prompt, "ref2va", "1.3.0"), ())
            self.assertTrue(sequence.prompt_errors(prompt, "ref2va", "1.2.0"))
            self.assertIn("at fast speed", prompt)
            self.assertIn("with large amplitude", prompt)

    def test_static_camera_is_compatible_with_unleashed_action(self):
        plan, writer, context = fixture()
        for shot in plan["shots"]:
            shot["phases"] = shot["phases"][:1]
            shot["phases"][0]["camera"] = {"motion": "static_shot", "amplitude": None, "speed": None, "target_clause": ""}
        for shot in writer["shots"]:
            shot["phases"] = shot["phases"][:1]
        context["plan"] = json.loads(sequence.canonical_plan(json.dumps(plan), context))
        prompt, _ = sequence.compile_result(json.dumps(writer), sequence.encode_context(context), "final_prompt")
        self.assertEqual(prompt.count("The camera holds a static shot."), 2)
        self.assertIn("branching volley", prompt)

    def test_invalid_camera_targets_phase_counts_cuts_and_writer_loss_fail_locally(self):
        bad = {"motion": "shake.slightly", "amplitude": None, "speed": None, "target_clause": "beside the blade"}
        with self.assertRaisesRegex(ValueError, "does not accept a target"):
            Camera.model_validate(bad)
        for motion in ("static_shot", "shake.slightly", "pov"):
            with self.assertRaises(ValueError):
                Camera.model_validate({**bad, "motion": motion, "target_clause": "", "speed": "fast"})
        plan, writer, context = fixture()
        too_many = deepcopy(plan)
        too_many["shots"][0]["phases"].append(deepcopy(too_many["shots"][0]["phases"][0]))
        with self.assertRaises(ValueError):
            sequence.canonical_plan(json.dumps(too_many), context)
        bad_cut = deepcopy(plan)
        bad_cut["shots"][0]["phases"][1]["cue"] = "Cut to a close-up of the blade."
        with self.assertRaises(ValueError):
            sequence.canonical_plan(json.dumps(bad_cut), context)
        bad_prose = deepcopy(plan)
        bad_prose["shots"][0]["phases"][0]["exchanges"] = ["The camera follows the creature."]
        with self.assertRaisesRegex(ValueError, "camera movement"):
            sequence.canonical_plan(json.dumps(bad_prose), context)
        context["plan"] = json.loads(sequence.canonical_plan(json.dumps(plan), context))
        writer["shots"][0]["phases"].pop()
        with self.assertRaises(ValueError):
            sequence.compile_result(json.dumps(writer), sequence.encode_context(context), "final_prompt")
        context.pop("plan")
        with self.assertRaisesRegex(ValueError, "Plan"):
            sequence.compile_result(json.dumps(writer), sequence.encode_context(context), "final_prompt")

    def test_compiled_direction_fields_and_per_shot_layout_are_protected(self):
        prompt, context = compiled()
        removed = prompt.replace(context["plan"]["shots"][0]["pacing"], "", 1)
        with self.assertRaises(ValueError):
            sequence.validate_final(removed, context)
        removed = prompt.replace(context["plan"]["shots"][0]["transition"], "", 1)
        with self.assertRaises(ValueError):
            sequence.validate_final(removed, context)
        clause = context["cameras"][1]
        moved = prompt.replace(clause, "", 1).replace(context["cameras"][2], context["cameras"][2] + " " + clause)
        with self.assertRaises(ValueError):
            canonicalize_h3_revision(prompt, moved, H3RenderInputMode.REF2VA, combat_sequence=True, combat_version="1.3.0")

    def test_magic_and_demonstrations_are_isolated_from_old_versions(self):
        magic = CombatSettings(3, 2, "magic")
        validate_combat_settings(PREPARATION, magic)
        with self.assertRaises(ValueError):
            validate_combat_settings(VideoPreparationRef("combat", "1.2.0"), magic)
        for settings, intention, key in ((magic, "", "powers"), (CombatSettings(2, 2, "hand_to_hand"), "", "hand_to_hand"),
                (CombatSettings(3, 2, "weapons"), "A heavy axe duel", "heavy_weapons"),
                (CombatSettings(3, 2, "weapons"), "Light sabres", "fast_weapons"),
                (CombatSettings(3, 2, "weapons"), "A sword cultivator duel", "aerial_fantasy"),
                (CombatSettings(3, 2, "mixed"), "Des gerbes de feu", "powers")):
            self.assertEqual(example_key(settings, intention), key)
            self.assertIn(key, demonstration(settings, "beat_sheet", intention))
        self.assertIn("battlefield scale", action_policy(magic))
        self.assertNotIn("battlefield scale", action_policy(replace(magic, action_level=2)))
        for path, digest in json.loads((ROOT / "tests/fixtures/pre_combat_1_3_assets.json").read_text(encoding="utf-8")).items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest, path)


class CinematicIntegrationTest(unittest.TestCase):
    def test_only_two_call_recipes_and_previous_routes_remain_available(self):
        catalog = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        for mode in ("fl2va", "ref2v"):
            recipes = [r for r in catalog.list() if r.preparation == PREPARATION and r.reference.cookbook_id.startswith(f"minimax.h3.{mode}.")]
            self.assertEqual([r.preparation_steps for r in recipes], [2])
            self.assertEqual(recipes[0].output_contract, sequence.CINEMATIC_PLAN_CONTRACT)
            for version in ("1.1.0", "1.1.1", "1.2.0"):
                self.assertEqual([catalog.get(f"minimax.h3.{mode}.combat.{route}", version).preparation_steps
                                  for route in ("prompt", "planned", "guided")], [1, 2, 3])

    def test_two_scripted_calls_reopen_and_render_revision_keep_direction(self):
        for mode in ("ref2v", "fl2va"):
            for streamed in (False, True):
                with self.subTest(mode=mode, streamed=streamed), tempfile.TemporaryDirectory() as directory:
                    plan, writer, _ = fixture("ref2va" if mode == "ref2v" else "fl2va", count=6)
                    settings = CombatSettings(3, 6, "magic")
                    service, gateway, session, _ = preparation_service(directory, mode, "planned",
                        [json.dumps(plan), json.dumps(writer), json.dumps(writer)], version="1.3.0", preparation_family="combat",
                        combat_settings=settings, source_text="A magical encounter lasting 8 seconds. No music or speech.",
                        roles=("first_frame", "last_frame") if mode == "fl2va" else ("subject_reference", "subject_reference"))
                    with self.assertRaises(ValueError):
                        service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
                    self.assertEqual(gateway.requests, [])
                    for stage in (CompositionStage.BEAT_SHEET, CompositionStage.FINAL_PROMPT):
                        if streamed:
                            events = list(service.stream_generate(session.session_id, stage))
                            self.assertEqual(events[-1].kind, StreamEventKind.COMPLETED, events[-1])
                        else:
                            service.generate(session.session_id, stage)
                        service.approve(session.session_id, stage)
                    self.assertEqual(len(gateway.requests), 2)
                    self.assertEqual(len(gateway.requests[0].images), 2)
                    self.assertEqual(gateway.requests[1].images, ())
                    self.assertFalse(service.sessions.get(session.session_id).brief_revisions)
                    for request in gateway.requests:
                        self.assertIn("COMBAT 1.3 SAVED CONTROLS", request.system_prompt)
                        self.assertIn("WORKED EXAMPLE (powers)", request.system_prompt)
                        self.assertNotIn("COMBAT ORIENTATION 1.2.0", request.system_prompt)
                    self.assertEqual(LocalPromptSessionStore(directory).get(session.session_id).combat_settings, settings)
                    service.revise(session.session_id, CompositionStage.FINAL_PROMPT, "Keep the same actions and direction.")
                    self.assertEqual(len(gateway.requests), 3)  # one explicit revision, never an automatic retry
                    renders = CombatRenderTest().service(directory)
                    renders.sessions, renders.compositions = service.sessions, service.compositions
                    renders.combat_revision_policies[PREPARATION] = load_combat_revision_policy(ROOT / "prompt_cookbooks/_blocks", "1.3.0")
                    project = renders.get_or_create_from_session(session.session_id)
                    self.assertEqual(project.revision_version, H3RenderRevisionVersion.COMBAT_1_3)
                    self.assertEqual(len(project.camera_clauses), 12)
                    self.assertEqual(LocalH3RenderProjectStore(directory).get(project.project_id), project)
                    request = renders._completion_request(project, "Keep the powers dominant.", include_reasoning=False, creative_audacity=2)
                    self.assertIn("COMBAT CINEMATIC REVISION 1.3.0", request.system_prompt)
                    reply = json.dumps({"message": "Direction retained.", "questions": [], "recommendations": [], "camera_directives": None,
                        "prompt": protect_h3_revision_camera(project.current_prompt, project.camera_clauses)})
                    revised = renders._accept_chat_response(project.project_id, reply, H3RenderRevisionVersion.COMBAT_1_3, "fixture")
                    self.assertEqual(revised.camera_clauses, project.camera_clauses)
                    self.assertEqual(revised.attempts, ())
                    lab = PromptLabService(gateway=gateway, profiles=LocalPromptProfileCatalog(ROOT / "prompt_profiles"), assets=service.assets, sessions=service.sessions)
                    fork = lab.fork_session(session.session_id)
                    self.assertEqual(fork.combat_settings, settings)
                    old = lab.fork_session(session.session_id, profile_id=session.profile_id, profile_version="1.2.0")
                    self.assertEqual(old.combat_settings.orientation, "mixed")

    def test_camera_revision_retains_untimed_second_phase_after_cut(self):
        prompt, context = compiled()
        directives = []
        for index, phase in enumerate(p for s in context["plan"]["shots"] for p in s["phases"]):
            directives.append({"id": f"camera_{index+1}", "start_ms": 4000 if index == 2 else 0, **phase["camera"]})
        self.assertEqual(_revision_camera_clauses(directives, tuple(context["cameras"]), continuous_phases=True), tuple(context["cameras"]))
        directives[-1]["start_ms"] = 4000
        with self.assertRaises(ValueError):
            _revision_camera_clauses(directives, tuple(context["cameras"]), continuous_phases=True)

    def test_conversion_preserves_all_phases_and_render_settings(self):
        prompt, context = compiled("fl2va", count=6)
        document = conversion_document(prompt)
        converted = compile_conversion(json.dumps({"shots": document["shots"]}), prompt, ("first_frame", "last_frame"),
            combat_sequence=True, combat_version="1.3.0")
        self.assertEqual(tuple(map(len, camera_layout(converted))), (2,) * 6)
        self.assertIn(context["plan"]["shots"][0]["transition"], converted)
        with tempfile.TemporaryDirectory() as directory:
            service, source, setup, _ = H3Ref2VConversionTest().service(directory)
            source = replace(source, current_prompt=prompt, preparation=PREPARATION, combat_settings=CombatSettings(3, 6, "magic"),
                revision_version=H3RenderRevisionVersion.COMBAT_1_3, camera_clauses=tuple(context["cameras"]))
            service.renders.projects.save(source)
            target = service.prepare(source.project_id, request_id="cinematic-conversion", prompt=prompt, model_id="fixture", setup=setup)
            target = list(service.stream(target.project_id))[-1].project
            self.assertEqual(target.adaptation.status, "ready", target.adaptation.error)
            self.assertEqual(target.adaptation.render_setup, setup)
            self.assertEqual(target.preparation, PREPARATION)
            self.assertEqual(target.combat_settings, source.combat_settings)
            self.assertEqual(target.camera_clauses, source.camera_clauses)
            self.assertEqual(target.attempts, ())
            self.assertEqual(len(service.renders.gateway.requests), 1)

    def test_previous_session_and_render_storage_schemas_remain_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            from tests.test_combat_identity import identity_candidate
            service, _, session, _ = preparation_service(directory, "ref2v", "prompt", [json.dumps(identity_candidate(2))],
                version="1.2.0", preparation_family="combat", combat_settings=CombatSettings(2, 2, "weapons"),
                source_text="A duel lasting 8 seconds.", roles=("subject_reference", "subject_reference"))
            service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            path = Path(directory) / "prompt_sessions" / session.session_id / "session.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["schema_version"], 13)
            raw["schema_version"] = 12
            path.write_text(json.dumps(raw), encoding="utf-8")
            self.assertEqual(LocalPromptSessionStore(directory).get(session.session_id).combat_settings, session.combat_settings)
            renders = CombatRenderTest().service(directory)
            renders.sessions, renders.compositions = service.sessions, service.compositions
            project = renders.get_or_create_from_session(session.session_id)
            path = Path(directory) / "h3_render_projects" / project.project_id / "project.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["schema_version"], 12)
            raw["schema_version"] = 9
            path.write_text(json.dumps(raw), encoding="utf-8")
            self.assertEqual(LocalH3RenderProjectStore(directory).get(project.project_id), project)
