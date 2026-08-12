import json
import tempfile
import unittest
from pathlib import Path

from panelforge.application import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    PromptCompositionService,
    StreamEventKind,
    StreamPhase,
    lint_i2v_prompt,
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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COOKBOOK_ROOT = PROJECT_ROOT / "prompt_cookbooks"
PNG = b"\x89PNG\r\n\x1a\ndirect-i2v-first-frame"
I2VA_HEADER = (
    "For the target video, at 0.00 seconds into the target video, "
    "<Picture 1> (from [Shot 1]) is fully referenced."
)


def action_plan(*, with_camera: bool = True, resolved: bool = False) -> dict:
    return {
        "scene_setup": (
            "The same indoor court, late-afternoon light, player, blue uniform, "
            "and ball remain spatially stable."
        ),
        "continuity_invariants": [
            "The player's identity, uniform, court geometry, light, and ball persist."
        ],
        "beats": [
            {
                "beat_id": "kick",
                "start_ms": 0,
                "end_ms": 8000,
                "primary_action": "The player takes one controlled shot at the goal.",
                "participants": ["player", "ball"],
                "observable_end_state": "The ball reaches the net after the kick.",
                "steps": [
                    {
                        "step_id": "wind_up",
                        "start_ms": 0,
                        "end_ms": 4000,
                        "action": "The player shifts weight and swings the kicking leg.",
                        "continuity_after": "The planted foot remains beside the ball.",
                    },
                    {
                        "step_id": "strike",
                        "start_ms": 4000,
                        "end_ms": 8000,
                        "action": "The foot strikes the ball and follows through.",
                        "continuity_after": "The ball reaches the net and the player balances.",
                    },
                ],
            }
        ],
        "final_state": {
            "description": "The player regains balance while the net settles.",
            "final_hold_ms": 1500,
        },
        "camera_directives": (
            [
                {
                    "directive_id": "camera_1",
                    "start_ms": 4000,
                    "end_ms": 8000,
                    "motion": "pan.right",
                    "amplitude": "small",
                    "speed": "fast",
                    "target_clause": "following the ball",
                    "visible_change": "The ball remains framed through the strike.",
                }
            ]
            if with_camera
            else []
        ),
        "risks": [
            {
                "risk_id": "risk_1",
                "category": "spatial",
                "description": "The exact target corner is not visible in the opening frame.",
                "recommendation": "Keep the ball path inside the established court axis.",
                "resolution": (
                    "Keep the ball path on the established court axis."
                    if resolved
                    else None
                ),
            }
        ],
        "technical_adjustments": [],
        "overall_soundscape": "Indoor court ambience, footwork, impact, and net movement.",
        "non_diegetic_music": "N/A",
    }


def final_document(*, with_camera: bool = True, revised: bool = False) -> str:
    camera = (
        "At 00:04.000, [[camera:camera_1]] The ball accelerates toward the net.\n"
        if with_camera
        else "The ball accelerates toward the net.\n"
    )
    soundscape = (
        "Concise court ambience, one kick, and the net settling."
        if revised
        else "Court ambience, measured footwork, one kick, and the net settling."
    )
    return (
        "integrated_multimodal_description:\n"
        "[Shot 1] The target video is one continuous 12-second shot. The visible "
        "player, blue uniform, planted foot, ball, court geometry, and warm light "
        "begin exactly from the opening frame. The player transfers weight and "
        "swings the kicking leg without breaking the planted-foot contact.\n"
        f"{camera}"
        "At 00:08.000, the player regains balance while the net settles, with "
        "natural breathing and residual fabric motion through the final hold.\n"
        "overall_soundscape:\n"
        f"{soundscape}\n"
        "non_diegetic_music:\n"
        "N/A"
    )


