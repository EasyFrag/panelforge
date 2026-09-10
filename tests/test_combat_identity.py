"""User-run Combat 1.1.1 regressions. Fixed responses; no generation service."""
from dataclasses import replace
import hashlib
import json
import tempfile
import unittest

from panelforge.application import PromptLabService, StreamEventKind
from panelforge.application import combat_sequence as sequence
from panelforge.application.direct_ref2v_prompt import direct_reference_header_for_roles
from panelforge.application.h3_render import protect_h3_revision_camera
from panelforge.domain import CompositionStage
from panelforge.domain.h3_render import H3RenderRevisionVersion
from panelforge.domain.prompt_lab import CreativeFreedomAxes
from panelforge.domain.video_preparation import CombatSettings, VideoPreparationRef
from panelforge.infrastructure.combat_preparation import load_combat_revision_policy
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.storage import LocalH3RenderProjectStore, LocalPromptSessionStore
from tests.test_combat_preparation import BRIEF, INTENT, ROOT, CombatRenderTest
from tests.test_combat_sequence import candidate, context
from tests.test_video_preparation_recipes import preparation_service
from tests import test_h3_ref2v_conversion as conversion_fixtures


VERSION = "1.1.1"
PREPARATION = VideoPreparationRef("combat", VERSION)
REF_OPENING = (
    "The man in <Picture 1> is the fire-wielding combatant, on the left. "
    "The man in <Picture 2> is the ice-wielding combatant, on the right."
)
REF_ACTION = (
    "The fire-wielding combatant from <Picture 1> steps around the shield and strikes; "
    "the ice-wielding combatant from <Picture 2> deflects the strike into a counter."
)


def identity_candidate(count=1, *, planned=False, native=False):
    value = candidate(count, planned=planned)
    for shot in value["shots"]:
        shot["camera_motion"] = "tracking_shot"
        shot["opening_composition"] = (
            "The two combatants from the opening frame <Picture 1> face each other across the courtyard."
            if native else REF_OPENING
        )
        action = "The combatants from <Picture 1> exchange a parry and an advancing counter." if native else REF_ACTION
        shot["exchanges" if planned else "description"] = [action] if planned else action
    if planned:
        value["continuity_invariants"] = ["Keep the same referenced identities: " + value["shots"][0]["opening_composition"]]
    return value


def identity_context(count=1, mode="ref2va"):
    data = context(mode, count)
    data["preparation"] = PREPARATION.as_dict()
    if mode == "ref2va":
        data["header"] = direct_reference_header_for_roles(("subject_reference", "subject_reference"))
    return data


