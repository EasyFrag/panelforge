"""User-run regressions: temporary records and fakes, never real LLM/GPU calls."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import tempfile
from types import SimpleNamespace
import unittest
from uuid import uuid4

from panelforge.application.creation_batch import CreationBatchService, CreationBatchConflict
from panelforge.application.creation_batch_csv import parse_intentions_csv
from panelforge.domain.creation_batch import CreationBatchRenderMode, MAX_BATCH_ITEMS, MAX_CSV_BYTES
from panelforge.domain.krea2_assisted import Krea2AssistedProject, Krea2AssistedAttempt, Krea2AssistedAttemptStatus
from panelforge.domain.krea2_assisted_workflows import KREA2_FLUX_KLEIN_WORKFLOW
from panelforge.domain.krea2_batch import Krea2PromptLanguage
from panelforge.domain.krea2_lab import Krea2AspectRatio
from panelforge.domain.krea2_sampling import Krea2AssistedSettings, sampling_from_dict, as_batch_settings
from panelforge.domain.krea2_style_presets import Krea2StylePreset
from panelforge.domain.krea2_art_direction import compile_krea2_art_direction
from panelforge.infrastructure.storage.creation_batch import LocalCreationBatchStore


def make_preset():
    settings = Krea2AssistedSettings(
        model_name="Krea2/test.safetensors", aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
        megapixels=2.1, workflow=KREA2_FLUX_KLEIN_WORKFLOW,
        sampling=sampling_from_dict(None, default_preset_id="finish_4"),
    )
    return Krea2StylePreset("style-test", 1, "Lips", "A jeweled macro photograph", "asset-style",
                           as_batch_settings(settings), "source-project", "source-attempt", 22)


class Projects:
    def __init__(self):
        self.values = {}

    def get(self, project_id):
        if project_id not in self.values:
            raise FileNotFoundError(project_id)
        return self.values[project_id]

    def save(self, project):
        self.values[project.project_id] = project
        return project


class AssistedDouble:
    def __init__(self):
        self.preset = make_preset()
        self.render_settings = Krea2AssistedSettings(
            model_name=self.preset.settings.model_name, aspect_ratio=self.preset.settings.aspect_ratio,
            megapixels=self.preset.settings.megapixels, workflow=KREA2_FLUX_KLEIN_WORKFLOW,
            sampling=sampling_from_dict(None, default_preset_id="moody_beta"),
        )
        self.projects = Projects()
        self.style_catalog = None
        self.keys, self.chat_calls, self.queue_calls = {}, [], []
        self.prepare_calls = 0

    def list_models(self):
        return (SimpleNamespace(model_id="local::gemma"),)

    def list_assistance_recipes(self):
        return [{"version": "6.0.0"}]

    def snapshot_batch_preset(self, preset_id, revision, *, render_mode=CreationBatchRenderMode.FLUX_KLEIN):
        if (preset_id, revision) != (self.preset.preset_id, self.preset.revision):
            raise ValueError("Preset changed")
        base = self.preset.settings
        settings = replace(self.render_settings, model_name=base.model_name, loras=base.loras,
                           aspect_ratio=base.aspect_ratio, megapixels=base.megapixels)
        if isinstance(settings, Krea2AssistedSettings):
            settings = replace(settings, workflow=CreationBatchRenderMode(render_mode).workflow)
        return self.preset, settings

    def create_batch_project(self, *, config, name, intention, managed_key):
        if managed_key in self.keys:
            return self.projects.get(self.keys[managed_key])
        project_id = "managed-" + str(len(self.keys) + 1)
        self.keys[managed_key] = project_id
        return self.projects.save(Krea2AssistedProject(
            project_id=project_id, name=name, intention=intention, model_id=config.model_id,
            assistance_recipe_version=config.recipe_version, prompt_language=config.language,
            style_preset=config.preset, preset_pending=True, art_direction=config.art_direction,
            render_settings=config.settings, local_inspiration_enabled=config.local_inspiration,
        ))

    def stream_chat(self, project_id, intention, **kwargs):
        self.chat_calls.append(project_id)
        if intention == "fail":
            yield SimpleNamespace(error="Fixture LLM failure")
            return
        self.projects.save(replace(self.projects.get(project_id), current_prompt="Complete fixture prompt " + intention))
        yield SimpleNamespace(error=None, kind="completed", text="")

    def prepare_attempt(self, project_id, *, prompt, settings, **kwargs):
        self.prepare_calls += 1
        project = self.projects.get(project_id)
        attempt = Krea2AssistedAttempt(attempt_id="attempt-" + str(self.prepare_calls), index=1,
                                      prompt=compile_krea2_art_direction(prompt, project.art_direction),
                                      canonical_prompt=prompt, settings=settings, seed=self.prepare_calls,
                                      style_preset=project.style_preset, art_direction=project.art_direction,
                                      conversation_prompt_language=project.prompt_language)
        return self.projects.save(project.add_attempt(attempt))

    def queue_attempt(self, project_id, attempt_id):
        self.queue_calls.append((project_id, attempt_id))
        project = self.projects.get(project_id)
        return self.projects.save(project.replace_attempt(project.attempt(attempt_id).queue(1)))

    def finish(self, project_id):
        project = self.projects.get(project_id)
        attempt = replace(project.attempts[0], status=Krea2AssistedAttemptStatus.SUCCEEDED,
                          execution_id="execution", compiled_workflow_sha256="a" * 64,
                          output_asset_id="asset-result")
        self.projects.save(project.replace_attempt(attempt))


def request_values(**changes):
    values = dict(request_id=str(uuid4()), name="My batch", model_id="local::gemma",
                  preset_id="style-test", preset_revision=1,
                  intentions=[{"name": "First", "intention": "Jewels"}])
    values.update(changes)
    return values


class CreationCsvTests(unittest.TestCase):
    def test_bom_semicolons_multiline_quotes_and_duplicate_intentions(self):
        source = '\ufeffnom;intention\r\nA;"Rubis; or jaune\r\navec des ""diamants"""\r\nB;Même idée\r\nC;Même idée\r\n;\r\n'
        items, ignored = parse_intentions_csv(source.encode("utf-8"))
        self.assertEqual(len(items), 3)
        self.assertIn('Rubis; or jaune\r\navec des "diamants"', items[0].intention)
        self.assertEqual(items[1].intention, items[2].intention)
        self.assertEqual(ignored, 1)

    def test_comma_file_and_optional_name(self):
        items, _ = parse_intentions_csv(b'intention\n"red, green"\nblue\n')
        self.assertEqual([i.name for i in items], ["Intention 1", "Intention 2"])
        self.assertEqual(items[0].intention, "red, green")

    def test_bad_files_are_rejected_before_launch(self):
        invalid = [b'', b'prompt\na\n', b'intention,intention\na,b\n', b'intention\n"unfinished',
                   b'intention\na,b\n', b'intention\n\xff', b'intention\n\x00',
                   b'intention\n' + b'a' * 12001, b'a' * (MAX_CSV_BYTES + 1),
                   b'intention\n' + b'idea\n' * (MAX_BATCH_ITEMS + 1)]
        for content in invalid:
            with self.subTest(sample=content[:50]), self.assertRaises(ValueError):
                parse_intentions_csv(content)


class CreationBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LocalCreationBatchStore(self.temp.name)
        self.assisted = AssistedDouble()
        self.service = CreationBatchService(self.store, self.assisted)

    def test_launch_is_durable_and_idempotent_even_after_catalog_changes(self):
        values = request_values()
        batch = self.service.create(**values)
        self.assertEqual(self.store.get(batch.batch_id), batch)
        self.assertEqual(self.assisted.chat_calls, [])
        self.assisted.preset = replace(self.assisted.preset, revision=2)
        restarted = CreationBatchService(self.store, self.assisted)
        self.assertEqual(restarted.create(**values), batch)
        with self.assertRaises(CreationBatchConflict):
            restarted.create(**{**values, "name": "different"})

    def test_concurrent_duplicate_launch_creates_one_record(self):
        values = request_values()
        with ThreadPoolExecutor(max_workers=4) as pool:
            batches = list(pool.map(lambda _: self.service.create(**values), range(4)))
        self.assertEqual(len({batch.batch_id for batch in batches}), 1)
        self.assertEqual(len(self.store.list()), 1)

    def test_mode_is_frozen_for_every_item_and_conflicting_retry_is_rejected(self):
        values = request_values(render_mode="krea2-sampling",
                                intentions=[dict(name=str(i), intention="Jewels") for i in range(2)])
        batch = self.service.create(**values)
        restarted = CreationBatchService(self.store, self.assisted)
        self.assertEqual(restarted.get(batch.batch_id).config.render_mode, CreationBatchRenderMode.TWO_PASS)
        self.assertEqual(restarted.create(**values), batch)
        with self.assertRaises(CreationBatchConflict):
            restarted.create(**{**values, "render_mode": "krea2-flux-klein"})
        for _ in range(2):
            restarted.process_next()
        for item in restarted.get(batch.batch_id).items:
            attempt = self.assisted.projects.get(item.project_id).attempt(item.attempt_id)
            self.assertEqual(attempt.settings.workflow, CreationBatchRenderMode.TWO_PASS.workflow)
            self.assertEqual(attempt.settings.sampling.preset_id, "moody_beta")

    def test_omitted_and_explicit_flux_mode_share_the_historical_request_digest(self):
        import hashlib
        import json
        values = request_values()
        batch = self.service.create(**values)
        legacy_request = {key: value for key, value in values.items() if key != "request_id"}
        legacy_request.update(recipe_version="6.0.0", language="en", local_inspiration=False, art_style_id=None)
        legacy_digest = hashlib.sha256(json.dumps(legacy_request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(batch.request_digest, legacy_digest)
        self.assertEqual(self.service.create(**values, render_mode="krea2-flux-klein"), batch)

    def test_unknown_mode_is_rejected_without_creating_a_batch(self):
        for mode in ("unknown", "krea2-sampling@1.0.0", None):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.service.create(**request_values(render_mode=mode))
        self.assertEqual(self.store.list(), ())
        self.assertEqual(self.assisted.chat_calls, [])

    def test_snapshot_settings_and_status_survive_restart_without_new_calls(self):
        batch = self.service.create(**request_values(language="zh"))
        original = batch.config.settings
        self.assisted.preset = replace(self.assisted.preset, revision=2,
                                       settings=as_batch_settings(replace(original, megapixels=1.0)))
        self.assertFalse(self.service.process_next())
        item = self.service.get(batch.batch_id).items[0]
        self.assertEqual(item.prompt_status, "succeeded")
        project = self.assisted.projects.get(item.project_id)
        self.assertEqual(project.prompt_language, Krea2PromptLanguage.CHINESE_SIMPLIFIED)
        self.assertEqual(project.attempts[0].settings, original)
        restarted = CreationBatchService(self.store, self.assisted)
        before = self.store.get(batch.batch_id).revision
        self.assertFalse(restarted.process_next())
        self.assertEqual(self.store.get(batch.batch_id).revision, before)
        self.assertEqual(len(self.assisted.chat_calls), 1)
        self.assertEqual(len(self.assisted.queue_calls), 1)
        self.assisted.finish(item.project_id)
        self.assertTrue(restarted.process_next())
        self.assertTrue(restarted.get(batch.batch_id).terminal)
        self.assertEqual(restarted.get(batch.batch_id).items[0].output_asset_id, "asset-result")

    def test_failure_isolated_and_duplicate_csv_rows_stay_distinct(self):
        batch = self.service.create(**request_values(intentions=[
            {"name": "Bad", "intention": "fail"}, {"name": "B", "intention": "same"}, {"name": "C", "intention": "same"},
        ]))
        self.assertTrue(self.service.process_next())
        self.assertEqual(self.service.get(batch.batch_id).items[0].image_status, "failed")
        self.service.process_next()
        second = self.service.get(batch.batch_id).items[1]
        self.assisted.finish(second.project_id)
        self.service.process_next()
        self.service.process_next()
        third = self.service.get(batch.batch_id).items[2]
        self.assertNotEqual(second.project_id, third.project_id)

    def test_uncertain_llm_call_is_not_replayed(self):
        batch = self.service.create(**request_values())
        project = self.assisted.create_batch_project(config=batch.config, name="A", intention="A",
                                                    managed_key=batch.batch_id + "/1")
        self.service._update(batch.batch_id, 0, project_id=project.project_id, prompt_status="running")
        restarted = CreationBatchService(self.store, self.assisted)
        self.assertTrue(restarted.process_next())
        item = restarted.get(batch.batch_id).items[0]
        self.assertEqual(item.image_status, "failed")
        self.assertIn("interrompue", item.error)
        self.assertEqual(self.assisted.chat_calls, [])

    def test_saved_prompt_and_unlinked_attempt_are_adopted(self):
        batch = self.service.create(**request_values())
        project = self.assisted.create_batch_project(config=batch.config, name="A", intention="A",
                                                    managed_key=batch.batch_id + "/1")
        self.assisted.projects.save(replace(project, current_prompt="Saved prompt"))
        self.assisted.prepare_attempt(project.project_id, prompt="Saved prompt", settings=batch.config.settings)
        # Simulate termination after project/attempt writes, before batch links are written.
        restarted = CreationBatchService(self.store, self.assisted)
        restarted.process_next()
        self.assertEqual(self.assisted.prepare_calls, 1)
        self.assertEqual(self.assisted.chat_calls, [])
        self.assertEqual(len(self.assisted.queue_calls), 1)
        self.assertIsNotNone(restarted.get(batch.batch_id).items[0].attempt_id)

    def test_failed_receipt_write_does_not_enqueue_and_recovers_same_project(self):
        batch = self.service.create(**request_values())
        original = self.store.save
        self.store.save = lambda batch: (_ for _ in ()).throw(OSError("disk full"))
        with self.assertRaises(OSError):
            self.service.process_next()
        self.assertEqual(self.assisted.chat_calls, [])
        self.assertEqual(self.assisted.queue_calls, [])
        self.store.save = original
        CreationBatchService(self.store, self.assisted).process_next()
        self.assertEqual(len(self.assisted.projects.values), 1)
        self.assertEqual(len(self.assisted.queue_calls), 1)

    def test_store_rejects_paths_outside_namespace(self):
        for value in ("../other", "creation-batch-../../bad", "C:/outside"):
            with self.assertRaises(ValueError):
                self.store.get(value)


class AssistedBatchIntegrationTests(unittest.TestCase):
    def test_real_project_store_retains_snapshot_in_active_branch_and_recovers(self):
        from panelforge.application.krea2_assisted import Krea2AssistedService
        from panelforge.domain.creation_batch import CreationBatchConfig
        from panelforge.infrastructure.storage.krea2_assisted import LocalKrea2AssistedProjectStore
        from threading import RLock
        from unittest.mock import Mock
        # Exercise the actual managed-creation and snapshot methods with the real project codec.
        with tempfile.TemporaryDirectory() as root:
            assisted = Krea2AssistedService.__new__(Krea2AssistedService)
            assisted._lock = RLock()
            assisted.projects = LocalKrea2AssistedProjectStore(root)
            assisted.resources = SimpleNamespace(inventory_warnings=lambda: ())
            assisted.presets = assisted.style_catalog = None
            assisted._project_id_factory = lambda: "unused-unmanaged"
            config = CreationBatchService(LocalCreationBatchStore(root), AssistedDouble()).create(**request_values()).config
            project = assisted.create_batch_project(config=config, name="Lips", intention="Jewels", managed_key="batch/1")
            restored = assisted.projects.get(project.project_id)
            self.assertEqual(restored.style_preset, config.preset)
            self.assertEqual(restored.render_settings, config.settings)
            self.assertEqual(restored.branches[0].style_preset, config.preset)
            self.assertFalse(restored.local_inspiration_enabled)
            self.assertEqual(assisted.create_batch_project(config=config, name="Lips", intention="Jewels", managed_key="batch/1").project_id,
                             project.project_id)
            attempt = Krea2AssistedAttempt("source-attempt", 1, "Saved prompt", config.settings, 22)
            source = replace(restored, project_id=config.preset.source_project_id, attempts=(attempt,))
            assisted.projects.create(source)
            assisted._preset = Mock(return_value=config.preset)
            assisted._validate_render_settings = Mock()
            preset, settings = assisted.snapshot_batch_preset(config.preset.preset_id, config.preset.revision)
            self.assertEqual(settings.workflow, KREA2_FLUX_KLEIN_WORKFLOW)
            self.assertEqual(settings.sampling.preset_id, "moody_beta")
            self.assertEqual(preset, config.preset)
            with self.assertRaises(ValueError):
                assisted.snapshot_batch_preset(config.preset.preset_id, 99)

    def test_new_batches_use_selected_mode_and_moody_with_legacy_missing_or_different_source(self):
        from panelforge.application.krea2_assisted import Krea2AssistedService
        from panelforge.domain.krea2_batch import Krea2LoraSelection
        from unittest.mock import Mock
        preset = make_preset()
        preset = replace(preset, settings=replace(preset.settings,
            loras=(Krea2LoraSelection("krea2/fixture.safetensors", 0.65),)))
        legacy = preset.settings
        alternate = Krea2AssistedSettings(legacy.model_name, legacy.aspect_ratio, 1.0,
            sampling=sampling_from_dict(None, default_preset_id="finish_4"))
        cases = [(mode, source) for mode in CreationBatchRenderMode for source in (None, legacy, alternate)]
        for mode, source_settings in cases:
            with self.subTest(mode=mode, source=type(source_settings).__name__):
                assisted = Krea2AssistedService.__new__(Krea2AssistedService)
                assisted._preset = Mock(return_value=preset)
                assisted._validate_render_settings = Mock()
                assisted.projects = Projects()
                if source_settings is not None:
                    attempt = Krea2AssistedAttempt(preset.source_attempt_id, 1, "Old prompt", source_settings, 22)
                    assisted.projects.save(Krea2AssistedProject(
                        preset.source_project_id, "Old project", "Jewels", "local::gemma", attempts=(attempt,)))
                with tempfile.TemporaryDirectory() as root:
                    assisted.list_models = lambda: (SimpleNamespace(model_id="local::gemma"),)
                    assisted.list_assistance_recipes = lambda: [{"version": "6.0.0"}]
                    assisted.style_catalog = None
                    store = LocalCreationBatchStore(root)
                    batch = CreationBatchService(store, assisted).create(**request_values(render_mode=mode))
                    settings = store.get(batch.batch_id).config.settings
                    self.assertEqual(as_batch_settings(settings), preset.settings)
                    self.assertEqual(settings.workflow, mode.workflow)
                    self.assertEqual(settings.sampling.preset_id, "moody_beta")
                    self.assertEqual((settings.sampling.first_pass.steps, settings.sampling.second_pass.steps), (8, 4))
                    for sampling_pass in (settings.sampling.first_pass, settings.sampling.second_pass):
                        self.assertEqual((sampling_pass.sampler, sampling_pass.scheduler), ("euler_ancestral", "beta"))
                    assisted._validate_render_settings.assert_called_once_with(settings, allow_cached=True)
                if source_settings is not None:
                    self.assertEqual(assisted.projects.get(preset.source_project_id).attempts[0].settings, source_settings)

    def test_existing_batch_replay_keeps_its_historical_render_snapshot(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as root:
            assisted = AssistedDouble()
            assisted.render_settings = as_batch_settings(assisted.render_settings)
            store = LocalCreationBatchStore(root)
            values = request_values()
            batch = CreationBatchService(store, assisted).create(**values)
            assisted.snapshot_batch_preset = Mock(side_effect=AssertionError("Must reuse saved settings"))
            restored = CreationBatchService(store, assisted).create(**values)
            self.assertEqual(restored, batch)
            self.assertNotIsInstance(restored.config.settings, Krea2AssistedSettings)
            self.assertEqual(restored.config.render_mode, CreationBatchRenderMode.TWO_PASS)

    def test_invalid_new_batch_resources_do_not_fall_back_to_legacy_mode(self):
        from panelforge.application.krea2_assisted import Krea2AssistedService
        from unittest.mock import Mock
        assisted = Krea2AssistedService.__new__(Krea2AssistedService)
        assisted._preset = Mock(return_value=make_preset())
        assisted._validate_render_settings = Mock(side_effect=ValueError("Flux unavailable"))
        with self.assertRaisesRegex(ValueError, "Flux unavailable"):
            assisted.snapshot_batch_preset("style-test", 1)
