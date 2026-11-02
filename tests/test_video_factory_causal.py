"""User-run v5 lifecycle and request regressions; fake gateways and temporary stores only."""
from copy import deepcopy
from dataclasses import replace
import json
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from panelforge.application.video_factory import VideoFactoryService
from panelforge.application.video_factory_workflows import FactoryWorkflows
from panelforge.application.vocal_policy import validate_speech, vocal_policy
from panelforge.domain import CompositionStage
from panelforge.domain.little_men_direction import (
    NEED_DIRECTIONS, SOLUTION_PLAN_POLICY_V5, SOLUTION_WRITER_POLICY_V5,
)
from panelforge.domain.little_men_languages import make_selection
from panelforge.domain.localized_speech import FIXED_THANKS, LOCALIZED_THANKS_V5
from panelforge.domain.prompt_composition import PreparationIntent
from panelforge.domain.prompt_lab import CreativeFreedomAxes
from panelforge.domain.video_factory import (
    LITTLE_MEN_EXPERIMENTAL_INTENT, LITTLE_MEN_EXPERIMENTAL_INTENT_V2,
    LITTLE_MEN_EXPERIMENTAL_INTENT_V3, LITTLE_MEN_EXPERIMENTAL_INTENT_V4,
    LITTLE_MEN_STANDARD_INTENT,
    STAGES, apply_preset, invalidate, new_item, preparation_text, stage_signature,
)
from panelforge.domain.video_preparation import ClassicCinematicSettings
from panelforge.infrastructure.storage import LocalPromptCompositionStore
from panelforge.infrastructure.storage.prompt_compositions import intent_from_dict, intent_to_dict
from tests.test_little_men_causal import causal_fixture
from tests.test_video_factory import FakeWorkflows, MemoryStore
from tests.test_video_factory_languages import config_for
from tests.test_video_preparation_recipes import preparation_service


