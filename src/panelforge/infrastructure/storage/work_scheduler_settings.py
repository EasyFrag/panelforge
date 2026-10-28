"""Persistent global settings for the two PanelForge execution lanes."""

from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
from time import sleep

from panelforge.domain.production import (
    ComputeResource, GlobalThermalPause, ThermalPolicy, WorkSchedulerSettings,
)


_REPLACE_RETRY_DELAYS = (0.02, 0.05, 0.1, 0.2, 0.4)


class LocalWorkSchedulerSettings:
    def __init__(self, workspace) -> None:
        root = Path(workspace).resolve() / "system"
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "work-scheduler.json"
        self.pause_path = root / "work-thermal-pause.json"
        self._lock = RLock()

    def load(self) -> WorkSchedulerSettings:
        with self._lock:
            if not self.path.exists():
                return WorkSchedulerSettings(
                    thermal=ThermalPolicy(pause_when_unavailable=False)
                )
            value = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError("Version des paramètres globaux de traitement inconnue.")
        thermal = value.get("thermal")
        if not isinstance(thermal, dict):
            raise ValueError("Protection thermique globale invalide.")
        return WorkSchedulerSettings(
            thermal=ThermalPolicy(**thermal),
            local_cooldown_temperature_c=value.get('local_cooldown_temperature_c', 80),
            local_cooldown_seconds=value.get('local_cooldown_seconds', 80),
            remote_non_video_cooldown_temperature_c=value.get(
                'remote_non_video_cooldown_temperature_c', 80,
            ),
            remote_non_video_cooldown_seconds=value.get(
                'remote_non_video_cooldown_seconds', 80,
            ),
            remote_video_cooldown_seconds=value.get("remote_video_cooldown_seconds", 30),
            pause_after_failure=value.get("pause_after_failure", False),
            history_limit=value.get("history_limit", 30),
            global_thermal_pause_enabled=value.get("global_thermal_pause_enabled", True),
            global_thermal_pause_temperature_c=value.get("global_thermal_pause_temperature_c", 86),
        )

    def save(self, settings: WorkSchedulerSettings) -> WorkSchedulerSettings:
        if not isinstance(settings, WorkSchedulerSettings):
            raise TypeError("settings must be WorkSchedulerSettings")
        value = {
            'local_cooldown_temperature_c': settings.local_cooldown_temperature_c,
            'local_cooldown_seconds': settings.local_cooldown_seconds,
            'remote_non_video_cooldown_temperature_c': settings.remote_non_video_cooldown_temperature_c,
            'remote_non_video_cooldown_seconds': settings.remote_non_video_cooldown_seconds,
            "schema_version": 1,
            "thermal": asdict(settings.thermal),
            "remote_video_cooldown_seconds": settings.remote_video_cooldown_seconds,
            "pause_after_failure": settings.pause_after_failure,
            "history_limit": settings.history_limit,
            "global_thermal_pause_enabled": settings.global_thermal_pause_enabled,
            "global_thermal_pause_temperature_c": settings.global_thermal_pause_temperature_c,
        }
        self._write(self.path, value)
        return settings

    def load_global_thermal_pause(self) -> GlobalThermalPause | None:
        with self._lock:
            if not self.pause_path.exists():
                return None
            value = json.loads(self.pause_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError("Version de la pause thermique globale inconnue.")
        incident = value.get("incident")
        if incident is None:
            return None
        if not isinstance(incident, dict):
            raise ValueError("Incident thermique global invalide.")
        return GlobalThermalPause(**{**incident, "resource": ComputeResource(incident["resource"])})

    def save_global_thermal_pause(self, incident: GlobalThermalPause | None) -> None:
        if incident is not None and not isinstance(incident, GlobalThermalPause):
            raise TypeError("incident must be a GlobalThermalPause or None")
        self._write(self.pause_path, {
            "schema_version": 1,
            "incident": asdict(incident) if incident is not None else None,
        })

    def _write(self, path: Path, value: dict) -> None:
        content = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")
        with self._lock:
            descriptor, temporary_name = tempfile.mkstemp(
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                for attempt in range(len(_REPLACE_RETRY_DELAYS) + 1):
                    try:
                        os.replace(temporary, path)
                        break
                    except PermissionError:
                        if attempt == len(_REPLACE_RETRY_DELAYS):
                            raise
                        sleep(_REPLACE_RETRY_DELAYS[attempt])
            finally:
                temporary.unlink(missing_ok=True)


__all__ = ["LocalWorkSchedulerSettings"]
