"""Small immutable views of durable KREA2 render attempts."""
from dataclasses import dataclass

from .krea2_assisted import Krea2AssistedAttemptStatus, Krea2AssistedProject


PENDING_RENDER_STATUSES = frozenset({
    Krea2AssistedAttemptStatus.QUEUED,
    Krea2AssistedAttemptStatus.SUBMITTING,
    Krea2AssistedAttemptStatus.RUNNING,
    Krea2AssistedAttemptStatus.CANCEL_PENDING,
})


@dataclass(frozen=True, slots=True)
class Krea2RenderQueueEntry:
    project_id: str
    project_name: str
    attempt_id: str
    index: int
    status: Krea2AssistedAttemptStatus
    queue_order: int | None
    error: str | None

    @property
    def sort_key(self) -> tuple[bool, int, str, int]:
        # Resume submitted work before accepting another queued submission.
        return (self.status is Krea2AssistedAttemptStatus.QUEUED,
                self.queue_order or 0, self.project_id, self.index)


def pending_render_entries(project: Krea2AssistedProject) -> tuple[Krea2RenderQueueEntry, ...]:
    return tuple(
        Krea2RenderQueueEntry(project.project_id, project.name, attempt.attempt_id,
                             attempt.index, attempt.status, attempt.queue_order, attempt.error)
        for attempt in project.attempts if attempt.status in PENDING_RENDER_STATUSES
    )
