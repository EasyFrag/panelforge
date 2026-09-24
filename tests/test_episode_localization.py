"""User-run regressions. Temporary storage and fake LLM only; never the live workspace."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from threading import RLock
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from panelforge.application.episodes import EpisodeConflict
from panelforge.application.h3_render import H3RenderService
from panelforge.application.prompt_lab import CompletionResult, ModelDescriptor, StreamEventKind
from panelforge.domain import episode_localization as contract
from panelforge.domain.dlss import DlssResult
from panelforge.domain.episodes import fingerprint, scene_inputs
from panelforge.domain.h3_render import H3RenderProject, H3RenderInputMode, H3RenderAttempt, H3RenderAttemptStatus
from panelforge.domain.video_lab import VideoLabSettings, VideoAspectRatio
from panelforge.domain.recipes import RecipeRef
from panelforge.infrastructure.storage.h3_render_projects import LocalH3RenderProjectStore
from tests import test_episodes as fixtures


class DialogueLocalizationContractTest(unittest.TestCase):
    def test_nested_quotes_repeated_lines_and_visual_text_keep_their_exact_positions(self):
        prompt = 'Camera A. Sign "Bonjour". <d>[French] Tu dis « mon cœur » ?</d>\nCUT <d>[French] Bonjour.</d> <d>[French] Bonjour.</d> END'
        slots = contract.dialogue_slots(prompt, "scene-1")
        translated = dict(zip((s["id"] for s in slots), ['You call her “sweetheart”?', 'Hello.', 'Hi.']))
        expected = 'Camera A. Sign "Bonjour". <d>[English] You call her “sweetheart”?</d>\nCUT <d>[English] Hello.</d> <d>[English] Hi.</d> END'
        self.assertEqual(contract.inject(prompt, "scene-1", "English", translated), expected)
        self.assertEqual(len(slots), 3)

    def test_bad_or_missing_dialogue_ids_never_change_prompt(self):
        prompt = '<d>[French] Bonjour.</d>'
        for value in ({}, {"scene:d1": "Hello <d>"}, {"other": "Hello"}, {"scene:d1": ""}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                contract.inject(prompt, "scene", "English", value)
        with self.assertRaises(ValueError):
            contract.translations({"translations": [{"id": "scene:d1", "text": "Hello"}] * 2}, contract.dialogue_slots(prompt, "scene"))

    def test_malformed_nested_tags_are_not_classified_as_silent(self):
        for prompt in ('<d>[French] Bonjour', '<D>[French] Bonjour</D>', '<d>[French] hi <d>[English] no</d></d>'):
            with self.subTest(prompt=prompt), self.assertRaises(ValueError):
                contract.dialogue_slots(prompt, "scene")
        self.assertEqual(contract.dialogue_slots('A silent wave. Text: "Bonjour".', "scene"), [])


class EpisodeLocalizationTest(unittest.TestCase):
    create = fixtures.EpisodeTest.create
    ready = fixtures.EpisodeTest.ready

    def setUp(self):
        fixtures.EpisodeTest.setUp(self)
        second = deepcopy(self.story["document"]["scenario"]["scenes"][0])
        second.update(title="Le regard", dialogue=[])
        self.story["document"]["scenario"]["scenes"].append(second)
        self.story = self.stories.store.save(self.story)
        value = self.ready()
        self.render_store = LocalH3RenderProjectStore(self.temp.name)
        fork_service = object.__new__(H3RenderService)
        fork_service._lock = RLock()
        fork_service.projects = self.render_store
        fork_service._project_id_factory = lambda: "localized-render-" + uuid4().hex
        self.service.render.projects = self.render_store
        self.service.render.fork_localization = fork_service.fork_localization
        self.fork_service = fork_service
        self.source_projects = []
        for index, scene in enumerate(value["scenes"]):
            inputs = scene_inputs(value, scene)
            prompt = ('Camera holds. <d>[French] Vous avez pris mon portefeuille !</d> ' +
                      '<d>[French] Il dépasse de votre poche.</d> End.') if index == 0 else 'A silent embarrassed look. No speech.'
            settings = VideoLabSettings(aspect_ratio=VideoAspectRatio('9:16 (Portrait Widescreen)'),
                megapixels=.9, duration_seconds=8, steps=9, seed=42 + index)
            video = H3RenderAttempt(attempt_id=f"source-video-{index}", index=3, prompt=prompt, effective_prompt=prompt,
                settings=settings, music_enabled=False, keyframe_timestamps_ms=(),
                status=H3RenderAttemptStatus.SUCCEEDED, output_asset_id=f"source-output-{index}",
                execution_id=f"source-execution-{index}", compiled_workflow_sha256="1" * 64,
                recipe=RecipeRef(operation_id="test", recipe_id="minimax-h3-ref2v", version="0.2.1", workflow_sha256="0" * 64))
            self.assets.values[video.output_asset_id] = NS(media_type="video/mp4")
            dlss = replace(video, attempt_id=f"source-dlss-{index}", output_asset_id=f"source-upscaled-{index}",
                execution_id=None, compiled_workflow_sha256=None,
                dlss=DlssResult(job_id=f"source-job-{index}", parent_attempt_id=video.attempt_id, root_attempt_id=video.attempt_id,
                    input_asset_id=video.output_asset_id, report_asset_id=f"report-{index}", width=1440, height=2560, size="2"))
            project = self.render_store.create(H3RenderProject(project_id=f"source-render-{index}", source_session_id=f"session-{index}",
                source_prompt_revision_id="revision-1", model_id="original-model", input_mode=H3RenderInputMode.REF2VA,
                current_prompt=prompt, reference_asset_ids=tuple(r["asset_id"] for r in inputs["references"]),
                reference_labels=tuple(r["name"] for r in inputs["references"]), attempts=(video, dlss)))
            self.source_projects.append(project)
            scene["preparations"] = [dict(id=f"prep-{index}", inputs=inputs, input_hash=fingerprint(inputs),
                session_id=f"session-{index}", render_project_id=project.project_id, status="ready")]
        self.source = self.service.store.save(value)
        self.calls = []
        def stream(request):
            self.calls.append(request)
            payload = json.loads(request.user_prompt)
            ids = payload["translate_ids"]
            output = dict(translations=[dict(id=identity, text=f"Translated line {i + 1}.") for i, identity in enumerate(ids)])
            yield NS(kind=StreamEventKind.COMPLETED, result=CompletionResult(model_id=contract.DEFAULT_MODEL,
                content=json.dumps(output), call_id="translation-call"), text=None)
        self.stories.gateway = NS(list_models=lambda: (ModelDescriptor(contract.DEFAULT_MODEL),), stream=stream)
        self.local_thread = patch("panelforge.application.episode_localization.Thread", fixtures.InlineThread)
        self.local_thread.start(); self.addCleanup(self.local_thread.stop)
        self.source_bytes = self._source_bytes()

    def _source_bytes(self):
        paths = [Path(self.temp.name) / "episodes" / (self.source["episode_id"] + ".json")]
        paths.extend(Path(self.temp.name) / "h3_render_projects" / p.project_id / "project.json" for p in self.source_projects)
        return [p.read_bytes() for p in paths]

    def selection(self):
        catalog = self.service.localization_catalog(self.source["episode_id"])
        source = next(s for s in catalog["sources"] if s["episode_id"] == self.source["episode_id"])
        return dict(episode_id=source["episode_id"], scenes=[dict(scene_id=s["id"], **{k: s["choices"][0][k]
            for k in ("preparation_id", "project_id", "attempt_id", "token")}) for s in source["scenes"]])

    def copy(self, request_id="copy-request-123"):
        result = self.service.create_localization(self.source["episode_id"], language="English", model_id=contract.DEFAULT_MODEL,
            selections=[self.selection()], request_id=request_id)
        return self.service.get(result["episode_ids"][0])

    def start(self, copy, mode="translate", request_id="start-request-123"):
        self.service.start_localization(copy["episode_id"], model_id=contract.DEFAULT_MODEL, mode=mode,
            expected_revisions={copy["episode_id"]: copy["localization"]["revision"]}, request_id=request_id)
        return self.service.get(copy["episode_id"])

    def test_copy_pins_actual_attempt_and_reuses_only_silent_video_and_dlss(self):
        copy = self.copy()
        spoken, silent = copy["scenes"]
        self.assertEqual(spoken["render_setup"]["settings"]["duration_seconds"], 8)
        self.assertEqual(spoken["render_setup"]["settings"]["seed"], "42")
        self.assertFalse(spoken["preparations"])
        self.assertEqual(silent["video_attempt"]["output_asset_id"], "source-output-1")
        self.assertTrue(silent["video_reused"])
        self.assertEqual(silent["localization_dlss"]["output_asset_id"], "source-upscaled-1")
        self.assertFalse(copy["story_changed"])
        self.assertEqual(self._source_bytes(), self.source_bytes)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.composition.calls, [])
        self.assertEqual(self.copy()["episode_id"], copy["episode_id"])

    def test_translate_is_one_call_for_the_episode_and_does_not_repeat_ready_work(self):
        translated = self.start(self.copy())
        self.assertEqual(translated["localization"]["job"]["status"], "succeeded")
        scene = translated["scenes"][0]
        project = self.render_store.get(scene["preparations"][-1]["render_project_id"])
        self.assertEqual(project.current_prompt, 'Camera holds. <d>[English] Translated line 1.</d> <d>[English] Translated line 2.</d> End.')
        self.assertEqual(project.reference_asset_ids, self.source_projects[0].reference_asset_ids)
        self.assertFalse(scene["stale"])
        self.start(translated, request_id="another-start-123")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.composition.calls, [])
        self.assertEqual(self._source_bytes(), self.source_bytes)

    def test_failed_translation_keeps_draft_and_does_not_partially_inject(self):
        self.stories.gateway.stream = lambda request: iter([NS(kind=StreamEventKind.COMPLETED,
            result=CompletionResult(model_id=contract.DEFAULT_MODEL, content='{"translations": []}', call_id="bad-call"), text=None)])
        failed = self.start(self.copy())
        self.assertEqual(failed["localization"]["job"]["status"], "failed")
        self.assertEqual(failed["localization"]["job"]["call_id"], "bad-call")
        self.assertIn("translations", failed["localization"]["job"]["draft"])
        self.assertFalse(failed["scenes"][0]["preparations"])
        self.assertTrue(failed["scenes"][1]["video_reused"])

    def test_edit_changes_one_scene_preserves_other_scene_and_old_preparation(self):
        copy = self.start(self.copy())
        scene = copy["scenes"][0]
        previous = deepcopy(scene["preparations"])
        silent = deepcopy(copy["scenes"][1]["preparations"])
        lines = [dict(id=s["id"], text=f"New line {i + 1}.") for i, s in enumerate(scene["localization"]["slots"])]
        edited = self.service.save_localized_dialogues(copy["episode_id"], scene["id"],
            expected_revision=copy["localization"]["revision"], lines=lines)
        self.assertEqual(edited["scenes"][0]["preparations"][:-1], previous)
        self.assertEqual(edited["scenes"][1]["preparations"], silent)
        self.assertIsNone(edited["scenes"][0]["video_attempt"])
        self.assertEqual(len(self.calls), 1)
        with self.assertRaises(EpisodeConflict):
            self.service.save_localized_dialogues(copy["episode_id"], scene["id"], expected_revision=copy["localization"]["revision"], lines=lines)

    def test_full_launch_reuses_prepared_prompts_and_queues_video_dlss(self):
        queue = Mock(return_value={})
        self.service.start_video_chain = queue
        copy = self.start(self.copy(), mode="all")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(queue.call_count, 1)
        self.assertTrue(queue.call_args.kwargs["auto_dlss"])
        self.assertEqual(queue.call_args.kwargs["scene_ids"], [s["id"] for s in copy["scenes"]])
        raw = self.service.store.get(copy["episode_id"])
        raw["video_chain"] = dict(items=[dict(scene_id=s["id"], status="pending") for s in raw["scenes"]])
        self.service._reuse_localized_chain(raw)
        self.assertEqual(raw["video_chain"]["items"][0]["status"], "pending")
        self.assertEqual(raw["video_chain"]["items"][1]["status"], "succeeded")

    def test_prompt_generation_and_reference_changes_are_forbidden_in_copy(self):
        copy = self.copy()
        with self.assertRaises(EpisodeConflict):
            self.service.prepare_scene(copy["episode_id"], copy["scenes"][0]["id"], 1, "forbidden-request")
        with self.assertRaises(EpisodeConflict):
            self.service.select_image(copy["episode_id"], copy["references"][0]["id"], copy["references"][0]["revision"], copy["references"][0]["image_asset_id"])
        with self.assertRaises(ValueError):
            self.service.start_video_chain(copy["episode_id"], expected_video_revision=copy["video_revision"],
                scene_ids=[s["id"] for s in copy["scenes"]], request_id="not-translated")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.composition.calls, [])

    def test_stale_source_and_conflicting_creation_request_are_rejected(self):
        selected = self.selection()
        selected["scenes"][0]["token"] = "0" * 64
        with self.assertRaises(EpisodeConflict):
            self.service.create_localization(self.source["episode_id"], language="English", model_id=contract.DEFAULT_MODEL,
                selections=[selected], request_id="stale-copy-request")
        self.copy()
        with self.assertRaises(EpisodeConflict):
            self.service.create_localization(self.source["episode_id"], language="Japanese", model_id=contract.DEFAULT_MODEL,
                selections=[self.selection()], request_id="copy-request-123")

    def test_restart_marks_translation_interrupted_without_calling_model(self):
        copy = self.copy()
        raw = self.service.store.get(copy["episode_id"])
        raw["localization"]["job"] = dict(status="running", request_id="lost-request")
        self.service.store.save(raw)
        view = self.service.get(copy["episode_id"])
        self.assertEqual(view["localization"]["job"]["status"], "interrupted")
        self.assertEqual(self.calls, [])

    def test_localized_render_roundtrip_keeps_original_revision_lookup(self):
        copy = self.copy()
        localized = self.render_store.get(copy["scenes"][1]["localization"]["frozen_project_id"])
        self.assertEqual(localized.localization_parent_project_id, self.source_projects[1].project_id)
        self.assertEqual(len(localized.attempts), 2)
        self.assertEqual(self.render_store.find_source_revision("session-1", "revision-1"), self.source_projects[1])

    def test_two_episodes_are_translated_once_each_and_keep_all_source_documents(self):
        first = self.service.store.get(self.source["episode_id"])
        first["series_episode_id"] = "part-1"
        self.service.store.save(first)
        second = deepcopy(first)
        second.update(episode_id="episode-" + "e" * 32, series_episode_id="part-2", title="Partie 2")
        self.service.store.save(second)
        sources = self.service.localization_catalog(first["episode_id"])["sources"]
        selections = [dict(episode_id=source["episode_id"], scenes=[dict(scene_id=s["id"],
            **{k: s["choices"][0][k] for k in ("preparation_id", "project_id", "attempt_id", "token")})
            for s in source["scenes"]]) for source in sources]
        group = self.service.create_localization(first["episode_id"], language="English", model_id=contract.DEFAULT_MODEL,
            selections=selections, request_id="multi-copy-request")
        self.service.start_localization(group["episode_ids"][0], expected_revisions={i: 1 for i in group["episode_ids"]},
            model_id=contract.DEFAULT_MODEL, mode="translate", request_id="multi-start-request")
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(all(self.service.get(i)["localization"]["job"]["status"] == "succeeded" for i in group["episode_ids"]))
        self.assertEqual(self.composition.calls, [])

    def test_localized_render_rejects_prompt_rewrite_before_llm_or_recipe_call(self):
        copy = self.copy()
        project_id = copy["scenes"][0]["localization"]["frozen_project_id"]
        self.fork_service.workflow_for_mode = Mock(side_effect=AssertionError("must not resolve recipe"))
        with self.assertRaises(ValueError):
            self.fork_service.prepare_attempt(project_id, prompt="Rewrite everything", settings=self.source_projects[0].attempts[0].settings)
        with self.assertRaises(ValueError):
            list(self.fork_service.stream_chat(project_id, "Rewrite everything"))
        self.assertEqual(self.calls, [])

    def test_changed_video_duration_requires_regeneration_of_a_silent_scene(self):
        copy = self.copy()
        raw = self.service.store.get(copy["episode_id"])
        scene = raw["scenes"][1]
        scene["render_setup"]["settings"]["duration_seconds"] = 7
        raw["video_chain"] = dict(items=[dict(scene_id=scene["id"], status="pending")])
        self.service._reuse_localized_chain(raw)
        self.assertEqual(raw["video_chain"]["items"][0]["status"], "pending")

    def test_dlss_already_copied_is_not_queued_again(self):
        copy = self.copy()
        scene = copy["scenes"][1]
        raw = self.service.store.get(copy["episode_id"])
        raw["video_chain"] = dict(chain_id="chain-copy", status="completed", auto_dlss=True,
            items=[dict(scene_id=scene["id"], status="succeeded", dlss_job_id=None)])
        self.service.store.save(raw)
        self.service._queue_chain_dlss(copy["episode_id"], "chain-copy", scene["id"],
            scene["preparations"][-1]["render_project_id"], scene["video_attempt"]["attempt_id"])
        self.assertEqual(self.dlss.calls, [])
        saved = self.service.store.get(copy["episode_id"])["video_chain"]["items"][0]
        self.assertEqual(saved["dlss_status"], "succeeded")
