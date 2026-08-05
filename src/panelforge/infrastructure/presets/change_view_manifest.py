"""Load and validate the Qwen Multiple Angles recipe bundle."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from panelforge.domain.character import OPERATION_ID


JsonObject = dict[str, Any]
RECIPE_ID = "qwen-edit-2511-multiple-angles"
PROMPT_TEMPLATE = "<sks> {azimuth} {elevation} {shot_size}"
MULTIPLE_ANGLES_LORA_STRENGTH = "multiple_angles_lora_strength"

_OFFICIAL_PHRASES = {
    "azimuth": {
        "front": "front view",
        "front_right_quarter": "front-right quarter view",
        "right_side": "right side view",
        "back_right_quarter": "back-right quarter view",
        "back": "back view",
        "back_left_quarter": "back-left quarter view",
        "left_side": "left side view",
        "front_left_quarter": "front-left quarter view",
    },
    "elevation": {
        "low": "low-angle shot",
        "eye_level": "eye-level shot",
        "elevated": "elevated shot",
        "high": "high-angle shot",
    },
    "shot_size": {
        "close_up": "close-up",
        "medium": "medium shot",
        "wide": "wide shot",
    },
}

_REQUIRED_ASSERTION_IDS = {
    "unet",
    "clip",
    "clip_type",
    "vae",
    "lightning_lora",
    "multiple_angles_lora",
    "steps",
    "cfg",
    "sampler",
    "scheduler",
    "denoise",
    "sampling_shift",
    "cfg_norm_strength",
    "cfg_norm_pre_cfg",
    "negative_reference_method",
    "positive_reference_method",
}


class PresetValidationError(ValueError):
    """Raised when a versioned recipe and its workflow disagree."""


@dataclass(frozen=True, slots=True)
class WorkflowBinding:
    node_id: str
    input_name: str | None = None
    history_field: str | None = None


@dataclass(frozen=True, slots=True)
class NumericWorkflowControl:
    """One manifest-declared numeric override of a workflow assertion value."""

    control_id: str
    workflow_assertion_id: str
    node_id: str
    input_name: str
    value_path: tuple[str, ...]
    minimum: float
    maximum: float
    step: float
    default: float
    validated_values: tuple[float, ...]

    def validate_value(self, value: Any) -> float:
        """Return a finite in-range step value, rejecting bools as numbers."""
        number = _require_finite_number(value, self.control_id)
        if not self.minimum <= number <= self.maximum:
            raise ValueError(
                f"{self.control_id} must be between {self.minimum} and "
                f"{self.maximum}"
            )
        step_position = (number - self.minimum) / self.step
        if not math.isclose(
            step_position,
            round(step_position),
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                f"{self.control_id} must use increments of {self.step}"
            )
        return number

    def is_experimental_override(self, value: Any) -> bool:
        """Whether a valid value is outside this recipe's qualified values."""
        number = self.validate_value(value)
        return not any(
            math.isclose(number, validated, rel_tol=0.0, abs_tol=1e-12)
            for validated in self.validated_values
        )


@dataclass(frozen=True, slots=True)
class ValidatedChangeViewPreset:
    recipe_id: str
    version: str
    prompt_template: str
    negative_prompt: str
    azimuth_phrases: Mapping[str, str]
    elevation_phrases: Mapping[str, str]
    shot_size_phrases: Mapping[str, str]
    bindings: Mapping[str, WorkflowBinding]
    controls: Mapping[str, NumericWorkflowControl]
    workflow_sha256: str
    _workflow_json: bytes = field(repr=False)

    @property
    def workflow(self) -> JsonObject:
        """Return a fresh workflow so one run cannot contaminate another."""
        value = json.loads(self._workflow_json)
        if not isinstance(value, dict):
            raise PresetValidationError("stored workflow must be an object")
        return value


