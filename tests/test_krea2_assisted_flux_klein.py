"""User-run regressions for the isolated KREA2 + Flux Klein family."""

from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from panelforge.application.krea2_assisted import Krea2AssistedService
from panelforge.domain.krea2_assisted_workflows import (
    DEFAULT_KREA2_ASSISTED_WORKFLOW,
    KREA2_FLUX_KLEIN_WORKFLOW,
    Krea2AssistedWorkflowOutput,
)
from panelforge.domain.krea2_batch import Krea2LoraSelection
from panelforge.domain.krea2_lab import Krea2AspectRatio
from panelforge.domain.krea2_sampling import Krea2AssistedSettings, sampling_from_dict, sampling_spec
from panelforge.domain.recipes import RecipeRef
from panelforge.infrastructure.krea2_creation_exports import LocalKrea2CreationExporter
from panelforge.infrastructure.presets.krea2_flux_klein import load_krea2_flux_klein_workflow
from panelforge.infrastructure.storage import LocalAssetStore, LocalKrea2AssistedProjectStore


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "workflows/image.generate.assisted/krea2-flux-klein/1.0.0"
PNG = b"\x89PNG\r\n\x1a\nFAKE"


def flux_settings(*, lora_count=0):
    moody = next(item["settings"] for item in sampling_spec()["presets"] if item["id"] == "moody_beta")
    return Krea2AssistedSettings(
        model_name="Krea2/custom.safetensors",
        aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
        megapixels=2.1,
        loras=tuple(Krea2LoraSelection(f"krea2/lora-{index}.safetensors", index / 10)
                    for index in range(1, lora_count + 1)),
        sampling=sampling_from_dict(moody),
        workflow=KREA2_FLUX_KLEIN_WORKFLOW,
    )


class FluxKleinWorkflowTest(unittest.TestCase):
    def test_clean_graph_derives_final_geometry_seeds_and_two_lora_banks(self):
        workflow = load_krea2_flux_klein_workflow(RECIPE)
        settings = flux_settings(lora_count=7)
        graph = workflow.build(
            prompt="A cinematic portrait",
            settings=settings,
            seed=123,
            output_prefix="image/test/attempt",
            sidecar_text="fixed metadata",
        )
        self.assertNotIn("LayerUtility: PurgeVRAM V2", {node["class_type"] for node in graph.values()})
        self.assertEqual(graph["950"]["inputs"]["megapixels"], round(2.1 / 2.25, 4))
        self.assertEqual(graph["1015"]["inputs"]["scale_to_length"], max(settings.resolution))
        self.assertEqual(graph["1045"]["inputs"]["noise_seed"], 123)
        self.assertEqual(graph["1045"]["inputs"]["end_at_step"], 8)
        self.assertNotEqual(graph["1041"]["inputs"]["seed"], 123)
        self.assertNotEqual(graph["999"]["inputs"]["noise_seed"], 123)
        self.assertEqual([key for key in graph["885"]["inputs"] if key.startswith("lora_")],
                         [f"lora_{index}" for index in range(1, 6)])
        self.assertEqual([key for key in graph["1040"]["inputs"] if key.startswith("lora_")],
                         ["lora_1", "lora_2"])
        self.assertEqual(graph["1022"]["inputs"]["filename_prefix"], "image/test/attempt")
        self.assertEqual(graph["1050"]["inputs"]["filename_prefix"], "image/test/attempt-pre-flux")
        self.assertEqual([output.role for output in workflow.outputs], ["final", "pre_flux"])

    def test_build_is_deterministic_and_does_not_mutate_recipe(self):
        workflow = load_krea2_flux_klein_workflow(RECIPE)
        settings = flux_settings(lora_count=10)
        first = workflow.build(prompt="Photo", settings=settings, seed=42,
                               output_prefix="image/a", sidecar_text="metadata")
        second = workflow.build(prompt="Photo", settings=settings, seed=42,
                                output_prefix="image/a", sidecar_text="metadata")
        self.assertEqual(first, second)
        self.assertFalse(any(key.startswith("lora_") for key in workflow.workflow["885"]["inputs"]))


