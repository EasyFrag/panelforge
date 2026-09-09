"""Conversational edit contracts using local stores and a fake text gateway only."""

import json
import tempfile
import unittest

from panelforge.application import Krea2EditService, Krea2EditAttemptRequest
from panelforge.application import krea2_edit_assistance
from panelforge.domain import Krea2EditMetadata, Krea2EditSettings, Krea2AspectRatio
from panelforge.infrastructure.presets import load_krea2_edit_workflow
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2EditStore
from panelforge.features.lab.web import serialize_krea2_edit_source
from tests.test_krea2_edit import FakeGateway, PNG, WORKFLOW


PROMPT = "A fixed wide photograph of a stone wall with a rectangular rough opening, intact surrounding stones and natural daylight."


class EditWorkshopTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.assets = LocalAssetStore(self.temp.name)
        self.asset = self.assets.create(PNG, media_type="image/png")
        self.store = LocalKrea2EditStore(self.temp.name)
        self.gateway = FakeGateway(json.dumps({"message": "Je propose une ouverture localisee.", "prompt": PROMPT}))
        self.service = Krea2EditService(gateway=self.gateway, workflow=load_krea2_edit_workflow(WORKFLOW),
                                        comfy=None, assets=self.assets, sources=self.store)
        self.source = self.service.add_source(asset_id=self.asset.asset_id, filename="wall.png", metadata=Krea2EditMetadata())

    def tearDown(self):
        self.temp.cleanup()

    def chat(self, instruction):
        return list(self.service.stream_prepare_prompt(self.source.source_id, instruction, "fake", assistance_version="2.0.0"))[-1].source

    def test_visible_reply_and_recent_instructions_are_persisted_without_old_prompt_copies(self):
        first = self.chat("FIRST_CORRECTION")
        self.assertEqual(first.prompt_status.value, "ready")
        self.assertEqual(first.generated_prompt, PROMPT)
        self.assertTrue(first.revisions[0].assistant_message)
        self.assertEqual(first.revisions[0].assistance_version, "2.0.0")
        second = self.chat("SECOND_CORRECTION")
        request = self.gateway.requests[-1]
        self.assertEqual(request.operation_id, krea2_edit_assistance.OPERATION)
        self.assertIn("FIRST_CORRECTION", request.user_prompt)
        self.assertIn(first.revisions[0].assistant_message, request.user_prompt)
        self.assertEqual(request.user_prompt.count(PROMPT), 1)
        self.assertEqual([i.label for i in request.images], ["STAGE SOURCE"])
        self.assertEqual(LocalKrea2EditStore(self.temp.name).get(second.source_id), second)
        self.assertEqual(serialize_krea2_edit_source(second)["revisions"][0]["assistant_message"], first.revisions[0].assistant_message)

    def test_invalid_reply_does_not_create_a_memory_turn_or_replace_the_working_prompt(self):
        accepted = self.chat("Make an opening")
        self.gateway.response = '{"message":"Only a message"}'
        rejected = self.chat("A smaller opening")
        self.assertEqual(rejected.prompt_status.value, "failed")
        self.assertEqual(rejected.revisions, accepted.revisions)
        self.assertEqual(rejected.generated_prompt, accepted.generated_prompt)
        self.assertIsNotNone(rejected.prompt_error)

    def test_promotion_inherits_render_settings_and_begins_a_new_conversation(self):
        accepted = self.chat("OPENING_HISTORY")
        settings = Krea2EditSettings(model_name="model.safetensors", aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
                                     megapixels=1.4, seed=0, ref_boost=25.5, steps=17)
        prepared = self.service.prepare_attempt(accepted.source_id, Krea2EditAttemptRequest(PROMPT, settings))
        attempt = prepared.attempts[-1].queue().start("fake-execution", "a" * 64).succeed(self.asset.asset_id)
        self.store.save(prepared.replace_attempt(attempt))  # Fixture only: no renderer is invoked.
        child = self.service.promote_attempt(accepted.source_id, attempt.attempt_id, project_name="Wall", step_name="Opening")
        self.assertEqual(child.metadata.ref_boost, 25.5)
        self.assertEqual(child.metadata.steps, 17)
        self.assertEqual(child.metadata.seed, 0)
        self.assertEqual(child.prompt_model_id, "fake")
        self.assertEqual(child.revisions, ())
        self.assertEqual(child.source_asset_id, attempt.output_asset_id)
        self.assertEqual(self.store.get(child.source_id), child)
        self.assertNotIn("OPENING_HISTORY", krea2_edit_assistance.context(child))
        self.assertEqual(serialize_krea2_edit_source(child)["metadata"]["ref_boost"], 25.5)
