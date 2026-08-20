"""Persistent orchestration for KREA2 text-to-image renders."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
import secrets
from threading import RLock
import time
from typing import Any, Protocol
from uuid import uuid4

from panelforge.domain.assets import Asset
from panelforge.domain.krea2_lab import (
    Krea2AspectRatio,
    Krea2LabRun,
    Krea2LabRunStatus,
    Krea2LabSettings,
    normalize_krea2_model_name,
)
from panelforge.domain.recipes import RecipeRef


class Krea2ComfyGateway(Protocol):
    def submit_workflow(self, workflow: Mapping[str, Any]) -> str: ...

    def get_history(self, prompt_id: str) -> dict[str, Any]: ...

    def download_output(
        self,
        *,
        filename: str,
        subfolder: str = "",
        folder_type: str = "output",
    ) -> bytes: ...

    def cancel_execution(self, prompt_id: str) -> object | None: ...


class Krea2AssetStore(Protocol):
    def create(
        self,
        content: bytes,
        *,
        media_type: str,
        source_run_id: str | None = None,
    ) -> Asset: ...

    def get(self, asset_id: str) -> Asset: ...


class Krea2RunStore(Protocol):
    def create(self, run: Krea2LabRun) -> Krea2LabRun: ...

    def save(self, run: Krea2LabRun) -> Krea2LabRun: ...

    def get(self, run_id: str) -> Krea2LabRun: ...

    def list(self, limit: int = 20) -> list[Krea2LabRun]: ...

    def save_compiled_workflow(
        self,
        run_id: str,
        workflow: Mapping[str, Any],
    ) -> str: ...


class Krea2Preset(Protocol):
    preset_id: str
    label: str
    aspect_ratio: Krea2AspectRatio
    megapixels: float
    model_name: str


class Krea2LabRecipe(Protocol):
    @property
    def reference(self) -> RecipeRef: ...

    @property
    def status(self) -> str: ...

    @property
    def presets(self) -> Mapping[str, Krea2Preset]: ...

    @property
    def qualified_models(self) -> tuple[str, ...]: ...

    @property
    def default_model(self) -> str: ...

    @property
    def output_node_id(self) -> str: ...

    @property
    def output_history_field(self) -> str: ...

    def build_workflow(
        self,
        *,
        prompt: str,
        settings: Krea2LabSettings,
        output_filename_prefix: str,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class Krea2LabRunRequest:
    prompt: str
    preset_id: str = "krea2-base"
    model_name: str | None = None
    aspect_ratio: Krea2AspectRatio | None = None
    megapixels: float | None = None
    seed: int | None = None
    seed_locked: bool = False
    source_storyboard_run_id: str | None = None
    source_prompt_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.prompt, "prompt")
        _require_text(self.preset_id, "preset_id")
        if self.model_name is not None:
            _require_text(self.model_name, "model_name")
        if self.aspect_ratio is not None and not isinstance(
            self.aspect_ratio,
            Krea2AspectRatio,
        ):
            raise TypeError("aspect_ratio must be a Krea2AspectRatio")
        if self.megapixels is not None and (
            isinstance(self.megapixels, bool)
            or not isinstance(self.megapixels, (int, float))
        ):
            raise TypeError("megapixels must be a number")
        if self.seed is not None and (
            isinstance(self.seed, bool)
            or not isinstance(self.seed, int)
            or not 0 <= self.seed < 2**64
        ):
            raise ValueError("seed must be between 0 and 2^64 - 1")
        if not isinstance(self.seed_locked, bool):
            raise TypeError("seed_locked must be a boolean")
        if self.source_storyboard_run_id is not None:
            _require_text(
                self.source_storyboard_run_id,
                "source_storyboard_run_id",
            )
        if self.source_prompt_sha256 is not None:
            _require_sha256(self.source_prompt_sha256, "source_prompt_sha256")


class Krea2LabRunner:
    """Prepare, queue, execute and cancel one KREA2 render at a time."""

    def __init__(
        self,
        *,
        recipe: Krea2LabRecipe,
        comfy: Krea2ComfyGateway,
        assets: Krea2AssetStore,
        runs: Krea2RunStore,
        run_timeout: float = 3600.0,
        poll_interval: float = 1.0,
        run_id_factory: Callable[[], str] | None = None,
        seed_factory: Callable[[], int] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if run_timeout <= 0:
            raise ValueError("run_timeout must be greater than zero")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be greater than zero")
        self.recipe = recipe
        self.comfy = comfy
        self.assets = assets
        self.runs = runs
        self.run_timeout = run_timeout
        self.poll_interval = poll_interval
        self._run_id_factory = run_id_factory or (
            lambda: f"krea2-{uuid4().hex}"
        )
        self._seed_factory = seed_factory or (lambda: secrets.randbits(64))
        self._monotonic = monotonic
        self._sleep = sleep
        self._state_lock = RLock()
        self._claimed: set[str] = set()

    def prepare(self, request: Krea2LabRunRequest) -> Krea2LabRun:
        preset = self.recipe.presets.get(request.preset_id)
        if preset is None:
            raise ValueError(f"unknown KREA2 preset {request.preset_id!r}")
        model_name = request.model_name or preset.model_name
        qualified_keys = {
            normalize_krea2_model_name(value)
            for value in self.recipe.qualified_models
        }
        if normalize_krea2_model_name(model_name) not in qualified_keys:
            raise ValueError(f"unqualified KREA2 model {model_name!r}")
        seed = request.seed if request.seed is not None else self._seed_factory()
        settings = Krea2LabSettings(
            model_name=model_name,
            aspect_ratio=request.aspect_ratio or preset.aspect_ratio,
            megapixels=(
                preset.megapixels
                if request.megapixels is None
                else request.megapixels
            ),
            seed=seed,
            seed_locked=request.seed_locked,
        )
        run = Krea2LabRun.create(
            run_id=self._run_id_factory(),
            recipe=self.recipe.reference,
            preset_id=preset.preset_id,
            prompt=request.prompt,
            settings=settings,
            source_storyboard_run_id=request.source_storyboard_run_id,
            source_prompt_sha256=request.source_prompt_sha256,
        )
        return self.runs.create(run)

    def queue(self, run_id: str) -> Krea2LabRun:
        """Claim the single KREA2 slot before scheduling background work."""
        with self._state_lock:
            run = self.runs.get(run_id)
            self._require_current_recipe(run)
            active = {
                Krea2LabRunStatus.QUEUED,
                Krea2LabRunStatus.RUNNING,
                Krea2LabRunStatus.CANCEL_PENDING,
            }
            candidates = self.runs.list(2**31 - 1)
            candidates = [
                self._refresh_detached_active(candidate)
                if (
                    candidate.status
                    in {
                        Krea2LabRunStatus.RUNNING,
                        Krea2LabRunStatus.CANCEL_PENDING,
                    }
                    and candidate.run_id not in self._claimed
                    and candidate.recipe == self.recipe.reference
                )
                else candidate
                for candidate in candidates
            ]
            if any(
                candidate.run_id != run_id and candidate.status in active
                for candidate in candidates
            ):
                raise ValueError("another KREA2 render is already active")
            run = run.queue()
            return self.runs.save(run)

    def execute(self, run_id: str) -> Krea2LabRun:
        """Execute a queued render; terminal errors remain visible in history."""
        with self._state_lock:
            run = self.runs.get(run_id)
            if run.status is Krea2LabRunStatus.CANCELLED:
                return run
            if run_id in self._claimed:
                raise ValueError(f"run {run_id!r} is already being executed")
            if run.status is not Krea2LabRunStatus.QUEUED:
                raise ValueError(f"run {run_id!r} is not queued")
            self._require_current_recipe(run)
            self._claimed.add(run_id)

        execution_id: str | None = None
        workflow_sha256: str | None = None
        try:
            if self._is_cancelled(run_id):
                return self.runs.get(run_id)
            workflow = self.recipe.build_workflow(
                prompt=run.prompt,
                settings=run.settings,
                output_filename_prefix=f"image/krea2/PanelForge_KREA2_{run.run_id}",
            )
            workflow_sha256 = self.runs.save_compiled_workflow(run.run_id, workflow)
            with self._state_lock:
                current = self.runs.get(run_id)
                if current.status in {
                    Krea2LabRunStatus.CANCELLED,
                    Krea2LabRunStatus.CANCEL_PENDING,
                }:
                    return current
                execution_id = self.comfy.submit_workflow(workflow)
                run = current.start(execution_id, workflow_sha256)
                self.runs.save(run)

            history_run = self._wait_for_history(run_id, execution_id)
            if history_run is None:
                return self.runs.get(run_id)
            output_ref = extract_bound_image(
                history_run,
                node_id=self.recipe.output_node_id,
                history_field=self.recipe.output_history_field,
            )
            output_content = self.comfy.download_output(
                filename=output_ref["filename"],
                subfolder=output_ref["subfolder"],
                folder_type=output_ref["type"],
            )
            _validate_png(output_content, output_ref["filename"])
            with self._state_lock:
                current = self.runs.get(run_id)
                if current.status in {
                    Krea2LabRunStatus.CANCELLED,
                    Krea2LabRunStatus.CANCEL_PENDING,
                }:
                    return current
                if current.status is not Krea2LabRunStatus.RUNNING:
                    return current
                output = self.assets.create(
                    output_content,
                    media_type="image/png",
                    source_run_id=run_id,
                )
                run = current.succeed(output.asset_id)
                self.runs.save(run)
                return run
        except Exception as error:
            with self._state_lock:
                current = self.runs.get(run_id)
                if current.status is Krea2LabRunStatus.CREATED:
                    current = current.fail(_error_message(error))
                    self.runs.save(current)
                elif (
                    current.status is Krea2LabRunStatus.QUEUED
                    and execution_id is not None
                    and workflow_sha256 is not None
                ):
                    current = self._stop_unpersisted_submission(
                        current,
                        execution_id,
                        workflow_sha256,
                        error,
                    )
                elif current.status is Krea2LabRunStatus.QUEUED:
                    current = current.fail(_error_message(error))
                    self.runs.save(current)
                elif current.status is Krea2LabRunStatus.RUNNING:
                    current = self._stop_remote_after_failure(current, error)
                return current
        finally:
            with self._state_lock:
                self._claimed.discard(run_id)

    def cancel(self, run_id: str) -> Krea2LabRun:
        with self._state_lock:
            run = self.runs.get(run_id)
            if (
                run.status
                in {
                    Krea2LabRunStatus.RUNNING,
                    Krea2LabRunStatus.CANCEL_PENDING,
                }
                and run.run_id not in self._claimed
                and run.recipe == self.recipe.reference
            ):
                run = self._refresh_detached_active(run)
                if run.status not in {
                    Krea2LabRunStatus.RUNNING,
                    Krea2LabRunStatus.CANCEL_PENDING,
                }:
                    return run
            if run.status in {
                Krea2LabRunStatus.RUNNING,
                Krea2LabRunStatus.CANCEL_PENDING,
            }:
                assert run.execution_id is not None
                try:
                    cancellation = self.comfy.cancel_execution(run.execution_id)
                except Exception as error:
                    if run.status is Krea2LabRunStatus.RUNNING:
                        run = run.mark_cancel_pending(
                            "Remote cancellation failed: " + _error_message(error)
                        )
                    else:
                        run = _replace_cancel_error(run, error)
                    return self.runs.save(run)
                if _cancellation_action(cancellation) == "already_finished":
                    run = self._refresh_detached_active(
                        run,
                        interruption_is_cancelled=True,
                    )
                    if run.status not in {
                        Krea2LabRunStatus.RUNNING,
                        Krea2LabRunStatus.CANCEL_PENDING,
                    }:
                        return run
                    run = _mark_history_reconciliation_pending(run)
                    return self.runs.save(run)
            run = run.cancel()
            return self.runs.save(run)

    def get(self, run_id: str) -> Krea2LabRun:
        with self._state_lock:
            run = self.runs.get(run_id)
            if (
                run.status
                in {
                    Krea2LabRunStatus.RUNNING,
                    Krea2LabRunStatus.CANCEL_PENDING,
                }
                and run_id not in self._claimed
                and run.recipe == self.recipe.reference
            ):
                run = self._refresh_detached_active(run)
            return run

    def list(self, limit: int = 20) -> list[Krea2LabRun]:
        return self.runs.list(limit)

    def output_asset(self, run_id: str) -> Asset:
        run = self.runs.get(run_id)
        if run.status is not Krea2LabRunStatus.SUCCEEDED:
            raise ValueError("only a successful run has a final image")
        assert run.output_asset_id is not None
        return self.assets.get(run.output_asset_id)

    def _wait_for_history(
        self,
        run_id: str,
        execution_id: str,
    ) -> dict[str, Any] | None:
        deadline = self._monotonic() + self.run_timeout
        while True:
            if self._is_cancelled(run_id):
                return None
            history = self.comfy.get_history(execution_id)
            candidate = history.get(execution_id)
            if isinstance(candidate, dict):
                status = candidate.get("status")
                if isinstance(status, dict):
                    completed = status.get("completed") is True
                    status_name = status.get("status_str")
                    if completed and status_name == "success":
                        return candidate
                    if completed or status_name == "error":
                        raise RuntimeError(
                            f"ComfyUI execution failed: {status.get('messages', status)}"
                        )
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"ComfyUI did not complete {execution_id!r} within "
                    f"{self.run_timeout:g} seconds"
                )
            self._sleep(min(self.poll_interval, remaining))

    def _is_cancelled(self, run_id: str) -> bool:
        return self.runs.get(run_id).status in {
            Krea2LabRunStatus.CANCELLED,
            Krea2LabRunStatus.CANCEL_PENDING,
        }

    def _require_current_recipe(self, run: Krea2LabRun) -> None:
        if run.recipe != self.recipe.reference:
            raise ValueError(
                "the run recipe version is not loaded; create a new KREA2 run"
            )

    def _stop_remote_after_failure(
        self,
        run: Krea2LabRun,
        error: Exception,
    ) -> Krea2LabRun:
        assert run.execution_id is not None
        execution_error = _error_message(error)
        try:
            self.comfy.cancel_execution(run.execution_id)
        except Exception as cancellation_error:
            run = run.mark_cancel_pending(
                f"{execution_error}; remote cancellation failed: "
                f"{_error_message(cancellation_error)}"
            )
        else:
            run = run.fail(execution_error)
        return self.runs.save(run)

    def _stop_unpersisted_submission(
        self,
        run: Krea2LabRun,
        execution_id: str,
        workflow_sha256: str,
        error: Exception,
    ) -> Krea2LabRun:
        submitted = run.start(execution_id, workflow_sha256)
        execution_error = _error_message(error)
        try:
            self.comfy.cancel_execution(execution_id)
        except Exception as cancellation_error:
            submitted = submitted.mark_cancel_pending(
                f"{execution_error}; remote cancellation failed: "
                f"{_error_message(cancellation_error)}"
            )
        else:
            submitted = submitted.fail(execution_error)
        return self.runs.save(submitted)

    def _refresh_detached_active(
        self,
        run: Krea2LabRun,
        *,
        interruption_is_cancelled: bool = False,
    ) -> Krea2LabRun:
        """Reconcile a persisted Comfy execution after worker detachment."""
        if run.status not in {
            Krea2LabRunStatus.RUNNING,
            Krea2LabRunStatus.CANCEL_PENDING,
        }:
            raise ValueError(
                f"cannot refresh a detached {run.status.value} run"
            )
        assert run.execution_id is not None
        try:
            history = self.comfy.get_history(run.execution_id)
        except Exception:
            return run
        candidate = history.get(run.execution_id)
        if not isinstance(candidate, dict):
            return run
        status = candidate.get("status")
        if not isinstance(status, dict):
            return run
        completed = status.get("completed") is True
        status_name = status.get("status_str")
        terminal_kind = _history_terminal_kind(status)
        if not completed and terminal_kind is None:
            return run
        if terminal_kind == "success":
            try:
                output_ref = extract_bound_image(
                    candidate,
                    node_id=self.recipe.output_node_id,
                    history_field=self.recipe.output_history_field,
                )
                content = self.comfy.download_output(
                    filename=output_ref["filename"],
                    subfolder=output_ref["subfolder"],
                    folder_type=output_ref["type"],
                )
                _validate_png(content, output_ref["filename"])
                output = self.assets.create(
                    content,
                    media_type="image/png",
                    source_run_id=run.run_id,
                )
                return self.runs.save(run.succeed(output.asset_id))
            except Exception as error:
                return self.runs.save(run.fail(_error_message(error)))
        if (
            terminal_kind == "interrupted"
            and (
                interruption_is_cancelled
                or run.status is Krea2LabRunStatus.CANCEL_PENDING
            )
        ):
            return self.runs.save(run.cancel())
        return self.runs.save(
            run.fail(
                "ComfyUI execution failed after restart: "
                f"{status.get('messages', status)}"
            )
        )


def extract_bound_image(
    history_run: Mapping[str, Any],
    *,
    node_id: str,
    history_field: str,
) -> dict[str, str]:
    """Read the exact SaveImage result declared by the recipe manifest."""
    outputs = history_run.get("outputs")
    if not isinstance(outputs, Mapping):
        raise ValueError("ComfyUI history has no outputs object")
    node_output = outputs.get(node_id)
    if not isinstance(node_output, Mapping):
        raise ValueError(f"ComfyUI history has no output for node {node_id!r}")
    images = node_output.get(history_field)
    if not isinstance(images, list) or not images:
        raise ValueError(
            f"ComfyUI node {node_id!r} has no {history_field!r} output"
        )
    image = images[0]
    if not isinstance(image, Mapping):
        raise ValueError("ComfyUI image output must be an object")
    filename = image.get("filename")
    subfolder = image.get("subfolder", "")
    folder_type = image.get("type", "output")
    if not isinstance(filename, str) or not filename:
        raise ValueError("ComfyUI image output has no filename")
    if not isinstance(subfolder, str) or not isinstance(folder_type, str):
        raise ValueError("ComfyUI image output has invalid location fields")
    return {
        "filename": filename,
        "subfolder": subfolder,
        "type": folder_type,
    }


def _validate_png(content: bytes, filename: str) -> None:
    if not filename.lower().endswith(".png"):
        raise ValueError("ComfyUI output is not a PNG image")
    if len(content) < 8 or content[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("ComfyUI output has no PNG file signature")


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    return value


def _require_sha256(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest")
    return value


def _error_message(error: Exception) -> str:
    detail = str(error).strip()
    return f"{type(error).__name__}: {detail}" if detail else type(error).__name__


def _replace_cancel_error(run: Krea2LabRun, error: Exception) -> Krea2LabRun:
    return replace(
        run,
        error="Remote cancellation failed: " + _error_message(error),
    )


def _cancellation_action(result: object | None) -> str | None:
    action = getattr(result, "action", None)
    value = getattr(action, "value", action)
    return value if isinstance(value, str) else None


def _mark_history_reconciliation_pending(run: Krea2LabRun) -> Krea2LabRun:
    message = (
        "ComfyUI reports the job already finished, but terminal history is "
        "temporarily unavailable; reconciliation will retry"
    )
    if run.status is Krea2LabRunStatus.RUNNING:
        return run.mark_cancel_pending(message)
    if run.status is Krea2LabRunStatus.CANCEL_PENDING:
        return replace(run, error=message)
    raise ValueError(
        f"cannot defer history reconciliation for a {run.status.value} run"
    )


def _history_terminal_kind(status: Mapping[str, Any]) -> str | None:
    status_name = status.get("status_str")
    normalized_status = (
        status_name.casefold() if isinstance(status_name, str) else ""
    )
    event_names: set[str] = set()
    messages = status.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, Mapping):
                event_name = message.get("type")
            elif isinstance(message, (list, tuple)) and message:
                event_name = message[0]
            else:
                event_name = None
            if isinstance(event_name, str):
                event_names.add(event_name.casefold())
    if normalized_status in {"interrupted", "cancelled", "canceled"} or (
        "execution_interrupted" in event_names
    ):
        return "interrupted"
    if normalized_status in {"error", "failed", "failure"} or (
        "execution_error" in event_names
    ):
        return "failed"
    if normalized_status in {"success", "completed"} and (
        status.get("completed") is True
        or normalized_status == "completed"
    ):
        return "success"
    return None