class CausalPreparationTest(unittest.TestCase):
    def test_v5_uses_full_scene_evidence_without_text_classifier_or_forced_tool(self):
        scenes = (
            "Un animal dangereux menace les habitants sous la pluie.",
            "Une vague immense arrive ; les habitants montent des flood barriers.",
            "Une inondation est toujours alimentée par un courant.",
            "Un orage au-dessus du village.",
            "Une tornade traverse la place.",
            "Sécheresse et manque d’eau.",
        )
        for description in scenes:
            with self.subTest(scene=description):
                config = config_for(image_context={"intention": description})
                before = deepcopy(config)
                selected = make_selection(config, "scene")
                selection_before = deepcopy(selected)
                with patch("panelforge.domain.little_men_direction.scene_need",
                           side_effect=AssertionError("v5 must not classify a solution from keywords")):
                    source = preparation_text(config, thanks_selection=selected)
                self.assertEqual(selected["version"], 5)
                self.assertTrue({"flood_first_action", "drought_result", "weather_direction"}.isdisjoint(selected))
                self.assertIn(description, source)
                self.assertFalse(any(direction in source for direction in NEED_DIRECTIONS.values()))
                self.assertIn("Aucun parapluie ni ombrelle", source)
                self.assertEqual(config["render"]["settings"]["duration_seconds"], 10)
                self.assertEqual(config, before)
                self.assertEqual(selected, selection_before)
                resolved = {**selected, "language": "French", "words": "Merci"}
                self.assertEqual(preparation_text(config, thanks_selection=resolved), source)

    def test_current_rules_have_no_concrete_object_catalogue_or_scenario_examples(self):
        current = "\n".join((LITTLE_MEN_EXPERIMENTAL_INTENT,
                              SOLUTION_PLAN_POLICY_V5, SOLUTION_WRITER_POLICY_V5)).casefold()
        for former_example in ("ventouse", "plunger", "aspirateur", "vacuum cleaner",
                               "éventail", "watering can", "par exemple", "for example"):
            self.assertNotIn(former_example, current)
        self.assertIn("accessories are optional", SOLUTION_PLAN_POLICY_V5)
        self.assertIn("no gesture quota", SOLUTION_PLAN_POLICY_V5)

    def test_first_preparation_upgrades_all_untouched_defaults_but_preserves_custom_intent(self):
        defaults = (LITTLE_MEN_EXPERIMENTAL_INTENT_V2, LITTLE_MEN_EXPERIMENTAL_INTENT_V3,
                    LITTLE_MEN_EXPERIMENTAL_INTENT_V4)
        custom = "Mon intention précise : conserver les habitants au premier plan."
        for original_intent in (*defaults, custom):
            with self.subTest(intention=original_intent[:45]):
                config = config_for("Pays : Japon")
                config["intention"] = original_intent
                original_render = deepcopy(config["render"])
                store, adapter = MemoryStore(), FakeWorkflows()
                service = VideoFactoryService(store=store, adapter=adapter)
                item = service.receive([dict(name="Image", config=config,
                    source={"kind": "image", "id": "source"})])["state"]["items"][0]
                service.launch([item["id"]], {item["id"]: item["revision"]})
                service._execute("local_gpu", item["id"], "plan")
                saved = store.value["items"][0]
                self.assertEqual(saved["source_config"]["intention"], original_intent)
                self.assertEqual(saved["config"]["intention"],
                    LITTLE_MEN_EXPERIMENTAL_INTENT if original_intent in defaults else custom)
                self.assertEqual(saved["runtime"]["thanks_selection"]["version"], 5)
                self.assertEqual(saved["config"]["little_men_direction_version"], 5)
                self.assertEqual(saved["config"]["render"], original_render)
                reopened = VideoFactoryService(store=store, adapter=adapter).snapshot()["items"][0]
                self.assertEqual(reopened["runtime"]["thanks_selection"], saved["runtime"]["thanks_selection"])

    def test_existing_v4_preparation_survives_restart_and_model_change_until_reapply(self):
        config = config_for("Pays : Japon\nUne inondation")
        config["intention"] = LITTLE_MEN_EXPERIMENTAL_INTENT_V4
        config["little_men_direction_version"] = None
        old = new_item("Old", config, {}, "old")
        selected = {**make_selection(config, old["id"]), "version": 4,
                    "flood_first_action": "plunger", "drought_result": "lush_growth", "weather_direction": "v1"}
        old["runtime"].update(session_id="old-session", thanks_selection=selected)
        old["status"] = "active"
        original_source = preparation_text(config, thanks_selection=selected)
        store, adapter = MemoryStore(), FakeWorkflows()
        store.value["items"] = [old]
        service = VideoFactoryService(store=store, adapter=adapter)
        service._execute("local_gpu", old["id"], "plan")
        saved = store.value["items"][0]
        self.assertEqual(saved["config"]["intention"], LITTLE_MEN_EXPERIMENTAL_INTENT_V4)
        self.assertEqual(saved["runtime"]["thanks_selection"], selected)
        self.assertIn(NEED_DIRECTIONS["flood"], original_source)
        before = deepcopy(saved["config"])
        saved["config"]["writer_model_id"] = "another-writer"
        invalidate(saved, before)
        self.assertEqual(saved["runtime"]["thanks_selection"]["version"], 4)
        self.assertEqual(preparation_text(saved["config"], thanks_selection=saved["runtime"]["thanks_selection"]),
                         original_source)
        before = deepcopy(saved["config"])
        saved["config"] = apply_preset(before, "little_men_experimental", saved["source_config"])
        invalidate(saved, before)
        upgraded = saved["runtime"]["thanks_selection"]
        self.assertEqual(upgraded["version"], 8)
        self.assertEqual(upgraded["requested_language"], "Japanese")
        self.assertTrue({"flood_first_action", "drought_result", "weather_direction"}.isdisjoint(upgraded))
        self.assertNotIn(NEED_DIRECTIONS["flood"], preparation_text(saved["config"], thanks_selection=upgraded))

    def test_marker_only_reapply_upgrades_v4_even_when_intention_already_matches(self):
        config = config_for("Pays : Japon")
        config["intention"] = LITTLE_MEN_STANDARD_INTENT
        config["little_men_direction_version"] = None
        item = new_item("Same intention", config, {}, "marker-only")
        selected = {**make_selection(config, item["id"]), "version": 4,
                    "language": "Japanese", "words": FIXED_THANKS["Japanese"],
                    "flood_first_action": "plunger", "drought_result": "lush_growth", "weather_direction": "v1"}
        item["runtime"].update(session_id="legacy-session", thanks_selection=selected)
        before = deepcopy(item["config"])
        item["config"] = apply_preset(before, "little_men_experimental", item["source_config"])
        self.assertEqual(item["config"]["intention"], LITTLE_MEN_STANDARD_INTENT)
        self.assertEqual({key for key, value in item["config"].items() if value != before.get(key)},
                         {"little_men_direction_version"})
        invalidate(item, before)
        upgraded = item["runtime"]["thanks_selection"]
        self.assertEqual(upgraded["version"], 8)
        self.assertEqual(upgraded["language"], "Japanese")
        self.assertEqual(upgraded["requested_language"], "Japanese")
        self.assertEqual(upgraded["words"], FIXED_THANKS["Japanese"])
        self.assertTrue({"flood_first_action", "drought_result", "weather_direction"}.isdisjoint(upgraded))
        self.assertNotIn("session_id", item["runtime"])
        self.assertEqual(selected["version"], 4)

    def test_absent_and_none_direction_marker_keep_historical_stage_fingerprints(self):
        historical = config_for("Pays : Japon")
        historical["intention"] = LITTLE_MEN_EXPERIMENTAL_INTENT_V4
        historical.pop("little_men_direction_version")
        explicit_legacy = {**historical, "little_men_direction_version": None}
        for stage in STAGES:
            with self.subTest(stage=stage):
                self.assertEqual(stage_signature(historical, stage), stage_signature(explicit_legacy, stage))
        current = {**historical, "little_men_direction_version": 5}
        self.assertNotEqual(stage_signature(historical, "plan"), stage_signature(current, "plan"))


