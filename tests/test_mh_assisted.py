"""User-run MH regressions. All model/render/catalogue ports are local fakes."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.mh_assisted import MhAssistedService
from panelforge.application import mh_assisted_prompting as prompting
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
        self.assertEqual(request.operation_id, "mh.assisted@1.1.0")
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


class MhPromptingTests(MhFixture):
    def payload(self):
        return json.loads(prompting.user_prompt(self.current(), "Actualise avec les références actuelles."))

    def test_anatomy_constraints_reach_saved_prompt_and_attempt_in_requested_language(self):
        for language in ("en", "zh"):
            with self.subTest(language=language):
                self.configure(prompt_language=language)
                stage = self.update(draft="Une personne debout.", model_id="fake-vision")
                _, message_id = self.service.begin_message(self.project_id, self.stage_id,
                    revision=stage["revision"], request_id="language-" + language)
                before = len(self.gateway.requests)
                self.service.execute_message(self.project_id, self.stage_id, message_id)
                message = self.current()["messages"][-1]
                self.assertEqual(message["status"], "succeeded", message.get("error"))
                self.assertEqual(len(self.gateway.requests), before + 1)
                self.assertEqual(json.loads(message["raw"])["prompt"], self.current()["prompt"].split("\n\n")[0])
                self.assertTrue(self.current()["prompt"].endswith(prompting.POSE_CONSTRAINTS[language]))
                self.assertEqual(self.queue("render-" + language)["prompt"], self.current()["prompt"])
                self.assertNotIn(prompting.POSE_CONSTRAINTS[language], self.payload()["CURRENT TARGET"])

    def test_finalization_is_idempotent_and_revalidates_reference_labels_and_length(self):
        context = policy.context_snapshot(self.current())
        prompt = prompting.finalize_prompt("Use <Picture 1> for posture.", context)
        self.assertEqual(prompting.finalize_prompt(prompt, context), prompt)
        with self.assertRaises(ValueError):
            prompting.finalize_prompt("Use <Picture 2> for posture.", context)
        with self.assertRaises(ValueError):
            prompting.finalize_prompt("<Picture 1> " + "x" * 23980, context)

    def test_no_pose_and_legacy_replies_and_manual_prompts_are_not_rewritten(self):
        raw_prompt = "Use <Picture 1> for the subject."
        raw = json.dumps({"message": "Proposition.", "prompt": raw_prompt})
        context = policy.context_snapshot(self.current())
        old = {"policy_version": "1.0.0", "context": context}
        self.assertEqual(self.service._decode_message(old, raw)[1], raw_prompt)
        self.reference("Sujet", "render")
        self.configure(pose_id="")
        context = policy.context_snapshot(self.current())
        self.assertEqual(prompting.finalize_prompt(raw_prompt, context), raw_prompt)
        self.configure(pose_id="pose-a")
        manual = "Use <Picture 1> for posture and <Picture 2> for identity. A wooden articulated toy."
        self.update(prompt=manual)
        self.assertEqual(self.queue()["prompt"], manual)

    def test_late_reply_keeps_frozen_pose_and_language_without_overwriting_current_prompt(self):
        self.gateway.hook = lambda: self.configure(prompt_language="zh")
        message = self.message()
        self.assertFalse(message["applied"])
        self.assertTrue(message["prompt"].endswith(prompting.POSE_CONSTRAINTS["en"]))
        self.assertFalse(policy.prompt_is_ready(self.current()))

    def test_pose_change_discards_obsolete_assistant_description_but_keeps_user_choices(self):
        message = self.message("Conserve une lumière bleue.")
        old_context = deepcopy(message["context"])
        self.assertFalse(self.payload()["REFERENCE CHANGES"]["pose_changed"])
        self.configure(pose_id="pose-b")
        payload = self.payload()
        self.assertTrue(payload["REFERENCE CHANGES"]["baseline_known"])
        self.assertTrue(payload["REFERENCE CHANGES"]["pose_changed"])
        self.assertEqual(payload["REFERENCE CHANGES"]["modified"], ["mh-pose"])
        self.assertEqual(payload["CONVERSATION"], [{"user": "Conserve une lumière bleue.", "assistant": ""}])
        self.assertEqual(self.current()["messages"][0]["context"], old_context)
        self.assertEqual(self.current()["messages"][0]["reply"], message["reply"])

    def test_replacement_role_and_usage_changes_are_explicit_and_tags_follow_current_inputs(self):
        original = self.reference("Sujet", "render", "blue")
        self.message()
        self.service.add_references(self.project_id, self.stage_id, revision=self.current()["revision"],
            request_id=str(uuid4()), replace_id=original["id"],
            references=[dict(content=png("red"), name="Autre sujet", role="Identité", usage="render")])
        payload = self.payload()
        new_id = payload["REFERENCE CHANGES"]["added"][0]
        self.assertEqual(payload["REFERENCE CHANGES"]["removed"], [original["id"]])
        self.assertFalse(payload["REFERENCE CHANGES"]["pose_changed"])
        refs = deepcopy(self.current()["references"])
        next(ref for ref in refs if ref["id"] == new_id).update(role="Éclairage", usage="assistant")
        self.update(references=refs)
        self.assertEqual(len(self.payload()["CURRENT INPUTS"]["render_inputs"]), 1)
        self.assertTrue(self.payload()["REFERENCE CHANGES"]["render_tags_changed"])
        # Same identity, different role/usage must also be reported as a modification.
        baseline = deepcopy(self.current())
        baseline["prompt"] = "Use <Picture 1>."
        baseline["messages"] = [dict(status="succeeded", prompt=baseline["prompt"],
                                     context=policy.context_snapshot(baseline))]
        next(ref for ref in baseline["references"] if ref["id"] == new_id).update(role="Décor", usage="render")
        changes = prompting.reference_changes(baseline, policy.context_snapshot(baseline))
        self.assertEqual(changes["modified"], [new_id])
        self.assertTrue(changes["render_tags_changed"])

    def test_unknown_manual_baseline_is_conservative_and_restored_attempt_can_supply_context(self):
        self.update(prompt="A manually composed scene using <Picture 1>.")
        payload = self.payload()
        self.assertFalse(payload["REFERENCE CHANGES"]["baseline_known"])
        self.assertTrue(payload["REFERENCE CHANGES"]["pose_changed"])
        attempt = deepcopy(self.queue())
        self.configure(pose_id="pose-b")
        other_context = policy.context_snapshot(self.current())
        self.service.restore_attempt(self.project_id, self.stage_id, attempt["id"], revision=self.current()["revision"])
        self.assertTrue(self.payload()["REFERENCE CHANGES"]["baseline_known"])
        self.assertFalse(self.payload()["REFERENCE CHANGES"]["pose_changed"])
        self.assertEqual(self.current()["attempts"][0], attempt)
        # A later reply can reuse the same words for another pose; prefer the restored context.
        restored = deepcopy(self.current())
        restored["messages"].append(dict(status="succeeded", prompt=restored["prompt"], context=other_context))
        changes = prompting.reference_changes(restored, policy.context_snapshot(restored))
        self.assertFalse(changes["pose_changed"])
        self.assertEqual(changes["modified"], [])

    def test_crop_uncertainty_reaches_request_and_style_only_change_does_not_replace_pose(self):
        stage = deepcopy(self.current())
        stage["creative"]["pose"].update(confidence="low", review_note="Genou et pied hors cadre.",
                                          elevation="Contre-plongée")
        payload = json.loads(prompting.user_prompt(stage, "Utilise cette pose."))
        self.assertEqual(payload["CURRENT INPUTS"]["creative"]["pose"]["review_note"], "Genou et pied hors cadre.")
        self.message()
        self.configure(art_style_id="style-one", prompt_language="zh")
        self.assertFalse(self.payload()["REFERENCE CHANGES"]["pose_changed"])
        self.assertEqual(self.payload()["REFERENCE CHANGES"]["modified"], [])


class MhReferenceUploadTests(MhFixture):
    @staticmethod
    def upload(color="blue", **metadata):
        return {"content":png(color), "name":"Sujet.png", "role":"Identité uniquement", "usage":"render", **metadata}

    def test_initial_images_roles_and_usage_reach_first_prompt_and_creation_replay(self):
        uploads = [self.upload(), {**self.upload("red"), "role": "Tenue uniquement"},
                   {**self.upload("white"), "usage": "assistant", "role": "Lumière uniquement"}]
        request = dict(request_id=str(uuid4()), name="Plusieurs références", pose_id="pose-b",
                       preset_id="preset-one", references=uploads)
        project = self.service.create_assisted(**request)
        self.assertEqual(self.service.create_assisted(**request), project)
        self.project_id, self.stage_id = project["id"], project["active_stage_id"]
        refs = self.current()["references"]
        self.assertEqual(len({r["name"] for r in refs}), 5)
        self.assertEqual(len(policy.render_inputs(self.current())), 3)
        self.assertEqual(self.message()["status"], "succeeded")
        sent = self.gateway.requests[-1]
        self.assertEqual(len(sent.images), 5)
        context = json.loads(sent.user_prompt)["CURRENT INPUTS"]
        self.assertEqual([r["role"] for r in context["render_inputs"]][1:], ["Identité uniquement", "Tenue uniquement"])
        self.assertEqual([r["tag"] for r in context["render_inputs"]], ["<Picture 1>", "<Picture 2>", "<Picture 3>"])
        with self.assertRaises(QwenEditConflict):
            self.service.create_assisted(**{**request, "references": list(reversed(uploads))})

    def test_creation_limits_include_pose_and_preset_and_reject_assistant_only(self):
        before = len(self.store.list())
        invalid = [dict(pose_id="pose-a", references=[self.upload()] * 9),
                   dict(references=[{**self.upload(), "usage":"assistant"}]),
                   dict(pose_id="pose-a", preset_id="preset-one",
                        references=[{**self.upload(), "usage":"assistant"}] * 31)]
        for choices in invalid:
            with self.subTest(choices=list(choices)), self.assertRaises(ValueError):
                self.service.create_assisted(request_id=str(uuid4()), name="Limite", **choices)
        self.assertEqual(len(self.store.list()), before)
        valid = self.service.create_assisted(request_id=str(uuid4()), name="Neuf", references=[self.upload()] * 9)
        self.assertEqual(len(policy.render_inputs(valid["stages"][0])), 9)

    def test_atomic_batch_retry_and_replacement_at_capacity_preserve_attempt(self):
        args = dict(revision=self.current()["revision"], request_id=str(uuid4()), references=[self.upload()] * 8)
        first = self.service.add_references(self.project_id, self.stage_id, **args)
        self.assertEqual(self.service.add_references(self.project_id, self.stage_id, **args), first)
        self.assertEqual(len(policy.render_inputs(self.current())), 9)
        with self.assertRaises(QwenEditConflict):
            self.service.add_references(self.project_id, self.stage_id, **{**args, "references":[self.upload("red")]})
        self.message(); attempt = deepcopy(self.queue())
        original = deepcopy(self.current()["references"][3])
        replace = dict(revision=self.current()["revision"], request_id=str(uuid4()),
                       references=[{**self.upload("red"), "name":"Remplacement.png"}], replace_id=original["id"])
        result = self.service.add_references(self.project_id, self.stage_id, **replace)
        self.assertEqual(result, self.service.add_references(self.project_id, self.stage_id, **replace))
        stage = self.current()
        self.assertEqual(len(policy.render_inputs(stage)), 9)
        self.assertEqual(policy.render_inputs(stage)[3]["name"], "Remplacement.png")
        self.assertFalse(next(r for r in stage["references"] if r["id"] == original["id"])["active"])
        self.assertFalse(policy.prompt_is_ready(stage))
        self.assertEqual(stage["attempts"][0]["context"], attempt["context"])
        self.service.restore_attempt(self.project_id, self.stage_id, attempt["id"], revision=stage["revision"])
        self.assertEqual(self.current()["references"], attempt["context"]["references"])

    def test_failed_batch_and_protected_replacement_do_not_change_project(self):
        before = self.service.get(self.project_id)
        cases = [dict(references=[self.upload(), {**self.upload(), "content":b"not an image"}]),
                 dict(references=[self.upload()] * 9),
                 dict(references=[self.upload()], replace_id="mh-pose"),
                 dict(references=[{**self.upload(), "role":"x" * 301}])]
        for case in cases:
            with self.subTest(case=list(case)), self.assertRaises((ValueError, OSError)):
                self.service.add_references(self.project_id, self.stage_id, revision=self.current()["revision"],
                                            request_id=str(uuid4()), **case)
            self.assertEqual(self.service.get(self.project_id), before)


class MhWebTests(MhFixture):
    def test_multipart_multi_creation_batch_replacement_and_legacy_upload(self):
        app = FastAPI(); app.include_router(mh_assisted_router(self.service))
        with TestClient(app) as client:
            api = "/api/image-lab/mh-assisted"
            metadata = [dict(name="Identité", role="Visage", usage="render"),
                        dict(name="Lumière", role="Éclairage", usage="assistant")]
            data = dict(request_id=str(uuid4()), name="Multi", reference_details=json.dumps(metadata))
            files = [("references", ("one.png", png(), "image/png")), ("references", ("two.png", png("red"), "image/png"))]
            response = client.post(api + "/projects", data=data, files=files)
            self.assertEqual(response.status_code, 201, response.text)
            project = response.json()["project"]; stage = project["stages"][0]
            self.assertEqual([r["role"] for r in stage["references"]], ["Visage", "Éclairage"])
            self.assertEqual(client.post(api + "/projects", data=data, files=files).json()["project"], project)
            self.assertEqual(client.post(api + "/projects", data={**data, "reference_details":"[]"}, files=files).status_code, 422)
            url = f"{api}/projects/{project['id']}/stages/{stage['id']}/references/batch"
            batch = dict(revision=stage["revision"], request_id=str(uuid4()), replace_id=stage["references"][0]["id"])
            replacement = [("images", ("new.png", png("green"), "image/png"))]
            replaced = client.post(url, data=batch, files=replacement)
            self.assertEqual(replaced.status_code, 201, replaced.text)
            self.assertEqual(client.post(url, data=batch, files=replacement).json(), replaced.json())
            legacy = client.post(api + "/projects", data=dict(request_id=str(uuid4()), name="Legacy"),
                                 files={"reference": ("old.png", png(), "image/png")})
            self.assertEqual(legacy.status_code, 201, legacy.text)
            self.assertEqual(len(legacy.json()["project"]["stages"][0]["render_inputs"]), 1)

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
