"""User-run regressions for identity, visual scale and REF2VA handoff; no real engines."""
from copy import deepcopy
from io import BytesIO
import json
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from test_image_transitions import TransitionFixture
from panelforge.application.image_transitions import ImageTransitionService, TransitionConflict
from panelforge.application.image_transition_sources import ImageTransitionSources
from panelforge.domain.image_transitions import active, status, factory_entry, context_key
from panelforge.domain.image_transition_references import placement, reference_state
from panelforge.features.lab.image_transitions_web import image_transitions_router
from panelforge.infrastructure.image_transition_references import PillowTransitionReferences


class ReferenceImages:
    def __init__(self):
        self.compositions = []

    def normalize_worker(self, content):
        return b"worker:" + content, (100, 400)

    def compose(self, scene, worker, position):
        self.compositions.append((scene, worker, deepcopy(position)))
        return b"scale:" + scene + worker + json.dumps(position).encode(), (1600, 900)


class ReferenceFixture(TransitionFixture):
    def visual_intention(self):
        p = self.latest()
        text = "Le personnage de <Picture 3>"
        if reference_state(p, active(p)[0])["scale"]:
            text += ", à l’échelle et au placement montrés dans <Picture 4>,"
        return text + " entre, balaie les déchets puis sort avec son balai."

    def prepare(self):
        if not self.latest().get("worker_reference"):
            return super().prepare()
        for transition in active(self.latest()):
            self.edit(transition["id"], action="Travaux", intention=self.visual_intention())
        p = self.latest()
        return self.service.review(p["id"], p["version"], [t["id"] for t in active(p)])

    def propose(self, transition_id, request_id="proposal"):
        if self.latest().get("worker_reference"):
            value = json.loads(self.gateway.raw)
            value["intention"] = self.visual_intention()
            self.gateway.raw = json.dumps(value)
        return super().propose(transition_id, request_id)

    def make_service(self):
        self.reference_images = ReferenceImages()
        return ImageTransitionService(store=self.store, assets=self.assets, images=self.images,
            gateway=self.gateway, factory=self.factory, sources=ImageTransitionSources(),
            reference_images=self.reference_images)

    def worker(self, content=b"person"):
        p = self.latest()
        return self.service.upload_worker(p["id"], p["version"], content, "Ouvrier en pied")

    def scale(self, index=0, scope="following", height=.06):
        p = self.latest()
        return self.service.set_scale(p["id"], p["version"], active(p)[index]["id"],
                                      dict(x=.4, y=.8, height=height), scope)


