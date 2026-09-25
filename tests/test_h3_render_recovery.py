"""Orphan recovery uses simulated Comfy responses; never submits a workflow."""

from dataclasses import replace
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from panelforge.application.h3_render import H3RenderService
from panelforge.domain.h3_render import H3RenderAttempt, H3RenderAttemptStatus, H3RenderInputMode, H3RenderProject
from panelforge.domain.video_lab import VideoAspectRatio, VideoLabSettings
from panelforge.infrastructure.comfy.client import ComfyHttpClient, ComfyPromptPhase, ComfyQueueEntry, ComfyQueueSnapshot
from panelforge.infrastructure.presets import H3RenderPresetRecipe, load_h3_render_workflow
from panelforge.infrastructure.storage import LocalAssetStore, LocalH3RenderProjectStore
from tests.test_h3_render import ImmediateH3Comfy, WORKFLOW_DIRECTORY


PROMPT = (
    "integrated_multimodal_description:\n[Shot 1] The camera holds a static shot. A cat walks.\n"
    "overall_soundscape:\nFootsteps.\nnon_diegetic_music:\nN/A"
)


class RecoveryComfy(ImmediateH3Comfy):
    def __init__(self, phase=None, *, arrival=False, failure=None, interrupted=False):
        super().__init__()
        self.phase = phase
        self.arrival = arrival
        self.failure = failure
        self.interrupted = interrupted
        self.reads = []

    def get_history(self, prompt_id):
        self.reads.append("history")
        if self.failure == "malformed_history":
            return []
        if self.failure == "unexpected_history":
            return {"error": "unavailable"}
        if self.failure == "history" or (self.failure == "second_history" and len(self.reads) == 3):
            raise OSError("network unavailable")
        if self.interrupted:
            return {prompt_id: {"status": {"status_str": "interrupted", "completed": False}}}
        if self.arrival and self.reads.count("history") > 1:
            return super().get_history(prompt_id)
        return {}

    def get_queue(self):
        self.reads.append("queue")
        if self.failure == "queue":
            raise OSError("network unavailable")
        entries = () if self.phase is None else (
            ComfyQueueEntry("execution-old", self.phase, 1, None),
        )
        return ComfyQueueSnapshot(
            running=entries if self.phase is ComfyPromptPhase.RUNNING else (),
            pending=entries if self.phase is ComfyPromptPhase.PENDING else (),
        )

    def submit_workflow(self, workflow):
        raise AssertionError("Recovery must never submit a workflow")

    def cancel_execution(self, prompt_id):
        raise AssertionError("Recovery must never cancel a remote workflow")


