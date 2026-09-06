"""Offline regression scenarios; gateways are fakes and no renderer is called."""

from dataclasses import replace
from itertools import count
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from panelforge.application.krea2_assisted import Krea2AssistedService
from panelforge.domain.krea2_assisted import (
    Krea2AssistedAttempt, Krea2AssistedProject, Krea2AssistedTurn,
    Krea2AssistedTurnMode as Mode, Krea2AssistedTurnRole as Role,
)
from panelforge.domain.krea2_batch import Krea2AspectRatio, Krea2BatchSettings, Krea2PromptLanguage
from panelforge.features.lab.web import serialize_krea2_assisted_project
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2AssistedProjectStore
from panelforge.infrastructure.storage.krea2_assisted import _serialize, _deserialize
from tests.test_krea2_assisted import Gateway, PNG, PROMPT


SETTINGS = Krea2BatchSettings(
    model_name="krea2_turbo_bf16.safetensors", aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN, megapixels=2.1,
)


def exchange(number, subject):
    return (
        Krea2AssistedTurn(turn_id=f"user-{number}", mode=Mode.CREATION, role=Role.USER, content=subject),
        Krea2AssistedTurn(turn_id=f"assistant-{number}", mode=Mode.CREATION, role=Role.ASSISTANT,
                          content=f"Proposal for {subject}", prompt=PROMPT + subject, model_id="local"),
    )


def fixture():
    attempt = Krea2AssistedAttempt(
        attempt_id="image-1", index=1, prompt=PROMPT + " MANUAL_EDIT", settings=SETTINGS, seed=0,
        conversation_branch_id="main", conversation_turn_id="assistant-1",
        conversation_prompt_language=Krea2PromptLanguage.CHINESE_SIMPLIFIED,
        conversation_model_id="previous-model",
    ).queue().start("execution-1", "a" * 64).succeed("asset-result")
    return Krea2AssistedProject(
        project_id="branch-test", name="Dragon", intention="A dragon", model_id="local",
        assistance_recipe_version="2.0.0", turns=(*exchange(1, "DRAGON_BASE"), *exchange(2, "EGG_FUTURE")),
        current_prompt=PROMPT + " EGG_FUTURE", attempts=(attempt,), feedback_attempt_id=attempt.attempt_id,
    )


