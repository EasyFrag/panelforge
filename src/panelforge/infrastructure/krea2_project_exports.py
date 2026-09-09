"""Human-readable exports for validated KREA2 Edit project chains."""

from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import asdict
from panelforge.domain.edit_settings import edit_engine, edit_settings_record, edit_output_dimensions, edit_render_dimensions
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from typing import Protocol

from panelforge.domain.assets import Asset
from panelforge.domain.krea2_edit import (
    Krea2EditAttempt,
    Krea2EditAttemptStatus,
    Krea2EditSource,
)


_UNSAFE_NAME = re.compile(r"[^a-z0-9]+")
_PROJECT_SLUG_MAX_LENGTH = 48
_STAGE_SLUG_MAX_LENGTH = 40


class Krea2ProjectAssetReader(Protocol):
    def get(self, asset_id: str) -> Asset: ...
    def read_bytes(self, asset_id: str) -> bytes: ...


class LocalKrea2ProjectExporter:
    """Materialize only the original and accepted chain outside the workspace."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def export(
        self,
        stages: tuple[Krea2EditSource, ...],
        assets: Krea2ProjectAssetReader,
    ) -> str:
        ordered = tuple(sorted(stages, key=lambda value: value.stage_index))
        if not ordered or ordered[0].stage_index != 1:
            raise ValueError("KREA2 project export requires its first stage")
        project_id = ordered[0].project_id
        if any(value.project_id != project_id for value in ordered):
            raise ValueError("KREA2 project export cannot mix projects")
        if [stage.stage_index for stage in ordered] != list(range(1, len(ordered) + 1)):
            raise ValueError("KREA2 project export requires a single complete chain")
        for parent, child in zip(ordered, ordered[1:]):
            if (child.parent_source_id != parent.source_id
                    or child.parent_attempt_id != parent.accepted_attempt_id
                    or _accepted_attempt(parent).output_asset_id != child.source_asset_id):
                raise ValueError("KREA2 project export cannot mix image lineages")
        project_name = next(
            (value.project_name for value in ordered if value.project_name),
            Path(ordered[0].filename).stem,
        )
        project_slug = _slug(
            project_name,
            "krea2-project",
            max_length=_PROJECT_SLUG_MAX_LENGTH,
        )
        short_id = hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:8]

        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise ValueError("KREA2 project export root cannot be a symlink")
        project_directory = self.root / f"{project_slug}__{short_id}"
        project_directory.mkdir(exist_ok=True)
        if project_directory.is_symlink():
            raise ValueError("KREA2 project export directory cannot be a symlink")

        root = ordered[0]
        original_asset = assets.get(root.source_asset_id)
        original_extension = _extension(original_asset.media_type)
        original_directory = project_directory / "00_original"
        original_stem = "00_original"
        original_image = original_directory / f"{original_stem}{original_extension}"
        original_sidecar = original_directory / f"{original_stem}.txt"
        _atomic_write(original_image, assets.read_bytes(root.source_asset_id))
        _atomic_json(
            original_sidecar,
            {
                "schema_version": 1,
                "kind": "original",
                "project_id": project_id,
                "project_name": project_name,
                "source_id": root.source_id,
                "source_asset_id": root.source_asset_id,
                "original_filename": root.filename,
                "prompt": root.metadata.prompt,
                "prompt_language": root.prompt_language.value,
                "metadata": _metadata(root),
                **({"subject_reference": asdict(root.subject_reference)} if root.subject_reference else {}),
            },
        )

        accepted_entries: list[dict[str, object]] = []
        for stage in ordered:
            if stage.accepted_attempt_id is None:
                continue
            attempt = _accepted_attempt(stage)
            label = stage.accepted_label or stage.instruction or f"Modification {stage.stage_index}"
            label_slug = _slug(
                label,
                f"modification-{stage.stage_index:02d}",
                max_length=_STAGE_SLUG_MAX_LENGTH,
            )
            directory_name = f"{stage.stage_index:02d}_{label_slug}"
            stage_directory = project_directory / directory_name
            image_stem = directory_name
            output_asset = assets.get(attempt.output_asset_id)
            image_path = stage_directory / f"{image_stem}{_extension(output_asset.media_type)}"
            sidecar_path = stage_directory / f"{image_stem}.txt"
            _atomic_write(image_path, assets.read_bytes(attempt.output_asset_id))
            retouch_files = None
            if attempt.retouch:
                source_asset = assets.get(attempt.retouch.source_asset_id)
                generated = assets.get(attempt.retouch.generated_asset_id)
                retouch_files = {"source_file": "source" + _extension(source_asset.media_type),
                                 "generated_file": "generation" + _extension(generated.media_type),
                                 "mask_file": "mask.png"}
                for key, asset_id in (("source_file", source_asset.asset_id),
                                      ("generated_file", generated.asset_id),
                                      ("mask_file", attempt.retouch.mask_asset_id)):
                    _atomic_write(stage_directory / retouch_files[key], assets.read_bytes(asset_id))
            upscale_files = None
            dlss = _dlss_provenance(stage, attempt)
            if dlss:
                _atomic_write(stage_directory / "dlss-report.json", assets.read_bytes(dlss.report_asset_id))
            upscale = _upscale_provenance(stage, attempt)
            if upscale:
                upscale_files = {"input_file": "upscale-input.png", "enhanced_file": "upscale-enhanced.png"}
                for key, asset_id in (("input_file", upscale.input_asset_id), ("enhanced_file", upscale.enhanced_asset_id)):
                    asset = assets.get(asset_id)
                    upscale_files[key] = Path(upscale_files[key]).stem + _extension(asset.media_type)
                    _atomic_write(stage_directory / upscale_files[key], assets.read_bytes(asset_id))
                if upscale.mask_asset_id:
                    upscale_files["mask_file"] = "upscale-mask.png"
                    _atomic_write(stage_directory / upscale_files["mask_file"], assets.read_bytes(upscale.mask_asset_id))
                    asset = assets.get(stage.source_asset_id)
                    upscale_files["source_file"] = "upscale-source" + _extension(asset.media_type)
                    _atomic_write(stage_directory / upscale_files["source_file"], assets.read_bytes(stage.source_asset_id))
            sidecar = _accepted_sidecar(project_name, stage, attempt, retouch_files=retouch_files,
                                       upscale_files=upscale_files)
            if stage.subject_reference:
                reference_asset = assets.get(stage.subject_reference.asset_id)
                subject_filename = "subject-reference" + _extension(reference_asset.media_type)
                _atomic_write(stage_directory / subject_filename, assets.read_bytes(reference_asset.asset_id))
                sidecar["subject_reference"] = {**asdict(stage.subject_reference), "file": subject_filename,
                                               "content_sha256": reference_asset.content_sha256}
            _atomic_json(sidecar_path, sidecar)
            accepted_entries.append(
                {
                    "stage_index": stage.stage_index,
                    "label": label,
                    "source_id": stage.source_id,
                    "attempt_id": attempt.attempt_id,
                    "output_asset_id": attempt.output_asset_id,
                    **({"subject_reference": {**asdict(stage.subject_reference),
                          "file": (stage_directory / subject_filename).relative_to(project_directory).as_posix()}}
                       if stage.subject_reference else {}),
                    "kind": attempt.kind,
                    "dlss": asdict(dlss) if dlss else None,
                    "dlss_report_file": "dlss-report.json" if dlss else None,
                    "engine": edit_engine(attempt.settings),
                    "output_dimensions": edit_output_dimensions(attempt),
                    "upscale": asdict(upscale) if upscale else None,
                    "retouch": asdict(attempt.retouch) if attempt.retouch else None,
                    "retouch_files": ({key: (stage_directory / name).relative_to(project_directory).as_posix()
                                       for key, name in retouch_files.items()} if retouch_files else None),
                    "image": image_path.relative_to(project_directory).as_posix(),
                    "sidecar": sidecar_path.relative_to(project_directory).as_posix(),
                    "content_sha256": output_asset.content_sha256,
                }
            )

        manifest = {
            "schema_version": 1,
            "exported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "project_id": project_id,
            "project_name": project_name,
            "prompt_language": ordered[-1].prompt_language.value,
            "revision": asdict(root.revision) if root.revision else None,
            "version_number": root.revision.number if root.revision else 1,
            "original": {
                "source_id": root.source_id,
                "asset_id": root.source_asset_id,
                "image": original_image.relative_to(project_directory).as_posix(),
                "sidecar": original_sidecar.relative_to(project_directory).as_posix(),
                "content_sha256": original_asset.content_sha256,
            },
            "accepted_chain": accepted_entries,
        }
        _atomic_json(project_directory / "project.json", manifest)
        return str(project_directory)


def _accepted_attempt(stage: Krea2EditSource) -> Krea2EditAttempt:
    attempt = next(
        (
            value
            for value in stage.attempts
            if value.attempt_id == stage.accepted_attempt_id
        ),
        None,
    )
    if (
        attempt is None
        or attempt.status is not Krea2EditAttemptStatus.SUCCEEDED
        or attempt.output_asset_id is None
    ):
        raise ValueError("accepted KREA2 edit attempt is unavailable for export")
    return attempt


def _metadata(source: Krea2EditSource) -> dict[str, object]:
    value = source.metadata
    return {
        "origin": value.origin,
        "model_name": value.model_name,
        "aspect_ratio": value.aspect_ratio.value if value.aspect_ratio else None,
        "megapixels": value.megapixels,
        "seed": str(value.seed) if value.seed is not None else None,
        "loras": [
            {"name": lora.name, "strength": lora.strength}
            for lora in value.loras
        ],
        "warnings": list(value.warnings),
        "firered_settings": edit_settings_record(value.firered_settings) if value.firered_settings else None,
    }


def _upscale_provenance(source, attempt):
    if attempt.upscale:
        return attempt.upscale
    if attempt.retouch:
        return next(a.upscale for a in source.attempts if a.attempt_id == attempt.retouch.original_attempt_id)


def _dlss_provenance(source, attempt):
    if attempt.dlss:
        return attempt.dlss
    if attempt.retouch:
        return next(a.dlss for a in source.attempts if a.attempt_id == attempt.retouch.original_attempt_id)
    return None


def _accepted_sidecar(
    project_name: str,
    source: Krea2EditSource,
    attempt: Krea2EditAttempt,
    *,
    retouch_files: dict[str, str] | None = None,
    upscale_files: dict[str, str] | None = None,
) -> dict[str, object]:
    width, height = edit_render_dimensions(source, attempt) or (None, None)
    output_dimensions = edit_output_dimensions(attempt)
    upscale = _upscale_provenance(source, attempt)
    return {
        "schema_version": 1,
        "kind": "accepted_upscale" if attempt.upscale else "accepted_retouch" if attempt.retouch else "accepted_edit",
        "upscale": asdict(upscale) if upscale else None,
        "dlss": asdict(_dlss_provenance(source, attempt)) if _dlss_provenance(source, attempt) else None,
        "upscale_files": upscale_files,
        "output_dimensions": ({"width": output_dimensions[0], "height": output_dimensions[1]} if output_dimensions else None),
        "render_settings_are_inherited": bool(upscale or attempt.retouch),
        "retouch": asdict(attempt.retouch) if attempt.retouch else None,
        "operation": "image.upscale" if attempt.upscale else "image.compose.mask@1.0.0" if attempt.retouch else "image.edit",
        "composition": ({"width": attempt.retouch.width, "height": attempt.retouch.height,
                         "harmonize": attempt.retouch.harmonize,
                         "harmonize_strength": attempt.retouch.harmonize_strength,
                         "color_method": attempt.retouch.color_method,
                         **(retouch_files or {}), "render_settings_are_inherited": True}
                        if attempt.retouch else None),
        "project_id": source.project_id,
        "revision": asdict(source.revision) if source.revision else None,
        "copied_from_source_id": source.copied_from_source_id,
        "project_name": project_name,
        "stage_index": source.stage_index,
        "label": source.accepted_label,
        "prompt": attempt.prompt,
        "prompt_language": source.prompt_language.value,
        "edit": {
            "source_id": source.source_id,
            "source_asset_id": source.source_asset_id,
            "accepted_attempt_id": attempt.attempt_id,
            "instruction": source.instruction,
        },
        "render": {
            **edit_settings_record(attempt.settings),
            "base_width": width,
            "base_height": height,
        },
        "workflow": {
            "operation_id": (attempt.recipe or source.recipe).operation_id,
            "recipe_id": (attempt.recipe or source.recipe).recipe_id,
            "version": (attempt.recipe or source.recipe).version,
            "sha256": (attempt.recipe or source.recipe).workflow_sha256,
        },
    }


def _slug(value: str, fallback: str, *, max_length: int = 80) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _UNSAFE_NAME.sub("-", ascii_value).strip("-.")
    return (slug or fallback)[:max_length].rstrip("-.")


def _extension(media_type: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }.get(media_type, ".bin")


def _atomic_json(path: Path, value: dict[str, object]) -> None:
    content = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
    ).encode("utf-8") + b"\n"
    _atomic_write(path, content)


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("KREA2 project export path cannot be a symlink")
    # Repeating a long human-readable target in the temporary name can exceed
    # the legacy Windows MAX_PATH limit even when the final path itself fits.
    handle, temporary = tempfile.mkstemp(prefix=".pf-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
