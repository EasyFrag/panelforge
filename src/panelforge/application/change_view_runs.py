"""Persistent application flow for the curated character view recipe."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

from panelforge.domain import (
    Asset,
    ControlValue,
    PromptPolicy,
    PromptSnapshot,
    RecipeRef,
    RunRecord,
    RunReview,
    RunStatus,
    VariationPolicy,
)
from panelforge.domain.character import (
    CameraAzimuth,
    CameraElevation,
    ChangeView,
    ShotSize,
)


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class UploadedImage(Protocol):
    @property
    def workflow_value(self) -> str: ...


class ComfyGateway(Protocol):
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


class AssetStore(Protocol):
    def create(
        self,
        content: bytes,
        *,
        media_type: str,
        source_run_id: str | None = None,
    ) -> Asset: ...

    def get(self, asset_id: str) -> Asset: ...

    def read_bytes(self, asset_id: str) -> bytes: ...


class RunStore(Protocol):
    def create(self, run: RunRecord) -> None: ...

    def save(self, run: RunRecord) -> None: ...

    def get(self, run_id: str) -> RunRecord: ...

    def list(self, limit: int = 20) -> list[RunRecord]: ...

    def save_compiled_workflow(
        self,
        run_id: str,
        workflow: Mapping[str, Any],
    ) -> str: ...


class ChangeViewRecipe(Protocol):
    @property
    def reference(self) -> RecipeRef: ...

    @property
    def variation_policy(self) -> VariationPolicy: ...

    @property
    def prompt_policy(self) -> PromptPolicy: ...

    @property
    def negative_prompt(self) -> str: ...

    @property
    def output_node_id(self) -> str: ...

    @property
    def output_history_field(self) -> str: ...

    def render_prompt(self, change: ChangeView) -> str: ...

    def build_workflow(
        self,
        change: ChangeView,
        *,
        source_image: str,
        seed: int,
        lora_strength: float,
    ) -> dict[str, Any]: ...

    def is_experimental_lora_override(self, value: float) -> bool: ...


@dataclass(frozen=True, slots=True)
class ChangeViewRunRequest:
    source_asset_id: str
    azimuth: CameraAzimuth
    elevation: CameraElevation
    shot_size: ShotSize
    lora_strength: float
    seed: int

    def __post_init__(self) -> None:
        if not isinstance(self.source_asset_id, str) or not self.source_asset_id.strip():
            raise ValueError("source_asset_id must not be empty")
        if not isinstance(self.azimuth, CameraAzimuth):
            raise TypeError("azimuth must be a CameraAzimuth")
        if not isinstance(self.elevation, CameraElevation):
            raise TypeError("elevation must be a CameraElevation")
        if not isinstance(self.shot_size, ShotSize):
            raise TypeError("shot_size must be a ShotSize")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an integer")
        if not 0 <= self.seed < 2**64:
            raise ValueError("seed must be between 0 and 2^64 - 1")


class ChangeViewRunner:
    """Create a run immediately, then execute it through ComfyUI."""

    def __init__(
        self,
        *,
        recipe: ChangeViewRecipe,
        comfy: ComfyGateway,
        assets: AssetStore,
        runs: RunStore,
        run_timeout: float = 600.0,
        poll_interval: float = 1.0,
        run_id_factory: Callable[[], str] | None = None,
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
            lambda: f"run-{uuid4().hex}"
        )
        self._monotonic = monotonic
        self._sleep = sleep

    def prepare(self, request: ChangeViewRunRequest) -> RunRecord:
        """Validate and persist a created run before background execution."""
        source = self.assets.get(request.source_asset_id)
        if not source.media_type.startswith("image/"):
            raise ValueError("source asset must be an image")

        change = _change_from_request(request)
        controls = self.recipe.variation_policy.validate_values(
            (
                ControlValue("azimuth", request.azimuth.value),
                ControlValue("elevation", request.elevation.value),
                ControlValue("shot_size", request.shot_size.value),
                ControlValue("multiple_angles_lora_strength", request.lora_strength),
                ControlValue("seed", request.seed),
            )
        )
        overrides = (
            ("multiple_angles_lora_strength",)
            if self.recipe.is_experimental_lora_override(request.lora_strength)
            else ()
        )
        run = RunRecord.create(
            run_id=self._run_id_factory(),
            recipe=self.recipe.reference,
            source_asset_ids=(source.asset_id,),
            prompt=PromptSnapshot(
                positive=self.recipe.render_prompt(change),
                negative=self.recipe.negative_prompt,
                policy=self.recipe.prompt_policy,
            ),
            controls=controls,
            experimental_overrides=overrides,
            parent_run_id=source.source_run_id,
        )
        self.runs.create(run)
        return run

    def execute(self, run_id: str) -> RunRecord:
        """Execute one previously prepared run and persist every transition."""
        run = self.runs.get(run_id)
        if run.status is not RunStatus.CREATED:
            raise ValueError(f"run {run_id!r} is not ready for execution")

        try:
            source = self.assets.get(run.source_asset_ids[0])
            source_content = self.assets.read_bytes(source.asset_id)
            uploaded = self.comfy.upload_image(
                source_content,
                filename=_comfy_filename(source),
                subfolder="panelforge",
            )
            values = {control.control_id: control.value for control in run.controls}
            change = ChangeView(
                source_asset_id=source.asset_id,
                azimuth=CameraAzimuth(values["azimuth"]),
                elevation=CameraElevation(values["elevation"]),
                shot_size=ShotSize(values["shot_size"]),
            )
            workflow = self.recipe.build_workflow(
                change,
                source_image=uploaded.workflow_value,
                seed=_require_int(values["seed"], "seed"),
                lora_strength=_require_float(
                    values["multiple_angles_lora_strength"],
                    "multiple_angles_lora_strength",
                ),
            )
            workflow_sha256 = self.runs.save_compiled_workflow(run.run_id, workflow)
            execution_id = self.comfy.submit_workflow(workflow)
            run = run.submit(execution_id, workflow_sha256)
            self.runs.save(run)

            history_run = self._wait_for_history(execution_id)
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
            if not output_content.startswith(PNG_SIGNATURE):
                raise ValueError("ComfyUI output is not a PNG image")
            output = self.assets.create(
                output_content,
                media_type="image/png",
                source_run_id=run.run_id,
            )
            run = run.succeed((output.asset_id,))
            self.runs.save(run)
            return run
        except Exception as error:
            current = self.runs.get(run_id)
            if current.status in (RunStatus.CREATED, RunStatus.SUBMITTED):
                current = current.fail(_error_message(error))
                self.runs.save(current)
            return current

    def review(self, run_id: str, decision: RunReview) -> RunRecord:
        run = self.runs.get(run_id).review(decision)
        self.runs.save(run)
        return run

    def reusable_asset(self, run_id: str) -> Asset:
        run = self.runs.get(run_id)
        if run.status is not RunStatus.SUCCEEDED or not run.output_asset_ids:
            raise ValueError("only a successful run has a reusable result")
        return self.assets.get(run.output_asset_ids[0])

    def _wait_for_history(self, execution_id: str) -> dict[str, Any]:
        deadline = self._monotonic() + self.run_timeout
        while True:
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


def extract_bound_image(
    history_run: Mapping[str, Any],
    *,
    node_id: str,
    history_field: str,
) -> dict[str, str]:
    """Read exactly the output declared by the recipe manifest."""
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


def _change_from_request(request: ChangeViewRunRequest) -> ChangeView:
    return ChangeView(
        source_asset_id=request.source_asset_id,
        azimuth=request.azimuth,
        elevation=request.elevation,
        shot_size=request.shot_size,
    )


def _comfy_filename(asset: Asset) -> str:
    extension = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }.get(asset.media_type)
    if extension is None:
        raise ValueError(f"unsupported source media type {asset.media_type!r}")
    return f"{asset.asset_id}{extension}"


def _require_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    return value


def _require_float(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    return float(value)


def _error_message(error: Exception) -> str:
    detail = str(error).strip()
    return f"{type(error).__name__}: {detail}" if detail else type(error).__name__
