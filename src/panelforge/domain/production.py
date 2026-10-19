"""Shared compute-resource, workload and thermal-policy contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import math


class ComputeResource(StrEnum):
    LOCAL_GPU = "local_gpu"
    REMOTE_GPU = "remote_gpu"


class ProductionWorkload(StrEnum):
    LLM = "llm"
    MAINTENANCE = "maintenance"
    IMAGE_RENDER = "image_render"
    VIDEO_RENDER = "video_render"
    VIDEO_COOLDOWN = "video_cooldown"
    DLSS = "dlss"


class ComputeResourceState(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    PAUSED = "paused"
    HOT = "hot"
    COOLING = "cooling"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ComputeResourceStatus:
    resource: ComputeResource
    state: ComputeResourceState
    temperature_c: float | None = None
    owner_job_id: str | None = None
    operation: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.resource, ComputeResource):
            raise TypeError("resource must be a ComputeResource")
        if not isinstance(self.state, ComputeResourceState):
            raise TypeError("state must be a ComputeResourceState")
        if self.temperature_c is not None:
            temperature = _finite(self.temperature_c, "temperature_c")
            if not 0 <= temperature <= 150:
                raise ValueError("temperature_c must be between 0 and 150")
        for value, label, maximum in (
            (self.owner_job_id, "owner_job_id", 128),
            (self.operation, "operation", 200),
            (self.error, "resource error", 1_000),
        ):
            if value is not None:
                _text(value, label, maximum)


@dataclass(frozen=True, slots=True)
class ThermalPolicy:
    stop_temperature_c: float = 85.0
    resume_temperature_c: float = 40.0
    cooldown_seconds: int = 120
    monitor_local: bool = True
    monitor_remote: bool = True
    pause_when_unavailable: bool = True

    def __post_init__(self) -> None:
        _finite(self.stop_temperature_c, "stop_temperature_c")
        _finite(self.resume_temperature_c, "resume_temperature_c")
        if not 30 <= float(self.stop_temperature_c) <= 110:
            raise ValueError("stop_temperature_c must be between 30 and 110")
        if not 15 <= float(self.resume_temperature_c) < float(self.stop_temperature_c):
            raise ValueError("resume_temperature_c must be below the stop temperature")
        if (
            isinstance(self.cooldown_seconds, bool)
            or not isinstance(self.cooldown_seconds, int)
            or not 0 <= self.cooldown_seconds <= 86_400
        ):
            raise ValueError("cooldown_seconds must be between 0 and 86400")
        for value, label in (
            (self.monitor_local, "monitor_local"),
            (self.monitor_remote, "monitor_remote"),
            (self.pause_when_unavailable, "pause_when_unavailable"),
        ):
            if not isinstance(value, bool):
                raise TypeError(f"{label} must be a boolean")
        if not self.monitor_local and not self.monitor_remote:
            raise ValueError("at least one thermal source must be monitored")


@dataclass(frozen=True, slots=True)
class WorkSchedulerSettings:
    """Global admission and hardware-protection policy for both machines."""

    thermal: ThermalPolicy = field(default_factory=ThermalPolicy)
    local_cooldown_temperature_c: float = 80.0
    local_cooldown_seconds: int = 80
    remote_non_video_cooldown_temperature_c: float = 80.0
    remote_non_video_cooldown_seconds: int = 80
    remote_video_cooldown_seconds: int = 30
    pause_after_failure: bool = False
    history_limit: int = 30

    def __post_init__(self) -> None:
        _finite(self.local_cooldown_temperature_c, 'local_cooldown_temperature_c')
        if not 30 <= float(self.local_cooldown_temperature_c) <= 110:
            raise ValueError('local_cooldown_temperature_c must be between 30 and 110')
        if (
            isinstance(self.local_cooldown_seconds, bool)
            or not isinstance(self.local_cooldown_seconds, int)
            or not 0 <= self.local_cooldown_seconds <= 3_600
        ):
            raise ValueError('local_cooldown_seconds must be between 0 and 3600')
        _finite(
            self.remote_non_video_cooldown_temperature_c,
            'remote_non_video_cooldown_temperature_c',
        )
        if not 30 <= float(self.remote_non_video_cooldown_temperature_c) <= 110:
            raise ValueError('remote_non_video_cooldown_temperature_c must be between 30 and 110')
        if (
            isinstance(self.remote_non_video_cooldown_seconds, bool)
            or not isinstance(self.remote_non_video_cooldown_seconds, int)
            or not 0 <= self.remote_non_video_cooldown_seconds <= 3_600
        ):
            raise ValueError('remote_non_video_cooldown_seconds must be between 0 and 3600')
        if not isinstance(self.thermal, ThermalPolicy):
            raise TypeError("thermal must be a ThermalPolicy")
        if (
            isinstance(self.remote_video_cooldown_seconds, bool)
            or not isinstance(self.remote_video_cooldown_seconds, int)
            or not 0 <= self.remote_video_cooldown_seconds <= 3_600
        ):
            raise ValueError("remote_video_cooldown_seconds must be between 0 and 3600")
        if not isinstance(self.pause_after_failure, bool):
            raise TypeError("pause_after_failure must be a boolean")
        if (
            isinstance(self.history_limit, bool)
            or not isinstance(self.history_limit, int)
            or not 5 <= self.history_limit <= 200
        ):
            raise ValueError("history_limit must be between 5 and 200")


@dataclass(frozen=True, slots=True)
class ThermalSnapshot:
    local_temperature_c: float | None = None
    remote_temperature_c: float | None = None
    local_error: str | None = None
    remote_error: str | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.local_temperature_c, "local_temperature_c"),
            (self.remote_temperature_c, "remote_temperature_c"),
        ):
            if value is not None:
                temperature = _finite(value, label)
                if not 0 <= temperature <= 150:
                    raise ValueError(f"{label} must be between 0 and 150")
        for value, label in (
            (self.local_error, "local_error"),
            (self.remote_error, "remote_error"),
        ):
            if value is not None:
                _text(value, label, 1_000)


def _text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if not value.strip():
        raise ValueError(f"{label} must not be empty")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return value.strip()


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    if not math.isfinite(float(value)):
        raise ValueError(f"{label} must be finite")
    return float(value)


__all__ = [
    "ComputeResource",
    "ComputeResourceState",
    "ComputeResourceStatus",
    "ProductionWorkload",
    "ThermalPolicy",
    "ThermalSnapshot",
    "WorkSchedulerSettings",
]