class CausalLanguageLifecycleTest(unittest.TestCase):
    def test_v5_round_trips_and_keeps_all_eleven_minimal_formulas(self):
        for language, words in FIXED_THANKS.items():
            with self.subTest(language=language):
                intent = PreparationIntent("Scene", speech_policy=LOCALIZED_THANKS_V5, speech_language=language)
                self.assertEqual(intent_from_dict(intent_to_dict(intent)), intent)
                self.assertEqual(validate_speech(((language, words),), (), level=1, source_text="Scene",
                    speech_policy=LOCALIZED_THANKS_V5, speech_language=language), (words,))
                for bad_words in (words + " " + words, words + " kind hand"):
                    with self.assertRaises(ValueError):
                        validate_speech(((language, bad_words),), (), level=1, source_text="Scene",
                            speech_policy=LOCALIZED_THANKS_V5, speech_language=language, locked=(bad_words,))
        policy = vocal_policy(1, speech_policy=LOCALIZED_THANKS_V5, speech_language="French", locked=True)
        self.assertIn("after visibly benefiting", policy)
        self.assertIn("natural pace", policy)
        self.assertIn("French: Merci", policy)
        self.assertNotIn("English: Thank you", policy)

    def test_v5_plan_resolution_is_saved_without_changing_the_preparation_input(self):
        plan, _, _ = causal_fixture(language="Japanese")
        adapter = FactoryWorkflows(prompt_lab=Mock(), composition=Mock(), render=None,
            dlss=None, social=None, episodes=None, assets=None, coordinator=None)
        adapter.prompt_lab.get_session.return_value = NS(session_id="session", references=[])
        adapter.composition.cookbooks.get.return_value = NS(
            preparation_steps=2, slots=[], stages=("beat_sheet",))
        document = NS(approved_revision_id="approved", active_revision=NS(content=json.dumps(plan)))
        adapter.composition.get.return_value.document.return_value = document
        item = new_item("Image", config_for(), {}, "image")
        selection = make_selection(item["config"], item["id"])
        item["runtime"].update(session_id="session", thanks_selection=selection)
        checkpoint = Mock()
        adapter._plan(item, checkpoint, lambda: False, Mock())
        saved = checkpoint.call_args.kwargs["thanks_selection"]
        self.assertEqual((saved["version"], saved["language"], saved["words"]),
                         (5, "Japanese", FIXED_THANKS["Japanese"]))
        self.assertEqual(saved["priority"], selection["priority"])
        self.assertEqual(saved["requested_language"], selection["requested_language"])
        self.assertEqual(preparation_text(item["config"], thanks_selection=saved),
                         preparation_text(item["config"], thanks_selection=selection))
        adapter.composition.stream_generate.assert_not_called()


