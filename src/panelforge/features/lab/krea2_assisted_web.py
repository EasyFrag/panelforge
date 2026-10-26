"""Krea2 assisted web for the PanelForge Lab HTTP interface."""

from __future__ import annotations
from typing import TypedDict
from .http_support import http_errors
from panelforge.domain.krea2_sampling import Krea2AssistedSettings, sampling_for, sampling_from_dict, sampling_spec
from panelforge.domain.krea2_assisted_workflows import workflow_selection_from_dict
from panelforge.domain.krea2_style_presets import Krea2StylePresetCategory
from dataclasses import asdict
from urllib.parse import quote
from time import perf_counter
from typing import Annotated, Any, Literal
from panelforge.application.krea2_restage import DEFAULT_INSTRUCTION as RESTAGING_INSTRUCTION, RestagingConflictError
from fastapi import File, Form, HTTPException, UploadFile, status, Query
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from panelforge.application import ChangeViewRunner, Krea2AssistedService, Krea2EditService, parse_krea2_assisted_recipe_draft
from panelforge.domain import Krea2AssistedProject, Krea2AssistedTurnMode, Krea2AspectRatio, Krea2BatchSettings, Krea2LoraSelection, Krea2PromptLanguage
from fastapi import APIRouter
from .http_streaming import stream_response
from .http_support import _parse_json_seed, _serialize_llm_model
from .krea2_edit_web import _require_krea2_edit, serialize_krea2_edit_source
from .krea2_resources_web import Krea2LoraBody
from .media_http import MAX_IMAGE_BYTES, detect_image_media_type


class Krea2RestageBody(BaseModel):
    scene_asset_id: str = Field(min_length=1)
    instruction: str = Field(min_length=1, max_length=12_000)
    request_id: str = Field(min_length=1, max_length=80)


class Krea2AssistedChatBody(BaseModel):
    message: str
    current_prompt: str | None = None
    mode: str = "creation"
    model_id: str | None = None
    feedback_attempt_id: str | None = None
    prompt_language: str | None = None
    guidance_asset_id: str | None = None
    guidance_filename: str | None = None
    expected_branch_id: str | None = None
    refresh_prompt_examples: bool = True


class Krea2AssistedAttemptBody(BaseModel):
    prompt: str
    model_id: str
    aspect_ratio: str
    megapixels: float
    seed: str | int | None = None
    loras: list[Krea2LoraBody] | None = None
    expected_branch_id: str | None = None
    sampling: dict[str, Any] | None = None
    workflow: str | None = None
    prompt_language: Literal["en", "zh"] | None = None


class Krea2AssistedBranchBody(BaseModel):
    expected_branch_id: str
    branch_id: str | None = None
    attempt_id: str | None = None
    image_prompt_only: bool = False
    draft: Krea2AssistedAttemptBody | None = None
    prompt_language: str | None = None
    model_id: str | None = None


def _krea2_assisted_settings(body: Krea2AssistedAttemptBody) -> Krea2AssistedSettings:
    workflow = workflow_selection_from_dict(body.workflow)
    default_sampling = "moody_beta" if workflow.recipe_id == "krea2-flux-klein" else "current"
    return Krea2AssistedSettings(
        sampling=sampling_from_dict(body.sampling, default_preset_id=default_sampling),
        workflow=workflow,
        model_name=body.model_id,
        aspect_ratio=Krea2AspectRatio(body.aspect_ratio),
        megapixels=body.megapixels,
        loras=tuple(
            Krea2LoraSelection(name=value.name, strength=value.strength)
            for value in (body.loras or [])
        ),
    )


class Krea2StylePresetSaveBody(BaseModel):
    project_id: str
    attempt_id: str
    name: str = Field(min_length=1, max_length=120)
    preset_id: str | None = None
    expected_revision: int | None = None
    category: Literal["work", "fun", "nsfw", "archive"] | None = None


class Krea2StylePresetUpdateBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: Literal["work", "fun", "nsfw", "archive"]
    expected_revision: int = Field(ge=1, strict=True)


class Krea2StylePresetDeleteBody(BaseModel):
    expected_revision: int = Field(ge=1, strict=True)


class Krea2StylePresetApplyBody(BaseModel):
    preset_id: str | None = None
    expected_branch_id: str
    draft: Krea2AssistedAttemptBody


class Krea2ArtDirectionApplyBody(BaseModel):
    style_id: str | None = Field(default=None, max_length=240)
    expected_branch_id: str
    draft: Krea2AssistedAttemptBody


class Krea2AssistedFeedbackBody(BaseModel):
    attempt_id: str | None = None


