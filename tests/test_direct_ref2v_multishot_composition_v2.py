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
COOKBOOK_ID = "minimax.h3.ref2v.direct.multishot"
COOKBOOK_VERSION = "0.2.0"
CONTEXT_MARKER_V2 = "__PANELFORGE_DIRECT_REF2V_MULTISHOT_CONTEXT_V2__:"
PNG = b"\x89PNG\r\n\x1a\nflexible-multishot-reference-"
RISK_DECISION = "Keep the runner moving toward screen right across every cut."


def _camera(number: int) -> dict[str, object]:
    return {
        "motion": "push.in",
        "amplitude": "small",
        "speed": "slow",
        "target_clause": f"toward the runner entering visual phase {number}",
        "visible_change": f"The runner becomes more prominent in phase {number}.",
    }


def _continuity(number: int) -> dict[str, str]:
    return {
        "spatial_anchor": "The blue crate remains at frame left.",
        "subject_position": "The runner resumes near the center of the wet lane.",
        "travel_direction": "The runner continues toward screen right.",
        "motion_phase": f"Phase {number} resumes the same forward stride.",
    }


def flexible_plan(
    shot_count: int,
    *,
    cameras: tuple[int, ...] = (),
    resolved: bool = True,
    reference_count: int = 2,
) -> dict[str, object]:
    shots: list[dict[str, object]] = []
    for number in range(1, shot_count + 1):
        shots.append({
            "duration_ms": 2_000,
            "opening_composition": {
                "scale": "wide shot" if number == 1 else "medium shot",
                "angle": "eye level" if number % 2 else "low angle",
                "axis": "same left side of the lane's 180-degree axis",
                "perspective": f"street-level depth revealing obstacle {number}",
            },
            "purpose": f"Advance the chase through visual phase {number}.",
            "new_information": f"Obstacle {number} becomes clearly visible.",
            "continuity_from_previous": (
                None if number == 1 else _continuity(number)
            ),
            "actions": [
                f"The runner approaches obstacle {number}.",
                f"The runner clears obstacle {number} toward screen right.",
            ],
            "observable_end_state": f"Obstacle {number} is behind the runner.",
            "active_picture_labels": [
                f"<Picture {index}>"
                for index in range(1, reference_count + 1)
            ],
            "camera": _camera(number) if number in cameras else None,
        })
    return {
        "scene_setup": "A rain-soaked alley contains a stable line of blue crates.",
        "continuity_invariants": [
            "The runner, armor, alley geometry, rain, and travel direction remain stable."
        ],
        "shots": shots,
        "final_state": {
            "description": "The runner lands beyond the final blue crate.",
            "final_hold_ms": 1_000,
        },
        "risks": [{
            "risk_id": "risk_1",
            "category": "spatial",
            "description": "The screen direction could reverse across a hard cut.",
            "recommendation": RISK_DECISION,
            "resolution": RISK_DECISION if resolved else None,
        }],
        "technical_adjustments": [],
        "overall_soundscape": "Rain, footfalls, armor movement, and crate impacts.",
        "non_diegetic_music": "N/A",
    }


def writer_document(shot_count: int) -> str:
    sections = [
        "scene_setup:\n"
        "A rain-soaked alley holds the same runner, blue crates, lighting, and travel axis."
    ]
    for number in range(1, shot_count + 1):
        final = (
            " The runner lands beyond the final crate and settles into balanced stillness."
            if number == shot_count
            else ""
        )
        sections.append(
            f"shot_{number}:\n"
            f"The runner advances through visual phase {number}, clears obstacle "
            f"{number} toward screen right, and leaves it visibly behind.{final}"
        )
    sections.extend((
        "overall_soundscape:\n"
        "Steady rain, measured footfalls, armor movement, breathing, and crate impacts.",
        "non_diegetic_music:\nN/A",
    ))
    return "\n\n".join(sections)


class FlexibleMultiShotGateway:
    def __init__(
        self,
        shot_count: int,
        *,
        cameras: tuple[int, ...] = (),
        reconcile_shot_count: int | None = None,
        reference_count: int = 2,
    ) -> None:
        self.shot_count = shot_count
        self.cameras = cameras
        self.reconcile_shot_count = reconcile_shot_count
        self.reference_count = reference_count
        self.requests: list[CompletionRequest] = []

    def _content(self, request: CompletionRequest) -> str:
        if request.operation_id == "action_plan.generate":
            return json.dumps(flexible_plan(
                self.shot_count,
                cameras=self.cameras,
                resolved=False,
                reference_count=self.reference_count,
            ))
        if request.operation_id == "action_plan.reconcile":
            return json.dumps(flexible_plan(
                self.reconcile_shot_count or self.shot_count,
                cameras=self.cameras,
                resolved=True,
                reference_count=self.reference_count,
            ))
        return writer_document(self.shot_count)

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


