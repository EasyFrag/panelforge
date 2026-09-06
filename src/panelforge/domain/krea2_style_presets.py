"""Immutable named style examples, independent from published Batch recipes."""

from dataclasses import dataclass
from .krea2_batch import Krea2BatchSettings, Krea2PromptLanguage


@dataclass(frozen=True, slots=True)
class Krea2StylePreset:
    preset_id: str
    revision: int
    name: str
    prompt: str
    image_asset_id: str
    settings: Krea2BatchSettings
    source_project_id: str
    source_attempt_id: str
    source_seed: int
    prompt_language: Krea2PromptLanguage = Krea2PromptLanguage.ENGLISH

    def __post_init__(self):
        for field, limit in (("preset_id", 128), ("name", 120), ("prompt", 40000),
                             ("image_asset_id", 128), ("source_project_id", 128), ("source_attempt_id", 128)):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError(f"invalid style preset {field}")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
            raise ValueError("invalid preset revision")
        if not isinstance(self.settings, Krea2BatchSettings):
            raise TypeError("preset settings must be Krea2BatchSettings")
        if not isinstance(self.prompt_language, Krea2PromptLanguage):
            raise TypeError("invalid preset prompt language")
        if isinstance(self.source_seed, bool) or not isinstance(self.source_seed, int) or not 0 <= self.source_seed <= 2**50:
            raise ValueError("invalid preset source seed")


def validate_preset_selection(preset, pending):
    if preset is not None and not isinstance(preset, Krea2StylePreset):
        raise TypeError("style_preset must be Krea2StylePreset")
    if not isinstance(pending, bool) or (pending and preset is None):
        raise ValueError("pending preset requires a preset")
