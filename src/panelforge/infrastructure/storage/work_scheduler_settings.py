"""Persistent global settings for the two PanelForge execution lanes."""

from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
from time import sleep

from panelforge.domain.production import ThermalPolicy, WorkSchedulerSettings


_REPLACE_RETRY_DELAYS = (0.02, 0.05, 0.1, 0.2, 0.4)


class LocalWorkSchedulerSettings:
    def __init__(self, workspace) -> None:
        root = Path(workspace).resolve() / "system"
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "work-scheduler.json"
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
            remote_video_cooldown_seconds=value.get("remote_video_cooldown_seconds", 30),
            pause_after_failure=value.get("pause_after_failure", False),
            history_limit=value.get("history_limit", 30),
        )

    def save(self, settings: WorkSchedulerSettings) -> WorkSchedulerSettings:
        if not isinstance(settings, WorkSchedulerSettings):
            raise TypeError("settings must be WorkSchedulerSettings")
        value = {
            "schema_version": 1,
            "thermal": asdict(settings.thermal),
            "remote_video_cooldown_seconds": settings.remote_video_cooldown_seconds,
            "pause_after_failure": settings.pause_after_failure,
            "history_limit": settings.history_limit,
        }
        content = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")
        with self._lock:
            descriptor, temporary_name = tempfile.mkstemp(
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
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
                        os.replace(temporary, self.path)
                        break
                    except PermissionError:
                        if attempt == len(_REPLACE_RETRY_DELAYS):
                            raise
                        sleep(_REPLACE_RETRY_DELAYS[attempt])
            finally:
                temporary.unlink(missing_ok=True)
        return settings


__all__ = ["LocalWorkSchedulerSettings"]
