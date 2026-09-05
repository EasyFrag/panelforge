from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from panelforge.application import (
    ChangeViewRunner,
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    NewReference,
    PromptCompositionService,
    PromptLabService,
    SUPER_FAST_REF2V_COOKBOOK_ID,
    SUPER_FAST_REF2V_COOKBOOK_VERSION,
    StreamEventKind,
    StreamPhase,
)
from panelforge.application.direct_ref2v_multishot_plan_v2 import (
    auto_resolve_direct_ref2v_multishot_risks_v2,
)
from panelforge.domain import CompositionStage, CookbookBinding, ReferenceUse
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.presets import (
    ChangeViewPresetRecipe,
    load_change_view_preset,
)
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalPromptCompositionStore,
    LocalPromptSessionStore,
    LocalRunStore,
)


PNG = b"\x89PNG\r\n\x1a\nsuper-fast-reference"
PRESET_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "character.change_view"
    / "qwen-edit-2511-multiple-angles"
    / "0.2.0"
)


def _plan(*, unresolved: bool = True) -> dict[str, object]:
    return {
        "scene_setup": "A rain-soaked alley holds a runner and two blue crates.",
        "continuity_invariants": [
            "The runner, armor, rain, crate positions, and screen-right travel remain stable."
        ],
        "shots": [
            {
                "duration_ms": 2000,
                "opening_composition": {
                    "scale": "a wide view of the alley",
                    "angle": "eye level",
                    "axis": "the left side of the established travel axis",
                    "perspective": "deep wet pavement behind the first blue crate",
                },
                "purpose": "The runner begins the screen-right approach.",
                "new_information": "The first blue crate blocks the near path.",
                "continuity_from_previous": None,
                "actions": [
                    "The runner accelerates toward the first blue crate.",
                    "The runner plants one foot before the obstacle.",
                ],
                "observable_end_state": "The runner is compressed into takeoff beside the crate.",
                "active_picture_labels": ["<Picture 1>", "<Picture 2>"],
                "camera": {
                    "motion": "push.in",
                    "amplitude": "small",
                    "speed": "slow",
                    "target_clause": "toward the runner beside the first blue crate",
                    "visible_change": "The runner becomes more prominent before takeoff.",
                },
            },
            {
                "duration_ms": 2500,
                "opening_composition": {
                    "scale": "a low medium view",
                    "angle": "low angle",
                    "axis": "the same side of the established travel axis",
                    "perspective": "the second crate visible beyond the landing zone",
                },
                "purpose": "The runner clears the obstacle and lands.",
                "new_information": "The landing zone and second crate become visible.",
                "continuity_from_previous": {
                    "spatial_anchor": "The first blue crate remains below the runner.",
                    "subject_position": "The runner continues just above the first crate.",
                    "travel_direction": "The runner keeps moving toward screen right.",
                    "motion_phase": "The takeoff continues into the same airborne arc.",
                },
                "actions": [
                    "The runner clears the first crate along the established arc.",
                    "The runner lands beyond it and absorbs the impact.",
                ],
                "observable_end_state": "The runner is balanced beyond the first crate.",
                "active_picture_labels": ["<Picture 1>", "<Picture 2>"],
                "camera": None,
            },
        ],
        "final_state": {
            "description": "The runner holds a balanced stance facing screen right.",
            "final_hold_ms": 1000,
        },
        "risks": [
            {
                "risk_id": "direction",
                "category": "spatial",
                "description": "The travel direction could reverse across the cut.",
                "recommendation": "Keep the runner moving toward screen right",
                "resolution": None if unresolved else "Keep the runner moving toward screen right.",
            }
        ],
        "technical_adjustments": [],
        "overall_soundscape": "Rain, footfalls, armor movement, and a firm landing.",
        "non_diegetic_music": "N/A",
    }


