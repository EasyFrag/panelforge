"""User-run Combat 1.2 tests with scripted LLM responses and no renderer."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.application import PromptLabService, StreamEventKind
from panelforge.application import combat_sequence as sequence
from panelforge.application.combat_orientation import orientation_policy
from panelforge.application.h3_render import protect_h3_revision_camera
from panelforge.domain import CompositionStage
from panelforge.domain.h3_render import H3RenderRevisionVersion
from panelforge.domain.prompt_lab import CreativeFreedomAxes
from panelforge.domain.video_preparation import CombatSettings, VideoPreparationRef, validate_combat_settings
from panelforge.infrastructure.combat_preparation import load_combat_revision_policy
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.storage import LocalH3RenderProjectStore, LocalPromptSessionStore
from tests.test_combat_preparation import BRIEF, INTENT, ROOT, CombatRenderTest
from tests.test_combat_identity import identity_candidate, identity_context, REF_ACTION
from tests.test_video_preparation_recipes import preparation_service
from tests import test_h3_ref2v_conversion as conversion_fixtures


PREPARATION = VideoPreparationRef("combat", "1.2.0")
ORIENTATIONS = {"mixed": "MIXED / FREE", "hand_to_hand": "HAND-TO-HAND", "weapons": "WEAPONS"}


class CombatOrientationContractTest(unittest.TestCase):
    def test_orientation_is_versioned_and_old_serialization_stays_exact(self):
        old = {"action_level": 2, "shot_count": 4}
        self.assertEqual(CombatSettings.from_dict(old).as_dict(), old)
        self.assertEqual(orientation_policy(CombatSettings.from_dict(old)), "")
        self.assertEqual(orientation_policy(None), "")
        for orientation, marker in ORIENTATIONS.items():
            settings = CombatSettings(2, 4, orientation)
            validate_combat_settings(PREPARATION, settings)
            self.assertEqual(CombatSettings.from_dict(settings.as_dict()), settings)
            policy = orientation_policy(settings)
            self.assertIn("COMBAT ORIENTATION 1.2.0", policy)
            self.assertIn(marker, policy)
            self.assertIn("If the intention requests one against several opponents", policy)
            self.assertIn("writers preserve the approved plan", policy)
            for version in ("1.1.0", "1.1.1"):
                with self.assertRaises(ValueError):
                    validate_combat_settings(VideoPreparationRef("combat", version), settings)
            with self.assertRaises(ValueError):
                validate_combat_settings(VideoPreparationRef(), settings)
        with self.assertRaises(ValueError):
            validate_combat_settings(PREPARATION, CombatSettings())
        for value in ("unknown", "", True, 1, ["weapons"]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                CombatSettings(orientation=value)

    def test_settings_survive_compilation_independently_of_action_and_cuts(self):
        for orientation in ORIENTATIONS:
            for count in (1, 4):
                data = identity_context(count)
                data["preparation"] = PREPARATION.as_dict()
                data["settings"] = CombatSettings(3, count, orientation).as_dict()
                prompt, encoded = sequence.compile_result(json.dumps(identity_candidate(count)), sequence.encode_context(data), "final_prompt")
                saved = sequence.decode_context(encoded)
                self.assertEqual(saved["settings"], data["settings"])
                self.assertEqual(len(saved["shot_starts_ms"]), count)
                self.assertIn(REF_ACTION, prompt)
                sequence.validate_final(prompt, saved)

    def test_older_templates_and_family_are_not_modified(self):
        for name in ("pre_combat_1_1_assets.json", "pre_combat_1_1_1_assets.json", "pre_combat_1_2_assets.json"):
            for path, digest in json.loads((ROOT / "tests/fixtures" / name).read_text(encoding="utf-8")).items():
                self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest, path)
        catalog = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        for mode in ("fl2va", "ref2v"):
            recipes = [r for r in catalog.list() if r.preparation == PREPARATION and r.reference.cookbook_id.startswith(f"minimax.h3.{mode}.")]
            self.assertEqual(sorted(r.preparation_steps for r in recipes), [1, 2, 3])
            for version in ("1.0.0", "1.1.0", "1.1.1"):
                self.assertEqual(catalog.get(f"minimax.h3.{mode}.combat.prompt", version).preparation.version, version)


class CombatOrientationIntegrationTest(unittest.TestCase):
    def test_six_routes_and_three_orientations_use_only_the_expected_calls(self):
        for streamed in (False, True):
            for orientation, marker in ORIENTATIONS.items():
                for mode in ("ref2v", "fl2va"):
                    for route, calls in (("prompt", 1), ("planned", 2), ("guided", 3)):
                        with self.subTest(streamed=streamed, orientation=orientation, mode=mode, route=route), tempfile.TemporaryDirectory() as directory:
                            native = mode == "fl2va"
                            value = identity_candidate(4, native=native)
                            plan = identity_candidate(4, planned=True, native=native)
                            written = json.dumps({"shots": [s["description"] for s in value["shots"]], "overall_soundscape": "Impacts and footwork.", "non_diegetic_music": "N/A"})
                            responses = ([BRIEF] if calls == 3 else []) + ([json.dumps(value)] if calls == 1 else [json.dumps(plan), written])
                            settings = CombatSettings(3, 4, orientation)
                            service, gateway, session, _ = preparation_service(directory, mode, route, responses,
                                version="1.2.0", preparation_family="combat", combat_settings=settings, source_text=INTENT,
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
                            for request in gateway.requests:
                                self.assertIn("COMBAT ORIENTATION 1.2.0", request.system_prompt)
                                self.assertIn(marker, request.system_prompt)
                                self.assertIn("COMBAT REFERENCE IDENTITY 1.1.1", request.system_prompt)
                            if calls > 1:
                                self.assertEqual(gateway.requests[-1].images, ())
                            self.assertEqual(LocalPromptSessionStore(directory).get(session.session_id).combat_settings, settings)
                            raw = json.loads((Path(directory) / "prompt_sessions" / session.session_id / "session.json").read_text(encoding="utf-8"))
                            self.assertEqual(raw["schema_version"], 15)
                            renders = CombatRenderTest().service(directory)
                            renders.sessions, renders.compositions = service.sessions, service.compositions
                            project = renders.get_or_create_from_session(session.session_id)
                            self.assertEqual(project.preparation, PREPARATION)
                            self.assertEqual(project.revision_version, H3RenderRevisionVersion.COMBAT_1_2)
                            self.assertEqual(project.combat_settings, settings)
                            self.assertEqual(LocalH3RenderProjectStore(directory).get(project.project_id), project)
                            self.assertEqual(project.attempts, ())

    def test_revisions_and_forks_keep_orientation_without_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = CombatSettings(2, 4, "weapons")
            response = json.dumps(identity_candidate(4))
            written = json.dumps({"shots": [REF_ACTION] * 4, "overall_soundscape": "Footwork.", "non_diegetic_music": "N/A"})
            service, gateway, session, _ = preparation_service(directory, "ref2v", "prompt", [response, written],
                version="1.2.0", preparation_family="combat", combat_settings=settings, source_text=INTENT,
                roles=("subject_reference", "subject_reference"))
            service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            service.revise(session.session_id, CompositionStage.FINAL_PROMPT, "Clarify the parry.")
            self.assertEqual(len(gateway.requests), 2)
            self.assertIn("WEAPONS", gateway.requests[-1].system_prompt)
            self.assertIn("WRITER OWNERSHIP", gateway.requests[-1].system_prompt)
            renders = CombatRenderTest().service(directory)
            renders.sessions, renders.compositions = service.sessions, service.compositions
            renders.combat_revision_policies[PREPARATION] = load_combat_revision_policy(ROOT / "prompt_cookbooks/_blocks", "1.2.0")
            project = renders.get_or_create_from_session(session.session_id)
            request = renders._completion_request(project, "Preserve the grip.", include_reasoning=False, creative_audacity=2)
            self.assertIn("POST-RENDER REVISION 1.2.0", request.system_prompt)
            self.assertIn("COMBAT ORIENTATION 1.2.0", request.system_prompt)
            reply = json.dumps({"message": "Grip retained.", "questions": [], "recommendations": [], "camera_directives": None,
                "prompt": protect_h3_revision_camera(project.current_prompt, project.camera_clauses)})
            revised = renders._accept_chat_response(project.project_id, reply, H3RenderRevisionVersion.COMBAT_1_2, "fixture")
            self.assertEqual(revised.combat_settings, settings)
            self.assertEqual(revised.camera_clauses, project.camera_clauses)
            self.assertEqual(revised.attempts, ())
            lab = PromptLabService(gateway=gateway, profiles=LocalPromptProfileCatalog(ROOT / "prompt_profiles"), assets=service.assets, sessions=service.sessions)
            fork = lab.fork_session(session.session_id)
            self.assertEqual(fork.preparation, PREPARATION)
            self.assertEqual(fork.combat_settings, settings)
            old = lab.fork_session(session.session_id, profile_id=session.profile_id, profile_version="1.1.1")
            self.assertIsNone(old.combat_settings.orientation)
            upgraded = lab.fork_session(old.session_id, profile_id=old.profile_id, profile_version="1.2.0")
            self.assertEqual(upgraded.combat_settings.orientation, "mixed")
            self.assertEqual(len(gateway.requests), 2)

    def test_conversion_keeps_orientation_and_render_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            service, source, setup, _ = conversion_fixtures.H3Ref2VConversionTest().service(directory)
            data = identity_context(4, "fl2va")
            settings = CombatSettings(3, 4, "weapons")
            data.update(preparation=PREPARATION.as_dict(), settings=settings.as_dict())
            prompt, _ = sequence.compile_result(json.dumps(identity_candidate(4, native=True)), sequence.encode_context(data), "final_prompt")
            source = replace(source, preparation=PREPARATION, combat_settings=settings,
                revision_version=H3RenderRevisionVersion.COMBAT_1_2, current_prompt=prompt)
            service.renders.projects.save(source)
            target = service.prepare(source.project_id, request_id="orientation-conversion", prompt=prompt, model_id="fixture", setup=setup)
            target = list(service.stream(target.project_id))[-1].project
            self.assertEqual(target.adaptation.status, "ready")
            self.assertEqual(target.preparation, PREPARATION)
            self.assertEqual(target.combat_settings, settings)
            self.assertEqual(target.adaptation.render_setup, setup)
            self.assertEqual(target.revision_version, H3RenderRevisionVersion.COMBAT_1_2)
            self.assertEqual(target.attempts, ())

    def test_previous_storage_schemas_remain_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = CombatSettings(2, 4)
            service, _, session, _ = preparation_service(directory, "ref2v", "prompt", [json.dumps(identity_candidate(4))],
                version="1.1.1", preparation_family="combat", combat_settings=settings, source_text=INTENT,
                roles=("subject_reference", "subject_reference"))
            service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            path = Path(directory) / "prompt_sessions" / session.session_id / "session.json"
            raw = json.loads(path.read_text(encoding="utf-8")); raw.pop("sensual_settings"); raw.pop("cinematic_settings"); raw["schema_version"] = 11
            path.write_text(json.dumps(raw), encoding="utf-8")
            self.assertEqual(LocalPromptSessionStore(directory).get(session.session_id).combat_settings, settings)
            renders = CombatRenderTest().service(directory)
            renders.sessions, renders.compositions = service.sessions, service.compositions
            project = renders.get_or_create_from_session(session.session_id)
            path = Path(directory) / "h3_render_projects" / project.project_id / "project.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["schema_version"], 14)
            raw["schema_version"] = 8; path.write_text(json.dumps(raw), encoding="utf-8")
            self.assertEqual(LocalH3RenderProjectStore(directory).get(project.project_id), project)