def load_change_view_preset(directory: Path) -> ValidatedChangeViewPreset:
    """Load and validate one immutable recipe directory."""
    manifest = _read_json_object(directory / "manifest.json")
    workflow_config = _require_mapping(manifest.get("workflow"), "workflow")
    workflow_filename = _require_string(workflow_config.get("file"), "workflow.file")
    expected_hash = _require_string(
        workflow_config.get("sha256"), "workflow.sha256"
    ).lower()

    workflow_path = directory / workflow_filename
    workflow_content = workflow_path.read_bytes()
    actual_hash = hashlib.sha256(workflow_content).hexdigest()
    if actual_hash != expected_hash:
        raise PresetValidationError(
            f"workflow hash mismatch: expected {expected_hash}, got {actual_hash}"
        )
    workflow = _decode_json_object(workflow_content, str(workflow_path))

    prompt_config = _require_mapping(manifest.get("prompt"), "prompt")
    prompt_filename = _require_string(
        prompt_config.get("template_file"), "prompt.template_file"
    )
    expected_prompt_hash = _require_string(
        prompt_config.get("sha256"), "prompt.sha256"
    ).lower()
    prompt_content = (directory / prompt_filename).read_bytes()
    actual_prompt_hash = hashlib.sha256(prompt_content).hexdigest()
    if actual_prompt_hash != expected_prompt_hash:
        raise PresetValidationError(
            "prompt template hash mismatch: "
            f"expected {expected_prompt_hash}, got {actual_prompt_hash}"
        )
    try:
        prompt_template = prompt_content.decode("utf-8").rstrip("\r\n")
    except UnicodeDecodeError as error:
        raise PresetValidationError("prompt template must be UTF-8") from error

    return validate_change_view_preset(
        manifest,
        workflow,
        prompt_template,
        workflow_sha256=actual_hash,
    )