class TransitionReferencesTest(ReferenceFixture):
    def test_worker_is_reusable_across_friezes_and_restart_without_recreating_asset(self):
        p = self.worker()
        worker = deepcopy(p["worker_reference"])
        count = len(self.assets.values)
        restarted = self.make_service()
        self.assertEqual(restarted.worker_library()["saved"], [worker])
        other = restarted.create("Autre décor")
        other = restarted.choose_worker(other["id"], other["version"], worker["asset_id"])
        self.assertEqual(other["worker_reference"], worker)
        self.assertEqual(len(self.assets.values), count)
        self.assertEqual(self.gateway.requests, [])
        self.assertEqual(self.adapter.calls, [])

    def test_recent_selection_keeps_source_provenance_and_reuses_normalized_worker(self):
        original = self.assets.create(b"recent person", "image/png")
        p = self.latest()
        p = self.service.choose_worker(p["id"], p["version"], original.asset_id, "Récent")
        canonical = p["worker_reference"]["asset_id"]
        p = self.service.choose_worker(p["id"], p["version"], original.asset_id, "Récent")
        self.assertEqual(p["worker_reference"]["source_asset_id"], original.asset_id)
        self.assertEqual(p["worker_reference"]["asset_id"], canonical)
        self.assertEqual(self.assets.read_bytes(original.asset_id), b"recent person")
        self.assertEqual(len(self.service.worker_library()["saved"]), 1)

    def test_scale_shared_with_local_override_and_originals_intact(self):
        p = self.worker()
        originals = [(f["asset_id"], self.assets.read_bytes(f["asset_id"])) for f in p["frames"]]
        p = self.scale()
        shared = active(p)[0]["scale_setup_id"]
        self.assertEqual([t["scale_setup_id"] for t in active(p)], [shared] * 3)
        p = self.scale(1, "pair", .04)
        own = active(p)[1]["scale_setup_id"]
        self.assertNotEqual(shared, own)
        p = self.scale(0, "following", .08)
        self.assertEqual(active(p)[1]["scale_setup_id"], own)  # Stop before explicit different framing.
        self.assertEqual(active(p)[2]["scale_setup_id"], shared)
        self.assertEqual([(f["asset_id"], self.assets.read_bytes(f["asset_id"])) for f in p["frames"]], originals)
        self.assertEqual(len(self.reference_images.compositions), 3)

    def test_scale_stops_at_camera_and_later_camera_discovery_requires_reposition(self):
        self.worker()
        p = self.scale()
        camera = active(p)[1]["id"]
        p = self.edit(camera, kind="camera")
        self.assertIsNone(reference_state(p, active(p)[0])["error"])
        self.assertIn("cadrage", reference_state(p, active(p)[2])["error"])
        p = self.scale(2, "pair")
        self.assertIsNone(reference_state(p, active(p)[2])["error"])
        last_setup = active(p)[2]["scale_setup_id"]
        p = self.scale(0)
        self.assertEqual(active(p)[2]["scale_setup_id"], last_setup)

    def test_appended_pair_inherits_but_reordered_new_pair_does_not(self):
        self.worker()
        p = self.scale()
        shared = active(p)[0]["scale_setup_id"]
        p = self.service.upload(p["id"], p["version"], b"next", "Nouvelle étape")
        self.assertEqual(active(p)[-1]["scale_setup_id"], shared)
        ids = [f["id"] for f in p["frames"]]
        p = self.service.order(p["id"], p["version"], [ids[0], ids[2], ids[1], *ids[3:]])
        self.assertNotIn("scale_setup_id", active(p)[0])
        self.assertNotIn("scale_setup_id", active(p)[1])

    def test_four_visual_inputs_and_workforce_reach_proposal_then_factory(self):
        self.worker()
        p = self.scale()
        p = self.service.update(p["id"], p["version"], {"settings": {"crew_size": "industrial"}})
        identity = active(p)[0]["id"]
        p = self.propose(identity)
        request = self.gateway.requests[-1]
        self.assertEqual(request.operation_id, "image.transitions.propose@3.1.0")
        self.assertEqual(len(request.images), 4)
        setup = reference_state(p, active(p)[0])["scale"]
        expected = [p["frames"][0]["asset_id"], p["frames"][1]["asset_id"],
                    p["worker_reference"]["asset_id"], setup["asset_id"]]
        self.assertEqual([image.content for image in request.images],
                         [self.assets.read_bytes(asset) for asset in expected])
        payload = json.loads(request.user_prompt)
        self.assertEqual(payload["workforce"]["id"], "industrial")
        self.assertEqual(payload["visual_references"]["scale"], {"picture": 4})
        self.assertNotIn("worker", payload["settings"])
        self.assertNotIn("previous_intention", payload)
        self.assertEqual(status(p, active(p)[0]), "review")
        p = self.service.review(p["id"], p["version"], [identity])
        p, ids, count = self.service.send(p["id"], p["version"], [identity])
        config = self.factory.snapshot()["items"][0]["config"]
        self.assertEqual(config["mode"], "ref2v")
        self.assertEqual(config["profile"]["id"], "minimax.h3.ref2v.classic.cinematic")
        self.assertEqual([r["asset_id"] for r in config["references"]], expected)
        self.assertEqual([r["role"] for r in config["references"]],
                         ["first_frame", "last_frame", "subject_reference", "composition_reference"])
        self.assertIn("Gros chantier industriel", config["intention"])
        self.assertIn("<Picture 3>", config["intention"])
        self.assertIn("<Picture 4>", config["intention"])
        self.assertEqual(config["worker_visual_policy"]["scale_asset_id"], setup["asset_id"])
        self.assertEqual(config["final_prompt"], "")  # LLM writes final wording later.
        self.assertEqual(count, 1)
        self.assertEqual(self.adapter.calls, [])

    def test_worker_only_uses_three_references_and_clear_restores_two_frame_mode(self):
        self.worker()
        p = self.latest()
        config = factory_entry(p, active(p)[0], 0)["config"]
        self.assertEqual(config["mode"], "ref2v")
        self.assertEqual(len(config["references"]), 3)
        p = self.scale()
        p = self.service.choose_worker(p["id"], p["version"], None)
        self.assertTrue(all("scale_setup_id" not in t for t in active(p)))
        config = factory_entry(p, active(p)[0], 0)["config"]
        self.assertEqual(config["mode"], "h3")
        self.assertEqual(len(config["references"]), 2)

    def test_crew_and_scale_changes_invalidate_review_without_modifying_delivery(self):
        self.worker()
        self.scale()
        p = self.prepare()
        identity = active(p)[0]["id"]
        p, ids, _ = self.service.send(p["id"], p["version"], [identity])
        original = deepcopy(self.factory.snapshot()["items"][0])
        p = self.service.update(p["id"], p["version"], {"settings": {"crew_size": "team"}})
        self.assertEqual(status(p, active(p)[0]), "review")
        with self.assertRaises(TransitionConflict):
            self.service.send(p["id"], p["version"], [identity])
        p = self.service.review(p["id"], p["version"], [identity])
        p = self.scale(0, "pair", .02)
        self.assertEqual(status(p, active(p)[0]), "review")
        self.assertEqual(self.factory.snapshot()["items"][0], original)

    def test_worker_or_basis_replacement_blocks_stale_composition_until_adjustment(self):
        self.worker()
        self.scale()
        p = self.prepare()
        identity = active(p)[0]["id"]
        p = self.worker(b"different worker")
        with self.assertRaisesRegex(ValueError, "ouvrier a changé"):
            self.service.review(p["id"], p["version"], [identity])
        p = self.scale()
        p = self.service.upload(p["id"], p["version"], b"new scene", "Nouveau décor", p["frames"][0]["id"])
        with self.assertRaisesRegex(ValueError, "décor de référence"):
            self.service.begin_proposals(p["id"], p["version"], [identity], "changed-basis")
        p = self.service.set_scale(p["id"], p["version"], identity, None)
        self.assertIsNone(reference_state(p, active(p)[0])["error"])

    def test_scale_change_during_proposal_does_not_apply_old_intention(self):
        self.worker()
        p = self.scale()
        self.gateway.hook = lambda: self.scale(0, "pair", .03)
        p = self.propose(active(p)[0]["id"])
        self.assertEqual(active(p)[0]["intention"], "")
        self.assertEqual(p["jobs"][-1]["status"], "failed")

    def test_legacy_read_preserves_context_and_creates_no_worker_catalog(self):
        p = self.latest()
        p["settings"].pop("crew_size")
        self.store.save(p)
        key = context_key(p, active(p)[0])
        p = self.make_service().get(p["id"])
        self.assertNotIn("crew_size", p["settings"])
        self.assertNotIn("worker_reference", p)
        self.assertEqual(context_key(p, active(p)[0]), key)
        self.assertFalse((self.store.root / "workers.json").exists())

    def test_http_import_scale_validation_and_revision_conflict_without_generation(self):
        app = FastAPI()
        app.include_router(image_transitions_router(self.service))
        p = self.latest()
        base = "/api/image-transitions/projects/" + p["id"]
        identity = active(p)[0]["id"]
        with TestClient(app) as client:
            spec = client.get("/api/image-transitions/spec").json()
            self.assertEqual([c["label"] for c in spec["crews"]],
                             ["Ouvrier solo", "Petite équipe", "Petit chantier", "Gros chantier industriel"])
            response = client.post(base + "/worker/upload", data={"version": p["version"]},
                                   files={"image": ("ouvrier.png", b"person", "image/png")})
            self.assertEqual(response.status_code, 201)
            p = response.json()["project"]
            before = len(self.assets.values)
            self.assertEqual(client.put(base + "/worker", json={"version": p["version"] - 1, "asset_id": None}).status_code, 409)
            invalid = client.put(base + "/transitions/" + identity + "/scale",
                json={"version": p["version"], "position": {"x": 0, "y": 0, "height": .2}})
            self.assertEqual(invalid.status_code, 422)
            self.assertEqual(len(self.assets.values), before)
            valid = client.put(base + "/transitions/" + identity + "/scale",
                json={"version": p["version"], "position": {"x": .4, "y": .8, "height": .05}, "scope": "pair"})
            self.assertEqual(valid.status_code, 200)
            self.assertEqual(len(client.get("/api/image-transitions/worker-library").json()["saved"]), 1)
        self.assertEqual(self.gateway.requests, [])
        self.assertEqual(self.adapter.calls, [])


