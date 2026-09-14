"""Ports shared by the rendering engines in the iterative image workshop."""

from typing import Protocol

from panelforge.domain.edit_settings import EditSettings
from panelforge.domain.recipes import RecipeRef


class EditWorkflow(Protocol):
    reference: RecipeRef
    engine: str
    status: str
    display_name: str
    output_node_id: str
    output_history_field: str
    output_media_type: str

    @property
    def defaults(self) -> dict[str, object]: ...

    def build(self, *, source_image: str, prompt: str, settings: EditSettings,
              output_prefix: str, sidecar_text: str) -> dict: ...


class EditImages(Protocol):
    def normalize_source(self, content: bytes) -> bytes: ...
    def dimensions(self, content: bytes) -> tuple[int, int]: ...
    def crop(self, content: bytes, *, x: int, y: int, width: int, height: int) -> bytes: ...
