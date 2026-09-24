"""User-run sampling regressions; only temporary files and compiled graphs."""

from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.domain.krea2_assisted import Krea2AssistedAttempt, Krea2AssistedProject
from panelforge.domain.krea2_batch import Krea2BatchSettings, Krea2LoraSelection
from panelforge.domain.krea2_lab import Krea2AspectRatio
from panelforge.domain.krea2_sampling import (
    Krea2AssistedSampling, Krea2AssistedSettings, Krea2SamplingPass,
    as_batch_settings, sampling_for, sampling_from_dict, sampling_spec,
)
from panelforge.infrastructure.presets.krea2_assisted import load_krea2_assisted_workflow
from panelforge.infrastructure.presets.krea2_batch import load_krea2_batch_workflow
from panelforge.infrastructure.storage.krea2_assisted import LocalKrea2AssistedProjectStore


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "workflows/image.generate.batch/krea2-community/0.2.0"
ASSISTED = ROOT / "workflows/image.generate.assisted/krea2-sampling/1.0.0"


def settings(sampling=None):
    return Krea2AssistedSettings(
        model_name="Krea2/moody.safetensors", aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
        megapixels=2.1, loras=(Krea2LoraSelection("detail.safetensors", 0.5),),
        sampling=sampling or Krea2AssistedSampling(),
    )


