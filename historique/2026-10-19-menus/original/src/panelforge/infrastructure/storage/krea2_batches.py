"""Local durable store for KREA2 recipe batches and image reviews."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
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


class LocalKrea2BatchStore:
    def __init__(self, workspace_root: str | Path) -> None:
        self._root = Path(workspace_root).resolve() / "krea2_batches"
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def create(self, batch: Krea2Batch) -> Krea2Batch:
        with self._lock:
            directory = self._directory(batch.batch_id)
            directory.mkdir(exist_ok=False)
            _atomic_write(directory / "batch.json", _json_bytes(_serialize(batch)))
        return batch

    def save(self, batch: Krea2Batch) -> Krea2Batch:
        with self._lock:
            directory = self._directory(batch.batch_id)
            if not (directory / "batch.json").is_file():
                raise FileNotFoundError(batch.batch_id)
            _atomic_write(directory / "batch.json", _json_bytes(_serialize(batch)))
        return batch

    def get(self, batch_id: str) -> Krea2Batch:
        with self._lock:
            path = self._directory(batch_id) / "batch.json"
            if not path.is_file() or path.is_symlink():
                raise FileNotFoundError(batch_id)
            return _deserialize(json.loads(path.read_text(encoding="utf-8")))

    def list(self, limit: int = 20) -> list[Krea2Batch]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("limit must be a non-negative integer")
        values: list[tuple[float, str, Krea2Batch]] = []
        with self._lock:
            for directory in self._root.iterdir():
                path = directory / "batch.json"
                if directory.is_dir() and not directory.is_symlink() and path.is_file():
                    values.append((path.stat().st_mtime, directory.name, _deserialize(json.loads(path.read_text(encoding="utf-8")))))
        values.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [batch for _, _, batch in values[:limit]]

    def save_compiled_workflow(
        self,
        batch_id: str,
        item_id: str,
        workflow: dict[str, Any],
    ) -> str:
        _safe(item_id)
        directory = self._directory(batch_id) / "workflows"
        directory.mkdir(exist_ok=True)
        content = json.dumps(workflow, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        _atomic_write(directory / f"{item_id}.json", content)
        return hashlib.sha256(content).hexdigest()

    def recent_signatures(self, recipe_id: str, *, limit: int = 40) -> tuple[str, ...]:
        result: list[str] = []
        for batch in self.list(100):
            if batch.recipe_id != recipe_id:
                continue
            for item in reversed(batch.items):
                if item.variation_signature not in result:
                    result.append(item.variation_signature)
                if len(result) >= limit:
                    return tuple(result)
        return tuple(result)

    def _directory(self, batch_id: str) -> Path:
        _safe(batch_id)
        candidate = self._root / batch_id
        candidate.resolve().relative_to(self._root)
        if candidate.is_symlink():
            raise ValueError("batch directory cannot be a symlink")
        return candidate


def _serialize(batch: Krea2Batch) -> dict[str, object]:
    return {
        "schema_version": 1,
        "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "batch_id": batch.batch_id,
        "recipe_id": batch.recipe_id,
        "recipe_version": batch.recipe_version,
        "recipe_sha256": batch.recipe_sha256,
        "model_id": batch.model_id,
        "image_count": batch.image_count,
        "direction": batch.direction,
        "settings": {
            "model_name": batch.settings.model_name,
            "aspect_ratio": batch.settings.aspect_ratio.value,
            "megapixels": batch.settings.megapixels,
            "loras": [{"name": lora.name, "strength": lora.strength} for lora in batch.settings.loras],
        },
        "status": batch.status.value,
        "items": [
            {
                "item_id": item.item_id,
                "index": item.index,
                "prompt": item.prompt,
                "variation_signature": item.variation_signature,
                "seed": str(item.seed),
                "status": item.status.value,
                "execution_id": item.execution_id,
                "compiled_workflow_sha256": item.compiled_workflow_sha256,
                "output_asset_id": item.output_asset_id,
                "error": item.error,
                "review": item.review.value,
                "comment": item.comment,
            }
            for item in batch.items
        ],
        "raw_prompt_response": batch.raw_prompt_response,
        "warnings": list(batch.warnings),
        "error": batch.error,
        "recipe_revision_draft": batch.recipe_revision_draft,
        "recipe_workshop": batch.recipe_workshop,
        "workshop_source_batch_id": batch.workshop_source_batch_id,
        "recipe_snapshot": batch.recipe_snapshot,
    }


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


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def _atomic_write(path: Path, content: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
