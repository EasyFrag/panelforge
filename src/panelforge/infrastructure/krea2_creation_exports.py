"""Human-readable exports for explicitly saved KREA2 assisted creations."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata

from panelforge.domain.krea2_assisted import Krea2AssistedAttempt, Krea2AssistedProject


class LocalKrea2CreationExporter:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def export(self, project: Krea2AssistedProject, attempt: Krea2AssistedAttempt, assets) -> str:
        if attempt.output_asset_id is None:
            raise ValueError("the selected attempt has no image")
        asset = assets.get(attempt.output_asset_id)
        if asset.media_type != "image/png":
            raise ValueError("KREA2 assisted exports currently require a PNG")
        content = assets.read_bytes(attempt.output_asset_id)
        suffix = project.project_id.rsplit("-", 1)[-1][:8]
        directory = self.root / f"{_slug(project.name, 54)}__{suffix}"
        directory.mkdir(parents=True, exist_ok=True)
        stem = f"creation_{attempt.index:03d}"
        _atomic_write(directory / f"{stem}.png", content)
        width, height = attempt.settings.resolution
        sidecar = {
            "schema_version": 1,
            "project_id": project.project_id,
            "project_name": project.name,
            "intention": project.intention,
            "attempt_id": attempt.attempt_id,
            "prompt": attempt.prompt,
            "prompt_language": project.prompt_language.value,
            "llm_model_id": project.model_id,
            "render": {
                "model_name": attempt.settings.model_name,
                "aspect_ratio": attempt.settings.aspect_ratio.value,
                "megapixels": attempt.settings.megapixels,
                "resolution": {"width": width, "height": height},
                "seed": attempt.seed,
                "loras": [
                    {"name": lora.name, "strength": lora.strength}
                    for lora in attempt.settings.loras
                ],
            },
        }
        _atomic_write(directory / f"{stem}.txt", _json_bytes(sidecar))
        manifest = {
            "schema_version": 1,
            "project_id": project.project_id,
            "name": project.name,
            "intention": project.intention,
            "reference_filename": project.reference_filename,
            "selected": {
                "attempt_id": attempt.attempt_id,
                "image": f"{stem}.png",
                "sidecar": f"{stem}.txt",
            },
            "published_recipe": (
                f"{project.published_recipe_id}@{project.published_recipe_version}"
                if project.published_recipe_id and project.published_recipe_version
                else None
            ),
        }
        _atomic_write(directory / "project.json", _json_bytes(manifest))
        return str(directory)


def _slug(value: str, maximum: int) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").casefold()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-") or "creation-krea2"
    return slug[:maximum].rstrip("-") or "creation-krea2"


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def _atomic_write(path: Path, content: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.stem[:24]}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
