import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from panelforge.application.prompt_lab import (
    CompletionResult,
    CompletionStreamEvent,
    LlmCallApplicationOutcome,
    ModelDescriptor,
    StreamEventKind,
    StreamPhase,
)
from panelforge.application.storyboard_lab import (
    StoryboardLabService,
    StoryboardRunRequest,
)
from panelforge.domain.storyboard import (
    StoryboardCharacter,
    StoryboardEnvironment,
    StoryboardPanel,
    StoryboardSpec,
)
from panelforge.domain.storyboard_runs import StoryboardRunStatus


def neutral_spec(panel_count=2):
    panels = []
    for index in range(panel_count):
        panels.append(
            StoryboardPanel(
                present_characters=("Traveler",),
                framing="three-quarter portrait",
                camera_angle="eye level",
                visual_beat=f"The traveler completes beat {index + 1}.",
                emotional_beat="Focused and calm.",
                continuity_from_previous=(
                    None if index == 0 else f"Continues from beat {index}."
                ),
                visible_anchors=("red suitcase",),
            )
        )
    return StoryboardSpec(
        sequence_context="A traveler crosses one quiet station.",
        avoid_repeats=(),
        characters=(
            StoryboardCharacter(
                label="Traveler",
                identity_lock="Adult traveler with short dark hair.",
                wardrobe_lock="The same green coat and boots.",
                allowed_progression="The coat may become rain-spotted.",
            ),
        ),
        environment=StoryboardEnvironment(
            location_lock="The same small railway station.",
            lighting_lock="Soft overcast morning light.",
            layout_lock="Platform remains behind the traveler.",
            props_lock=("red suitcase",),
        ),
        panels=tuple(panels),
    )


class FakeRecipe:
    recipe_id = "krea2.storyboard.photorealistic"
    version = "0.1.0"
    display_name = "KREA2 storyboard"
    description = "Test recipe"
    template_sha256 = "a" * 64
    panel_counts = (2, 4, 6, 9)

    def __init__(self, *, reject=False):
        self.reject = reject
        self.parse_calls = 0

    def build_request_prompts(self, intention, panel_count):
        return "Return JSON only.", f"{panel_count} panels: {intention}"

    def parse_spec(self, raw_response, panel_count):
        self.parse_calls += 1
        if self.reject:
            raise ValueError("invalid storyboard JSON")
        return neutral_spec(panel_count)

    def compile_prompt(self, spec, panel_count):
        return f"STRICT FORMAT: exactly {panel_count} panels. {spec.sequence_context}"

    def warnings_for_spec(self, spec, panel_count):
        return ("Two adjacent beats use the same framing.",)


class FakeCatalog:
    def __init__(self, recipe):
        self.recipe = recipe

    def list(self):
        return (self.recipe,)

    def get(self, recipe_id, version):
        if (recipe_id, version) != (self.recipe.recipe_id, self.recipe.version):
            raise KeyError((recipe_id, version))
        return self.recipe


class MemoryRunStore:
    def __init__(self):
        self.values = {}

    def create(self, run):
        if run.run_id in self.values:
            raise FileExistsError(run.run_id)
        self.values[run.run_id] = run
        return run

    def save(self, run):
        if run.run_id not in self.values:
            raise FileNotFoundError(run.run_id)
        self.values[run.run_id] = run
        return run

    def get(self, run_id):
        return self.values[run_id]

    def list(self, limit=20):
        return list(self.values.values())[-limit:][::-1]


class FakeGateway:
    def __init__(self, content="candidate-json", *, finish_reason=None):
        self.content = content
        self.finish_reason = finish_reason
        self.complete_requests = []
        self.stream_requests = []

    def list_models(self):
        return (ModelDescriptor("local-model"),)

    def complete(self, request):
        self.complete_requests.append(request)
        return CompletionResult(
            model_id=request.model_id,
            content=self.content,
            finish_reason=self.finish_reason,
            call_id="call-sync",
        )

    def stream(self, request):
        self.stream_requests.append(request)
        yield CompletionStreamEvent(
            kind=StreamEventKind.STATUS,
            phase=StreamPhase.GENERATING,
            text="Generating",
        )
        if request.include_reasoning:
            yield CompletionStreamEvent(
                kind=StreamEventKind.REASONING,
                phase=StreamPhase.GENERATING,
                text="debug trace",
            )
        yield CompletionStreamEvent(
            kind=StreamEventKind.DELTA,
            phase=StreamPhase.GENERATING,
            text=self.content,
        )
        kind = (
            StreamEventKind.TRUNCATED
            if self.finish_reason == "length"
            else StreamEventKind.COMPLETED
        )
        phase = (
            StreamPhase.TRUNCATED
            if kind is StreamEventKind.TRUNCATED
            else StreamPhase.COMPLETED
        )
        yield CompletionStreamEvent(
            kind=kind,
            phase=phase,
            text=self.content,
            result=CompletionResult(
                model_id=request.model_id,
                content=self.content,
                finish_reason=self.finish_reason,
                call_id="call-stream",
            ),
        )


