"""Qwen workshop regressions with local assets and fake model/render gateways."""

from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image

from panelforge.application.machine_work import MachineWorkCoordinator
from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, ModelDescriptor, StreamEventKind, StreamPhase
from panelforge.application.qwen_edit import QwenEditService, QwenEditConflict
from panelforge.domain.qwen_edit import QwenEditSettings, prompt_is_ready, render_inputs
from panelforge.domain.production import ComputeResource, ProductionWorkload
from panelforge.infrastructure.presets.qwen_edit import load_qwen_edit_workflow
from panelforge.infrastructure.qwen_edit_images import PillowQwenEditImages
from panelforge.infrastructure.qwen_project_exports import LocalQwenProjectExporter, project_zip
from panelforge.infrastructure.storage.local import LocalAssetStore
from panelforge.infrastructure.storage.qwen_edits import LocalQwenEditStore


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflows/image.edit/qwen-image-2.1/1.0.0"


def png(color="navy", size=(160, 96)):
    result = BytesIO()
    Image.new("RGB", size, color).save(result, "PNG")
    return result.getvalue()


class Gateway:
    def __init__(self):
        self.requests, self.outcomes = [], []
        self.hook = None
        self.fail_after_delta = False
        self.malformed = False

    def list_models(self):
        return (ModelDescriptor("fake-vision"),)

    def report_application_outcome(self, *args, **kwargs):
        self.outcomes.append((args, kwargs))

    def stream(self, request):
        self.requests.append(request)
        inputs = json.loads(request.user_prompt)["CURRENT INPUTS"]["render_inputs"]
        prompt = "Compose naturally with " + ", ".join(f"{r['tag']} as {r['name']}" for r in inputs) + ". Preserve untargeted content."
        raw = "invalid partial {" if self.malformed else json.dumps({"message": "Je conserve le décor et place les personnages.", "prompt": prompt})
        yield CompletionStreamEvent(StreamEventKind.REASONING, StreamPhase.GENERATING, "Reasoning received from the fake model.")
        yield CompletionStreamEvent(StreamEventKind.DELTA, StreamPhase.GENERATING, raw)
        if self.hook:
            self.hook()
        if self.fail_after_delta:
            raise OSError("stream interrupted")
        yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED,
            result=CompletionResult(request.model_id, raw, finish_reason="stop", call_id="fake-call"))


class Comfy:
    def __init__(self):
        self.uploads, self.submitted, self.cancelled = [], [], []
        self.output = png("green")

    def upload_image(self, content, *, filename, subfolder):
        self.uploads.append((content, filename))
        return SimpleNamespace(workflow_value=f"{subfolder}/{filename}")

    def submit_workflow(self, graph):
        self.submitted.append(graph)
        return "fake-execution"

    def get_history(self, execution_id):
        return {execution_id: {"status": {"completed": True, "status_str": "success"},
            "outputs": {"56": {"images": [{"filename": "result.png", "subfolder": "test", "type": "output"}]}}}}

    def download_output(self, **kwargs):
        return self.output

    def cancel_execution(self, execution_id):
        self.cancelled.append(execution_id)
        return SimpleNamespace(action="cancel_job")


class QwenEditFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.assets = LocalAssetStore(self.temporary.name)
        self.store = LocalQwenEditStore(self.temporary.name)
        self.gateway, self.comfy = Gateway(), Comfy()
        self.workflow = load_qwen_edit_workflow(WORKFLOW)
        self.service = QwenEditService(gateway=self.gateway, workflow=self.workflow, comfy=self.comfy,
            assets=self.assets, projects=self.store, images=PillowQwenEditImages(), poll_interval=.001,
            exporter=LocalQwenProjectExporter(Path(self.temporary.name) / "exports"))
        self.project = self.service.create(name="Composition test", content=png())
        self.project_id = self.project["id"]
        self.stage_id = self.project["active_stage_id"]

    def current(self):
        self.project = self.service.get(self.project_id)
        return next(s for s in self.project["stages"] if s["id"] == self.stage_id)

    def update(self, **changes):
        s = self.current()
        self.project = self.service.update(self.project_id, self.stage_id, revision=s["revision"], changes=changes)
        return self.current()

    def reference(self, name, usage, color="red"):
        s = self.current()
        self.service.add_reference(self.project_id, self.stage_id, revision=s["revision"],
                                   name=name, usage=usage, content=png(color))
        return self.current()["references"][-1]

    def message(self, text="Place les personnages et garde le décor."):
        s = self.update(draft=text, model_id="fake-vision")
        _, message_id = self.service.begin_message(self.project_id, self.stage_id, revision=s["revision"], request_id="message-request")
        self.service.execute_message(self.project_id, self.stage_id, message_id)
        return self.current()["messages"][-1]

    def queue(self, request_id="render-request"):
        s = self.current()
        self.service.queue_attempt(self.project_id, self.stage_id, revision=s["revision"], request_id=request_id)
        return self.current()["attempts"][-1]

    def render(self):
        a = self.queue()
        self.service.execute_attempt(self.project_id, self.stage_id, a["id"])
        return self.current()["attempts"][-1]


