"""Server-side temperature sources used by long-running production jobs."""

from __future__ import annotations

from collections.abc import Callable
import json
from threading import RLock
import time
from typing import Any

from panelforge.domain.production import ThermalSnapshot


class CrystoolsRemoteGpuMonitor:
    """Read one Crystools telemetry event without depending on an open browser."""

    def __init__(
        self,
        websocket_url: str,
        *,
        timeout: float = 3.0,
        cache_seconds: float = 1.5,
        connector: Callable[[str, float], Any] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(websocket_url, str) or not websocket_url.strip():
            raise ValueError("websocket_url must not be empty")
        if timeout <= 0 or cache_seconds < 0:
            raise ValueError("remote monitor timings are invalid")
        self.websocket_url = websocket_url
        self.timeout = timeout
        self.cache_seconds = cache_seconds
        self._connector = connector or _connect
        self._monotonic = monotonic
        self._lock = RLock()
        self._cached: tuple[float, float] | None = None

    def get_temperature(self) -> float:
        now = self._monotonic()
        with self._lock:
            if self._cached is not None and now - self._cached[0] <= self.cache_seconds:
                return self._cached[1]
        deadline = now + self.timeout
        with self._connector(self.websocket_url, self.timeout) as connection:
            while True:
                remaining = deadline - self._monotonic()
                if remaining <= 0:
                    raise TimeoutError("Crystools temperature telemetry timed out")
                message = connection.recv(timeout=remaining)
                temperature = _temperature_from_message(message)
                if temperature is None:
                    continue
                with self._lock:
                    self._cached = (self._monotonic(), temperature)
                return temperature


class CombinedProductionThermalMonitor:
    def __init__(self, *, local: Any | None, remote: Any | None) -> None:
        self.local = local
        self.remote = remote

    def snapshot(self) -> ThermalSnapshot:
        local_temperature = None
        remote_temperature = None
        local_error = None
        remote_error = None
        if self.local is None:
            local_error = "GPU local non configuré."
        else:
            try:
                local_temperature = float(self.local.get_stats().temperature_c)
            except Exception as error:
                local_error = _error(error, "GPU local indisponible.")
        if self.remote is None:
            remote_error = "Télémétrie GPU distante non configurée."
        else:
            try:
                remote_temperature = float(self.remote.get_temperature())
            except Exception as error:
                remote_error = _error(error, "Télémétrie GPU distante indisponible.")
        return ThermalSnapshot(
            local_temperature_c=local_temperature,
            remote_temperature_c=remote_temperature,
            local_error=local_error,
            remote_error=remote_error,
        )


def _connect(url: str, timeout: float):
    from websockets.sync.client import connect

    return connect(url, open_timeout=timeout, close_timeout=1.0)


def _temperature_from_message(message: object) -> float | None:
    if not isinstance(message, str):
        return None
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("type") != "crystools.monitor":
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    gpus = data.get("gpus")
    if not isinstance(gpus, list) or not gpus or not isinstance(gpus[0], dict):
        return None
    value = gpus[0].get("gpu_temperature")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    temperature = float(value)
    if not 0 <= temperature <= 150:
        return None
    return temperature


def _error(error: Exception, fallback: str) -> str:
    value = str(error).strip()
    return value[:1_000] if value else fallback


__all__ = [
    "CombinedProductionThermalMonitor",
    "CrystoolsRemoteGpuMonitor",
]