class ExplodingStreamGateway(FakeGateway):
    def stream(self, request):
        self.stream_requests.append(request)
        yield CompletionStreamEvent(
            kind=StreamEventKind.DELTA,
            phase=StreamPhase.GENERATING,
            text="partial draft",
        )
        raise ConnectionError("connection lost")


class BlockingStreamGateway(FakeGateway):
    def __init__(self):
        super().__init__()
        self.entered = Event()
        self.release = Event()

    def stream(self, request):
        self.stream_requests.append(request)
        self.entered.set()
        if not self.release.wait(2):
            raise TimeoutError("test release was not signalled")
        yield CompletionStreamEvent(
            kind=StreamEventKind.DELTA,
            phase=StreamPhase.GENERATING,
            text=self.content,
        )
        yield CompletionStreamEvent(
            kind=StreamEventKind.COMPLETED,
            phase=StreamPhase.COMPLETED,
            text=self.content,
            result=CompletionResult(
                model_id=request.model_id,
                content=self.content,
                call_id="call-stream",
            ),
        )


class OutcomeReporter:
    def __init__(self):
        self.calls = []

    def report_application_outcome(
        self,
        call_id,
        outcome,
        *,
        error_type=None,
        error_message=None,
    ):
        self.calls.append((call_id, outcome, error_type, error_message))


