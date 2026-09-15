"""User-run offline contracts: scripted LLM replies, no network or rendering."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from panelforge.application import PromptLabService, StreamEventKind
from panelforge.application import classic_cinematic as classic, cinematic_core_v1 as core
from panelforge.application.direct_ref2v_prompt import direct_reference_header_for_roles
from panelforge.application.h3_render import canonicalize_h3_revision, protect_h3_revision_camera
from panelforge.application.h3_ref2v_conversion import conversion_document, compile_conversion
from panelforge.domain import CompositionStage
from panelforge.domain.h3_render import H3RenderInputMode, H3RenderRevisionVersion
from panelforge.domain.video_preparation import (
    VideoPreparationRef, ClassicCinematicSettings, CombatSettings, validate_cinematic_settings,
)
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.storage import LocalPromptSessionStore, LocalH3RenderProjectStore
from tests.test_video_preparation_recipes import preparation_service
from tests import test_combat_preparation as render_fixtures
from tests import test_h3_ref2v_conversion as conversion_fixtures

ROOT = Path(__file__).resolve().parents[1]
PREPARATION = VideoPreparationRef("classic", "1.0.0")
BLOCK = ROOT / "prompt_cookbooks/_blocks/h3-classic-cinematic/1.0.0"


def fixture(mode="ref2va", count=2, *, setting=None, source="A quiet object reveal in eight seconds."):
    value = json.loads((BLOCK / "examples.json").read_text(encoding="utf-8"))
    plan = value["plan"]
    if count != 2:
        plan["shots"] = [deepcopy(plan["shots"][0]) for _ in range(count)]
        for shot in plan["shots"]:
            shot["duration_ms"] = 8000 // count
    writer = {"shots": [{"phases": [" ".join(p["actions"]) for p in s["phases"]]} for s in plan["shots"]],
              "overall_soundscape": plan["overall_soundscape"], "non_diegetic_music": plan["non_diegetic_music"]}
    settings = setting if setting is not None else ClassicCinematicSettings(count)
    context = {"mode": mode, "header": direct_reference_header_for_roles(("subject_reference",)) if mode == "ref2va" else "",
        "settings": settings.as_dict(), "preparation": PREPARATION.as_dict(), "source_text": source,
        "duration_ms": 8000, "dialogues": [], "dialogue_level": 0, "locked_speech": []}
    return plan, writer, context


def compiled(mode="ref2va", count=2, **kwargs):
    plan, writer, context = fixture(mode, count, **kwargs)
    context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
    prompt, saved = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
    return prompt, classic.decode_context(saved)


class ClassicCinematicContractTest(unittest.TestCase):
    def test_numbered_phase_key_preserves_exact_compilation_for_h3_and_ref2v(self):
        for mode in ("i2va", "ref2va"):
            for count in (1, 2):
                with self.subTest(mode=mode, count=count):
                    plan, writer, context = fixture(mode=mode, count=count)
                    context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
                    encoded = classic.encode_context(context)
                    expected = classic.compile_result(json.dumps(writer), encoded, "final_prompt")
                    variant = deepcopy(writer)
                    first, second = variant["shots"][0]["phases"]
                    variant["shots"][0] = {"phases": [first], "phases2": [second]}
                    before = deepcopy(variant)
                    normalized = classic._normalize_numbered_phase_key(variant, classic.Plan.model_validate(plan))
                    self.assertEqual(normalized, writer)
                    self.assertEqual(variant, before)
                    self.assertEqual(classic.compile_result(json.dumps(variant), encoded, "final_prompt"), expected)

    def test_numbered_phase_key_does_not_discard_extra_content_or_bypass_validation(self):
        plan, writer, context = fixture(count=1)
        context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
        encoded = classic.encode_context(context)
        first, second = writer["shots"][0]["phases"]
        cases = [
            {"phases": [first, second], "phases2": [second]},
            {"phases": [first], "phases2": []},
            {"phases": [first], "phases2": second},
            {"phases": [first], "phases2": [second], "phases3": ["Another action."]},
            {"phases": [first], "phases2": [second], "camera": "An extra movement."},
            {"phases": [first], "phases2": ["The camera pans left."]},
            {"phases": [first], "phases2": ['She says <d>[English] An unapproved line.</d>']},
        ]
        for shot in cases:
            with self.subTest(keys=list(shot)), self.assertRaises(ValueError):
                classic.compile_result(json.dumps({**writer, "shots": [shot]}), encoded, "final_prompt")
        one_phase = deepcopy(plan)
        one_phase["shots"][0]["phases"] = one_phase["shots"][0]["phases"][:1]
        with self.assertRaisesRegex(ValueError, "phases2 est ambigu"):
            classic._normalize_numbered_phase_key({**writer, "shots": [{"phases": [first], "phases2": [second]}]}, classic.Plan.model_validate(one_phase))
        wrong_shots = {**writer, "shots": [{"phases": [first], "phases2": [second]}, {"phases": [first]}]}
        with self.assertRaises(ValueError):
            classic.compile_result(json.dumps(wrong_shots), encoded, "final_prompt")

    def test_writer_preserves_one_shot_two_phases_and_repairs_only_that_packaging(self):
        plan, writer, context = fixture(count=1)
        self.assertEqual(len(plan["shots"][0]["phases"]), 2)
        context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
        expected = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
        split = deepcopy(writer)
        split["shots"] = [{"phases": [text]} for text in writer["shots"][0]["phases"]]
        self.assertEqual(classic.compile_result(json.dumps(split), classic.encode_context(context), "final_prompt"), expected)
        shape = json.loads(classic.schema("final_prompt", plan=plan))["properties"]["shots"]
        self.assertEqual((shape["minItems"], shape["maxItems"]), (1, 1))
        phases = shape["prefixItems"][0]["properties"]["phases"]
        self.assertEqual((phases["minItems"], phases["maxItems"]), (2, 2))
        self.assertIn('"shots": [{"phases": [', classic.writer_layout(plan))
        split["shots"].append({"phases": ["An unapproved extra action."]})
        with self.assertRaises(ValueError):
            classic.compile_result(json.dumps(split), classic.encode_context(context), "final_prompt")

    def test_auto_manual_priority_and_invalid_settings(self):
        auto = ClassicCinematicSettings()
        self.assertIsNone(classic.requested_count("A calm observation.", auto))
        self.assertEqual(classic.requested_count("Une scène en trois plans.", auto), 3)
        self.assertEqual(classic.requested_count("En un seul plan.", auto), 1)
        self.assertEqual(classic.requested_count("En un seul plan.", ClassicCinematicSettings(4)), 4)
        for value in (0, 7, True, 2.0, "2"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ClassicCinematicSettings(value)
        with self.assertRaises(ValueError):
            classic.requested_count("En 7 plans.", auto)
        with self.assertRaises(ValueError):
            validate_cinematic_settings(VideoPreparationRef(), auto)
        with self.assertRaises(ValueError):
            validate_cinematic_settings(VideoPreparationRef("combat", "1.3.0"), auto)
        with self.assertRaises(ValueError):
            validate_cinematic_settings(PREPARATION, CombatSettings())

    def test_five_input_modes_one_two_and_six_shots_with_exact_duration(self):
        for mode in ("t2va", "i2va", "l2va", "fl2va", "ref2va"):
            for count in (1, 2, 6):
                with self.subTest(mode=mode, count=count):
                    prompt, context = compiled(mode, count)
                    self.assertEqual(classic.prompt_errors(prompt, mode), ())
                    self.assertEqual(len(core.shot_bodies(prompt)), count)
                    self.assertEqual(sum(s["duration_ms"] for s in context["plan"]["shots"]), 8000)
                    self.assertEqual(len(context["cameras"]), 3 if count == 2 else 2 * count)
                    self.assertEqual("integrated_multimodal_description:" in prompt, mode != "ref2va")
                    self.assertIn(context["plan"]["shots"][-1]["end_state"], prompt)
                    if mode in ("l2va", "fl2va") and count > 1:
                        self.assertIn(f"Shot {count}", context["compiled_header"])
                        self.assertIn("8.00-second", context["compiled_header"])

    def test_auto_follows_intention_but_keeps_auto_in_saved_context(self):
        prompt, context = compiled(setting=ClassicCinematicSettings(), source="Une présentation en deux plans.")
        self.assertEqual(context["settings"], {"shot_count": None})
        self.assertEqual(len(core.shot_bodies(prompt)), 2)
        plan, _, wrong = fixture(count=2, setting=ClassicCinematicSettings(), source="En un seul plan.")
        with self.assertRaises(ValueError):
            classic.canonical_plan(json.dumps(plan), wrong)
        compiled(count=2, setting=ClassicCinematicSettings(2), source="En un seul plan.")

    def test_local_validation_before_writer_and_failed_revision_preserves_structure(self):
        plan, writer, context = fixture()
        bad = deepcopy(plan)
        bad["shots"][0]["phases"][0]["camera"]["motion"] = "shake.slightly"
        bad["shots"][0]["phases"][0]["camera"]["target_clause"] = "toward the bowl"
        with self.assertRaises(ValueError):
            classic.canonical_plan(json.dumps(bad), context)
        for field in ("cue", "actions"):
            bad = deepcopy(plan)
            value = "The camera cuts to a close-up."
            bad["shots"][0]["phases"][0][field] = [value] if field == "actions" else value
            with self.assertRaises(ValueError):
                classic.canonical_plan(json.dumps(bad), context)
        with self.assertRaises(ValueError):
            classic.canonical_plan(json.dumps(plan), {**context, "duration_ms": 1000})
        prompt, saved = compiled()
        for candidate in (prompt.replace("[Shot 2]", "[Shot 3]"),
                          prompt.replace("At 00:05.000,", "At 00:04.000,"),
                          prompt.replace(saved["plan"]["shots"][0]["pacing"], "A sudden frantic pursuit begins.")):
            with self.assertRaises(ValueError):
                classic.validate_final(candidate, saved)
        writer["shots"][0]["phases"].pop()
        with self.assertRaises(ValueError):
            classic.compile_result(json.dumps(writer), classic.encode_context(saved), "final_prompt")

    def test_references_and_speech_are_not_invented(self):
        plan, writer, context = fixture()
        context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
        for prose in ("<Picture 9> takes the bowl.", "She smiles. <d>[English] Hello!</d>"):
            bad = deepcopy(writer)
            bad["shots"][0]["phases"][0] = prose
            with self.assertRaises(ValueError):
                classic.compile_result(json.dumps(bad), classic.encode_context(context), "final_prompt")

    def test_existing_assets_and_recipe_defaults_remain_available(self):
        hashes = json.loads((ROOT / "tests/fixtures/pre_classic_cinematic_assets.json").read_text(encoding="utf-8"))
        for name, digest in hashes.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest, name)
        catalog = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        profiles = LocalPromptProfileCatalog(ROOT / "prompt_profiles")
        for mode, old in (("fl2va", "1.2.0"), ("ref2v", "1.1.0")):
            ident = f"minimax.h3.{mode}.classic.cinematic"
            recipe = catalog.get(ident + ".planned", "1.0.0")
            self.assertEqual(recipe.stages, ("beat_sheet", "final_prompt"))
            self.assertEqual(recipe.preparation_steps, 2)
            self.assertEqual(recipe.preparation, PREPARATION)
            self.assertEqual(profiles.get(ident, "1.0.0").preparation, PREPARATION)
            for text in (recipe.beat_sheet_system_prompt, recipe.final_prompt_system_prompt, recipe.revision_system_prompt):
                self.assertNotIn("COMBAT", text)
                self.assertNotIn("UNLEASHED", text)
            for route, calls in (("prompt", 1), ("planned", 2), ("guided", 3)):
                self.assertEqual(catalog.get(f"minimax.h3.{mode}.direct.{route}", old).preparation_steps, calls)

    def test_editing_classic_experimental_blocks_does_not_change_combat_or_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "prompt_cookbooks"
            shutil.copytree(ROOT / "prompt_cookbooks", destination)
            catalog = LocalPromptCookbookCatalog(destination)
            pins = (("minimax.h3.fl2va.combat.planned", "1.3.0"),
                    ("minimax.h3.fl2va.direct.planned", "1.2.0"))
            before = [catalog.get(*pin).beat_sheet_system_prompt for pin in pins]
            path = destination / "_blocks/h3-classic-cinematic/1.0.0/direction.system.txt"
            path.write_text(path.read_text(encoding="utf-8") + "\nCLASSIC_ONLY_FIXTURE", encoding="utf-8")
            after = LocalPromptCookbookCatalog(destination)
            self.assertEqual([after.get(*pin).beat_sheet_system_prompt for pin in pins], before)
            self.assertIn("CLASSIC_ONLY_FIXTURE", after.get("minimax.h3.fl2va.classic.cinematic.planned", "1.0.0").beat_sheet_system_prompt)


class ClassicCinematicIntegrationTest(unittest.TestCase):
    def test_two_calls_reopen_fork_and_render_revision(self):
        for mode in ("fl2va", "ref2v"):
            for streamed in (False, True):
                with self.subTest(mode=mode, streamed=streamed), tempfile.TemporaryDirectory() as directory:
                    plan, writer, _ = fixture()
                    settings = ClassicCinematicSettings()
                    service, gateway, session, _ = preparation_service(directory, mode, "planned",
                        [json.dumps(plan), json.dumps(writer), json.dumps(writer)], version="1.0.0", cinematic_settings=settings,
                        source_text="A quiet object reveal lasting 8 seconds. No music or speech.",
                        roles=("first_frame", "last_frame") if mode == "fl2va" else ("subject_reference",))
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
                    self.assertTrue(gateway.requests[0].images)
                    self.assertEqual(gateway.requests[1].images, ())
                    self.assertFalse(service.sessions.get(session.session_id).brief_revisions)
                    for request in gateway.requests:
                        self.assertIn("CLASSIC CINEMATIC 1.0", request.system_prompt)
                        self.assertNotIn("COMBAT", request.system_prompt)
                    service.revise(session.session_id, CompositionStage.FINAL_PROMPT, "Keep the quiet observation.")
                    self.assertEqual(len(gateway.requests), 3)  # explicit revision only
                    reopened = LocalPromptSessionStore(directory).get(session.session_id)
                    self.assertEqual(reopened.cinematic_settings, settings)
                    self.assertIsNone(reopened.combat_settings)
                    lab = PromptLabService(gateway=gateway, profiles=LocalPromptProfileCatalog(ROOT / "prompt_profiles"),
                        assets=service.assets, sessions=service.sessions)
                    self.assertEqual(lab.fork_session(session.session_id).cinematic_settings, settings)
                    changed = lab.fork_session(session.session_id, cinematic_settings=ClassicCinematicSettings(3))
                    self.assertEqual(changed.cinematic_settings.shot_count, 3)
                    renders = render_fixtures.CombatRenderTest().service(directory)
                    renders.sessions, renders.compositions = service.sessions, service.compositions
                    project = renders.get_or_create_from_session(session.session_id)
                    self.assertEqual(project.input_mode,
                        H3RenderInputMode.REF2VA if mode == "ref2v" else H3RenderInputMode.FL2VA)
                    self.assertEqual(project.reference_asset_ids,
                        tuple(r.asset_id for r in session.references) if mode == "ref2v" else ())
                    self.assertEqual(project.revision_version, H3RenderRevisionVersion.CLASSIC_CINEMATIC)
                    self.assertEqual(project.cinematic_settings, settings)
                    self.assertEqual(LocalH3RenderProjectStore(directory).get(project.project_id), project)
                    request = renders._completion_request(project, "Keep the quiet observation.", include_reasoning=False, creative_audacity=0)
                    self.assertIn("Classic cinematic 1.0", request.system_prompt)
                    self.assertNotIn("COMBAT", request.system_prompt)
                    reply = json.dumps({"message": "Cadrage conservé.", "questions": [], "recommendations": [], "camera_directives": None,
                        "prompt": protect_h3_revision_camera(project.current_prompt, project.camera_clauses)})
                    revised = renders._accept_chat_response(project.project_id, reply, H3RenderRevisionVersion.CLASSIC_CINEMATIC, "fixture")
                    self.assertEqual(revised.current_prompt, project.current_prompt)
                    self.assertEqual(revised.attempts, ())
                    with self.assertRaises(ValueError):
                        replace(project, revision_version=H3RenderRevisionVersion.VOCAL)

    def test_conversion_preserves_two_phase_shots_and_pinned_settings(self):
        prompt, context = compiled("fl2va", count=6)
        document = conversion_document(prompt)
        converted = compile_conversion(json.dumps({"shots": document["shots"]}), prompt,
            ("first_frame", "last_frame"), classic_cinematic=True)
        self.assertEqual(tuple(map(len, core.camera_layout(converted))), (2,) * 6)
        canonicalize_h3_revision(converted, converted, H3RenderInputMode.REF2VA, classic_cinematic=True)
        with tempfile.TemporaryDirectory() as directory:
            service, source, setup, _ = conversion_fixtures.H3Ref2VConversionTest().service(directory)
            source = replace(source, current_prompt=prompt, preparation=PREPARATION, cinematic_settings=ClassicCinematicSettings(6),
                revision_version=H3RenderRevisionVersion.CLASSIC_CINEMATIC, camera_clauses=tuple(context["cameras"]))
            service.renders.projects.save(source)
            target = service.prepare(source.project_id, request_id="classic-conversion", prompt=prompt, model_id="fixture", setup=setup)
            target = list(service.stream(target.project_id))[-1].project
            self.assertEqual(target.cinematic_settings, source.cinematic_settings)
            self.assertEqual(target.preparation, PREPARATION)
            self.assertEqual(target.revision_version, H3RenderRevisionVersion.CLASSIC_CINEMATIC)
            self.assertEqual(target.adaptation.status, "ready")
            self.assertEqual(target.attempts, ())

    def test_prior_session_schema_thirteen_keeps_legacy_classic(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _, session, _ = preparation_service(directory, "fl2va", "planned", [], version="1.2.0", profile_version="0.6.0")
            path = Path(directory) / "prompt_sessions" / session.session_id / "session.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["schema_version"], 15)
            raw["schema_version"] = 13
            raw.pop("sensual_settings")
            raw.pop("cinematic_settings")
            path.write_text(json.dumps(raw), encoding="utf-8")
            reopened = LocalPromptSessionStore(directory).get(session.session_id)
            self.assertEqual(reopened, session)
            self.assertIsNone(reopened.cinematic_settings)
