"""Persistent orchestration for MiniMax H3 Video Lab renders."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
import secrets
from threading import RLock
import time
from typing import Any, Protocol
from uuid import uuid4

from panelforge.domain import (
    Asset,
    RecipeRef,
    VideoAspectRatio,
    VideoLabRun,
    VideoLabRunStatus,
    VideoLabSettings,
)


class UploadedImage(Protocol):
    @property
    def workflow_value(self) -> str: ...


class VideoComfyGateway(Protocol):
    def upload_image(
        self,
        content: bytes,
        *,
        filename: str,
        subfolder: str = "",
    ) -> UploadedImage: ...

    def submit_workflow(self, workflow: Mapping[str, Any]) -> str: ...

    def get_history(self, prompt_id: str) -> dict[str, Any]: ...

    def download_output(
        self,
        *,
        filename: str,
        subfolder: str = "",
        folder_type: str = "output",
    ) -> bytes: ...

    def cancel_execution(self, prompt_id: str) -> None: ...


class VideoAssetStore(Protocol):
    def create(
        self,
        content: bytes,
        *,
        media_type: str,
        source_run_id: str | None = None,
    ) -> Asset: ...

    def get(self, asset_id: str) -> Asset: ...

    def read_bytes(self, asset_id: str) -> bytes: ...


class VideoRunStore(Protocol):
    def create(self, run: VideoLabRun) -> VideoLabRun: ...

    def save(self, run: VideoLabRun) -> VideoLabRun: ...

    def get(self, run_id: str) -> VideoLabRun: ...

    def list(self, limit: int = 20) -> list[VideoLabRun]: ...

    def save_compiled_workflow(
        self,
        run_id: str,
        workflow: Mapping[str, Any],
    ) -> str: ...


class VideoPreset(Protocol):
    preset_id: str
    label: str
    aspect_ratio: VideoAspectRatio
    megapixels: float
    duration_seconds: float
    steps: int
    preview_frames: int
    preview_fps: int
    preview_jpeg_quality: int
    preview_max_resolution: int


class VideoLabRecipe(Protocol):
    @property
    def reference(self) -> RecipeRef: ...

    @property
    def status(self) -> str: ...

    @property
    def presets(self) -> Mapping[str, VideoPreset]: ...

    @property
    def output_node_id(self) -> str: ...

    @property
    def output_history_field(self) -> str: ...

    def build_workflow(
        self,
        *,
        source_images: Sequence[str],
        prompt: str,
        settings: VideoLabSettings,
        output_filename_prefix: str,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class VideoLabRunRequest:
    source_asset_ids: tuple[str, ...]
    prompt: str
    preset_id: str
    source_labels: tuple[str, ...] = ()
    aspect_ratio: VideoAspectRatio | None = None
    megapixels: float | None = None
    duration_seconds: float | None = None
    steps: int | None = None
    seed: int | None = None
    seed_locked: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.source_asset_ids, tuple):
            raise TypeError("source_asset_ids must be a tuple")
        if not 1 <= len(self.source_asset_ids) <= 3:
            raise ValueError("provide between 1 and 3 source images")
        if len(set(self.source_asset_ids)) != len(self.source_asset_ids):
            raise ValueError("source_asset_ids must not contain duplicates")
        for asset_id in self.source_asset_ids:
            _require_text(asset_id, "source_asset_ids item")
        if not isinstance(self.source_labels, tuple):
            raise TypeError("source_labels must be a tuple")
        if self.source_labels and len(self.source_labels) != len(self.source_asset_ids):
            raise ValueError("source_labels must align with source_asset_ids")
        for label in self.source_labels:
            _require_text(label, "source_labels item")
        _require_text(self.prompt, "prompt")
        _require_text(self.preset_id, "preset_id")
        if self.aspect_ratio is not None and not isinstance(
            self.aspect_ratio,
            VideoAspectRatio,
        ):
            raise TypeError("aspect_ratio must be a VideoAspectRatio")
        if self.seed is not None and (
            isinstance(self.seed, bool)
            or not isinstance(self.seed, int)
            or not 0 <= self.seed < 2**64
        ):
            raise ValueError("seed must be between 0 and 2^64 - 1")
        if not isinstance(self.seed_locked, bool):
            raise TypeError("seed_locked must be a boolean")


class VideoLabRunner:
    """Prepare, queue, execute and cancel one Video Lab render at a time."""

    def __init__(
        self,
        *,
        recipe: VideoLabRecipe,
        comfy: VideoComfyGateway,
        assets: VideoAssetStore,
        runs: VideoRunStore,
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
            lambda: f"video-{uuid4().hex}"
        )
        self._seed_factory = seed_factory or (lambda: secrets.randbits(64))
        self._monotonic = monotonic
        self._sleep = sleep
        self._state_lock = RLock()
        self._claimed: set[str] = set()

    def prepare(self, request: VideoLabRunRequest) -> VideoLabRun:
        sources = tuple(self.assets.get(asset_id) for asset_id in request.source_asset_ids)
        if any(not source.media_type.startswith("image/") for source in sources):
            raise ValueError("every source asset must be an image")
        preset = self.recipe.presets.get(request.preset_id)
        if preset is None:
            raise ValueError(f"unknown Video Lab preset {request.preset_id!r}")
        seed = request.seed if request.seed is not None else self._seed_factory()
        settings = VideoLabSettings(
            aspect_ratio=request.aspect_ratio or preset.aspect_ratio,
            megapixels=(
                preset.megapixels
                if request.megapixels is None
                else request.megapixels
            ),
            duration_seconds=(
                preset.duration_seconds
                if request.duration_seconds is None
                else request.duration_seconds
            ),
            steps=preset.steps if request.steps is None else request.steps,
            seed=seed,
            seed_locked=request.seed_locked,
        )
        labels = request.source_labels or tuple(source.asset_id for source in sources)
        run = VideoLabRun.create(
            run_id=self._run_id_factory(),
            recipe=self.recipe.reference,
            preset_id=preset.preset_id,
            source_asset_ids=tuple(source.asset_id for source in sources),
            source_labels=labels,
            prompt=request.prompt,
            settings=settings,
        )
        return self.runs.create(run)

    def queue(self, run_id: str) -> VideoLabRun:
        """Claim the single Video Lab slot before scheduling background work."""
        with self._state_lock:
            run = self.runs.get(run_id)
            self._require_current_recipe(run)
            active = {
                VideoLabRunStatus.QUEUED,
                VideoLabRunStatus.RUNNING,
                VideoLabRunStatus.CANCEL_PENDING,
            }
            candidates = self.runs.list(2**31 - 1)
            candidates = [
                self._refresh_detached_running(candidate)
                if (
                    candidate.status is VideoLabRunStatus.RUNNING
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
                raise ValueError("another Video Lab render is already active")
            run = run.queue()
            return self.runs.save(run)

    def execute(self, run_id: str) -> VideoLabRun:
        """Execute a queued render; terminal errors remain visible in history."""
        with self._state_lock:
            run = self.runs.get(run_id)
            if run.status is VideoLabRunStatus.CANCELLED:
                return run
            if run.status is not VideoLabRunStatus.QUEUED:
                raise ValueError(f"run {run_id!r} is not queued")
            self._require_current_recipe(run)
            if run_id in self._claimed:
                raise ValueError(f"run {run_id!r} is already being executed")
            self._claimed.add(run_id)

        execution_id: str | None = None
        workflow_sha256: str | None = None
        try:
            uploaded_values: list[str] = []
            for asset_id in run.source_asset_ids:
                if self._is_cancelled(run_id):
                    return self.runs.get(run_id)
                source = self.assets.get(asset_id)
                uploaded = self.comfy.upload_image(
                    self.assets.read_bytes(asset_id),
                    filename=_comfy_filename(source),
                    subfolder="panelforge/video-lab",
                )
                uploaded_values.append(uploaded.workflow_value)

            if self._is_cancelled(run_id):
                return self.runs.get(run_id)
            workflow = self.recipe.build_workflow(
                source_images=uploaded_values,
                prompt=run.prompt,
                settings=run.settings,
                output_filename_prefix=f"video/PanelForge_H3_{run.run_id}",
            )
            workflow_sha256 = self.runs.save_compiled_workflow(run.run_id, workflow)
            with self._state_lock:
                current = self.runs.get(run_id)
                if current.status in {
                    VideoLabRunStatus.CANCELLED,
                    VideoLabRunStatus.CANCEL_PENDING,
                }:
                    return current
                execution_id = self.comfy.submit_workflow(workflow)
                run = current.start(execution_id, workflow_sha256)
                self.runs.save(run)

            history_run = self._wait_for_history(run_id, execution_id)
            if history_run is None:
                return self.runs.get(run_id)
            output_ref = extract_bound_video(
                history_run,
                node_id=self.recipe.output_node_id,
                history_field=self.recipe.output_history_field,
            )
            output_content = self.comfy.download_output(
                filename=output_ref["filename"],
                subfolder=output_ref["subfolder"],
                folder_type=output_ref["type"],
            )
            _validate_mp4(output_content, output_ref["filename"])
            with self._state_lock:
                current = self.runs.get(run_id)
                if current.status in {
                    VideoLabRunStatus.CANCELLED,
                    VideoLabRunStatus.CANCEL_PENDING,
                }:
                    return current
                if current.status is not VideoLabRunStatus.RUNNING:
                    return current
                output = self.assets.create(
                    output_content,
                    media_type="video/mp4",
                    source_run_id=run_id,
                )
                run = current.succeed(output.asset_id)
                self.runs.save(run)
                return run
        except Exception as error:
            with self._state_lock:
                current = self.runs.get(run_id)
                if current.status in {
                    VideoLabRunStatus.CREATED,
                }:
                    current = current.fail(_error_message(error))
                    self.runs.save(current)
                elif (
                    current.status is VideoLabRunStatus.QUEUED
                    and execution_id is not None
                    and workflow_sha256 is not None
                ):
                    current = self._stop_unpersisted_submission(
                        current,
                        execution_id,
                        workflow_sha256,
                        error,
                    )
                elif current.status is VideoLabRunStatus.QUEUED:
                    current = current.fail(_error_message(error))
                    self.runs.save(current)
                elif current.status is VideoLabRunStatus.RUNNING:
                    current = self._stop_remote_after_failure(current, error)
                return current
        finally:
            with self._state_lock:
                self._claimed.discard(run_id)

    def cancel(self, run_id: str) -> VideoLabRun:
        with self._state_lock:
            run = self.runs.get(run_id)
            if (
                run.status is VideoLabRunStatus.RUNNING
                and run.run_id not in self._claimed
                and run.recipe == self.recipe.reference
            ):
                run = self._refresh_detached_running(run)
                if run.status is not VideoLabRunStatus.RUNNING:
                    return run
            if run.status in {
                VideoLabRunStatus.RUNNING,
                VideoLabRunStatus.CANCEL_PENDING,
            }:
                assert run.execution_id is not None
                try:
                    self.comfy.cancel_execution(run.execution_id)
                except Exception as error:
                    if run.status is VideoLabRunStatus.RUNNING:
                        run = run.mark_cancel_pending(
                            "Remote cancellation failed: " + _error_message(error)
                        )
                    else:
                        run = _replace_cancel_error(run, error)
                    return self.runs.save(run)
            run = run.cancel()
            return self.runs.save(run)

    def get(self, run_id: str) -> VideoLabRun:
        with self._state_lock:
            run = self.runs.get(run_id)
            if (
                run.status is VideoLabRunStatus.RUNNING
                and run_id not in self._claimed
                and run.recipe == self.recipe.reference
            ):
                run = self._refresh_detached_running(run)
            return run

    def list(self, limit: int = 20) -> list[VideoLabRun]:
        return self.runs.list(limit)

    def output_asset(self, run_id: str) -> Asset:
        run = self.runs.get(run_id)
        if run.status is not VideoLabRunStatus.SUCCEEDED:
            raise ValueError("only a successful run has a final video")
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
            VideoLabRunStatus.CANCELLED,
            VideoLabRunStatus.CANCEL_PENDING,
        }

    def _require_current_recipe(self, run: VideoLabRun) -> None:
        if run.recipe != self.recipe.reference:
            raise ValueError(
                "the run recipe version is not loaded; create a new Video Lab run"
            )

    def _stop_remote_after_failure(
        self,
        run: VideoLabRun,
        error: Exception,
    ) -> VideoLabRun:
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
        run: VideoLabRun,
        execution_id: str,
        workflow_sha256: str,
        error: Exception,
    ) -> VideoLabRun:
        """Retain a known Comfy ID when persisting RUNNING initially failed."""
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

    def _refresh_detached_running(self, run: VideoLabRun) -> VideoLabRun:
        """Reconcile one persisted Comfy execution after a process restart."""
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
        if not completed and status_name != "error":
            return run
        if completed and status_name == "success":
            try:
                output_ref = extract_bound_video(
                    candidate,
                    node_id=self.recipe.output_node_id,
                    history_field=self.recipe.output_history_field,
                )
                content = self.comfy.download_output(
                    filename=output_ref["filename"],
                    subfolder=output_ref["subfolder"],
                    folder_type=output_ref["type"],
                )
                _validate_mp4(content, output_ref["filename"])
                output = self.assets.create(
                    content,
                    media_type="video/mp4",
                    source_run_id=run.run_id,
                )
                return self.runs.save(run.succeed(output.asset_id))
            except Exception as error:
                return self.runs.save(run.fail(_error_message(error)))
        return self.runs.save(
            run.fail(
                "ComfyUI execution failed after restart: "
                f"{status.get('messages', status)}"
            )
        )


def extract_bound_video(
    history_run: Mapping[str, Any],
    *,
    node_id: str,
    history_field: str,
) -> dict[str, str]:
    """Read the exact SaveVideo result declared by the recipe manifest."""
    outputs = history_run.get("outputs")
    if not isinstance(outputs, Mapping):
        raise ValueError("ComfyUI history has no outputs object")
    node_output = outputs.get(node_id)
    if not isinstance(node_output, Mapping):
        raise ValueError(f"ComfyUI history has no output for node {node_id!r}")
    videos = node_output.get(history_field)
    if not isinstance(videos, list) or not videos:
        raise ValueError(
            f"ComfyUI node {node_id!r} has no {history_field!r} output"
        )
    video = videos[0]
    if not isinstance(video, Mapping):
        raise ValueError("ComfyUI video output must be an object")
    filename = video.get("filename")
    subfolder = video.get("subfolder", "")
    folder_type = video.get("type", "output")
    if not isinstance(filename, str) or not filename:
        raise ValueError("ComfyUI video output has no filename")
    if not isinstance(subfolder, str) or not isinstance(folder_type, str):
        raise ValueError("ComfyUI video output has invalid location fields")
    return {
        "filename": filename,
        "subfolder": subfolder,
        "type": folder_type,
    }


def _comfy_filename(asset: Asset) -> str:
    extension = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }.get(asset.media_type)
    if extension is None:
        raise ValueError(f"unsupported source media type {asset.media_type!r}")
    return f"{asset.asset_id}{extension}"


def _validate_mp4(content: bytes, filename: str) -> None:
    if not filename.lower().endswith(".mp4"):
        raise ValueError("ComfyUI output is not an MP4 video")
    if len(content) < 12 or content[4:8] != b"ftyp":
        raise ValueError("ComfyUI output has no MP4 file signature")


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    return value


def _error_message(error: Exception) -> str:
    detail = str(error).strip()
    return f"{type(error).__name__}: {detail}" if detail else type(error).__name__


def _replace_cancel_error(run: VideoLabRun, error: Exception) -> VideoLabRun:
    """Refresh a pending-cancellation diagnostic without losing provenance."""
    return replace(
        run,
        error="Remote cancellation failed: " + _error_message(error),
    )
