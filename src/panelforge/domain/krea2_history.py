"""Small, immutable history rows; projects remain the source of truth."""
from dataclasses import dataclass
from datetime import datetime, timezone

from .krea2_assisted import Krea2AssistedProject, Krea2AssistedAttemptStatus


@dataclass(frozen=True, slots=True)
class Krea2ProjectSummary:
    project_id: str
    name: str
    updated_at: str
    turn_count: int
    render_count: int
    attempt_count: int
    last_status: str | None
    preview_asset_id: str | None


def project_summary(project: Krea2AssistedProject, modified_ns: int) -> Krea2ProjectSummary:
    preview = next((a.output_asset_id for a in reversed(project.attempts) if a.output_asset_id), None)
    return Krea2ProjectSummary(
        project_id=project.project_id, name=project.name,
        updated_at=datetime.fromtimestamp(modified_ns / 1_000_000_000, timezone.utc).isoformat(),
        turn_count=len(project.turns),
        render_count=sum(a.status is Krea2AssistedAttemptStatus.SUCCEEDED for a in project.attempts),
        attempt_count=len(project.attempts),
        last_status=project.attempts[-1].status.value if project.attempts else None,
        preview_asset_id=preview,
    )
