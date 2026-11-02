"""User-run adaptive preset regressions with fake adapters and memory stores only."""
from copy import deepcopy
import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from panelforge.application.video_factory import VideoFactoryService
from panelforge.application.video_factory_workflows import FactoryWorkflows
from panelforge.domain.little_men_languages import make_selection
from panelforge.domain.little_men_variety import PRESET_ID, make_variety_selection
from panelforge.domain.localized_speech import FIXED_THANKS, LOCALIZED_THANKS_V7
from panelforge.domain.video_factory import (
    LITTLE_MEN_ADAPTIVE_INTENT, LITTLE_MEN_VARIETY_INTENT,
    apply_preset, invalidate, new_item, next_steps, preparation_text,
)
from tests.test_little_men_adaptive_contract import adaptive_fixture
from tests.test_video_factory import FakeWorkflows, MemoryStore
from tests.test_video_factory_languages import config_for


def adaptive_config():
    source = config_for("Pays : Japon")
    config = apply_preset(source, PRESET_ID, source)
    config.update(little_men_direction_version=7, intention=LITTLE_MEN_ADAPTIVE_INTENT)
    return config


def frozen_selection(config, identity):
    selection = make_selection(config, identity)
    selection["variety"] = make_variety_selection(identity, [])
    return selection


class AdaptiveLifecycleTest(unittest.TestCase):
    def service(self, config):
        store, adapter = MemoryStore(), FakeWorkflows()
        service = VideoFactoryService(store=store, adapter=adapter)
        response = service.receive([dict(name="Adaptive", config=config,
            source={"kind": "image", "id": "adaptive-source"})])
        identity = response["ids"][0]
        item = service.snapshot()["items"][0]
        service.launch([identity], {identity: item["revision"]})
        return service, store, adapter, identity

    def test_unprepared_legacy_variety_keeps_v6_with_explicit_or_absent_marker(self):
        for marker in (6, None, "absent"):
            with self.subTest(marker=marker):
                config = adaptive_config()
                config.update(intention=LITTLE_MEN_VARIETY_INTENT, little_men_direction_version=marker)
                if marker == "absent":
                    config.pop("little_men_direction_version")
                self.assertEqual(make_selection(config, "legacy")["version"], 6)
                service, store, _adapter, identity = self.service(config)
                service._execute("local_gpu", identity, "plan")
                saved = store.value["items"][0]
                self.assertEqual(saved["config"]["little_men_direction_version"], 6)
                self.assertEqual(saved["config"]["intention"], LITTLE_MEN_VARIETY_INTENT)
                self.assertEqual(saved["runtime"]["thanks_selection"]["version"], 6)
                self.assertEqual(len(saved["runtime"]["thanks_selection"]["variety"]["candidates"]), 12)

    def test_v7_reserves_before_plan_and_reuses_its_input_after_explicit_retry(self):
        service, store, adapter, identity = self.service(adaptive_config())
        observed = []

        def interrupted(snapshot, stage, checkpoint, cancelled, progress):
            selected = snapshot["runtime"]["thanks_selection"]
            self.assertEqual(selected["version"], 7)
            self.assertEqual(selected, store.value["items"][0]["runtime"]["thanks_selection"])
            self.assertEqual(len(selected["variety"]["candidates"]), 12)
            observed.append(deepcopy(selected))
            checkpoint(session_id="adaptive-session")
            raise RuntimeError("Fake interrupted request")

        adapter.run = Mock(side_effect=interrupted)
        service._execute("local_gpu", identity, "plan")
        failed = service.snapshot()["items"][0]
        self.assertEqual(failed["config"]["intention"], LITTLE_MEN_ADAPTIVE_INTENT)
        self.assertEqual(failed["status"], "failed")
        service = VideoFactoryService(store=store, adapter=adapter)
        current = service.snapshot()["items"][0]
        service.action("retry", [identity], {identity: current["revision"]})
        with patch("panelforge.application.video_factory.make_variety_selection",
                   side_effect=AssertionError("An explicit retry must keep its reserved assortment")):
            service._execute("local_gpu", identity, "plan")
        self.assertEqual(observed, [observed[0], observed[0]])

    def test_explicit_migration_preserves_manual_language_context_and_clears_old_plan_choice(self):
        config = adaptive_config()
        config.update(little_men_direction_version=6, intention=LITTLE_MEN_VARIETY_INTENT,
                      little_men_language="French", little_men_context="Objectif saisi par l'utilisateur")
        item = new_item("Existing", config, {}, "legacy")
        old = frozen_selection(config, item["id"])
        old.update(words="Merci", variety_choice={"objects": [], "mechanism_family": "move",
                   "departure_reason": "Direct contact is sufficient."})
        item["runtime"].update(session_id="old-session", thanks_selection=old)
        before = deepcopy(item["config"])
        item["config"] = apply_preset(before, PRESET_ID, item["source_config"])
        invalidate(item, before)
        migrated = item["runtime"]["thanks_selection"]
        self.assertEqual(item["config"]["little_men_direction_version"], 8)
        self.assertEqual(item["config"]["little_men_language"], "French")
        self.assertEqual(item["config"]["little_men_context"], before["little_men_context"])
        self.assertEqual((migrated["version"], migrated["requested_language"], migrated["words"]),
                         (8, "French", "Merci"))
        self.assertNotIn("variety", migrated)
        self.assertNotIn("variety_choice", migrated)
        self.assertNotIn("session_id", item["runtime"])
        self.assertEqual(old["version"], 6)

    def test_model_edit_preserves_each_frozen_version_and_assortment(self):
        for version in (6, 7):
            with self.subTest(version=version):
                config = adaptive_config()
                if version == 6:
                    config.update(little_men_direction_version=6, intention=LITTLE_MEN_VARIETY_INTENT)
                item = new_item("Existing", config, {}, "same-version")
                selected = frozen_selection(config, item["id"])
                selected["variety_choice"] = {"objects": [], "mechanism_family": "move",
                                               "departure_reason": "Direct contact is sufficient."}
                item["runtime"].update(session_id="session", thanks_selection=selected)
                source = preparation_text(config, thanks_selection=selected)
                before = deepcopy(item["config"])
                item["config"]["writer_model_id"] = "another-writer"
                invalidate(item, before)
                saved = item["runtime"]["thanks_selection"]
                self.assertEqual(saved["version"], version)
                self.assertEqual(saved["variety"], selected["variety"])
                self.assertNotIn("variety_choice", saved)
                self.assertEqual(preparation_text(item["config"], thanks_selection=saved), source)

    def test_context_diagnostic_fails_plan_without_automatic_retry_or_dependent_work(self):
        service, store, adapter, identity = self.service(adaptive_config())
        adapter.run = Mock(side_effect=ValueError("Contexte insuffisant : objectif de l'aide indéterminable."))
        service._execute("local_gpu", identity, "plan")
        saved = store.value["items"][0]
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["steps"]["plan"]["status"], "failed")
        self.assertIn("objectif", saved["steps"]["plan"]["error"])
        self.assertNotIn("retry_after", saved)
        self.assertEqual(next_steps(saved), [])
        for stage in ("prompt", "video", "dlss"):
            self.assertEqual(saved["steps"][stage]["status"], "cancelled")
        with patch("panelforge.application.video_factory.Thread") as worker:
            service.dispatch()
            worker.assert_not_called()
        self.assertEqual(adapter.run.call_count, 1)


