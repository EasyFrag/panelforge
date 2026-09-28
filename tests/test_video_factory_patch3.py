"""User-run regressions for factory presets and progress, with no live services."""
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from panelforge.application.video_factory_workflows import FactoryWorkflows
from panelforge.domain.dlss import dlss_progress_ratio
from panelforge.domain.video_factory import apply_preset, configuration, new_item, preparation_text


class FactoryPresetPatchTest(unittest.TestCase):
    def test_lips_overrides_source_options_and_restoring_source_keeps_original(self):
        source = configuration("ref2v")
        source["references"] = [dict(asset_id="asset-image", role="subject_reference")]
        source["social"].update(language="fr", variant_count=1, model_id="other")
        source["final_prompt"] = "Existing prompt"
        original = deepcopy(source)
        lips = apply_preset(source, "lips", source)
        self.assertEqual(source, original)
        self.assertEqual(lips["references"][0]["role"], "last_frame")
        self.assertEqual((lips["mode"], lips["shot_count"], lips["final_prompt"]), ("h3", 1, ""))
        self.assertEqual(lips["render"]["settings"]["duration_seconds"], 10)
        self.assertTrue(lips["dlss"]["enabled"])
        self.assertEqual((lips["social"]["enabled"], lips["social"]["language"], lips["social"]["variant_count"]), (False, "en", 3))
        self.assertIn("gemma-4", lips["social"]["model_id"])
        self.assertEqual(lips["creative_axes"], dict(scene_life=1, camera=1, extra_motion=1, dialogue=0))
        self.assertEqual(apply_preset(lips, "source", source), original)
        little = apply_preset(lips, "little_men", source)
        self.assertEqual(little["render"]["settings"]["duration_seconds"], 8)
        self.assertEqual(little["creative_axes"]["dialogue"], 1)

    def test_lips_preparation_uses_effective_duration_without_changing_saved_intention(self):
        config = configuration()
        config["references"] = [dict(asset_id="asset-image", role="unassigned")]
        config = apply_preset(config, "lips", config)
        for duration in (10, 7.5):
            config["render"]["settings"]["duration_seconds"] = duration
            config["preset"] = "custom"  # Origin survives an advanced setting change.
            before = deepcopy(config)
            session = NS(session_id="session", references=[])
            prompt_lab, composition = Mock(), Mock()
            prompt_lab.get_session.return_value = session
            composition.cookbooks.get.return_value = NS(preparation_steps=2, slots=[])
            adapter = FactoryWorkflows(prompt_lab=prompt_lab, composition=composition,
                render=None, dlss=None, social=None, episodes=None, assets=None, coordinator=None)
            item = new_item("Lips", config, {}, "key")
            item["runtime"]["session_id"] = "session"
            adapter._session(item, Mock(), lambda: False, Mock())
            intent = composition.configure.call_args.kwargs["preparation_intent"]
            self.assertIn(f"{duration:g} secondes", intent.source_text)
            self.assertIn(f"{duration:.2f} secondes", intent.source_text)
            self.assertTrue(intent.source_text.endswith(config["intention"]))
            self.assertEqual(config, before)
            prompt_lab.stream_structure_brief.assert_not_called()

    def test_source_intention_and_injected_dialogue_prompt_are_preserved(self):
        config = configuration("ref2v")
        config.update(intention="Description française, répliques originales.",
                      final_prompt="<d>[English] I will come back.</d>")
        original = deepcopy(config)
        self.assertEqual(preparation_text(config), original["intention"])
        self.assertEqual(config, original)


class FactoryDlssProgressTest(unittest.TestCase):
    def test_phase_percent_is_normalized_over_the_whole_workflow(self):
        self.assertAlmostEqual(dlss_progress_ratio(dict(stage_index=1, stage_count=3, percent=50)), .5)
        self.assertAlmostEqual(dlss_progress_ratio(dict(stage_index=2, stage_count=3, percent=None)), 2/3)
        self.assertEqual(dlss_progress_ratio(dict(stage_index=2, stage_count=3, percent=120)), 1)
        self.assertEqual(dlss_progress_ratio(dict(stage_index=0, stage_count=3, percent=-4)), 0)
        self.assertEqual(dlss_progress_ratio(.25), .25)

    def test_unknown_or_invalid_progress_never_becomes_a_fake_number(self):
        for value in (None, {}, True, "50", float("nan"), float("inf"), [],
                      dict(stage_index=0, stage_count=0, percent=50),
                      dict(stage_index=True, stage_count=3, percent=50),
                      dict(stage_index=3, stage_count=3, percent=50),
                      dict(stage_index=0, stage_count=3, percent="50"),
                      dict(stage_index=0, stage_count=3, percent=float("nan"))):
            with self.subTest(value=value):
                self.assertIsNone(dlss_progress_ratio(value))

    def test_factory_converts_polling_progress_and_clears_it_during_finalization(self):
        raw = dict(stage_index=1, stage_count=3, percent=50, label="Interpolation")
        jobs = [dict(job_id="job", status=status, progress=deepcopy(raw))
                for status in ("running", "receiving", "importing")]
        jobs.append(dict(job_id="job", status="succeeded", output_asset_id="asset-dlss"))
        dlss, callback = Mock(), Mock()
        dlss.jobs.get.side_effect = jobs
        adapter = FactoryWorkflows(prompt_lab=None, composition=None, render=None, dlss=dlss,
            social=None, episodes=None, assets=None, coordinator=None)
        item = new_item("Video", configuration(), {}, "key")
        item["runtime"]["dlss_job_id"] = "job"
        with patch("panelforge.application.video_factory_workflows.time.sleep"):
            result = adapter._dlss(item, Mock(), lambda: False, callback)
        self.assertEqual(result["asset_id"], "asset-dlss")
        self.assertEqual([call.args for call in callback.call_args_list],
                         [("DLSS · running", .5), ("Finalisation DLSS", None), ("Finalisation DLSS", None)])
        dlss.queue.assert_not_called()
        dlss.retry.assert_not_called()


if __name__ == "__main__":
    unittest.main()
