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
PNG = b"\x89PNG\r\n\x1a\nmultishot-reference-"
COOKBOOK_ID = "minimax.h3.ref2v.direct.multishot"
MULTISHOT_CONTEXT_MARKER = "__PANELFORGE_DIRECT_REF2V_MULTISHOT_CONTEXT_V1__:"


def multishot_plan(
    *,
    cameras: tuple[int, ...] = (1, 3),
    resolved: bool = True,
    reference_count: int = 2,
) -> dict:
    shots = []
    for number, duration in enumerate((3000, 4000, 3500), 1):
        camera = None
        if number in cameras:
            camera = {
                "motion": "push.in" if number == 1 else "pan.right",
                "amplitude": "small",
                "speed": "slow",
                "target_clause": (
                    "toward the parcel between both participants"
                    if number == 1
                    else "to reveal the recipient holding the parcel"
                ),
                "visible_change": "The parcel and recipient become more prominent.",
            }
        shots.append({
            "shot_id": f"shot_{number}",
            "duration_ms": duration,
            "purpose": f"Advance the handoff through visual step {number}.",
            "new_information": f"The handoff reaches visible state {number}.",
            "entry_state": f"The participants enter state {number} coherently.",
            "primary_action": (
                "The courier approaches with the parcel."
                if number == 1
                else "Both people share the parcel's weight."
                if number == 2
                else "The courier releases the parcel to the recipient."
            ),
            "observable_end_state": f"The sequence visibly completes step {number}.",
            "active_picture_labels": [
                f"<Picture {index}>" for index in range(1, reference_count + 1)
            ],
            "camera": camera,
        })
    return {
        "scene_setup": "A stable warm room contains the same courier, recipient, and parcel.",
        "continuity_invariants": [
            "Room geometry, identities, wardrobe, lighting, and parcel remain stable."
        ],
        "shots": shots,
        "final_state": {
            "description": "The recipient holds the parcel while both people maintain eye contact.",
            "final_hold_ms": 1500,
        },
        "risks": [{
            "risk_id": "risk_1",
            "category": "spatial",
            "description": "The parcel path needs a stable screen direction.",
            "recommendation": "Keep the parcel moving toward frame right.",
            "resolution": (
                "Keep the parcel moving toward frame right."
                if resolved else None
            ),
        }],
        "technical_adjustments": [],
        "overall_soundscape": "Quiet room tone, footsteps, and soft parcel handling.",
        "non_diegetic_music": "N/A",
    }


def writer_document(*, cameras: tuple[int, ...] = (1, 3)) -> str:
    camera_1 = "[[camera:camera_1]] " if 1 in cameras else ""
    camera_2 = "[[camera:camera_2]] " if 2 in cameras else ""
    camera_3 = "[[camera:camera_3]] " if 3 in cameras else ""
    return (
        "scene_setup:\n"
        "The same warm room, courier, recipient, parcel, lighting, and screen direction remain stable.\n"
        "shot_1:\n"
        f"{camera_1}The courier approaches while supporting the parcel with both hands.\n"
        "shot_2:\n"
        f"{camera_2}After the hard cut, both people share the parcel's weight before release.\n"
        "shot_3:\n"
        f"{camera_3}After the hard cut, the courier releases it and the recipient holds it.\n"
        "The final state holds with natural breathing and balance.\n"
        "overall_soundscape:\n"
        "Quiet room tone, measured footsteps, breathing, and soft parcel handling.\n"
        "non_diegetic_music:\n"
        "N/A"
    )


class MultiShotGateway:
    def __init__(
        self,
        *,
        cameras: tuple[int, ...] = (1, 3),
        reference_count: int = 2,
    ) -> None:
        self.cameras = cameras
        self.reference_count = reference_count
        self.requests: list[CompletionRequest] = []

    def _content(self, request: CompletionRequest) -> str:
        if request.operation_id == "action_plan.generate":
            return json.dumps(multishot_plan(
                cameras=self.cameras,
                resolved=False,
                reference_count=self.reference_count,
            ))
        if request.operation_id == "action_plan.reconcile":
            return json.dumps(multishot_plan(
                cameras=self.cameras,
                resolved=True,
                reference_count=self.reference_count,
            ))
        return writer_document(cameras=self.cameras)

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.requests.append(request)
        return CompletionResult(
            model_id=request.model_id,
            content=self._content(request),
            call_id=f"call-{len(self.requests)}",
        )

    def stream(self, request: CompletionRequest):
        self.requests.append(request)
        content = self._content(request)
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


class MalformedWriterGateway(MultiShotGateway):
    def __init__(self, replacement) -> None:
        super().__init__()
        self.replacement = replacement

    def _content(self, request: CompletionRequest) -> str:
        content = super()._content(request)
        if request.operation_id.startswith("final_prompt."):
            return self.replacement(content)
        return content