class Krea2AssistedPromptExampleBody(BaseModel):
    example_id: str = Field(min_length=1, max_length=128)
    expected_branch_id: str


class Krea2AssistedExpectedBranchBody(BaseModel):
    expected_branch_id: str


class Krea2AssistedLocalInspirationBody(BaseModel):
    enabled: bool
    expected_branch_id: str


class Krea2AssistedRecipeDraftBody(BaseModel):
    recipe_id: str
    display_name: str
    description: str
    identity: str
    invariants: list[str]
    variables: list[str]
    risks: list[str]
    canonical_prompt: str


class Krea2AssistedRecipePublishBody(BaseModel):
    draft: Krea2AssistedRecipeDraftBody | None = None


def serialize_krea2_visual_recipe(recipe) -> dict[str, object]:
    return {
        "id": recipe.recipe_id,
        "recipe_id": recipe.recipe_id,
        "version": recipe.version,
        "display_name": recipe.display_name,
        "description": recipe.description,
        "identity": recipe.identity,
        "invariants": list(recipe.invariants),
        "variables": list(recipe.variables),
        "risks": list(recipe.risks),
        "canonical_prompt": recipe.canonical_prompt,
        "prompt_language": recipe.prompt_language.value,
        "content_sha256": recipe.content_sha256,
        "parent_version": recipe.parent_version,
        "status": recipe.status,
        "settings": {
            "model_id": recipe.settings.model_name,
            "aspect_ratio": recipe.settings.aspect_ratio.value,
            "megapixels": recipe.settings.megapixels,
            "loras": [
                {"name": lora.name, "strength": lora.strength}
                for lora in recipe.settings.loras
            ],
        },
    }


def _serialize_krea2_style_preset(preset) -> dict[str, object] | None:
    if preset is None:
        return None
    return {
        "preset_id": preset.preset_id, "revision": preset.revision, "name": preset.name,
        "prompt": preset.prompt, "image_url": f"/api/assets/{preset.image_asset_id}/content",
        "settings": _serialize_krea2_assisted_settings(preset.settings),
        "source_project_id": preset.source_project_id, "source_attempt_id": preset.source_attempt_id,
        "source_seed": str(preset.source_seed), "prompt_language": preset.prompt_language.value,
        "category": preset.category.value,
        "art_direction": _serialize_krea2_art_direction(preset.art_direction),
    }


def _serialize_krea2_art_direction(direction) -> dict[str, object] | None:
    if direction is None:
        return None
    return {
        "provider_id": direction.provider_id,
        "style_id": direction.style_id,
        "name": direction.name,
        "display_name": direction.display_name,
        "category": direction.category,
        "prompt": direction.prompt,
        "catalog_revision": direction.catalog_revision,
        "thumbnail_url": (
            "/api/image-lab/krea2-assisted/art-styles/thumbnail?style_id="
            + quote(direction.style_id, safe="")
        ),
    }


class Krea2AssistedProjectPayload(TypedDict):
    id: str
    active_branch_id: str
    composition_base_asset_id: str | None
    local_inspiration_enabled: bool
    prompt_examples: list[dict[str, object]]
    selected_prompt_example_id: str | None
    prompt_example_search_brief: dict[str, object] | None
    branches: list[dict[str, object]]
    render_settings: dict[str, object] | None
    style_preset: dict[str, object] | None
    art_direction: dict[str, object] | None
    preset_pending: bool
    render_seed: str | None
    project_id: str
    name: str
    intention: str
    model_id: str
    assistance_recipe_version: str
    revision_model_id: str | None
    prompt_language: str
    reference_asset_id: str | None
    reference_filename: str | None
    reference_url: str | None
    turns: list[dict[str, object]]
    current_prompt: str | None
    attempts: list[dict[str, object]]
    feedback_attempt_id: str | None
    accepted_attempt_id: str | None
    recipe_draft: dict[str, object] | None
    published_recipe: dict[str, object] | None
    export: dict[str, object]
    warnings: list[str]


