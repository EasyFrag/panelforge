"""Application boundary for controlling the external model runtime."""

from __future__ import annotations

from typing import Protocol


class ModelRuntimeControl(Protocol):
    """Minimal control surface needed by the Lab."""

    def unload_all(self) -> None: ...

    def running_models(self) -> tuple[str, ...]: ...
