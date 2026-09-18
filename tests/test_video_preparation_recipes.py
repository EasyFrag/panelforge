"""Offline preparation contracts. All model responses below are fixed fixtures."""

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.application import (
    CompletionResult, CompletionStreamEvent, PromptCompositionService,
    StreamEventKind, StreamPhase,
)
from panelforge.application.video_preparation import (
    compile_direct_prompt, direct_prompt_context, direct_prompt_errors,
)
from panelforge.application.direct_ref2v_prompt import validate_direct_ref2v_labels
from panelforge.domain import (
    BriefReferenceSnapshot, BriefRevision, CompositionStage, CookbookBinding,
    PromptLabSession, PromptReference, PromptSessionMode, ReferenceUse, RevisionOrigin,
)
from panelforge.domain.prompt_composition import PreparationIntent
from panelforge.domain.prompt_lab import CreativeFreedomAxes
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.storage import LocalAssetStore, LocalPromptCompositionStore, LocalPromptSessionStore
from tests.test_h3_base_motion_v3 import late_anchor_motion_plan, writer_body
from tests.test_direct_ref2v_composition import action_plan_v4, final_document


ROOT = Path(__file__).resolve().parents[1]
DIRECT_BODY = json.dumps({
    "camera_motion": "static_shot",
    "integrated_multimodal_description": "A small dragon breaks the shell and lifts its head. At 00:06.000, fragments fall as its wings keep opening through the cut.",
    "overall_soundscape": "N/A",
    "non_diegetic_music": "N/A",
})


class ScriptedGateway:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return CompletionResult(request.model_id, next(self.responses))

    def stream(self, request):
        result = self.complete(request)
        yield CompletionStreamEvent(StreamEventKind.DELTA, StreamPhase.GENERATING, text=result.content)
        yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED, result=result)


def preparation_service(directory, family, route, responses, *, roles=None, source_text="A dragon emerges from an egg in 12 seconds.", version="1.0.0", multishot=False, profile_version=None, creative_axes=None, preparation_family="classic", combat_settings=None, cinematic_settings=None, sensual_settings=None):
    h3 = family == "fl2va"
    roles = roles if roles is not None else ("first_frame",) if h3 else ("subject_reference",)
    assets = LocalAssetStore(directory)
    refs = []
    for index, role in enumerate(roles):
        asset = assets.create(b"\x89PNG\r\n\x1a\nfixture" + bytes([index]), "image/png")
        refs.append(PromptReference(f"ref-{index}", asset.asset_id, role, f"private-{index}.png",
                                    uses=(ReferenceUse(role.removesuffix("_reference")),)))
    from panelforge.domain.video_preparation import VideoPreparationRef
    preparation = VideoPreparationRef(preparation_family, version if preparation_family in {"combat", "sensual"} or cinematic_settings is not None else None)
    base = f"minimax.h3.{family}.{'combat' if preparation.is_combat else 'direct'}"
    if preparation.is_classic_cinematic:
        base = f"minimax.h3.{family}.classic.cinematic"
        profile_version = version
    if preparation.is_combat:
        profile_version = version
    if preparation.is_sensual:
        base = f"minimax.h3.{family}.sensual"
        profile_version = version
    if multishot:
        base += ".multishot"
    session = PromptLabSession(
        session_id="preparation-session", model_id="fixture-model", profile_id=base,
        profile_version=profile_version or ("0.2.0" if multishot else ("0.5.0" if version == "1.1.0" else "0.4.0") if h3 else "0.5.0"), references=tuple(refs),
        session_mode=PromptSessionMode.H3_BASE if h3 else PromptSessionMode.DIRECT_MULTIMODAL,
        preparation=preparation, combat_settings=combat_settings, cinematic_settings=cinematic_settings,
        sensual_settings=sensual_settings,
    )
    sessions = LocalPromptSessionStore(directory)
    sessions.create(session)
    gateway = ScriptedGateway(responses)
    service = PromptCompositionService(
        gateway=gateway, cookbooks=LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks"),
        sessions=sessions, compositions=LocalPromptCompositionStore(directory), assets=assets,
    )
    bindings = tuple(CookbookBinding(role, tuple(ref.reference_id for ref in refs if ref.role == role))
                     for role in ("first_frame", "last_frame")) if h3 else (
                         CookbookBinding("references", tuple(ref.reference_id for ref in refs)),
                     )
    intent = PreparationIntent(source_text, 35, creative_axes or CreativeFreedomAxes(1, 0, 1), 2)
    composition = service.configure(session.session_id, f"{base}.{route}", version, bindings,
                                    preparation_intent=None if route == "guided" else intent)
    return service, gateway, session, composition


