"""Persistent state for one text-to-storyboard prompt generation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import re

from .storyboard import StoryboardSpec, storyboard_layout


_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class StoryboardRunStatus(StrEnum):
    CREATED = "created"
    GENERATING = "generating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TRUNCATED = "truncated"


@dataclass(frozen=True, slots=True)
class StoryboardRun:
    """Complete provenance and current state of one Storyboard Lab run."""

    run_id: str
    intention: str
    panel_count: int
    model_id: str
    recipe_id: str
    recipe_version: str
    template_sha256: str
    status: StoryboardRunStatus
    raw_response: str | None = None
    spec: StoryboardSpec | None = None
    compiled_prompt: str | None = None
    warnings: tuple[str, ...] = ()
    error: str | None = None

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        intention: str,
        panel_count: int,
        model_id: str,
        recipe_id: str,
        recipe_version: str,
        template_sha256: str,
    ) -> StoryboardRun:
        return cls(
            run_id=run_id,
            intention=intention,
            panel_count=panel_count,
            model_id=model_id,
            recipe_id=recipe_id,
            recipe_version=recipe_version,
            template_sha256=template_sha256,
            status=StoryboardRunStatus.CREATED,
        )

    def start(self) -> StoryboardRun:
        self._require_status(StoryboardRunStatus.CREATED, "start")
        return replace(self, status=StoryboardRunStatus.GENERATING)

    def succeed(
        self,
        *,
        raw_response: str,
        spec: StoryboardSpec,
        compiled_prompt: str,
        warnings: tuple[str, ...] = (),
    ) -> StoryboardRun:
        self._require_status(StoryboardRunStatus.GENERATING, "succeed")
        return replace(
            self,
            status=StoryboardRunStatus.SUCCEEDED,
            raw_response=_require_text(raw_response, "raw_response"),
            spec=spec,
            compiled_prompt=_require_text(compiled_prompt, "compiled_prompt"),
            warnings=warnings,
        )

    def fail(
        self,
        error: str,
        *,
        raw_response: str | None = None,
        warnings: tuple[str, ...] = (),
    ) -> StoryboardRun:
        if self.status not in {
            StoryboardRunStatus.CREATED,
            StoryboardRunStatus.GENERATING,
        }:
            raise ValueError(f"cannot fail a {self.status.value} run")
        return replace(
            self,
            status=StoryboardRunStatus.FAILED,
            raw_response=_require_optional_string(raw_response, "raw_response"),
            warnings=warnings,
            error=_require_text(error, "error"),
        )

    def truncate(
        self,
        raw_response: str,
        *,
        error: str = "The model response was truncated.",
    ) -> StoryboardRun:
        self._require_status(StoryboardRunStatus.GENERATING, "truncate")
        return replace(
            self,
            status=StoryboardRunStatus.TRUNCATED,
            raw_response=_require_optional_string(raw_response, "raw_response"),
            error=_require_text(error, "error"),
        )

    def __post_init__(self) -> None:
        for value, name in (
            (self.run_id, "run_id"),
            (self.intention, "intention"),
            (self.model_id, "model_id"),
            (self.recipe_id, "recipe_id"),
            (self.recipe_version, "recipe_version"),
        ):
            _require_text(value, name)
        storyboard_layout(self.panel_count)
        if (
            not isinstance(self.template_sha256, str)
            or _SHA256_PATTERN.fullmatch(self.template_sha256) is None
        ):
            raise ValueError("template_sha256 must be 64 lowercase hexadecimal characters")
        if not isinstance(self.status, StoryboardRunStatus):
            raise TypeError("status must be a StoryboardRunStatus")
        _require_optional_string(self.raw_response, "raw_response")
        if self.spec is not None and not isinstance(self.spec, StoryboardSpec):
            raise TypeError("spec must be a StoryboardSpec")
        if self.compiled_prompt is not None:
            _require_text(self.compiled_prompt, "compiled_prompt")
        _require_warnings(self.warnings)
        if self.error is not None:
            _require_text(self.error, "error")
        self._validate_state()

    def _validate_state(self) -> None:
        if self.status in {StoryboardRunStatus.CREATED, StoryboardRunStatus.GENERATING}:
            if any(
                value is not None
                for value in (
                    self.raw_response,
                    self.spec,
                    self.compiled_prompt,
                    self.error,
                )
            ) or self.warnings:
                raise ValueError(f"{self.status.value} run contains result fields")
            return
        if self.status is StoryboardRunStatus.SUCCEEDED:
            if (
                self.raw_response is None
                or self.spec is None
                or self.compiled_prompt is None
                or self.error is not None
            ):
                raise ValueError("succeeded run requires raw response, spec and prompt")
            if len(self.spec.panels) != self.panel_count:
                raise ValueError("succeeded run spec does not match panel_count")
            return
        if self.status is StoryboardRunStatus.FAILED:
            if self.spec is not None or self.compiled_prompt is not None or self.error is None:
                raise ValueError("failed run requires only its draft and error")
            return
        if self.spec is not None or self.compiled_prompt is not None or self.error is None:
            raise ValueError("truncated run requires only its raw draft and error")

    def _require_status(self, expected: StoryboardRunStatus, action: str) -> None:
        if self.status is not expected:
            raise ValueError(f"cannot {action} a {self.status.value} run")


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _require_optional_string(value: object, name: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise TypeError(f"{name} must be a string or None")
    return value


def _require_warnings(value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError("warnings must be a tuple")
    for warning in value:
        _require_text(warning, "warnings item")
    return value
