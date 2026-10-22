import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi import HTTPException
from panelforge.features.lab.http_streaming import stream_response
from panelforge.features.lab.http_support import http_errors


def event(**updates):
    values = dict(kind=SimpleNamespace(value="delta"), phase=SimpleNamespace(value="generating"),
                  text="Un café\nUne suite", progress=0.25, error=None,
                  finish_reason=None, max_tokens=1024, document_stage=SimpleNamespace(value="final_prompt"),
                  project=None, source=None, session=None, composition=None)
    return SimpleNamespace(**{**values, **updates})


async def frames(response):
    chunks = [chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk async for chunk in response.body_iterator]
    return [(frame.splitlines()[0].removeprefix("event: "), json.loads(frame.splitlines()[1].removeprefix("data: ")))
            for frame in "".join(chunks).strip().split("\n\n")]


class StreamingContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_each_workshop_retains_its_optional_fields_and_entity_name(self):
        cases = [
            ("KREA2", "project", ("error",), False, {"error": None}),
            ("H3", "project", ("error",), False, {"error": None}),
            ("Social", "project", ("error",), False, {"error": None}),
            ("Edit", "source", (), False, {}),
            ("Prompt", "session", ("finish_reason", "max_tokens"), False, {"finish_reason": None, "max_tokens": 1024}),
            ("Composition", "composition", ("finish_reason", "max_tokens"), True, {"finish_reason": None, "max_tokens": 1024, "document_stage": "final_prompt"}),
        ]
        for name, entity, fields, stage, extra in cases:
            with self.subTest(workshop=name):
                calls = []
                related = {"id": "already-produced", "nullable": None}
                def serialize(value):
                    calls.append(value)
                    return value
                response = stream_response(iter([event(), event(**{entity: related})]), serialize=serialize,
                                           entity=entity, fields=fields, document_stage=stage)
                self.assertEqual(calls, [])
                self.assertEqual(response.headers["cache-control"], "no-cache, no-transform")
                self.assertEqual(response.headers["x-accel-buffering"], "no")
                self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
                actual = await frames(response)
                expected = dict(kind="delta", phase="generating", text="Un café\nUne suite", progress=0.25, **extra)
                self.assertEqual(actual, [("delta", expected), ("delta", {**expected, entity: related})])
                self.assertEqual(calls, [related])

    async def test_midstream_failure_keeps_previous_events_and_emits_the_existing_error_shape(self):
        started = []
        def events():
            started.append(True)
            yield event()
            raise ValueError("interrupted stream")
        response = stream_response(events(), serialize=lambda value: value)
        self.assertEqual(started, [])
        actual = await frames(response)
        self.assertEqual(actual[0][0], "delta")
        self.assertEqual(actual[1], ("error", {"kind": "error", "phase": "failed", "message": "interrupted stream"}))

    async def test_nonfinite_json_becomes_an_error_event(self):
        response = stream_response(iter([event(progress=float("nan"))]), serialize=lambda value: value)
        actual = await frames(response)
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0][0], "error")
        self.assertEqual(actual[0][1]["phase"], "failed")
        self.assertIn("JSON", actual[0][1]["message"])

    async def test_composition_keeps_null_document_stage(self):
        response = stream_response(iter([event(document_stage=None)]), serialize=lambda value: value,
                                   entity="composition", fields=("finish_reason", "max_tokens"), document_stage=True)
        actual = await frames(response)
        self.assertIn("document_stage", actual[0][1])
        self.assertIsNone(actual[0][1]["document_stage"])


class HttpErrorContractTests(unittest.TestCase):
    def test_default_mapping_preserves_status_detail_and_exception_cause(self):
        for error, status, detail in (
            (KeyError("id"), 404, "project not found"),
            (FileNotFoundError("file"), 404, "project not found"),
            (TypeError("bad type"), 422, "bad type"),
            (ValueError("bad value"), 422, "bad value"),
        ):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(HTTPException) as caught:
                    with http_errors("project not found"):
                        raise error
                self.assertEqual((caught.exception.status_code, caught.exception.detail), (status, detail))
                self.assertIs(caught.exception.__cause__, error)

    def test_route_specific_exception_groups_are_not_widened(self):
        for error in (FileNotFoundError("file"), TypeError("type"), RuntimeError("runtime")):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(type(error)) as caught:
                    with http_errors("missing", missing=(KeyError,), invalid=(ValueError,)):
                        raise error
                self.assertIs(caught.exception, error)
        with self.assertRaises(HTTPException) as caught:
            with http_errors("missing", invalid=(RuntimeError, TypeError, ValueError)):
                raise RuntimeError("declared validation failure")
        self.assertEqual((caught.exception.status_code, caught.exception.detail), (422, "declared validation failure"))

    def test_workshop_conflicts_keep_their_original_response(self):
        conflict = HTTPException(409, "already submitted")
        with self.assertRaises(HTTPException) as caught:
            with http_errors("missing"):
                raise conflict
        self.assertIs(caught.exception, conflict)