class _NoLlm:
    def stream(self, _request):
        raise AssertionError("rendering must not call the LLM")


class _Workflow:
    def __init__(self, selection, digest, outputs):
        self.reference = RecipeRef("image.generate.assisted", selection.recipe_id, selection.version, digest)
        self.outputs = outputs
        self.output_node_id = outputs[0].node_id
        self.output_history_field = outputs[0].history_field
        self.output_media_type = outputs[0].media_type
        self.display_name = selection.key
        self.description = selection.key
        self.default_sampling_preset_id = "current"
        self.supports_sampling = True

    def seed_metadata(self, seed):
        return {"root": seed}

    def build(self, *, settings, **values):
        return {**values, "family": self.reference.recipe_id, "settings": asdict(settings)}


class _Comfy:
    def __init__(self):
        self.workflows = []

    def submit_workflow(self, workflow):
        self.workflows.append(workflow)
        return "remote-1"

    def get_history(self, execution_id):
        return {execution_id: {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {
                "final": {"images": [{"filename": "final.png", "type": "output"}]},
                "pre": {"images": [{"filename": "pre.png", "type": "output"}]},
            },
        }}

    def download_output(self, **_values):
        return PNG

    def cancel_execution(self, _execution_id):
        return None


class _Resources:
    def list_models(self):
        return (SimpleNamespace(comfy_name="Krea2/custom.safetensors"),)

    def list_loras(self):
        return ()


class FluxKleinServiceTest(unittest.TestCase):
    def test_family_reference_and_both_outputs_are_snapshotted(self):
        outputs = (
            Krea2AssistedWorkflowOutput("final", "final", "images", "image/png"),
            Krea2AssistedWorkflowOutput("pre_flux", "pre", "images", "image/png", "-pre-flux", False),
        )
        default = _Workflow(DEFAULT_KREA2_ASSISTED_WORKFLOW, "a" * 64, outputs[:1])
        flux = _Workflow(KREA2_FLUX_KLEIN_WORKFLOW, "b" * 64, outputs)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service = Krea2AssistedService(
                gateway=_NoLlm(), recipes=SimpleNamespace(current=lambda: ()),
                workflow=default, workflows=(default, flux), comfy=_Comfy(),
                assets=LocalAssetStore(root), projects=LocalKrea2AssistedProjectStore(root),
                exporter=LocalKrea2CreationExporter(root / "exports"),
                resources=_Resources(), poll_interval=0.001,
                project_id_factory=lambda: "project", attempt_id_factory=lambda: "attempt",
            )
            project = service.create_project(name="Family", intention="Photo", model_id="local")
            queued = service.prepare_attempt(project.project_id, prompt="Photo", settings=flux_settings(),
                                             seed=7, enqueue=True)
            result = service.execute_attempt(project.project_id, queued.attempts[-1].attempt_id)
            attempt = result.attempt("attempt")
            self.assertEqual(attempt.workflow, flux.reference)
            self.assertIsNotNone(attempt.output_asset_id)
            self.assertIsNotNone(attempt.pre_flux_asset_id)
            self.assertEqual(attempt.output_warnings, ())
            reloaded = service.projects.get(project.project_id).attempt("attempt")
            self.assertEqual(reloaded.workflow, flux.reference)
            self.assertEqual(reloaded.pre_flux_asset_id, attempt.pre_flux_asset_id)
            exported = service.save_image(project.project_id, "attempt")
            self.assertTrue(Path(exported.export_path, "creation_001_pre_flux.png").is_file())
            sidecar = json.loads(Path(exported.export_path, "creation_001.txt").read_text(encoding="utf-8"))
            self.assertEqual(sidecar["workflow"], asdict(flux.reference))
            self.assertEqual(sidecar["artifacts"]["pre_flux"], "creation_001_pre_flux.png")


if __name__ == "__main__":
    unittest.main()
