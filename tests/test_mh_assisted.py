"""User-run MH regressions. All model/render/catalogue ports are local fakes."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.mh_assisted import MhAssistedService
from panelforge.application.qwen_edit import QwenEditConflict
from panelforge.domain.krea2_art_direction import Krea2ArtDirection
from panelforge.domain import mh_assisted as policy
from panelforge.features.lab.mh_assisted_web import mh_assisted_router
from panelforge.infrastructure.minimax_edit_images import PillowMinimaxEditImages
from panelforge.infrastructure.presets.minimax_edit import load_minimax_edit_workflow
from panelforge.infrastructure.storage.mh_assisted import LocalMhAssistedStore
from tests.test_qwen_edit import QwenEditFixture, Comfy, png

ROOT = Path(__file__).resolve().parents[1]


class MhComfy(Comfy):
    def __init__(self, output_node_id):
        super().__init__()
        self.output_node_id = output_node_id

    def get_history(self, execution_id):
        value = super().get_history(execution_id)
        outputs = value[execution_id]["outputs"]
        value[execution_id]["outputs"] = {self.output_node_id: next(iter(outputs.values()))}
        return value


class Poses:
    def __init__(self):
        self.calls = []
        self.revision = "revision-1"

    def status(self):
        return {"state": "ready", "pose_count": 2, "image_count": 2}

    def reference(self, identity):
        if identity not in {"pose-a", "pose-b"}:
            raise FileNotFoundError(identity)
        self.calls.append(identity)
        return dict(id=identity, pose_id=identity, number="P001", name="Pose témoin", angle="Face",
                    category="Debout", family="Corps entier", catalog_revision=self.revision,
                    source_url="https://ai-pose-gallery.pages.dev/img/fixture.png", sha256="fixture"), png("grey" if identity == "pose-a" else "silver")


class MhFixture(QwenEditFixture):
    def setUp(self):
        super().setUp()
        self.qwen_store = self.store
        self.poses = Poses()
        example = self.assets.create(png("orange"), media_type="image/png")
        self.art = Krea2ArtDirection("fixture", "style-one", "Joaillerie", "Matières", "Gemstone treatment.", "v1")
        self.preset = SimpleNamespace(preset_id="preset-one", revision=3, name="Preset témoin", prompt="Artistic example only.",
            image_asset_id=example.asset_id, source_project_id="source-project", source_attempt_id="source-attempt",
            art_direction=self.art)
        self.style_source = SimpleNamespace(list_style_presets=lambda: (self.preset,), list_art_styles=lambda: (self.art,))
        self.workflow = load_minimax_edit_workflow(ROOT / "workflows/image.edit/minimax-h3-still/1.3.0")
        self.comfy = MhComfy(self.workflow.output_node_id)
        self.store = LocalMhAssistedStore(self.temporary.name)
        self.service = MhAssistedService(gateway=self.gateway, workflow=self.workflow, comfy=self.comfy,
            assets=self.assets, projects=self.store, images=PillowMinimaxEditImages(),
            style_source=self.style_source, poses=self.poses, poll_interval=.001)
        self.project = self.service.create_assisted(request_id=str(uuid4()), name="Création MH", pose_id="pose-a")
        self.project_id, self.stage_id = self.project["id"], self.project["active_stage_id"]

    def configure(self, **changes):
        s = self.current()
        self.service.configure(self.project_id, self.stage_id, revision=s["revision"], changes=changes)
        return self.current()


class MhAssistedTests(MhFixture):
    def test_pose_only_composition_has_no_fixed_source_and_separate_store(self):
        s = self.current()
        self.assertIsNone(s["source_asset_id"])
        self.assertEqual(s["mode"], "composition")
        self.assertEqual([r["id"] for r in policy.render_inputs(s)], ["mh-pose"])
        self.assertEqual(s["settings"]["resolution"], "2")
        self.assertFalse(s["settings"]["reuse_seed"])
        self.assertNotEqual(self.store.root, self.qwen_store.root)
        self.assertTrue(self.service.list()[0]["thumbnail_asset_id"])

    def test_reference_required_and_preset_is_not_a_render_reference(self):
        count = len(self.store.list())
        for choices in ({}, {"preset_id": "preset-one"}):
            with self.assertRaisesRegex(ValueError, "référence"):
                self.service.create_assisted(request_id=str(uuid4()), name="Sans référence", intention="A scene", **choices)
        self.assertEqual(len(self.store.list()), count)
        p = self.service.create_assisted(request_id=str(uuid4()), name="Sujet seul", content=png("blue"))
        self.assertIsNone(p["stages"][0]["creative"]["pose"])
        self.assertEqual(len(policy.render_inputs(p["stages"][0])), 1)

    def test_creation_retry_does_not_duplicate_project_or_download(self):
        identity = str(uuid4())
        first = self.service.create_assisted(request_id=identity, name="Idempotent", pose_id="pose-b")
        calls = len(self.poses.calls)
        again = self.service.create_assisted(request_id=identity, name="Idempotent", pose_id="pose-b")
        self.assertEqual(first, again)
        self.assertEqual(len(self.poses.calls), calls)
        with self.assertRaises(QwenEditConflict):
            self.service.create_assisted(request_id=identity, name="Changed", pose_id="pose-b")

    def test_preset_language_and_direction_reach_assistant_but_only_pose_reaches_renderer(self):
        self.configure(preset_id="preset-one", prompt_language="zh", art_style_id="style-one")
        m = self.message()
        self.assertEqual(m["status"], "succeeded", m.get("error"))
        request = self.gateway.requests[-1]
        self.assertEqual(request.operation_id, "mh.assisted@1.0.0")
        context = json.loads(request.user_prompt)["CURRENT INPUTS"]
        self.assertEqual(context["creative"]["prompt_language"], "zh")
        self.assertEqual(context["creative"]["style_preset"]["revision"], 3)
        self.assertEqual(context["creative"]["art_direction"]["style_id"], "style-one")
        self.assertNotIn("settings", context["creative"]["style_preset"])
        self.assertEqual(len(request.images), 2)
        self.assertEqual([r["id"] for r in context["render_inputs"]], ["mh-pose"])
        a = self.queue()
        self.service.execute_attempt(self.project_id, self.stage_id, a["id"])
        result = self.current()["attempts"][-1]
        self.assertEqual(result["status"], "succeeded", result["error"])
        self.assertEqual(len(self.comfy.uploads), 1)
        self.assertEqual(result["context"]["creative"]["pose"]["id"], "pose-a")

    def test_queued_attempt_keeps_pose_and_creative_choices_after_changes(self):
        self.configure(preset_id="preset-one", art_style_id="style-one", prompt_language="zh")
        self.message(); a = deepcopy(self.queue())
        self.configure(pose_id="pose-b", preset_id="", art_style_id="", prompt_language="en")
        self.assertFalse(policy.prompt_is_ready(self.current()))
        self.service.execute_attempt(self.project_id, self.stage_id, a["id"])
        after = self.current()["attempts"][-1]
        self.assertEqual(after["context"], a["context"])
        self.assertEqual(after["status"], "succeeded", after["error"])
        self.service.restore_attempt(self.project_id, self.stage_id, a["id"], revision=self.current()["revision"])
        restored = self.current()
        self.assertEqual(restored["creative"], a["context"]["creative"])
        self.assertEqual(restored["references"], a["context"]["references"])
        self.assertTrue(policy.prompt_is_ready(restored))

    def test_removing_only_reference_is_atomic_and_stale_revision_rejected(self):
        before = self.service.get(self.project_id)
        with self.assertRaises(ValueError):
            self.configure(pose_id="")
        self.assertEqual(before, self.service.get(self.project_id))
        revision = self.current()["revision"]
        self.configure(prompt_language="zh")
        with self.assertRaises(QwenEditConflict):
            self.service.configure(self.project_id, self.stage_id, revision=revision, changes={"pose_id":"pose-b"})
        self.reference("Sujet", "render", "blue")
        self.configure(pose_id="")
        self.assertIsNone(self.current()["creative"]["pose"])

    def test_reserved_pose_cannot_be_relabelled_or_disabled_by_generic_update(self):
        refs = deepcopy(self.current()["references"])
        refs[0]["usage"] = "assistant"
        with self.assertRaisesRegex(ValueError, "sélecteur"):
            self.update(references=refs)
        self.assertEqual(self.current()["references"][0]["usage"], "render")

    def test_explicit_reselection_can_adopt_a_new_catalogue_revision_without_changing_old_attempt(self):
        self.message(); self.queue()
        self.poses.revision = "revision-2"
        self.configure(pose_id="pose-a")
        self.assertEqual(self.current()["creative"]["pose"]["catalog_revision"], "revision-2")
        self.assertEqual(self.current()["attempts"][0]["context"]["creative"]["pose"]["catalog_revision"], "revision-1")
        self.assertFalse(policy.prompt_is_ready(self.current()))

    def test_late_prompt_does_not_overwrite_changed_language(self):
        self.gateway.hook = lambda: self.configure(prompt_language="zh")
        m = self.message()
        self.assertEqual(m["status"], "succeeded")
        self.assertFalse(m["applied"])
        self.assertFalse(policy.prompt_is_ready(self.current()))

    def test_language_and_pose_updates_preserve_prior_attempts_on_disk(self):
        self.message(); a = self.queue()
        self.configure(prompt_language="zh", art_style_id="style-one")
        loaded = LocalMhAssistedStore(self.temporary.name).get(self.project_id)
        self.assertEqual(loaded["stages"][0]["attempts"][0]["context"], a["context"])
        self.assertEqual(loaded["stages"][0]["creative"]["prompt_language"], "zh")
        with self.assertRaises(ValueError):
            self.configure(prompt_language="xx")
        with self.assertRaises(ValueError):
            policy.Settings(resolution="source", reference_mode="native")

    def test_render_request_replay_uses_original_attempt(self):
        self.message(); first = self.queue("same-render")
        self.configure(prompt_language="zh")
        repeated = self.service.queue_attempt(self.project_id, self.stage_id, revision=0, request_id="same-render")
        self.assertEqual(len(repeated["stages"][0]["attempts"]), 1)
        self.assertEqual(repeated["stages"][0]["attempts"][0]["id"], first["id"])


class MhWebTests(MhFixture):
    def test_create_prepare_render_contract_and_validation_without_live_gateways(self):
        app = FastAPI(); app.include_router(mh_assisted_router(self.service))
        with TestClient(app) as client:
            api = "/api/image-lab/mh-assisted"
            spec = client.get(api + "/spec").json()
            self.assertEqual(spec["prompt_languages"], ["en", "zh"])
            self.assertEqual(client.post(api + "/projects", data={"request_id":str(uuid4()), "name":"No reference"}).status_code, 422)
            result = client.post(api + "/projects", data={"request_id":str(uuid4()), "name":"Web", "pose_id":"pose-b", "prompt_language":"zh"})
            self.assertEqual(result.status_code, 201, result.text)
            project = result.json()["project"]; s = project["stages"][0]
            url = f"{api}/projects/{project['id']}/stages/{s['id']}"
            result = client.post(url + "/messages", json={"request_id":"initial", "revision":s["revision"]})
            self.assertEqual(result.status_code, 202, result.text)
            current = client.get(f"{api}/projects/{project['id']}").json()["project"]["stages"][0]
            self.assertTrue(current["prompt_ready"])
            result = client.post(url + "/attempts", json={"request_id":"render", "revision":current["revision"]})
            self.assertEqual(result.status_code, 202, result.text)
            self.assertEqual(len(result.json()["project"]["stages"][0]["attempts"]), 1)
            self.assertEqual(client.patch(url + "/creative", json={"revision":0,"changes":{"pose_id":"pose-a"}}).status_code, 409)
            self.assertEqual(client.get(f"{api}/projects/{project['id']}/download").status_code, 200)

    def test_unconfigured_workshop_returns_503(self):
        app = FastAPI(); app.include_router(mh_assisted_router(None))
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/image-lab/mh-assisted/spec").status_code, 503)