class CombatIdentityContractTest(unittest.TestCase):
    def test_inline_subject_links_compile_in_one_and_multiple_shots_and_revisions(self):
        for count in (1, 4):
            for planned in (False, True):
                with self.subTest(count=count, planned=planned):
                    data = identity_context(count)
                    value = identity_candidate(count, planned=planned)
                    if planned:
                        data["plan"] = json.loads(sequence.canonical_plan(json.dumps(value), data))
                        content = json.dumps({"shots": [REF_ACTION] * count,
                                              "overall_soundscape": "Impacts and footwork.", "non_diegetic_music": "N/A"})
                    else:
                        content = json.dumps(value)
                    prompt, saved = sequence.compile_result(content, sequence.encode_context(data), "final_prompt")
                    self.assertIn(REF_OPENING, prompt)
                    self.assertIn(REF_ACTION, prompt)
                    self.assertTrue(prompt.startswith(data["header"] + "\n\n"))
                    self.assertEqual(prompt.count(data["header"]), 1)
                    restored = sequence.decode_context(saved)
                    sequence.validate_final(prompt, restored)
                    self.assertEqual(len(restored["cameras"]), count)
                    if count > 1:
                        self.assertTrue(restored["cameras"][1].startswith("At "))
                    with self.assertRaises(ValueError):
                        sequence.validate_final(prompt.replace("The camera performs a tracking shot.", "The camera pushes in.", 1), restored)

    def test_only_existing_picture_mentions_are_allowed_and_headers_stay_owned(self):
        for invalid in ("<Picture 3>", "<Picture 01>", "<picture 1>"):
            value = identity_candidate()
            value["shots"][0]["description"] += " " + invalid
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "Picture"):
                sequence.compile_result(json.dumps(value), sequence.encode_context(identity_context()), "final_prompt")
        for field in ("opening_composition", "description"):
            value = identity_candidate()
            value["shots"][0][field] += " " + identity_context()["header"]
            with self.subTest(field=field), self.assertRaises(ValueError):
                sequence.compile_result(json.dumps(value), sequence.encode_context(identity_context()), "final_prompt")
        old = identity_context()
        old["preparation"] = VideoPreparationRef("combat", "1.1.0").as_dict()
        with self.assertRaises(ValueError):
            sequence.compile_result(json.dumps(identity_candidate()), sequence.encode_context(old), "final_prompt")

    def test_camera_prose_rejection_is_not_silently_bypassed(self):
        value = identity_candidate()
        value["shots"][0]["description"] += " The camera tracks laterally with the action as it relocates through the courtyard."
        with self.assertRaisesRegex(ValueError, "camera movement"):
            sequence.compile_result(json.dumps(value), sequence.encode_context(identity_context()), "final_prompt")

    def test_picture_numbers_follow_mapping_and_plans_reject_unknown_references(self):
        data = identity_context()
        data["header"] = direct_reference_header_for_roles(("environment_reference", "subject_reference", "subject_reference"))
        value = identity_candidate()
        for field in ("opening_composition", "description"):
            value["shots"][0][field] = value["shots"][0][field].replace("<Picture 2>", "<Picture 3>").replace("<Picture 1>", "<Picture 2>")
        result, _ = sequence.compile_result(json.dumps(value), sequence.encode_context(data), "final_prompt")
        self.assertIn("The man in <Picture 2> is the fire-wielding combatant", result)
        self.assertIn("The man in <Picture 3> is the ice-wielding combatant", result)
        plan = identity_candidate(planned=True)
        plan["continuity_invariants"].append("An unknown fighter from <Picture 4>.")
        with self.assertRaisesRegex(ValueError, "Picture"):
            sequence.canonical_plan(json.dumps(plan), data)

    def test_native_frame_roles_and_text_only_mode_remain_supported(self):
        for mode in ("t2va", "i2va", "l2va", "fl2va"):
            value = candidate(4) if mode == "t2va" else identity_candidate(4, native=True)
            data = identity_context(4, mode)
            prompt, saved = sequence.compile_result(json.dumps(value), sequence.encode_context(data), "final_prompt")
            self.assertEqual(sequence.prompt_errors(prompt, mode), ())
            if mode == "t2va":
                self.assertNotIn("<Picture", prompt)
            if mode in {"l2va", "fl2va"}:
                self.assertIn("Shot 4", sequence.decode_context(saved)["compiled_header"])

    def test_schema_field_guidance_is_scoped_to_the_new_version(self):
        for stage, planned, name in (("final_prompt", False, "Shot"), ("beat_sheet", True, "PlannedShot")):
            new = json.loads(sequence.schema(stage, planned, VERSION))
            old = json.loads(sequence.schema(stage, planned, "1.1.0"))
            fields = new["$defs"][name]["properties"]
            self.assertIn("sole field", fields["camera_motion"]["description"])
            self.assertIn("<Picture N>", fields["opening_composition"]["description"])
            self.assertNotIn("description", old["$defs"][name]["properties"]["camera_motion"])
        writer_schema = json.loads(sequence.schema("final_prompt", True, VERSION))
        self.assertIn("No camera movement", writer_schema["properties"]["shots"]["items"]["description"])


