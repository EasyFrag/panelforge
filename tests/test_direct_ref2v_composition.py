import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from panelforge.application import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    PromptCompositionService,
    StreamEventKind,
    StreamPhase,
)
from panelforge.domain import (
    BriefReferenceSnapshot,
    BriefRevision,
    CompositionStage,
    CookbookBinding,
    PromptLabSession,
    PromptReference,
    PromptSessionMode,
    ReferenceUse,
    RevisionOrigin,
)
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.storage import (
    LocalAssetStore,
    LocalPromptCompositionStore,
    LocalPromptSessionStore,
)


COOKBOOK_ROOT = PROJECT_ROOT / "prompt_cookbooks"
PNG = b"\x89PNG\r\n\x1a\nreference-"
DIRECT_CONTEXT_MARKER = "__PANELFORGE_DIRECT_REF2V_CONTEXT__:"


def action_plan(*, with_camera: bool = True) -> dict:
    return {
        "duration_seconds": 12,
        "scene_setup": "One continuous room with stable geometry and warm light.",
        "continuity_invariants": [
            "The room layout, lighting, and participant identities remain stable."
        ],
        "beats": [
            {
                "beat_id": "handoff",
                "start_ms": 0,
                "end_ms": 8000,
                "primary_action": "A courier carries a parcel to a recipient.",
                "participants": ["courier", "recipient", "parcel"],
                "observable_end_state": "The recipient holds the parcel.",
                "steps": [
                    {
                        "step_id": "approach",
                        "start_ms": 0,
                        "end_ms": 4000,
                        "action": "The courier approaches while carrying the parcel.",
                        "continuity_after": "The parcel remains in the courier's hands.",
                    },
                    {
                        "step_id": "transfer",
                        "start_ms": 4000,
                        "end_ms": 8000,
                        "action": "Both people share the parcel's weight before release.",
                        "continuity_after": "Only the recipient holds the parcel.",
                    },
                ],
            }
        ],
        "final_state": {
            "start_ms": 8000,
            "description": "Both people hold eye contact while the recipient holds the parcel.",
            "hold_until_end": True,
        },
        "camera_directives": (
            [
                {
                    "directive_id": "camera_1",
                    "start_ms": 8000,
                    "end_ms": 11000,
                    "motion": "push.in",
                    "amplitude": "small",
                    "speed": "slow",
                    "target_clause": "toward the parcel held by the recipient",
                    "visible_change": "The parcel and both faces become more prominent.",
                }
            ]
            if with_camera
            else []
        ),
        "risks": [],
        "technical_adjustments": [],
        "overall_soundscape": "Quiet room tone, footsteps, and soft parcel handling.",
        "non_diegetic_music": "N/A",
    }


def action_plan_v2(*, with_camera: bool = True) -> dict:
    value = action_plan(with_camera=with_camera)
    value.pop("duration_seconds")
    if value["camera_directives"]:
        value["camera_directives"][0]["end_ms"] = 9000
    value["final_state"] = {
        "description": value["final_state"]["description"],
        "final_hold_ms": 1500,
    }
    return value


def final_document(
    *,
    with_camera: bool = True,
    duration: str = "12",
    camera_layout: str = "canonical",
    camera_owned: bool = False,
) -> str:
    camera = (
        (
            "At 00:08.000, The recipient secures the parcel.\n"
            if camera_owned
            else "At 00:08.000, [[camera:camera_1]]\n"
        )
        if with_camera
        else "At 00:08.000, the transfer is complete.\n"
    )
    shot_header = "shot_1:\n"
    if with_camera and camera_layout == "extra_period":
        camera = camera.replace("]]\n", "]].\n")
    elif with_camera and camera_layout == "inline_field":
        shot_header = "shot_1: [[camera:camera_1]] "
        camera = "At 00:08.000, the transfer is complete.\n"
    elif with_camera and camera_layout == "embedded_prose":
        camera = "At 00:08.000, the recipient turns while [[camera:camera_1]] following the parcel.\n"
    return (
        "scene_setup:\n"
        f"The target video is one continuous {duration}-second shot. The same warm room, "
        "table, lighting, courier, recipient, and parcel remain spatially stable.\n"
        f"{shot_header}"
        "The courier crosses the room with both hands supporting the parcel. The "
        "recipient takes a shared grip before the courier releases it.\n"
        f"{camera}"
        "The recipient holds the parcel while both people maintain natural balance "
        "and eye contact until the end.\n"
        "overall_soundscape:\n"
        "Quiet room tone, measured footsteps, natural breathing, and soft parcel handling.\n"
        "non_diegetic_music:\n"
        "N/A"
    )


