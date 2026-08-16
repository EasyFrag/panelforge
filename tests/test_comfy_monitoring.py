import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.infrastructure.comfy import (
    ComfyCancelAction,
    ComfyCancellationError,
    ComfyHttpClient,
    ComfyPromptPhase,
    build_websocket_url,
)


class FakeHttpResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def queue_payload(*, running=(), pending=()):
    return json.dumps(
        {"queue_running": list(running), "queue_pending": list(pending)}
    ).encode("utf-8")


def queue_entry(prompt_id, *, client_id="video-lab", number=1):
    return [number, prompt_id, {"3": {"class_type": "KSampler"}}, {"client_id": client_id}, ["9"]]


class ComfyMonitoringTest(unittest.TestCase):
    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_get_queue_normalizes_running_and_pending_entries(self, urlopen):
        urlopen.return_value = FakeHttpResponse(
            queue_payload(
                running=[queue_entry("running-1", number=4)],
                pending=[queue_entry("pending-1", number=5)],
            )
        )
        client = ComfyHttpClient(
            "http://127.0.0.1:8188", client_id="video-lab", timeout=7
        )

        snapshot = client.get_queue()

        self.assertEqual(snapshot.running[0].prompt_id, "running-1")
        self.assertEqual(snapshot.running[0].phase, ComfyPromptPhase.RUNNING)
        self.assertEqual(snapshot.pending[0].queue_number, 5)
        self.assertEqual(snapshot.pending[0].client_id, "video-lab")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8188/queue")
        self.assertEqual(request.get_method(), "GET")

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_prompt_status_reads_queue_before_history(self, urlopen):
        urlopen.return_value = FakeHttpResponse(
            queue_payload(pending=[queue_entry("prompt-1", number=8)])
        )
        client = ComfyHttpClient("http://127.0.0.1:8188", client_id="video-lab")

        status = client.get_prompt_status("prompt-1")

        self.assertEqual(status.phase, ComfyPromptPhase.PENDING)
        self.assertEqual(status.queue_number, 8)
        self.assertEqual(urlopen.call_count, 1)

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_prompt_status_normalizes_terminal_history(self, urlopen):
        history = {
            "prompt-1": {
                "status": {
                    "status_str": "error",
                    "completed": False,
                    "messages": [["execution_error", {"node_id": "9"}]],
                }
            }
        }
        urlopen.side_effect = [
            FakeHttpResponse(queue_payload()),
            FakeHttpResponse(json.dumps(history).encode("utf-8")),
        ]
        client = ComfyHttpClient("http://127.0.0.1:8188", client_id="video-lab")

        status = client.get_prompt_status("prompt-1")

        self.assertEqual(status.phase, ComfyPromptPhase.FAILED)
        self.assertEqual(status.status_text, "error")

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_cancel_uses_targeted_jobs_api_for_owned_prompt(self, urlopen):
        urlopen.side_effect = [
            FakeHttpResponse(b'{"prompt_id":"prompt/id"}'),
            FakeHttpResponse(b'{"cancelled":true}'),
        ]
        client = ComfyHttpClient(
            "http://127.0.0.1:8188", client_id="video-lab", timeout=11
        )
        client.submit_workflow({"3": {"class_type": "KSampler"}})

        result = client.cancel_prompt("prompt/id")

        self.assertEqual(result.action, ComfyCancelAction.CANCEL_JOB)
        request = urlopen.call_args_list[1].args[0]
        self.assertEqual(
            request.full_url,
            "http://127.0.0.1:8188/api/jobs/prompt%2Fid/cancel",
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data), {})

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_cancel_false_after_completion_is_reported_as_already_finished(
        self, urlopen
    ):
        history = {
            "prompt-1": {
                "status": {"status_str": "success", "completed": True}
            }
        }
        urlopen.side_effect = [
            FakeHttpResponse(b'{"prompt_id":"prompt-1"}'),
            FakeHttpResponse(b'{"cancelled":false}'),
            FakeHttpResponse(json.dumps(history).encode("utf-8")),
        ]
        client = ComfyHttpClient("http://127.0.0.1:8188", client_id="video-lab")
        client.submit_workflow({})

        result = client.cancel_job("prompt-1")

        self.assertEqual(result.action, ComfyCancelAction.ALREADY_FINISHED)

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_cancel_false_for_unknown_job_is_reported_as_not_found(self, urlopen):
        urlopen.side_effect = [
            FakeHttpResponse(b'{"cancelled":false}'),
            FakeHttpResponse(b"{}"),
        ]
        client = ComfyHttpClient("http://127.0.0.1:8188", client_id="video-lab")

        result = client.cancel_job("unknown")

        self.assertEqual(result.action, ComfyCancelAction.NOT_FOUND)

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_cancel_falls_back_to_targeted_queue_delete_on_missing_jobs_api(
        self, urlopen
    ):
        unavailable = HTTPError(
            "http://127.0.0.1:8188/api/jobs/prompt-1/cancel",
            404,
            "not found",
            hdrs=None,
            fp=BytesIO(),
        )
        urlopen.side_effect = [
            FakeHttpResponse(b'{"prompt_id":"prompt-1"}'),
            unavailable,
            FakeHttpResponse(
                queue_payload(pending=[queue_entry("prompt-1", number=3)])
            ),
            FakeHttpResponse(b""),
        ]
        client = ComfyHttpClient("http://127.0.0.1:8188", client_id="video-lab")
        client.submit_workflow({})

        result = client.cancel_prompt("prompt-1")

        self.assertEqual(result.action, ComfyCancelAction.DELETE_PENDING)
        delete_request = urlopen.call_args_list[3].args[0]
        self.assertEqual(delete_request.full_url, "http://127.0.0.1:8188/queue")
        self.assertEqual(json.loads(delete_request.data), {"delete": ["prompt-1"]})

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_legacy_running_cancel_rechecks_sole_owned_runner(self, urlopen):
        unavailable = HTTPError(
            "http://127.0.0.1:8188/api/jobs/prompt-1/cancel",
            405,
            "method not allowed",
            hdrs=None,
            fp=BytesIO(),
        )
        running = queue_payload(running=[queue_entry("prompt-1")])
        urlopen.side_effect = [
            FakeHttpResponse(b'{"prompt_id":"prompt-1"}'),
            unavailable,
            FakeHttpResponse(running),
            FakeHttpResponse(running),
            FakeHttpResponse(b""),
        ]
        client = ComfyHttpClient("http://127.0.0.1:8188", client_id="video-lab")
        client.submit_workflow({})

        result = client.cancel_prompt("prompt-1")

        self.assertEqual(result.action, ComfyCancelAction.INTERRUPT_RUNNING)
        interrupt_request = urlopen.call_args_list[4].args[0]
        self.assertEqual(
            interrupt_request.full_url, "http://127.0.0.1:8188/interrupt"
        )
        self.assertEqual(
            json.loads(interrupt_request.data), {"prompt_id": "prompt-1"}
        )

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_cancel_refuses_a_foreign_queue_entry_before_posting(self, urlopen):
        unavailable = HTTPError(
            "http://127.0.0.1:8188/api/jobs/foreign/cancel",
            404,
            "not found",
            hdrs=None,
            fp=BytesIO(),
        )
        urlopen.side_effect = [
            unavailable,
            FakeHttpResponse(
                queue_payload(
                    running=[queue_entry("foreign", client_id="other-client")]
                )
            ),
        ]
        client = ComfyHttpClient("http://127.0.0.1:8188", client_id="video-lab")

        with self.assertRaises(ComfyCancellationError):
            client.cancel_prompt("foreign")

        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(urlopen.call_args_list[1].args[0].get_method(), "GET")

    def test_websocket_url_supports_https_prefix_and_encoded_client_id(self):
        url = build_websocket_url(
            "https://gpu.example.test/comfy/", client_id="video lab/1"
        )

        self.assertEqual(
            url,
            "wss://gpu.example.test/comfy/ws?clientId=video+lab%2F1",
        )

if __name__ == "__main__":
    unittest.main()
