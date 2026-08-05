"""Pure contracts exposed by curated generation recipes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
import re
from typing import TypeAlias


_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")

ScalarValue: TypeAlias = str | int | float | bool


class PromptPolicy(StrEnum):
    """How much of a compiled prompt a later variation may rewrite."""

    LOCKED = "locked"
    PROTECTED = "protected"
    MUTABLE = "mutable"


class VariationMethod(StrEnum):
    """Recipe-specific mechanisms, ordered by expected usefulness."""

    SEMANTIC = "semantic"
    PROMPT_JITTER = "prompt_jitter"
    LORA_STRENGTH = "lora_strength"
    SEED = "seed"


class ControlKind(StrEnum):
    """Small set of controls needed by the first Lab interface."""

    CHOICE = "choice"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"


@dataclass(frozen=True, slots=True)
class RecipeRef:
    """Stable identity and executable-source fingerprint of one recipe."""

    operation_id: str
    recipe_id: str
    version: str
    workflow_sha256: str

    def __post_init__(self) -> None:
        _require_text(self.operation_id, "operation_id")
        _require_text(self.recipe_id, "recipe_id")
        _require_text(self.version, "version")
        _require_sha256(self.workflow_sha256, "workflow_sha256")


@dataclass(frozen=True, slots=True)
class PromptSnapshot:
    """The exact prompts executed by a run, plus their rewrite boundary."""

    positive: str
    negative: str
    policy: PromptPolicy
    protected_fragments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.positive, "positive")
        if not isinstance(self.negative, str):
            raise TypeError("negative must be a string")
        if not isinstance(self.policy, PromptPolicy):
            raise TypeError("policy must be a PromptPolicy")
        _require_tuple(self.protected_fragments, "protected_fragments")

        seen: set[str] = set()
        for fragment in self.protected_fragments:
            _require_text(fragment, "protected_fragments item")
            if fragment in seen:
                raise ValueError("protected_fragments must not contain duplicates")
            if fragment not in self.positive:
                raise ValueError(
                    "each protected fragment must occur in the positive prompt"
                )
            seen.add(fragment)

        if self.policy is PromptPolicy.PROTECTED and not self.protected_fragments:
            raise ValueError("protected policy requires at least one protected fragment")
        if self.policy is PromptPolicy.MUTABLE and self.protected_fragments:
            raise ValueError("mutable policy cannot define protected fragments")


@dataclass(frozen=True, slots=True)
class ControlSpec:
    """A curated, renderable recipe control and its validated range."""

    control_id: str
    label: str
    kind: ControlKind
    method: VariationMethod
    default: ScalarValue
    options: tuple[ScalarValue, ...] = ()
    minimum: int | float | None = None
    maximum: int | float | None = None
    step: int | float | None = None
    advanced: bool = False

    def __post_init__(self) -> None:
        _require_text(self.control_id, "control_id")
        _require_text(self.label, "label")
        if not isinstance(self.kind, ControlKind):
            raise TypeError("kind must be a ControlKind")
        if not isinstance(self.method, VariationMethod):
            raise TypeError("method must be a VariationMethod")
        _require_tuple(self.options, "options")
        if not isinstance(self.advanced, bool):
            raise TypeError("advanced must be a boolean")

        if self.kind is ControlKind.CHOICE:
            self._validate_choice_shape()
        elif self.kind is ControlKind.INTEGER:
            self._validate_integer_shape()
        elif self.kind is ControlKind.FLOAT:
            self._validate_float_shape()
        else:
            self._validate_boolean_shape()
        self.validate_value(self.default)

    def validate_value(self, value: ScalarValue) -> None:
        """Reject a runtime value that is outside this declared control."""
        if self.kind is ControlKind.CHOICE:
            if not any(_same_scalar(value, option) for option in self.options):
                raise ValueError(
                    f"{self.control_id} must be one of the declared options"
                )
            return
        if self.kind is ControlKind.INTEGER:
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{self.control_id} must be an integer")
            self._validate_bounds(value)
            return
        if self.kind is ControlKind.FLOAT:
            if not _is_finite_number(value):
                raise TypeError(f"{self.control_id} must be a finite number")
            self._validate_bounds(value)
            return
        if not isinstance(value, bool):
            raise TypeError(f"{self.control_id} must be a boolean")

    def _validate_choice_shape(self) -> None:
        if not self.options:
            raise ValueError("choice controls require options")
        if any(value is not None for value in (self.minimum, self.maximum, self.step)):
            raise ValueError("choice controls cannot define a numeric range")
        for option in self.options:
            _require_scalar(option, "option")
        for index, option in enumerate(self.options):
            if any(_same_scalar(option, prior) for prior in self.options[:index]):
                raise ValueError("choice options must not contain duplicates")

    def _validate_integer_shape(self) -> None:
        if self.options:
            raise ValueError("integer controls cannot define options")
        for value, name in (
            (self.minimum, "minimum"),
            (self.maximum, "maximum"),
            (self.step, "step"),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int)
            ):
                raise TypeError(f"{name} must be an integer for an integer control")
        self._validate_range_shape()

    def _validate_float_shape(self) -> None:
        if self.options:
            raise ValueError("float controls cannot define options")
        for value, name in (
            (self.minimum, "minimum"),
            (self.maximum, "maximum"),
            (self.step, "step"),
        ):
            if value is not None and not _is_finite_number(value):
                raise TypeError(f"{name} must be a finite number")
        self._validate_range_shape()

    def _validate_boolean_shape(self) -> None:
        if self.options or any(
            value is not None for value in (self.minimum, self.maximum, self.step)
        ):
            raise ValueError("boolean controls cannot define options or a range")

    def _validate_range_shape(self) -> None:
        if self.minimum is None or self.maximum is None:
            raise ValueError("numeric controls require minimum and maximum")
        if self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")
        if self.step is None or self.step <= 0:
            raise ValueError("numeric controls require a positive step")

    def _validate_bounds(self, value: int | float) -> None:
        if self.minimum is not None and value < self.minimum:
            raise ValueError(f"{self.control_id} is below its minimum")
        if self.maximum is not None and value > self.maximum:
            raise ValueError(f"{self.control_id} is above its maximum")


@dataclass(frozen=True, slots=True)
class ControlValue:
    """One concrete control value recorded in a run."""

    control_id: str
    value: ScalarValue

    def __post_init__(self) -> None:
        _require_text(self.control_id, "control_id")
        _require_scalar(self.value, "value")


@dataclass(frozen=True, slots=True)
class VariationPolicy:
    """Ordered variation methods and the controls exposed by one recipe."""

    method_order: tuple[VariationMethod, ...]
    controls: tuple[ControlSpec, ...]

    def __post_init__(self) -> None:
        _require_tuple(self.method_order, "method_order")
        _require_tuple(self.controls, "controls")
        if not self.method_order:
            raise ValueError("method_order must not be empty")
        if len(set(self.method_order)) != len(self.method_order):
            raise ValueError("method_order must not contain duplicates")
        if any(not isinstance(method, VariationMethod) for method in self.method_order):
            raise TypeError("method_order items must be VariationMethod values")

        control_ids: set[str] = set()
        for control in self.controls:
            if not isinstance(control, ControlSpec):
                raise TypeError("controls items must be ControlSpec values")
            if control.control_id in control_ids:
                raise ValueError("controls must have unique control_id values")
            if control.method not in self.method_order:
                raise ValueError(
                    f"control method {control.method.value!r} is absent from method_order"
                )
            control_ids.add(control.control_id)

    def validate_values(
        self,
        values: tuple[ControlValue, ...],
    ) -> tuple[ControlValue, ...]:
        """Validate overrides and return every control in declaration order.

        Missing values receive their declared default so a run always records the
        complete effective configuration rather than only UI overrides.
        """
        _require_tuple(values, "values")
        by_id: dict[str, ControlValue] = {}
        specs = {control.control_id: control for control in self.controls}
        for value in values:
            if not isinstance(value, ControlValue):
                raise TypeError("values items must be ControlValue values")
            if value.control_id in by_id:
                raise ValueError(f"duplicate control value {value.control_id!r}")
            if value.control_id not in specs:
                raise ValueError(f"unknown control value {value.control_id!r}")
            specs[value.control_id].validate_value(value.value)
            by_id[value.control_id] = value

        return tuple(
            by_id.get(
                spec.control_id,
                ControlValue(control_id=spec.control_id, value=spec.default),
            )
            for spec in self.controls
        )


def _same_scalar(left: ScalarValue, right: ScalarValue) -> bool:
    return type(left) is type(right) and left == right


def _is_finite_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    )


def _require_scalar(value: object, name: str) -> ScalarValue:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if not isinstance(value, (str, int, float, bool)):
        raise TypeError(f"{name} must be a scalar value")
    return value


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _require_tuple(value: object, name: str) -> tuple[object, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    return value


def _require_sha256(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return value