class H3RenderRecoveryTest(unittest.TestCase):
    def setup_service(self, root, comfy, *, same_project=False, cancel_pending=False):
        store = LocalH3RenderProjectStore(root)
        settings = VideoLabSettings(VideoAspectRatio.PORTRAIT_WIDESCREEN, 0.2, 9, 25, 42, seed_locked=True)
        old = H3RenderAttempt("attempt-old", 1, PROMPT, PROMPT, settings, False, ())
        old = old.queue().start("execution-old", "a" * 64)
        if cancel_pending:
            old = old.cancel_pending("Remote cancellation could not be confirmed")
        new = H3RenderAttempt("attempt-new", 2, PROMPT, PROMPT, settings, False, ())
        project = H3RenderProject(
            project_id="project-old", source_session_id="session-1",
            source_prompt_revision_id="prompt-1", model_id="model-1",
            input_mode=H3RenderInputMode.T2VA, current_prompt=PROMPT,
            attempts=(old, new) if same_project else (old,),
        )
        store.create(project)
        target = project.project_id if same_project else "project-new"
        if not same_project:
            store.create(replace(project, project_id=target, attempts=(new,)))
        service = H3RenderService(
            gateway=object(), workflow=H3RenderPresetRecipe(load_h3_render_workflow(WORKFLOW_DIRECTORY)),
            comfy=comfy, assets=LocalAssetStore(root), projects=store,
            sessions=object(), compositions=object(),
        )
        return service, target, old

    def queued_service(self, root, *, live_ticket=False, claimed=False, coordinator=True, same_project=False):
        comfy = RecoveryComfy()
        service, target, old = self.setup_service(root, comfy, same_project=same_project)
        queued = replace(old, status=H3RenderAttemptStatus.QUEUED, execution_id=None, compiled_workflow_sha256=None)
        source = service.projects.get("project-old")
        service.projects.save(source.replace_attempt(queued))
        tickets = {"h3:project-old:attempt-old"} if live_ticket else set()
        if coordinator:
            service.work_coordinator = SimpleNamespace(
                has_activity=lambda key: key in tickets,
                enqueue=lambda key, *args, **kwargs: tickets.add(key))
        if claimed:
            service._claimed.add(("project-old", "attempt-old"))
        return service, target, queued, comfy, tickets

    def test_abandoned_queued_attempt_is_terminal_and_does_not_block_new_admission(self):
        for same_project in (False, True):
            with self.subTest(same_project=same_project), tempfile.TemporaryDirectory() as root:
                service, target, original, comfy, tickets = self.queued_service(root, same_project=same_project)
                new = service.queue_attempt(target, "attempt-new")
                old = service.projects.get("project-old").attempt("attempt-old")
                self.assertEqual(old.status, H3RenderAttemptStatus.FAILED)
                self.assertIn("réservation locale", old.error)
                self.assertIsNone(old.execution_id)
                self.assertEqual((old.prompt, old.settings), (original.prompt, original.settings))
                self.assertEqual(new.attempt("attempt-new").status, H3RenderAttemptStatus.QUEUED)
                self.assertIn(f"h3:{target}:attempt-new", tickets)
                self.assertEqual(service.get("project-old").attempt("attempt-old").status, H3RenderAttemptStatus.FAILED)
                self.assertEqual(comfy.reads, [])

    def test_queued_attempt_with_live_fifo_ticket_is_never_recovered(self):
        with tempfile.TemporaryDirectory() as root:
            service, target, _, comfy, tickets = self.queued_service(root, live_ticket=True)
            service.queue_attempt(target, "attempt-new")
            self.assertEqual(service.get("project-old").attempt("attempt-old").status, H3RenderAttemptStatus.QUEUED)
            self.assertIn("h3:project-old:attempt-old", tickets)
            self.assertEqual(len(tickets), 2)
            self.assertEqual(comfy.reads, [])

    def test_queued_attempt_with_claim_or_without_coordinator_is_not_declared_abandoned(self):
        for options in ({"claimed": True}, {"coordinator": False}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as root:
                service, target, _, comfy, _ = self.queued_service(root, **options)
                with self.assertRaisesRegex(ValueError, "déjà actif"):
                    service.queue_attempt(target, "attempt-new")
                self.assertEqual(service.projects.get("project-old").attempt("attempt-old").status, H3RenderAttemptStatus.QUEUED)
                self.assertEqual(comfy.reads, [])

    def test_missing_remote_attempt_releases_admission_and_stays_terminal(self):
        for same_project in (False, True):
            for cancel_pending in (False, True):
                with self.subTest(same_project=same_project, cancel_pending=cancel_pending), tempfile.TemporaryDirectory() as root:
                    comfy = RecoveryComfy()
                    service, target, original = self.setup_service(root, comfy, same_project=same_project, cancel_pending=cancel_pending)
                    result = service.queue_attempt(target, "attempt-new")
                    recovered = LocalH3RenderProjectStore(root).get("project-old").attempt("attempt-old")
                    self.assertEqual(result.attempt("attempt-new").status, H3RenderAttemptStatus.QUEUED)
                    self.assertEqual(recovered.status, H3RenderAttemptStatus.FAILED)
                    self.assertIn("introuvable", recovered.error)
                    self.assertEqual(recovered.prompt, original.prompt)
                    self.assertEqual(recovered.settings, original.settings)
                    self.assertEqual(recovered.execution_id, original.execution_id)
                    self.assertEqual(comfy.reads, ["history", "queue", "history"])

    def test_remote_running_or_pending_still_blocks_other_renders(self):
        for phase in (ComfyPromptPhase.RUNNING, ComfyPromptPhase.PENDING):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as root:
                comfy = RecoveryComfy(phase)
                service, target, _ = self.setup_service(root, comfy)
                with self.assertRaisesRegex(ValueError, "déjà actif.*project-old"):
                    service.queue_attempt(target, "attempt-new")
                self.assertEqual(service.projects.get("project-old").attempt("attempt-old").status, H3RenderAttemptStatus.RUNNING)
                self.assertEqual(comfy.reads, ["history", "queue"])

    def test_network_failure_never_proves_an_execution_is_missing(self):
        for failure in ("history", "queue", "second_history", "malformed_history", "unexpected_history"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as root:
                service, target, _ = self.setup_service(root, RecoveryComfy(failure=failure))
                with self.assertRaisesRegex(ValueError, "déjà actif"):
                    service.queue_attempt(target, "attempt-new")
                self.assertEqual(service.projects.get("project-old").attempt("attempt-old").status, H3RenderAttemptStatus.RUNNING)

    def test_live_worker_claim_is_not_recovered(self):
        with tempfile.TemporaryDirectory() as root:
            comfy = RecoveryComfy()
            service, target, _ = self.setup_service(root, comfy)
            service._claimed.add(("project-old", "attempt-old"))
            with self.assertRaisesRegex(ValueError, "déjà actif"):
                service.queue_attempt(target, "attempt-new")
            self.assertEqual(comfy.reads, [])

    def test_completion_between_history_and_queue_is_imported_and_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            comfy = RecoveryComfy(arrival=True)
            service, target, _ = self.setup_service(root, comfy, same_project=True)
            result = service.queue_attempt(target, "attempt-new")
            self.assertEqual(result.attempt("attempt-old").status, H3RenderAttemptStatus.SUCCEEDED)
            self.assertIsNotNone(result.attempt("attempt-old").output_asset_id)
            self.assertEqual(result.feedback_attempt_id, "attempt-old")
            self.assertEqual(comfy.reads, ["history", "queue", "history"])

    def test_interrupted_history_releases_the_slot_without_resubmission(self):
        with tempfile.TemporaryDirectory() as root:
            service, target, _ = self.setup_service(root, RecoveryComfy(interrupted=True))
            service.queue_attempt(target, "attempt-new")
            self.assertEqual(service.projects.get("project-old").attempt("attempt-old").status, H3RenderAttemptStatus.CANCELLED)

    def test_incomplete_queue_response_is_not_treated_as_empty(self):
        client = ComfyHttpClient("http://unused.invalid", client_id="test")
        for response in ({}, {"queue_running": []}, {"queue_pending": []}, {"queue_running": None, "queue_pending": []}):
            with self.subTest(response=response), patch.object(client, "_read_json", return_value=response):
                with self.assertRaisesRegex(ValueError, "incomplete queue"):
                    client.get_queue()
        with patch.object(client, "_read_json", return_value={"queue_running": [], "queue_pending": []}):
            self.assertIsNone(client.get_queue().find("execution-old"))