class StoryboardLabServiceTest(unittest.TestCase):
    def make_service(self, gateway=None, recipe=None, reporter=None):
        gateway = gateway or FakeGateway()
        recipe = recipe or FakeRecipe()
        store = MemoryRunStore()
        return (
            StoryboardLabService(
                gateway=gateway,
                recipes=FakeCatalog(recipe),
                runs=store,
                application_outcomes=reporter,
                run_id_factory=lambda: "storyboard-1",
            ),
            gateway,
            recipe,
            store,
        )

    @staticmethod
    def request():
        return StoryboardRunRequest(
            intention="A traveler reaches the last train.",
            panel_count=2,
            model_id="local-model",
            recipe_id=FakeRecipe.recipe_id,
            recipe_version=FakeRecipe.version,
        )

    def test_prepare_persists_provenance_without_calling_the_model(self):
        service, gateway, _, store = self.make_service()

        run = service.prepare(self.request())

        self.assertEqual(run.status, StoryboardRunStatus.CREATED)
        self.assertEqual(run.template_sha256, "a" * 64)
        self.assertEqual(store.get(run.run_id), run)
        self.assertEqual(gateway.complete_requests, [])
        self.assertEqual(gateway.stream_requests, [])

    def test_generate_uses_exactly_one_call_then_compiles_and_warns(self):
        reporter = OutcomeReporter()
        service, gateway, recipe, store = self.make_service(reporter=reporter)
        run = service.prepare(self.request())

        result = service.generate(run.run_id)

        self.assertEqual(len(gateway.complete_requests), 1)
        self.assertEqual(recipe.parse_calls, 1)
        self.assertEqual(result.status, StoryboardRunStatus.SUCCEEDED)
        self.assertEqual(result.raw_response, "candidate-json")
        self.assertIn("exactly 2 panels", result.compiled_prompt)
        self.assertEqual(len(result.spec.panels), 2)
        self.assertEqual(
            result.warnings,
            ("Two adjacent beats use the same framing.",),
        )
        self.assertEqual(store.get(run.run_id), result)
        self.assertEqual(
            reporter.calls,
            [("call-sync", LlmCallApplicationOutcome.ACCEPTED, None, None)],
        )

    def test_invalid_candidate_is_kept_as_failed_draft_without_repair_call(self):
        reporter = OutcomeReporter()
        recipe = FakeRecipe(reject=True)
        service, gateway, _, _ = self.make_service(
            recipe=recipe,
            reporter=reporter,
        )
        run = service.prepare(self.request())

        result = service.generate(run.run_id)

        self.assertEqual(len(gateway.complete_requests), 1)
        self.assertEqual(result.status, StoryboardRunStatus.FAILED)
        self.assertEqual(result.raw_response, "candidate-json")
        self.assertIsNone(result.compiled_prompt)
        self.assertIn("invalid storyboard JSON", result.error)
        self.assertEqual(reporter.calls[0][1], LlmCallApplicationOutcome.REJECTED)

    def test_stream_keeps_reasoning_separate_from_raw_response(self):
        reporter = OutcomeReporter()
        service, gateway, _, _ = self.make_service(reporter=reporter)
        run = service.prepare(self.request())

        events = list(service.stream_generate(run.run_id, include_reasoning=True))

        self.assertEqual(len(gateway.stream_requests), 1)
        self.assertTrue(gateway.stream_requests[0].include_reasoning)
        self.assertIn(StreamEventKind.REASONING, [event.kind for event in events])
        terminal = events[-1]
        self.assertEqual(terminal.kind, StreamEventKind.COMPLETED)
        self.assertEqual(terminal.run.status, StoryboardRunStatus.SUCCEEDED)
        self.assertEqual(terminal.run.raw_response, "candidate-json")
        self.assertNotIn("debug trace", terminal.run.raw_response)

    def test_truncated_stream_persists_the_raw_draft(self):
        gateway = FakeGateway("unfinished-json", finish_reason="length")
        service, _, recipe, _ = self.make_service(gateway=gateway)
        run = service.prepare(self.request())

        events = list(service.stream_generate(run.run_id))

        terminal = events[-1]
        self.assertEqual(terminal.kind, StreamEventKind.TRUNCATED)
        self.assertEqual(terminal.run.status, StoryboardRunStatus.TRUNCATED)
        self.assertEqual(terminal.run.raw_response, "unfinished-json")
        self.assertEqual(recipe.parse_calls, 0)
        self.assertEqual(len(gateway.stream_requests), 1)

    def test_invalid_stream_candidate_has_a_failed_terminal_run(self):
        recipe = FakeRecipe(reject=True)
        service, gateway, _, _ = self.make_service(recipe=recipe)
        run = service.prepare(self.request())

        terminal = list(service.stream_generate(run.run_id))[-1]

        self.assertEqual(terminal.kind, StreamEventKind.COMPLETED)
        self.assertEqual(terminal.run.status, StoryboardRunStatus.FAILED)
        self.assertEqual(terminal.run.raw_response, "candidate-json")
        self.assertIn("invalid storyboard JSON", terminal.run.error)
        self.assertEqual(len(gateway.stream_requests), 1)

    def test_stream_transport_error_persists_partial_draft(self):
        gateway = ExplodingStreamGateway()
        service, _, recipe, store = self.make_service(gateway=gateway)
        run = service.prepare(self.request())

        terminal = list(service.stream_generate(run.run_id))[-1]

        self.assertEqual(terminal.run.status, StoryboardRunStatus.FAILED)
        self.assertEqual(terminal.run.raw_response, "partial draft")
        self.assertIn("connection lost", terminal.run.error)
        self.assertEqual(store.get(run.run_id), terminal.run)
        self.assertEqual(recipe.parse_calls, 0)
        self.assertEqual(len(gateway.stream_requests), 1)

    def test_concurrent_streams_claim_one_run_before_calling_the_model(self):
        gateway = BlockingStreamGateway()
        service, _, _, _ = self.make_service(gateway=gateway)
        run = service.prepare(self.request())

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                lambda: list(service.stream_generate(run.run_id))
            )
            self.assertTrue(gateway.entered.wait(1))
            second = executor.submit(
                lambda: list(service.stream_generate(run.run_id))
            )
            with self.assertRaises(ValueError):
                second.result(timeout=1)
            gateway.release.set()
            terminal = first.result(timeout=2)[-1]

        self.assertEqual(len(gateway.stream_requests), 1)
        self.assertEqual(terminal.run.status, StoryboardRunStatus.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()
