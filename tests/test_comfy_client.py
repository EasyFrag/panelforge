import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.infrastructure.comfy import ComfyHttpClient, ComfyImageRef


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

    @patch("panelforge.infrastructure.comfy.client.uuid.uuid4")
    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_upload_image_posts_non_destructive_multipart_payload(
        self,
        urlopen,
        uuid4,
    ):
        uuid4.return_value = SimpleNamespace(hex="fixed-boundary")
        urlopen.return_value = FakeHttpResponse(
            b'{"name":"candidate (1).png","subfolder":"characters","type":"input"}'
        )
        client = ComfyHttpClient(
            "http://127.0.0.1:8188",
            client_id="client",
            timeout=14.0,
        )

        image_ref = client.upload_image(
            b"png-bytes\x00\xff",
            filename="candidate.png",
            subfolder="characters",
        )

        self.assertEqual(
            image_ref,
            ComfyImageRef(
                filename="candidate (1).png",
                subfolder="characters",
                folder_type="input",
            ),
        )
        self.assertEqual(image_ref.workflow_value, "characters/candidate (1).png")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8188/upload/image")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.get_header("Content-type"),
            "multipart/form-data; boundary=PanelForge-fixed-boundary",
        )
        self.assertEqual(urlopen.call_args.kwargs, {"timeout": 14.0})
        self.assertIn(
            b'Content-Disposition: form-data; name="type"\r\n\r\ninput\r\n',
            request.data,
        )
        self.assertIn(
            b'Content-Disposition: form-data; name="subfolder"\r\n\r\ncharacters\r\n',
            request.data,
        )
        self.assertIn(
            b'Content-Disposition: form-data; name="overwrite"\r\n\r\nfalse\r\n',
            request.data,
        )
        self.assertIn(
            b'Content-Disposition: form-data; name="image"; filename="candidate.png"',
            request.data,
        )
        self.assertIn(b"Content-Type: image/png", request.data)
        self.assertIn(b"png-bytes\x00\xff", request.data)

    def test_uploaded_image_without_subfolder_uses_returned_filename(self):
        image_ref = ComfyImageRef(
            filename="server-name.png",
            subfolder="",
            folder_type="input",
        )

        self.assertEqual(image_ref.workflow_value, "server-name.png")

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_upload_image_rejects_an_invalid_server_reference(self, urlopen):
        urlopen.return_value = FakeHttpResponse(
            b'{"name":"candidate.png","subfolder":"","type":"output"}'
        )
        client = ComfyHttpClient("http://127.0.0.1:8188", client_id="client")

        with self.assertRaisesRegex(ValueError, "unexpected uploaded image type"):
            client.upload_image(b"content", filename="candidate.png")

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_upload_image_rejects_a_non_object_response(self, urlopen):
        urlopen.return_value = FakeHttpResponse(b"[]")
        client = ComfyHttpClient("http://127.0.0.1:8188", client_id="client")

        with self.assertRaisesRegex(ValueError, "invalid upload response"):
            client.upload_image(b"content", filename="candidate.png")

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_upload_image_validates_local_input_before_network(self, urlopen):
        client = ComfyHttpClient("http://127.0.0.1:8188", client_id="client")

        invalid_inputs = (
            {"content": b"", "filename": "candidate.png"},
            {"content": b"content", "filename": ""},
            {"content": b"content", "filename": "folder/candidate.png"},
            {"content": b"content", "filename": "candidate\r\n.png"},
            {
                "content": b"content",
                "filename": "candidate.png",
                "subfolder": "../characters",
            },
            {
                "content": b"content",
                "filename": "candidate.png",
                "subfolder": "characters/",
            },
            {
                "content": b"content",
                "filename": "candidate.png",
                "subfolder": "characters\\views",
            },
        )
        for arguments in invalid_inputs:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    client.upload_image(**arguments)
        urlopen.assert_not_called()

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_upload_network_errors_are_not_swallowed(self, urlopen):
        expected_error = URLError("ComfyUI unavailable")
        urlopen.side_effect = expected_error
        client = ComfyHttpClient("http://127.0.0.1:8188", client_id="client")

        with self.assertRaises(URLError) as raised:
            client.upload_image(b"content", filename="candidate.png")

        self.assertIs(raised.exception, expected_error)

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
