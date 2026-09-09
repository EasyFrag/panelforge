"""Prepare an ordinary Edit workshop using a fixed scene and an Assisted subject.

Preparation never calls the LLM, uploads to ComfyUI or queues a generation.
"""

import hashlib
import math

from panelforge.domain.edit_subject_reference import EditSubjectReference
from panelforge.domain.krea2_edit import Krea2EditMetadata, Krea2EditSource
from panelforge.domain.krea2_lab import Krea2AspectRatio


DEFAULT_INSTRUCTION = (
    "Place the subject from image 2 into the scene of image 1. Preserve the subject's "
    "appearance, outfit, action and relevant props from image 2. Adapt their scale, "
    "placement, contact shadows and reflections to image 1. Keep the architecture, "
    "camera angle and lighting of image 1. Let the floor materials and objects change "
    "as required by the action. Produce one coherent photograph."
)

PROMPT_CONTEXT = (
    "\n\nTWO-IMAGE IDENTITY EDIT CONTRACT:\n"
    "The renderer receives STAGE SOURCE as image 1 (scene/camera/architecture) and "
    "SUBJECT REFERENCE as image 2 (subject, appearance, action and requested props). "
    "Both are real render inputs and remain fixed throughout this stage. "
    "GENERATED FEEDBACK, when present, is a separate evaluation image, never a render input. "
    "Write a targeted edit instruction with explicit roles for image 1 and image 2. "
    "Preserve the scene's architecture and requested framing; adapt the subject's "
    "scale, placement, light, contact shadows and reflections to it. "
    "Distinguish fixed room structure from changing floor contents, tools and materials. "
    "Take the user's latest changes as authoritative. Never promise exact preservation "
    "or describe both reference backgrounds as the desired room."
)


class RestagingConflictError(ValueError):
    pass


def create(service, project, attempt_id, *, scene_asset_id, instruction, request_id):
    if service.edit_images is None:
        raise ValueError("Le décodage des images n’est pas configuré.")
    workflow = next((w for w in service.workflows if getattr(w, "requires_subject_reference", False)), None)
    if workflow is None:
        raise ValueError("Le workflow décor + sujet n’est pas configuré.")
    attempt = project.attempt(attempt_id)
    if attempt.status.value != "succeeded" or attempt.output_asset_id is None:
        raise ValueError("Choisis une image Assisted réussie.")
    if not isinstance(instruction, str):
        raise ValueError("L’instruction est obligatoire.")
    subject = EditSubjectReference(attempt.output_asset_id, project.attempt_label(attempt_id),
        project.project_id, attempt_id, request_id, instruction.strip())
    digest = hashlib.sha256(f"{project.project_id}/{attempt_id}/{request_id}".encode()).hexdigest()
    source_id = f"krea2-restage-{digest[:32]}"
    with service._lock:
        try:
            existing = service.sources.get(source_id)
        except (KeyError, FileNotFoundError):
            existing = None
        if existing is not None:
            if existing.source_asset_id != scene_asset_id or existing.subject_reference != subject:
                raise RestagingConflictError("Cette requête correspond déjà à un autre atelier décor + sujet.")
            return existing
        dimensions = {}
        for asset_id in dict.fromkeys((scene_asset_id, subject.asset_id)):
            if service.assets.get(asset_id).media_type not in {"image/png", "image/jpeg", "image/webp"}:
                raise ValueError("Les références doivent être des images PNG, JPEG ou WebP.")
            dimensions[asset_id] = service.edit_images.dimensions(service.assets.read_bytes(asset_id))
        width, height = dimensions[scene_asset_id]
        ratio = min(Krea2AspectRatio, key=lambda r: abs(math.log((r.dimensions[0] / r.dimensions[1]) / (width / height))))
        defaults = workflow.defaults
        source = Krea2EditSource(source_id=source_id, recipe=workflow.reference,
            source_asset_id=scene_asset_id, filename=f"Decor - {project.name}",
            subject_reference=subject,
            instruction=subject.initial_instruction,
            metadata=Krea2EditMetadata(prompt=subject.initial_instruction,
                model_name=defaults["model_id"], aspect_ratio=ratio, megapixels=1.0,
                ref_boost=defaults["ref_boost"], steps=defaults["steps"], origin="assisted-restaging"))
        return service.sources.create(source)
