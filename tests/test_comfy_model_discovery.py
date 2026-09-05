import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.infrastructure.comfy import ComfyHttpClient


class FakeHttpResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def response(payload):
    return FakeHttpResponse(json.dumps(payload).encode("utf-8"))


class ComfyModelDiscoveryTest(unittest.TestCase):
    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_lists_models_from_unet_loader_description(self, urlopen):
        urlopen.return_value = response(
            {
                "UNETLoader": {
                    "input": {
                        "required": {
                            "unet_name": [
                                [
                                    "Krea2/krea2_turbo_bf16.safetensors",
                                    "Krea2/current-gpt.safetensors",
                                    "Krea2/current-gpt.safetensors",
                                ],
                                {"tooltip": "model"},
                            ]
                        }
                    }
                }
            }
        )
        client = ComfyHttpClient("http://gpu:8188", client_id="image-lab")

        models = client.list_unet_models()

        self.assertEqual(
            models,
            (
                "Krea2/krea2_turbo_bf16.safetensors",
                "Krea2/current-gpt.safetensors",
            ),
        )
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "http://gpu:8188/object_info/UNETLoader",
        )
        self.assertEqual(request.get_method(), "GET")

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_falls_back_to_diffusion_models_route_when_node_is_missing(self, urlopen):
        urlopen.side_effect = [
            HTTPError(
                "http://gpu:8188/object_info/UNETLoader",
                404,
                "missing",
                {},
                None,
            ),
            response(["Krea2/a.safetensors", "Krea2/b.safetensors"]),
        ]
        client = ComfyHttpClient("http://gpu:8188", client_id="image-lab")

        models = client.list_unet_models()

        self.assertEqual(
            models,
            ("Krea2/a.safetensors", "Krea2/b.safetensors"),
        )
        self.assertEqual(
            urlopen.call_args_list[1].args[0].full_url,
            "http://gpu:8188/models/diffusion_models",
        )

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_falls_back_when_node_description_is_malformed(self, urlopen):
        urlopen.side_effect = [
            response({"UNETLoader": {"input": {}}}),
            response({"models": ["Krea2/a.safetensors"]}),
        ]
        client = ComfyHttpClient("http://gpu:8188", client_id="image-lab")

        self.assertEqual(client.list_unet_models(), ("Krea2/a.safetensors",))

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_does_not_hide_network_failures(self, urlopen):
        expected = URLError("ComfyUI unavailable")
        urlopen.side_effect = expected
        client = ComfyHttpClient("http://gpu:8188", client_id="image-lab")

        with self.assertRaises(URLError) as raised:
            client.list_unet_models()

        self.assertIs(raised.exception, expected)
        self.assertEqual(urlopen.call_count, 1)

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_rejects_invalid_fallback_model_names(self, urlopen):
        urlopen.side_effect = [response({}), response(["Krea2/a.safetensors", None])]
        client = ComfyHttpClient("http://gpu:8188", client_id="image-lab")

        with self.assertRaisesRegex(ValueError, "invalid diffusion model name"):
            client.list_unet_models()

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_lists_loras_from_comfy_model_inventory(self, urlopen):
        urlopen.return_value = response(
            ["krea2/style.safetensors", "other/detail.safetensors"]
        )
        client = ComfyHttpClient("http://gpu:8188", client_id="image-lab")

        self.assertEqual(
            client.list_lora_models(),
            ("krea2/style.safetensors", "other/detail.safetensors"),
        )
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://gpu:8188/models/loras")
        self.assertEqual(request.get_method(), "GET")

    @patch("panelforge.infrastructure.comfy.client.urllib.request.urlopen")
    def test_reads_cached_rgthree_lora_info_without_refreshing_or_hashing(self, urlopen):
        urlopen.return_value = response({
            "status": 200,
            "data": [{
                "file": "krea2/style.safetensors",
                "name": "Style card",
                "images": [{"url": "https://image.civitai.com/style.webp"}],
            }],
        })
        client = ComfyHttpClient("http://gpu:8188", client_id="image-lab")

        value = client.get_cached_model_info("lora", "krea2/style.safetensors")

        self.assertEqual(value["name"], "Style card")
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "http://gpu:8188/rgthree/api/loras/info?files=krea2%2Fstyle.safetensors",
        )
        self.assertNotIn("refresh", request.full_url)
        self.assertEqual(request.get_method(), "GET")


if __name__ == "__main__":
    unittest.main()