class Krea2AssistedSamplingTest(unittest.TestCase):
    def test_presets_are_exact_and_reject_inconsistent_labels(self):
        expected = [("current", 8, 2, "er_sde", "simple"),
                    ("finish_4", 8, 4, "er_sde", "simple"),
                    ("moody_beta", 8, 4, "euler_ancestral", "beta")]
        for preset, (key, first, second, sampler, scheduler) in zip(sampling_spec()["presets"], expected, strict=True):
            value = sampling_from_dict(preset["settings"])
            self.assertEqual(value.preset_id, key)
            self.assertEqual(value.first_pass, Krea2SamplingPass(first, sampler, scheduler))
            self.assertEqual(value.second_pass, Krea2SamplingPass(second, sampler, scheduler))
            self.assertEqual(asdict(value), preset["settings"])
        invalid = asdict(Krea2AssistedSampling())
        invalid["second_pass"]["steps"] = 4
        with self.assertRaises(ValueError):
            sampling_from_dict(invalid)
        invalid["preset_id"] = "custom"
        self.assertEqual(sampling_from_dict(invalid).second_pass.steps, 4)

    def test_invalid_inputs_are_rejected_without_coercion(self):
        for field, values in {"steps": [True, 0, 51, 1.5, "8", None],
                              "sampler": ["unknown", None], "scheduler": ["unknown", None]}.items():
            for value in values:
                raw = asdict(Krea2AssistedSampling(preset_id="custom"))
                raw["first_pass"][field] = value
                with self.subTest(field=field, value=value), self.assertRaises((TypeError, ValueError)):
                    sampling_from_dict(raw)
        for raw in ({}, {**asdict(Krea2AssistedSampling()), "version": "9.0.0"},
                    {**asdict(Krea2AssistedSampling()), "cfg": 4}):
            with self.assertRaises(ValueError):
                sampling_from_dict(raw)

    def test_shared_style_and_batch_settings_do_not_inherit_sampling(self):
        original = settings(sampling_from_dict(sampling_spec()["presets"][2]["settings"]))
        shared = as_batch_settings(original)
        self.assertIs(type(shared), Krea2BatchSettings)
        self.assertEqual((shared.model_name, shared.aspect_ratio, shared.megapixels, shared.loras),
                         (original.model_name, original.aspect_ratio, original.megapixels, original.loras))
        self.assertEqual(sampling_for(shared), Krea2AssistedSampling())

    def test_current_graph_matches_batch_and_presets_only_change_six_bindings(self):
        base = load_krea2_batch_workflow(BASE)
        wrapper = load_krea2_assisted_workflow(ASSISTED, base)
        baseline = base.build(prompt="A studio photograph", settings=settings(), seed=0,
                              output_prefix="test/image", sidecar_text="fixed metadata")
        graph = wrapper.build(prompt="A studio photograph", settings=settings(), seed=0,
                              output_prefix="test/image", sidecar_text="fixed metadata")
        self.assertEqual(graph, baseline)
        custom = Krea2AssistedSampling(Krea2SamplingPass(12, "euler", "karras"),
                                      Krea2SamplingPass(5, "heun", "normal"), preset_id="custom")
        variants = [sampling_from_dict(p["settings"]) for p in sampling_spec()["presets"]] + [custom]
        for value in variants:
            graph = wrapper.build(prompt="A studio photograph", settings=settings(value), seed=0,
                                  output_prefix="test/image", sidecar_text="fixed metadata")
            expected = deepcopy(baseline)
            for name, binding in wrapper.sampling_inputs.items():
                stage, field = name.split(".")
                expected[binding.node_id]["inputs"][binding.input_name] = getattr(getattr(value, stage), field)
            self.assertEqual(graph, expected)
        # Both the shared compiler and immutable source remain unchanged after use.
        self.assertEqual(base.build(prompt="A studio photograph", settings=settings(custom), seed=0,
                                   output_prefix="test/image", sidecar_text="fixed metadata"), baseline)
        self.assertEqual(wrapper.build(prompt="A studio photograph", settings=settings(), seed=0,
                                      output_prefix="test/image", sidecar_text="fixed metadata"), baseline)

    def test_overlay_rejects_wrong_base_and_overlapping_pass_bindings(self):
        base = load_krea2_batch_workflow(BASE)
        original = json.loads((ASSISTED / "manifest.json").read_text(encoding="utf-8"))
        wrong_hash = deepcopy(original)
        wrong_hash["base_workflow"]["workflow_sha256"] = "0" * 64
        overlap = deepcopy(original)
        overlap["sampling_inputs"]["second_pass.sampler"] = overlap["sampling_inputs"]["first_pass.sampler"]
        with tempfile.TemporaryDirectory() as folder:
            for manifest in (wrong_hash, overlap):
                (Path(folder) / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_krea2_assisted_workflow(folder, base)

    def test_storage_keeps_each_attempt_and_branch_draft_independent(self):
        beta = sampling_from_dict(sampling_spec()["presets"][2]["settings"])
        custom = Krea2AssistedSampling(Krea2SamplingPass(10), Krea2SamplingPass(3, "euler", "beta"), preset_id="custom")
        first = Krea2AssistedAttempt("first", 1, "A photograph", settings(beta), 0,
                                     conversation_branch_id="main")
        second = Krea2AssistedAttempt("second", 2, "Another photograph", settings(custom), 123,
                                      conversation_branch_id="main")
        project = Krea2AssistedProject("project", "Sampling", "Photo", "local",
                                      attempts=(first, second), render_settings=second.settings, render_seed=123)
        with tempfile.TemporaryDirectory() as folder:
            store = LocalKrea2AssistedProjectStore(folder)
            store.create(project)
            loaded = store.get(project.project_id)
            self.assertEqual(sampling_for(loaded.attempt("first").settings), beta)
            self.assertEqual(sampling_for(loaded.attempt("second").settings), custom)
            self.assertEqual(sampling_for(loaded.render_settings), custom)
            # The draft may change without rewriting either attempt snapshot.
            updated = replace(loaded, render_settings=settings(), render_seed=0)
            store.save(updated)
            self.assertEqual(sampling_for(store.get("project").attempt("second").settings), custom)
            self.assertEqual(sampling_for(store.get("project").render_settings), Krea2AssistedSampling())

    def test_legacy_schema_reads_default_without_writing_or_changing_type(self):
        old_settings = Krea2BatchSettings("Krea2/base.safetensors", Krea2AspectRatio.PORTRAIT_WIDESCREEN, 0.8)
        attempt = Krea2AssistedAttempt("old", 1, "Photo", old_settings, 0)
        project = Krea2AssistedProject("old-project", "Old", "Photo", "local", attempts=(attempt,))
        with tempfile.TemporaryDirectory() as folder:
            store = LocalKrea2AssistedProjectStore(folder)
            store.create(project)
            path = Path(folder) / "krea2_assisted/old-project/project.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["schema_version"], 14)
            raw["schema_version"] = 8
            path.write_text(json.dumps(raw), encoding="utf-8")
            before = path.read_bytes()
            loaded = store.get("old-project")
            self.assertEqual(loaded.attempt("old").settings, old_settings)
            self.assertEqual(sampling_for(loaded.attempt("old").settings), Krea2AssistedSampling())
            self.assertEqual(path.read_bytes(), before)