class QwenEditSchedulingTest(QwenEditFixture):
    def test_queued_render_uses_the_same_requirement_even_after_project_rename(self):
        coordinator = MachineWorkCoordinator(monitor_interval=.001)
        self.service.work_coordinator = coordinator
        self.update(prompt="Recolor the wall in <image1> blue. Preserve everything else.")
        for rename in (False, True):
            with self.subTest(rename=rename):
                attempt = self.queue(request_id=f"render-{rename}")
                self.assertTrue(coordinator.has_activity(attempt["id"]))
                if rename:
                    self.update(name="Renamed while queued")
                self.service.execute_attempt(self.project_id, self.stage_id, attempt["id"])
                result = self.current()["attempts"][-1]
                self.assertEqual(result["status"], "succeeded", result["error"])
                self.assertEqual(result["execution_id"], "fake-execution")
                self.assertTrue(result["output_asset_id"])
                self.assertFalse(coordinator.has_activity(attempt["id"]))
        self.assertEqual(len(self.comfy.submitted), 2)
        self.assertEqual(self.gateway.requests, [])

    def test_older_queued_attempt_without_operation_snapshot_can_resume(self):
        self.update(prompt="Recolor the wall in <image1> blue.")
        attempt = self.queue()
        project = self.store.get(self.project_id)
        project["stages"][0]["attempts"][-1].pop("work_operation")
        self.store.save(project)
        self.service.work_coordinator = MachineWorkCoordinator(monitor_interval=.001)
        self.service.execute_attempt(self.project_id, self.stage_id, attempt["id"])
        result = self.current()["attempts"][-1]
        self.assertEqual(result["status"], "succeeded", result["error"])
        self.assertEqual(len(self.comfy.submitted), 1)
        self.assertFalse(self.service.work_coordinator.has_activity(attempt["id"]))

    def test_admission_failure_releases_only_its_own_queue_reservation(self):
        coordinator = MachineWorkCoordinator(monitor_interval=.001)
        self.service.work_coordinator = coordinator
        self.update(prompt="Recolor the wall in <image1> blue.")
        attempt = self.queue()
        coordinator.enqueue("following-job", ComputeResource.REMOTE_GPU,
                            ProductionWorkload.IMAGE_RENDER, "Another workshop")
        self.addCleanup(coordinator.cancel_queued, "following-job")
        with patch.object(coordinator, "lease", side_effect=ValueError("Admission unavailable")):
            self.service.execute_attempt(self.project_id, self.stage_id, attempt["id"])
        result = self.current()["attempts"][-1]
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"], "Admission unavailable")
        self.assertIsNotNone(result["finished_at"])
        self.assertIsNone(result["execution_id"])
        self.assertFalse(coordinator.has_activity(attempt["id"]))
        self.assertTrue(coordinator.has_activity("following-job"))
        self.assertEqual(self.comfy.uploads, [])
        self.assertEqual(self.comfy.submitted, [])


