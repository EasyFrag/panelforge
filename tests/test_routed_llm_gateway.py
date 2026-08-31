import unittest

from panelforge.application import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    ModelDescriptor,
    StreamEventKind,
    StreamPhase,
)
from panelforge.infrastructure.llm import RoutedMultimodalGateway


class FakeGateway:
    def __init__(self, model_id: str, *, unavailable: bool = False) -> None:
        self.model_id = model_id
        self.unavailable = unavailable
        self.requests: list[CompletionRequest] = []

    def list_models(self):
        if self.unavailable:
            raise ConnectionError("offline")
        return (ModelDescriptor(self.model_id),)

    def complete(self, request):
        self.requests.append(request)
        return CompletionResult(model_id=self.model_id, content="ok")

    def stream(self, request):
        self.requests.append(request)
        yield CompletionStreamEvent(
            kind=StreamEventKind.STATUS,
            phase=StreamPhase.PREPARING,
            text="loading",
        )
        yield CompletionStreamEvent(
            kind=StreamEventKind.COMPLETED,
            phase=StreamPhase.COMPLETED,
            text="ok",
            result=CompletionResult(model_id=self.model_id, content="ok"),
        )


class RoutedMultimodalGatewayTest(unittest.TestCase):
    def setUp(self):
        self.server = FakeGateway("server-model")
        self.local = FakeGateway("local-model")
        self.alternate = FakeGateway("alternate-model")
        self.gateway = RoutedMultimodalGateway(
            {
                "server": self.server,
                "local": self.local,
                "alternate": self.alternate,
            }
        )

    def test_catalog_keeps_server_ids_compatible_and_namespaces_local_models(self):
        models = self.gateway.list_models()

        self.assertEqual(
            [(model.model_id, model.source, model.display_name) for model in models],
            [
                ("server-model", "server", "server-model"),
                ("local::local-model", "local", "local-model"),
                ("alternate::alternate-model", "alternate", "alternate-model"),
            ],
        )

    def test_routes_old_plain_model_ids_to_the_server(self):
        result = self.gateway.complete(_request("server-model"))

        self.assertEqual(self.server.requests[0].model_id, "server-model")
        self.assertEqual(result.model_id, "server-model")
        self.assertFalse(self.local.requests)
        self.assertFalse(self.alternate.requests)

    def test_routes_namespaced_models_locally_and_restores_the_namespace(self):
        result = self.gateway.complete(_request("local::local-model"))

        self.assertEqual(self.local.requests[0].model_id, "local-model")
        self.assertEqual(result.model_id, "local::local-model")
        self.assertFalse(self.server.requests)
        self.assertFalse(self.alternate.requests)

    def test_routes_namespaced_models_to_an_alternate_provider(self):
        result = self.gateway.complete(_request("alternate::alternate-model"))

        self.assertEqual(self.alternate.requests[0].model_id, "alternate-model")
        self.assertEqual(result.model_id, "alternate::alternate-model")
        self.assertFalse(self.server.requests)
        self.assertFalse(self.local.requests)

    def test_routes_stream_terminal_results_locally(self):
        events = tuple(self.gateway.stream(_request("local::local-model")))

        self.assertIsNone(events[0].result)
        self.assertEqual(events[-1].result.model_id, "local::local-model")
        self.assertEqual(self.local.requests[0].model_id, "local-model")

    def test_one_unavailable_source_does_not_hide_the_other_catalog(self):
        gateway = RoutedMultimodalGateway(
            {
                "server": self.server,
                "local": FakeGateway("local-model", unavailable=True),
                "alternate": self.alternate,
            }
        )

        self.assertEqual(
            [model.model_id for model in gateway.list_models()],
            ["server-model", "alternate::alternate-model"],
        )

    def test_rejects_unknown_namespaces_instead_of_sending_them_to_the_server(self):
        with self.assertRaisesRegex(ValueError, "unknown LLM source"):
            self.gateway.complete(_request("other::model"))


def _request(model_id: str) -> CompletionRequest:
    return CompletionRequest(
        model_id=model_id,
        system_prompt="system",
        user_prompt="user",
    )


if __name__ == "__main__":
    unittest.main()
