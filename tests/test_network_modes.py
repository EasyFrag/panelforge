"""Network profiles: no real servers, model loads, GPU calls or mounted drives."""
from contextlib import ExitStack, redirect_stderr
import io
import json
import os
import sys
from pathlib import Path, PureWindowsPath
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.request
from urllib.response import addinfourl

from scripts import run_lab
from fastapi.testclient import TestClient
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.comfy import ComfyHttpClient
from panelforge.infrastructure.dlss_video_exports import DlssVideoExporter
from panelforge.infrastructure.prompt_examples import LocalPromptExampleLibrary
from panelforge.infrastructure.llm import OpenAICompatibleGateway
from panelforge.infrastructure.network_profiles import (
    DEFAULT_EXPORT_ROOT, describe_network, resolve_network_configuration,
)
from panelforge.infrastructure.network_transports import (
    direct_http_opener, direct_preview_connection, direct_thermal_connection,
    direct_dlss_connection,
)


class StartupProfilesTest(unittest.TestCase):
    def parse(self, argv=(), env=None):
        with patch.dict(os.environ, env or {}, clear=True):
            return run_lab.parse_args(list(argv))

    def test_users_historical_command_preserves_both_urls_local_key_and_export_path(self):
        args = self.parse([
            "--workspace", r"D:\Code\panelforge\workspace",
            "--base-url", "http://bucket:8188", "--llm-base-url", "http://bucket:8083/v1",
            "--port", "7861",
        ], {"PANELFORGE_LOCAL_LLM_URL": "http://127.0.0.1:8888/v1",
            "PANELFORGE_LOCAL_LLM_API_KEY": "local-test-key"})
        self.assertIsNone(args.network_mode)
        self.assertEqual((args.base_url, args.llm_base_url),
                         ("http://bucket:8188", "http://bucket:8083/v1"))
        self.assertEqual(args.local_llm_base_url, "http://127.0.0.1:8888/v1")
        self.assertEqual(args.local_llm_api_key, "local-test-key")
        self.assertEqual(args.dlss_base_url, "http://127.0.0.1:8188")
        self.assertEqual(args.dlss_video_export_root, Path(DEFAULT_EXPORT_ROOT))
        self.assertIsNone(args.dlss_video_export_access_root)
        self.assertEqual(args.port, 7861)

    def test_absent_mode_keeps_legacy_defaults_even_though_they_mix_routes(self):
        args = self.parse()
        self.assertEqual(args.base_url, "http://192.168.1.72:8188")
        self.assertEqual(args.llm_base_url, "http://bucket:8083/v1")
        self.assertIn("malmo@bucket", str(args.krea2_models_root))
        self.assertIsNone(args.network_mode)

    def test_legacy_environment_and_cli_overrides_keep_their_precedence(self):
        env = {
            "PANELFORGE_COMFY_URL": "http://custom-comfy:9001",
            "PANELFORGE_LLM_URL": "http://custom-llm:9002/v1",
            "PANELFORGE_KREA2_MODELS_ROOT": "custom-models",
            "PANELFORGE_KREA2_LORAS_ROOT": "custom-loras",
        }
        inherited = self.parse(env=env)
        self.assertEqual(inherited.base_url, env["PANELFORGE_COMFY_URL"])
        self.assertEqual(inherited.llm_base_url, env["PANELFORGE_LLM_URL"])
        self.assertEqual(inherited.krea2_models_root, Path("custom-models"))
        overridden = self.parse(["--base-url", "http://explicit:8880",
                                 "--krea2-models-root", "explicit-models"], env)
        self.assertEqual(overridden.base_url, "http://explicit:8880")
        self.assertEqual(overridden.krea2_models_root, Path("explicit-models"))
        self.assertEqual(overridden.krea2_loras_root, Path("custom-loras"))

    def test_explicit_profiles_control_api_and_unc_roots_despite_old_environment(self):
        env = {
            "PANELFORGE_COMFY_URL": "http://wrong-route:1",
            "PANELFORGE_LLM_URL": "http://wrong-route:2/v1",
            "PANELFORGE_KREA2_MODELS_ROOT": "wrong-models",
            "PANELFORGE_KREA2_LORAS_ROOT": "wrong-loras",
            "PANELFORGE_LOCAL_LLM_API_KEY": "local-test-key",
        }
        for mode, host in (("lan", "192.168.1.72"), ("tailscale", "bucket")):
            with self.subTest(mode=mode):
                args = self.parse(["--network-mode", mode, "--port", "7861"], env)
                self.assertEqual(args.base_url, f"http://{host}:8188")
                self.assertEqual(args.llm_base_url, f"http://{host}:8083/v1")
                share = "\\\\sshfs.r\\malmo@" + host
                self.assertEqual(str(args.krea2_models_root),
                    share + r"\data\models\ComfyUi\diffusion_models\Krea2")
                self.assertEqual(str(args.krea2_loras_root),
                    share + r"\data\models\ComfyUi\loras\krea2")
                self.assertEqual(str(args.dlss_video_export_access_root),
                    share + r"\data\ComfyUI\output\video\Upscale")
                self.assertTrue(PureWindowsPath(args.krea2_models_root).is_absolute())
                self.assertEqual(str(args.dlss_video_export_root), DEFAULT_EXPORT_ROOT)
                self.assertEqual(args.local_llm_api_key, "local-test-key")
                self.assertEqual(args.local_llm_base_url, "http://127.0.0.1:8888/v1")
                self.assertEqual(args.dlss_base_url, "http://127.0.0.1:8188")

    def test_contradictory_explicit_urls_or_roots_fail_before_building_services(self):
        for option, value in (
            ("--base-url", "http://bucket:8188"),
            ("--llm-base-url", "http://bucket:8083/v1"),
            ("--krea2-models-root", r"X:\models"),
            ("--krea2-loras-root", r"\\sshfs.r\malmo@bucket\data\loras"),
            ("--dlss-video-export-root", r"Y:\exports"),
        ):
            with self.subTest(option=option), redirect_stderr(io.StringIO()) as output:
                with self.assertRaises(SystemExit) as error:
                    self.parse(["--network-mode", "lan", option, value])
                self.assertEqual(error.exception.code, 2)
                self.assertIn(option + " contredit", output.getvalue())

    def test_equivalent_explicit_values_are_allowed(self):
        args = self.parse([
            "--network-mode=lan", "--base-url=http://192.168.1.72:8188/",
            "--llm-base-url", "http://192.168.1.72:8083/v1/",
            "--dlss-video-export-root", "X:/data/ComfyUI/output/video/Upscale/",
        ])
        self.assertEqual(args.base_url, "http://192.168.1.72:8188")
        self.assertEqual(str(args.dlss_video_export_root), DEFAULT_EXPORT_ROOT)

    def test_profile_url_cannot_hide_another_service_or_credentials(self):
        for url in ("http://192.168.1.72:8888", "https://192.168.1.72:8188",
                    "http://user:secret@192.168.1.72:8188", "http://192.168.1.72:8188/?route=other"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                resolve_network_configuration("lan", base_url=url, environ={})

    def test_console_diagnostics_never_print_api_keys_or_url_credentials(self):
        args = self.parse(["--base-url", "http://user:secret@custom:8188/api?token=private"],
                          {"PANELFORGE_LOCAL_LLM_API_KEY": "do-not-print"})
        text = describe_network(args)
        self.assertIn("http://custom:8188/api", text)
        self.assertIn("configuration historique", text)
        for secret in ("user:secret", "token=private", "do-not-print"):
            self.assertNotIn(secret, text)


class RoutedExportsTest(unittest.TestCase):
    job_id = "dlss-" + "a" * 32
    day = "2026-09-28"

    def job(self, exporter):
        return {"job_id": self.job_id,
                "video_export": {"date": self.day, "path": str(exporter.target(self.job_id, self.day))}}

    def test_old_windows_job_can_use_either_access_without_changing_saved_path(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            lan = base / "lan" / "video" / "Upscale"
            tailscale = base / "tailscale" / "video" / "Upscale"
            first = DlssVideoExporter(DEFAULT_EXPORT_ROOT, access_root=lan)
            job = self.job(first)
            original = json.dumps(job)
            for physical in (lan, tailscale):
                physical.parent.mkdir(parents=True)
                exporter = DlssVideoExporter(DEFAULT_EXPORT_ROOT, access_root=physical)
                saved = exporter.export(job, b"video", b"report")
                target = physical / self.day / (self.job_id + ".mp4")
                self.assertEqual(target.read_bytes(), b"video")
                self.assertEqual(target.with_suffix(".json").read_bytes(), b"report")
                self.assertEqual(saved, job["video_export"]["path"])
                self.assertEqual(json.dumps(job), original)
                before = target.stat().st_mtime_ns
                exporter.export(job, b"video", b"report")
                self.assertEqual(target.stat().st_mtime_ns, before)

    def test_changed_saved_destination_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            exporter = DlssVideoExporter(DEFAULT_EXPORT_ROOT, access_root=root / "physical" / "Upscale")
            job = self.job(exporter)
            job["video_export"]["path"] = str(PureWindowsPath(r"X:\elsewhere") / self.day / (self.job_id + ".mp4"))
            with self.assertRaises(ValueError):
                exporter.export(job, b"video", b"report")
            self.assertEqual(list(root.iterdir()), [])

    def test_unavailable_profile_share_never_falls_back_to_working_logical_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logical = root / "logical" / "Upscale"
            logical.parent.mkdir()
            exporter = DlssVideoExporter(logical, access_root=root / "unavailable" / "Upscale")
            with self.assertRaises(OSError):
                exporter.export(self.job(exporter), b"video", b"report")
            self.assertFalse(logical.exists())

    def test_constructor_does_not_probe_or_create_a_network_directory(self):
        with patch.object(Path, "is_dir", side_effect=AssertionError("network probe")), \
             patch.object(Path, "mkdir", side_effect=AssertionError("network write")):
            with tempfile.TemporaryDirectory() as directory:
                exporter = DlssVideoExporter(DEFAULT_EXPORT_ROOT, access_root=Path(directory) / "Upscale")
                self.assertEqual(str(exporter.target(self.job_id, self.day)),
                    DEFAULT_EXPORT_ROOT + "\\" + self.day + "\\" + self.job_id + ".mp4")

    def test_physical_destination_still_rejects_different_existing_content(self):
        with tempfile.TemporaryDirectory() as directory:
            physical = Path(directory) / "Upscale"
            exporter = DlssVideoExporter(DEFAULT_EXPORT_ROOT, access_root=physical)
            job = self.job(exporter)
            exporter.export(job, b"first", b"report")
            with self.assertRaises(ValueError):
                exporter.export(job, b"second", b"report")
            self.assertEqual((physical / self.day / (self.job_id + ".mp4")).read_bytes(), b"first")


class DirectTransportsTest(unittest.TestCase):
    def test_http_profile_ignores_environment_proxy_and_preserves_target(self):
        seen = []
        def local_http(handler, request):
            seen.append((request.host, request.full_url))
            response = addinfourl(io.BytesIO(b"{}"), {}, request.full_url, 200)
            response.msg = "OK"
            return response
        with patch.dict(os.environ, {"http_proxy": "http://proxy.invalid:9999", "no_proxy": ""}, clear=True), \
             patch.object(urllib.request.HTTPHandler, "http_open", local_http):
            client = ComfyHttpClient("http://192.168.1.72:8188", client_id="test", opener=direct_http_opener())
            self.assertEqual(client.get_history("existing"), {})
        self.assertEqual(seen, [("192.168.1.72:8188", "http://192.168.1.72:8188/history/existing")])

    def test_legacy_comfy_still_uses_the_original_urlopen_path(self):
        response = Mock()
        response.__enter__ = Mock(return_value=io.BytesIO(b"{}"))
        response.__exit__ = Mock(return_value=False)
        client = ComfyHttpClient("http://bucket:8188", client_id="legacy")
        with patch("urllib.request.urlopen", return_value=response) as opener:
            self.assertEqual(client.get_history("existing"), {})
        opener.assert_called_once()

    def test_llm_explicit_transport_disables_proxy_environment_without_changing_legacy(self):
        module = "panelforge.infrastructure.llm.openai_compatible"
        with patch(module + ".OpenAI") as sdk, patch(module + ".DefaultHttpxClient") as http:
            OpenAICompatibleGateway("http://bucket:8083/v1", trust_env=False)
            http.assert_called_once_with(trust_env=False)
            self.assertIs(sdk.call_args.kwargs["http_client"], http.return_value)
            self.assertEqual(sdk.call_args.kwargs["max_retries"], 0)
            http.reset_mock()
            OpenAICompatibleGateway("http://bucket:8083/v1")
            http.assert_not_called()
            self.assertNotIn("http_client", sdk.call_args.kwargs)

    def test_websocket_15_proxy_is_disabled_for_all_profile_streams(self):
        calls = []
        def connect(url, *, proxy=True, **kwargs):
            calls.append((url, proxy, kwargs))
            return "connection"
        with patch("websockets.asyncio.client.connect", connect), patch("websockets.sync.client.connect", connect):
            self.assertEqual(direct_preview_connection("ws://192.168.1.72:8188/ws"), "connection")
            direct_thermal_connection("ws://192.168.1.72:8188/ws", 2)
            direct_dlss_connection("ws://127.0.0.1:8188/ws")
        self.assertEqual([proxy for _, proxy, _ in calls], [None, None, None])

    def test_websocket_13_and_14_do_not_receive_an_unsupported_proxy_keyword(self):
        def connect(url, *, open_timeout, close_timeout, max_size=None):
            return url
        with patch("websockets.asyncio.client.connect", connect), patch("websockets.sync.client.connect", connect):
            self.assertEqual(direct_preview_connection("ws://server/ws"), "ws://server/ws")
            self.assertEqual(direct_thermal_connection("ws://server/ws", 2), "ws://server/ws")
            self.assertEqual(direct_dlss_connection("ws://local/ws"), "ws://local/ws")


class OfflineExamplesTest(unittest.TestCase):
    def test_lan_embedding_uses_only_cached_files_even_when_the_index_is_missing(self):
        for offline in (False, True):
            with self.subTest(offline=offline), tempfile.TemporaryDirectory() as directory:
                embedding = Mock()
                with patch.dict(sys.modules, {"fastembed": Mock(TextEmbedding=embedding)}), \
                     patch.object(LocalPromptExampleLibrary, "_index_is_current", return_value=False):
                    library = LocalPromptExampleLibrary(directory, local_files_only=offline)
                    library._embedding_model()
                self.assertEqual(embedding.call_args.kwargs["local_files_only"], offline)
                self.assertFalse(embedding.call_args.kwargs["cuda"])



class NetworkBadgeTest(unittest.TestCase):
    def test_public_mode_is_explicit_and_contains_no_connection_secrets(self):
        for mode, label in ((None, None), ("lan", "Local"), ("tailscale", "Tailscale")):
            with self.subTest(mode=mode), TestClient(create_app(Mock(), network_mode=mode)) as client:
                response = client.get("/api/network-mode")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"mode": mode, "label": label})
                self.assertIn('id="network-mode"', client.get("/").text)

    def test_unknown_mode_cannot_produce_a_badge(self):
        with self.assertRaises(ValueError):
            create_app(Mock(), network_mode="unknown")


