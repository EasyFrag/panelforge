"""Version routing and stage-relative context with a fake gateway, no rendering."""

from dataclasses import replace
import hashlib
import json
import tempfile
import unittest

from panelforge.application import Krea2EditService, Krea2EditAttemptRequest
from panelforge.application import krea2_edit_assistance as v2, krea2_edit_assistance_v3 as v3
from panelforge.application.krea2_edit import _PROMPT_SYSTEM
from panelforge.domain import Krea2EditMetadata, Krea2EditSettings, Krea2AspectRatio
from panelforge.domain.krea2_batch import Krea2PromptLanguage
from panelforge.features.lab.web import serialize_krea2_edit_source
from panelforge.infrastructure.presets import load_krea2_edit_workflow
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2EditStore
from panelforge.infrastructure.storage.krea2_edits import _to_dict, _from_dict
from tests.test_krea2_edit import FakeGateway, PNG, WORKFLOW


SHORT = "Replace the central paint patch with brown soil."
FULL = "A fixed wide photograph of a stone wall with a rectangular opening, intact surrounding stones and natural daylight."


class EditAssistanceV3Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.assets = LocalAssetStore(self.temp.name)
        self.asset = self.assets.create(PNG, media_type="image/png")
        self.store = LocalKrea2EditStore(self.temp.name)
        self.gateway = FakeGateway()
        self.service = Krea2EditService(
            gateway=self.gateway, workflow=load_krea2_edit_workflow(WORKFLOW),
            comfy=None, assets=self.assets, sources=self.store,
        )
        self.source = self.service.add_source(
            asset_id=self.asset.asset_id, filename="wall.png", metadata=Krea2EditMetadata(),
        )

    def chat(self, instruction="Remove the paint", *, version="3.0.0", output=SHORT, **kwargs):
        self.gateway.response = output if version == "1.0.0" else json.dumps({
            "message": "Je propose de remplacer la peinture par de la terre.", "prompt": output,
        })
        return list(self.service.stream_prepare_prompt(
            self.source.source_id, instruction, "fake", assistance_version=version, **kwargs,
        ))[-1].source

    def test_v3_accepts_short_edits_and_persists_exact_version_without_a_render(self):
        result = self.chat()
        self.assertEqual(result.generated_prompt, SHORT)
        self.assertEqual(result.prompt_status.value, "ready")
        self.assertEqual(result.revisions[-1].assistance_version, "3.0.0")
        self.assertEqual(self.gateway.requests[-1].operation_id, v3.OPERATION)
        self.assertEqual(self.gateway.requests[-1].system_prompt, v3.SYSTEM)
        self.assertEqual([image.label for image in self.gateway.requests[-1].images], ["STAGE SOURCE"])
        self.assertEqual(result.attempts, ())
        loaded = LocalKrea2EditStore(self.temp.name).get(result.source_id)
        self.assertEqual(loaded, result)
        self.assertEqual(serialize_krea2_edit_source(loaded)["revisions"][-1]["assistance_version"], "3.0.0")

    def test_switching_versions_keeps_their_contracts_and_saved_history(self):
        first = self.chat("FIRST_CORRECTION", version="2.0.0", output=FULL)
        second = self.chat("SECOND_CORRECTION")
        request = self.gateway.requests[-1]
        self.assertIn("CURRENT EDIT TARGET", request.user_prompt)
        self.assertEqual(request.user_prompt.count(FULL), 1)
        self.assertIn("FIRST_CORRECTION", request.user_prompt)
        self.assertEqual(second.revisions[0], first.revisions[0])
        rejected = self.chat(version="2.0.0", output=SHORT)
        self.assertEqual(rejected.prompt_status.value, "failed")
        self.assertEqual(rejected.revisions, second.revisions)
        self.assertEqual(rejected.generated_prompt, SHORT)
        final = self.chat(version="2.0.0", output=FULL)
        self.assertEqual(self.gateway.requests[-1].system_prompt, v2.SYSTEM)
        self.assertEqual(self.gateway.requests[-1].operation_id, v2.OPERATION)
        self.assertIn("CURRENT TARGET PROMPT TO REWRITE", self.gateway.requests[-1].user_prompt)
        final = self.chat(version="1.0.0", output=FULL)
        self.assertEqual(self.gateway.requests[-1].system_prompt, _PROMPT_SYSTEM)
        self.assertEqual([r.assistance_version for r in final.revisions], ["2.0.0", "3.0.0", "2.0.0", "1.0.0"])

    def test_source_caption_is_not_treated_as_pending_work_even_when_sent_by_the_editor(self):
        self.source = self.store.save(replace(self.source, metadata=Krea2EditMetadata(prompt=FULL)))
        self.chat(base_prompt=FULL)
        request = self.gateway.requests[-1]
        self.assertIn("SOURCE DESCRIPTION (context only", request.user_prompt)
        self.assertNotIn("CURRENT EDIT TARGET", request.user_prompt)
        self.assertNotIn("Reconstruct", request.user_prompt)
        self.assertEqual(request.user_prompt.count(FULL), 1)

    def test_manual_target_overrides_current_prompt_without_stacking_old_prompt_copies(self):
        self.chat(output=FULL)
        manual = "Widen the opening and line its interior with wood."
        self.chat(base_prompt=manual)
        user = self.gateway.requests[-1].user_prompt
        self.assertIn("CURRENT EDIT TARGET", user)
        self.assertEqual(user.count(manual), 1)
        self.assertNotIn(FULL, user)

    def test_feedback_is_evidence_and_promoting_it_resets_stage_context(self):
        accepted = self.chat("FIRST_STAGE_CORRECTION", output=FULL)
        settings = Krea2EditSettings(
            model_name="model.safetensors", aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
            megapixels=2.1, seed=42, steps=10, ref_boost=2.5,
        )
        prepared = self.service.prepare_attempt(accepted.source_id, Krea2EditAttemptRequest(FULL, settings))
        output = self.assets.create(PNG + b"different-result", media_type="image/png")
        attempt = prepared.attempts[-1].queue().start("fixture-only", "a" * 64).succeed(output.asset_id)
        self.store.save(prepared.replace_attempt(attempt))
        feedback = self.chat(feedback_attempt_id=attempt.attempt_id)
        request = self.gateway.requests[-1]
        self.assertEqual([i.label for i in request.images], ["STAGE SOURCE", "GENERATED FEEDBACK"])
        self.assertEqual(request.images[0].content, PNG)
        self.assertEqual(request.images[1].content, PNG + b"different-result")
        self.assertEqual(feedback.source_asset_id, self.asset.asset_id)
        self.assertEqual(feedback.revisions[-1].feedback_attempt_id, attempt.attempt_id)
        self.source = self.service.promote_attempt(feedback.source_id, attempt.attempt_id)
        self.chat("NEXT_STAGE_CORRECTION", base_prompt=FULL)
        request = self.gateway.requests[-1]
        self.assertEqual(request.images[0].content, PNG + b"different-result")
        self.assertIn("SOURCE DESCRIPTION", request.user_prompt)
        self.assertNotIn("FIRST_STAGE_CORRECTION", request.user_prompt)
        self.assertEqual(self.source.metadata.megapixels, 2.1)

    def test_invalid_reply_and_unknown_version_leave_the_accepted_prompt_intact(self):
        accepted = self.chat()
        self.gateway.response = '{"message":"missing prompt"}'
        rejected = list(self.service.stream_prepare_prompt(
            self.source.source_id, "Retry", "fake", assistance_version="3.0.0",
        ))[-1].source
        self.assertEqual(rejected.revisions, accepted.revisions)
        self.assertEqual(rejected.generated_prompt, SHORT)
        before = self.store.get(self.source.source_id)
        count = len(self.gateway.requests)
        with self.assertRaisesRegex(ValueError, "unsupported"):
            list(self.service.stream_prepare_prompt(self.source.source_id, "Retry", "fake", assistance_version="99.0.0"))
        self.assertEqual(len(self.gateway.requests), count)
        self.assertEqual(self.store.get(self.source.source_id), before)

    def test_short_chinese_edit_and_legacy_record_loading(self):
        result = self.chat(output="把中央白色涂料换成棕色泥土。", prompt_language=Krea2PromptLanguage.CHINESE_SIMPLIFIED)
        self.assertEqual(result.prompt_status.value, "ready")
        self.assertEqual(result.revisions[-1].prompt_language, Krea2PromptLanguage.CHINESE_SIMPLIFIED)
        for schema in range(2, 7):
            raw = _to_dict(result)
            raw["schema_version"] = schema
            raw["revisions"][0].pop("assistance_version")
            self.assertEqual(_from_dict(raw).revisions[0].assistance_version, "1.0.0")

    def test_frozen_v2_and_v1_system_prompts_remain_available(self):
        self.assertEqual(hashlib.sha256(v2.SYSTEM.encode()).hexdigest(),
                         "f9b968683162a1f3772e7d9d05f3f0a71acb8bc957edcb1173ab384204f39329")
        self.assertEqual(hashlib.sha256(_PROMPT_SYSTEM.encode()).hexdigest(),
                         "98a302ee6a5e7edc618729baabdbc728e91718d95f917460d711fe0c7fcd2e25")