class DirectI2VGateway:
    decision = "Keep the ball path on the established court axis."

    def __init__(self, *, with_camera: bool = True, picture_2: bool = False) -> None:
        self.with_camera = with_camera
        self.picture_2 = picture_2
        self.requests: list[CompletionRequest] = []

    def _content(self, request: CompletionRequest) -> str:
        if request.operation_id == "action_plan.generate":
            return json.dumps(action_plan(with_camera=self.with_camera))
        document = final_document(
            with_camera=self.with_camera,
            revised=request.operation_id == "final_prompt.revise",
        )
        if self.picture_2:
            document = document.replace(
                "The visible player",
                "The player from <Picture 2>",
                1,
            )
        return document

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.requests.append(request)
        return CompletionResult(
            model_id=request.model_id,
            content=self._content(request),
            call_id=f"call-{len(self.requests)}",
        )

    def stream(self, request: CompletionRequest):
        self.requests.append(request)
        content = (
            json.dumps(action_plan(with_camera=self.with_camera, resolved=True))
            if request.operation_id == "action_plan.reconcile"
            else self._content(request)
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


def direct_i2v_session(assets: LocalAssetStore) -> PromptLabSession:
    asset = assets.create(PNG, "image/png")
    reference = PromptReference(
        reference_id="reference-1",
        asset_id=asset.asset_id,
        role="first_frame",
        label="kick.png",
        uses=(ReferenceUse.FIRST_FRAME,),
    )
    session = PromptLabSession(
        session_id="direct-i2v-session",
        model_id="vision-model",
        profile_id="minimax.h3.i2v.direct",
        profile_version="0.1.0",
        references=(reference,),
        session_mode=PromptSessionMode.DIRECT_MULTIMODAL,
    )
    brief = BriefRevision(
        revision_id="brief-1",
        source_text="Le joueur tire au but puis retrouve son equilibre.",
        content=(
            "La premiere frame est l'etat initial exact. Le joueur effectue un tir "
            "continu, puis retrouve son equilibre dans le meme terrain."
        ),
        creative_freedom=35,
        origin=RevisionOrigin.MODEL,
        references=(
            BriefReferenceSnapshot(
                reference_id=reference.reference_id,
                analysis_revision_id=None,
                uses=reference.uses,
                evidence_policy=reference.evidence_policy,
            ),
        ),
    )
    return session.add_brief_revision(brief).approve_brief()


def configured_service(
    directory: str,
    *,
    with_camera: bool = True,
    picture_2: bool = False,
):
    assets = LocalAssetStore(directory, id_factory=lambda: "asset-1")
    session = direct_i2v_session(assets)
    sessions = LocalPromptSessionStore(directory)
    sessions.create(session)
    gateway = DirectI2VGateway(
        with_camera=with_camera,
        picture_2=picture_2,
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
        "minimax.h3.i2v.direct",
        "0.1.0",
        (CookbookBinding("first_frame", ("reference-1",)),),
    )
    return service, gateway


class DirectI2VCompositionTest(unittest.TestCase):
    def test_direct_cookbook_rejects_an_unbound_extra_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            asset_ids = iter(("asset-1", "asset-2"))
            assets = LocalAssetStore(directory, id_factory=lambda: next(asset_ids))
            first_asset = assets.create(PNG, "image/png")
            extra_asset = assets.create(PNG + b"-extra", "image/png")
            first = PromptReference(
                reference_id="reference-1",
                asset_id=first_asset.asset_id,
                role="first_frame",
                label="first.png",
                uses=(ReferenceUse.FIRST_FRAME,),
            )
            extra = PromptReference(
                reference_id="reference-2",
                asset_id=extra_asset.asset_id,
                role="subject_reference",
                label="extra.png",
                uses=(ReferenceUse.SUBJECT,),
            )
            session = PromptLabSession(
                session_id="direct-i2v-extra",
                model_id="vision-model",
                profile_id="minimax.h3.i2v.direct",
                profile_version="0.1.0",
                references=(first, extra),
                session_mode=PromptSessionMode.DIRECT_MULTIMODAL,
            )
            session = session.add_brief_revision(
                BriefRevision(
                    revision_id="brief-extra",
                    source_text="Anime la premiere frame.",
                    content="La premiere frame reste le point de depart exact.",
                    creative_freedom=35,
                    origin=RevisionOrigin.MODEL,
                    references=tuple(
                        BriefReferenceSnapshot(
                            reference_id=reference.reference_id,
                            analysis_revision_id=None,
                            uses=reference.uses,
                            evidence_policy=reference.evidence_policy,
                        )
                        for reference in (first, extra)
                    ),
                )
            ).approve_brief()
            sessions = LocalPromptSessionStore(directory)
            sessions.create(session)
            service = PromptCompositionService(
                gateway=DirectI2VGateway(),
                cookbooks=LocalPromptCookbookCatalog(COOKBOOK_ROOT),
                sessions=sessions,
                compositions=LocalPromptCompositionStore(directory),
                assets=assets,
            )

            with self.assertRaisesRegex(ValueError, "bind every reference"):
                service.configure(
                    session.session_id,
                    "minimax.h3.i2v.direct",
                    "0.1.0",
                    (CookbookBinding("first_frame", (first.reference_id,)),),
                )

    def test_runs_native_plan_then_text_writer_and_compiles_i2va(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = configured_service(directory)

            composition = service.generate(
                "direct-i2v-session",
                CompositionStage.BEAT_SHEET,
            )
            plan_request = gateway.requests[-1]
            self.assertEqual(plan_request.operation_id, "action_plan.generate")
            self.assertEqual(len(plan_request.images), 1)
            self.assertEqual(plan_request.images[0].content, PNG)
            self.assertIn("<Picture 1>", plan_request.images[0].label)
            self.assertIn("<Picture 1> = <Image 1>", plan_request.user_prompt)
            self.assertNotIn("duration_seconds", json.loads(
                composition.beat_sheet.active_revision.content
            ))

            service.approve("direct-i2v-session", CompositionStage.BEAT_SHEET)
            composition = service.generate(
                "direct-i2v-session",
                CompositionStage.FINAL_PROMPT,
            )
            writer_request = gateway.requests[-1]
            self.assertEqual(writer_request.operation_id, "final_prompt.generate")
            self.assertEqual(writer_request.images, ())
            self.assertIn('"duration_ms": 9500', writer_request.user_prompt)
            self.assertIn('"duration_seconds": 9.5', writer_request.user_prompt)
            self.assertNotIn('"risks"', writer_request.user_prompt)
            self.assertNotIn('"technical_adjustments"', writer_request.user_prompt)

            final = composition.final_prompt.active_revision
            self.assertTrue(final.content.startswith(I2VA_HEADER + "\n\n"))
            self.assertIn(
                "[Shot 1] The target video is one continuous 9.5-second shot.",
                final.content,
            )
            fields = (
                "integrated_multimodal_description:",
                "overall_soundscape:",
                "non_diegetic_music:",
            )
            self.assertEqual(tuple(final.content.count(field) for field in fields), (1, 1, 1))
            self.assertEqual(
                tuple(final.content.index(field) for field in fields),
                tuple(sorted(final.content.index(field) for field in fields)),
            )
            self.assertNotIn("[[camera:", final.content)
            self.assertEqual(
                final.content.count(
                    "The camera pans right with small amplitude at fast speed, "
                    "following the ball."
                ),
                1,
            )
            self.assertEqual(lint_i2v_prompt(final.content), ())
            self.assertIsNotNone(final.compiler_context)

    def test_accepts_a_plan_without_camera_directives(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = configured_service(directory, with_camera=False)
            service.generate("direct-i2v-session", CompositionStage.BEAT_SHEET)
            service.approve("direct-i2v-session", CompositionStage.BEAT_SHEET)

            composition = service.generate(
                "direct-i2v-session",
                CompositionStage.FINAL_PROMPT,
            )

            final = composition.final_prompt.active_revision
            self.assertEqual(gateway.requests[-1].images, ())
            self.assertNotIn("[[camera:", final.content)
            self.assertNotIn("The camera ", final.content)
            self.assertEqual(lint_i2v_prompt(final.content), ())
            self.assertIsNotNone(final.compiler_context)

    def test_reconciles_plan_risk_against_the_native_first_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = configured_service(directory)
            service.generate("direct-i2v-session", CompositionStage.BEAT_SHEET)

            events = list(
                service.stream_reconcile_action_plan(
                    "direct-i2v-session",
                    {"risk_1": gateway.decision},
                    "Preserve every unaffected timing and opening-frame fact.",
                )
            )

            request = gateway.requests[-1]
            self.assertEqual(request.operation_id, "action_plan.reconcile")
            self.assertEqual(len(request.images), 1)
            self.assertEqual(request.images[0].content, PNG)
            self.assertIn("<Picture 1> = <Image 1>", request.user_prompt)
            self.assertIn(gateway.decision, request.user_prompt)
            composition = events[-1].composition
            self.assertIsNotNone(composition)
            plan = json.loads(composition.beat_sheet.active_revision.content)
            self.assertEqual(plan["risks"][0]["resolution"], gateway.decision)
            self.assertIs(
                composition.beat_sheet.active_revision.origin,
                RevisionOrigin.REWRITE,
            )

    def test_manual_edit_and_revision_preserve_plan_compiler_context(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway = configured_service(directory)
            service.generate("direct-i2v-session", CompositionStage.BEAT_SHEET)
            service.approve("direct-i2v-session", CompositionStage.BEAT_SHEET)
            generated = service.generate(
                "direct-i2v-session",
                CompositionStage.FINAL_PROMPT,
            )
            context = generated.final_prompt.active_revision.compiler_context

            edited = service.edit(
                "direct-i2v-session",
                CompositionStage.FINAL_PROMPT,
                generated.final_prompt.active_revision.content.replace(
                    "Court ambience, measured footwork",
                    "Concise court ambience, measured footwork",
                ),
            )
            self.assertEqual(
                edited.final_prompt.active_revision.compiler_context,
                context,
            )

            revised = service.revise(
                "direct-i2v-session",
                CompositionStage.FINAL_PROMPT,
                "Shorten only the soundscape.",
            )
            request = gateway.requests[-1]
            self.assertEqual(request.operation_id, "final_prompt.revise")
            self.assertEqual(request.images, ())
            self.assertIn("[[camera:camera_1]]", request.user_prompt)
            self.assertNotIn(I2VA_HEADER, request.user_prompt)
            self.assertIn('"duration_ms": 9500', request.user_prompt)
            self.assertEqual(
                revised.final_prompt.active_revision.compiler_context,
                context,
            )
            self.assertIn(
                "Concise court ambience, one kick",
                revised.final_prompt.active_revision.content,
            )

    def test_rejects_picture_two_without_persisting_the_writer_result(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _ = configured_service(directory, picture_2=True)
            service.generate("direct-i2v-session", CompositionStage.BEAT_SHEET)
            service.approve("direct-i2v-session", CompositionStage.BEAT_SHEET)

            with self.assertRaisesRegex(ValueError, "Picture 1|Picture 2|label"):
                service.generate(
                    "direct-i2v-session",
                    CompositionStage.FINAL_PROMPT,
                )

            self.assertIsNone(
                service.get("direct-i2v-session").final_prompt.active_revision
            )

    def test_legacy_i2va_cookbook_remains_a_final_only_witness(self):
        catalog = LocalPromptCookbookCatalog(COOKBOOK_ROOT)
        legacy = catalog.get("minimax.h3.i2v.simple", "0.3.0")
        direct = catalog.get("minimax.h3.i2v.direct", "0.1.0")

        self.assertEqual(legacy.output_contract, "minimax.h3.i2va.canonical_v1")
        self.assertEqual(legacy.stages, ("final_prompt",))
        self.assertEqual(
            direct.output_contract,
            "minimax.h3.i2va.direct_supervised_h3_v1",
        )
        self.assertEqual(direct.stages, ("beat_sheet", "final_prompt"))


if __name__ == "__main__":
    unittest.main()