def _prompt_body() -> str:
    return """A rain-soaked alley holds a runner and two blue crates under cold light.

[Shot 1] The runner accelerates screen right toward the first blue crate, plants one foot, and compresses into takeoff. The camera pushes in with small amplitude at slow speed toward the runner.

[Shot 2] At 00:02.000, a low side view catches the same airborne arc above the crate. The runner clears it, lands beyond it, absorbs the impact, and holds a balanced stance facing screen right.

overall_soundscape:
Rain, footfalls, armor movement, and a firm landing.

non_diegetic_music:
N/A"""


class _Gateway:
    def __init__(self) -> None:
        self.requests: list[CompletionRequest] = []
        self.content = _prompt_body()

    def list_models(self):
        return ()

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.requests.append(request)
        return CompletionResult(
            model_id=request.model_id,
            content=self.content,
            call_id=f"call-{len(self.requests)}",
        )

    def stream(self, request: CompletionRequest):
        self.requests.append(request)
        content = self.content
        if request.include_reasoning:
            yield CompletionStreamEvent(
                kind=StreamEventKind.REASONING,
                phase=StreamPhase.GENERATING,
                text="Trace de test sÃ©parÃ©e.",
            )
        yield CompletionStreamEvent(
            kind=StreamEventKind.DELTA,
            phase=StreamPhase.GENERATING,
            text=content,
        )
        yield CompletionStreamEvent(
            kind=StreamEventKind.COMPLETED,
            phase=StreamPhase.COMPLETED,
            text=content,
            result=CompletionResult(
                model_id=request.model_id,
                content=content,
                call_id=f"call-{len(self.requests)}",
            ),
        )


def _services(
    directory: str,
    *,
    freedom: int = 10,
    cookbook_version: str = SUPER_FAST_REF2V_COOKBOOK_VERSION,
    reference_count: int = 2,
):
    gateway = _Gateway()
    asset_ids = iter(f"asset-{number}" for number in range(1, reference_count + 1))
    assets = LocalAssetStore(directory, id_factory=lambda: next(asset_ids))
    first = assets.create(PNG + b"-first", "image/png")
    references = [NewReference(
        first.asset_id,
        "first_frame",
        "opening.png",
        (ReferenceUse.FIRST_FRAME,),
    )]
    if reference_count >= 2:
        subject = assets.create(PNG + b"-subject", "image/png")
        references.append(NewReference(
            subject.asset_id,
            "subject_reference",
            "identity.png",
            (ReferenceUse.SUBJECT,),
        ))
    if reference_count >= 3:
        composition_asset = assets.create(PNG + b"-composition", "image/png")
        references.append(NewReference(
            composition_asset.asset_id,
            "composition_reference",
            "framing.png",
            (ReferenceUse.COMPOSITION,),
        ))
    sessions = LocalPromptSessionStore(directory)
    prompt_lab = PromptLabService(
        gateway=gateway,
        profiles=LocalPromptProfileCatalog(PROJECT_ROOT / "prompt_profiles"),
        assets=assets,
        sessions=sessions,
    )
    session = prompt_lab.create_session(
        model_id="vision-model",
        profile_id="minimax.h3.ref2v.direct",
        profile_version="0.1.0",
        references=tuple(references),
    )
    session = prompt_lab.create_super_fast_brief(
        session.session_id,
        "Le coureur saute la caisse\npuis atterrit.",
        freedom,
        legacy_plan=cookbook_version == "0.1.0",
    )
    composition = PromptCompositionService(
        gateway=gateway,
        cookbooks=LocalPromptCookbookCatalog(PROJECT_ROOT / "prompt_cookbooks"),
        sessions=sessions,
        compositions=LocalPromptCompositionStore(directory),
        assets=assets,
    )
    composition.configure(
        session.session_id,
        SUPER_FAST_REF2V_COOKBOOK_ID,
        cookbook_version,
        (CookbookBinding(
            "references",
            tuple(reference.reference_id for reference in session.references),
        ),),
    )
    if cookbook_version == "0.1.0":
        gateway.content = json.dumps(_plan())
    return prompt_lab, composition, gateway, session


