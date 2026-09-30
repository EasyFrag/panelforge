"""User-run thumbnail regressions. No real model/GPU clients or workers."""
from copy import deepcopy
from dataclasses import dataclass
import json
import unittest

from panelforge.application import story_thumbnail_assistance
from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.application.qwen_edit import QwenEditService
from tests.test_story_v2_preparation import engine, image_request


@dataclass(frozen=True)
class FakeRecipe:
    recipe_id: str = "fake-thumbnail"
    version: str = "1"


class Gateway:
    def __init__(self, prompt, hook=None, interrupted=False):
        self.raw = json.dumps({"message": "Une scène avec les personnages utiles.", "prompt": prompt})
        self.requests, self.hook, self.interrupted = [], hook, interrupted

    def stream(self, request):
        self.requests.append(request)
        yield CompletionStreamEvent(StreamEventKind.DELTA, StreamPhase.GENERATING, self.raw)
        if self.hook:
            self.hook()
        if self.interrupted:
            raise OSError("stream interrupted")
        yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED,
            result=CompletionResult(request.model_id, self.raw, finish_reason="stop"))


class StoryThumbnailReferencesTest(unittest.TestCase):
    def prepare(self, prompt, *, service=None, thumbnail=True, source=None, hook=None, interrupted=False):
        service = service or engine()
        service.workflow.reference = FakeRecipe()
        service.gateway = Gateway(prompt, hook, interrupted)
        request = {**image_request(8 if source else 9), "thumbnail": thumbnail, "source_asset_id": source}
        project = service.ensure_story_image(**request)
        stage = project["stages"][0]
        project, message_id = service.begin_message(project["id"], stage["id"], revision=stage["revision"],
            request_id="one-thumbnail", render_after_prompt=True)
        return service, project["id"], stage["id"], message_id

    def execute(self, values):
        service, project_id, stage_id, message_id = values
        service.execute_message(project_id, stage_id, message_id)
        return service.get(project_id)["stages"][0]

    def test_nine_candidates_become_four_matching_images_without_losing_original_trace(self):
        raw_prompt = ('Bananito <Picture 1> and Cerisa <Picture 2> hold baby <Picture 4> '
                      'in apartment <Picture 6>. The hair of <Picture 4> is green. Title "La mèche verte".')
        values = self.prepare(raw_prompt)
        service, project_id, stage_id, message_id = values
        original = deepcopy(service.get(project_id)["stages"][0]["messages"][0])
        stage = self.execute(values)
        message = stage["messages"][0]
        self.assertEqual(message["status"], "succeeded", message.get("error"))
        self.assertEqual(message["auto_render"]["status"], "queued")
        attempt = stage["attempts"][0]
        inputs = attempt["context"]["render_inputs"]
        self.assertEqual([r["asset_id"] for r in inputs], ["asset-0", "asset-1", "asset-3", "asset-5"])
        self.assertEqual([r["tag"] for r in inputs], [f"<Picture {i}>" for i in range(1, 5)])
        self.assertIn("baby <Picture 3>", attempt["prompt"])
        self.assertIn("apartment <Picture 4>", attempt["prompt"])
        self.assertIn('Title "La mèche verte"', attempt["prompt"])
        self.assertEqual(attempt["prompt"].count("<Picture 3>"), 2)
        self.assertEqual(message["raw"], service.gateway.raw)
        self.assertEqual(message["context"], original["context"])
        self.assertEqual(message["fingerprint"], original["fingerprint"])
        self.assertNotEqual(message["fingerprint"], message["applied_fingerprint"])
        self.assertEqual(message["applied_fingerprint"], service.policy.context_fingerprint(stage))
        self.assertEqual(attempt["prompt_policy_version"], story_thumbnail_assistance.VERSION)
        self.assertEqual(service.gateway.requests[0].operation_id, "minimax.story-thumbnail@1.0.0")
        self.assertEqual(len(service.gateway.requests[0].images), 9)
        self.assertTrue(all(i.label.startswith("CANDIDATE ") for i in service.gateway.requests[0].images))
        self.assertTrue(service.policy.prompt_is_ready(stage))
        service.execute_message(project_id, stage_id, message_id)
        service._queue_message_render(project_id, stage_id, message_id)
        self.assertEqual(len(service.get(project_id)["stages"][0]["attempts"]), 1)
        self.assertEqual(len(service.gateway.requests), 1)
        self.assertEqual(len(service._render_queue), 1)
        service.comfy.submit_workflow.assert_not_called()

    def test_bad_or_missing_labels_fail_before_changing_references_or_queuing(self):
        for prompt in ("Compose a thumbnail.", "Use <Picture 10>.", "Use <Picture 0>.",
                       "Use <Picture 1> and <image2>.", "Use <Picture 1> and <Video 2>.",
                       "Use <Picture 1> and <picture 2>.", "Use <Picture 01>."):
            with self.subTest(prompt=prompt):
                stage = self.execute(self.prepare(prompt))
                self.assertEqual(stage["messages"][0]["status"], "failed")
                self.assertEqual(stage["attempts"], [])
                self.assertTrue(all(r["active"] for r in stage["references"]))

    def test_qwen_subset_keeps_its_labels_and_original_candidate_order(self):
        values = self.prepare("<Subject 1> uses <image9> beside <image3>. Retain <image9>'s identity.",
                              service=engine(QwenEditService))
        service = values[0]
        stage = self.execute(values)
        self.assertEqual(stage["messages"][0]["auto_render"]["status"], "queued")
        self.assertEqual([r["asset_id"] for r in stage["attempts"][0]["context"]["render_inputs"]],
                         ["asset-2", "asset-8"])
        self.assertEqual(stage["prompt"], "<Subject 1> uses <image2> beside <image1>. Retain <image2>'s identity.")
        self.assertTrue(service.policy.prompt_is_ready(stage))

    def test_regular_compositions_and_variants_still_require_all_references(self):
        for source in (None, "asset-source"):
            with self.subTest(source=source):
                values = self.prepare("Use <Picture 1>.", thumbnail=False, source=source)
                # Source plus eight references stays within the MiniMax limit.
                stage = self.execute(values)
                self.assertNotIn("reference_selection", stage["messages"][0])
                self.assertEqual(stage["messages"][0]["status"], "failed")
                self.assertEqual(stage["attempts"], [])
                self.assertTrue(all(r["active"] for r in stage["references"]))

    def test_changed_candidate_context_prevents_selection_and_render(self):
        values = self.prepare("Use <Picture 1> and <Picture 4>.")
        service, project_id, stage_id, _ = values
        def changed():
            stage = service.get(project_id)["stages"][0]
            refs = deepcopy(stage["references"])
            refs[0]["role"] = "A new role entered during the call"
            service.update(project_id, stage_id, revision=stage["revision"], changes={"references": refs})
        service.gateway.hook = changed
        stage = self.execute(values)
        self.assertFalse(stage["messages"][0]["applied"])
        self.assertEqual(stage["messages"][0]["auto_render"]["status"], "skipped")
        self.assertTrue(all(r["active"] for r in stage["references"]))
        self.assertEqual(stage["attempts"], [])

    def test_changed_settings_preserve_selected_prompt_but_prevent_auto_render(self):
        values = self.prepare("Use <Picture 1> and <Picture 4>.")
        service, project_id, stage_id, _ = values
        def changed():
            stage = service.get(project_id)["stages"][0]
            service.update(project_id, stage_id, revision=stage["revision"],
                           changes={"settings": {**stage["settings"], "steps": 21}})
        service.gateway.hook = changed
        stage = self.execute(values)
        self.assertTrue(stage["messages"][0]["applied"])
        self.assertEqual(stage["messages"][0]["auto_render"]["status"], "skipped")
        self.assertTrue(service.policy.prompt_is_ready(stage))
        self.assertEqual(len(service.policy.render_inputs(stage)), 2)
        self.assertEqual(stage["attempts"], [])

    def test_interrupted_response_can_be_recovered_without_automatic_generation(self):
        values = self.prepare("Use <Picture 2> and <Picture 6>.", interrupted=True)
        service, project_id, stage_id, message_id = values
        stage = self.execute(values)
        self.assertTrue(stage["messages"][0]["recovery_available"])
        self.assertEqual(stage["messages"][0]["status"], "failed")
        for _ in range(2):
            project = service.recover_message(project_id, stage_id, message_id, revision=stage["revision"])
            stage = project["stages"][0]
            self.assertEqual(stage["prompt"], "Use <Picture 1> and <Picture 2>.")
            self.assertTrue(service.policy.prompt_is_ready(stage))
            self.assertEqual(stage["attempts"], [])
            self.assertEqual(len(stage["messages"][0]["context"]["render_inputs"]), 9)
        self.assertEqual(len(service.gateway.requests), 1)

    def test_thumbnail_selection_cannot_remove_a_fixed_source(self):
        with self.assertRaisesRegex(ValueError, "sans source"):
            self.prepare("Use <Picture 1>.", source="asset-source")
        service = engine()
        project = service.ensure_story_image(**image_request(2))
        context = service.policy.context_snapshot(project["stages"][0])
        context["source_asset_id"] = "source"
        with self.assertRaisesRegex(ValueError, "source"):
            story_thumbnail_assistance.decode(json.dumps({"message": "ok", "prompt": "Use <Picture 1>."}),
                                              context, service.policy)


if __name__ == "__main__":
    unittest.main()
