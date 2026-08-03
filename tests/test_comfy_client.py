import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.infrastructure.comfy import ComfyHttpClient


class FakeHttpResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class ComfyHttpClientTest(unittest.TestCase):
    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_submit_workflow_posts_comfy_payload_and_returns_prompt_id(self, urlopen):
        urlopen.return_value = FakeHttpResponse(b'{"prompt_id": "prompt-123"}')
        client = ComfyHttpClient(
            "http://127.0.0.1:8188/",
            client_id="client-456",
            timeout=12.0,
        )

        prompt_id = client.submit_workflow({"3": {"class_type": "KSampler"}})

        self.assertEqual(prompt_id, "prompt-123")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8188/prompt")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(
            json.loads(request.data),
            {
                "prompt": {"3": {"class_type": "KSampler"}},
                "client_id": "client-456",
            },
        )
        self.assertEqual(urlopen.call_args.kwargs, {"timeout": 12.0})

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_get_history_encodes_prompt_id_and_returns_raw_payload(self, urlopen):
        payload = {"prompt/id?": {"status": {"completed": True}}}
        urlopen.return_value = FakeHttpResponse(json.dumps(payload).encode("utf-8"))
        client = ComfyHttpClient("http://127.0.0.1:8188", client_id="client")

        history = client.get_history("prompt/id?")

        self.assertEqual(history, payload)
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "http://127.0.0.1:8188/history/prompt%2Fid%3F",
        )
        self.assertEqual(request.get_method(), "GET")

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_download_output_encodes_reference_and_returns_bytes(self, urlopen):
        expected_content = b"generated-image"
        urlopen.return_value = FakeHttpResponse(expected_content)
        client = ComfyHttpClient("http://127.0.0.1:8188", client_id="client")

        content = client.download_output(
            filename="candidate 01.png",
            subfolder="characters/main",
            folder_type="output",
        )

        self.assertEqual(content, expected_content)
        request = urlopen.call_args.args[0]
        parsed_url = urlsplit(request.full_url)
        self.assertEqual(parsed_url.path, "/view")
        self.assertEqual(
            parse_qs(parsed_url.query),
            {
                "filename": ["candidate 01.png"],
                "subfolder": ["characters/main"],
                "type": ["output"],
            },
        )

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_network_errors_are_not_swallowed(self, urlopen):
        expected_error = URLError("ComfyUI unavailable")
        urlopen.side_effect = expected_error
        client = ComfyHttpClient("http://127.0.0.1:8188", client_id="client")

        with self.assertRaises(URLError) as raised:
            client.get_history("prompt-123")

        self.assertIs(raised.exception, expected_error)

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_submit_workflow_rejects_an_invalid_prompt_id(self, urlopen):
        urlopen.return_value = FakeHttpResponse(b'{"prompt_id": null}')
        client = ComfyHttpClient("http://127.0.0.1:8188", client_id="client")

        with self.assertRaisesRegex(ValueError, "invalid prompt_id"):
            client.submit_workflow({})


if __name__ == "__main__":
    unittest.main()