class AdaptiveWorkflowTest(unittest.TestCase):
    def test_v7_policy_and_actual_choice_are_saved_without_rewriting_preparation_input(self):
        plan, _, context = adaptive_fixture("Japanese")
        adapter = FactoryWorkflows(prompt_lab=Mock(), composition=Mock(), render=None,
            dlss=None, social=None, episodes=None, assets=None, coordinator=None)
        adapter.prompt_lab.get_session.return_value = NS(session_id="session", references=[])
        adapter.composition.cookbooks.get.return_value = NS(
            preparation_steps=2, slots=[], stages=("beat_sheet",))
        document = NS(approved_revision_id="approved", active_revision=NS(content=json.dumps(plan)))
        adapter.composition.get.return_value.document.return_value = document
        item = new_item("Adaptive", adaptive_config(), {}, "adaptive")
        selected = make_selection(item["config"], item["id"])
        selected["variety"] = context["variety_selection"]
        original_source = preparation_text(item["config"], thanks_selection=selected)
        item["runtime"].update(session_id="session", thanks_selection=selected)
        checkpoint = Mock()
        adapter._plan(item, checkpoint, lambda: False, Mock())
        intent = adapter.composition.configure.call_args.kwargs["preparation_intent"]
        self.assertEqual(intent.speech_policy, LOCALIZED_THANKS_V7)
        saved = checkpoint.call_args.kwargs["thanks_selection"]
        self.assertEqual((saved["version"], saved["language"], saved["words"]),
                         (7, "Japanese", FIXED_THANKS["Japanese"]))
        self.assertEqual(saved["variety_choice"], plan["variety_choice"])
        self.assertEqual(saved["variety"], selected["variety"])
        self.assertEqual(preparation_text(item["config"], thanks_selection=saved), original_source)
        adapter.composition.stream_generate.assert_not_called()

    def test_v7_manual_prompt_still_bans_umbrella_before_new_submission(self):
        for frozen in (False, True):
            with self.subTest(frozen=frozen):
                project = NS(project_id="project")
                adapter = FactoryWorkflows(prompt_lab=None, composition=None, render=Mock(),
                    dlss=None, social=None, episodes=None, assets=None, coordinator=None)
                adapter.render.get.return_value = project
                config = adaptive_config()
                config.update(preset="custom", final_prompt="The giant hand opens an umbrella.")
                item = new_item("Adaptive", config, {}, "adaptive")
                item["runtime"]["render_project_id"] = project.project_id
                if frozen:
                    item["runtime"]["thanks_selection"] = {"version": 7}
                with self.assertRaises(ValueError):
                    adapter._video(item, Mock(), lambda: False, Mock())
                adapter.render.prepare_attempt.assert_not_called()
                adapter.render.queue_attempt.assert_not_called()
                adapter.render.execute_attempt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