def direct_session(
    assets: LocalAssetStore,
    reference_count: int = 2,
) -> tuple[PromptLabSession, tuple[bytes, ...]]:
    definitions = (
        ("first_frame", ReferenceUse.FIRST_FRAME, "Opening frame"),
        ("subject_reference", ReferenceUse.SUBJECT, "Identity reference"),
        ("environment_reference", ReferenceUse.ENVIRONMENT, "Room reference"),
    )[:reference_count]
    references = []
    contents = []
    for index, (role, use, label) in enumerate(definitions, 1):
        content = PNG + str(index).encode("ascii")
        asset = assets.create(content, "image/png")
        contents.append(content)
        references.append(PromptReference(
            reference_id=f"reference-{index}",
            asset_id=asset.asset_id,
            role=role,
            label=label,
            uses=(use,),
        ))
    session = PromptLabSession(
        session_id="multishot-session",
        model_id="vision-model",
        profile_id="minimax.h3.ref2v.direct",
        profile_version="0.1.0",
        references=tuple(references),
        session_mode=PromptSessionMode.DIRECT_MULTIMODAL,
    )
    session = session.add_brief_revision(BriefRevision(
        revision_id="brief-1",
        source_text="Le coursier remet le colis en trois plans.",
        content=(
            "Trois plans reliés par des coupes franches montrent une remise de "
            "colis cohérente dans le même décor."
        ),
        creative_freedom=35,
        origin=RevisionOrigin.MODEL,
        references=tuple(BriefReferenceSnapshot(
            reference_id=reference.reference_id,
            analysis_revision_id=None,
            uses=reference.uses,
            evidence_policy=reference.evidence_policy,
        ) for reference in references),
    )).approve_brief()
    return session, tuple(contents)


def configured_service(
    directory: str,
    *,
    cameras: tuple[int, ...] = (1, 3),
    reference_count: int = 2,
):
    asset_ids = iter(("asset-1", "asset-2", "asset-3"))
    assets = LocalAssetStore(directory, id_factory=lambda: next(asset_ids))
    session, contents = direct_session(assets, reference_count)
    sessions = LocalPromptSessionStore(directory)
    sessions.create(session)
    gateway = MultiShotGateway(
        cameras=cameras,
        reference_count=reference_count,
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
        COOKBOOK_ID,
        "0.1.0",
        (CookbookBinding(
            "references",
            tuple(f"reference-{index}" for index in range(1, reference_count + 1)),
        ),),
    )
    return service, gateway, contents


