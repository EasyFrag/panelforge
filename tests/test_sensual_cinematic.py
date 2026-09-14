"""User-run offline contracts for the independent Sensual 1.0 family."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from panelforge.application import PromptLabService
from panelforge.application import cinematic_core_v1 as core, sensual_cinematic as sensual
from panelforge.application.direct_ref2v_prompt import direct_reference_header_for_roles
from panelforge.application.h3_ref2v_conversion import compile_conversion, conversion_document
from panelforge.application.h3_render import canonicalize_h3_revision
from panelforge.domain import CompositionStage
from panelforge.domain.h3_render import H3RenderInputMode, H3RenderRevisionVersion
from panelforge.domain.video_preparation import (
    SensualSettings,
    VideoPreparationRef,
    validate_sensual_settings,
)
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.storage import LocalH3RenderProjectStore, LocalPromptSessionStore
from tests import test_combat_preparation as render_fixtures
from tests import test_h3_ref2v_conversion as conversion_fixtures
from tests.test_video_preparation_recipes import preparation_service


ROOT = Path(__file__).resolve().parents[1]
PREPARATION = VideoPreparationRef("sensual", "1.0.0")
BLOCK = ROOT / "prompt_cookbooks/_blocks/h3-sensual/1.0.0"


def fixture(mode="i2va"):
    example = json.loads((BLOCK / "examples.json").read_text(encoding="utf-8"))
    context = {
        "mode": mode,
        "header": direct_reference_header_for_roles(("subject_reference",)) if mode == "ref2va" else "",
        "settings": SensualSettings().as_dict(),
        "preparation": PREPARATION.as_dict(),
        "source_text": "An explicit scene with two participants in one continuous eight-second shot.",
        "duration_ms": 8000,
        "dialogues": [],
        "dialogue_level": 0,
        "locked_speech": [],
    }
    return deepcopy(example["plan"]), deepcopy(example["writer"]), context


def compiled(mode="i2va"):
    plan, writer, context = fixture(mode)
    context["plan"] = json.loads(sensual.canonical_plan(json.dumps(plan), context))
    prompt, saved = sensual.compile_result(
        json.dumps(writer), sensual.encode_context(context), "final_prompt",
    )
    return prompt, sensual.decode_context(saved)


class SensualCinematicContractTest(unittest.TestCase):
    def test_exact_family_settings_and_two_stage_manifests(self):
        auto = SensualSettings()
        self.assertEqual(auto.as_dict(), {"explicitness": "explicit_maximal", "shot_count": None})
        validate_sensual_settings(PREPARATION, auto)
        for value in ("soft", "explicit", "unbounded"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                SensualSettings(value)
        with self.assertRaises(ValueError):
            VideoPreparationRef("sensual", None)
        with self.assertRaises(ValueError):
            validate_sensual_settings(VideoPreparationRef(), auto)

        catalog = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        profiles = LocalPromptProfileCatalog(ROOT / "prompt_profiles")
        for mode in ("fl2va", "ref2v"):
            recipe = catalog.get(f"minimax.h3.{mode}.sensual.planned", "1.0.0")
            profile = profiles.get(f"minimax.h3.{mode}.sensual", "1.0.0")
            self.assertEqual(recipe.stages, ("beat_sheet", "final_prompt"))
            self.assertEqual(recipe.preparation_steps, 2)
            self.assertEqual(recipe.preparation, PREPARATION)
            self.assertEqual(profile.preparation, PREPARATION)
            prompts = "\n".join((recipe.beat_sheet_system_prompt, recipe.final_prompt_system_prompt))
            self.assertIn("EXPLICIT MAXIMAL", prompts.upper())
            self.assertNotIn("undressing.single_shot", prompts.casefold())
            for term in ("adult", "consent", "voluntary", "coerc", "youth", "minor"):
                self.assertNotIn(term, prompts.casefold())
        schema = sensual.schema("beat_sheet").casefold()
        for term in ("adult", "consent", "voluntary", "coerc", "youth", "minor"):
            self.assertNotIn(term, schema)
            self.assertNotIn(term, sensual.REVISION_SYSTEM.casefold())

    def test_compiles_exact_beat_ledger_for_h3_base_and_ref2v(self):
        for mode in ("i2va", "ref2va"):
            with self.subTest(mode=mode):
                prompt, context = compiled(mode)
                self.assertEqual(sensual.prompt_errors(prompt, mode), ())
                self.assertEqual(tuple(map(len, core.camera_layout(prompt))), (2,))
                self.assertEqual(context["settings"], SensualSettings().as_dict())
                self.assertEqual(
                    [beat["beat_id"] for phase in context["sequence_plan"]["shots"][0]["phases"] for beat in phase["interactions"]],
                    ["beat_1", "beat_2", "beat_3"],
                )
                self.assertEqual("integrated_multimodal_description:" in prompt, mode != "ref2va")
                canonicalize_h3_revision(
                    prompt, prompt, H3RenderInputMode(mode), sensual_cinematic=True,
                )

    def test_plan_and_writer_reject_structural_drift(self):
        plan, writer, context = fixture()
        bad_plan = deepcopy(plan)
        bad_plan["shots"][0]["phases"][0]["interactions"][0]["beat_id"] = "beat_2"
        with self.assertRaises(ValueError):
            sensual.canonical_plan(json.dumps(bad_plan), context)
        bad_plan = deepcopy(plan)
        bad_plan["participants"][0]["unexpected"] = True
        with self.assertRaises(ValueError):
            sensual.canonical_plan(json.dumps(bad_plan), context)
        bad_plan = deepcopy(plan)
        bad_plan["shots"][0]["phases"][0]["interactions"][0]["actor"] = "An undeclared participant"
        with self.assertRaises(ValueError):
            sensual.canonical_plan(json.dumps(bad_plan), context)
        bad_plan = deepcopy(plan)
        bad_plan["participants"][0]["reference_picture"] = "<Picture 9>"
        with self.assertRaises(ValueError):
            sensual.canonical_plan(json.dumps(bad_plan), context)

        context["plan"] = json.loads(sensual.canonical_plan(json.dumps(plan), context))
        wrong_writer = deepcopy(writer)
        wrong_writer["shots"][0]["phases"][0]["beat_ids"].reverse()
        with self.assertRaises(ValueError):
            sensual.compile_result(json.dumps(wrong_writer), sensual.encode_context(context), "final_prompt")

    def test_legacy_alignment_fields_are_read_without_reentering_the_contract(self):
        plan, _, context = fixture()
        plan["consent_confirmed"] = True
        for participant in plan["participants"]:
            participant["adult"] = True
        normalized = json.loads(sensual.canonical_plan(json.dumps(plan), context))
        self.assertNotIn("consent_confirmed", normalized)
        self.assertTrue(all("adult" not in participant for participant in normalized["participants"]))

    def test_plan_canonicalizes_exact_unbracketed_language_and_passive_camera_position(self):
        plan, _, context = fixture()
        line = "Keep looking."
        beat = plan["shots"][0]["phases"][0]["interactions"][0]
        beat["action"] += f" and says <d>English {line}</d>"
        beat["contact"] += "; an off-screen voice comes from the camera position"
        plan["spoken_lines"] = [line]
        plan["spoken_languages"] = ["English"]
        context.update(
            source_text=f'One participant says "{line}"',
            dialogues=[line],
            locked_speech=[line],
        )

        normalized = json.loads(sensual.canonical_plan(json.dumps(plan), context))
        normalized_beat = normalized["shots"][0]["phases"][0]["interactions"][0]
        self.assertIn(f"<d>[English] {line}</d>", normalized_beat["action"])
        self.assertIn("from the camera position", normalized_beat["contact"])

        wrong_language = deepcopy(plan)
        wrong_language["shots"][0]["phases"][0]["interactions"][0]["action"] = (
            beat["action"].replace("<d>English ", "<d>French ")
        )
        with self.assertRaisesRegex(ValueError, "Langue manquante ou ambiguë"):
            sensual.canonical_plan(json.dumps(wrong_language), context)

        free_camera = deepcopy(plan)
        free_camera["shots"][0]["phases"][0]["interactions"][0]["contact"] = (
            "The camera drifts toward the passenger."
        )
        with self.assertRaisesRegex(ValueError, "camera movement"):
            sensual.canonical_plan(json.dumps(free_camera), context)

    def test_plan_teaches_the_exact_camera_target_prefix_contract(self):
        expected = (
            "to", "toward", "onto", "into", "from", "behind", "beside", "above", "below",
            "away from", "around", "along", "across", "past", "through", "following", "keeping",
            "maintaining", "revealing", "showing", "centered on", "focused on", "ending on", "framing",
            "holding", "leaving", "placing", "as", "while", "until", "with",
        )
        self.assertEqual(sensual.CAMERA_TARGET_PREFIXES, expected)
        prefixes = ", ".join(expected)
        plan_system = (BLOCK / "plan.system.txt").read_text(encoding="utf-8")
        schema = json.loads(sensual.schema("beat_sheet"))
        description = schema["$defs"]["Camera"]["properties"]["target_clause"]["description"]
        self.assertIn(prefixes, plan_system)
        self.assertIn(prefixes, description)
        self.assertIn("For tilt.down", plan_system)
        self.assertIn("for tilt.down", description)

        with self.assertRaisesRegex(ValueError, "spatial or visual continuation"):
            sensual.Camera(
                motion="tilt.down",
                amplitude="small",
                speed="slow",
                target_clause="down between the subjects",
            )
        directive = sensual.Camera(
            motion="tilt.down",
            amplitude="small",
            speed="slow",
            target_clause="ending on the subjects' joined hands",
        )
        self.assertEqual(directive.target_clause, "ending on the subjects' joined hands")

    def test_sensual_blocks_do_not_change_classic_or_combat(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "prompt_cookbooks"
            shutil.copytree(ROOT / "prompt_cookbooks", destination)
            catalog = LocalPromptCookbookCatalog(destination)
            pins = (
                ("minimax.h3.fl2va.classic.cinematic.planned", "1.0.0"),
                ("minimax.h3.fl2va.combat.planned", "1.3.0"),
            )
            before = [catalog.get(*pin).beat_sheet_system_prompt for pin in pins]
            path = destination / "_blocks/h3-sensual/1.0.0/direction.system.txt"
            path.write_text(path.read_text(encoding="utf-8") + "\nSENSUAL_ONLY_FIXTURE", encoding="utf-8")
            after = LocalPromptCookbookCatalog(destination)
            self.assertEqual([after.get(*pin).beat_sheet_system_prompt for pin in pins], before)
            self.assertIn(
                "SENSUAL_ONLY_FIXTURE",
                after.get("minimax.h3.fl2va.sensual.planned", "1.0.0").beat_sheet_system_prompt,
            )


class SensualCinematicIntegrationTest(unittest.TestCase):
    def test_two_calls_persist_fork_and_use_own_render_revision(self):
        for mode in ("fl2va", "ref2v"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                plan, writer, _ = fixture("i2va" if mode == "fl2va" else "ref2va")
                settings = SensualSettings()
                service, gateway, session, _ = preparation_service(
                    directory,
                    mode,
                    "planned",
                    [json.dumps(plan), json.dumps(writer)],
                    preparation_family="sensual",
                    sensual_settings=settings,
                    source_text="An explicit scene with two participants lasting eight seconds.",
                    roles=("first_frame",) if mode == "fl2va" else ("subject_reference",),
                )
                for stage in (CompositionStage.BEAT_SHEET, CompositionStage.FINAL_PROMPT):
                    service.generate(session.session_id, stage)
                    service.approve(session.session_id, stage)
                self.assertEqual(len(gateway.requests), 2)
                self.assertTrue(gateway.requests[0].images)
                self.assertEqual(gateway.requests[1].images, ())
                for request in gateway.requests:
                    self.assertIn("Sensual 1.0", request.system_prompt)
                    self.assertNotIn("undressing.single_shot", request.system_prompt.casefold())
                    for term in ("adult", "consent", "voluntary", "coerc", "youth", "minor"):
                        self.assertNotIn(term, request.system_prompt.casefold())

                reopened = LocalPromptSessionStore(directory).get(session.session_id)
                self.assertEqual(reopened.sensual_settings, settings)
                self.assertIsNone(reopened.combat_settings)
                self.assertIsNone(reopened.cinematic_settings)
                lab = PromptLabService(
                    gateway=gateway,
                    profiles=LocalPromptProfileCatalog(ROOT / "prompt_profiles"),
                    assets=service.assets,
                    sessions=service.sessions,
                )
                self.assertEqual(lab.fork_session(session.session_id).sensual_settings, settings)

                renders = render_fixtures.CombatRenderTest().service(directory)
                renders.sessions, renders.compositions = service.sessions, service.compositions
                project = renders.get_or_create_from_session(session.session_id)
                self.assertEqual(project.revision_version, H3RenderRevisionVersion.SENSUAL)
                self.assertEqual(project.sensual_settings, settings)
                request = renders._completion_request(
                    project, "Conserve exactement la progression.", False, 0,
                )
                self.assertIn("Sensual 1.0 explicit-maximal", request.system_prompt)
                self.assertNotIn("COMBAT POST-RENDER", request.system_prompt)
                for term in ("adult", "consent", "voluntary", "coerc", "youth", "minor"):
                    self.assertNotIn(term, request.system_prompt.casefold())
                self.assertEqual(LocalH3RenderProjectStore(directory).get(project.project_id), project)

    def test_h3_to_ref2v_conversion_keeps_family_and_settings(self):
        prompt, context = compiled("i2va")
        document = conversion_document(prompt)
        converted = compile_conversion(
            json.dumps({"shots": document["shots"]}),
            prompt,
            ("first_frame",),
            sensual_cinematic=True,
        )
        self.assertEqual(tuple(map(len, core.camera_layout(converted))), (2,))

        with tempfile.TemporaryDirectory() as directory:
            service, source, setup, _ = conversion_fixtures.H3Ref2VConversionTest().service(
                directory, mode=H3RenderInputMode.I2VA,
            )
            source = replace(
                source,
                current_prompt=prompt,
                preparation=PREPARATION,
                sensual_settings=SensualSettings(),
                revision_version=H3RenderRevisionVersion.SENSUAL,
                camera_clauses=tuple(context["cameras"]),
            )
            service.renders.projects.save(source)
            target = service.prepare(
                source.project_id,
                request_id="sensual-conversion",
                prompt=prompt,
                model_id="fixture",
                setup=setup,
            )
            target = list(service.stream(target.project_id))[-1].project
            self.assertEqual(target.preparation, PREPARATION)
            self.assertEqual(target.sensual_settings, SensualSettings())
            self.assertEqual(target.revision_version, H3RenderRevisionVersion.SENSUAL)
            self.assertEqual(target.adaptation.status, "ready")


if __name__ == "__main__":
    unittest.main()
