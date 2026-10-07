"""User-run regressions; temporary journals, fake LLM and no rendering."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.image_transitions import ImageTransitionService, TransitionConflict
from panelforge.application.image_transition_sources import ImageTransitionSources
from panelforge.application.prompt_lab import StreamEventKind, CompletionResult, ModelDescriptor
from panelforge.application.video_factory import VideoFactoryService
from panelforge.domain.image_transitions import active, context_key, status, effective, factory_entry, temporal_contract
from panelforge.features.lab.image_transitions_web import image_transitions_router
from panelforge.infrastructure.storage.image_transitions import LocalImageTransitionStore
from test_video_factory import MemoryStore, FakeWorkflows


class Assets:
    def __init__(self):
        self.values = {}
    def create(self, content, media_type):
        identity = "asset-" + str(len(self.values) + 1)
        self.values[identity] = NS(asset_id=identity, content=content, media_type=media_type)
        return self.values[identity]
    def get(self, identity):
        return self.values[identity]
    def read_bytes(self, identity):
        return self.get(identity).content


class Images:
    def normalize_source(self, content):
        return content
    def dimensions(self, content):
        return (1600, 900)
    def prepare(self, content, dimensions):
        return content


class Gateway:
    def __init__(self):
        self.requests = []
        self.hook = None
        self.raw = json.dumps(dict(action="Nettoyer le sol", kind="cleaning",
            intention="L’ouvrier entre, balaie les déchets puis sort avec son balai.",
            observations="Le sol devient propre.", uncertainties="L’outil est une proposition."))
        self.truncated = False
    def list_models(self):
        return [ModelDescriptor("fake", "local", "Fake vision")]
    def stream(self, request):
        self.requests.append(request)
        if self.hook:
            self.hook()
        yield NS(kind=StreamEventKind.TRUNCATED if self.truncated else StreamEventKind.COMPLETED,
                 result=CompletionResult(model_id=request.model_id, content=self.raw, call_id="fake-call"), text="")


class TransitionFixture(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LocalImageTransitionStore(self.temp.name)
        self.assets, self.images, self.gateway = Assets(), Images(), Gateway()
        self.adapter = FakeWorkflows()
        self.factory = VideoFactoryService(store=MemoryStore(), adapter=self.adapter)
        self.service = self.make_service()
        self.project = self.service.create("L’arbre")
        for index in range(4):
            self.project = self.service.upload(self.project["id"], self.project["version"],
                                               f"image-{index}".encode(), f"État {index}")
        self.identity = self.project["id"]

    def make_service(self):
        return ImageTransitionService(store=self.store, assets=self.assets, images=self.images,
            gateway=self.gateway, factory=self.factory, sources=ImageTransitionSources())

    def latest(self):
        return self.service.get(self.project["id"])

    def edit(self, transition_id, **changes):
        p = self.latest()
        return self.service.edit(p["id"], p["version"], transition_id, changes)

    def prepare(self):
        for transition in active(self.latest()):
            self.edit(transition["id"], action="Travaux", intention="L’ouvrier réalise la transformation puis sort.")
        p = self.latest()
        return self.service.review(p["id"], p["version"], [t["id"] for t in active(p)])

    def propose(self, transition_id, request_id="proposal"):
        p = self.latest()
        project, job_id = self.service.begin_proposals(p["id"], p["version"], [transition_id], request_id)
        self.service.execute_proposals(p["id"], job_id)
        return self.latest()


class TransitionServiceTest(TransitionFixture):
    def test_middle_image_change_only_invalidates_adjacent_reviews(self):
        p = self.prepare()
        original = deepcopy(active(p))
        replacement = self.assets.create(b"new middle", "image/png")
        p = self.service.add_frames(p["id"], p["version"],
            [dict(asset_id=replacement.asset_id, label="Nouvel état")], p["frames"][1]["id"])
        self.assertEqual([status(p,t) for t in active(p)], ["review","review","ready"])
        self.assertEqual([t["id"] for t in active(p)], [t["id"] for t in original])
        self.assertEqual([t["intention"] for t in active(p)], [t["intention"] for t in original])

    def test_reorder_retains_unaffected_pairs_and_restore_recovers_review(self):
        p = self.prepare()
        ids = [f["id"] for f in p["frames"]]
        kept = active(p)[-1]["id"]
        p = self.service.order(p["id"], p["version"], [ids[1], ids[0], ids[2], ids[3]])
        self.assertEqual(len(active(p)), 3)
        self.assertEqual(active(p)[-1]["id"], kept)
        self.assertEqual(status(p,active(p)[-1]), "ready")
        p = self.service.order(p["id"], p["version"], ids)
        self.assertEqual([status(p,t) for t in active(p)], ["ready"]*3)

    def test_empty_intention_send_is_rejected_before_creating_factory_units(self):
        p = self.latest()
        self.assertIn("intention", self.service.public(p)["transitions"][0]["send_error"])
        with self.assertRaisesRegex(ValueError, "intention"):
            self.service.send(p["id"], p["version"], [active(p)[0]["id"]])
        self.assertEqual(self.factory.snapshot()["items"], [])

    def test_proposal_can_be_sent_without_marking_it_human_reviewed(self):
        identity = active(self.latest())[0]["id"]
        p = self.propose(identity)
        self.assertIsNone(active(p)[0]["reviewed"])
        self.assertIsNone(self.service.public(p)["transitions"][0]["send_error"])
        p, ids, added = self.service.send(p["id"], p["version"], [identity])
        self.assertEqual(added, 1)
        self.assertEqual(status(p, active(p)[0]), "sent")
        self.assertIsNone(active(p)[0]["reviewed"])
        self.assertIn(active(p)[0]["intention"], self.factory.snapshot()["items"][0]["config"]["intention"])
        self.assertEqual(self.adapter.calls, [])

    def test_one_empty_transition_blocks_entire_selection_without_partial_receipt(self):
        first, second = active(self.latest())[:2]
        p = self.edit(first["id"], intention="Assembler les pièces puis sortir.")
        with self.assertRaisesRegex(ValueError, "intention"):
            self.service.send(p["id"], p["version"], [first["id"], second["id"]])
        self.assertEqual(self.latest()["deliveries"], [])
        self.assertEqual(self.factory.snapshot()["items"], [])

    def test_running_proposal_blocks_send_even_with_existing_intention(self):
        p = self.prepare()
        identity = active(p)[0]["id"]
        p, _ = self.service.begin_proposals(p["id"], p["version"], [identity], "pending-send")
        with self.assertRaisesRegex(TransitionConflict, "fin de l’analyse"):
            self.service.send(p["id"], p["version"], [identity])
        self.assertEqual(self.latest()["deliveries"], [])
        self.assertEqual(self.factory.snapshot()["items"], [])

    def test_mixed_selection_only_receives_new_versions_and_all_sent_is_noop(self):
        first, second = active(self.latest())[:2]
        self.edit(first["id"], intention="Poser les poutres.")
        p = self.edit(second["id"], intention="Poser le plancher.")
        p, first_ids, _ = self.service.send(p["id"], p["version"], [first["id"]])
        with patch.object(self.factory, "receive", wraps=self.factory.receive) as receive:
            p, mixed_ids, added = self.service.send(p["id"], p["version"], [second["id"], first["id"]])
            self.assertEqual(added, 1)
            self.assertEqual(mixed_ids[0], first_ids[0])
            entries = receive.call_args.args[0]
            self.assertEqual([e["source"]["transition_id"] for e in entries], [second["id"]])
        saved = deepcopy(p)
        with patch.object(self.factory, "receive", wraps=self.factory.receive) as receive:
            p, repeated, added = self.service.send(p["id"], p["version"], [first["id"], second["id"]])
            receive.assert_not_called()
        self.assertEqual(p, saved)
        self.assertEqual(repeated, mixed_ids)
        self.assertEqual(added, 0)
        p = self.edit(first["id"], intention="Poser les poutres avec un petit treuil.")
        with patch.object(self.factory, "receive", wraps=self.factory.receive) as receive:
            p, revised_ids, added = self.service.send(p["id"], p["version"], [first["id"], second["id"]])
            self.assertEqual(len(receive.call_args.args[0]), 1)
        self.assertEqual(added, 1)
        self.assertNotEqual(revised_ids[0], mixed_ids[0])
        self.assertEqual(revised_ids[1], mixed_ids[1])
        self.assertEqual(len(self.factory.snapshot()["items"]), 3)

    def test_send_is_ordered_deduplicated_and_preserves_exact_boundaries(self):
        p = self.prepare()
        ids = [t["id"] for t in active(p)]
        p, factory_ids, count = self.service.send(p["id"], p["version"], list(reversed(ids)))
        self.assertEqual(count, 3)
        items = self.factory.snapshot()["items"]
        self.assertEqual([i["source"]["transition_id"] for i in items], ids)
        for index, item in enumerate(items):
            self.assertEqual(item["status"], "preparation")
            self.assertEqual([r["asset_id"] for r in item["config"]["references"]],
                             [p["frames"][index]["asset_id"],p["frames"][index+1]["asset_id"]])
            self.assertEqual([r["role"] for r in item["config"]["references"]], ["first_frame","last_frame"])
            self.assertEqual(item["config"]["render"]["settings"]["aspect_ratio"], "16:9 (Widescreen)")
            self.assertEqual(item["config"]["render"]["settings"]["duration_seconds"], 7)
        p, repeated, count = self.service.send(p["id"],p["version"],ids)
        self.assertEqual(repeated, factory_ids)
        self.assertEqual(count, 0)
        self.assertEqual(self.adapter.calls, [])  # Receipt does not launch production.

    def test_edited_intention_creates_new_version_without_retargeting_old_unit(self):
        p = self.prepare()
        identity = active(p)[0]["id"]
        p, ids, _ = self.service.send(p["id"],p["version"],[identity])
        original = deepcopy(self.factory.snapshot()["items"][0])
        p = self.edit(identity, intention="Poser une porte et sortir.")
        self.assertEqual(self.factory.snapshot()["items"][0], original)
        p, new_ids, added = self.service.send(p["id"],p["version"],[identity])
        self.assertEqual(added, 1)
        self.assertNotEqual(ids, new_ids)
        self.assertEqual(len(self.service.public(p)["transitions"][0]["factory_ids"]),2)

    def test_crash_after_receipt_retries_saved_entry_once(self):
        p = self.prepare()
        ids = [active(p)[0]["id"]]
        original_save = self.store.save
        def fail_on_receipt(project):
            if any(d.get("factory_id") for d in project["deliveries"]):
                raise OSError("simulated interruption after factory receipt")
            return original_save(project)
        with patch.object(self.store,"save",side_effect=fail_on_receipt):
            with self.assertRaises(OSError):
                self.service.send(p["id"],p["version"],ids)
        self.assertEqual(len(self.factory.snapshot()["items"]),1)
        p = self.latest()
        p, received, added = self.service.send(p["id"],p["version"],ids)
        self.assertEqual(added,0)
        self.assertEqual(len(received),1)
        self.assertEqual(len(self.factory.snapshot()["items"]),1)

    def test_llm_uses_two_images_and_never_marks_proposal_reviewed(self):
        p = self.latest()
        worker = "Un adulte au pied du tronc, haut comme un cinquième de sa largeur à la base."
        p = self.service.update(p["id"], p["version"], dict(settings=dict(worker=worker)))
        identity = active(p)[0]["id"]
        p = self.propose(identity)
        self.assertEqual(status(p,active(p)[0]),"review")
        request = self.gateway.requests[0]
        self.assertEqual(len(request.images),2)
        self.assertEqual([i.content for i in request.images],[b"image-0",b"image-1"])
        self.assertEqual(json.loads(request.user_prompt)["settings"]["worker"], worker)
        self.assertEqual(active(p)[0]["intention"], json.loads(self.gateway.raw)["intention"])
        self.assertIn(worker, factory_entry(p, active(p)[0], 0)["config"]["intention"])
        self.assertEqual(self.factory.snapshot()["items"],[])

    def test_manual_intention_is_preserved_with_separate_applicable_suggestion(self):
        identity = active(self.latest())[0]["id"]
        self.edit(identity,action="Un travail précis",intention="Mon intention relue.")
        p = self.propose(identity)
        transition = active(p)[0]
        self.assertEqual(transition["intention"],"Mon intention relue.")
        self.assertIsNotNone(transition["suggestion"])
        p = self.service.apply_suggestion(p["id"],p["version"],identity)
        self.assertIn("balaie",active(p)[0]["intention"])
        self.assertEqual(status(p,active(p)[0]),"review")

    def test_changed_input_during_llm_is_not_overwritten(self):
        identity = active(self.latest())[0]["id"]
        self.gateway.hook = lambda: self.edit(identity,note="Nouvelle consigne pendant l’analyse")
        p = self.propose(identity)
        self.assertEqual(active(p)[0]["intention"],"")
        self.assertEqual(p["jobs"][-1]["status"],"failed")
        self.assertIn("modifiées",p["jobs"][-1]["error"])

    def test_truncated_response_retains_previous_intention(self):
        identity = active(self.latest())[0]["id"]
        self.edit(identity,intention="Texte à conserver")
        self.gateway.truncated=True
        p = self.propose(identity)
        self.assertEqual(active(p)[0]["intention"],"Texte à conserver")
        self.assertEqual(p["jobs"][-1]["status"],"failed")
        self.assertIsNone(active(p)[0]["suggestion"])

    def test_retrying_same_proposal_request_does_not_repeat_llm(self):
        p = self.latest()
        ids=[active(p)[0]["id"]]
        _, job_id=self.service.begin_proposals(p["id"],p["version"],ids,"same-click")
        self.service.execute_proposals(p["id"],job_id)
        _, repeated=self.service.begin_proposals(p["id"],p["version"],ids,"same-click")
        self.service.execute_proposals(p["id"],repeated)
        self.assertEqual(job_id,repeated)
        self.assertEqual(len(self.gateway.requests),1)

    def test_restart_marks_interrupted_job_without_calling_llm(self):
        p = self.latest()
        self.service.begin_proposals(p["id"],p["version"],[active(p)[0]["id"]],"pending")
        restarted=self.make_service()
        self.assertEqual(restarted.get(p["id"])["jobs"][-1]["status"],"failed")
        self.assertEqual(self.gateway.requests,[])

    def test_stale_version_and_foreign_order_are_rejected(self):
        p=self.latest()
        self.service.update(p["id"],p["version"],dict(name="Autre nom"))
        with self.assertRaises(TransitionConflict):
            self.service.order(p["id"],p["version"],[])
        p=self.latest()
        with self.assertRaises(ValueError):
            self.service.order(p["id"],p["version"],["foreign-frame"])
        with self.assertRaises(ValueError):
            self.store.get("../escape")

    def test_http_direct_send_after_background_proposals(self):
        app=FastAPI()
        app.include_router(image_transitions_router(self.service))
        p=self.latest()
        base="/api/image-transitions/projects/"+p["id"]
        identity=active(p)[0]["id"]
        with TestClient(app) as client:
            self.assertTrue(client.get("/api/image-transitions/spec").json()["direct_send"])
            self.assertEqual(client.post(base+"/send",json=dict(version=p["version"],ids=[identity])).status_code,422)
            response=client.post(base+"/proposals",json=dict(version=p["version"],ids=[identity],request_id="http"))
            self.assertEqual(response.status_code,202)
            p=client.get(base).json()["project"]
            self.assertEqual(p["jobs"][-1]["status"],"succeeded")
            self.assertIsNone(p["transitions"][0]["reviewed"])
            self.assertIsNone(p["transitions"][0]["send_error"])
            response=client.post(base+"/send",json=dict(version=p["version"],ids=[identity]))
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()["added"],1)
        self.assertEqual(self.adapter.calls,[])


class TransitionLocalChangeTest(TransitionFixture):
    def test_image_history_and_old_auto_prose_do_not_steer_reproposal(self):
        p = self.latest()
        t = active(p)[0]
        t.update(action="Construire la tour Eiffel", intention="Terminer la tour Eiffel.", manual=False,
                 note="Assembler uniquement le socle visible.")
        for frame in p["frames"]:
            frame["label"] = "Tour Eiffel complete.png"
            frame["origin"] = dict(action="Retirer les niveaux superieurs et la fleche dans LATER.",
                                   observation="La tour Eiffel complete a ete reduite.")
        p["settings"]["worker"] = "Des ouvriers minuscules manipulent les allumettes comme des poutres."
        frames = deepcopy(p["frames"])
        worker = p["settings"]["worker"]
        self.store.save(p)

        result = self.propose(t["id"])
        request = self.gateway.requests[-1]
        payload = json.loads(request.user_prompt)
        for fragment in ("Eiffel", "LATER", "origin"):
            self.assertNotIn(fragment, request.user_prompt)
        self.assertEqual(payload["sequence"], [dict(index=i + 1) for i in range(len(frames))])
        self.assertEqual(payload["current_action"], "")
        self.assertNotIn("previous_intention", payload)
        self.assertEqual(payload["user_note"], t["note"])
        self.assertEqual(payload["settings"]["worker"], worker)
        self.assertEqual([payload["start"], payload["end"]], [dict(picture=1), dict(picture=2)])
        self.assertEqual([image.content for image in request.images],
                         [self.assets.read_bytes(frame["asset_id"]) for frame in frames[:2]])
        self.assertEqual(result["frames"], frames)  # Keep provenance for browsing, outside the LLM input.
        self.assertEqual(result["settings"]["worker"], worker)
        self.assertEqual(result["jobs"][-1]["status"], "succeeded")
        self.assertEqual(self.adapter.calls, [])

    def test_manual_directions_and_textual_worker_constraints_are_preserved(self):
        p = self.latest()
        identity = active(p)[0]["id"]
        action = "Assembler le socle et conserver son inscription."
        intention = "Assembler les supports autour de l'inscription sans la masquer."
        note = "Le texte lisible doit rester : Tour Eiffel."
        worker = "Deux ouvriers, chacun de la hauteur d'une allumette, utilisent un palan."
        p = self.service.update(p["id"], p["version"], dict(settings=dict(worker=worker)))
        self.edit(identity, action=action, intention=intention, note=note)

        result = self.propose(identity)
        payload = json.loads(self.gateway.requests[-1].user_prompt)
        self.assertEqual(payload["current_action"], action)
        self.assertEqual(payload["previous_intention"], intention)
        self.assertEqual(payload["user_note"], note)
        self.assertEqual(payload["settings"]["worker"], worker)
        current = active(result)[0]
        self.assertEqual((current["action"], current["intention"]), (action, intention))
        self.assertIsNotNone(current["suggestion"])
        self.assertEqual(self.adapter.calls, [])


class TransitionPaceTest(TransitionFixture):
    def set_preset(self, preset):
        p = self.latest()
        return self.service.update(p["id"], p["version"], dict(settings=dict(pace_preset=preset)))

    def test_new_frieze_fast_contract_reaches_proposal_and_factory(self):
        p = self.latest()
        self.assertEqual(p["settings"]["pace_preset"], "fast")
        identity = active(p)[0]["id"]
        p = self.propose(identity)
        request = self.gateway.requests[-1]
        intent = json.loads(request.user_prompt)
        self.assertEqual(request.operation_id, "image.transitions.propose@3.1.0")
        self.assertEqual(intent["temporal_contract"]["preset"], "fast")
        self.assertIn("aggressively fast-forwarded time-lapse", intent["temporal_contract"]["h3_guidance"])
        p = self.service.review(p["id"], p["version"], [identity])
        p, ids, _ = self.service.send(p["id"], p["version"], [identity])
        config = self.factory.snapshot()["items"][0]["config"]
        self.assertIn("aggressively fast-forwarded time-lapse", config["intention"])
        self.assertIn("staccato, frame-jumping beats", config["intention"])
        self.assertLess(config["intention"].index("Traitement temporel"), config["intention"].index("Action :"))
        self.assertEqual([ref["asset_id"] for ref in config["references"]],
                         [p["frames"][0]["asset_id"], p["frames"][1]["asset_id"]])
        self.assertEqual(config["render"]["settings"]["duration_seconds"], 7)
        self.assertEqual(self.adapter.calls, [])

    def test_slow_replaces_fast_for_both_stages_without_changing_duration(self):
        p = self.set_preset("slow")
        p = self.service.update(p["id"], p["version"], dict(settings=dict(duration=9.5)))
        p = self.propose(active(p)[0]["id"])
        contract = json.loads(self.gateway.requests[-1].user_prompt)["temporal_contract"]
        self.assertEqual(contract["preset"], "slow")
        config = factory_entry(p, active(p)[0], 0)["config"]
        self.assertIn("moderately accelerated", config["intention"])
        self.assertNotIn("frame-jumping", config["intention"])
        self.assertEqual(config["render"]["settings"]["duration_seconds"], 9.5)
        self.assertIn("dernière image à 9.5 s", config["intention"])

    def test_switch_can_send_new_version_directly_and_preserves_previous_unit(self):
        p = self.prepare()
        identity = active(p)[0]["id"]
        p, ids, _ = self.service.send(p["id"], p["version"], [identity])
        original = deepcopy(self.factory.snapshot()["items"][0])
        p = self.set_preset("slow")
        self.assertEqual(status(p, active(p)[0]), "review")
        p, new_ids, added = self.service.send(p["id"], p["version"], [identity])
        self.assertEqual(added, 1)
        self.assertNotEqual(new_ids, ids)
        self.assertEqual(self.factory.snapshot()["items"][0], original)

    def test_pair_override_supersedes_common_preset_and_retains_review(self):
        identity = active(self.latest())[0]["id"]
        self.edit(identity, pace="Travelling lent vers l’intérieur, sans ouvrier.", kind="camera")
        p = self.prepare()
        transition = active(p)[0]
        original_key = context_key(p, transition)
        p = self.set_preset("slow")
        transition = active(p)[0]
        self.assertEqual(context_key(p, transition), original_key)
        self.assertEqual(status(p, transition), "ready")
        self.assertIsNone(temporal_contract(effective(p, transition)))
        config = factory_entry(p, transition, 0)["config"]
        self.assertIn("Travelling lent", config["intention"])
        self.assertNotIn("Traitement temporel prioritaire", config["intention"])
        p = self.propose(identity)
        self.assertIsNone(json.loads(self.gateway.requests[-1].user_prompt)["temporal_contract"])

    def test_free_text_switches_to_custom_without_hidden_fast_instruction(self):
        p = self.latest()
        p = self.service.update(p["id"], p["version"],
                                dict(settings=dict(pace="Une seule action fluide à vitesse normale.")))
        self.assertEqual(p["settings"]["pace_preset"], "custom")
        p = self.propose(active(p)[0]["id"])
        self.assertIsNone(json.loads(self.gateway.requests[-1].user_prompt)["temporal_contract"])
        self.assertNotIn("fast-forwarded", factory_entry(p, active(p)[0], 0)["config"]["intention"])

    def test_legacy_settings_are_not_migrated_or_invalidated_on_read(self):
        p = self.latest()
        p["settings"].pop("pace_preset")
        p["settings"]["pace"] = "Captation fortement accélérée de toute l’action, gestes rapides et saccadés."
        self.store.save(p)
        p = self.prepare()
        before = deepcopy(p["settings"])
        keys = [context_key(p, t) for t in active(p)]
        restarted = self.make_service()
        public = restarted.public(restarted.get(p["id"]))
        self.assertEqual(public["settings"], before)
        self.assertEqual([t["context_key"] for t in public["transitions"]], keys)
        self.assertEqual([t["state"] for t in public["transitions"]], ["ready"] * 3)
        p = self.service.update(p["id"], p["version"], dict(settings=dict(model_id="another-proposer")))
        self.assertNotIn("pace_preset", p["settings"])
        self.assertEqual([status(p,t) for t in active(p)], ["ready"] * 3)
        self.assertNotIn("Traitement temporel prioritaire", factory_entry(p, active(p)[0], 0)["config"]["intention"])

    def test_preset_change_during_proposal_rejects_old_result(self):
        identity = active(self.latest())[0]["id"]
        self.gateway.hook = lambda: self.set_preset("slow")
        p = self.propose(identity)
        self.assertEqual(p["settings"]["pace_preset"], "slow")
        self.assertEqual(active(p)[0]["intention"], "")
        self.assertEqual(p["jobs"][-1]["status"], "failed")

    def test_http_catalog_and_preset_validation_are_consistent(self):
        app = FastAPI()
        app.include_router(image_transitions_router(self.service))
        p = self.latest()
        base = "/api/image-transitions/projects/" + p["id"]
        with TestClient(app) as client:
            spec = client.get("/api/image-transitions/spec").json()
            presets = {value["id"]: value for value in spec["pace_presets"]}
            self.assertEqual(set(presets), {"slow", "fast"})
            self.assertEqual(spec["defaults"]["pace_preset"], "fast")
            response = client.patch(base, json=dict(version=p["version"],
                changes=dict(settings=dict(pace_preset="slow", pace=presets["slow"]["pace"]))))
            self.assertEqual(response.status_code, 200)
            p = response.json()["project"]
            for changes in (dict(pace_preset="turbo"), dict(pace_preset=[]),
                            dict(pace_preset="fast", pace="Travail au ralenti")):
                with self.subTest(changes=changes):
                    response = client.patch(base, json=dict(version=p["version"], changes=dict(settings=changes)))
                    self.assertEqual(response.status_code, 422)
                    self.assertEqual(client.get(base).json()["project"]["version"], p["version"])


class TransitionSourcesTest(unittest.TestCase):
    def test_exact_qwen_version_and_validated_chain_are_distinct(self):
        project=dict(stages=[dict(id="stage1",label="Porte",source_asset_id="asset-start",
            accepted_attempt_id="a2",attempts=[
                dict(id="a1",status="succeeded",output_asset_id="asset-first",prompt="First"),
                dict(id="a2",status="succeeded",output_asset_id="asset-chosen",prompt="Second"),
                dict(id="a3",status="running",output_asset_id=None)])])
        sources=ImageTransitionSources(qwen=NS(get=lambda _:deepcopy(project)))
        choices=sources.choices("qwen","project")
        self.assertEqual([c["asset_id"] for c in choices if c["accepted"]],["asset-start","asset-chosen"])
        selected=sources.select("qwen","project",["stage1:a1"])
        self.assertEqual(selected[0]["asset_id"],"asset-first")
        self.assertEqual(selected[0]["origin"]["attempt_id"],"a1")
        with self.assertRaises(ValueError):
            sources.select("qwen","project",["stage1:a3"])

    def test_krea_chain_uses_stage_order_and_accepted_results(self):
        first=NS(project_id="p",source_id="s1",stage_index=1,source_asset_id="asset-start",
                 accepted_attempt_id="a1",instruction="Créer une porte",
                 attempts=[NS(attempt_id="a1",status="succeeded",output_asset_id="asset-door",prompt="Door")])
        second=NS(project_id="p",source_id="s2",stage_index=2,source_asset_id="asset-door",
                  accepted_attempt_id="a2",instruction="Nettoyer",
                  attempts=[NS(attempt_id="a2",status="succeeded",output_asset_id="asset-clean",prompt="Clean")])
        sources=ImageTransitionSources(krea=NS(sources=NS(list=lambda *a,**k:[second,first])))
        choices=sources.choices("krea","p")
        self.assertEqual([c["asset_id"] for c in choices],["asset-start","asset-door","asset-clean"])
        self.assertTrue(all(c["accepted"] for c in choices))
