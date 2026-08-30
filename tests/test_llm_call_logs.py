import json
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.application import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    ImageInput,
    LlmCallApplicationOutcome,
    LlmCallImage,
    LlmCallRecord,
    LlmCallStatus,
    StreamEventKind,
    StreamPhase,
)
from panelforge.infrastructure.llm import LoggedMultimodalGateway
from panelforge.infrastructure.storage import LocalLlmCallStore


START = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
SHA = "a" * 64


def sample_record(index: int) -> LlmCallRecord:
    return LlmCallRecord(
        call_id=f"call-{index}",
        operation_id="reference.observe",
        requested_model_id="vision-model",
        actual_model_id="vision-model",
        started_at=START,
        duration_ms=index,
        status=LlmCallStatus.SUCCEEDED,
        system_prompt="System",
        user_prompt="User",
        images=(LlmCallImage("Image 1", "image/png", 8, SHA),),
        temperature=0.2,
        max_tokens=32768,
        response_text=f"Response {index}",
        finish_reason="stop",
        prompt_tokens=10,
        completion_tokens=5,
        error_type=None,
        error_message=None,
    )


class LocalLlmCallStoreTest(unittest.TestCase):
    def test_keeps_only_twenty_newest_calls_without_image_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalLlmCallStore(directory)
            for index in range(25):
                store.append(sample_record(index))

            records = store.list()

            self.assertEqual(len(records), 20)
            self.assertEqual(records[0].call_id, "call-24")
            self.assertEqual(records[-1].call_id, "call-5")
            raw = json.loads(
                (Path(directory) / "llm_calls.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(raw["calls"]), 20)
            self.assertNotIn("image-content", json.dumps(raw))

    def test_round_trip_preserves_an_unlimited_output_request(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalLlmCallStore(directory)
            store.append(replace(sample_record(1), max_tokens=None))

            self.assertIsNone(store.list()[0].max_tokens)
            raw = json.loads(
                (Path(directory) / "llm_calls.json").read_text(encoding="utf-8")
            )
            self.assertIsNone(raw["calls"][0]["max_tokens"])

    def test_reads_v1_and_rewrites_it_as_v2_on_the_next_append(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalLlmCallStore(directory)
            store.append(sample_record(1))
            path = Path(directory) / "llm_calls.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["schema_version"] = 1
            for call in raw["calls"]:
                call.pop("application_outcome")
                call.pop("application_error_type")
                call.pop("application_error_message")
            path.write_text(json.dumps(raw), encoding="utf-8")

            migrated = store.list()[0]
            self.assertIsNone(migrated.application_outcome)
            store.append(sample_record(2))

            rewritten = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(rewritten["schema_version"], 2)
            self.assertIn("application_outcome", rewritten["calls"][0])


class SuccessfulGateway:
    def list_models(self):
        return ()

    def complete(self, request):
        return CompletionResult(
            model_id=request.model_id,
            content="Done",
            prompt_tokens=9,
            completion_tokens=2,
            finish_reason="stop",
        )

    def stream(self, request):
        yield CompletionStreamEvent(
            kind=StreamEventKind.DELTA,
            phase=StreamPhase.GENERATING,
            text="Partial",
        )
        yield CompletionStreamEvent(
            kind=StreamEventKind.TRUNCATED,
            phase=StreamPhase.TRUNCATED,
            text="Partial",
            result=CompletionResult(
                model_id=request.model_id,
                content="Partial",
                finish_reason="length",
            ),
        )


class FailingGateway(SuccessfulGateway):
    def complete(self, request):
        raise RuntimeError("server unavailable")


class BlockingGateway(SuccessfulGateway):
    def __init__(self):
        self.entered = Event()
        self.release = Event()

    def complete(self, request):
        self.entered.set()
        self.release.wait(2)
        return super().complete(request)


class TerminalGateway(SuccessfulGateway):
    def stream(self, request):
        yield CompletionStreamEvent(
            kind=StreamEventKind.COMPLETED,
            phase=StreamPhase.COMPLETED,
            text="Done",
            result=CompletionResult(
                model_id=request.model_id,
                content="Done",
                finish_reason="stop",
            ),
        )


class DeltaThenTerminalGateway(TerminalGateway):
    def stream(self, request):
        yield CompletionStreamEvent(
            kind=StreamEventKind.DELTA,
            phase=StreamPhase.GENERATING,
            text="Partial",
        )
        yield from super().stream(request)


class ReasoningThenTerminalGateway(TerminalGateway):
    def stream(self, request):
        yield CompletionStreamEvent(
            kind=StreamEventKind.REASONING,
            phase=StreamPhase.GENERATING,
            text="Private reasoning that must not be journaled.",
        )
        yield CompletionStreamEvent(
            kind=StreamEventKind.DELTA,
            phase=StreamPhase.GENERATING,
            text="Done",
        )
        yield from super().stream(request)


class LoggedMultimodalGatewayTest(unittest.TestCase):
    def test_exposes_only_calls_that_are_currently_running(self):
        with tempfile.TemporaryDirectory() as directory:
            delegate = BlockingGateway()
            gateway = LoggedMultimodalGateway(
                delegate,
                LocalLlmCallStore(directory),
                id_factory=lambda: "call-active",
            )
            request = CompletionRequest(
                model_id="vllm::qwen",
                system_prompt="System",
                user_prompt="User",
                operation_id="krea2.assisted.creation_chat@0.3.0",
            )
            worker = Thread(target=gateway.complete, args=(request,))

            worker.start()
            self.assertTrue(delegate.entered.wait(1))
            self.assertEqual(gateway.active_calls()[0].call_id, "call-active")
            self.assertEqual(gateway.active_calls()[0].model_id, "vllm::qwen")
            delegate.release.set()
            worker.join(2)

            self.assertFalse(worker.is_alive())
            self.assertEqual(gateway.active_calls(), ())

    def test_records_complete_and_truncated_stream_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalLlmCallStore(directory)
            timer_values = iter((10.0, 10.25, 20.0, 20.5))
            ids = iter(("call-complete", "call-stream"))
            gateway = LoggedMultimodalGateway(
                SuccessfulGateway(),
                store,
                clock=lambda: START,
                timer=lambda: next(timer_values),
                id_factory=lambda: next(ids),
            )
            request = CompletionRequest(
                model_id="vision-model",
                system_prompt="System",
                user_prompt="User",
                images=(ImageInput("image/png", b"image-content", "Image 1"),),
                operation_id="reference.observe",
            )

            completed_result = gateway.complete(request)
            stream_events = list(gateway.stream(request))

            streamed, completed = store.list()
            self.assertEqual(streamed.status, LlmCallStatus.TRUNCATED)
            self.assertEqual(streamed.response_text, "Partial")
            self.assertEqual(streamed.finish_reason, "length")
            self.assertEqual(streamed.duration_ms, 500)
            self.assertEqual(completed.status, LlmCallStatus.SUCCEEDED)
            self.assertEqual(completed_result.call_id, completed.call_id)
            self.assertEqual(stream_events[-1].result.call_id, streamed.call_id)
            self.assertEqual(completed.duration_ms, 250)
            self.assertEqual(completed.images[0].byte_size, len(b"image-content"))

    def test_records_errors_without_swallowing_them(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalLlmCallStore(directory)
            gateway = LoggedMultimodalGateway(
                FailingGateway(),
                store,
                clock=lambda: START,
                timer=iter((1.0, 1.1)).__next__,
                id_factory=lambda: "call-failed",
            )
            request = CompletionRequest(
                model_id="vision-model",
                system_prompt="System",
                user_prompt="User",
                operation_id="reference.observe",
            )

            with self.assertRaisesRegex(RuntimeError, "server unavailable"):
                gateway.complete(request)

            record = store.list()[0]
            self.assertEqual(record.status, LlmCallStatus.FAILED)
            self.assertEqual(record.error_type, "RuntimeError")
            self.assertEqual(record.error_message, "server unavailable")

    def test_terminal_model_result_stays_succeeded_when_consumer_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalLlmCallStore(directory)
            gateway = LoggedMultimodalGateway(
                TerminalGateway(),
                store,
                clock=lambda: START,
                timer=iter((1.0, 1.1)).__next__,
                id_factory=lambda: "call-terminal",
            )
            stream = gateway.stream(
                CompletionRequest("vision-model", "System", "User")
            )

            terminal = next(stream)
            self.assertEqual(terminal.kind, StreamEventKind.COMPLETED)
            self.assertEqual(terminal.result.call_id, "call-terminal")
            gateway.report_application_outcome(
                terminal.result.call_id,
                LlmCallApplicationOutcome.ACCEPTED,
            )
            stream.close()

            record = store.list()[0]
            self.assertEqual(record.status, LlmCallStatus.SUCCEEDED)
            self.assertIsNone(record.error_type)
            self.assertEqual(record.response_text, "Done")
            self.assertEqual(
                record.application_outcome,
                LlmCallApplicationOutcome.ACCEPTED,
            )

    def test_closing_before_terminal_result_is_still_cancelled(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalLlmCallStore(directory)
            gateway = LoggedMultimodalGateway(
                DeltaThenTerminalGateway(),
                store,
                clock=lambda: START,
                timer=iter((1.0, 1.1)).__next__,
                id_factory=lambda: "call-cancelled",
            )
            stream = gateway.stream(
                CompletionRequest("vision-model", "System", "User")
            )

            self.assertEqual(next(stream).kind, StreamEventKind.DELTA)
            stream.close()

            record = store.list()[0]
            self.assertEqual(record.status, LlmCallStatus.CANCELLED)
            self.assertEqual(record.error_type, "GeneratorExit")

    def test_reasoning_events_pass_through_but_never_enter_response_log(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalLlmCallStore(directory)
            gateway = LoggedMultimodalGateway(
                ReasoningThenTerminalGateway(),
                store,
                clock=lambda: START,
                timer=iter((1.0, 1.1)).__next__,
                id_factory=lambda: "call-reasoning",
            )

            events = list(
                gateway.stream(
                    CompletionRequest(
                        "vision-model",
                        "System",
                        "User",
                        include_reasoning=True,
                    )
                )
            )

            self.assertEqual(events[0].kind, StreamEventKind.REASONING)
            self.assertEqual(
                events[0].text,
                "Private reasoning that must not be journaled.",
            )
            record = store.list()[0]
            self.assertEqual(record.status, LlmCallStatus.SUCCEEDED)
            self.assertEqual(record.response_text, "Done")
            self.assertNotIn("Private reasoning", record.response_text)


if __name__ == "__main__":
    unittest.main()