def serialize_krea2_assisted_project(
    project: Krea2AssistedProject,
    *,
    include_prompt_examples: bool = True,
) -> Krea2AssistedProjectPayload:
    draft = project.recipe_draft
    branches = []
    for branch in project.conversation_branches():
        preview = next((a for a in reversed(project.attempts)
                        if a.output_asset_id and (a.conversation_branch_id == branch.branch_id
                            or (branch.branch_id == "main" and a.conversation_branch_id is None))), None)
        if preview is None and branch.source_attempt_id:
            preview = project.attempt(branch.source_attempt_id)
        branches.append({
            "branch_id": branch.branch_id, "name": branch.name,
            "parent_branch_id": branch.parent_branch_id, "source_attempt_id": branch.source_attempt_id,
            "turn_count": len(branch.turns),
            "preview_url": f"/api/assets/{preview.output_asset_id}/content" if preview and preview.output_asset_id else None,
        })
    return {
        "id": project.project_id,
        "active_branch_id": project.active_branch_id,
        "composition_base_asset_id": project.composition_base_asset_id,
        "local_inspiration_enabled": project.local_inspiration_enabled,
        "prompt_examples": [
            {
                "example_id": example.example_id,
                "source_file": example.source_file,
                "source_line": example.source_line,
                "digest": example.digest,
                "prompt": example.prompt,
                "score": example.score,
                "relevance": example.relevance,
                "actions": list(example.actions),
                "participants": list(example.participants),
                "interactions": list(example.interactions),
                "positions": list(example.positions),
                "framings": list(example.framings),
                "settings": list(example.settings),
                "source_kind": example.source_kind,
                "template_id": example.template_id,
                "variant_seed": (
                    str(example.variant_seed)
                    if example.variant_seed is not None
                    else None
                ),
                "recommended_aspect_ratio": example.recommended_aspect_ratio,
                "preview_url": (
                    "/api/image-lab/krea2-assisted/wildcard-preview?template_id="
                    + example.template_id
                    if example.source_kind == "wildcard" and example.template_id
                    else None
                ),
                "selected": example.example_id == project.selected_prompt_example_id,
            }
            for example in project.prompt_examples
        ] if include_prompt_examples else [],
        "selected_prompt_example_id": project.selected_prompt_example_id,
        "prompt_example_search_brief": (
            asdict(project.prompt_example_search_brief)
            if project.prompt_example_search_brief is not None
            else None
        ),
        "branches": branches,
        "render_settings": _serialize_krea2_assisted_settings(project.render_settings),
        "style_preset": _serialize_krea2_style_preset(project.style_preset),
        "art_direction": _serialize_krea2_art_direction(project.art_direction),
        "preset_pending": project.preset_pending,
        "render_seed": str(project.render_seed) if project.render_seed is not None else None,
        "project_id": project.project_id,
        "name": project.name,
        "intention": project.intention,
        "model_id": project.model_id,
        "assistance_recipe_version": project.assistance_recipe_version,
        "revision_model_id": project.revision_model_id,
        "prompt_language": project.prompt_language.value,
        "reference_asset_id": project.reference_asset_id,
        "reference_filename": project.reference_filename,
        "reference_url": (
            f"/api/assets/{project.reference_asset_id}/content"
            if project.reference_asset_id is not None
            else None
        ),
        "turns": [
            {
                "turn_id": turn.turn_id,
                "mode": turn.mode.value,
                "role": turn.role.value,
                "content": turn.content,
                "guidance_asset_id": turn.guidance_asset_id,
                "guidance_filename": turn.guidance_filename,
                "guidance_url": (
                    f"/api/assets/{turn.guidance_asset_id}/content"
                    if turn.guidance_asset_id is not None
                    else None
                ),
                "questions": list(turn.questions),
                "prompt": turn.prompt,
                "recommendations": list(turn.recommendations),
                "model_id": turn.model_id,
                "assistance_recipe_version": turn.assistance_recipe_version,
                "style_preset": _serialize_krea2_style_preset(turn.style_preset),
                "art_direction": _serialize_krea2_art_direction(turn.art_direction),
            }
            for turn in project.turns
        ],
        "current_prompt": project.current_prompt,
        "attempts": [
            {
                "id": attempt.attempt_id,
                "conversation_branch_id": attempt.conversation_branch_id,
                "conversation_turn_id": attempt.conversation_turn_id,
                "prompt_language": attempt.conversation_prompt_language.value,
                "can_restore_conversation": attempt.conversation_branch_id is not None,
                "attempt_id": attempt.attempt_id,
                "index": attempt.index,
                "label": project.attempt_label(attempt.attempt_id),
                "kind": attempt.kind,
                "composition": asdict(attempt.composition) if attempt.composition else None,
                "dlss": asdict(attempt.dlss) if attempt.dlss else None,
                "output_dimensions": ({"width": attempt.composition.width, "height": attempt.composition.height}
                                      if attempt.composition else {"width": attempt.dlss.width, "height": attempt.dlss.height} if attempt.dlss else None),
                "prompt": attempt.prompt,
                "canonical_prompt": attempt.canonical_prompt or attempt.prompt,
                "art_direction": _serialize_krea2_art_direction(attempt.art_direction),
                "seed": str(attempt.seed),
                "status": attempt.status.value,
                "execution_id": attempt.execution_id,
                "output_asset_id": attempt.output_asset_id,
                "output_url": (
                    f"/api/assets/{attempt.output_asset_id}/content"
                    if attempt.output_asset_id is not None
                    else None
                ),
                "pre_flux_asset_id": attempt.pre_flux_asset_id,
                "pre_flux_url": (
                    f"/api/assets/{attempt.pre_flux_asset_id}/content"
                    if attempt.pre_flux_asset_id is not None
                    else None
                ),
                "artifacts": [
                    *([{"role": "final", "asset_id": attempt.output_asset_id,
                        "url": f"/api/assets/{attempt.output_asset_id}/content"}]
                      if attempt.output_asset_id else []),
                    *([{"role": "pre_flux", "asset_id": attempt.pre_flux_asset_id,
                        "url": f"/api/assets/{attempt.pre_flux_asset_id}/content"}]
                      if attempt.pre_flux_asset_id else []),
                ],
                "output_warnings": list(attempt.output_warnings),
                "workflow": asdict(attempt.workflow) if attempt.workflow else None,
                "error": attempt.error,
                "accepted": attempt.accepted,
                "settings": {
                    "sampling": asdict(sampling_for(attempt.settings)),
                    "workflow": (
                        attempt.settings.workflow.key
                        if isinstance(attempt.settings, Krea2AssistedSettings)
                        else None
                    ),
                    "model_id": attempt.settings.model_name,
                    "aspect_ratio": attempt.settings.aspect_ratio.value,
                    "megapixels": attempt.settings.megapixels,
                    "resolution": {
                        "width": attempt.settings.resolution[0],
                        "height": attempt.settings.resolution[1],
                    },
                    "loras": [
                        {"name": value.name, "strength": value.strength}
                        for value in attempt.settings.loras
                    ],
                },
            }
            for attempt in project.attempts
        ],
        "feedback_attempt_id": project.feedback_attempt_id,
        "accepted_attempt_id": project.accepted_attempt_id,
        "recipe_draft": (
            {
                "recipe_id": draft.recipe_id,
                "display_name": draft.display_name,
                "description": draft.description,
                "identity": draft.identity,
                "invariants": list(draft.invariants),
                "variables": list(draft.variables),
                "risks": list(draft.risks),
                "canonical_prompt": draft.canonical_prompt,
                "prompt_language": draft.prompt_language.value,
            }
            if draft is not None
            else None
        ),
        "published_recipe": (
            {
                "recipe_id": project.published_recipe_id,
                "version": project.published_recipe_version,
            }
            if project.published_recipe_id is not None
            else None
        ),
        "export": {
            "status": (
                "failed"
                if project.export_error is not None
                else "exported"
                if project.export_path is not None
                else "pending"
            ),
            "path": project.export_path,
            "error": project.export_error,
        },
        "warnings": list(project.warnings),
    }


