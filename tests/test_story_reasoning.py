"""User-run regressions: recorded reasoning and fake streams, no model calls."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from panelforge.application.prompt_lab import CompletionRequest, CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.application.story_stream import story_truncation_message
from panelforge.application.story_attempts import archive_job
from panelforge.infrastructure.llm.openai_compatible import OpenAICompatibleGateway
from tests import test_story_workflow as workflow_fixture


CYCLE = json.loads((Path(__file__).parent / 'fixtures/long_stories/reasoning_loop_2026_09_22.json').read_text(encoding='utf-8'))['cycle']


class StoryTruncationMessageTest(unittest.TestCase):
    def test_length_message_distinguishes_empty_and_partial_response(self):
        empty = story_truncation_message(80000, draft='', reasoning='Work received')
        partial = story_truncation_message(80000, draft='{"reply":', reasoning='Work received')
        self.assertIn('budget demandé : 80 000 tokens', empty)
        self.assertIn('Aucun scénario', empty)
        self.assertIn('pas de brouillon', empty)
        self.assertIn('raisonnement reçu est conservé', empty)
        self.assertIn('brouillon partiel est conservé', partial)
        self.assertNotIn('Aucun scénario', partial)


class RecordingGateway:
    def __init__(self, events):
        self.events = events
        self.requests = []
        self.closed = False

    def stream(self, request):
        self.requests.append(request)
        try:
            yield from self.events
        finally:
            self.closed = True


def reasoning_events(text):
    for offset in range(0, len(text), 127):
        yield CompletionStreamEvent(StreamEventKind.REASONING, StreamPhase.GENERATING, text=text[offset:offset + 127])


class StoryReasoningServiceTest(unittest.TestCase):
    setUp = workflow_fixture.StoryWorkflowTest.setUp
    create = workflow_fixture.StoryWorkflowTest.create
    settle = workflow_fixture.StoryWorkflowTest.settle
    advance = workflow_fixture.StoryWorkflowTest.advance

    def install_gateway(self, events):
        self.gateway = RecordingGateway(events)
        self.service.gateway = self.gateway

    def test_repeated_reasoning_continues_until_provider_terminal_event(self):
        text = CYCLE * 8
        def events():
            yield from reasoning_events(text)
            yield CompletionStreamEvent(StreamEventKind.TRUNCATED, StreamPhase.TRUNCATED,
                result=CompletionResult('local::fixture', '', finish_reason='length', call_id='provider-terminal'))
        self.install_gateway(events())
        project = self.create(count=1)
        original = deepcopy(project['document'])
        result = self.advance(project)
        self.assertEqual(result['job']['status'], 'failed')
        self.assertEqual(result['job']['call_id'], 'provider-terminal')
        self.assertIn('limite de longueur', result['job']['error'])
        self.assertEqual(result['job']['draft'], '')
        self.assertEqual(result['job']['reasoning'], text)
        self.assertEqual(result['document'], original)
        self.assertEqual(result['workflow']['status'], 'blocked')
        self.assertNotIn('revalide le brouillon', result['workflow']['message'])
        self.assertEqual(len(self.gateway.requests), 1)
        self.assertEqual(self.gateway.requests[0].max_tokens, 80000)
        self.assertEqual(result['llm_usage']['calls'], 1)
        self.assertTrue(self.gateway.closed)

        archive_job(result)
        self.assertEqual(result['draft_history'][-1]['reasoning'], result['job']['reasoning'])

    def test_provider_truncation_without_response_does_not_offer_a_nonexistent_draft(self):
        def events():
            yield from reasoning_events('Considering a simple consequence.')
            yield CompletionStreamEvent(StreamEventKind.TRUNCATED, StreamPhase.TRUNCATED,
                result=CompletionResult('local::fixture', '', finish_reason='length'))
        self.install_gateway(events())
        result = self.advance(self.create(count=1))
        self.assertEqual(result['job']['status'], 'failed')
        self.assertIn('Aucun scénario', result['job']['error'])
        self.assertEqual(result['job']['draft'], '')
        self.assertTrue(self.gateway.closed)
        self.assertEqual(len(self.gateway.requests), 1)

    def test_received_response_is_preserved_when_provider_truncates(self):
        draft = '{"reply":"A partial response'
        def events():
            yield CompletionStreamEvent(StreamEventKind.DELTA, StreamPhase.GENERATING, text=draft)
            yield from reasoning_events(CYCLE * 8)
            yield CompletionStreamEvent(StreamEventKind.TRUNCATED, StreamPhase.TRUNCATED,
                result=CompletionResult('local::fixture', draft, finish_reason='length'))
        self.install_gateway(events())
        result = self.advance(self.create(count=1))
        self.assertEqual(result['job']['draft'], draft)
        self.assertIn('brouillon partiel est conservé', result['job']['error'])
        self.assertTrue(self.gateway.closed)
        self.assertEqual(len(self.gateway.requests), 1)


class StoryStreamTransportTest(unittest.TestCase):
    def test_closing_on_reasoning_closes_provider_stream(self):
        class ProviderStream:
            closed = False
            def __iter__(self):
                yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(reasoning_content='Choosing a consequence.\n'), finish_reason=None)])
                raise AssertionError('Consumer should close before requesting another chunk')
            def close(self):
                self.closed = True
        provider = ProviderStream()
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: provider)))
        gateway = OpenAICompatibleGateway('http://unused.invalid/v1', client=client)
        stream = gateway.stream(CompletionRequest('fixture', 'Return a story', 'An argument', include_reasoning=True))
        for event in stream:
            if event.kind is StreamEventKind.REASONING:
                stream.close()
                break
        self.assertTrue(provider.closed)
