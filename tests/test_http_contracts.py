"""Compatibility with the HTTP surface recorded before patch 2."""
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import get_type_hints
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi import routing
from fastapi.testclient import TestClient
from panelforge.features.lab.web import create_app


class LabHttpContractsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((ROOT / "tests/fixtures/lab-http-before-patch2.json").read_text(encoding="utf-8"))
        # No services or workers are started; the router dependencies are optional.
        cls.app = create_app(SimpleNamespace())

    def test_recorded_routes_keep_their_paths_methods_names_statuses_and_parameters(self):
        # Recent FastAPI versions retain included routers as nested route groups.
        # Use the effective paths/metadata; older versions already expose a flat list.
        iter_routes = getattr(routing, "iter_route_contexts", iter)
        # WebSocket contexts carry their effective path on a Starlette route.
        registered_routes = tuple(getattr(context, "starlette_route", None) or context
                                  for context in iter_routes(self.app.routes))
        for expected in self.contract["routes"]:
            with self.subTest(path=expected["path"], method=expected["method"]):
                routes = [route for route in registered_routes
                          if getattr(route, "path", None) == expected["path"]
                          and (expected["method"] in (getattr(route, "methods", None) or ())
                               or (expected["method"] == "WEBSOCKET"
                                   and isinstance(getattr(route, "original_route", route), routing.APIWebSocketRoute)))]
                self.assertEqual(len(routes), 1)
                route = routes[0]
                self.assertEqual(route.endpoint.__name__, expected["endpoint"])
                self.assertEqual(getattr(route, "status_code", None), expected["status_code"])
                annotations = expected["annotations"]
                if expected["path"] == "/":
                    # Lot 4 renders the same HTML endpoint from a versioned
                    # asset snapshot instead of streaming the source file.
                    annotations = {**annotations, "return": "HTMLResponse"}
                self.assertEqual(route.endpoint.__annotations__, annotations)

    def test_request_models_still_resolve_in_openapi_after_the_move(self):
        schema = self.app.openapi()
        for expected in self.contract["routes"]:
            if expected["method"] == "WEBSOCKET" or expected["path"] == "/":
                continue
            with self.subTest(path=expected["path"], method=expected["method"]):
                self.assertIn(expected["method"].lower(), schema["paths"][expected["path"]])

    def test_response_contracts_cover_the_existing_keys_and_remain_resolvable(self):
        for expected in self.contract["responses"]:
            with self.subTest(serializer=expected["serializer"]):
                module = importlib.import_module("panelforge.features.lab." + expected["module"])
                contract = getattr(module, expected["contract"])
                fields = get_type_hints(contract)
                self.assertEqual(set(fields), set(expected["fields"]))
                self.assertEqual(contract.__required_keys__, set(expected["fields"]))
                serializer = getattr(module, expected["serializer"])
                self.assertIs(get_type_hints(serializer)["return"], contract)

    def test_unconfigured_workshops_keep_their_503_responses(self):
        with TestClient(self.app) as client:
            for path, detail in (
                ("/api/social-lab/projects", "Social Lab is not configured"),
                ("/api/image-lab/krea2-assisted/projects", "KREA2 Assisted Creation is not configured"),
                ("/api/image-lab/krea2-edit/sources", "KREA2 Edit Lab is not configured"),
                ("/api/h3-render/checkpoints", "H3 Base renderer is not configured"),
                ("/api/prompt-lab/models", "Prompt engine is not configured"),
            ):
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.json(), {"detail": detail})