def validate_change_view_preset(
    manifest: Mapping[str, Any],
    workflow: Mapping[str, Any],
    prompt_template: str,
    *,
    workflow_sha256: str = "",
) -> ValidatedChangeViewPreset:
    """Validate this LoRA's grammar, bindings and fixed workflow values."""
    if manifest.get("schema_version") != 1:
        raise PresetValidationError("schema_version must be 1")
    if manifest.get("operation") != OPERATION_ID:
        raise PresetValidationError(f"operation must be {OPERATION_ID!r}")
    if manifest.get("recipe_id") != RECIPE_ID:
        raise PresetValidationError(f"recipe_id must be {RECIPE_ID!r}")
    version = _require_string(manifest.get("version"), "version")
    prompt_config = _require_mapping(manifest.get("prompt"), "prompt")
    if prompt_config.get("rewriter_policy") != "forbidden":
        raise PresetValidationError("prompt.rewriter_policy must be 'forbidden'")
    if prompt_template != PROMPT_TEMPLATE:
        raise PresetValidationError(f"prompt template must be exactly {PROMPT_TEMPLATE!r}")
    negative_prompt = prompt_config.get("negative")
    if not isinstance(negative_prompt, str):
        raise PresetValidationError("prompt.negative must be a string")

    phrases = _require_mapping(prompt_config.get("phrases"), "prompt.phrases")
    validated_phrases = {
        name: _validate_phrases(phrases.get(name), expected, name)
        for name, expected in _OFFICIAL_PHRASES.items()
    }

    workflow_nodes = _require_mapping(workflow, "workflow JSON")
    if not workflow_nodes:
        raise PresetValidationError("workflow JSON must not be empty")
    bindings = _validate_bindings(manifest.get("bindings"), workflow_nodes)
    assertions = _validate_workflow_assertions(
        manifest.get("workflow_assertions"), workflow_nodes
    )
    controls = _validate_controls(manifest.get("controls"), assertions)

    serialized_workflow = json.dumps(
        workflow_nodes,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    return ValidatedChangeViewPreset(
        recipe_id=RECIPE_ID,
        version=version,
        prompt_template=prompt_template,
        negative_prompt=negative_prompt,
        azimuth_phrases=MappingProxyType(validated_phrases["azimuth"]),
        elevation_phrases=MappingProxyType(validated_phrases["elevation"]),
        shot_size_phrases=MappingProxyType(validated_phrases["shot_size"]),
        bindings=MappingProxyType(bindings),
        controls=MappingProxyType(controls),
        workflow_sha256=workflow_sha256,
        _workflow_json=serialized_workflow,
    )


def _validate_phrases(
    value: Any,
    expected: Mapping[str, str],
    name: str,
) -> dict[str, str]:
    label = f"prompt.phrases.{name}"
    phrases = _require_mapping(value, label)
    result = {
        str(key): _require_string(phrase, f"{label}.{key}")
        for key, phrase in phrases.items()
    }
    if result != expected:
        raise PresetValidationError(f"{label} must match the official LoRA vocabulary")
    return result


def _validate_bindings(
    value: Any,
    workflow: Mapping[str, Any],
) -> dict[str, WorkflowBinding]:
    raw_bindings = _require_mapping(value, "bindings")
    required_inputs = {
        "source_image",
        "positive_prompt",
        "negative_prompt",
        "seed",
    }
    required_bindings = required_inputs | {"output_image"}
    if set(raw_bindings) != required_bindings:
        raise PresetValidationError(
            f"bindings must define exactly {sorted(required_bindings)!r}"
        )

    result: dict[str, WorkflowBinding] = {}
    for binding_name, raw_binding in raw_bindings.items():
        binding = _require_mapping(raw_binding, f"bindings.{binding_name}")
        node_id = _require_string(
            binding.get("node_id"), f"bindings.{binding_name}.node_id"
        )
        node = _require_mapping(
            workflow.get(node_id), f"workflow node {node_id}"
        )
        if binding_name == "output_image":
            if node.get("class_type") != "SaveImage":
                raise PresetValidationError("output_image node must be a SaveImage")
            history_field = _require_string(
                binding.get("history_field"),
                "bindings.output_image.history_field",
            )
            result[binding_name] = WorkflowBinding(
                node_id=node_id,
                history_field=history_field,
            )
            continue

        input_name = _require_string(
            binding.get("input"), f"bindings.{binding_name}.input"
        )
        inputs = _require_mapping(node.get("inputs"), f"workflow node {node_id}.inputs")
        if input_name not in inputs:
            raise PresetValidationError(
                f"workflow node {node_id} has no input {input_name!r}"
            )
        result[binding_name] = WorkflowBinding(
            node_id=node_id,
            input_name=input_name,
        )
    return result


def _validate_workflow_assertions(
    value: Any,
    workflow: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    if not isinstance(value, list) or not value:
        raise PresetValidationError("workflow_assertions must be a non-empty list")

    seen_ids: set[str] = set()
    for index, raw_assertion in enumerate(value):
        label = f"workflow_assertions[{index}]"
        assertion = _require_mapping(raw_assertion, label)
        assertion_id = _require_string(assertion.get("id"), f"{label}.id")
        if assertion_id in seen_ids:
            raise PresetValidationError(
                f"duplicate workflow assertion id {assertion_id!r}"
            )
        seen_ids.add(assertion_id)
        node_id = _require_string(assertion.get("node_id"), f"{label}.node_id")
        input_name = _require_string(assertion.get("input"), f"{label}.input")
        if "equals" not in assertion:
            raise PresetValidationError(f"{label}.equals is required")
        node = _require_mapping(workflow.get(node_id), f"workflow node {node_id}")
        inputs = _require_mapping(node.get("inputs"), f"workflow node {node_id}.inputs")
        if input_name not in inputs:
            raise PresetValidationError(
                f"workflow node {node_id} has no input {input_name!r}"
            )
        actual = inputs[input_name]
        expected = assertion["equals"]
        if actual != expected:
            raise PresetValidationError(
                f"{assertion_id} expected node {node_id}.{input_name}={expected!r}, "
                f"got {actual!r}"
            )

    missing = _REQUIRED_ASSERTION_IDS - seen_ids
    if missing:
        raise PresetValidationError(
            f"missing required workflow assertions: {sorted(missing)!r}"
        )
    return {
        _require_string(assertion.get("id"), "workflow assertion id"): assertion
        for assertion in value
    }


def _validate_controls(
    value: Any,
    assertions: Mapping[str, Mapping[str, Any]],
) -> dict[str, NumericWorkflowControl]:
    if value is None:
        return {}
    raw_controls = _require_mapping(value, "controls")
    unsupported = set(raw_controls) - {MULTIPLE_ANGLES_LORA_STRENGTH}
    if unsupported:
        raise PresetValidationError(
            f"unsupported controls: {sorted(unsupported)!r}"
        )

    result: dict[str, NumericWorkflowControl] = {}
    for control_id, raw_control in raw_controls.items():
        label = f"controls.{control_id}"
        control = _require_mapping(raw_control, label)
        if control.get("type") != "number":
            raise PresetValidationError(f"{label}.type must be 'number'")

        target = _require_mapping(control.get("target"), f"{label}.target")
        assertion_id = _require_string(
            target.get("workflow_assertion_id"),
            f"{label}.target.workflow_assertion_id",
        )
        if control_id == MULTIPLE_ANGLES_LORA_STRENGTH:
            if assertion_id != "multiple_angles_lora":
                raise PresetValidationError(
                    f"{label} must target workflow assertion 'multiple_angles_lora'"
                )
        assertion = assertions.get(assertion_id)
        if assertion is None:
            raise PresetValidationError(
                f"{label} targets unknown workflow assertion {assertion_id!r}"
            )

        raw_path = target.get("value_path")
        if not isinstance(raw_path, list) or not raw_path:
            raise PresetValidationError(
                f"{label}.target.value_path must be a non-empty list"
            )
        value_path = tuple(
            _require_string(part, f"{label}.target.value_path[{index}]")
            for index, part in enumerate(raw_path)
        )
        if control_id == MULTIPLE_ANGLES_LORA_STRENGTH and value_path != (
            "strength",
        ):
            raise PresetValidationError(
                f"{label} value_path must be exactly ['strength']"
            )

        minimum = _preset_number(control.get("minimum"), f"{label}.minimum")
        maximum = _preset_number(control.get("maximum"), f"{label}.maximum")
        step = _preset_number(control.get("step"), f"{label}.step")
        default = _preset_number(control.get("default"), f"{label}.default")
        if minimum >= maximum:
            raise PresetValidationError(f"{label}.minimum must be below maximum")
        if step <= 0:
            raise PresetValidationError(f"{label}.step must be positive")

        raw_validated_values = control.get("validated_values")
        if not isinstance(raw_validated_values, list) or not raw_validated_values:
            raise PresetValidationError(
                f"{label}.validated_values must be a non-empty list"
            )
        validated_values = tuple(
            _preset_number(item, f"{label}.validated_values[{index}]")
            for index, item in enumerate(raw_validated_values)
        )
        if len(set(validated_values)) != len(validated_values):
            raise PresetValidationError(
                f"{label}.validated_values must not contain duplicates"
            )

        numeric_control = NumericWorkflowControl(
            control_id=control_id,
            workflow_assertion_id=assertion_id,
            node_id=_require_string(assertion.get("node_id"), f"{label}.node_id"),
            input_name=_require_string(assertion.get("input"), f"{label}.input"),
            value_path=value_path,
            minimum=minimum,
            maximum=maximum,
            step=step,
            default=default,
            validated_values=validated_values,
        )
        try:
            numeric_control.validate_value(default)
            for validated_value in validated_values:
                numeric_control.validate_value(validated_value)
        except ValueError as error:
            raise PresetValidationError(str(error)) from error
        if numeric_control.is_experimental_override(default):
            raise PresetValidationError(
                f"{label}.default must be one of validated_values"
            )

        asserted_value = _resolve_value_path(
            assertion.get("equals"),
            value_path,
            f"workflow assertion {assertion_id!r}",
        )
        try:
            asserted_number = numeric_control.validate_value(asserted_value)
        except ValueError as error:
            raise PresetValidationError(str(error)) from error
        if not math.isclose(
            asserted_number,
            default,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise PresetValidationError(
                f"{label}.default must equal the asserted workflow value"
            )
        result[control_id] = numeric_control
    return result


def _resolve_value_path(value: Any, path: tuple[str, ...], label: str) -> Any:
    current = value
    for part in path:
        mapping = _require_mapping(current, label)
        if part not in mapping:
            raise PresetValidationError(f"{label} has no value_path part {part!r}")
        current = mapping[part]
    return current


def _read_json_object(path: Path) -> JsonObject:
    return _decode_json_object(path.read_bytes(), str(path))


def _decode_json_object(content: bytes, label: str) -> JsonObject:
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PresetValidationError(f"invalid JSON in {label}: {error}") from error
    if not isinstance(value, dict):
        raise PresetValidationError(f"{label} must contain a JSON object")
    return value


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PresetValidationError(f"{label} must be an object")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PresetValidationError(f"{label} must be a non-empty string")
    return value


def _require_finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError(f"{label} must be finite") from error
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def _preset_number(value: Any, label: str) -> float:
    try:
        return _require_finite_number(value, label)
    except ValueError as error:
        raise PresetValidationError(str(error)) from error
