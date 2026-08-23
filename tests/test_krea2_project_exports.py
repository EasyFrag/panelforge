import json
from pathlib import Path
import tempfile
import unittest

from panelforge.domain.krea2_edit import (
    Krea2EditAttempt,
    Krea2EditMetadata,
    Krea2EditSettings,
    Krea2EditSource,
    Krea2EditSourceState,
)
from panelforge.domain.krea2_lab import Krea2AspectRatio
from panelforge.infrastructure.krea2_project_exports import (
    LocalKrea2ProjectExporter,
)
from panelforge.infrastructure.presets import load_krea2_edit_workflow
from panelforge.infrastructure.storage import LocalAssetStore


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflows" / "image.edit" / "krea2-identity" / "0.1.0"


class Krea2ProjectExporterTest(unittest.TestCase):
    def test_export_contains_only_original_and_accepted_chain_with_sidecars(self):
        with tempfile.TemporaryDirectory() as workspace:
            workspace_path = Path(workspace)
            assets = LocalAssetStore(workspace_path / "internal")
            original = assets.create(b"original-image", media_type="image/png")
            accepted_asset = assets.create(b"accepted-image", media_type="image/png")
            second_accepted_asset = assets.create(
                b"second-accepted-image",
                media_type="image/png",
            )
            rejected_asset = assets.create(b"rejected-image", media_type="image/png")
            settings = Krea2EditSettings(
                model_name="Krea2/kroma-v0.2-turbo.safetensors",
                aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
                megapixels=2.1,
                seed=123,
                ref_boost=3.25,
                steps=12,
            )
            accepted = _succeeded_attempt(
                "accepted-attempt",
                "The accepted full-body gorilla prompt.",
                settings,
                accepted_asset.asset_id,
            )
            rejected = _succeeded_attempt(
                "rejected-attempt",
                "The rejected gorilla prompt.",
                settings,
                rejected_asset.asset_id,
            )
            second_accepted = _succeeded_attempt(
                "second-accepted-attempt",
                "The accepted gorilla prompt with a blue moon.",
                settings,
                second_accepted_asset.asset_id,
            )
            root = Krea2EditSource(
                source_id="project-root",
                recipe=load_krea2_edit_workflow(WORKFLOW).reference,
                source_asset_id=original.asset_id,
                filename="Gorille source.png",
                metadata=Krea2EditMetadata(
                    prompt="The original gorilla prompt.",
                    origin="sidecar",
                ),
                accepted_attempt_id=accepted.attempt_id,
                project_name="Gorille bijoux",
                accepted_label="Plein pied",
                state=Krea2EditSourceState.ADVANCED,
                instruction="Show the gorilla full body.",
                attempts=(accepted, rejected),
            )
            child = Krea2EditSource(
                source_id="project-stage-2",
                recipe=root.recipe,
                source_asset_id=accepted_asset.asset_id,
                filename=root.filename,
                metadata=Krea2EditMetadata(
                    prompt=accepted.prompt,
                    origin="edit",
                ),
                project_id=root.project_id,
                stage_index=2,
                parent_source_id=root.source_id,
                parent_attempt_id=accepted.attempt_id,
                project_name=root.project_name,
                accepted_attempt_id=second_accepted.attempt_id,
                accepted_label="Lune bleue",
                state=Krea2EditSourceState.ADVANCED,
                instruction="Turn the moon blue.",
                attempts=(second_accepted,),
            )
            third_stage = Krea2EditSource(
                source_id="project-stage-3",
                recipe=root.recipe,
                source_asset_id=second_accepted_asset.asset_id,
                filename=root.filename,
                metadata=Krea2EditMetadata(
                    prompt=second_accepted.prompt,
                    origin="edit",
                ),
                project_id=root.project_id,
                stage_index=3,
                parent_source_id=child.source_id,
                parent_attempt_id=second_accepted.attempt_id,
                project_name=root.project_name,
            )
            export_root = workspace_path / "KREA2 Projects"
            exporter = LocalKrea2ProjectExporter(export_root)

            first_path = Path(exporter.export((third_stage, child, root), assets))
            first_files = sorted(
                value.relative_to(first_path).as_posix()
                for value in first_path.rglob("*")
                if value.is_file()
            )
            second_path = Path(exporter.export((root, child, third_stage), assets))
            second_files = sorted(
                value.relative_to(second_path).as_posix()
                for value in second_path.rglob("*")
                if value.is_file()
            )

            self.assertEqual(first_path, second_path)
            self.assertEqual(first_files, second_files)
            self.assertEqual(first_path.parent, export_root.resolve())
            self.assertTrue(first_path.name.startswith("gorille-bijoux__"))
            self.assertEqual(len(list(first_path.rglob("*.png"))), 3)
            self.assertEqual(
                (first_path / "00_original" / "00_original.png").read_bytes(),
                b"original-image",
            )
            accepted_image = (
                first_path
                / "01_plein-pied"
                / "01_plein-pied.png"
            )
            self.assertEqual(accepted_image.read_bytes(), b"accepted-image")
            second_accepted_image = (
                first_path
                / "02_lune-bleue"
                / "02_lune-bleue.png"
            )
            self.assertEqual(
                second_accepted_image.read_bytes(),
                b"second-accepted-image",
            )
            self.assertNotIn(b"rejected-image", [
                value.read_bytes() for value in first_path.rglob("*.png")
            ])
            sidecar = json.loads(accepted_image.with_suffix(".txt").read_text(encoding="utf-8"))
            self.assertEqual(sidecar["prompt"], accepted.prompt)
            self.assertEqual(sidecar["render"]["ref_boost"], 3.25)
            self.assertEqual(sidecar["render"]["steps"], 12)
            manifest = json.loads((first_path / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["project_name"], "Gorille bijoux")
            self.assertEqual(len(manifest["accepted_chain"]), 2)
            self.assertEqual(manifest["accepted_chain"][0]["label"], "Plein pied")
            self.assertEqual(manifest["accepted_chain"][1]["label"], "Lune bleue")

    def test_export_bounds_long_human_names_for_windows_paths(self):
        with tempfile.TemporaryDirectory() as workspace:
            workspace_path = Path(workspace)
            assets = LocalAssetStore(workspace_path / "internal")
            original = assets.create(b"original-image", media_type="image/png")
            accepted_asset = assets.create(b"accepted-image", media_type="image/png")
            settings = Krea2EditSettings(
                model_name="Krea2/kroma-v0.2-turbo.safetensors",
                aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN,
                megapixels=2.1,
                seed=123,
                ref_boost=3.25,
                steps=12,
            )
            accepted = _succeeded_attempt(
                "accepted-attempt",
                "The accepted prompt.",
                settings,
                accepted_asset.asset_id,
            )
            source = Krea2EditSource(
                source_id="project-root",
                recipe=load_krea2_edit_workflow(WORKFLOW).reference,
                source_asset_id=original.asset_id,
                filename=f"{'attempt-' + ('a' * 80)}_00001_.png",
                metadata=Krea2EditMetadata(origin="sidecar"),
                accepted_attempt_id=accepted.attempt_id,
                project_name=f"{'attempt-' + ('b' * 80)}_00001_",
                accepted_label=(
                    "On ne voit pas assez son corps et nous aimerions voir "
                    "le ventre ainsi que le haut des pattes avant"
                ),
                state=Krea2EditSourceState.ADVANCED,
                instruction="Show more of the subject.",
                attempts=(accepted,),
            )

            project_path = Path(
                LocalKrea2ProjectExporter(workspace_path / "KREA2 Projects").export(
                    (source,),
                    assets,
                )
            )
            files = [value for value in project_path.rglob("*") if value.is_file()]

            self.assertTrue(files)
            self.assertLessEqual(len(project_path.name), 58)
            self.assertTrue(all(len(value.name) <= 47 for value in files))
            self.assertEqual(
                next(project_path.glob("01_*/*.png")).read_bytes(),
                b"accepted-image",
            )


def _succeeded_attempt(
    attempt_id: str,
    prompt: str,
    settings: Krea2EditSettings,
    output_asset_id: str,
) -> Krea2EditAttempt:
    return (
        Krea2EditAttempt(attempt_id, prompt, settings)
        .queue()
        .start(f"execution-{attempt_id}", "0" * 64)
        .succeed(output_asset_id)
    )


if __name__ == "__main__":
    unittest.main()