class CausalRenderAdmissionTest(unittest.TestCase):
    def adapter(self, project):
        adapter = FactoryWorkflows(prompt_lab=None, composition=None, render=Mock(),
            dlss=None, social=None, episodes=None, assets=None, coordinator=None)
        adapter.render.get.return_value = project
        adapter.render.projects.get.return_value = project
        adapter.render.run_timeout = 5
        return adapter

    def test_v5_manual_prompt_is_checked_before_creating_a_render_attempt(self):
        project = NS(project_id="existing-project")
        adapter = self.adapter(project)
        item = new_item("Animal", config_for(), {}, "image")
        item["runtime"].update(render_project_id=project.project_id, thanks_selection={"version": 5})
        item["steps"]["prompt"]["output"] = {"text": "The hand opens a transparent umbrella above the animal."}
        with self.assertRaises(ValueError):
            adapter._video(item, Mock(), lambda: False, Mock())
        adapter.render.prepare_attempt.assert_not_called()
        adapter.render.queue_attempt.assert_not_called()
        adapter.render.execute_attempt.assert_not_called()

    def test_customized_new_preset_still_checks_direct_final_prompt_without_a_plan(self):
        project = NS(project_id="existing-project")
        adapter = self.adapter(project)
        config = config_for()
        self.assertEqual(config["little_men_direction_version"], 5)
        config.update(preset="custom", intention="Mon intention entièrement personnalisée.",
                      final_prompt="The hand opens an umbrella above the animal.")
        item = new_item("Direct", config, {}, "image")
        item["runtime"]["render_project_id"] = project.project_id
        self.assertNotIn("thanks_selection", item["runtime"])
        with self.assertRaises(ValueError):
            adapter._video(item, Mock(), lambda: False, Mock())
        adapter.render.prepare_attempt.assert_not_called()
        adapter.render.queue_attempt.assert_not_called()

    def test_legacy_direct_prompt_without_version_marker_keeps_its_original_admission(self):
        created = NS(attempt_id="legacy-attempt", status=NS(value="created"),
                     effective_prompt="The hand opens an umbrella.")
        queued = NS(attempt_id=created.attempt_id, status=NS(value="queued"))
        completed = NS(attempt_id=created.attempt_id, status=NS(value="succeeded"),
                       output_asset_id="asset-legacy", keyframes=[])
        initial = NS(project_id="legacy-project")
        prepared = NS(project_id=initial.project_id, attempts=[created])
        queue_state = NS(attempt=lambda identity: queued)
        final = NS(project_id=initial.project_id, input_mode=NS(value="fl2va"),
                   attempt=lambda identity: completed)
        adapter = self.adapter(initial)
        adapter.render.prepare_attempt.return_value = prepared
        adapter.render.projects.get.return_value = queue_state
        adapter.render.get.side_effect = [initial, final]
        config = config_for()
        config.pop("little_men_direction_version")
        config.update(preset="custom", intention=LITTLE_MEN_EXPERIMENTAL_INTENT_V4,
                      final_prompt=created.effective_prompt)
        item = new_item("Legacy direct", config, {}, "image")
        item["runtime"]["render_project_id"] = initial.project_id
        output = adapter._video(item, Mock(), lambda: False, Mock())
        self.assertEqual(output["asset_id"], "asset-legacy")
        adapter.render.prepare_attempt.assert_called_once()
        adapter.render.queue_attempt.assert_called_once()
        adapter.render.execute_attempt.assert_called_once()

    def test_resumed_unsent_v5_attempt_checks_its_frozen_effective_prompt(self):
        attempt = NS(attempt_id="unsent", status=NS(value="created"),
                     effective_prompt="The hand leaves a parasol over the villagers.")
        project = NS(project_id="existing-project", attempt=lambda identity: attempt)
        adapter = self.adapter(project)
        item = new_item("Animal", config_for(), {}, "image")
        item["runtime"].update(render_project_id=project.project_id, attempt_id=attempt.attempt_id,
                               thanks_selection={"version": 5})
        item["steps"]["prompt"]["output"] = {"text": "A harmless current prompt with no forbidden prop."}
        with self.assertRaises(ValueError):
            adapter._video(item, Mock(), lambda: False, Mock())
        adapter.render.prepare_attempt.assert_not_called()
        adapter.render.queue_attempt.assert_not_called()
        adapter.render.execute_attempt.assert_not_called()

    def test_completed_attempts_remain_reconcilable_without_retroactive_ban(self):
        for version in (4, 5):
            with self.subTest(version=version):
                attempt = NS(attempt_id="completed", status=NS(value="succeeded"),
                    effective_prompt="The hand opens an umbrella.", output_asset_id="asset-kept", keyframes=[])
                project = NS(project_id="existing-project", input_mode=NS(value="fl2va"),
                             attempt=lambda identity: attempt)
                adapter = self.adapter(project)
                item = new_item("Historical", config_for(), {}, "image")
                item["runtime"].update(render_project_id=project.project_id, attempt_id=attempt.attempt_id,
                                       thanks_selection={"version": version})
                item["steps"]["prompt"]["output"] = {"text": attempt.effective_prompt}
                output = adapter._video(item, Mock(), lambda: False, Mock())
                self.assertEqual(output["asset_id"], "asset-kept")
                adapter.render.prepare_attempt.assert_not_called()
                adapter.render.queue_attempt.assert_not_called()
                adapter.render.execute_attempt.assert_not_called()

    def test_already_queued_v5_attempt_is_resumed_without_revalidating_old_input(self):
        queued = NS(attempt_id="queued", status=NS(value="queued"),
                    effective_prompt="An umbrella is already in the submitted input.")
        completed = NS(attempt_id="queued", status=NS(value="succeeded"),
                       output_asset_id="asset-kept", keyframes=[])
        initial = NS(project_id="existing-project", attempt=lambda identity: queued)
        final = NS(project_id="existing-project", input_mode=NS(value="fl2va"),
                   attempt=lambda identity: completed)
        adapter = self.adapter(initial)
        adapter.render.get.side_effect = [initial, final]
        item = new_item("Submitted", config_for(), {}, "image")
        item["runtime"].update(render_project_id=initial.project_id, attempt_id=queued.attempt_id,
                               thanks_selection={"version": 5})
        item["steps"]["prompt"]["output"] = {"text": queued.effective_prompt}
        output = adapter._video(item, Mock(), lambda: False, Mock())
        self.assertEqual(output["asset_id"], "asset-kept")
        adapter.render.prepare_attempt.assert_not_called()
        adapter.render.queue_attempt.assert_not_called()
        adapter.render.execute_attempt.assert_called_once()