class DirectRef2VMultiShotCompositionTest(unittest.TestCase):
    def test_one_to_three_reference_boundary_keeps_mapping_and_writer_separate(self):
        for reference_count in (1, 3):
            with self.subTest(reference_count=reference_count), tempfile.TemporaryDirectory() as directory:
                service, gateway, contents = configured_service(
                    directory,
                    reference_count=reference_count,
                )
                service.generate("multishot-session", CompositionStage.BEAT_SHEET)
                plan_request = gateway.requests[-1]
                self.assertEqual(
                    tuple(image.content for image in plan_request.images),
                    contents,
                )
                for index in range(1, reference_count + 1):
                    self.assertIn(
                        f"<Picture {index}> = <Image {index}>",
                        plan_request.user_prompt,
                    )
                service.approve("multishot-session", CompositionStage.BEAT_SHEET)
                composition = service.generate(
                    "multishot-session", CompositionStage.FINAL_PROMPT
                )
                self.assertEqual(gateway.requests[-1].images, ())
                final = composition.final_prompt.active_revision.content
                self.assertEqual(
                    sorted(int(value) for value in re.findall(r"<Picture (\d+)>", final)),
                    list(range(1, reference_count + 1)),
                )

    def test_plan_uses_native_images_and_projects_derived_writer_timeline(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, contents = configured_service(directory)

            composition = service.generate(
                "multishot-session", CompositionStage.BEAT_SHEET
            )

            request = gateway.requests[-1]
            self.assertEqual(request.operation_id, "action_plan.generate")
            self.assertEqual(tuple(image.content for image in request.images), contents)
            self.assertIn('"shot_id"', request.user_prompt)
            self.assertIn('"duration_ms"', request.user_prompt)
            plan = json.loads(composition.beat_sheet.active_revision.content)
            self.assertEqual([shot["shot_id"] for shot in plan["shots"]], [
                "shot_1", "shot_2", "shot_3",
            ])

            service.approve("multishot-session", CompositionStage.BEAT_SHEET)
            service.generate("multishot-session", CompositionStage.FINAL_PROMPT)
            writer = gateway.requests[-1]
            self.assertEqual(writer.operation_id, "final_prompt.generate")
            self.assertEqual(writer.images, ())
            self.assertIn('"heading": "[Shot 1]"', writer.user_prompt)
            self.assertIn('"heading": "[Shot 2] At 00:03.000,"', writer.user_prompt)
            self.assertIn('"heading": "[Shot 3] At 00:07.000,"', writer.user_prompt)
            self.assertIn('"duration_ms": 12000', writer.user_prompt)
            self.assertNotIn('"risks"', writer.user_prompt)
            final = service.compositions.get(
                "multishot-session"
            ).final_prompt.active_revision
            self.assertTrue(final.compiler_context.startswith(MULTISHOT_CONTEXT_MARKER))
            self.assertIn("[Shot 1] ", final.content)
            self.assertIn("[Shot 2] At 00:03.000, ", final.content)
            self.assertIn("[Shot 3] At 00:07.000, ", final.content)
            self.assertNotIn("[[camera:", final.content)
            self.assertEqual(final.content.count("The camera pushes in"), 1)
            self.assertEqual(final.content.count("The camera pans right"), 1)
            self.assertEqual(final.content.count("<Picture 1>"), 1)
            self.assertEqual(final.content.count("<Picture 2>"), 1)

    def test_arbitration_reuses_native_images_and_preserves_risk_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, contents = configured_service(directory)
            service.generate("multishot-session", CompositionStage.BEAT_SHEET)

            events = list(service.stream_reconcile_action_plan(
                "multishot-session",
                {"risk_1": "Keep the parcel moving toward frame right."},
                "Keep all three shot durations unchanged.",
            ))

            request = gateway.requests[-1]
            self.assertEqual(request.operation_id, "action_plan.reconcile")
            self.assertEqual(tuple(image.content for image in request.images), contents)
            self.assertIn('"risk_id": "risk_1"', request.user_prompt)
            active = events[-1].composition.beat_sheet.active_revision
            self.assertIs(active.origin, RevisionOrigin.REWRITE)
            self.assertEqual(
                json.loads(active.content)["risks"][0]["resolution"],
                "Keep the parcel moving toward frame right.",
            )

    def test_zero_camera_plan_compiles_without_placeholders(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, _ = configured_service(directory, cameras=())
            service.generate("multishot-session", CompositionStage.BEAT_SHEET)
            service.approve("multishot-session", CompositionStage.BEAT_SHEET)

            composition = service.generate(
                "multishot-session", CompositionStage.FINAL_PROMPT
            )

            self.assertEqual(gateway.requests[-1].images, ())
            final = composition.final_prompt.active_revision
            self.assertTrue(final.compiler_context.startswith(MULTISHOT_CONTEXT_MARKER))
            self.assertNotIn("[[camera:", final.content)
            self.assertIn("[Shot 2] At 00:03.000,", final.content)

    def test_rejects_writer_owned_heading_and_unknown_camera_placeholder(self):
        cases = (
            (
                "heading",
                lambda value: value.replace(
                    "shot_2:\n",
                    "shot_2:\n[Shot 2] At 00:04.000, ",
                    1,
                ),
                "compiled shot headings",
            ),
            (
                "placeholder",
                lambda value: value.replace(
                    "[[camera:camera_1]]",
                    "[[camera:camera_2]]",
                    1,
                ),
                "unknown multi-shot camera placeholder|camera placeholder",
            ),
        )
        for name, replacement, error in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                service, _, _ = configured_service(directory)
                service.gateway = MalformedWriterGateway(replacement)
                service.generate("multishot-session", CompositionStage.BEAT_SHEET)
                service.approve("multishot-session", CompositionStage.BEAT_SHEET)

                with self.assertRaisesRegex(ValueError, error):
                    service.generate(
                        "multishot-session", CompositionStage.FINAL_PROMPT
                    )

    def test_manual_edit_and_writer_revision_round_trip_the_hidden_context(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, _ = configured_service(directory)
            service.generate("multishot-session", CompositionStage.BEAT_SHEET)
            service.approve("multishot-session", CompositionStage.BEAT_SHEET)
            composition = service.generate(
                "multishot-session", CompositionStage.FINAL_PROMPT
            )
            original = composition.final_prompt.active_revision
            edited_content = original.content.replace(
                "measured footsteps",
                "soft measured footsteps",
                1,
            )

            edited = service.edit(
                "multishot-session",
                CompositionStage.FINAL_PROMPT,
                edited_content,
            ).final_prompt.active_revision
            self.assertEqual(edited.compiler_context, original.compiler_context)

            revised = service.revise(
                "multishot-session",
                CompositionStage.FINAL_PROMPT,
                "Clarify the shared grip without changing cuts or camera.",
            ).final_prompt.active_revision

            request = gateway.requests[-1]
            self.assertEqual(request.operation_id, "final_prompt.revise")
            self.assertEqual(request.images, ())
            self.assertIn("scene_setup:", request.user_prompt)
            self.assertIn("shot_2:", request.user_prompt)
            self.assertIn("[[camera:camera_1]]", request.user_prompt)
            self.assertIn("[[camera:camera_3]]", request.user_prompt)
            self.assertEqual(revised.compiler_context, original.compiler_context)
            self.assertNotIn("[[camera:", revised.content)

    def test_mono_plan_recipe_remains_a_distinct_contract(self):
        catalog = LocalPromptCookbookCatalog(COOKBOOK_ROOT)
        mono = catalog.get("minimax.h3.ref2v.direct", "0.3.2")
        multi = catalog.get(COOKBOOK_ID, "0.1.0")

        self.assertEqual(mono.output_contract, "minimax.h3.ref2v.direct_supervised_h3_v2")
        self.assertEqual(mono.writer_projection, "compact_v1")
        self.assertNotEqual(mono.output_contract, multi.output_contract)
        self.assertNotEqual(mono.reference.cookbook_id, multi.reference.cookbook_id)


if __name__ == "__main__":
    unittest.main()
