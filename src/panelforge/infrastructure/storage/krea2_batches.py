"""Read-only legacy Batch sources for the active KREA2 editing workshop."""

from __future__ import annotations

import json
from pathlib import Path
import re
from threading import RLock
from typing import Any

from panelforge.domain.krea2_batch import (
    Krea2Batch,
    Krea2BatchItem,
    Krea2BatchItemStatus,
    Krea2BatchSettings,
    Krea2BatchStatus,
    Krea2LoraSelection,
    Krea2ReviewDecision,
)
from panelforge.domain.krea2_lab import Krea2AspectRatio


_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class LocalKrea2BatchHistory:
    def __init__(self, workspace_root: str | Path) -> None:
        self._root = Path(workspace_root).resolve() / "krea2_batches"
        self._lock = RLock()


    def get(self, batch_id: str) -> Krea2Batch:
        with self._lock:
            path = self._directory(batch_id) / "batch.json"
            if not path.is_file() or path.is_symlink():
                raise FileNotFoundError(batch_id)
            return _deserialize(json.loads(path.read_text(encoding="utf-8")))

    def list(self, limit: int = 20) -> list[Krea2Batch]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("limit must be a non-negative integer")
        if not self._root.is_dir() or limit == 0:
            return []
        values: list[tuple[float, str, Krea2Batch]] = []
        with self._lock:
            for directory in self._root.iterdir():
                path = directory / "batch.json"
                if directory.is_dir() and not directory.is_symlink() and path.is_file():
                    values.append((path.stat().st_mtime, directory.name, _deserialize(json.loads(path.read_text(encoding="utf-8")))))
        values.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [batch for _, _, batch in values[:limit]]


    def _directory(self, batch_id: str) -> Path:
        _safe(batch_id)
        candidate = self._root / batch_id
        candidate.resolve().relative_to(self._root)
        if candidate.is_symlink():
            raise ValueError("batch directory cannot be a symlink")
        return candidate


def _deserialize(value: dict[str, Any]) -> Krea2Batch:
    if value.get("schema_version") != 1:
        raise ValueError("unsupported KREA2 batch schema")
    settings = value["settings"]
    return Krea2Batch(
        batch_id=value["batch_id"],
        recipe_id=value["recipe_id"],
        recipe_version=value["recipe_version"],
        recipe_sha256=value["recipe_sha256"],
        model_id=value["model_id"],
        image_count=value["image_count"],
        direction=value["direction"],
        settings=Krea2BatchSettings(
            model_name=settings["model_name"],
            aspect_ratio=Krea2AspectRatio(settings["aspect_ratio"]),
            megapixels=settings["megapixels"],
            loras=tuple(Krea2LoraSelection(name=item["name"], strength=item["strength"]) for item in settings["loras"]),
        ),
        status=Krea2BatchStatus(value["status"]),
        items=tuple(
            Krea2BatchItem(
                item_id=item["item_id"],
                index=item["index"],
                prompt=item["prompt"],
                variation_signature=item["variation_signature"],
                seed=int(item["seed"]),
                status=Krea2BatchItemStatus(item["status"]),
                execution_id=item["execution_id"],
                compiled_workflow_sha256=item["compiled_workflow_sha256"],
                output_asset_id=item["output_asset_id"],
                error=item["error"],
                review=Krea2ReviewDecision(item["review"]),
                comment=item["comment"],
            )
            for item in value["items"]
        ),
        raw_prompt_response=value["raw_prompt_response"],
        warnings=tuple(value["warnings"]),
        error=value["error"],
        recipe_revision_draft=value.get("recipe_revision_draft"),
        recipe_workshop=value.get("recipe_workshop"),
        workshop_source_batch_id=value.get("workshop_source_batch_id"),
        recipe_snapshot=value.get("recipe_snapshot"),
    )


def _safe(value: str) -> None:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise ValueError("unsafe batch identifier")