class SuperFastRef2VTest(unittest.TestCase):
    def test_risk_fallback_tracks_freedom_and_preserves_model_decisions(self):
        expected = {
            0: "Preserve the supplied evidence",
            30: "Use only the minimum",
            50: "Keep the runner moving",
            70: "Use a cinematic",
            100: "Use the recommendation as the continuity boundary",
        }
        for freedom, prefix in expected.items():
            with self.subTest(freedom=freedom):
                resolved = json.loads(
                    auto_resolve_direct_ref2v_multishot_risks_v2(
                        json.dumps(_plan()),
                        freedom,
                    )
                )
                self.assertTrue(
                    resolved["risks"][0]["resolution"].startswith(prefix)
                )
        authored = json.loads(
            auto_resolve_direct_ref2v_multishot_risks_v2(
                json.dumps(_plan(unresolved=False)),
                100,
            )
        )
        self.assertEqual(
            authored["risks"][0]["resolution"],
            "Keep the runner moving toward screen right.",
        )

    def test_internal_catalog_contract_is_hidden_from_manual_listing(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, gateway, _ = _services(directory)

            public_ids = {
                cookbook.reference.cookbook_id
                for cookbook in service.list_cookbooks()
            }
            internal = service.list_cookbooks(include_internal=True)
            cookbook = next(
                item
                for item in internal
                if item.reference.cookbook_id == SUPER_FAST_REF2V_COOKBOOK_ID
                and item.reference.version == SUPER_FAST_REF2V_COOKBOOK_VERSION
            )

            self.assertNotIn(SUPER_FAST_REF2V_COOKBOOK_ID, public_ids)
            self.assertEqual(cookbook.schema_version, 6)
            self.assertEqual(cookbook.visibility, "internal")
            self.assertEqual(cookbook.execution_mode, "super_fast_ref2v_direct_v2")
            self.assertEqual(gateway.requests, [])

    def test_one_call_persists_and_approves_direct_final_without_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            prompt_lab, service, gateway, session = _services(directory, freedom=10)

            self.assertTrue(session.brief_complete)
            self.assertEqual(session.active_brief_revision.origin.value, "manual")
            self.assertEqual(
                session.active_brief_revision.source_text,
                "Le coureur saute la caisse\npuis atterrit.",
            )
            self.assertIn("Creative freedom 10/100", session.active_brief_revision.content)
            self.assertEqual(gateway.requests, [])

            composition = service.generate_super_fast(session.session_id)

            self.assertEqual(len(gateway.requests), 1)
            request = gateway.requests[0]
            self.assertEqual(
                request.operation_id,
                "ref2v.super_fast.prompt_direct.generate",
            )
            self.assertEqual(len(request.images), 2)
            self.assertIn("10/100", request.user_prompt)
            self.assertIn("Factuel strict", request.user_prompt)
            self.assertIsNone(composition.beat_sheet.active_revision)
            self.assertIsNone(composition.beat_sheet.approved_revision_id)
            final = composition.final_prompt.active_revision
            self.assertIsNotNone(final)
            self.assertEqual(
                composition.final_prompt.approved_revision_id,
                composition.final_prompt.active_revision_id,
            )
            self.assertIn("<Picture 1>", final.content)
            self.assertIn("[Shot 1] The runner accelerates", final.content)
            self.assertIn("[Shot 2] At 00:02.000,", final.content)
            self.assertNotIn("scene_setup:", final.content)
            self.assertIsNone(final.compiler_context)
            self.assertTrue(prompt_lab.get_session(session.session_id).brief_complete)

    def test_stream_emits_direct_prompt_deltas_then_the_approved_final(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, gateway, session = _services(directory, freedom=55)

            events = tuple(service.stream_generate_super_fast(session.session_id))

            self.assertEqual(len(gateway.requests), 1)
            self.assertEqual(events[0].kind, StreamEventKind.DELTA)
            self.assertEqual(events[0].document_stage, CompositionStage.FINAL_PROMPT)
            self.assertEqual(events[-1].kind, StreamEventKind.COMPLETED)
            self.assertEqual(events[-1].document_stage, CompositionStage.FINAL_PROMPT)
            self.assertIn("[Shot 2] At 00:02.000,", events[-1].text)
            self.assertIsNotNone(events[-1].composition)
            self.assertIsNotNone(
                events[-1].composition.final_prompt.approved_revision_id
            )

    def test_direct_path_accepts_one_to_three_native_references(self):
        for reference_count in (1, 2, 3):
            with self.subTest(reference_count=reference_count), tempfile.TemporaryDirectory() as directory:
                _, service, gateway, session = _services(
                    directory,
                    reference_count=reference_count,
                )

                composition = service.generate_super_fast(session.session_id)

                self.assertEqual(len(gateway.requests[0].images), reference_count)
                content = composition.final_prompt.active_revision.content
                for number in range(1, reference_count + 1):
                    self.assertEqual(content.count(f"<Picture {number}>"), 1)
                self.assertNotIn(f"<Picture {reference_count + 1}>", content)

    def test_direct_path_extracts_one_fenced_body_and_drops_wrapper_prose(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, gateway, session = _services(directory)
            gateway.content = (
                "Here is the final MiniMax H3 prompt:\n\n```text\n"
                + _prompt_body()
                + "\n```\nThis is ready to use."
            )

            composition = service.generate_super_fast(session.session_id)

            content = composition.final_prompt.active_revision.content
            self.assertNotIn("```", content)
            self.assertNotIn("Here is", content)
            self.assertNotIn("ready to use", content)
            self.assertIn("[Shot 1] The runner accelerates", content)

    def test_direct_path_drops_common_unfenced_meta_preamble_and_conclusion(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, gateway, session = _services(directory)
            gateway.content = (
                "Certainly! Here is the complete MiniMax H3 prompt:\n\n"
                + _prompt_body()
                + "\n\nI hope this helps!"
            )

            composition = service.generate_super_fast(session.session_id)

            content = composition.final_prompt.active_revision.content
            self.assertNotIn("Certainly", content)
            self.assertNotIn("I hope this helps", content)
            self.assertTrue(content.rstrip().endswith("N/A"))

    def test_direct_path_rejects_an_incomplete_markdown_fence(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, gateway, session = _services(directory)
            gateway.content = "```text\n" + _prompt_body()

            with self.assertRaisesRegex(ValueError, "Markdown fence"):
                service.generate_super_fast(session.session_id)

            self.assertIsNone(service.get(session.session_id).final_prompt.active_revision)

    def test_direct_path_rejects_any_model_owned_picture_label_spelling(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, gateway, session = _services(directory)
            gateway.content = _prompt_body().replace(
                "A rain-soaked alley",
                "<picture 99 > A rain-soaked alley",
            )

            with self.assertRaisesRegex(ValueError, "Picture labels"):
                service.generate_super_fast(session.session_id)

    def test_direct_path_warns_about_timeline_and_empty_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, gateway, session = _services(directory)
            gateway.content = _prompt_body().replace(
                "[Shot 2] At 00:02.000,",
                "[Shot 2] At 00:00.000,",
            ).replace(
                "Rain, footfalls, armor movement, and a firm landing.",
                "",
            ).replace("\nN/A", "\n")

            composition = service.generate_super_fast(session.session_id)

            warnings = next(
                item.validation_warnings
                for item in service.status(composition)
                if item.stage is CompositionStage.FINAL_PROMPT
            )
            self.assertTrue(any("strictement croissants" in item for item in warnings))
            self.assertTrue(any("overall_soundscape" in item for item in warnings))
            self.assertTrue(any("non_diegetic_music" in item for item in warnings))

    def test_direct_auto_approval_cannot_approve_a_concurrent_manual_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, _, session = _services(directory)
            store = service.compositions
            original_save_if_current = store.save_if_current
            injected = False

            def save_with_manual_race(previous, updated):
                nonlocal injected
                saved = original_save_if_current(previous, updated)
                if not injected and saved.final_prompt.active_revision is not None:
                    injected = True
                    service.edit(
                        session.session_id,
                        CompositionStage.FINAL_PROMPT,
                        saved.final_prompt.active_revision.content.replace(
                            "rain-soaked alley",
                            "manual warm alley",
                        ),
                    )
                return saved

            store.save_if_current = save_with_manual_race
            with self.assertRaisesRegex(ValueError, "changed concurrently"):
                service.generate_super_fast(session.session_id)

            current = service.get(session.session_id)
            self.assertIn(
                "manual warm alley",
                current.final_prompt.active_revision.content,
            )
            self.assertIsNone(current.final_prompt.approved_revision_id)

    def test_direct_path_warns_but_does_not_reject_imperfect_h3_prose(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, gateway, session = _services(directory)
            gateway.content = _prompt_body().replace(
                "[Shot 2] At 00:02.000,",
                "[Shot 2] Later,",
            ).replace(
                "The camera pushes in with small amplitude at slow speed",
                "The camera moves naturally",
            )

            composition = service.generate_super_fast(session.session_id)

            final = composition.final_prompt.active_revision
            self.assertIsNotNone(final)
            self.assertEqual(
                composition.final_prompt.approved_revision_id,
                composition.final_prompt.active_revision_id,
            )
            warnings = next(
                item.validation_warnings
                for item in service.status(composition)
                if item.stage is CompositionStage.FINAL_PROMPT
            )
            self.assertTrue(any("timestamp" in warning for warning in warnings))
            self.assertTrue(any("camera" in warning for warning in warnings))

    def test_direct_path_rejects_non_prompt_json_without_creating_a_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, gateway, session = _services(directory)
            gateway.content = json.dumps(_plan())

            with self.assertRaisesRegex(ValueError, "prompt|Picture|heading"):
                service.generate_super_fast(session.session_id)

            composition = service.get(session.session_id)
            self.assertIsNone(composition.beat_sheet.active_revision)
            self.assertIsNone(composition.final_prompt.active_revision)

    def test_direct_prompt_revision_keeps_the_application_owned_header(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, gateway, session = _services(directory)
            generated = service.generate_super_fast(session.session_id)
            original = generated.final_prompt.active_revision.content
            original_header = original.split("\n\n", 1)[0]
            gateway.content = original_header + "\n\n" + _prompt_body().replace(
                "cold light",
                "warm amber light",
            )

            revised = service.revise(
                session.session_id,
                CompositionStage.FINAL_PROMPT,
                "Use warmer light.",
            )

            content = revised.final_prompt.active_revision.content
            self.assertTrue(content.startswith(original_header + "\n\n"))
            self.assertEqual(content.count("<Picture 1>"), 1)
            self.assertIn("warm amber light", content)
            self.assertEqual(len(gateway.requests[-1].images), 2)

    def test_direct_prompt_revision_extracts_a_fenced_body(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, gateway, session = _services(directory)
            generated = service.generate_super_fast(session.session_id)
            gateway.content = (
                "Here is the revised prompt:\n```text\n"
                + _prompt_body().replace("cold light", "warm amber light")
                + "\n```\nDone."
            )

            revised = service.revise(
                session.session_id,
                CompositionStage.FINAL_PROMPT,
                "Use warmer light.",
            )

            content = revised.final_prompt.active_revision.content
            self.assertNotIn("```", content)
            self.assertNotIn("Here is", content)
            self.assertNotIn("Done.", content)
            self.assertIn("warm amber light", content)

    def test_direct_prompt_revision_drops_common_unfenced_wrapper_prose(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, gateway, session = _services(directory)
            service.generate_super_fast(session.session_id)
            gateway.content = (
                "Sure — here is the revised MiniMax H3 prompt:\n\n"
                + _prompt_body().replace("cold light", "warm amber light")
                + "\n\nLet me know if you want another version."
            )

            revised = service.revise(
                session.session_id,
                CompositionStage.FINAL_PROMPT,
                "Use warmer light.",
            )

            content = revised.final_prompt.active_revision.content
            self.assertNotIn("Sure", content)
            self.assertNotIn("Let me know", content)
            self.assertTrue(content.rstrip().endswith("N/A"))

    def test_legacy_plan_first_run_with_no_first_camera_still_compiles(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, gateway, session = _services(
                directory,
                cookbook_version="0.1.0",
            )
            plan = _plan()
            plan["shots"][0]["camera"] = None
            gateway.content = json.dumps(plan)

            composition = service.generate_super_fast(session.session_id)

            self.assertIsNotNone(composition.beat_sheet.approved_revision_id)
            final = composition.final_prompt.active_revision
            self.assertIsNotNone(final)
            self.assertIn(
                "[Shot 1] The visible opening composition is",
                final.content,
            )

    def test_legacy_plan_first_renderer_preserves_opening_dialogue_tag_case(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, gateway, session = _services(
                directory,
                cookbook_version="0.1.0",
            )
            plan = _plan()
            plan["shots"][0]["actions"][0] = "<d>[English] Run!</d>"
            gateway.content = json.dumps(plan)

            composition = service.generate_super_fast(session.session_id)

            content = composition.final_prompt.active_revision.content
            self.assertIn("<d>[English] Run!</d>", content)
            self.assertNotIn("<D>", content)

    def test_legacy_auto_approval_cannot_approve_a_concurrent_plan_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, _, session = _services(
                directory,
                cookbook_version="0.1.0",
            )
            store = service.compositions
            original_save_if_current = store.save_if_current
            injected = False

            def save_with_plan_race(previous, updated):
                nonlocal injected
                saved = original_save_if_current(previous, updated)
                if (
                    not injected
                    and saved.beat_sheet.active_revision is not None
                    and saved.beat_sheet.approved_revision_id is None
                ):
                    injected = True
                    plan = json.loads(saved.beat_sheet.active_revision.content)
                    plan["scene_setup"] = "A manual concurrent scene setup."
                    service.edit(
                        session.session_id,
                        CompositionStage.BEAT_SHEET,
                        json.dumps(plan),
                    )
                return saved

            store.save_if_current = save_with_plan_race
            with self.assertRaisesRegex(ValueError, "changed concurrently"):
                service.generate_super_fast(session.session_id)

            current = service.get(session.session_id)
            self.assertIn(
                "A manual concurrent scene setup.",
                current.beat_sheet.active_revision.content,
            )
            self.assertIsNone(current.beat_sheet.approved_revision_id)
            self.assertIsNone(current.final_prompt.active_revision)

    def test_legacy_auto_approval_cannot_approve_a_concurrent_final_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, _, session = _services(
                directory,
                cookbook_version="0.1.0",
            )
            store = service.compositions
            original_save_if_current = store.save_if_current
            injected = False

            def save_with_final_race(previous, updated):
                nonlocal injected
                saved = original_save_if_current(previous, updated)
                if not injected and saved.final_prompt.active_revision is not None:
                    injected = True
                    service.edit(
                        session.session_id,
                        CompositionStage.FINAL_PROMPT,
                        saved.final_prompt.active_revision.content.replace(
                            "rain-soaked alley",
                            "manual warm alley",
                        ),
                    )
                return saved

            store.save_if_current = save_with_final_race
            with self.assertRaisesRegex(ValueError, "changed concurrently"):
                service.generate_super_fast(session.session_id)

            current = service.get(session.session_id)
            self.assertIn(
                "manual warm alley",
                current.final_prompt.active_revision.content,
            )
            self.assertIsNone(current.final_prompt.approved_revision_id)

    def test_generic_stage_generation_cannot_add_a_second_initial_call(self):
        with tempfile.TemporaryDirectory() as directory:
            _, service, gateway, session = _services(directory)

            with self.assertRaisesRegex(ValueError, "generate_super_fast"):
                service.generate(session.session_id, CompositionStage.BEAT_SHEET)

            self.assertEqual(gateway.requests, [])

    def test_web_route_runs_one_call_and_exposes_reasoning_only_on_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            prompt_lab, service, gateway, session = _services(directory, freedom=35)
            runner = ChangeViewRunner(
                recipe=ChangeViewPresetRecipe(
                    load_change_view_preset(PRESET_DIRECTORY)
                ),
                comfy=object(),
                assets=prompt_lab.assets,
                runs=LocalRunStore(directory),
            )
            with TestClient(create_app(
                runner,
                prompt_lab=prompt_lab,
                prompt_composition=service,
            )) as client:
                public_catalog = client.get("/api/prompt-lab/cookbooks").json()
                self.assertNotIn(
                    SUPER_FAST_REF2V_COOKBOOK_ID,
                    {item["id"] for item in public_catalog["cookbooks"]},
                )
                response = client.post(
                    f"/api/prompt-lab/sessions/{session.session_id}/super-fast/stream"
                    "?include_reasoning=true",
                    json={
                        "source_text": "Le coureur saute\npuis atterrit.",
                        "creative_freedom": 35,
                        "creative_audacity": 3,
                    },
                )

                self.assertEqual(response.status_code, 200, response.text)
                payloads = []
                for block in response.text.replace("\r\n", "\n").split("\n\n"):
                    data = "\n".join(
                        line[5:].lstrip()
                        for line in block.splitlines()
                        if line.startswith("data:")
                    )
                    if data:
                        payloads.append(json.loads(data))
                self.assertIn("reasoning", [item["kind"] for item in payloads])
                self.assertEqual(payloads[-1]["kind"], "completed")
                self.assertEqual(payloads[-1]["document_stage"], "final_prompt")
                self.assertTrue(
                    not payloads[-1]["composition"]["documents"]["beat_sheet"]["complete"]
                )
                self.assertTrue(
                    payloads[-1]["composition"]["documents"]["final_prompt"]["complete"]
                )
                self.assertEqual(len(gateway.requests), 1)
                self.assertTrue(gateway.requests[0].include_reasoning)
                persisted = prompt_lab.get_session(session.session_id)
                self.assertEqual(
                    persisted.active_brief_revision.source_text,
                    "Le coureur saute\npuis atterrit.",
                )
                self.assertEqual(persisted.active_brief_revision.creative_audacity, 3)
                self.assertIn(
                    "Creative audacity 3/3",
                    persisted.active_brief_revision.content,
                )

    def test_web_boundaries_reject_wrong_profile_and_manual_internal_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            prompt_lab, service, gateway, session = _services(directory, freedom=35)
            runner = ChangeViewRunner(
                recipe=ChangeViewPresetRecipe(
                    load_change_view_preset(PRESET_DIRECTORY)
                ),
                comfy=object(),
                assets=prompt_lab.assets,
                runs=LocalRunStore(directory),
            )
            wrong_profile = prompt_lab.create_session(
                model_id="vision-model",
                profile_id="minimax.h3.i2v.direct",
                profile_version="0.1.0",
                references=(NewReference(
                    session.references[0].asset_id,
                    "first_frame",
                    "opening.png",
                    (ReferenceUse.FIRST_FRAME,),
                ),),
            )
            with TestClient(create_app(
                runner,
                prompt_lab=prompt_lab,
                prompt_composition=service,
            )) as client:
                rejected = client.post(
                    f"/api/prompt-lab/sessions/{wrong_profile.session_id}/super-fast/stream",
                    json={"source_text": "Test", "creative_freedom": 35},
                )
                self.assertEqual(rejected.status_code, 422, rejected.text)
                self.assertIsNone(
                    prompt_lab.get_session(wrong_profile.session_id).active_brief_revision
                )

                manual = client.post(
                    f"/api/prompt-lab/sessions/{session.session_id}/composition",
                    json={
                        "cookbook_id": SUPER_FAST_REF2V_COOKBOOK_ID,
                        "cookbook_version": SUPER_FAST_REF2V_COOKBOOK_VERSION,
                        "bindings": {
                            "references": [
                                reference.reference_id
                                for reference in session.references
                            ]
                        },
                    },
                )
                self.assertEqual(manual.status_code, 422, manual.text)
                self.assertEqual(len(gateway.requests), 0)


if __name__ == "__main__":
    unittest.main()
