"""Human-readable exports for validated KREA2 Edit project chains."""

from __future__ import annotations

from datetime import UTC, datetime
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
            sidecar = _accepted_sidecar(project_name, stage, attempt)
            _atomic_json(sidecar_path, sidecar)
            accepted_entries.append(
                {
                    "stage_index": stage.stage_index,
                    "label": label,
                    "source_id": stage.source_id,
                    "attempt_id": attempt.attempt_id,
                    "output_asset_id": attempt.output_asset_id,
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
    }


def _accepted_sidecar(
    project_name: str,
    source: Krea2EditSource,
    attempt: Krea2EditAttempt,
) -> dict[str, object]:
    width, height = attempt.settings.resolution
    return {
        "schema_version": 1,
        "kind": "accepted_edit",
        "project_id": source.project_id,
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
            "model_name": attempt.settings.model_name,
            "aspect_ratio": attempt.settings.aspect_ratio.value,
            "megapixels": attempt.settings.megapixels,
            "base_width": width,
            "base_height": height,
            "seed": str(attempt.settings.seed),
            "ref_boost": attempt.settings.ref_boost,
            "steps": attempt.settings.steps,
            "loras": [
                {"name": lora.name, "strength": lora.strength}
                for lora in attempt.settings.loras
            ],
        },
        "workflow": {
            "operation_id": source.recipe.operation_id,
            "recipe_id": source.recipe.recipe_id,
            "version": source.recipe.version,
            "sha256": source.recipe.workflow_sha256,
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