class ScaleImageTest(unittest.TestCase):
    @staticmethod
    def png(image):
        stream = BytesIO()
        image.save(stream, format="PNG")
        return stream.getvalue()

    def test_alpha_crop_and_placement_preserve_originals_and_scene_dimensions(self):
        adapter = PillowTransitionReferences()
        original = Image.new("RGBA", (60, 100), (0, 0, 0, 0))
        original.paste((200, 20, 10, 255), (20, 10, 40, 90))
        worker_bytes = self.png(original)
        worker, dimensions = adapter.normalize_worker(worker_bytes)
        self.assertEqual(dimensions, (20, 80))
        scene = self.png(Image.new("RGBA", (200, 100), (0, 100, 20, 255)))
        result, dimensions = adapter.compose(scene, worker, dict(x=.5, y=.8, height=.4))
        self.assertEqual(dimensions, (200, 100))
        with Image.open(BytesIO(result)) as output:
            self.assertEqual(output.getpixel((100, 55)), (200, 20, 10, 255))
            self.assertEqual(output.getpixel((1, 1)), (0, 100, 20, 255))
        with Image.open(BytesIO(scene)) as untouched:
            self.assertEqual(untouched.getpixel((100, 55)), (0, 100, 20, 255))
        self.assertEqual(worker_bytes, self.png(original))

    def test_invalid_placements_and_empty_worker_are_rejected(self):
        invalid = [dict(x=.5, y=.8, height=float("nan")), dict(x=True, y=.8, height=.1),
                   dict(x=0, y=.8, height=.2), dict(x=.5, y=.01, height=.2),
                   dict(x=.5, y=.8, height=.001)]
        for position in invalid:
            with self.subTest(position=position), self.assertRaises(ValueError):
                placement(position, (1600, 900), (100, 400))
        with self.assertRaises(ValueError):
            PillowTransitionReferences().normalize_worker(self.png(Image.new("RGBA", (4, 4))))
