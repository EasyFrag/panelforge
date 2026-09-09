"""Explicit provenance and version selection for revised Edit chains."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from .krea2_edit import Krea2EditSource


@dataclass(frozen=True)
class Krea2EditRevision:
    family_id: str
    number: int
    source_project_id: str
    source_id: str
    stage_index: int
    attempt_id: str
    attempt_count: int
    request_id: str

    def __post_init__(self) -> None:
        for name in ("family_id", "source_project_id", "source_id", "attempt_id", "request_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"invalid revision {name}")
        for name, minimum in (("number", 2), ("stage_index", 1), ("attempt_count", 1)):
            value = getattr(self, name)
            if type(value) is not int or value < minimum:
                raise ValueError(f"invalid revision {name}")


def edit_project_versions(sources: Sequence[Krea2EditSource]) -> list[dict[str, object]]:
    groups: dict[str, list[Krea2EditSource]] = {}
    for source in sources:
        groups.setdefault(source.project_id, []).append(source)
    versions = []
    for project_id, stages in groups.items():
        stages.sort(key=lambda stage: stage.stage_index)
        root = stages[0]
        revision = root.revision
        activation = max(stage.revision_activation for stage in stages)
        versions.append({
            "project_id": project_id,
            "family_id": revision.family_id if revision else project_id,
            "number": revision.number if revision else 1,
            "status": "draft" if revision and not activation else "historical",
            "activation": activation,
            "stage_ids": [stage.source_id for stage in stages],
            "resumed_stage_index": revision.stage_index if revision else None,
        })
    for family_id in {version["family_id"] for version in versions}:
        published = [version for version in versions
                     if version["family_id"] == family_id and version["status"] != "draft"]
        if published:
            max(published, key=lambda version: version["activation"])["status"] = "active"
    return versions