class CombatIdentityIntegrationTest(unittest.TestCase):
    def test_all_six_routes_stream_and_sync_keep_reference_links_and_exact_version(self):
        for streamed in (False, True):
            for mode in ("fl2va", "ref2v"):
                for route, calls in (("prompt", 1), ("planned", 2), ("guided", 3)):
                    with self.subTest(streamed=streamed, mode=mode, route=route), tempfile.TemporaryDirectory() as directory:
                        native = mode == "fl2va"
                        plan = identity_candidate(4, planned=True, native=native)
                        response = identity_candidate(4, native=native)
                        written = json.dumps({"shots": [shot["description"] for shot in response["shots"]],
                                              "overall_soundscape": response["overall_soundscape"], "non_diegetic_music": "N/A"})
                        responses = ([BRIEF] if calls == 3 else []) + ([json.dumps(response)] if calls == 1 else [json.dumps(plan), written])
                        service, gateway, session, _ = preparation_service(directory, mode, route, responses,
                            version=VERSION, preparation_family="combat", combat_settings=CombatSettings(3, 4), source_text=INTENT,
                            roles=("first_frame", "last_frame") if native else ("subject_reference", "subject_reference"))
                        if calls == 3:
                            lab = PromptLabService(gateway=gateway, profiles=LocalPromptProfileCatalog(ROOT / "prompt_profiles"), assets=service.assets, sessions=service.sessions)
                            if streamed:
                                list(lab.stream_structure_brief(session.session_id, INTENT, 0, CreativeFreedomAxes(0, 0, 0), creative_audacity=2))
                            else:
                                lab.structure_brief(session.session_id, INTENT, 0, CreativeFreedomAxes(0, 0, 0), creative_audacity=2)
                            lab.approve_brief(session.session_id)
                        for stage in ([CompositionStage.BEAT_SHEET] if calls > 1 else []) + [CompositionStage.FINAL_PROMPT]:
                            if streamed:
                                self.assertEqual(list(service.stream_generate(session.session_id, stage))[-1].kind, StreamEventKind.COMPLETED)
                            else:
                                service.generate(session.session_id, stage)
                            service.approve(session.session_id, stage)
                        self.assertEqual(len(gateway.requests), calls)
                        self.assertTrue(all("COMBAT REFERENCE IDENTITY 1.1.1" in r.system_prompt for r in gateway.requests))
                        self.assertTrue(all("Do not repeat headings, reference labels" not in r.system_prompt for r in gateway.requests))
                        self.assertIn("No camera movement", gateway.requests[-1].user_prompt)
                        self.assertEqual(len(gateway.requests[0].images), 2)
                        if calls > 1:
                            self.assertEqual(gateway.requests[-1].images, ())
                        self.assertEqual(LocalPromptSessionStore(directory).get(session.session_id).preparation, PREPARATION)
                        renders = CombatRenderTest().service(directory)
                        renders.sessions, renders.compositions = service.sessions, service.compositions
                        project = renders.get_or_create_from_session(session.session_id)
                        self.assertEqual(project.preparation, PREPARATION)
                        self.assertEqual(project.revision_version, H3RenderRevisionVersion.COMBAT_1_1_1)
                        self.assertEqual(project.combat_settings, CombatSettings(3, 4))
                        self.assertEqual(project.attempts, ())
                        self.assertIn("<Picture 1>", project.current_prompt)
                        self.assertEqual(LocalH3RenderProjectStore(directory).get(project.project_id), project)

    def test_direct_revision_and_post_render_keep_links_camera_and_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, session, _ = preparation_service(directory, "ref2v", "prompt",
                [json.dumps(identity_candidate(4)), json.dumps({"shots": [REF_ACTION] * 4, "overall_soundscape": "Footwork.", "non_diegetic_music": "N/A"})],
                version=VERSION, preparation_family="combat", combat_settings=CombatSettings(2, 4), source_text=INTENT,
                roles=("subject_reference", "subject_reference"))
            service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            service.revise(session.session_id, CompositionStage.FINAL_PROMPT, "Clarify the contact.")
            self.assertEqual(len(gateway.requests), 2)
            self.assertIn("WRITER OWNERSHIP", gateway.requests[-1].system_prompt)
            self.assertEqual(gateway.requests[-1].images, ())
            renders = CombatRenderTest().service(directory)
            renders.sessions, renders.compositions = service.sessions, service.compositions
            renders.combat_revision_policies[PREPARATION] = load_combat_revision_policy(ROOT / "prompt_cookbooks/_blocks", VERSION)
            project = renders.get_or_create_from_session(session.session_id)
            request = renders._completion_request(project, "Preserve their faces.", include_reasoning=False, creative_audacity=2)
            self.assertIn("POST-RENDER REVISION 1.1.1", request.system_prompt)
            self.assertIn("[[camera:", request.user_prompt)
            reply = json.dumps({"message": "Identities preserved in the prompt.", "questions": [],
                "prompt": protect_h3_revision_camera(project.current_prompt, project.camera_clauses),
                "recommendations": [], "camera_directives": None})
            revised = renders._accept_chat_response(project.project_id, reply, H3RenderRevisionVersion.COMBAT_1_1_1, "fixture")
            self.assertIn(REF_ACTION, revised.current_prompt)
            self.assertEqual(revised.camera_clauses, project.camera_clauses)
            self.assertEqual(revised.attempts, ())
            with self.assertRaises(ValueError):
                revised.select_revision_version(H3RenderRevisionVersion.COMBAT_1_1)

    def test_conversion_and_fork_keep_the_pinned_version(self):
        with tempfile.TemporaryDirectory() as directory:
            service, source, setup, _ = conversion_fixtures.H3Ref2VConversionTest().service(directory)
            prompt, _ = sequence.compile_result(json.dumps(identity_candidate(4, native=True)),
                sequence.encode_context(identity_context(4, "fl2va")), "final_prompt")
            source = replace(source, preparation=PREPARATION, combat_settings=CombatSettings(3, 4),
                revision_version=H3RenderRevisionVersion.COMBAT_1_1_1, current_prompt=prompt)
            service.renders.projects.save(source)
            target = service.prepare(source.project_id, request_id="identity-conversion", prompt=prompt, model_id="fixture", setup=setup)
            target = list(service.stream(target.project_id))[-1].project
            self.assertEqual(target.adaptation.status, "ready")
            self.assertEqual(target.preparation, PREPARATION)
            self.assertEqual(target.combat_settings, source.combat_settings)
            self.assertEqual(target.revision_version, H3RenderRevisionVersion.COMBAT_1_1_1)
            self.assertEqual(target.reference_asset_ids, (source.first_frame_asset_id, source.last_frame_asset_id))
            self.assertEqual(target.attempts, ())
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, session, _ = preparation_service(directory, "ref2v", "prompt", [],
                version=VERSION, preparation_family="combat", combat_settings=CombatSettings(3, 4))
            lab = PromptLabService(gateway=gateway, profiles=LocalPromptProfileCatalog(ROOT / "prompt_profiles"), assets=service.assets, sessions=service.sessions)
            fork = lab.fork_session(session.session_id)
            self.assertEqual(fork.preparation, PREPARATION)
            self.assertEqual(fork.combat_settings, session.combat_settings)
            legacy = lab.fork_session(session.session_id, profile_id=session.profile_id, profile_version="1.1.0")
            self.assertEqual(legacy.preparation, VideoPreparationRef("combat", "1.1.0"))
            self.assertEqual(gateway.requests, [])

    def test_every_previous_prompt_asset_remains_unchanged(self):
        for name in ("pre_combat_1_1_assets.json", "pre_combat_1_1_1_assets.json"):
            baseline = json.loads((ROOT / "tests/fixtures" / name).read_text(encoding="utf-8"))
            for path, expected in baseline.items():
                self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected, path)
        catalog = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        self.assertEqual(len([r for r in catalog.list() if r.preparation == PREPARATION]), 6)
        for old in ("1.0.0", "1.1.0"):
            self.assertNotIn("COMBAT REFERENCE IDENTITY 1.1.1", catalog.get("minimax.h3.ref2v.combat.prompt", old).final_prompt_system_prompt)