class ProfileWiringTest(unittest.TestCase):
    def test_every_server_client_and_monitor_receives_the_same_profile(self):
        for mode, host in (("lan", "192.168.1.72"), ("tailscale", "bucket")):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
                root = Path(directory)
                stack.enter_context(patch.dict(os.environ, {}, clear=True))
                args = run_lab.parse_args([
                    "--network-mode", mode, "--workspace", str(root / "workspace"),
                    "--mobile-port", "0", "--krea2-models-root",
                    "\\\\sshfs.r\\malmo@" + host + r"\data\models\ComfyUi\diffusion_models\Krea2",
                    "--krea2-projects-root", str(root / "projects"),
                    "--krea2-creations-root", str(root / "creations"),
                    "--krea2-wildcards-root", str(root / "wildcards"),
                    "--dlss-root", str(root / "comfy"), "--dlss-output-root", str(root / "outputs"),
                ])
                clients = []
                def make_comfy(base_url, *, client_id, timeout=30, opener=None):
                    client = Mock(base_url=base_url, client_id=client_id, timeout=timeout,
                                  websocket_url=base_url.replace("http://", "ws://") + "/ws")
                    client.list_unet_models.return_value = ()
                    client.list_lora_models.return_value = ()
                    clients.append((client, opener))
                    return client
                stack.enter_context(patch.object(run_lab, "ComfyHttpClient", side_effect=make_comfy))
                gateways = stack.enter_context(patch.object(run_lab, "OpenAICompatibleGateway"))
                resources = stack.enter_context(patch.object(run_lab, "LocalKrea2ResourceCatalog"))
                examples = stack.enter_context(patch.object(run_lab, "LocalPromptExampleLibrary"))
                stack.enter_context(patch.object(run_lab, "H3LoraResourceCatalog"))
                stack.enter_context(patch.object(run_lab, "create_app", side_effect=lambda runner, **kwargs: kwargs))
                capture = run_lab.build_app(args)
                self.assertEqual(len(clients), 10)
                self.assertTrue(all(callable(opener) for _, opener in clients))
                for client, _ in clients:
                    expected = "http://127.0.0.1:8188" if client.client_id == "panelforge-dlss" else f"http://{host}:8188"
                    self.assertEqual(client.base_url, expected)
                self.assertEqual(gateways.call_args_list[0].args[0], f"http://{host}:8083/v1")
                self.assertTrue(all(call.kwargs["trust_env"] is False for call in gateways.call_args_list))
                self.assertEqual(resources.call_args.kwargs["models_root"], args.krea2_models_root)
                self.assertEqual(resources.call_args.kwargs["loras_root"], args.krea2_loras_root)
                self.assertEqual(capture["model_runtime"].base_url, f"http://{host}:8083")
                self.assertEqual(capture["network_mode"], mode)
                self.assertEqual(examples.call_args.kwargs.get("local_files_only", False), mode == "lan")
                self.assertTrue(callable(capture["dlss"].runtime._opener))
                self.assertIs(capture["video_preview_connector"], direct_preview_connection)
                self.assertIs(capture["runtime_monitor_connector"], direct_preview_connection)
                exporter = capture["dlss"].video_exporter
                self.assertEqual(str(exporter.root), DEFAULT_EXPORT_ROOT)
                self.assertEqual(exporter.access_root, args.dlss_video_export_access_root)
                self.assertIs(capture["dlss"].progress.connector, direct_dlss_connection)


if __name__ == "__main__":
    unittest.main()