class Krea2AssistedBranchDomainTest(unittest.TestCase):
    def test_feedback_keeps_current_conversation_but_restart_isolates_its_prefix(self):
        project = fixture()
        self.assertEqual(project.use_feedback("image-1").turns, project.turns)
        fork = project.branch_from_attempt("image-1", "dragon-again")
        self.assertEqual(fork.turns, project.turns[:2])
        self.assertEqual(fork.current_prompt, project.attempt("image-1").prompt)
        self.assertEqual(fork.render_settings, SETTINGS)
        self.assertEqual(fork.render_seed, 0)
        self.assertEqual(fork.prompt_language, Krea2PromptLanguage.CHINESE_SIMPLIFIED)
        self.assertEqual(fork.revision_model_id, "previous-model")
        fork = fork.add_turns(*exchange(3, "WINGS_BRANCH"))
        returned = fork.switch_branch("main")
        self.assertEqual(returned.turns, project.turns)
        self.assertEqual(returned.current_prompt, project.current_prompt)
        self.assertEqual(returned.switch_branch("dragon-again").turns, fork.turns)

    def test_shared_turns_survive_disk_roundtrip_and_nested_branches(self):
        project = fixture().branch_from_attempt("image-1", "child")
        project = project.add_turns(*exchange(3, "BRANCH_CHILD"))
        attempt = replace(project.attempt("image-1"), attempt_id="image-2", index=2,
                          conversation_branch_id="child", conversation_turn_id="assistant-3")
        project = project.add_attempt(attempt).branch_from_attempt("image-2", "grandchild")
        with tempfile.TemporaryDirectory() as directory:
            store = LocalKrea2AssistedProjectStore(Path(directory))
            store.create(project)
            reopened = LocalKrea2AssistedProjectStore(Path(directory)).get(project.project_id)
        self.assertEqual(reopened, project)
        self.assertEqual(reopened.branches[-1].parent_branch_id, "child")
        serialized = _serialize(reopened)
        self.assertEqual(len(serialized["conversation_turns"]), 6)
        self.assertEqual(len(serialized["branches"][2]["turn_ids"]), 4)
        self.assertEqual(reopened.switch_branch("main").turns[-1].content, "Proposal for EGG_FUTURE")

    def test_old_formats_do_not_invent_checkpoints(self):
        project = fixture()
        for schema in (1, 2, 3):
            with self.subTest(schema=schema):
                value = _serialize(project)
                value["schema_version"] = schema
                for key in ("active_branch_id", "branches", "conversation_turns", "render_settings", "render_seed"):
                    value.pop(key)
                for attempt in value["attempts"]:
                    for key in tuple(attempt):
                        if key.startswith("conversation_"):
                            attempt.pop(key)
                loaded = _deserialize(value)
                with self.assertRaisesRegex(ValueError, "ancien essai"):
                    loaded.branch_from_attempt("image-1", "child")
                resumed = loaded.branch_from_attempt("image-1", "child", image_prompt_only=True)
                self.assertEqual(resumed.turns, ())
                self.assertEqual(resumed.current_prompt, project.attempt("image-1").prompt)
                self.assertEqual(resumed.feedback_attempt_id, "image-1")
                self.assertEqual(resumed.switch_branch("main").turns, loaded.turns)
                self.assertEqual(_deserialize(_serialize(resumed)), resumed)

    def test_empty_checkpoint_is_distinct_from_missing_checkpoint(self):
        project = fixture()
        project = project.replace_attempt(replace(project.attempt("image-1"), conversation_turn_id=None))
        fork = project.branch_from_attempt("image-1", "empty")
        self.assertEqual(fork.turns, ())
        self.assertEqual(len(fork.switch_branch("main").turns), 4)

    def test_invalid_checkpoints_and_shared_turn_mutations_are_rejected(self):
        project = fixture()
        invalid = project.replace_attempt(replace(project.attempt("image-1"), conversation_turn_id="missing"))
        with self.assertRaisesRegex(ValueError, "checkpoint turn"):
            invalid.branch_from_attempt("image-1", "child")
        fork = project.branch_from_attempt("image-1", "child")
        with self.assertRaisesRegex(ValueError, "immutable"):
            replace(fork, turns=(replace(fork.turns[0], content="changed history"), *fork.turns[1:]))

    def test_render_completion_in_another_branch_does_not_move_the_conversation(self):
        project = fixture()
        pending = Krea2AssistedAttempt(
            attempt_id="pending", index=2, prompt=PROMPT, settings=SETTINGS, seed=42,
            conversation_branch_id="main", conversation_turn_id="assistant-2",
        ).queue().start("execution-2", "b" * 64)
        fork = project.add_attempt(pending).branch_from_attempt("image-1", "child")
        completed = fork.replace_attempt(pending.succeed("late-result"))
        self.assertEqual(completed.active_branch_id, "child")
        self.assertEqual(completed.turns, fork.turns)
        self.assertEqual(completed.current_prompt, fork.current_prompt)
        self.assertEqual(completed.attempt("pending").conversation_branch_id, "main")


