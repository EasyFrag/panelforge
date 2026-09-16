"""Versioned two-pass sampling settings used only by KREA2 Assisted."""

from dataclasses import asdict, dataclass, field
from typing import Any

from .krea2_batch import Krea2BatchSettings
from .krea2_assisted_workflows import (
    DEFAULT_KREA2_ASSISTED_WORKFLOW,
    Krea2AssistedWorkflowSelection,
)


SAMPLERS = ("er_sde", "euler_ancestral", "euler", "heun", "dpmpp_2m", "dpmpp_sde")
SCHEDULERS = ("simple", "beta", "normal", "karras", "exponential", "sgm_uniform")
SAMPLING_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class Krea2SamplingPass:
    steps: int
    sampler: str = "er_sde"
    scheduler: str = "simple"

    def __post_init__(self) -> None:
        if type(self.steps) is not int or not 1 <= self.steps <= 50:
            raise ValueError("Le nombre de steps doit être un entier entre 1 et 50.")
        if self.sampler not in SAMPLERS:
            raise ValueError("Sampler KREA2 Assisted non pris en charge.")
        if self.scheduler not in SCHEDULERS:
            raise ValueError("Scheduler KREA2 Assisted non pris en charge.")


_PRESETS = {
    "current": ("Actuel · 8 + 2", Krea2SamplingPass(8), Krea2SamplingPass(2)),
    "finish_4": ("Finition 4 steps · 8 + 4", Krea2SamplingPass(8), Krea2SamplingPass(4)),
    "moody_beta": ("Moody · Beta · expérimental", Krea2SamplingPass(8, "euler_ancestral", "beta"),
                   Krea2SamplingPass(4, "euler_ancestral", "beta")),
}


@dataclass(frozen=True, slots=True)
class Krea2AssistedSampling:
    first_pass: Krea2SamplingPass = field(default_factory=lambda: Krea2SamplingPass(8))
    second_pass: Krea2SamplingPass = field(default_factory=lambda: Krea2SamplingPass(2))
    preset_id: str = "current"
    version: str = SAMPLING_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.first_pass, Krea2SamplingPass) or not isinstance(self.second_pass, Krea2SamplingPass):
            raise TypeError("Les deux passes de sampling sont requises.")
        if self.version != SAMPLING_VERSION:
            raise ValueError("Version de sampling KREA2 Assisted non prise en charge.")
        if self.preset_id == "custom":
            return
        preset = _PRESETS.get(self.preset_id)
        if preset is None or (self.first_pass, self.second_pass) != preset[1:]:
            raise ValueError("Les réglages ne correspondent pas au preset de rendu sélectionné.")


@dataclass(frozen=True, slots=True)
class Krea2AssistedSettings(Krea2BatchSettings):
    sampling: Krea2AssistedSampling = field(default_factory=Krea2AssistedSampling)
    workflow: Krea2AssistedWorkflowSelection = field(default_factory=lambda: DEFAULT_KREA2_ASSISTED_WORKFLOW)

    def __post_init__(self) -> None:
        Krea2BatchSettings.__post_init__(self)
        if not isinstance(self.sampling, Krea2AssistedSampling):
            raise TypeError("sampling must be Krea2AssistedSampling")
        if not isinstance(self.workflow, Krea2AssistedWorkflowSelection):
            raise TypeError("workflow must be Krea2AssistedWorkflowSelection")


def sampling_for(settings: Krea2BatchSettings) -> Krea2AssistedSampling:
    # Old projects and callers retain the historical 8+2 workflow.
    return settings.sampling if isinstance(settings, Krea2AssistedSettings) else Krea2AssistedSampling()


def as_batch_settings(settings: Krea2BatchSettings) -> Krea2BatchSettings:
    """Keep shared style presets and Batch publication on their existing contract."""
    if not isinstance(settings, Krea2AssistedSettings):
        return settings
    return Krea2BatchSettings(settings.model_name, settings.aspect_ratio, settings.megapixels, settings.loras)


def sampling_from_dict(
    value: dict[str, Any] | None,
    *,
    default_preset_id: str = "current",
) -> Krea2AssistedSampling:
    if value is None:
        try:
            _, first, second = _PRESETS[default_preset_id]
        except KeyError as error:
            raise ValueError("Preset de sampling KREA2 Assisted inconnu.") from error
        return Krea2AssistedSampling(first, second, preset_id=default_preset_id)
    if not isinstance(value, dict) or set(value) != {"first_pass", "second_pass", "preset_id", "version"}:
        raise ValueError("Réglages de sampling KREA2 incomplets ou inconnus.")
    passes = []
    for name in ("first_pass", "second_pass"):
        item = value[name]
        if not isinstance(item, dict) or set(item) != {"steps", "sampler", "scheduler"}:
            raise ValueError("Chaque passe doit préciser steps, sampler et scheduler.")
        passes.append(Krea2SamplingPass(**item))
    if not isinstance(value["preset_id"], str):
        raise ValueError("Identifiant de preset invalide.")
    return Krea2AssistedSampling(*passes, preset_id=value["preset_id"], version=value["version"])


def sampling_spec() -> dict[str, object]:
    return {
        "version": SAMPLING_VERSION,
        "samplers": list(SAMPLERS), "schedulers": list(SCHEDULERS),
        "steps": {"minimum": 1, "maximum": 50},
        "presets": [{"id": key, "label": label,
                     "settings": asdict(Krea2AssistedSampling(first, second, preset_id=key))}
                    for key, (label, first, second) in _PRESETS.items()],
    }
