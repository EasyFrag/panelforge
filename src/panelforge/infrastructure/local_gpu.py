"""Local NVIDIA GPU telemetry exposed through ``nvidia-smi``."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import subprocess
from threading import Lock
from time import monotonic
from typing import Any, Callable


_MIB = 1024**2


@dataclass(frozen=True)
class LocalGpuStats:
    """A single local GPU snapshot, normalized for the Lab runtime API."""

    name: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_percent: float
    temperature_c: float | None


class NvidiaSmiMonitor:
    """Read one NVIDIA GPU without coupling PanelForge to an NVIDIA SDK."""

    def __init__(
        self,
        *,
        gpu_index: int = 0,
        timeout: float = 2.0,
        cache_seconds: float = 0.8,
        runner: Callable[..., Any] = subprocess.run,
    ) -> None:
        self._gpu_index = gpu_index
        self._timeout = timeout
        self._cache_seconds = max(0.0, cache_seconds)
        self._runner = runner
        self._cached: LocalGpuStats | None = None
        self._cached_at = 0.0
        self._lock = Lock()

    def get_stats(self) -> LocalGpuStats:
        """Return cached telemetry or query ``nvidia-smi`` with a short timeout."""
        with self._lock:
            now = monotonic()
            if self._cached is not None and now - self._cached_at < self._cache_seconds:
                return self._cached
            result = self._runner(
                [
                    "nvidia-smi",
                    f"--id={self._gpu_index}",
                    "--query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=self._timeout,
            )
            snapshot = _parse_nvidia_smi(result.stdout)
            self._cached = snapshot
            self._cached_at = now
            return snapshot


def _parse_nvidia_smi(output: str) -> LocalGpuStats:
    rows = [row for row in csv.reader(output.splitlines()) if row]
    if not rows or len(rows[0]) != 5:
        raise ValueError("unexpected nvidia-smi output")
    name, total_mib, used_mib, free_mib, temperature = (
        value.strip() for value in rows[0]
    )
    total_bytes = _mib_to_bytes(total_mib)
    used_bytes = _mib_to_bytes(used_mib)
    free_bytes = _mib_to_bytes(free_mib)
    if total_bytes <= 0:
        raise ValueError("invalid local GPU memory total")
    return LocalGpuStats(
        name=name,
        total_bytes=total_bytes,
        used_bytes=used_bytes,
        free_bytes=free_bytes,
        used_percent=round((used_bytes / total_bytes) * 100, 1),
        temperature_c=_optional_float(temperature),
    )


def _mib_to_bytes(value: str) -> int:
    return int(float(value) * _MIB)


def _optional_float(value: str) -> float | None:
    if value.casefold() in {"n/a", "[n/a]", "not supported"}:
        return None
    return float(value)
