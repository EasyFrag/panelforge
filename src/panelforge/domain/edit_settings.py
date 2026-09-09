"""Shared records for independently versioned image-edit engines."""

from .firered_edit import FireRedEditSettings
from .krea2_edit import Krea2EditAttempt, Krea2EditSettings, Krea2EditSource

EditSettings = Krea2EditSettings | FireRedEditSettings


def edit_engine(settings: EditSettings) -> str:
    return "firered" if isinstance(settings, FireRedEditSettings) else "krea2"


def edit_settings_record(settings: EditSettings, *, string_seed: bool = True) -> dict[str, object]:
    result = {
        "engine": edit_engine(settings), "model_name": settings.model_name,
        "megapixels": settings.megapixels, "seed": str(settings.seed) if string_seed else settings.seed,
        "steps": settings.steps,
    }
    if isinstance(settings, FireRedEditSettings):
        result.update(mode=settings.mode, cfg=settings.cfg, aspect_ratio="source")
    else:
        result.update(aspect_ratio=settings.aspect_ratio.value, ref_boost=settings.ref_boost,
                      loras=[{"name": value.name, "strength": value.strength} for value in settings.loras])
    return result


def edit_output_dimensions(attempt: Krea2EditAttempt) -> tuple[int, int] | None:
    if attempt.retouch:
        return attempt.retouch.width, attempt.retouch.height
    if attempt.upscale:
        return attempt.upscale.width, attempt.upscale.height
    if attempt.output_dimensions:
        return attempt.output_dimensions
    # KREA2's existing contract computes its target resolution. FireRed follows
    # the actual source ratio; only decoded output dimensions are authoritative.
    return attempt.settings.resolution if isinstance(attempt.settings, Krea2EditSettings) else None


def edit_render_dimensions(source: Krea2EditSource, attempt: Krea2EditAttempt) -> tuple[int, int] | None:
    while attempt.kind != "generation":
        original_id = (attempt.upscale.original_attempt_id if attempt.upscale
                       else attempt.retouch.original_attempt_id)
        attempt = next(value for value in source.attempts if value.attempt_id == original_id)
    return edit_output_dimensions(attempt)
