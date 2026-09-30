"""User-run regressions for the reported conflicting worker description; no real engines."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from types import SimpleNamespace as NS
import unittest

from test_image_transitions_references import ReferenceFixture
from test_classic_cinematic import fixture
from panelforge.application import classic_cinematic as classic
from panelforge.application import worker_visual_policy as visual
from panelforge.application.video_preparation import preparation_source
from panelforge.application.direct_ref2v_prompt import direct_reference_header, direct_reference_header_for_roles
from panelforge.domain.image_transitions import active, factory_entry, context_key, needs_visual_refresh
from panelforge.domain.prompt_composition import PreparationIntent
from panelforge.domain.worker_visual_policy import WorkerVisualPolicy, VERSION
from panelforge.infrastructure.storage.prompt_compositions import intent_to_dict, intent_from_dict

LEGACY = ("Un ouvrier en jean bleu, tee-shirt blanc et casquette bleue. "
          "Sa hauteur debout représente un dixième de la largeur du tronc à sa base.")
BINDING = dict(version=VERSION, identity_picture=3, scale_picture=4, depict_worker=True)
LINK = "The worker from <Picture 3>, at the scale and ground placement shown in <Picture 4>, carries the boards."


class VisualTransitionRegression(ReferenceFixture):
    def test_old_worker_text_history_and_numeric_placement_are_not_sent(self):
        self.worker()
        p = self.scale()
        p = self.service.update(p["id"], p["version"], {"settings": {"worker": LEGACY}})
        transition = active(p)[0]
        # Reproduce persisted old data, without marking it as a new manual rewrite.
        transition.update(intention=LEGACY, action="Installer les marches", manual=True)
        p["frames"][0]["origin"] = {"instruction": LEGACY}
        p["frames"][0]["label"] = LEGACY
        self.store.save(p)
        old = deepcopy(transition)
        p = self.propose(transition["id"])
        request = self.gateway.requests[-1]
        for fragment in ("jean bleu", "dixième", "height"):
            self.assertNotIn(fragment, request.user_prompt)
        payload = json.loads(request.user_prompt)
        self.assertNotIn("previous_intention", payload)
        self.assertNotIn("worker", payload["settings"])
        self.assertEqual(payload["visual_references"]["scale"], {"picture": 4})
        current = active(p)[0]
        self.assertEqual(current["intention"], old["intention"])
        self.assertTrue(needs_visual_refresh(p, current))
        with self.assertRaisesRegex(ValueError, "Reproposez"):
            self.service.review(p["id"], p["version"], [current["id"]])
        p = self.service.apply_suggestion(p["id"], p["version"], current["id"])
        p = self.service.review(p["id"], p["version"], [current["id"]])
        config = factory_entry(p, active(p)[0], 0)["config"]
        self.assertNotIn("jean bleu", config["intention"])
        self.assertNotIn("dixième", config["intention"])
        self.assertNotIn("proportions humaines", config["intention"])
        self.assertIn("<Picture 4>", config["intention"])
        self.assertEqual(config["worker_visual_policy"]["identity_asset_id"], p["worker_reference"]["asset_id"])

    def test_inactive_worker_text_does_not_invalidate_visual_review(self):
        self.worker()
        self.scale()
        p = self.prepare()
        before = context_key(p, active(p)[0])
        p = self.service.update(p["id"], p["version"], {"settings": {"worker": LEGACY}})
        self.assertEqual(before, context_key(p, active(p)[0]))

    def test_legacy_suggestion_cannot_restore_old_worker_prose(self):
        self.worker()
        p = self.scale()
        t = active(p)[0]
        t["suggestion"] = dict(context=context_key(p, t), value=dict(intention=LEGACY))
        self.store.save(p)
        with self.assertRaisesRegex(ValueError, "Reproposez"):
            self.service.apply_suggestion(p["id"], p["version"], t["id"])
        self.assertEqual(active(self.latest())[0]["intention"], t["intention"])

    def test_without_worker_reference_text_description_is_still_available(self):
        p = self.latest()
        p = self.service.update(p["id"], p["version"], {"settings": {"worker": LEGACY}})
        p = self.propose(active(p)[0]["id"])
        self.assertEqual(json.loads(self.gateway.requests[-1].user_prompt)["settings"]["worker"], LEGACY)
        self.assertIn(LEGACY, factory_entry(p, active(p)[0], 0)["config"]["intention"])


class VisualPreparationRegression(unittest.TestCase):
    def test_policy_roundtrip_and_absent_policy_preserves_legacy_source_digest(self):
        old = PreparationIntent("A continuous shot.")
        saved = intent_to_dict(old)
        self.assertNotIn("worker_visual_policy", saved)
        self.assertEqual(intent_from_dict(saved), old)
        snapshot = asdict(old)
        for key in ("speech_policy", "speech_language", "worker_visual_policy"):
            snapshot.pop(key)
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(preparation_source(None, NS(preparation_intent=old)).source_id, "intent:" + digest)
        new = PreparationIntent("Use the supplied worker.", worker_visual_policy=WorkerVisualPolicy("asset-worker", "asset-scale"))
        self.assertEqual(intent_from_dict(intent_to_dict(new)), new)
        self.assertNotEqual(preparation_source(None, NS(preparation_intent=new)).source_id, "intent:" + digest)

    def test_bindings_follow_asset_roles_and_actual_picture_order(self):
        refs = {
            "worker": NS(asset_id="asset-worker", role="subject_reference", reference_id="worker"),
            "scale": NS(asset_id="asset-scale", role="composition_reference", reference_id="scale"),
        }
        session = NS(reference=lambda key: refs[key])
        mapping = (("worker", 5), ("scale", 3))
        bound = visual.resolve(WorkerVisualPolicy("asset-worker", "asset-scale"), session, mapping)
        self.assertEqual((bound["identity_picture"], bound["scale_picture"]), (5, 3))
        header = direct_reference_header(session, mapping, rule_overrides=visual.rules(bound))
        self.assertIn("Use <Picture 5> as the sole visual definition", header)
        self.assertIn("Use <Picture 3> as the sole visual definition", header)
        self.assertNotIn("spatial balance", header)
        with self.assertRaises(ValueError):
            visual.resolve(WorkerVisualPolicy("asset-worker", "asset-missing"), session, mapping)

    def test_schema_hints_are_scoped_and_preserve_plan_phase_objects(self):
        original = classic.schema("beat_sheet")
        self.assertEqual(visual.scoped_schema(original, None), original)
        current = json.loads(visual.scoped_schema(original, BINDING))
        self.assertNotIn("retain the numeric ratio", json.dumps(current))
        phases = current["$defs"]["PlannedShot"]["properties"]["phases"]
        self.assertIn("$ref", phases["items"])
        self.assertNotIn("action paragraph", phases["description"])
        plan, _, _ = fixture(count=1)
        writer = visual.scoped_schema(classic.schema("final_prompt", plan=plan), BINDING)
        self.assertNotIn("retain its ratio", writer)

    def test_missing_scale_link_in_writer_is_rejected_even_when_header_has_it(self):
        plan, writer, context = fixture(count=1)
        context["worker_visual_binding"] = BINDING
        roles = ("first_frame", "last_frame", "subject_reference", "composition_reference")
        header = direct_reference_header_for_roles(roles).splitlines()
        for number, rule in visual.rules(BINDING).items():
            header[number - 1] = rule
        context["header"] = "\n".join(header)
        plan["shots"][0]["phases"][0]["actions"].insert(0, LINK)
        plan["continuity_invariants"].append(LINK)
        plan["shots"][0]["opening_composition"] += " The worker is associated with <Picture 3> and <Picture 4>."
        context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan), context))
        # The old failure: Picture 4 in the invariant/header, absent from the writer's actions.
        writer["shots"][0]["phases"][0] = "The worker from <Picture 3> carries the boards."
        with self.assertRaisesRegex(ValueError, "Picture 4"):
            classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
        writer["shots"][0]["phases"][0] = LINK
        prompt, saved = classic.compile_result(json.dumps(writer), classic.encode_context(context), "final_prompt")
        self.assertEqual(prompt.count(LINK), 1)
        self.assertNotIn("one tenth", prompt)
        self.assertEqual(classic.decode_context(saved)["worker_visual_binding"], BINDING)
        contaminated = deepcopy(plan)
        contaminated["continuity_invariants"].append("His height is one tenth of the trunk width.")
        with self.assertRaisesRegex(ValueError, "ancienne taille"):
            classic.canonical_plan(json.dumps(contaminated), context)

    def test_known_old_ratio_is_rejected_only_in_visual_worker_contract(self):
        for text in (LEGACY, "height 1/10 of the trunk width", "one-tenth of the trunk width"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                visual.validate(text, BINDING)
            visual.validate(text, None)
        visual.validate("A 7-second shot with 4 workers carrying 10 boards.", BINDING)
        visual.validate("The empty scene is revealed.", {**BINDING, "depict_worker": False}, require_links=True)
