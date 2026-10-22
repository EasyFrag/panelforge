"""Http support for the PanelForge Lab HTTP interface."""

from __future__ import annotations
from fastapi import HTTPException
from contextlib import contextmanager
from collections.abc import Iterator


def _serialize_llm_model(model) -> dict[str, object]:
    model_id = model.model_id
    display_name = getattr(model, "display_name", None) or model_id
    source = getattr(model, "source", "server") or "server"
    return {
        "id": model_id,
        "label": display_name,
        "source": source,
    }


def _parse_seed(value: str) -> int:
    if not isinstance(value, str) or not value or not value.isdecimal():
        raise ValueError("seed must be an unsigned decimal integer")
    seed = int(value)
    if not 0 <= seed < 2**64:
        raise ValueError("seed must be between 0 and 2^64 - 1")
    return seed


def _parse_json_seed(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("seed must be an unsigned decimal integer")
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str):
        raise ValueError("seed must be an unsigned decimal integer")
    return _parse_seed(value)


@contextmanager
def http_errors(
    not_found: str,
    *,
    missing: tuple[type[Exception], ...] = (KeyError, FileNotFoundError),
    invalid: tuple[type[Exception], ...] = (TypeError, ValueError),
) -> Iterator[None]:
    """Preserve the shared 404/422 mapping; workshop conflicts stay local."""
    try:
        yield
    except missing as error:
        raise HTTPException(status_code=404, detail=not_found) from error
    except invalid as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
