import sys
import unittest
import urllib.error
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.infrastructure.llm import LlamaSwapAdminClient


class FakeResponse:
    status = 200

    def __init__(self, payload=b'{}') -> None:
        self.read_limit = None
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit):
        self.read_limit = limit
        return self.payload


class LlamaSwapAdminClientTest(unittest.TestCase):
    def test_unloads_all_models_at_the_llama_swap_root(self):
        calls = []
        response = FakeResponse()

        def open_request(request, *, timeout):
            calls.append((request, timeout))
            return response

        client = LlamaSwapAdminClient(
            "https://bucket.example/proxy/v1/",
            api_key="secret",
            timeout=12.0,
            opener=open_request,
        )

        client.unload_all()

        request, timeout = calls[0]
        self.assertEqual(
            request.full_url,
            "https://bucket.example/proxy/api/models/unload",
        )
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.data, b"")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(timeout, 12.0)
        self.assertEqual(response.read_limit, 1024 * 1024)

    def test_reports_an_unreachable_runtime(self):
        def fail(*_, **__):
            raise urllib.error.URLError("offline")

        client = LlamaSwapAdminClient(
            "http://bucket:8083/v1",
            opener=fail,
        )

        with self.assertRaisesRegex(ConnectionError, "offline"):
            client.unload_all()

    def test_lists_running_models_from_strings_and_objects(self):
        calls = []
        response = FakeResponse(
            json.dumps(
                {
                    "running": [
                        "Qwen3.8-27B",
                        {"model": "Gemma-4-31B"},
                        {"model_id": "Qwen3.8-27B"},
                    ]
                }
            ).encode("utf-8")
        )

        def open_request(request, *, timeout):
            calls.append((request, timeout))
            return response

        client = LlamaSwapAdminClient(
            "http://bucket:8083/v1",
            api_key="secret",
            timeout=2.0,
            opener=open_request,
        )

        self.assertEqual(
            client.running_models(),
            ("Qwen3.8-27B", "Gemma-4-31B"),
        )
        request, timeout = calls[0]
        self.assertEqual(request.full_url, "http://bucket:8083/running")
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(timeout, 2.0)

    def test_rejects_a_malformed_running_model_response(self):
        client = LlamaSwapAdminClient(
            "http://bucket:8083/v1",
            opener=lambda *_args, **_kwargs: FakeResponse(b'{"running":{}}'),
        )

        with self.assertRaisesRegex(ValueError, "running-model list"):
            client.running_models()


if __name__ == "__main__":
    unittest.main()