class QwenEditTest(QwenEditFixture):
    def test_inspirations_reach_the_llm_but_never_the_qwen_uploads(self):
        inspiration = self.reference("Palette", "assistant", "yellow")
        self.message("Reprends les couleurs de Palette.")
        request = self.gateway.requests[0]
        self.assertEqual(len(request.images), 2)
        self.assertIn("ASSISTANT ONLY", request.images[1].label)
        self.assertEqual(request.images[1].content, self.assets.read_bytes(inspiration["asset_id"]))
        attempt = self.render()
        self.assertEqual(attempt["status"], "succeeded")
        self.assertEqual(len(self.comfy.uploads), 1)
        self.assertEqual([r["id"] for r in attempt["context"]["render_inputs"]], ["source"])
        self.assertEqual(len(self.gateway.requests), 1)

    def test_two_characters_and_one_inspiration_have_distinct_stable_roles(self):
        lea = self.reference("Léa", "render", "red")
        marc = self.reference("Marc", "render", "blue")
        self.reference("Ambiance", "assistant", "yellow")
        self.message()
        self.assertEqual([r["id"] for r in render_inputs(self.current())], ["source", lea["id"], marc["id"]])
        self.assertEqual(len(self.gateway.requests[0].images), 4)
        attempt = self.queue()
        snapshot = deepcopy(attempt)
        refs = deepcopy(self.current()["references"])
        refs[0]["usage"] = "assistant"
        self.update(references=refs, settings={**self.current()["settings"], "steps": 30})
        self.assertFalse(prompt_is_ready(self.current()))
        self.service.execute_attempt(self.project_id, self.stage_id, attempt["id"])
        graph = self.comfy.submitted[0]
        self.assertEqual(len(self.comfy.uploads), 3)
        self.assertEqual(graph["3"]["inputs"]["steps"], 25)
        self.assertEqual(self.current()["attempts"][0]["context"], snapshot["context"])
        with self.assertRaisesRegex(ValueError, "actualiser"):
            self.queue("another-render")

    def test_reference_change_during_the_llm_call_keeps_the_reply_without_applying_it(self):
        self.reference("Palette", "assistant")
        def change():
            refs = deepcopy(self.current()["references"])
            refs[0]["usage"] = "render"
            self.update(references=refs)
        self.gateway.hook = change
        message = self.message()
        self.assertEqual(message["status"], "succeeded")
        self.assertFalse(message["applied"])
        self.assertEqual(self.current()["prompt"], "")
        self.assertTrue(message["raw"])

    def test_manual_prompt_wins_over_late_assistant_reply(self):
        self.gateway.hook = lambda: self.update(prompt="Recolor only the wall burgundy.")
        message = self.message()
        self.assertFalse(message["applied"])
        self.assertEqual(self.current()["prompt"], "Recolor only the wall burgundy.")

    def test_interrupted_stream_keeps_all_received_text_and_reasoning(self):
        self.gateway.fail_after_delta = True
        message = self.message()
        self.assertEqual(message["status"], "failed")
        self.assertIn("Compose naturally", message["raw"])
        self.assertIn("Reasoning received", message["reasoning"])
        self.assertTrue(message["recovery_available"])
        self.service.recover_message(self.project_id, self.stage_id, message["id"], revision=self.current()["revision"])
        self.assertTrue(prompt_is_ready(self.current()))
        self.assertEqual(len(self.gateway.requests), 1)

    def test_malformed_json_is_kept_and_is_not_advertised_as_recoverable(self):
        self.gateway.malformed = True
        message = self.message()
        self.assertEqual(message["status"], "failed")
        self.assertEqual(message["raw"], "invalid partial {")
        self.assertFalse(message["recovery_available"])
        self.assertEqual(len(self.gateway.requests), 1)

    def test_autosave_settings_draft_and_64_bit_seed_survive_a_new_store(self):
        settings = {**self.current()["settings"], "steps": 28, "seed": str(2**64 - 1)}
        self.update(settings=settings, draft="Un brouillon pas encore envoyé.")
        restored = LocalQwenEditStore(self.temporary.name).get(self.project_id)["stages"][0]
        self.assertEqual(restored["settings"], settings)
        self.assertEqual(restored["draft"], "Un brouillon pas encore envoyé.")
        self.assertEqual(self.gateway.requests, [])

    def test_revision_conflict_does_not_overwrite_a_newer_draft(self):
        stale = self.current()["revision"]
        self.update(draft="Nouvelle demande")
        with self.assertRaises(QwenEditConflict):
            self.service.update(self.project_id, self.stage_id, revision=stale, changes={"draft": "Ancienne demande"})
        self.assertEqual(self.current()["draft"], "Nouvelle demande")

    def test_accept_preserves_history_and_starts_a_clean_stage_with_the_selected_result(self):
        self.reference("Palette", "assistant")
        self.message()
        attempt = self.render()
        old = self.current()
        project = self.service.accept(self.project_id, self.stage_id, attempt["id"], revision=old["revision"])
        following = project["stages"][-1]
        self.assertEqual(following["source_asset_id"], attempt["output_asset_id"])
        self.assertEqual(following["references"], [])
        self.assertEqual(following["messages"], [])
        self.assertEqual(following["prompt"], "")
        self.assertEqual(project["stages"][0]["references"], old["references"])
        self.assertIsNone(project["export_error"])
        archive = zipfile.ZipFile(BytesIO(project_zip(project, self.assets, self.store)))
        record = json.loads(archive.read("project.json"))
        self.assertIn(old["references"][0]["asset_id"], record["asset_files"])
        self.assertIn(f"workflows/{attempt['id']}.json", archive.namelist())

    def test_restoring_an_attempt_keeps_new_references_available_in_the_archive(self):
        self.reference("Léa", "render")
        self.message()
        attempt = self.render()
        newer = self.reference("Inspiration suivante", "assistant", "yellow")
        self.service.restore_attempt(self.project_id, self.stage_id, attempt["id"], revision=self.current()["revision"])
        restored = self.current()
        self.assertTrue(prompt_is_ready(restored))
        self.assertFalse(next(r for r in restored["references"] if r["id"] == newer["id"])["active"])
        self.assertEqual([r["id"] for r in render_inputs(restored)], [r["id"] for r in attempt["context"]["render_inputs"]])

    def test_idempotent_queue_and_cancel_never_submit_a_cancelled_attempt(self):
        self.update(prompt="Make the wall burgundy.")
        attempt = self.queue()
        self.queue()
        self.assertEqual(len(self.current()["attempts"]), 1)
        self.service.cancel_attempt(self.project_id, self.stage_id, attempt["id"])
        self.service.execute_attempt(self.project_id, self.stage_id, attempt["id"])
        self.assertEqual(self.comfy.submitted, [])

    def test_new_composition_has_no_fake_source_and_references_are_identity_inputs(self):
        project = self.service.create(name="Portraits ensemble", composition=True)
        self.project_id, self.stage_id = project["id"], project["active_stage_id"]
        self.reference("Léa", "render")
        self.reference("Marc", "render", "blue")
        self.message("Réunis Léa et Marc dans un café.")
        attempt = self.render()
        self.assertIsNone(attempt["context"]["source_asset_id"])
        self.assertEqual(len(self.comfy.uploads), 2)
        self.assertEqual(self.comfy.submitted[-1]["3"]["inputs"]["latent_image"], ["62", 0])
        self.assertEqual(self.comfy.submitted[-1]["62"]["inputs"]["width"], 1024)

    def test_workflow_handles_all_slots_and_native_edit_latent_without_orphans(self):
        graph = self.workflow.build(images=[f"image-{i}.png" for i in range(16)], prompt="Use every reference.",
            settings=QwenEditSettings(), dimensions=(160, 96), composition=False, output_prefix="test/result")
        self.assertEqual(graph["3"]["inputs"]["latent_image"], ["64", 2])
        self.assertEqual(graph["3"]["inputs"]["denoise"], 1)
        self.assertNotIn("62", graph)
        self.assertEqual(len([k for k in graph["64"]["inputs"] if k.startswith("images.image_")]), 16)
        self.assertEqual(graph["64"]["inputs"]["images.image_16"], ["qwen_reference_16", 0])
        self.assertEqual(self.workflow.template["64"]["inputs"]["images.image_1"], ["77", 0])

    def test_invalid_or_missing_prompt_image_reference_is_rejected_before_queue(self):
        self.reference("Léa", "render")
        with self.assertRaisesRegex(ValueError, "chaque référence"):
            self.update(prompt="Modify <image1>.")
        with self.assertRaisesRegex(ValueError, "ne sera pas envoyée"):
            self.update(prompt="Modify <image1> using <image2> and <image3>.")
        self.assertEqual(self.current()["attempts"], [])

    def test_new_failed_request_does_not_leave_the_previous_prompt_ready(self):
        self.update(prompt="Make the wall burgundy.")
        self.gateway.malformed = True
        self.message("Finalement, déplace la table.")
        self.assertFalse(prompt_is_ready(self.current()))
        self.assertEqual(self.current()["prompt"], "Make the wall burgundy.")
        with self.assertRaisesRegex(ValueError, "actualiser"):
            self.queue()

    def test_uncertain_submission_is_not_retried_automatically(self):
        self.update(prompt="Make the wall burgundy.")
        attempt = self.queue()
        def lost_reply(graph):
            self.comfy.submitted.append(graph)
            raise TimeoutError("response lost")
        self.comfy.submit_workflow = lost_reply
        self.service.execute_attempt(self.project_id, self.stage_id, attempt["id"])
        self.service.execute_attempt(self.project_id, self.stage_id, attempt["id"])
        failed = self.current()["attempts"][0]
        self.assertEqual(len(self.comfy.submitted), 1)
        self.assertEqual(failed["status"], "failed")
        self.assertIn("Vérifie sa file", failed["error"])

    def test_resuming_a_validated_stage_keeps_both_project_versions(self):
        self.message()
        attempt = self.render()
        self.service.accept(self.project_id, self.stage_id, attempt["id"], revision=self.current()["revision"])
        previous = self.service.get(self.project_id)
        next_id = previous["active_stage_id"]
        branch = self.service.resume(self.project_id, next_id, request_id="resume-request")
        again = self.service.resume(self.project_id, next_id, request_id="resume-request")
        self.assertEqual(branch["id"], again["id"])
        self.assertNotEqual(branch["id"], previous["id"])
        self.assertEqual(self.service.get(self.project_id), previous)
        self.assertEqual(branch["stages"][0]["accepted_attempt_id"], attempt["id"])
        self.assertEqual(self.store.read_workflow(branch["id"], attempt["id"]),
                         self.store.read_workflow(previous["id"], attempt["id"]))


if __name__ == "__main__":
    unittest.main()
