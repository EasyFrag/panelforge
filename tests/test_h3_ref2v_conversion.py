"""Offline conversion, persistence and single-call regression fixtures."""
import json
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from panelforge.application.h3_render import H3RenderService
from panelforge.application.h3_ref2v_conversion import (
    H3Ref2VConversionService, compile_conversion, conversion_document,
)
from panelforge.application.h3_render import canonicalize_h3_revision
from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.domain.h3_render import H3RenderInputMode, H3RenderProject, H3RenderSetup
from panelforge.domain.recipes import RecipeRef
from panelforge.domain.video_lab import VideoLabSettings, VideoAspectRatio
from panelforge.infrastructure.storage import LocalAssetStore, LocalH3RenderProjectStore

PROMPT = (
    'integrated_multimodal_description:\n[Shot 1] The target video is one continuous 8-second shot. '
    'The camera holds a static shot. At 00:01.000, she pours the liquid and says <d>[English] Wow!</d>\n'
    'overall_soundscape:\nLiquid splashes.\nnon_diegetic_music:\nN/A'
)
MULTI = (
    'integrated_multimodal_description:\n[Shot 1] The camera holds a static shot. She pours liquid. <scenetrans>\n'
    '[Shot 2] At 00:04.000, <scenetrans> The camera holds a static shot. She spreads it with a brush. At 00:08.000, the floor is covered.\n'
    'overall_soundscape:\nLiquid splashes.\nnon_diegetic_music:\nN/A'
)


class EchoConversionGateway:
    def __init__(self, malformed=False):
        self.requests = []
        self.malformed = malformed

    def stream(self, request):
        self.requests.append(request)
        content = 'incomplete candidate' if self.malformed else json.dumps({"shots": json.loads(request.user_prompt)["shots"]})
        yield CompletionStreamEvent(StreamEventKind.DELTA, StreamPhase.GENERATING, text=content)
        yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED,
                                    result=CompletionResult(request.model_id, content, call_id="fixture-call"))


class H3Ref2VConversionTest(unittest.TestCase):
    def service(self, directory, *, mode=H3RenderInputMode.FL2VA, malformed=False):
        assets, projects = LocalAssetStore(directory), LocalH3RenderProjectStore(directory)
        first = assets.create(b'first fixture', 'image/png').asset_id
        last = assets.create(b'last fixture', 'image/png').asset_id
        frames = {}
        if mode in (H3RenderInputMode.I2VA, H3RenderInputMode.FL2VA):
            frames.update(first_frame_asset_id=first, first_frame_label="Start")
        if mode in (H3RenderInputMode.L2VA, H3RenderInputMode.FL2VA):
            frames.update(last_frame_asset_id=last, last_frame_label="End")
        source = H3RenderProject("source", "session", "prompt-1", "fixture", mode, PROMPT, **frames)
        projects.create(source)
        recipe = RecipeRef("video.generate.ref2v", "minimax-h3-ref2v", "0.2.0", "a" * 64)
        setup = H3RenderSetup(VideoLabSettings(VideoAspectRatio.PORTRAIT_WIDESCREEN, .9, 8, 25, 2**63 + 7, True),
                              .2, False, False, None, recipe)
        renders = SimpleNamespace(projects=projects, assets=assets, gateway=EchoConversionGateway(malformed),
                                  default_revision_version=H3RenderService.default_revision_version,
                                  workflow_for_mode=lambda *args: SimpleNamespace(reference=recipe), _report=Mock())
        return H3Ref2VConversionService(renders), source, setup, first

    def test_first_last_single_call_reopen_and_idempotence(self):
        with tempfile.TemporaryDirectory() as directory:
            service, source, setup, _ = self.service(directory)
            edited = PROMPT.replace("pours the liquid", "pours pink liquid")
            args = dict(request_id="request-1234", prompt=edited, model_id="fixture", setup=setup)
            target = service.prepare(source.project_id, **args)
            self.assertEqual(target.adaptation.reference_roles, ("first_frame", "last_frame"))
            self.assertEqual(target.reference_asset_ids, (source.first_frame_asset_id, source.last_frame_asset_id))
            self.assertEqual(service.prepare(source.project_id, **args).project_id, target.project_id)
            completed = list(service.stream(target.project_id))[-1].project
            self.assertEqual(completed.adaptation.status, "ready", completed.adaptation.error)
            self.assertIn("pink liquid", completed.current_prompt)
            self.assertIn('<d>[English] Wow!</d>', completed.current_prompt)
            self.assertEqual(completed.attempts, ())
            list(service.stream(target.project_id))
            self.assertEqual(len(service.renders.gateway.requests), 1)
            self.assertEqual([i.content for i in service.renders.gateway.requests[0].images], [b'first fixture', b'last fixture'])
            self.assertEqual(service.renders.projects.get(source.project_id), source)
            reopened = LocalH3RenderProjectStore(directory).get(target.project_id)
            self.assertEqual(reopened.adaptation.render_setup, setup)
            with self.assertRaises(ValueError):
                service.prepare(source.project_id, **dict(args, prompt=PROMPT))

    def test_i2v_l2v_and_text_requiring_an_image(self):
        for mode, roles in ((H3RenderInputMode.I2VA, ("first_frame",)), (H3RenderInputMode.L2VA, ("last_frame",)),
                            (H3RenderInputMode.T2VA, ("subject_reference",))):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                service, source, setup, image = self.service(directory, mode=mode)
                args = dict(request_id="request-1234", prompt=PROMPT, model_id="fixture", setup=setup)
                if mode is H3RenderInputMode.T2VA:
                    with self.assertRaises(ValueError): service.prepare(source.project_id, **args)
                    args["extra_reference"] = (image, "Subject")
                target = service.prepare(source.project_id, **args)
                self.assertEqual(target.adaptation.reference_roles, roles)

    def test_failed_candidate_keeps_original_and_never_repeats_call(self):
        with tempfile.TemporaryDirectory() as directory:
            service, source, setup, _ = self.service(directory, malformed=True)
            target = service.prepare(source.project_id, request_id="request-1234", prompt=PROMPT, model_id="fixture", setup=setup)
            result = list(service.stream(target.project_id))[-1].project
            self.assertEqual(result.adaptation.status, "failed")
            self.assertEqual(result.adaptation.raw_response, "incomplete candidate")
            self.assertEqual(result.current_prompt, PROMPT)
            self.assertEqual(result.attempts, ())
            list(service.stream(target.project_id))
            self.assertEqual(len(service.renders.gateway.requests), 1)

    def test_protected_tokens_cannot_be_removed_duplicated_or_reordered(self):
        doc = conversion_document(PROMPT)
        for text in (doc["shots"][0].replace("[[keep:1]]", ""), doc["shots"][0] + " [[keep:1]]",
                     doc["shots"][0] + ' <d>[English] Surprise!</d>', doc["shots"][0] + ' <Picture 3>'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                compile_conversion(json.dumps({"shots": [text]}), PROMPT, ("first_frame",))

    def test_multiple_shots_cuts_and_revision_keep_the_envelope(self):
        document = conversion_document(MULTI)
        result = compile_conversion(json.dumps({"shots": document["shots"]}), MULTI, ("first_frame", "last_frame"))
        self.assertIn('[Shot 2] At 00:04.000,', result)
        self.assertEqual(result.count('<scenetrans>'), 2)
        self.assertIn('At 00:08.000,', result)
        self.assertEqual(result.count('The camera holds a static shot.'), 2)
        self.assertEqual(canonicalize_h3_revision(result, result, H3RenderInputMode.REF2VA), result)
