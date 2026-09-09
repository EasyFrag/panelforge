"""Optional enhancement of a selected Edit candidate, using the existing render lifecycle."""

from dataclasses import dataclass, replace
from typing import Protocol

from panelforge.domain.krea2_edit import Krea2EditAttempt, Krea2EditAttemptStatus, Krea2EditUpscale
from panelforge.domain.recipes import RecipeRef


@dataclass(frozen=True, slots=True)
class UpscaleInput:
    image_png: bytes
    width: int
    height: int


class UpscaleImages(Protocol):
    def prepare(self, source: bytes, generated: bytes) -> UpscaleInput: ...
    def normalize_output(self, content: bytes, width: int, height: int) -> bytes: ...


class UpscaleWorkflow(Protocol):
    reference: RecipeRef
    preferred_model: str
    output_node_id: str
    output_history_field: str
    output_media_type: str
    def build(self, *, source_image: str, model_name: str, width: int, height: int, output_prefix: str) -> dict: ...


def generation_asset(attempt: Krea2EditAttempt) -> str:
    asset_id = attempt.upscale.enhanced_asset_id if attempt.upscale else attempt.output_asset_id
    if not asset_id:
        raise ValueError("L’image générée est indisponible.")
    return asset_id


def mask_settings(attempt):
    return attempt.retouch or attempt.upscale


def prepare_upscale(service, source_id, parent_id, *, model_name, request_id):
    if service.upscale_workflow is None or service.upscale_images is None:
        raise ValueError("L’amélioration des détails n’est pas configurée.")
    with service._lock:
        source = service.sources.get(source_id)
        for attempt in source.attempts:
            if attempt.upscale and attempt.upscale.request_id == request_id:
                if attempt.upscale.parent_attempt_id != parent_id or attempt.upscale.model_name != model_name:
                    raise ValueError("Cette demande correspond déjà à une autre amélioration.")
                return source, attempt
        service._require_editable(source)
        selected = next((a for a in source.attempts if a.attempt_id == parent_id), None)
        if selected is None or selected.status is not Krea2EditAttemptStatus.SUCCEEDED:
            raise ValueError("Choisis un essai réussi à améliorer.")
        original = selected
        while original.kind != "generation":
            original_id = original.upscale.original_attempt_id if original.upscale else original.retouch.original_attempt_id
            original = next(a for a in source.attempts if a.attempt_id == original_id)
        mask = mask_settings(selected)
    # Read-only inventory and image validation happen before creating a candidate.
    if model_name not in service.comfy.list_upscale_models():
        raise ValueError("Cet upscaler n’est plus disponible dans ComfyUI. Recharge la liste.")
    prepared = service.upscale_images.prepare(service.assets.read_bytes(source.source_asset_id),
                                             service.assets.read_bytes(original.output_asset_id))
    info = Krea2EditUpscale(
        original_attempt_id=original.attempt_id, parent_attempt_id=parent_id,
        input_asset_id=original.output_asset_id, model_name=model_name, request_id=request_id,
        workflow=service.upscale_workflow.reference, width=prepared.width, height=prepared.height,
        mask_asset_id=mask.mask_asset_id if mask else None,
        harmonize=mask.harmonize if mask else False,
        harmonize_strength=mask.harmonize_strength if mask else 100,
    )
    if info.mask_asset_id and service.retouch_compositor is None:
        raise ValueError("Le compositeur de masque est indisponible.")
    with service._lock:
        current = service.sources.get(source_id)
        service._require_editable(current)
        if current.restart_count != source.restart_count:
            raise ValueError("L’étape a été recommencée. Recharge l’atelier.")
        for attempt in current.attempts:
            if attempt.upscale and attempt.upscale.request_id == request_id:
                if replace(attempt.upscale, enhanced_asset_id=None) != info:
                    raise ValueError("Cette demande correspond déjà à une autre amélioration.")
                return current, attempt
        candidate = Krea2EditAttempt(attempt_id=service._attempt_id_factory(), prompt=original.prompt,
                                     settings=original.settings, recipe=original.recipe or source.recipe,
                                     kind="upscale", upscale=info)
        return service.sources.save(replace(current, attempts=(*current.attempts, candidate))), candidate


def finish_upscale(service, source, attempt, content):
    info = attempt.upscale
    normalized = service.upscale_images.normalize_output(content, info.width, info.height)
    output = normalized
    if info.mask_asset_id:
        output = service.retouch_compositor.compose(
            service.assets.read_bytes(source.source_asset_id), normalized,
            service.assets.read_bytes(info.mask_asset_id),
            harmonize=info.harmonize, harmonize_strength=info.harmonize_strength,
        ).output_png
    enhanced = service.assets.create(normalized, media_type="image/png", source_run_id=source.source_id)
    composed = (service.assets.create(output, media_type="image/png", source_run_id=source.source_id)
                if info.mask_asset_id else enhanced)
    return replace(attempt, status=Krea2EditAttemptStatus.SUCCEEDED, output_asset_id=composed.asset_id,
                   upscale=replace(info, enhanced_asset_id=enhanced.asset_id), error=None)