class CausalRequestTest(unittest.TestCase):
    def test_two_calls_persist_the_contract_and_do_not_rechoose_language_or_solution(self):
        for country in ("Pays : Japon", ""):
            with self.subTest(country=country), TemporaryDirectory() as directory:
                config = config_for(country, {"intention": "Un animal dangereux menace la place sous la pluie."})
                selected = make_selection(config, "image")
                source = preparation_text(config, thanks_selection=selected)
                plan, writer, _ = causal_fixture(language="Japanese")
                service, gateway, session, composition = preparation_service(
                    directory, "fl2va", "planned", [json.dumps(plan), json.dumps(writer)],
                    source_text=source, creative_axes=CreativeFreedomAxes(3, 1, 3, 1),
                    cinematic_settings=ClassicCinematicSettings(1))
                intent = replace(composition.preparation_intent, speech_policy=LOCALIZED_THANKS_V5,
                                 speech_language=selected["requested_language"])
                service.configure(session.session_id, composition.cookbook.cookbook_id,
                                  composition.cookbook.version, composition.bindings, preparation_intent=intent)
                service.generate(session.session_id, CompositionStage.BEAT_SHEET)
                service.approve(session.session_id, CompositionStage.BEAT_SHEET)
                service.compositions = LocalPromptCompositionStore(directory)
                reopened = service.get(session.session_id)
                approved = json.loads(reopened.document(CompositionStage.BEAT_SHEET).active_revision.content)
                self.assertEqual(approved["help_contract"], plan["help_contract"])
                self.assertEqual(reopened.preparation_intent, intent)
                service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
                self.assertEqual(len(gateway.requests), 2)
                planner, writer_request = gateway.requests
                self.assertIn(SOLUTION_PLAN_POLICY_V5, planner.system_prompt)
                self.assertIn(SOLUTION_WRITER_POLICY_V5, writer_request.system_prompt)
                self.assertIn("help_contract", planner.user_prompt)
                self.assertIn("help_contract", writer_request.user_prompt)
                self.assertNotIn("Frozen order", writer_request.user_prompt + writer_request.system_prompt)
                self.assertIn("Japanese: ありがとう", writer_request.system_prompt)
                self.assertNotIn("English: Thank you", writer_request.system_prompt)
                self.assertEqual(len(planner.images), 1)
                self.assertEqual(writer_request.images, ())
                final = service.get(session.session_id).document(CompositionStage.FINAL_PROMPT).active_revision.content
                self.assertIn("<d>[Japanese] ありがとう</d>", final)
                self.assertNotIn("[[help:", final)
                actions = [action for shot in approved["shots"] for phase in shot["phases"]
                           for action in phase["actions"]]
                positions = [final.index(action) for action in actions]
                self.assertEqual(positions, sorted(positions))
                for request in gateway.requests:
                    self.assertFalse(any(direction in request.user_prompt for direction in NEED_DIRECTIONS.values()))
                    instructions = (request.system_prompt + "\n" + request.user_prompt).casefold()
                    for inherited_example in ("worked example only", "ceramic bowl", "toward the open box"):
                        self.assertNotIn(inherited_example, instructions)


if __name__ == "__main__":
    unittest.main()
