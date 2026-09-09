"""The second, immutable image in an Identity Edit scene/subject stage."""

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class EditSubjectReference:
    asset_id: str
    filename: str
    assisted_project_id: str
    assisted_attempt_id: str
    request_id: str
    initial_instruction: str

    def __post_init__(self):
        for name in ("asset_id", "filename", "assisted_project_id", "assisted_attempt_id", "initial_instruction"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"subject reference {name} must not be empty")
        if not isinstance(self.request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", self.request_id):
            raise ValueError("invalid restaging request ID")
        if len(self.initial_instruction) > 12_000:
            raise ValueError("restaging instruction exceeds 12000 characters")