class Krea2AssistedBranchServiceTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.store = LocalKrea2AssistedProjectStore(root)
        self.assets = LocalAssetStore(root)
        self.image = self.assets.create(PNG, media_type="image/png")
        self.guidance = self.assets.create(PNG + b"guidance", media_type="image/png")
        project = fixture()
        project = replace(project, reference_asset_id=self.image.asset_id)
        project = project.replace_attempt(replace(project.attempt("image-1"), output_asset_id=self.image.asset_id))
        self.store.create(project)
        self.gateway = Gateway((json.dumps({"message": "Proposal", "questions": [],
                                           "prompt": PROMPT, "recommendations": []}),))
        sequence = count(2)
        self.service = Krea2AssistedService(
            gateway=self.gateway, recipes=SimpleNamespace(current=lambda: ()),
            workflow=None, comfy=None, assets=self.assets, projects=self.store,
            resources=SimpleNamespace(list_models=lambda: (), list_loras=lambda: (), inventory_warnings=lambda: ()),
            attempt_id_factory=lambda: f"image-{next(sequence)}",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_checkpoint_is_recorded_at_prepare_and_seed_variants_share_it(self):
        for seed in (0, 9):
            project = self.service.prepare_attempt("branch-test", prompt=PROMPT + " edited", settings=SETTINGS, seed=seed)
        first, second = project.attempts[-2:]
        self.assertEqual(first.conversation_turn_id, "assistant-2")
        self.assertEqual(first.conversation_turn_id, second.conversation_turn_id)
        self.assertEqual(first.conversation_branch_id, second.conversation_branch_id)
        self.assertEqual(len(project.branches), 1)
        self.assertEqual(self.store.get("branch-test").attempts[-1].prompt, PROMPT + " edited")
        self.assertEqual(self.gateway.requests, [])

    def test_request_excludes_sibling_future_and_keeps_both_visual_inputs(self):
        for version in ("1.0.0", "2.0.0"):
            with self.subTest(version=version):
                project = self.store.get("branch-test").switch_branch("main")
                project = replace(project, assistance_recipe_version=version)
                project = project.branch_from_attempt("image-1", "child-" + version)
                user = Krea2AssistedTurn(turn_id="new-" + version, mode=Mode.CREATION, role=Role.USER,
                                         content="Keep the dragon", guidance_asset_id=self.guidance.asset_id)
                project = replace(project, turns=(*project.turns, user))
                request = self.service._completion_request(project, user.content, Mode.CREATION, False)
                self.assertIn("DRAGON_BASE", request.user_prompt)
                self.assertNotIn("EGG_FUTURE", request.user_prompt)
                self.assertNotIn("Arbre", request.system_prompt)
                self.assertEqual([i.label for i in request.images], ["GENERATED RESULT", "TURN GUIDANCE IMAGE"])
                self.assertIn("Initial reference not attached.", request.user_prompt)
        self.assertEqual(self.gateway.requests, [])

    def test_branch_switch_preserves_departing_edits_and_rejects_stale_tab(self):
        fork = self.service.change_branch(
            "branch-test", expected_branch_id="main", attempt_id="image-1",
            current_prompt=PROMPT + " unsent", settings=SETTINGS, seed=None,
        )
        with self.assertRaisesRegex(ValueError, "branche active"):
            self.service.change_branch("branch-test", expected_branch_id="main", branch_id="main")
        returned = self.service.change_branch("branch-test", expected_branch_id=fork.active_branch_id, branch_id="main")
        self.assertEqual(returned.current_prompt, PROMPT + " unsent")
        self.assertIsNone(returned.render_seed)
        self.assertEqual(self.gateway.requests, [])

    def test_initial_reference_retries_then_requires_explicit_guidance_in_both_versions(self):
        for version in ("1.0.0", "2.0.0"):
            with self.subTest(version=version):
                project = Krea2AssistedProject(
                    project_id="source-once", name="Source", intention="Describe this image", model_id="local",
                    assistance_recipe_version=version, reference_asset_id=self.image.asset_id,
                )
                first_user, assistant = exchange(10, "SOURCE_DESCRIPTION")
                project = replace(project, turns=(first_user,))
                first = self.service._completion_request(project, first_user.content, Mode.CREATION, False)
                self.assertEqual([i.label for i in first.images], ["REFERENCE IMAGE"])
                self.assertNotIn("Initial reference not attached.", first.user_prompt)

                # Failed/rejected/cancelled calls have no accepted assistant turn.
                retry_user = replace(first_user, turn_id="retry")
                project = _deserialize(_serialize(replace(project, turns=(*project.turns, retry_user))))
                retry = self.service._completion_request(project, retry_user.content, Mode.CREATION, False)
                self.assertEqual([i.label for i in retry.images], ["REFERENCE IMAGE"])

                next_user = replace(first_user, turn_id="next", content="Change the background")
                project = replace(project, turns=(*project.turns, assistant, next_user), current_prompt=PROMPT)
                project = _deserialize(_serialize(project))
                later = self.service._completion_request(project, next_user.content, Mode.CREATION, False)
                self.assertEqual(later.images, ())
                self.assertIn("Initial reference not attached.", later.user_prompt)
                self.assertIn(PROMPT, later.user_prompt)
                self.assertEqual(project.reference_asset_id, self.image.asset_id)

                resend = replace(first_user, turn_id="resend", content="Look at the source again",
                                 guidance_asset_id=self.image.asset_id, guidance_filename="source.png")
                project = replace(project, turns=(*project.turns, resend))
                explicit = self.service._completion_request(project, resend.content, Mode.CREATION, False)
                self.assertEqual([i.label for i in explicit.images], ["TURN GUIDANCE IMAGE"])
                next_user = replace(next_user, turn_id="after-resend", mode=Mode.RECIPE)
                project = replace(project, turns=(*project.turns, next_user))
                following = self.service._completion_request(project, next_user.content, Mode.RECIPE, False)
                self.assertEqual(following.images, ())
        self.assertEqual(self.gateway.requests, [])

    def test_empty_branch_does_not_reintroduce_the_initial_reference_after_reopening(self):
        project = self.store.get("branch-test")
        project = project.replace_attempt(replace(project.attempt("image-1"), conversation_turn_id=None))
        project = _deserialize(_serialize(project.branch_from_attempt("image-1", "empty")))
        self.assertEqual(project.turns, ())
        user, _ = exchange(12, "Start with the selected result")
        project = replace(project, turns=(user,))
        request = self.service._completion_request(project, user.content, Mode.CREATION, False)
        self.assertEqual([i.label for i in request.images], ["GENERATED RESULT"])
        self.assertIn("Initial reference not attached.", request.user_prompt)
        self.assertNotIn("EGG_FUTURE", request.user_prompt)
        self.assertEqual(self.gateway.requests, [])

    def test_switch_is_blocked_during_stream_and_released_after_close(self):
        stream = self.service.stream_chat("branch-test", "Continue", expected_branch_id="main")
        next(stream)  # Fake delta; no network or model execution.
        with self.assertRaisesRegex(ValueError, "fin de"):
            self.service.change_branch("branch-test", expected_branch_id="main", attempt_id="image-1")
        stream.close()
        fork = self.service.change_branch("branch-test", expected_branch_id="main", attempt_id="image-1")
        self.assertEqual(len(fork.turns), 2)

    def test_api_projection_only_exposes_active_messages_and_branch_summaries(self):
        fork = self.service.change_branch("branch-test", expected_branch_id="main", attempt_id="image-1")
        payload = serialize_krea2_assisted_project(fork)
        self.assertEqual(len(payload["turns"]), 2)
        self.assertEqual(len(payload["branches"]), 2)
        self.assertTrue(payload["attempts"][0]["can_restore_conversation"])
        self.assertEqual(payload["render_seed"], "0")
        self.assertEqual(payload["branches"][1]["parent_branch_id"], "main")
        self.assertEqual(payload["branches"][1]["preview_url"], f"/api/assets/{self.image.asset_id}/content")


if __name__ == "__main__":
    unittest.main()
