"""One-call text-to-storyboard prompt generation."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
import logging
import math
from threading import RLock
from typing import Protocol
from uuid import uuid4

from panelforge.domain.storyboard import StoryboardSpec
from panelforge.domain.storyboard_runs import StoryboardRun, StoryboardRunStatus

from .prompt_lab import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    LlmCallApplicationOutcome,
    LlmCallApplicationOutcomeReporter,
    ModelDescriptor,
    MultimodalGateway,
    StreamEventKind,
    StreamPhase,
)


_LOGGER = logging.getLogger(__name__)


class StoryboardRecipe(Protocol):
    recipe_id: str
    version: str
    display_name: str
    description: str
    template_sha256: str
    panel_counts: tuple[int, ...]

    def build_request_prompts(
        self,
        intention: str,
        panel_count: int,
    ) -> tuple[str, str]: ...

    def parse_spec(self, raw_response: str, panel_count: int) -> StoryboardSpec: ...

    def compile_prompt(self, spec: StoryboardSpec, panel_count: int) -> str: ...

    def warnings_for_spec(
        self,
        spec: StoryboardSpec,
        panel_count: int,
    ) -> tuple[str, ...]: ...


class StoryboardRecipeCatalog(Protocol):
    def list(self) -> tuple[StoryboardRecipe, ...]: ...

    def get(self, recipe_id: str, version: str) -> StoryboardRecipe: ...


class StoryboardRunStore(Protocol):
    def create(self, run: StoryboardRun) -> StoryboardRun: ...

    def save(self, run: StoryboardRun) -> StoryboardRun: ...

    def get(self, run_id: str) -> StoryboardRun: ...

    def list(self, limit: int = 20) -> list[StoryboardRun]: ...


@dataclass(frozen=True, slots=True)
class StoryboardRunRequest:
    intention: str
    panel_count: int
    model_id: str
    recipe_id: str
    recipe_version: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.intention, "intention"),
            (self.model_id, "model_id"),
            (self.recipe_id, "recipe_id"),
            (self.recipe_version, "recipe_version"),
        ):
            _require_text(value, name)
        if isinstance(self.panel_count, bool) or not isinstance(self.panel_count, int):
            raise TypeError("panel_count must be an integer")


@dataclass(frozen=True, slots=True)
class StoryboardStreamEvent:
    kind: StreamEventKind
    phase: StreamPhase
    text: str = ""
    progress: float | None = None
    run: StoryboardRun | None = None
    finish_reason: str | None = None
    max_tokens: int | None = None


class StoryboardLabService:
    """Persist a run before making exactly one model call to fill its spec."""

    def __init__(
        self,
        *,
        gateway: MultimodalGateway,
        recipes: StoryboardRecipeCatalog,
        runs: StoryboardRunStore,
        application_outcomes: LlmCallApplicationOutcomeReporter | None = None,
        run_id_factory: Callable[[], str] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 32768,
    ) -> None:
        if (
            isinstance(temperature, bool)
            or not isinstance(temperature, (int, float))
            or not math.isfinite(temperature)
        ):
            raise ValueError("temperature must be finite")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int):
            raise TypeError("max_tokens must be an integer")
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        self.gateway = gateway
        self.recipes = recipes
        self.runs = runs
        self.application_outcomes = application_outcomes
        self._run_id_factory = run_id_factory or (
            lambda: f"storyboard-{uuid4().hex}"
        )
        self.temperature = float(temperature)
        self.max_tokens = max_tokens
        self._state_lock = RLock()

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return self.gateway.list_models()

    def list_recipes(self) -> tuple[StoryboardRecipe, ...]:
        return self.recipes.list()

    def get_recipe(self, recipe_id: str, version: str) -> StoryboardRecipe:
        return self.recipes.get(recipe_id, version)

    def get(self, run_id: str) -> StoryboardRun:
        return self.runs.get(run_id)

    def list(self, limit: int = 20) -> list[StoryboardRun]:
        return self.runs.list(limit)

    def prepare(self, request: StoryboardRunRequest) -> StoryboardRun:
        if not isinstance(request, StoryboardRunRequest):
            raise TypeError("request must be a StoryboardRunRequest")
        recipe = self.recipes.get(request.recipe_id, request.recipe_version)
        if request.panel_count not in recipe.panel_counts:
            raise ValueError(
                f"recipe {recipe.recipe_id}@{recipe.version} does not support "
                f"{request.panel_count} panels"
            )
        run = StoryboardRun.create(
            run_id=self._run_id_factory(),
            intention=request.intention,
            panel_count=request.panel_count,
            model_id=request.model_id,
            recipe_id=recipe.recipe_id,
            recipe_version=recipe.version,
            template_sha256=recipe.template_sha256,
        )
        return self.runs.create(run)

    def generate(self, run_id: str) -> StoryboardRun:
        run, recipe = self._start(run_id)
        try:
            request = self._completion_request(run, recipe)
            result = self.gateway.complete(request)
        except Exception as error:
            return self.runs.save(run.fail(_error_message(error)))
        if result.finish_reason == "length":
            error = RuntimeError("The model response was truncated.")
            terminal = run.truncate(result.content, error=str(error))
            self._report(result.call_id, LlmCallApplicationOutcome.REJECTED, error)
            return self.runs.save(terminal)
        return self._apply_result(run, recipe, result)

    def stream_generate(
        self,
        run_id: str,
        *,
        include_reasoning: bool = False,
    ) -> Iterator[StoryboardStreamEvent]:
        if not isinstance(include_reasoning, bool):
            raise TypeError("include_reasoning must be a boolean")
        run, recipe = self._start(run_id)
        parts: list[str] = []
        try:
            request = self._completion_request(
                run,
                recipe,
                include_reasoning=include_reasoning,
            )
            for event in self.gateway.stream(request):
                if event.kind is StreamEventKind.DELTA:
                    parts.append(event.text)
                if event.kind is StreamEventKind.COMPLETED:
                    if event.result is None:
                        error = ValueError("stream completed without a result")
                        failed = self.runs.save(
                            run.fail(_error_message(error), raw_response="".join(parts))
                        )
                        yield _terminal_event(failed, "".join(parts), request)
                        return
                    terminal = self._apply_result(run, recipe, event.result)
                    yield StoryboardStreamEvent(
                        kind=StreamEventKind.COMPLETED,
                        phase=StreamPhase.COMPLETED,
                        text=(
                            terminal.compiled_prompt
                            if terminal.status is StoryboardRunStatus.SUCCEEDED
                            else terminal.raw_response or ""
                        ),
                        progress=1.0,
                        run=terminal,
                        finish_reason=event.result.finish_reason,
                        max_tokens=request.max_tokens,
                    )
                    return
                if event.kind is StreamEventKind.TRUNCATED:
                    raw_response = (
                        event.result.content
                        if event.result is not None
                        else "".join(parts) or event.text
                    )
                    error = RuntimeError("The model response was truncated.")
                    terminal = self.runs.save(
                        run.truncate(raw_response, error=str(error))
                    )
                    self._report(
                        event.result.call_id if event.result is not None else None,
                        LlmCallApplicationOutcome.REJECTED,
                        error,
                    )
                    yield StoryboardStreamEvent(
                        kind=StreamEventKind.TRUNCATED,
                        phase=StreamPhase.TRUNCATED,
                        text=raw_response,
                        run=terminal,
                        finish_reason=(
                            event.result.finish_reason
                            if event.result is not None
                            else None
                        ),
                        max_tokens=request.max_tokens,
                    )
                    return
                yield StoryboardStreamEvent(
                    kind=event.kind,
                    phase=event.phase,
                    text=event.text,
                    progress=event.progress,
                )
        except GeneratorExit:
            self._save_interrupted(run, "".join(parts), "Storyboard stream was closed.")
            raise
        except Exception as error:
            failed = self.runs.save(
                run.fail(_error_message(error), raw_response="".join(parts))
            )
            yield StoryboardStreamEvent(
                kind=StreamEventKind.COMPLETED,
                phase=StreamPhase.COMPLETED,
                text="".join(parts),
                progress=1.0,
                run=failed,
                max_tokens=self.max_tokens,
            )
            return

        error = RuntimeError("model stream ended before completion")
        failed = self.runs.save(
            run.fail(_error_message(error), raw_response="".join(parts))
        )
        yield _terminal_event(failed, "".join(parts), request)

    def _start(self, run_id: str) -> tuple[StoryboardRun, StoryboardRecipe]:
        with self._state_lock:
            run = self.runs.get(run_id)
            if run.status is not StoryboardRunStatus.CREATED:
                raise ValueError(f"run {run_id!r} is not ready for generation")
            recipe = self.recipes.get(run.recipe_id, run.recipe_version)
            if recipe.template_sha256 != run.template_sha256:
                raise ValueError("storyboard recipe content changed after run creation")
            generating = self.runs.save(run.start())
            return generating, recipe

    def _completion_request(
        self,
        run: StoryboardRun,
        recipe: StoryboardRecipe,
        *,
        include_reasoning: bool = False,
    ) -> CompletionRequest:
        system_prompt, user_prompt = recipe.build_request_prompts(
            run.intention,
            run.panel_count,
        )
        return CompletionRequest(
            model_id=run.model_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            operation_id=f"storyboard.generate.{recipe.recipe_id}@{recipe.version}",
            include_reasoning=include_reasoning,
        )

    def _apply_result(
        self,
        run: StoryboardRun,
        recipe: StoryboardRecipe,
        result: CompletionResult,
    ) -> StoryboardRun:
        try:
            spec = recipe.parse_spec(result.content, run.panel_count)
            prompt = recipe.compile_prompt(spec, run.panel_count)
            warnings = recipe.warnings_for_spec(spec, run.panel_count)
            terminal = run.succeed(
                raw_response=result.content,
                spec=spec,
                compiled_prompt=prompt,
                warnings=warnings,
            )
        except Exception as error:
            terminal = run.fail(
                _error_message(error),
                raw_response=result.content,
            )
            self._report(
                result.call_id,
                LlmCallApplicationOutcome.REJECTED,
                error,
            )
        else:
            self._report(result.call_id, LlmCallApplicationOutcome.ACCEPTED)
        return self.runs.save(terminal)

    def _save_interrupted(
        self,
        run: StoryboardRun,
        raw_response: str,
        error: str,
    ) -> None:
        try:
            current = self.runs.get(run.run_id)
            if current.status is StoryboardRunStatus.GENERATING:
                self.runs.save(
                    current.fail(error, raw_response=raw_response)
                )
        except Exception:
            _LOGGER.exception("failed to persist interrupted storyboard run %s", run.run_id)

    def _report(
        self,
        call_id: str | None,
        outcome: LlmCallApplicationOutcome,
        error: Exception | None = None,
    ) -> None:
        if self.application_outcomes is None or call_id is None:
            return
        try:
            self.application_outcomes.report_application_outcome(
                call_id,
                outcome,
                error_type=type(error).__name__ if error is not None else None,
                error_message=(str(error).strip() or None) if error is not None else None,
            )
        except Exception:
            _LOGGER.exception(
                "failed to persist application outcome for LLM call %s",
                call_id,
            )


def _terminal_event(
    run: StoryboardRun,
    text: str,
    request: CompletionRequest,
) -> StoryboardStreamEvent:
    return StoryboardStreamEvent(
        kind=StreamEventKind.COMPLETED,
        phase=StreamPhase.COMPLETED,
        text=text,
        progress=1.0,
        run=run,
        max_tokens=request.max_tokens,
    )


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _error_message(error: Exception) -> str:
    detail = str(error).strip()
    return f"{type(error).__name__}: {detail}" if detail else type(error).__name__
