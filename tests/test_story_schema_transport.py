"""Transport contract only: fake client, no network, model or GPU."""
from types import SimpleNamespace
import unittest
import httpx
from openai import BadRequestError

from panelforge.application.prompt_lab import CompletionRequest
from panelforge.infrastructure.llm.openai_compatible import OpenAICompatibleGateway


class Client:
    def __init__(self):
        self.arguments = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.arguments.append(kwargs)
        if kwargs["stream"]:
            return iter([SimpleNamespace(model="fixture", usage=None, choices=[SimpleNamespace(
                finish_reason="stop", delta=SimpleNamespace(content='{"reply":"OK"}'))])])
        return SimpleNamespace(model="fixture", usage=None, choices=[SimpleNamespace(
            finish_reason="stop", message=SimpleNamespace(content='{"reply":"OK"}'))])


class StorySchemaTransportTest(unittest.TestCase):
    def request(self, schema=True):
        return CompletionRequest(model_id="fixture", system_prompt="JSON", user_prompt="Fixture",
            max_tokens=80000, output_schema={"type": "object", "properties": {"reply": {"type": "string"}},
                "required": ["reply"], "additionalProperties": False} if schema else None)

    def test_schema_reaches_both_transport_methods_without_changing_budget(self):
        client = Client()
        gateway = OpenAICompatibleGateway("http://unused.invalid/v1", client=client, structured_output="json_schema")
        request = self.request()
        gateway.complete(request)
        events = list(gateway.stream(request))
        self.assertEqual(len(client.arguments), 2)
        for arguments in client.arguments:
            self.assertEqual(arguments["response_format"]["json_schema"]["schema"], request.output_schema)
            self.assertEqual(arguments["max_tokens"], 80000)
        self.assertTrue(any("sortie contrainte" in (event.text or "") for event in events))

    def test_off_is_explicit_and_other_operations_do_not_gain_a_schema(self):
        client = Client()
        gateway = OpenAICompatibleGateway("http://unused.invalid/v1", client=client)
        events = list(gateway.stream(self.request()))
        self.assertNotIn("response_format", client.arguments[0])
        self.assertTrue(any("contrainte serveur désactivée" in (event.text or "") for event in events))
        enabled = OpenAICompatibleGateway("http://unused.invalid/v1", client=client, structured_output="json_schema")
        enabled.complete(self.request(schema=False))
        self.assertNotIn("response_format", client.arguments[-1])

    def test_rejected_schema_is_explained_without_an_automatic_fallback_call(self):
        class Unsupported(Client):
            def create(self, **kwargs):
                self.arguments.append(kwargs)
                raise BadRequestError("response_format json_schema unsupported", body={},
                    response=httpx.Response(400, request=httpx.Request("POST", "http://unused.invalid/v1")))
        client = Unsupported()
        gateway = OpenAICompatibleGateway("http://unused.invalid/v1", client=client, structured_output="json_schema")
        with self.assertRaisesRegex(ValueError, "Aucun nouvel appel automatique"):
            list(gateway.stream(self.request()))
        self.assertEqual(len(client.arguments), 1)