class DirectGateway:
    def __init__(
        self,
        *,
        with_camera: bool = True,
        camera_layout: str = "canonical",
        camera_owned: bool = False,
    ) -> None:
        self.with_camera = with_camera
        self.camera_layout = camera_layout
        self.camera_owned = camera_owned
        self.requests: list[CompletionRequest] = []

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.requests.append(request)
        is_v2 = "REQUIRED DIRECT REF2V V2" in request.user_prompt
        if request.operation_id == "action_plan.generate":
            content = json.dumps(
                action_plan_v2(with_camera=self.with_camera)
                if is_v2
                else action_plan(with_camera=self.with_camera)
            )
        else:
            content = final_document(
                with_camera=self.with_camera,
                duration="12",
                camera_layout=self.camera_layout,
                camera_owned=self.camera_owned,
            )
        return CompletionResult(
            model_id=request.model_id,
            content=content,
            call_id=f"call-{len(self.requests)}",
        )

    def stream(self, request: CompletionRequest):
        self.requests.append(request)
        content = final_document(
            with_camera=self.with_camera,
            camera_layout=self.camera_layout,
            camera_owned=self.camera_owned,
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


class ArbitrationGateway(DirectGateway):
    decision = "Keep the fur slightly damp while preserving the current action."

    @staticmethod
    def _planned(*, resolved: bool) -> dict:
        value = action_plan_v2()
        value["risks"] = [
            {
                "risk_id": "risk_1",
                "category": "reference",
                "description": "The fur state is ambiguous between references.",
                "recommendation": "Keep the fur slightly damp.",
                "resolution": ArbitrationGateway.decision if resolved else None,
            },
            {
                "risk_id": "risk_2",
                "category": "spatial",
                "description": "The parcel path needs a stable side.",
                "recommendation": "Keep the parcel on frame right.",
                "resolution": None,
            },
        ]
        if resolved:
            value["beats"][0]["primary_action"] += " The fur remains slightly damp."
        return value

    def complete(self, request: CompletionRequest) -> CompletionResult:
        if request.operation_id != "action_plan.generate":
            return super().complete(request)
        self.requests.append(request)
        return CompletionResult(
            model_id=request.model_id,
            content=json.dumps(self._planned(resolved=False)),
            call_id=f"call-{len(self.requests)}",
        )

    def stream(self, request: CompletionRequest):
        if request.operation_id != "action_plan.reconcile":
            yield from super().stream(request)
            return
        self.requests.append(request)
        content = json.dumps(self._planned(resolved=True))
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


def direct_session(
    assets: LocalAssetStore,
    reference_count: int,
) -> tuple[PromptLabSession, tuple[bytes, ...]]:
    definitions = (
        ("first_frame", ReferenceUse.FIRST_FRAME, "Opening frame"),
        ("subject_reference", ReferenceUse.SUBJECT, "Identity reference"),
        ("environment_reference", ReferenceUse.ENVIRONMENT, "Room reference"),
    )[:reference_count]
    references: list[PromptReference] = []
    contents: list[bytes] = []
    for index, (role, use, label) in enumerate(definitions, 1):
        content = PNG + str(index).encode("ascii")
        asset = assets.create(content, "image/png")
        contents.append(content)
        references.append(
            PromptReference(
                reference_id=f"reference-{index}",
                asset_id=asset.asset_id,
                role=role,
                label=label,
                uses=(use,),
            )
        )
    session = PromptLabSession(
        session_id="direct-session",
        model_id="vision-model",
        profile_id="minimax.h3.ref2v.direct",
        profile_version="0.1.0",
        references=tuple(references),
        session_mode=PromptSessionMode.DIRECT_MULTIMODAL,
    )
    session = session.add_brief_revision(
        BriefRevision(
            revision_id="brief-1",
            source_text="Le coursier remet le colis au destinataire.",
            content=(
                "Le décor, les identités et les limites d'influence de chaque image "
                "doivent rester stables pendant une remise de colis continue."
            ),
            creative_freedom=35,
            origin=RevisionOrigin.MODEL,
            references=tuple(
                BriefReferenceSnapshot(
                    reference_id=reference.reference_id,
                    analysis_revision_id=None,
                    uses=reference.uses,
                    evidence_policy=reference.evidence_policy,
                )
                for reference in references
            ),
        )
    ).approve_brief()
    return session, tuple(contents)


def configured_service(
    directory: str,
    reference_count: int,
    *,
    with_camera: bool = True,
    cookbook_version: str = "0.1.0",
):
    asset_ids = iter(f"asset-{index}" for index in range(1, 4))
    assets = LocalAssetStore(directory, id_factory=lambda: next(asset_ids))
    session, contents = direct_session(assets, reference_count)
    sessions = LocalPromptSessionStore(directory)
    sessions.create(session)
    gateway = DirectGateway(
        with_camera=with_camera,
        camera_owned=cookbook_version == "0.3.3",
    )
    service = PromptCompositionService(
        gateway=gateway,
        cookbooks=LocalPromptCookbookCatalog(COOKBOOK_ROOT),
        sessions=sessions,
        compositions=LocalPromptCompositionStore(directory),
        assets=assets,
    )
    service.configure(
        session.session_id,
        "minimax.h3.ref2v.direct",
        cookbook_version,
        (
            CookbookBinding(
                "references",
                tuple(reference.reference_id for reference in session.references),
            ),
        ),
    )
    return service, gateway, contents


class DirectRef2VCompositionTest(unittest.TestCase):
    def test_camera_owned_mono_writer_uses_landmarks_and_code_inserts_camera(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, _ = configured_service(
                directory,
                2,
                cookbook_version="0.3.3",
            )
            service.generate("direct-session", CompositionStage.BEAT_SHEET)
            service.approve("direct-session", CompositionStage.BEAT_SHEET)

            composition = service.generate(
                "direct-session",
                CompositionStage.FINAL_PROMPT,
            )

            request = gateway.requests[-1]
            self.assertNotIn('"camera_directives"', request.user_prompt)
            self.assertIn('"camera_landmarks_ms": [', request.user_prompt)
            self.assertIn("8000", request.user_prompt)
            self.assertNotIn("[[camera:", request.system_prompt + request.user_prompt)
            final = composition.final_prompt.active_revision
            self.assertIn(
                "At 00:08.000, The camera pushes in with small amplitude at slow "
                "speed toward the parcel held by the recipient. The recipient",
                final.content,
            )
            self.assertNotIn("[[camera:", final.content)

            revised = service.revise(
                "direct-session",
                CompositionStage.FINAL_PROMPT,
                "Shorten only the soundscape.",
            )
            revision_request = gateway.requests[-1]
            self.assertNotIn("[[camera:", revision_request.user_prompt)
            self.assertNotIn("The camera pushes", revision_request.user_prompt)
            self.assertEqual(
                revised.final_prompt.active_revision.content.count(
                    "The camera pushes in with small amplitude at slow speed "
                    "toward the parcel held by the recipient."
                ),
                1,
            )

    def test_compact_recipe_keeps_supervision_out_of_the_writer_request(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _, _ = configured_service(
                directory,
                2,
                cookbook_version="0.3.2",
            )
            gateway = ArbitrationGateway()
            service.gateway = gateway
            service.generate("direct-session", CompositionStage.BEAT_SHEET)
            service.approve("direct-session", CompositionStage.BEAT_SHEET)

            service.generate("direct-session", CompositionStage.FINAL_PROMPT)

            writer_request = gateway.requests[-1]
            self.assertEqual(writer_request.operation_id, "final_prompt.generate")
            self.assertIn('"beat_id": "handoff"', writer_request.user_prompt)
            self.assertIn('"derived_timing"', writer_request.user_prompt)
            self.assertNotIn('"risks"', writer_request.user_prompt)
            self.assertNotIn('"technical_adjustments"', writer_request.user_prompt)
            self.assertNotIn("The fur state is ambiguous", writer_request.user_prompt)

    def test_v3_reconciles_risks_against_native_images_and_keeps_v2_as_witness(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _, image_contents = configured_service(
                directory,
                2,
                cookbook_version="0.3.0",
            )
            gateway = ArbitrationGateway()
            service.gateway = gateway
            service.generate("direct-session", CompositionStage.BEAT_SHEET)

            events = list(service.stream_reconcile_action_plan(
                "direct-session",
                {"risk_1": gateway.decision},
                "Preserve every unaffected timing and reference boundary.",
            ))

            request = gateway.requests[-1]
            self.assertEqual(request.operation_id, "action_plan.reconcile")
            self.assertEqual(
                tuple(image.content for image in request.images),
                image_contents,
            )
            self.assertIn('"risk_id": "risk_1"', request.user_prompt)
            self.assertIn("<Picture 1> = <Image 1>", request.user_prompt)
            composition = events[-1].composition
            self.assertIsNotNone(composition)
            active = composition.beat_sheet.active_revision
            self.assertIs(active.origin, RevisionOrigin.REWRITE)
            revised = json.loads(active.content)
            self.assertEqual(revised["risks"][0]["resolution"], gateway.decision)
            self.assertIsNone(revised["risks"][1]["resolution"])
            self.assertIn("slightly damp", revised["beats"][0]["primary_action"])

        with tempfile.TemporaryDirectory() as directory:
            service, _, _ = configured_service(
                directory,
                2,
                cookbook_version="0.2.0",
            )
            service.gateway = ArbitrationGateway()
            service.generate("direct-session", CompositionStage.BEAT_SHEET)
            with self.assertRaisesRegex(ValueError, "does not support plan arbitration"):
                list(service.stream_reconcile_action_plan(
                    "direct-session",
                    {"risk_1": ArbitrationGateway.decision},
                ))

    def test_recovers_only_unambiguous_camera_placeholder_layouts(self):
        for camera_layout in ("extra_period", "inline_field"):
            with self.subTest(camera_layout=camera_layout), tempfile.TemporaryDirectory() as directory:
                service, _, _ = configured_service(
                    directory,
                    2,
                    cookbook_version="0.2.0",
                )
                service.gateway = DirectGateway(camera_layout=camera_layout)
                service.generate("direct-session", CompositionStage.BEAT_SHEET)
                service.approve("direct-session", CompositionStage.BEAT_SHEET)

                composition = service.generate(
                    "direct-session",
                    CompositionStage.FINAL_PROMPT,
                )

                final = composition.final_prompt.active_revision.content
                self.assertNotIn("[[camera:", final)
                self.assertEqual(final.count("The camera pushes in"), 1)

        with tempfile.TemporaryDirectory() as directory:
            service, _, _ = configured_service(
                directory,
                2,
                cookbook_version="0.2.0",
            )
            service.gateway = DirectGateway(camera_layout="embedded_prose")
            service.generate("direct-session", CompositionStage.BEAT_SHEET)
            service.approve("direct-session", CompositionStage.BEAT_SHEET)
            with self.assertRaisesRegex(ValueError, "camera placeholder"):
                service.generate("direct-session", CompositionStage.FINAL_PROMPT)

    def test_v2_derives_final_timing_without_persisting_redundant_clocks(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, _ = configured_service(
                directory,
                2,
                cookbook_version="0.2.0",
            )

            composition = service.generate(
                "direct-session",
                CompositionStage.BEAT_SHEET,
            )
            plan_request = gateway.requests[-1]
            self.assertIn('"final_hold_ms"', plan_request.user_prompt)
            plan_content = composition.beat_sheet.active_revision.content
            plan_value = json.loads(plan_content)
            self.assertNotIn("duration_seconds", plan_value)
            self.assertNotIn("start_ms", plan_value["final_state"])
            self.assertEqual(plan_value["final_state"]["final_hold_ms"], 1500)
            self.assertNotIn("derived_timing", plan_value)

            service.approve("direct-session", CompositionStage.BEAT_SHEET)
            composition = service.generate(
                "direct-session",
                CompositionStage.FINAL_PROMPT,
            )
            writer_request = gateway.requests[-1]
            self.assertEqual(writer_request.images, ())
            self.assertIn('"final_state_start_ms": 8000', writer_request.user_prompt)
            self.assertIn('"duration_ms": 9500', writer_request.user_prompt)
            self.assertIn('"duration_seconds": 9.5', writer_request.user_prompt)
            self.assertIn(
                "one continuous 9.5-second shot",
                composition.final_prompt.active_revision.content,
            )
            invalid_landmark = composition.final_prompt.active_revision.content.replace(
                "At 00:08.000,",
                "At 00:07.500,",
                1,
            )
            with self.assertRaisesRegex(ValueError, "final-state landmark"):
                service.edit(
                    "direct-session",
                    CompositionStage.FINAL_PROMPT,
                    invalid_landmark,
                )

    def test_runs_approved_brief_to_multimodal_plan_and_text_only_writer(self):
        for reference_count in (1, 2, 3):
            with self.subTest(reference_count=reference_count), tempfile.TemporaryDirectory() as directory:
                service, gateway, image_contents = configured_service(
                    directory,
                    reference_count,
                )

                composition = service.generate(
                    "direct-session",
                    CompositionStage.BEAT_SHEET,
                )
                plan_request = gateway.requests[-1]
                self.assertEqual(plan_request.operation_id, "action_plan.generate")
                self.assertEqual(
                    tuple(image.content for image in plan_request.images),
                    image_contents,
                )
                self.assertEqual(
                    tuple(
                        re.match(r"<Picture \d+>", image.label).group(0)
                        for image in plan_request.images
                    ),
                    tuple(f"<Picture {index}>" for index in range(1, reference_count + 1)),
                )
                for index in range(1, reference_count + 1):
                    self.assertIn(
                        f"<Picture {index}> = <Image {index}>",
                        plan_request.user_prompt,
                    )

                with self.assertRaisesRegex(ValueError, "approve a current beat_sheet"):
                    service.generate("direct-session", CompositionStage.FINAL_PROMPT)

                composition = service.approve(
                    "direct-session",
                    CompositionStage.BEAT_SHEET,
                )
                composition = service.generate(
                    "direct-session",
                    CompositionStage.FINAL_PROMPT,
                )
                writer_request = gateway.requests[-1]
                self.assertEqual(writer_request.operation_id, "final_prompt.generate")
                self.assertEqual(writer_request.images, ())
                self.assertIn('"beat_id": "handoff"', writer_request.user_prompt)

                final = composition.final_prompt.active_revision
                self.assertIsNotNone(final)
                self.assertTrue(final.compiler_context.startswith(DIRECT_CONTEXT_MARKER))
                self.assertNotIn("[[camera:", final.content)
                self.assertEqual(final.content.count("The camera pushes in"), 1)
                picture_numbers = [
                    int(value)
                    for value in re.findall(r"<Picture\s+(\d+)>", final.content)
                ]
                self.assertEqual(
                    picture_numbers,
                    list(range(1, reference_count + 1)),
                )
                self.assertNotIn("<Image ", final.content)
                self.assertNotIn("<Subject ", final.content)

                composition = service.approve(
                    "direct-session",
                    CompositionStage.FINAL_PROMPT,
                )
                statuses = {item.stage: item for item in service.status(composition)}
                self.assertTrue(statuses[CompositionStage.BEAT_SHEET].complete)
                self.assertTrue(statuses[CompositionStage.FINAL_PROMPT].complete)

    def test_final_prompt_cannot_drop_a_bound_dynamic_header(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _, _ = configured_service(directory, 3)
            service.generate("direct-session", CompositionStage.BEAT_SHEET)
            service.approve("direct-session", CompositionStage.BEAT_SHEET)
            composition = service.generate(
                "direct-session",
                CompositionStage.FINAL_PROMPT,
            )
            final = composition.final_prompt.active_revision.content
            changed = "\n".join(
                line for line in final.splitlines() if "<Picture 3>" not in line
            )

            with self.assertRaisesRegex(
                ValueError,
                "required direct picture label.*<Picture 3>",
            ):
                service.edit(
                    "direct-session",
                    CompositionStage.FINAL_PROMPT,
                    changed,
                )

    def test_action_plan_rejects_an_unbound_picture_label(self):
        class UnboundPictureGateway(DirectGateway):
            def complete(self, request: CompletionRequest) -> CompletionResult:
                result = super().complete(request)
                plan = json.loads(result.content)
                plan["scene_setup"] += " <Picture 2> supplies the room."
                return CompletionResult(
                    model_id=result.model_id,
                    content=json.dumps(plan),
                    call_id=result.call_id,
                )

        with tempfile.TemporaryDirectory() as directory:
            service, _, _ = configured_service(directory, 1)
            gateway = UnboundPictureGateway()
            service.gateway = gateway

            with self.assertRaisesRegex(
                ValueError,
                "unknown or unbound direct picture.*<Picture 2>",
            ):
                service.generate("direct-session", CompositionStage.BEAT_SHEET)

    def test_zero_camera_plan_compiles_and_hides_context_during_streaming(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, _ = configured_service(
                directory,
                2,
                with_camera=False,
            )
            service.generate("direct-session", CompositionStage.BEAT_SHEET)
            service.approve("direct-session", CompositionStage.BEAT_SHEET)

            events = list(
                service.stream_generate(
                    "direct-session",
                    CompositionStage.FINAL_PROMPT,
                )
            )

            self.assertEqual(gateway.requests[-1].images, ())
            self.assertTrue(events[-1].composition is not None)
            self.assertTrue(
                events[-1].composition.final_prompt.active_revision.compiler_context.startswith(
                    DIRECT_CONTEXT_MARKER
                )
            )
            self.assertNotIn(
                DIRECT_CONTEXT_MARKER,
                "".join(event.text for event in events),
            )
            self.assertNotIn("[[camera:", events[-1].text)

    def test_single_newline_manual_edit_can_be_revised_by_the_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, _ = configured_service(directory, 2)
            service.generate("direct-session", CompositionStage.BEAT_SHEET)
            service.approve("direct-session", CompositionStage.BEAT_SHEET)
            composition = service.generate(
                "direct-session",
                CompositionStage.FINAL_PROMPT,
            )
            compact = composition.final_prompt.active_revision.content.replace(
                "\n\nShot 1:",
                "\nShot 1:",
            )
            service.edit(
                "direct-session",
                CompositionStage.FINAL_PROMPT,
                compact,
            )

            revised = service.revise(
                "direct-session",
                CompositionStage.FINAL_PROMPT,
                "Clarify the shared grip without changing the plan.",
            )

            self.assertEqual(gateway.requests[-1].operation_id, "final_prompt.revise")
            final = revised.final_prompt.active_revision
            self.assertIs(final.origin, RevisionOrigin.REWRITE)
            self.assertNotIn("[[camera:", final.content)
            self.assertTrue(final.compiler_context.startswith(DIRECT_CONTEXT_MARKER))


if __name__ == "__main__":
    unittest.main()
