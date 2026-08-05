"""Application-facing adapter for a validated change-view preset."""

from __future__ import annotations

from dataclasses import dataclass

from panelforge.domain import (
    ControlKind,
    ControlSpec,
    PromptPolicy,
    RecipeRef,
    VariationMethod,
    VariationPolicy,
)
from panelforge.domain.character import (
    OPERATION_ID,
    CameraAzimuth,
    CameraElevation,
    ChangeView,
    ShotSize,
)

from .change_view import build_change_view_workflow, render_change_view_prompt
from .change_view_manifest import (
    MULTIPLE_ANGLES_LORA_STRENGTH,
    PresetValidationError,
    ValidatedChangeViewPreset,
)


DEFAULT_CHANGE_VIEW_SEED = 151020854543467


@dataclass(frozen=True, slots=True)
class ChangeViewPresetRecipe:
    """Hide workflow bindings behind semantic application controls."""

    preset: ValidatedChangeViewPreset

    def __post_init__(self) -> None:
        if MULTIPLE_ANGLES_LORA_STRENGTH not in self.preset.controls:
            raise PresetValidationError(
                "change-view Lab requires a preset with the LoRA strength control"
            )
        output = self.preset.bindings["output_image"]
        if output.history_field is None:
            raise PresetValidationError("output image binding has no history field")

    @property
    def reference(self) -> RecipeRef:
        return RecipeRef(
            operation_id=OPERATION_ID,
            recipe_id=self.preset.recipe_id,
            version=self.preset.version,
            workflow_sha256=self.preset.workflow_sha256,
        )

    @property
    def prompt_policy(self) -> PromptPolicy:
        return PromptPolicy.LOCKED

    @property
    def negative_prompt(self) -> str:
        return self.preset.negative_prompt

    @property
    def output_node_id(self) -> str:
        return self.preset.bindings["output_image"].node_id

    @property
    def output_history_field(self) -> str:
        value = self.preset.bindings["output_image"].history_field
        if value is None:
            raise PresetValidationError("output image binding has no history field")
        return value

    @property
    def variation_policy(self) -> VariationPolicy:
        lora = self.preset.controls[MULTIPLE_ANGLES_LORA_STRENGTH]
        return VariationPolicy(
            method_order=(
                VariationMethod.SEMANTIC,
                VariationMethod.LORA_STRENGTH,
                VariationMethod.SEED,
            ),
            controls=(
                ControlSpec(
                    control_id="azimuth",
                    label="Angle horizontal",
                    kind=ControlKind.CHOICE,
                    method=VariationMethod.SEMANTIC,
                    default=CameraAzimuth.FRONT.value,
                    options=tuple(value.value for value in CameraAzimuth),
                ),
                ControlSpec(
                    control_id="elevation",
                    label="Hauteur de caméra",
                    kind=ControlKind.CHOICE,
                    method=VariationMethod.SEMANTIC,
                    default=CameraElevation.EYE_LEVEL.value,
                    options=tuple(value.value for value in CameraElevation),
                ),
                ControlSpec(
                    control_id="shot_size",
                    label="Cadrage",
                    kind=ControlKind.CHOICE,
                    method=VariationMethod.SEMANTIC,
                    default=ShotSize.MEDIUM.value,
                    options=tuple(value.value for value in ShotSize),
                ),
                ControlSpec(
                    control_id=MULTIPLE_ANGLES_LORA_STRENGTH,
                    label="Force de la LoRA d'angle",
                    kind=ControlKind.FLOAT,
                    method=VariationMethod.LORA_STRENGTH,
                    default=lora.default,
                    minimum=lora.minimum,
                    maximum=lora.maximum,
                    step=lora.step,
                ),
                ControlSpec(
                    control_id="seed",
                    label="Seed",
                    kind=ControlKind.INTEGER,
                    method=VariationMethod.SEED,
                    default=DEFAULT_CHANGE_VIEW_SEED,
                    minimum=0,
                    maximum=2**64 - 1,
                    step=1,
                    advanced=True,
                ),
            ),
        )

    def render_prompt(self, change: ChangeView) -> str:
        return render_change_view_prompt(change, self.preset)

    def build_workflow(
        self,
        change: ChangeView,
        *,
        source_image: str,
        seed: int,
        lora_strength: float,
    ) -> dict[str, object]:
        return build_change_view_workflow(
            change,
            self.preset,
            source_image=source_image,
            seed=seed,
            multiple_angles_lora_strength=lora_strength,
        )

    def is_experimental_lora_override(self, value: float) -> bool:
        control = self.preset.controls[MULTIPLE_ANGLES_LORA_STRENGTH]
        return control.is_experimental_override(value)
