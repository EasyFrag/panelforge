"""Pure identities and output roles for KREA2 Assisted workflow families."""

from __future__ import annotations

from dataclasses import dataclass
import re


_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")


@dataclass(frozen=True, slots=True)
class Krea2AssistedWorkflowSelection:
    recipe_id: str = "krea2-sampling"
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not isinstance(self.recipe_id, str) or _IDENTIFIER.fullmatch(self.recipe_id) is None:
            raise ValueError("Identifiant de famille KREA2 Assisted invalide.")
        if not isinstance(self.version, str) or _IDENTIFIER.fullmatch(self.version) is None:
            raise ValueError("Version de famille KREA2 Assisted invalide.")

    @property
    def key(self) -> str:
        return f"{self.recipe_id}@{self.version}"


@dataclass(frozen=True, slots=True)
class Krea2AssistedWorkflowOutput:
    role: str
    node_id: str
    history_field: str
    media_type: str
    prefix_suffix: str = ""
    required: bool = True

    def __post_init__(self) -> None:
        for value, label in (
            (self.role, "role"),
            (self.node_id, "node_id"),
            (self.history_field, "history_field"),
            (self.media_type, "media_type"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must not be empty")
        if not isinstance(self.prefix_suffix, str):
            raise TypeError("prefix_suffix must be a string")
        if not isinstance(self.required, bool):
            raise TypeError("required must be a boolean")


DEFAULT_KREA2_ASSISTED_WORKFLOW = Krea2AssistedWorkflowSelection()
KREA2_FLUX_KLEIN_WORKFLOW = Krea2AssistedWorkflowSelection("krea2-flux-klein", "1.0.0")


def workflow_selection_from_dict(value: object) -> Krea2AssistedWorkflowSelection:
    if value is None:
        return DEFAULT_KREA2_ASSISTED_WORKFLOW
    if isinstance(value, str):
        recipe_id, separator, version = value.partition("@")
        if not separator:
            raise ValueError("La famille de workflow doit inclure sa version.")
        return Krea2AssistedWorkflowSelection(recipe_id, version)
    if not isinstance(value, dict) or set(value) != {"recipe_id", "version"}:
        raise ValueError("Référence de famille KREA2 Assisted invalide.")
    return Krea2AssistedWorkflowSelection(value["recipe_id"], value["version"])
