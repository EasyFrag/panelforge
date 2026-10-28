"""Explicit contracts for CSV-driven assisted image creation."""
from dataclasses import dataclass
from enum import StrEnum

from .krea2_art_direction import Krea2ArtDirection
from .krea2_assisted_workflows import DEFAULT_KREA2_ASSISTED_WORKFLOW, KREA2_FLUX_KLEIN_WORKFLOW
from .krea2_batch import Krea2BatchSettings, Krea2PromptLanguage
from .krea2_sampling import Krea2AssistedSettings
from .krea2_style_presets import Krea2StylePreset

MAX_BATCH_ITEMS = 500
MAX_CSV_BYTES = 8 * 1024 * 1024
TERMINAL_IMAGE_STATES = frozenset({"succeeded", "failed", "cancelled"})


class CreationBatchRenderMode(StrEnum):
    TWO_PASS = "krea2-sampling"
    FLUX_KLEIN = "krea2-flux-klein"

    @property
    def workflow(self):
        return DEFAULT_KREA2_ASSISTED_WORKFLOW if self is CreationBatchRenderMode.TWO_PASS else KREA2_FLUX_KLEIN_WORKFLOW

    @classmethod
    def from_settings(cls, settings: Krea2BatchSettings):
        # Historical settings without a workflow use the original two-pass family.
        workflow = settings.workflow if isinstance(settings, Krea2AssistedSettings) else DEFAULT_KREA2_ASSISTED_WORKFLOW
        return cls(workflow.recipe_id)


@dataclass(frozen=True, slots=True)
class CreationIntent:
    name: str
    intention: str

    def __post_init__(self):
        for field, limit in (("name", 120), ("intention", 12000)):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
                raise ValueError(f"{field} doit contenir entre 1 et {limit} caractères.")


@dataclass(frozen=True, slots=True)
class CreationBatchConfig:
    model_id: str
    recipe_version: str
    language: Krea2PromptLanguage
    local_inspiration: bool
    preset: Krea2StylePreset
    settings: Krea2BatchSettings
    art_direction: Krea2ArtDirection | None = None

    @property
    def render_mode(self) -> CreationBatchRenderMode:
        return CreationBatchRenderMode.from_settings(self.settings)

    def __post_init__(self):
        if not isinstance(self.model_id, str) or not self.model_id.strip() or len(self.model_id) > 300:
            raise ValueError("Modèle LLM invalide.")
        if not isinstance(self.language, Krea2PromptLanguage) or type(self.local_inspiration) is not bool:
            raise ValueError("Langue ou option d'inspiration invalide.")
        if not isinstance(self.preset, Krea2StylePreset) or not isinstance(self.settings, Krea2BatchSettings):
            raise ValueError("Un preset et ses réglages sont requis.")
        if self.art_direction is not None and (
            not isinstance(self.art_direction, Krea2ArtDirection) or self.recipe_version != "6.0.0"
        ):
            raise ValueError("La direction artistique nécessite la recette V6.")


@dataclass(frozen=True, slots=True)
class CreationBatchRender:
    render_id: str
    label: str
    config: CreationBatchConfig
    prompt: str
    request_digest: str
    project_id: str | None = None
    attempt_id: str | None = None
    status: str = "waiting"
    error: str | None = None
    output_asset_id: str | None = None
    factory_item_id: str | None = None

    @property
    def terminal(self):
        return self.status in TERMINAL_IMAGE_STATES


@dataclass(frozen=True, slots=True)
class CreationBatchItem:
    item_id: str
    name: str
    intention: str
    project_id: str | None = None
    attempt_id: str | None = None
    prompt_status: str = "queued"
    image_status: str = "waiting"
    message: str = ""
    error: str | None = None
    output_asset_id: str | None = None
    parent_id: str | None = None
    config: CreationBatchConfig | None = None
    source_prompt: str | None = None
    request_id: str | None = None
    request_digest: str | None = None
    factory_item_id: str | None = None
    renders: tuple[CreationBatchRender, ...] = ()

    @property
    def terminal(self):
        return self.image_status in TERMINAL_IMAGE_STATES and all(r.terminal for r in self.renders)


@dataclass(frozen=True, slots=True)
class CreationBatch:
    batch_id: str
    request_digest: str
    name: str
    created_at: str
    config: CreationBatchConfig
    items: tuple[CreationBatchItem, ...]
    revision: int = 1

    @property
    def terminal(self):
        return all(item.terminal for item in self.items)