def _session(
    assets: LocalAssetStore,
    shot_count: int,
    reference_count: int = 2,
) -> tuple[PromptLabSession, tuple[bytes, ...]]:
    definitions = (
        ("first_frame", ReferenceUse.FIRST_FRAME, "Opening frame"),
        ("subject_reference", ReferenceUse.SUBJECT, "Identity reference"),
        ("environment_reference", ReferenceUse.ENVIRONMENT, "Alley reference"),
    )[:reference_count]
    references: list[PromptReference] = []
    contents: list[bytes] = []
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
        session_id="flexible-multishot-session",
        model_id="vision-model",
        profile_id="minimax.h3.ref2v.direct",
        profile_version="0.1.0",
        references=tuple(references),
        session_mode=PromptSessionMode.DIRECT_MULTIMODAL,
    )
    session = session.add_brief_revision(BriefRevision(
        revision_id="brief-1",
        source_text=f"Le coursier traverse la ruelle en {shot_count} plans.",
        content=(
            f"{shot_count} plans distincts relient une course vers la droite par "
            "des coupes franches dans la meme ruelle."
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
    shot_count: int,
    *,
    cameras: tuple[int, ...] = (),
    reconcile_shot_count: int | None = None,
    reference_count: int = 2,
) -> tuple[PromptCompositionService, FlexibleMultiShotGateway, tuple[bytes, ...]]:
    asset_ids = iter(("asset-1", "asset-2", "asset-3"))
    assets = LocalAssetStore(directory, id_factory=lambda: next(asset_ids))
    session, contents = _session(assets, shot_count, reference_count)
    sessions = LocalPromptSessionStore(directory)
    sessions.create(session)
    gateway = FlexibleMultiShotGateway(
        shot_count,
        cameras=cameras,
        reconcile_shot_count=reconcile_shot_count,
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
        COOKBOOK_VERSION,
        (CookbookBinding(
            "references",
            tuple(
                f"reference-{index}"
                for index in range(1, reference_count + 1)
            ),
        ),),
    )
    return service, gateway, contents


def _clock(milliseconds: int) -> str:
    minutes, remainder = divmod(milliseconds, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


class DirectRef2VMultiShotCompositionV2Test(unittest.TestCase):
    def test_two_and_six_shots_keep_images_at_planner_and_compile_owned_timeline(self):
        for shot_count in (2, 6):
            cameras = (1, shot_count)
            with self.subTest(shot_count=shot_count), tempfile.TemporaryDirectory() as directory:
                service, gateway, contents = configured_service(
                    directory,
                    shot_count,
                    cameras=cameras,
                )

                composition = service.generate(
                    "flexible-multishot-session", CompositionStage.BEAT_SHEET
                )
                plan_request = gateway.requests[-1]
                self.assertEqual(plan_request.operation_id, "action_plan.generate")
                self.assertEqual(
                    tuple(image.content for image in plan_request.images),
                    contents,
                )
                plan = json.loads(composition.beat_sheet.active_revision.content)
                self.assertEqual(len(plan["shots"]), shot_count)
                self.assertTrue(all("shot_id" not in shot for shot in plan["shots"]))

                service.approve(
                    "flexible-multishot-session", CompositionStage.BEAT_SHEET
                )
                composition = service.generate(
                    "flexible-multishot-session", CompositionStage.FINAL_PROMPT
                )
                writer_request = gateway.requests[-1]
                self.assertEqual(writer_request.operation_id, "final_prompt.generate")
                self.assertEqual(writer_request.images, ())
                self.assertIn(f'"shot_number": {shot_count}', writer_request.user_prompt)
                self.assertIn(
                    f'"heading": "[Shot {shot_count}] At '
                    f'{_clock((shot_count - 1) * 2_000)},"',
                    writer_request.user_prompt,
                )
                for forbidden in (
                    '"camera":',
                    '"motion":',
                    '"target_clause":',
                    '"visible_change":',
                    "[[camera:",
                ):
                    self.assertNotIn(forbidden, writer_request.user_prompt)

                final = composition.final_prompt.active_revision
                self.assertTrue(final.compiler_context.startswith(CONTEXT_MARKER_V2))
                self.assertEqual(
                    len(re.findall(r"(?m)^\[Shot \d+\]", final.content)),
                    shot_count,
                )
                self.assertIn("[Shot 1] The camera pushes in", final.content)
                for number in range(2, shot_count + 1):
                    self.assertIn(
                        f"[Shot {number}] At {_clock((number - 1) * 2_000)},",
                        final.content,
                    )
                self.assertIn(
                    f"[Shot {shot_count}] At "
                    f"{_clock((shot_count - 1) * 2_000)}, The camera pushes in",
                    final.content,
                )
                self.assertEqual(final.content.count("The camera pushes in"), 2)
                self.assertNotIn("[[camera:", final.content)
                self.assertNotIn("shot_1:", final.content)

    def test_zero_camera_plan_compiles_all_dynamic_headings_without_camera_prose(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, _ = configured_service(directory, 3, cameras=())
            service.generate(
                "flexible-multishot-session", CompositionStage.BEAT_SHEET
            )
            service.approve(
                "flexible-multishot-session", CompositionStage.BEAT_SHEET
            )

            composition = service.generate(
                "flexible-multishot-session", CompositionStage.FINAL_PROMPT
            )

            self.assertEqual(gateway.requests[-1].images, ())
            final = composition.final_prompt.active_revision
            self.assertTrue(final.compiler_context.startswith(CONTEXT_MARKER_V2))
            self.assertNotIn("The camera", final.content)
            self.assertNotIn("[[camera:", final.content)
            self.assertIn("[Shot 1] The runner", final.content)
            self.assertIn("[Shot 2] At 00:02.000, The runner", final.content)
            self.assertIn("[Shot 3] At 00:04.000, The runner", final.content)

    def test_manual_edit_and_revision_round_trip_dynamic_six_shot_context(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, _ = configured_service(
                directory, 6, cameras=(2, 6)
            )
            service.generate(
                "flexible-multishot-session", CompositionStage.BEAT_SHEET
            )
            service.approve(
                "flexible-multishot-session", CompositionStage.BEAT_SHEET
            )
            composition = service.generate(
                "flexible-multishot-session", CompositionStage.FINAL_PROMPT
            )
            original = composition.final_prompt.active_revision

            edited = service.edit(
                "flexible-multishot-session",
                CompositionStage.FINAL_PROMPT,
                original.content.replace("Steady rain", "Soft steady rain", 1),
            ).final_prompt.active_revision
            self.assertEqual(edited.compiler_context, original.compiler_context)

            revised = service.revise(
                "flexible-multishot-session",
                CompositionStage.FINAL_PROMPT,
                "Clarify the final landing without changing shots, cuts, or camera.",
            ).final_prompt.active_revision

            request = gateway.requests[-1]
            self.assertEqual(request.operation_id, "final_prompt.revise")
            self.assertEqual(request.images, ())
            current = request.user_prompt.split(
                "CURRENT INTERNAL DOCUMENT\n", 1
            )[1].split("\n\nREQUESTED CHANGE", 1)[0]
            self.assertIn("shot_1:", current)
            self.assertIn("shot_6:", current)
            self.assertNotIn("shot_7:", current)
            self.assertNotIn("[Shot ", current)
            self.assertNotIn("At 00:", current)
            self.assertNotIn("The camera", current)
            self.assertNotIn("[[camera:", current)
            self.assertEqual(revised.compiler_context, original.compiler_context)
            self.assertEqual(revised.content.count("The camera pushes in"), 2)
            self.assertNotIn("[[camera:", revised.content)

    def test_arbitration_reuses_images_and_preserves_dynamic_shot_count(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, contents = configured_service(directory, 4)
            service.generate(
                "flexible-multishot-session", CompositionStage.BEAT_SHEET
            )

            events = list(service.stream_reconcile_action_plan(
                "flexible-multishot-session",
                {"risk_1": RISK_DECISION},
                "Keep all four shot durations and hard-cut boundaries unchanged.",
            ))

            request = gateway.requests[-1]
            self.assertEqual(request.operation_id, "action_plan.reconcile")
            self.assertEqual(
                tuple(image.content for image in request.images),
                contents,
            )
            plan = json.loads(events[-1].composition.beat_sheet.active_revision.content)
            self.assertEqual(len(plan["shots"]), 4)
            self.assertEqual(plan["risks"][0]["resolution"], RISK_DECISION)

    def test_arbitration_rejects_a_valid_plan_that_changes_shot_count(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, _ = configured_service(
                directory,
                3,
                reconcile_shot_count=4,
            )
            original = service.generate(
                "flexible-multishot-session", CompositionStage.BEAT_SHEET
            ).beat_sheet.active_revision.content

            with self.assertRaises(ValueError):
                list(service.stream_reconcile_action_plan(
                    "flexible-multishot-session",
                    {"risk_1": RISK_DECISION},
                    "Resolve only the selected risk.",
                ))

            self.assertEqual(gateway.requests[-1].operation_id, "action_plan.reconcile")
            active = service.compositions.get(
                "flexible-multishot-session"
            ).beat_sheet.active_revision
            self.assertEqual(active.content, original)

    def test_published_v1_remains_a_distinct_fixed_three_shot_contract(self):
        catalog = LocalPromptCookbookCatalog(COOKBOOK_ROOT)
        v1 = catalog.get(COOKBOOK_ID, "0.1.0")
        v2 = catalog.get(COOKBOOK_ID, COOKBOOK_VERSION)

        self.assertEqual(
            v1.output_contract,
            "minimax.h3.ref2v.direct_multishot_compact_h3_v1",
        )
        self.assertEqual(v1.writer_projection, "compact_multishot_v1")
        self.assertIn("approved three-shot plan", v1.final_prompt_system_prompt.lower())
        self.assertIn("exactly these six internal fields", v1.final_prompt_system_prompt.lower())
        self.assertIn("[[camera:camera_N]]", v1.final_prompt_system_prompt)
        self.assertEqual(
            v2.output_contract,
            "minimax.h3.ref2v.direct_multishot_compact_h3_v2",
        )
        self.assertEqual(v2.writer_projection, "compact_multishot_v2_camera_owned")
        self.assertNotEqual(v1.output_contract, v2.output_contract)


if __name__ == "__main__":
    unittest.main()