class VideoPreparationRecipesTest(unittest.TestCase):
    def test_two_and_three_steps_pin_the_same_complete_writer(self):
        catalog = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        for family in ("fl2va", "ref2v"):
            base = f"minimax.h3.{family}.direct"
            guided = catalog.get(base + ".guided", "1.0.0")
            planned = catalog.get(base + ".planned", "1.0.0")
            direct = catalog.get(base + ".prompt", "1.0.0")
            self.assertEqual(guided.final_prompt_system_prompt, planned.final_prompt_system_prompt)
            self.assertEqual(guided.final_prompt_user_prompt, planned.final_prompt_user_prompt)
            self.assertEqual(guided.output_contract, planned.output_contract)
            self.assertEqual((guided.preparation_steps, planned.preparation_steps, direct.preparation_steps), (3, 2, 1))
            self.assertEqual(guided.profile_id, base)
            self.assertIn("user's raw intention", planned.beat_sheet_system_prompt)
            self.assertIn("approved Brief", guided.beat_sheet_system_prompt)
            self.assertIn("creative interpretation, chronology and prose", direct.final_prompt_system_prompt)
            self.assertNotIn("{{", direct.final_prompt_system_prompt)

    def test_two_steps_need_no_brief_and_send_images_only_to_the_plan(self):
        for family in ("fl2va", "ref2v"):
            with self.subTest(family=family), tempfile.TemporaryDirectory() as directory:
                responses = [json.dumps(late_anchor_motion_plan()), writer_body()] if family == "fl2va" else [
                    json.dumps(action_plan_v4(with_camera=False)), final_document(with_camera=False, camera_owned=True),
                ]
                service, gateway, session, _ = preparation_service(directory, family, "planned", responses)
                with self.assertRaisesRegex(ValueError, "approve a current beat_sheet"):
                    service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
                self.assertEqual(gateway.requests, [])
                service.generate(session.session_id, CompositionStage.BEAT_SHEET)
                service.approve(session.session_id, CompositionStage.BEAT_SHEET)
                service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
                service.approve(session.session_id, CompositionStage.FINAL_PROMPT)
                self.assertEqual(len(gateway.requests), 2)
                self.assertEqual(len(gateway.requests[0].images), 1)
                self.assertEqual(gateway.requests[1].images, ())
                self.assertIn("A dragon emerges", gateway.requests[0].user_prompt)
                self.assertNotIn("A dragon emerges", gateway.requests[1].user_prompt)
                self.assertIn(".planned@1.0.0.action_plan.generate", gateway.requests[0].operation_id)
                self.assertFalse(service.sessions.get(session.session_id).brief_revisions)

    def test_ref2v_keyframe_header_tracks_the_route_and_stays_locked_after_reopening(self):
        for route, source_label in (("planned", "user intention"), ("guided", "approved Brief")):
            with self.subTest(route=route), tempfile.TemporaryDirectory() as directory:
                writer = final_document(camera_owned=True)
                plan = action_plan_v4()
                plan["final_state"]["description"] += " (<Picture 2>)"
                service, gateway, session, configured = preparation_service(
                    directory, "ref2v", route, [json.dumps(plan), writer, writer],
                    roles=("first_frame", "keyframe_reference", "keyframe_reference", "keyframe_reference"),
                    source_text="A courier hands a parcel to a recipient in 12 seconds.",
                )
                if route == "guided":
                    brief = BriefRevision(
                        "brief-fixture", "A courier hands over a parcel in 12 seconds.",
                        "The courier crosses the room and transfers the parcel.", 35,
                        RevisionOrigin.MODEL,
                        tuple(BriefReferenceSnapshot(ref.reference_id, None, ref.uses)
                              for ref in session.references),
                    )
                    service.sessions.save(session.add_brief_revision(brief).approve_brief())
                service.generate(session.session_id, CompositionStage.BEAT_SHEET)
                service.approve(session.session_id, CompositionStage.BEAT_SHEET)
                events = list(service.stream_generate(session.session_id, CompositionStage.FINAL_PROMPT))
                self.assertIsNotNone(events[-1].composition)
                final = events[-1].composition.final_prompt.active_revision
                header = final.content.split("\n\n", 1)[0]
                self.assertIn("<Picture 1>: the exact fully preserved starting frame", header)
                for number in (2, 3, 4):
                    self.assertIn(
                        f"<Picture {number}>: a concrete keyframe anchor at the time assigned by "
                        f"the {source_label} and plan;", header,
                    )
                self.assertEqual(header.count("<Picture 2>"), 1)
                self.assertIn("<Picture 2>", final.content[len(header):])
                service.approve(session.session_id, CompositionStage.FINAL_PROMPT)
                reopened = LocalPromptCompositionStore(directory).get(session.session_id)
                self.assertEqual(reopened.final_prompt.active_revision.content, final.content)
                self.assertEqual(reopened.preparation_intent, configured.preparation_intent)
                revised = service.revise(session.session_id, CompositionStage.FINAL_PROMPT, "Keep the action concise.")
                self.assertEqual(revised.final_prompt.active_revision.content.split("\n\n", 1)[0], header)
                self.assertEqual(len(gateway.requests), 3)
                self.assertEqual(len(service.sessions.get(session.session_id).brief_revisions), int(route == "guided"))

                mapping = tuple((ref.reference_id, number) for number, ref in enumerate(session.references, 1))
                wrong_source = "approved Brief" if route == "planned" else "user intention"
                for changed in (
                    final.content.replace(source_label, wrong_source),
                    final.content.replace("a concrete keyframe anchor", "a subject identity reference"),
                    final.content.replace("<Picture 3>", "<Picture 4>"),
                    "\n".join(line for line in final.content.splitlines() if "<Picture 3>" not in line),
                ):
                    with self.subTest(changed=changed[:100]), self.assertRaises(ValueError):
                        validate_direct_ref2v_labels(
                            session, mapping, CompositionStage.FINAL_PROMPT, changed, expected_header=header,
                        )

    def test_one_step_streams_compiles_reopens_and_revises_without_upstream_documents(self):
        for family, roles in (("fl2va", ()), ("fl2va", ("first_frame",)),
                              ("fl2va", ("last_frame",)), ("fl2va", ("first_frame", "last_frame")),
                              ("ref2v", ("subject_reference",)),
                              ("ref2v", ("first_frame", "keyframe_reference", "keyframe_reference", "keyframe_reference")),
                              ("ref2v", ("first_frame",) + ("keyframe_reference",) * 8)):
            with self.subTest(family=family, roles=roles), tempfile.TemporaryDirectory() as directory:
                service, gateway, session, _ = preparation_service(directory, family, "prompt", [DIRECT_BODY, DIRECT_BODY], roles=roles)
                events = list(service.stream_generate(session.session_id, CompositionStage.FINAL_PROMPT))
                self.assertEqual(len(gateway.requests), 1)
                self.assertEqual(len(gateway.requests[0].images), len(roles))
                self.assertEqual(events[0].text, DIRECT_BODY)  # compiler context is never streamed as prose
                compiled = events[-1].composition
                self.assertIn("one continuous 12-second shot", compiled.final_prompt.active_revision.content)
                self.assertFalse(compiled.beat_sheet.revisions)
                self.assertFalse(service.sessions.get(session.session_id).brief_revisions)
                self.assertTrue(all("private-" not in image.label for image in gateway.requests[0].images))
                service.approve(session.session_id, CompositionStage.FINAL_PROMPT)
                reopened = LocalPromptCompositionStore(directory).get(session.session_id)
                self.assertEqual(reopened.cookbook, compiled.cookbook)
                self.assertEqual(reopened.preparation_intent, compiled.preparation_intent)
                service.revise(session.session_id, CompositionStage.FINAL_PROMPT, "Keep this action concise.")
                self.assertEqual(len(gateway.requests), 2)
                self.assertFalse(service.get(session.session_id).beat_sheet.revisions)

    def test_guided_route_still_requires_a_real_approved_brief(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, session, _ = preparation_service(directory, "fl2va", "guided", [json.dumps(late_anchor_motion_plan())])
            with self.assertRaisesRegex(ValueError, "structured brief"):
                service.generate(session.session_id, CompositionStage.BEAT_SHEET)
            self.assertEqual(gateway.requests, [])
            brief = BriefRevision("brief-fixture", "A dragon emerges in 12 seconds.", "Approved direction sentinel.", 35,
                                  RevisionOrigin.MODEL, tuple(BriefReferenceSnapshot(ref.reference_id, None, ref.uses)
                                                            for ref in session.references))
            service.sessions.save(session.add_brief_revision(brief).approve_brief())
            service.generate(session.session_id, CompositionStage.BEAT_SHEET)
            self.assertIn("Approved direction sentinel", gateway.requests[0].user_prompt)

    def test_intention_and_recipe_cannot_be_silently_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, session, original = preparation_service(directory, "fl2va", "planned", [])
            with self.assertRaisesRegex(ValueError, "intention is locked"):
                service.configure(session.session_id, original.cookbook.cookbook_id, "1.0.0", original.bindings,
                                  replace(original.preparation_intent, source_text="A different story."))
            with self.assertRaisesRegex(ValueError, "another cookbook"):
                service.configure(session.session_id, "minimax.h3.fl2va.direct.prompt", "1.0.0", original.bindings, original.preparation_intent)
            self.assertEqual(service.get(session.session_id), original)
            self.assertEqual(gateway.requests, [])

    def test_schema_two_compositions_remain_readable_without_a_direct_intention(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _, session, original = preparation_service(directory, "fl2va", "guided", [])
            path = Path(directory) / "prompt_compositions" / session.session_id / "composition.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["schema_version"] = 2
            raw.pop("preparation_intent")
            raw.pop("writer_model_id")
            raw.pop("prompt_variants")
            path.write_text(json.dumps(raw), encoding="utf-8")
            self.assertEqual(service.get(session.session_id), original)
            self.assertIsNone(service.get(session.session_id).preparation_intent)

    def test_direct_rejects_wrong_headers_and_does_not_lose_quoted_speech(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _, session, composition = preparation_service(directory, "fl2va", "prompt", [], source_text='The dragon says "Bonjour." in 8 seconds.')
            context = direct_prompt_context(session, ((session.references[0].reference_id, 1),), composition.preparation_intent.source_text)
            with self.assertRaisesRegex(ValueError, "paroles exactes"):
                compile_direct_prompt(DIRECT_BODY, context)
            body = json.loads(DIRECT_BODY)
            body["integrated_multimodal_description"] += ' The dragon says calmly <d>[French] Bonjour.</d>'
            compiled = compile_direct_prompt(json.dumps(body), context)
            self.assertFalse(direct_prompt_errors(compiled, context=json.loads(context)))
            self.assertTrue(direct_prompt_errors(compiled.replace("<Picture 1>", "<Picture 2>"), context=json.loads(context)))

    def test_template_dependencies_reject_mutable_versions_and_cycles(self):
        original = ROOT / "prompt_cookbooks/minimax.h3.fl2va.direct.prompt/1.0.0/manifest.json"
        for dependency in ({"cookbook_id": "minimax.h3.fl2va.direct.prompt", "version": "latest", "template": "final_prompt_system"},
                           {"cookbook_id": "minimax.h3.fl2va.direct.prompt", "version": "1.0.0", "template": "final_prompt_system"}):
            with self.subTest(dependency=dependency), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "minimax.h3.fl2va.direct.prompt/1.0.0"
                target.mkdir(parents=True)
                manifest = json.loads(original.read_text(encoding="utf-8"))
                manifest["templates"]["final_prompt_system"] = [dependency]
                (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "exact numeric version|cyclic"):
                    LocalPromptCookbookCatalog(directory).list()