def _serialize_krea2_assisted_settings(settings: Krea2BatchSettings | None) -> dict[str, object] | None:
    if settings is None:
        return None
    return {
        "sampling": asdict(sampling_for(settings)),
        "workflow": (
            settings.workflow.key if isinstance(settings, Krea2AssistedSettings) else None
        ),
        "model_id": settings.model_name, "aspect_ratio": settings.aspect_ratio.value,
        "megapixels": settings.megapixels,
        "loras": [{"name": value.name, "strength": value.strength} for value in settings.loras],
    }


def _require_krea2_assisted(
    value: Krea2AssistedService | None,
) -> Krea2AssistedService:
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="KREA2 Assisted Creation is not configured",
        )
    return value


def krea2_assisted_router(*, image_catalogs, krea2_assisted: Krea2AssistedService | None, krea2_edit: Krea2EditService | None, runner: ChangeViewRunner) -> APIRouter:
    router = APIRouter()

    @router.get("/api/image-lab/krea2-assisted/spec")
    def krea2_assisted_spec(refresh: bool = False) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        return {
            "sampling": sampling_spec(),
            "workflows": list(service.workflow_specs()),
            "restaging": {"enabled": krea2_edit is not None and any(getattr(w, "requires_subject_reference", False) for w in krea2_edit.workflows),
                          "default_instruction": RESTAGING_INSTRUCTION},
            "assistance_recipes": service.list_assistance_recipes(),
            "prompt_library": service.prompt_example_library_status(),
            "wildcard_library": service.prompt_wildcard_library_status(),
            "art_style_catalog": service.art_style_catalog_status(),
            **image_catalogs.read(service.resources, service, _serialize_llm_model, refresh=refresh),
            "aspect_ratios": [ratio.value for ratio in Krea2AspectRatio],
            "defaults": {
                "aspect_ratio": Krea2AspectRatio.PORTRAIT_WIDESCREEN.value,
                "megapixels": 2.1,
            },
            "limits": {
                "reference_bytes": MAX_IMAGE_BYTES,
                "megapixels": {"minimum": 0.5, "maximum": 4.0, "step": 0.1},
                "lora_count": 10,
            },
            "workflow": {
                "recipe_id": getattr(service.workflow.reference, "recipe_id"),
                "version": getattr(service.workflow.reference, "version"),
                "sampler": "er_sde",
                "scheduler": "simple",
                "first_pass": {"steps": 8, "cfg": 1.1, "denoise": 1.0},
                "latent_upscale": {"method": "bislerp", "scale_by": 1.5},
                "second_pass": {"steps": 2, "cfg": 1.0, "denoise": 0.3},
            },
            "exports": {"enabled": service.export_root is not None, "root": service.export_root},
        }

    @router.post(
        "/api/image-lab/krea2-assisted/projects",
        status_code=status.HTTP_201_CREATED,
    )
    async def create_krea2_assisted_project(
        name: Annotated[str, Form()],
        model_id: Annotated[str, Form()],
        intention: Annotated[str, Form()] = "",
        reference: Annotated[UploadFile | None, File()] = None,
        assistance_recipe_version: Annotated[str, Form()] = "3.0.0",
        style_preset_id: Annotated[str | None, Form()] = None,
        art_style_id: Annotated[str | None, Form()] = None,
        prompt_language: Annotated[str | None, Form()] = None,
        local_inspiration_enabled: Annotated[bool, Form()] = True,
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        asset_id = None
        try:
            if reference is not None:
                content = await reference.read(MAX_IMAGE_BYTES + 1)
                if len(content) > MAX_IMAGE_BYTES:
                    raise ValueError("reference image exceeds the 25 MiB limit")
                media_type = detect_image_media_type(content)
                asset_id = runner.assets.create(content, media_type=media_type).asset_id
            project = service.create_project(
                assistance_recipe_version=assistance_recipe_version,
                style_preset_id=style_preset_id,
                art_style_id=art_style_id,
                name=name,
                intention=intention,
                model_id=model_id,
                prompt_language=Krea2PromptLanguage(prompt_language) if prompt_language else None,
                local_inspiration_enabled=local_inspiration_enabled,
                reference_asset_id=asset_id,
                reference_filename=(reference.filename if reference is not None else None),
            )
            return {"project": serialize_krea2_assisted_project(project)}
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Preset ou direction artistique introuvable.") from error
        except (RuntimeError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        finally:
            if reference is not None:
                await reference.close()

    @router.get("/api/image-lab/krea2-assisted/style-presets")
    def list_krea2_style_presets() -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        return {"presets": [_serialize_krea2_style_preset(p) for p in service.list_style_presets()]}

    @router.get("/api/image-lab/krea2-assisted/art-styles")
    def list_krea2_art_styles(query: str = "", category: str | None = None) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            return {
                "catalog": service.art_style_catalog_status(),
                "styles": [_serialize_krea2_art_direction(value) for value in service.list_art_styles(
                    query=query,
                    category=category,
                )],
            }
        except (RuntimeError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post("/api/image-lab/krea2-assisted/art-styles/install")
    async def install_krea2_art_styles(force: bool = False) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            catalog = await run_in_threadpool(service.install_art_style_catalog, force=force)
            return {"catalog": catalog}
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/api/image-lab/krea2-assisted/art-styles/thumbnail")
    def get_krea2_art_style_thumbnail(style_id: str) -> FileResponse:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors('Miniature de style introuvable.', invalid=(RuntimeError,)):
            return FileResponse(service.art_style_thumbnail(style_id))

    @router.post("/api/image-lab/krea2-assisted/prompt-library/index", status_code=status.HTTP_202_ACCEPTED)
    def index_krea2_prompt_library(force: bool = False) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            return {"prompt_library": service.start_prompt_example_indexing(force=force)}
        except RuntimeError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post("/api/image-lab/krea2-assisted/style-presets")
    def save_krea2_style_preset(body: Krea2StylePresetSaveBody) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors('Essai ou preset introuvable.', missing=(KeyError,)):
            preset = service.save_style_preset(body.project_id, body.attempt_id, body.name,
                                              preset_id=body.preset_id, expected_revision=body.expected_revision,
                                              category=(Krea2StylePresetCategory(body.category)
                                                        if body.category is not None else None))
            return {"preset": _serialize_krea2_style_preset(preset)}

    @router.patch("/api/image-lab/krea2-assisted/style-presets/{preset_id}")
    def update_krea2_style_preset(preset_id: str, body: Krea2StylePresetUpdateBody) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors('Preset introuvable.', missing=(KeyError,)):
            preset = service.update_style_preset(
                preset_id, name=body.name, category=Krea2StylePresetCategory(body.category),
                expected_revision=body.expected_revision,
            )
            return {"preset": _serialize_krea2_style_preset(preset)}

    @router.delete("/api/image-lab/krea2-assisted/style-presets/{preset_id}")
    def delete_krea2_style_preset(preset_id: str, body: Krea2StylePresetDeleteBody) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors('Preset introuvable.', missing=(KeyError,)):
            preset = service.delete_style_preset(preset_id, expected_revision=body.expected_revision)
            return {"deleted": preset_id, "revision": preset.revision}

    @router.post("/api/image-lab/krea2-assisted/projects/{project_id}/style-preset")
    def apply_krea2_style_preset(project_id: str, body: Krea2StylePresetApplyBody) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        draft = body.draft
        with http_errors('Projet ou preset introuvable.', missing=(KeyError,)):
            project = service.apply_style_preset(
                project_id, body.preset_id, expected_branch_id=body.expected_branch_id,
                current_prompt=draft.prompt, seed=_parse_json_seed(draft.seed) if draft.seed not in (None, "") else None,
                settings=_krea2_assisted_settings(draft),
            )
            return {"project": serialize_krea2_assisted_project(project)}

    @router.post("/api/image-lab/krea2-assisted/projects/{project_id}/art-direction")
    def apply_krea2_art_direction(project_id: str, body: Krea2ArtDirectionApplyBody) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        draft = body.draft
        with http_errors('Projet ou direction artistique introuvable.', invalid=(RuntimeError, TypeError, ValueError)):
            project = service.select_art_direction(
                project_id,
                body.style_id,
                expected_branch_id=body.expected_branch_id,
                current_prompt=draft.prompt,
                seed=_parse_json_seed(draft.seed) if draft.seed not in (None, "") else None,
                settings=_krea2_assisted_settings(draft),
            )
            return {"project": serialize_krea2_assisted_project(project)}

    @router.get("/api/image-lab/krea2-assisted/project-summaries")
    def list_krea2_project_summaries(limit: int = Query(30, ge=0, le=100)) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors("project not found"):
            rows = service.summaries(limit)
            return {"projects": [dict(asdict(row), preview_url=(
                f"/api/assets/{quote(row.preview_asset_id, safe='')}/thumbnail?v=1"
                if row.preview_asset_id else None)) for row in rows]}

    @router.get("/api/image-lab/krea2-assisted/projects")
    def list_krea2_assisted_projects(limit: int = 30) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            return {
                "projects": [
                    serialize_krea2_assisted_project(project, include_prompt_examples=False)
                    for project in service.list(limit)
                ]
            }
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/api/image-lab/krea2-assisted/projects/{project_id}")
    def get_krea2_assisted_project(project_id: str) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            return {"project": serialize_krea2_assisted_project(service.get(project_id))}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="KREA2 assisted project not found") from error

    @router.post("/api/image-lab/krea2-assisted/projects/{project_id}/prompt-example")
    def select_krea2_prompt_example(
        project_id: str,
        body: Krea2AssistedPromptExampleBody,
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors('Projet ou exemple introuvable.'):
            project = service.select_prompt_example(
                project_id,
                body.example_id,
                expected_branch_id=body.expected_branch_id,
            )
            return {"project": serialize_krea2_assisted_project(project)}

    @router.post("/api/image-lab/krea2-assisted/projects/{project_id}/local-inspiration")
    def set_krea2_local_inspiration(
        project_id: str,
        body: Krea2AssistedLocalInspirationBody,
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors('Projet introuvable.', invalid=(RuntimeError, TypeError, ValueError)):
            project = service.set_local_inspiration(
                project_id,
                body.enabled,
                expected_branch_id=body.expected_branch_id,
            )
            return {"project": serialize_krea2_assisted_project(project)}

    @router.post("/api/image-lab/krea2-assisted/projects/{project_id}/prompt-example/variant")
    def recompile_krea2_prompt_example(
        project_id: str,
        body: Krea2AssistedExpectedBranchBody,
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors('Template introuvable.', invalid=(RuntimeError, TypeError, ValueError)):
            project = service.recompile_prompt_example(
                project_id,
                expected_branch_id=body.expected_branch_id,
            )
            return {"project": serialize_krea2_assisted_project(project)}

    @router.get("/api/image-lab/krea2-assisted/wildcard-preview")
    def get_krea2_wildcard_preview(template_id: str) -> FileResponse:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors('Aperçu de template introuvable.', invalid=(RuntimeError,)):
            return FileResponse(
                service.prompt_template_preview(template_id),
                media_type="image/png",
            )

    @router.post(
        "/api/image-lab/krea2-assisted/projects/{project_id}/guidance-images",
        status_code=status.HTTP_201_CREATED,
    )
    async def upload_krea2_assisted_guidance(
        project_id: str,
        image: Annotated[UploadFile, File()],
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            service.get(project_id)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(
                status_code=404,
                detail="KREA2 assisted project not found",
            ) from error
        try:
            content = await image.read(MAX_IMAGE_BYTES + 1)
            if len(content) > MAX_IMAGE_BYTES:
                raise ValueError("guidance image exceeds the 25 MiB limit")
            media_type = detect_image_media_type(content)
            asset = runner.assets.create(
                content,
                media_type=media_type,
                source_run_id=project_id,
            )
            filename = image.filename or "guidance-image"
            return {
                "guidance": {
                    "asset_id": asset.asset_id,
                    "filename": filename,
                    "url": f"/api/assets/{asset.asset_id}/content",
                }
            }
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        finally:
            await image.close()

    @router.post("/api/image-lab/krea2-assisted/projects/{project_id}/chat/stream")
    def stream_krea2_assisted_chat(
        project_id: str,
        body: Krea2AssistedChatBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_krea2_assisted(krea2_assisted)
        try:
            mode = Krea2AssistedTurnMode(body.mode)
            prompt_language = (
                Krea2PromptLanguage(body.prompt_language)
                if body.prompt_language is not None
                else None
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return stream_response(service.stream_chat(project_id, body.message, expected_branch_id=body.expected_branch_id, mode=mode, model_id=body.model_id, feedback_attempt_id=body.feedback_attempt_id, prompt_language=prompt_language, guidance_asset_id=body.guidance_asset_id, guidance_filename=body.guidance_filename, current_prompt=body.current_prompt, include_reasoning=include_reasoning, refresh_prompt_examples=body.refresh_prompt_examples), serialize=serialize_krea2_assisted_project)

    @router.get("/api/image-lab/krea2-assisted/render-queue")
    def krea2_assisted_render_queue() -> dict[str, object]:
        return _require_krea2_assisted(krea2_assisted).render_queue()

    @router.post(
        "/api/image-lab/krea2-assisted/projects/{project_id}/attempts",
        status_code=status.HTTP_201_CREATED,
    )
    def prepare_krea2_assisted_attempt(
        project_id: str,
        body: Krea2AssistedAttemptBody,
        response: Response,
        enqueue: bool = False,
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        started = perf_counter()
        with http_errors('KREA2 assisted project not found'):
            seed = None if body.seed is None or str(body.seed).strip() == "" else _parse_json_seed(body.seed)
            project = service.prepare_attempt(
                project_id,
                expected_branch_id=body.expected_branch_id,
                prompt=body.prompt,
                settings=_krea2_assisted_settings(body),
                seed=seed,
                enqueue=enqueue,
                prompt_language=(
                    Krea2PromptLanguage(body.prompt_language)
                    if body.prompt_language is not None
                    else None
                ),
            )
            prepared = perf_counter()
            if enqueue:
                service.start_render_worker()
            worker_ready = perf_counter()
            payload = {"project": serialize_krea2_assisted_project(project)}
            response.headers["Server-Timing"] = (
                f"prepare;dur={(prepared - started) * 1000:.1f}, "
                f"worker;dur={(worker_ready - prepared) * 1000:.1f}, "
                f"serialize;dur={(perf_counter() - worker_ready) * 1000:.1f}"
            )
            return payload

    @router.post(
        "/api/image-lab/krea2-assisted/projects/{project_id}/attempts/{attempt_id}/start",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def start_krea2_assisted_attempt(
        project_id: str,
        attempt_id: str,
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors('KREA2 assisted project or attempt not found'):
            project = service.queue_attempt(project_id, attempt_id)
        service.start_render_worker()
        return {"project": serialize_krea2_assisted_project(project)}

    @router.post("/api/image-lab/krea2-assisted/projects/{project_id}/attempts/{attempt_id}/cancel")
    def cancel_krea2_assisted_attempt(project_id: str, attempt_id: str) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors('KREA2 assisted project or attempt not found'):
            return {
                "project": serialize_krea2_assisted_project(
                    service.cancel_attempt(project_id, attempt_id)
                )
            }

    @router.post("/api/image-lab/krea2-assisted/projects/{project_id}/branches")
    def change_krea2_assisted_branch(project_id: str, body: Krea2AssistedBranchBody) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors('KREA2 project, branch or attempt not found'):
            draft = body.draft
            project = service.change_branch(
                project_id, expected_branch_id=body.expected_branch_id,
                branch_id=body.branch_id, attempt_id=body.attempt_id,
                image_prompt_only=body.image_prompt_only,
                current_prompt=draft.prompt if draft else None,
                settings=_krea2_assisted_settings(draft) if draft else None,
                seed=_parse_json_seed(draft.seed) if draft and draft.seed is not None and str(draft.seed).strip() else None,
                prompt_language=Krea2PromptLanguage(body.prompt_language) if body.prompt_language else None,
                model_id=body.model_id,
            )
            return {"project": serialize_krea2_assisted_project(project)}

    @router.post("/api/image-lab/krea2-assisted/projects/{project_id}/feedback")
    def select_krea2_assisted_feedback(
        project_id: str,
        body: Krea2AssistedFeedbackBody,
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors('KREA2 assisted project or attempt not found'):
            return {
                "project": serialize_krea2_assisted_project(
                    service.select_feedback(project_id, body.attempt_id)
                )
            }

    @router.post("/api/image-lab/krea2-assisted/projects/{project_id}/attempts/{attempt_id}/save")
    def save_krea2_assisted_image(project_id: str, attempt_id: str) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors('KREA2 assisted project or attempt not found'):
            return {
                "project": serialize_krea2_assisted_project(
                    service.save_image(project_id, attempt_id)
                )
            }

    @router.put("/api/image-lab/krea2-assisted/projects/{project_id}/recipe-draft")
    def update_krea2_assisted_recipe_draft(
        project_id: str,
        body: Krea2AssistedRecipeDraftBody,
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors('KREA2 assisted project not found'):
            draft = parse_krea2_assisted_recipe_draft(body.model_dump())
            return {
                "project": serialize_krea2_assisted_project(
                    service.set_recipe_draft(project_id, draft)
                )
            }

    @router.post("/api/image-lab/krea2-assisted/projects/{project_id}/recipe/publish")
    def publish_krea2_assisted_recipe(
        project_id: str,
        body: Krea2AssistedRecipePublishBody | None = None,
    ) -> dict[str, object]:
        service = _require_krea2_assisted(krea2_assisted)
        with http_errors('KREA2 assisted project not found'):
            draft = (
                parse_krea2_assisted_recipe_draft(body.draft.model_dump())
                if body is not None and body.draft is not None
                else None
            )
            project, recipe = service.publish_recipe(project_id, draft)
            return {
                "project": serialize_krea2_assisted_project(project),
                "recipe": serialize_krea2_visual_recipe(recipe),
            }

    @router.post("/api/image-lab/krea2-assisted/projects/{project_id}/scene-images", status_code=201)
    async def upload_assisted_scene(project_id: str, image: Annotated[UploadFile, File()]):
        assisted = _require_krea2_assisted(krea2_assisted)
        service = _require_krea2_edit(krea2_edit)
        try:
            assisted.projects.get(project_id)
            if service.edit_images is None:
                raise ValueError("Image decoding is not configured.")
            content = await image.read(MAX_IMAGE_BYTES + 1)
            media_type = detect_image_media_type(content)
            await run_in_threadpool(service.edit_images.dimensions, content)
            asset = service.assets.create(content, media_type=media_type, source_run_id=project_id)
            return {"image": {"asset_id": asset.asset_id, "filename": image.filename or "Decor",
                              "url": f"/api/assets/{asset.asset_id}/content"}}
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="Image or project not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        finally:
            await image.close()

    @router.post("/api/image-lab/krea2-assisted/projects/{project_id}/attempts/{attempt_id}/restage", status_code=201)
    def restage_assisted_image(project_id: str, attempt_id: str, body: Krea2RestageBody):
        assisted = _require_krea2_assisted(krea2_assisted)
        service = _require_krea2_edit(krea2_edit)
        try:
            project = assisted.projects.get(project_id)
            source = service.restage_assisted(project, attempt_id, scene_asset_id=body.scene_asset_id,
                instruction=body.instruction, request_id=body.request_id)
            return {"source": serialize_krea2_edit_source(source)}
        except RestagingConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="Image or project not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return router
