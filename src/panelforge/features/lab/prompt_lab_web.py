"""Prompt lab web for the PanelForge Lab HTTP interface."""

from __future__ import annotations
from typing import TypedDict
from .http_support import http_errors
import json
from typing import Annotated
from panelforge.domain.prompt_composition import PreparationIntent
from panelforge.domain.prompt_writer import supports_writer_model
from fastapi import File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from panelforge.application import NewReference, PromptCompositionService, PromptLabService, SUPER_FAST_REF2V_COOKBOOK_ID, SUPER_FAST_REF2V_COOKBOOK_VERSION, composition_picture_mapping, creative_axes_from_legacy
from panelforge.domain import CompositionStage, CookbookBinding, CreativeFreedomAxes, PromptComposition, PromptLabSession, ReferenceEvidencePolicy, ReferenceUse
from fastapi import APIRouter
from .http_streaming import stream_response
from .http_support import _serialize_llm_model
from .media_http import MAX_IMAGE_BYTES, detect_image_media_type


MAX_PROMPT_REFERENCES = 9


class PromptEditBody(BaseModel):
    content: str


class PromptRevisionBody(BaseModel):
    instruction: str


class CreativeAxesBody(BaseModel):
    scene_life: int = Field(ge=0, le=3)
    camera: int = Field(ge=0, le=3)
    extra_motion: int = Field(ge=0, le=3)
    dialogue: int = Field(default=0, ge=0, le=3, strict=True)

    def domain_value(self) -> CreativeFreedomAxes:
        return CreativeFreedomAxes(
            scene_life=self.scene_life,
            camera=self.camera,
            extra_motion=self.extra_motion,
            dialogue=self.dialogue,
        )


class BriefStructureBody(BaseModel):
    source_text: str
    creative_freedom: int = Field(default=35, ge=0, le=100)
    creative_axes: CreativeAxesBody | None = None
    creative_audacity: int = Field(default=0, ge=0, le=3)


class PromptSessionForkBody(BaseModel):
    model_id: str | None = None
    profile_id: str | None = None
    profile_version: str | None = None
    brief_variant_id: str | None = None
    brief_variant_version: str | None = None
    inherit_brief_variant: bool = True
    combat_settings: dict | None = None
    cinematic_settings: dict | None = None
    sensual_settings: dict | None = None


class BriefVariantBody(BaseModel):
    brief_variant_id: str | None = None
    brief_variant_version: str | None = None


class CompositionConfigureBody(BaseModel):
    cookbook_id: str
    cookbook_version: str
    bindings: dict[str, list[str]]
    preparation_intent: BriefStructureBody | None = None
    writer_model_id: str | None = None


class CompositionWriterModelBody(BaseModel):
    writer_model_id: str | None
    expected_writer_model_id: str | None


class ChinesePromptVariantBody(BaseModel):
    model_id: str | None = None


class PlanArbitrationBody(BaseModel):
    decisions: dict[str, str]
    instruction: str | None = None


class SuperFastRef2VBody(BaseModel):
    source_text: str
    creative_freedom: int = Field(default=35, ge=0, le=100)
    creative_axes: CreativeAxesBody | None = None
    creative_audacity: int = Field(default=0, ge=0, le=3)


class PromptSessionPayload(TypedDict):
    id: str
    session_id: str
    model_id: str
    session_mode: str
    preparation: dict[str, object]
    cinematic_settings: dict[str, object] | None
    sensual_settings: dict[str, object] | None
    combat_settings: dict[str, object] | None
    profile: dict[str, object]
    brief_variant: dict[str, object] | None
    analysis_complete: bool
    interpretation_complete: bool
    brief_complete: bool
    brief_is_stale: bool
    active_brief_revision_id: str | None
    approved_brief_revision_id: str | None
    active_brief: dict[str, object] | None
    brief_revisions: list[dict[str, object]]
    references: list[dict[str, object]]


def serialize_prompt_session(session: PromptLabSession) -> PromptSessionPayload:
    def creative_axes_payload(revision) -> dict[str, int]:
        axes = revision.creative_axes or creative_axes_from_legacy(
            revision.creative_freedom
        )
        return {
            "scene_life": axes.scene_life,
            "camera": axes.camera,
            "extra_motion": axes.extra_motion,
            "dialogue": axes.dialogue,
        }

    return {
        "id": session.session_id,
        "session_id": session.session_id,
        "model_id": session.model_id,
        "session_mode": session.session_mode.value,
        "preparation": session.preparation.as_dict(),
        "cinematic_settings": session.cinematic_settings.as_dict() if session.cinematic_settings else None,
        "sensual_settings": session.sensual_settings.as_dict() if session.sensual_settings else None,
        "combat_settings": session.combat_settings.as_dict() if session.combat_settings else None,
        "profile": {
            "id": session.profile_id,
            "version": session.profile_version,
        },
        "brief_variant": (
            {
                "id": session.brief_variant_id,
                "version": session.brief_variant_version,
            }
            if session.brief_variant_id is not None
            else None
        ),
        "analysis_complete": session.analysis_complete,
        "interpretation_complete": session.interpretation_complete,
        "brief_complete": session.brief_complete,
        "brief_is_stale": session.brief_is_stale,
        "active_brief_revision_id": session.active_brief_revision_id,
        "approved_brief_revision_id": session.approved_brief_revision_id,
        "active_brief": (
            {
                "id": session.active_brief_revision.revision_id,
                "revision_id": session.active_brief_revision.revision_id,
                "source_text": session.active_brief_revision.source_text,
                "content": session.active_brief_revision.content,
                "creative_freedom": (
                    session.active_brief_revision.creative_freedom
                ),
                "creative_audacity": session.active_brief_revision.creative_audacity,
                "creative_axes": creative_axes_payload(
                    session.active_brief_revision
                ),
                "origin": session.active_brief_revision.origin.value,
                "parent_revision_id": (
                    session.active_brief_revision.parent_revision_id
                ),
                "instruction": session.active_brief_revision.instruction,
            }
            if session.active_brief_revision is not None
            else None
        ),
        "brief_revisions": [
            {
                "id": revision.revision_id,
                "revision_id": revision.revision_id,
                "source_text": revision.source_text,
                "content": revision.content,
                "creative_freedom": revision.creative_freedom,
                "creative_audacity": revision.creative_audacity,
                "creative_axes": creative_axes_payload(revision),
                "origin": revision.origin.value,
                "parent_revision_id": revision.parent_revision_id,
                "instruction": revision.instruction,
                "references": [
                    {
                        "reference_id": reference.reference_id,
                        "analysis_revision_id": reference.analysis_revision_id,
                        "uses": [use.value for use in reference.uses],
                        "evidence_policy": reference.evidence_policy.value,
                    }
                    for reference in revision.references
                ],
            }
            for revision in session.brief_revisions
        ],
        "references": [
            {
                "id": reference.reference_id,
                "reference_id": reference.reference_id,
                "asset_id": reference.asset_id,
                "content_url": f"/api/assets/{reference.asset_id}/content",
                "role": reference.role,
                "label": reference.label,
                "evidence_policy": reference.evidence_policy.value,
                "review_status": reference.review_status.value,
                "uses": [use.value for use in reference.uses],
                "active_revision_id": reference.active_revision_id,
                "approved_revision_id": reference.approved_revision_id,
                "active_content": (
                    reference.active_revision.content
                    if reference.active_revision is not None
                    else None
                ),
                "revisions": [
                    {
                        "id": revision.revision_id,
                        "revision_id": revision.revision_id,
                        "content": revision.content,
                        "origin": revision.origin.value,
                        "parent_revision_id": revision.parent_revision_id,
                        "instruction": revision.instruction,
                    }
                    for revision in reference.revisions
                ],
                "interpretation_review_status": (
                    reference.interpretation_review_status.value
                ),
                "interpretation_is_stale": reference.interpretation_is_stale,
                "active_interpretation_id": reference.active_interpretation_id,
                "approved_interpretation_id": (
                    reference.approved_interpretation_id
                ),
                "active_interpretation": (
                    reference.active_interpretation.content
                    if reference.active_interpretation is not None
                    else None
                ),
                "interpretations": [
                    {
                        "id": interpretation.revision_id,
                        "revision_id": interpretation.revision_id,
                        "content": interpretation.content,
                        "origin": interpretation.origin.value,
                        "source_analysis_revision_id": (
                            interpretation.source_analysis_revision_id
                        ),
                        "uses": [use.value for use in interpretation.uses],
                        "parent_revision_id": interpretation.parent_revision_id,
                        "instruction": interpretation.instruction,
                    }
                    for interpretation in reference.interpretations
                ],
            }
            for reference in session.references
        ],
    }


class PromptCompositionPayload(TypedDict):
    source_session_id: str
    writer_model_id: str | None
    supports_writer_model: bool
    combat_sequence: dict[str, object] | None
    cinematic_sequence: dict[str, object] | None
    sensual_sequence: dict[str, object] | None
    preparation_intent: dict[str, object] | None
    cookbook: dict[str, object]
    bindings: dict[str, list[str]]
    picture_mapping: list[dict[str, object]]
    prompt_variants: list[dict[str, object]]
    documents: dict[str, object]


def serialize_prompt_composition(
    composition: PromptComposition,
    service: PromptCompositionService,
) -> PromptCompositionPayload:
    statuses = {status.stage: status for status in service.status(composition)}
    documents: dict[str, object] = {}
    for stage in CompositionStage:
        document = composition.document(stage)
        stage_status = statuses[stage]
        documents[stage.value] = {
            "stage": stage.value,
            "active_revision_id": document.active_revision_id,
            "approved_revision_id": document.approved_revision_id,
            "stale": stage_status.stale,
            "complete": stage_status.complete,
            "blocked_reason": stage_status.blocked_reason,
            "validation_errors": list(stage_status.validation_errors),
            "validation_warnings": list(stage_status.validation_warnings),
            "active_content": (
                document.active_revision.content
                if document.active_revision is not None
                else None
            ),
            "revisions": [
                {
                    "id": revision.revision_id,
                    "revision_id": revision.revision_id,
                    "content": revision.content,
                    "origin": revision.origin.value,
                    "source_ids": list(revision.source_ids),
                    "parent_revision_id": revision.parent_revision_id,
                    "instruction": revision.instruction,
                    "llm_call_id": revision.llm_call_id,
                    "prompt_recipe_revision": revision.prompt_recipe_revision,
                }
                for revision in document.revisions
            ],
        }
    return {
        "source_session_id": composition.source_session_id,
        "writer_model_id": composition.writer_model_id,
        "supports_writer_model": supports_writer_model(composition.cookbook.cookbook_id, composition.cookbook.version),
        "combat_sequence": _combat_sequence_summary(composition),
        "cinematic_sequence": _classic_sequence_summary(composition),
        "sensual_sequence": _sensual_sequence_summary(composition),
        "preparation_intent": (
            {
                "source_text": composition.preparation_intent.source_text,
                "creative_freedom": composition.preparation_intent.creative_freedom,
                "creative_audacity": composition.preparation_intent.creative_audacity,
                "creative_axes": (
                    {name: getattr(composition.preparation_intent.creative_axes, name) for name in ("scene_life", "camera", "extra_motion", "dialogue")}
                    if composition.preparation_intent.creative_axes else None
                ),
            } if composition.preparation_intent is not None else None
        ),
        "cookbook": {
            "id": composition.cookbook.cookbook_id,
            "version": composition.cookbook.version,
            "engine_contract": {
                "id": composition.cookbook.engine_contract_id,
                "version": composition.cookbook.engine_contract_version,
            },
        },
        "bindings": {
            binding.slot_id: list(binding.reference_ids)
            for binding in composition.bindings
        },
        "picture_mapping": [
            {"reference_id": reference_id, "picture_number": picture_number}
            for reference_id, picture_number in composition_picture_mapping(composition)
        ],
        "prompt_variants": [
            {
                "id": variant.variant_id,
                "variant_id": variant.variant_id,
                "source_revision_id": variant.source_revision_id,
                "language": variant.language,
                "content": variant.content,
                "model_id": variant.model_id,
                "llm_call_id": variant.llm_call_id,
            }
            for variant in composition.prompt_variants
        ],
        "documents": documents,
    }


def _require_prompt_lab(value: PromptLabService | None) -> PromptLabService:
    if value is None:
        raise HTTPException(status_code=503, detail="Prompt engine is not configured")
    return value


def _require_prompt_composition(
    value: PromptCompositionService | None,
) -> PromptCompositionService:
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="Prompt composition is not configured",
        )
    return value


def _prompt_action(action) -> dict[str, object]:
    with http_errors('prompt session or reference not found'):
        return serialize_prompt_session(action())


def _composition_action(service: PromptCompositionService, action) -> dict[str, object]:
    with http_errors('prompt session, composition or cookbook not found'):
        composition = action()
        return {"composition": serialize_prompt_composition(composition, service)}


def _composition_stream_action(
    service: PromptCompositionService,
    action,
) -> StreamingResponse:
    with http_errors('prompt session, composition or cookbook not found'):
        events = action()
    return stream_response(events, serialize=lambda value: serialize_prompt_composition(value, service), entity='composition', fields=('finish_reason', 'max_tokens'), document_stage=True)


def _parse_composition_stage(value: str) -> CompositionStage:
    try:
        return CompositionStage(value.replace("-", "_"))
    except ValueError as error:
        raise HTTPException(status_code=404, detail="composition stage not found") from error


def _parse_reference_uses(value: str) -> tuple[ReferenceUse, ...]:
    if not isinstance(value, str):
        raise TypeError("reference uses must be a string")
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        raise ValueError("reference uses must not be empty")
    return tuple(ReferenceUse(part) for part in parts)


def _combat_settings_value(value):
    from panelforge.domain.video_preparation import CombatSettings
    return CombatSettings.from_dict(value) if value is not None else None


def _combat_sequence_summary(composition):
    from panelforge.application.combat_sequence import MARKER, decode_context
    revision = composition.final_prompt.active_revision
    if revision is None or not (revision.compiler_context or "").startswith(MARKER):
        return None
    context = decode_context(revision.compiler_context)
    return {"shot_count": len(context["shot_starts_ms"]), "settings": context["settings"]}


def _cinematic_settings_value(value):
    from panelforge.domain.video_preparation import ClassicCinematicSettings
    return ClassicCinematicSettings.from_dict(value) if value is not None else None


def _sensual_settings_value(value):
    from panelforge.domain.video_preparation import SensualSettings
    return SensualSettings.from_dict(value) if value is not None else None


def _classic_sequence_summary(composition):
    from panelforge.application.classic_cinematic import MARKER, decode_context
    revision = composition.final_prompt.active_revision
    if revision is not None and (revision.compiler_context or "").startswith(MARKER):
        context = decode_context(revision.compiler_context)
        return {"shot_count": len(context["shot_starts_ms"]), "settings": context["settings"]}
    if composition.cookbook.cookbook_id.endswith(".classic.cinematic.planned"):
        plan = composition.beat_sheet.active_revision
        if plan is not None:
            return {"shot_count": len(json.loads(plan.content)["shots"])}
    return None


def _sensual_sequence_summary(composition):
    from panelforge.application.sensual_cinematic import MARKER, decode_context
    revision = composition.final_prompt.active_revision
    if revision is not None and (revision.compiler_context or "").startswith(MARKER):
        context = decode_context(revision.compiler_context)
        return {"shot_count": len(context["shot_starts_ms"]), "settings": context["settings"]}
    if composition.cookbook.cookbook_id.endswith(".sensual.planned"):
        plan = composition.beat_sheet.active_revision
        if plan is not None:
            return {"shot_count": len(json.loads(plan.content)["shots"])}
    return None


def prompt_lab_router(*, prompt_composition: PromptCompositionService | None, prompt_lab: PromptLabService | None) -> APIRouter:
    router = APIRouter()

    @router.get("/api/prompt-lab/spec")
    def prompt_lab_spec() -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return {
            "max_references": MAX_PROMPT_REFERENCES,
            "max_image_bytes": MAX_IMAGE_BYTES,
            "profiles": [
                {
                    "id": profile.profile_id,
                    "version": profile.version,
                    "display_name": profile.display_name,
                    "target_model_family": profile.target_model_family,
                    "session_mode": profile.session_mode.value,
                    "preparation": profile.preparation.as_dict(),
                    "supports_interpretation": (
                        profile.interpretation_system_prompt is not None
                    ),
                    "supports_brief": profile.brief_system_prompt is not None,
                    "brief_variants": [
                        {
                            "id": variant.variant_id,
                            "version": variant.version,
                            "display_name": variant.display_name,
                        }
                        for variant in profile.brief_variants
                    ],
                }
                for profile in service.list_profiles()
            ],
        }

    @router.get("/api/prompt-lab/models")
    def prompt_lab_models() -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return {
            "models": [
                _serialize_llm_model(model)
                for model in service.list_models()
            ]
        }

    @router.post("/api/prompt-lab/sessions", status_code=status.HTTP_201_CREATED)
    async def create_prompt_lab_session(
        model_id: Annotated[str, Form()],
        profile_id: Annotated[str, Form()],
        profile_version: Annotated[str, Form()],
        brief_variant_id: Annotated[str | None, Form()] = None,
        brief_variant_version: Annotated[str | None, Form()] = None,
        images: Annotated[list[UploadFile] | None, File()] = None,
        roles: Annotated[list[str] | None, Form()] = None,
        usages: Annotated[list[str] | None, Form()] = None,
        evidence_policies: Annotated[list[str] | None, Form()] = None,
        combat_settings: Annotated[str | None, Form()] = None,
        cinematic_settings: Annotated[str | None, Form()] = None,
        sensual_settings: Annotated[str | None, Form()] = None,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        images = images or []
        roles = roles or []
        if len(images) > MAX_PROMPT_REFERENCES:
            raise HTTPException(
                status_code=422,
                detail=f"provide at most {MAX_PROMPT_REFERENCES} images",
            )
        if len(images) != len(roles):
            raise HTTPException(
                status_code=422,
                detail="provide exactly one role for each image",
            )
        if usages is not None and len(images) != len(usages):
            raise HTTPException(
                status_code=422,
                detail="provide exactly one usage set for each image",
            )
        if evidence_policies is not None and len(images) != len(evidence_policies):
            raise HTTPException(
                status_code=422,
                detail="provide exactly one evidence policy for each image",
            )

        uploaded: list[
            tuple[
                bytes,
                str,
                str,
                str,
                tuple[ReferenceUse, ...],
                ReferenceEvidencePolicy,
            ]
        ] = []
        with http_errors('prompt profile not found'):
            service.get_profile(profile_id, profile_version)
            usage_values = usages or [ReferenceUse.SUBJECT.value] * len(images)
            policy_values = evidence_policies or [
                ReferenceEvidencePolicy.FULL.value
            ] * len(images)
            for index, (image, role, raw_uses, raw_policy) in enumerate(
                zip(images, roles, usage_values, policy_values, strict=True),
                1,
            ):
                content = await image.read(MAX_IMAGE_BYTES + 1)
                await image.close()
                if len(content) > MAX_IMAGE_BYTES:
                    raise ValueError(f"image {index} exceeds the 25 MiB limit")
                media_type = detect_image_media_type(content)
                label = (image.filename or "").strip() or f"Image {index}"
                uploaded.append(
                    (
                        content,
                        media_type,
                        role,
                        label,
                        _parse_reference_uses(raw_uses),
                        ReferenceEvidencePolicy(raw_policy),
                    )
                )

            references = tuple(
                NewReference(
                    asset_id=service.create_asset(content, media_type).asset_id,
                    role=role,
                    label=label,
                    uses=reference_uses,
                    evidence_policy=evidence_policy,
                )
                for (
                    content,
                    media_type,
                    role,
                    label,
                    reference_uses,
                    evidence_policy,
                ) in uploaded
            )
            session = service.create_session(
                model_id=model_id,
                profile_id=profile_id,
                profile_version=profile_version,
                brief_variant_id=brief_variant_id,
                brief_variant_version=brief_variant_version,
                references=references,
                combat_settings=_combat_settings_value(json.loads(combat_settings)) if combat_settings is not None else None,
                cinematic_settings=_cinematic_settings_value(json.loads(cinematic_settings)) if cinematic_settings is not None else None,
                sensual_settings=_sensual_settings_value(json.loads(sensual_settings)) if sensual_settings is not None else None,
            )
        return serialize_prompt_session(session)

    @router.get("/api/prompt-lab/sessions")
    def list_prompt_lab_sessions(limit: int = 20) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        try:
            sessions = service.list_sessions(limit)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "sessions": [serialize_prompt_session(session) for session in sessions]
        }

    @router.get("/api/prompt-lab/sessions/{session_id}")
    def get_prompt_lab_session(session_id: str) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        with http_errors('prompt session not found', invalid=(ValueError,)):
            return serialize_prompt_session(service.get_session(session_id))

    @router.post(
        "/api/prompt-lab/sessions/{session_id}/fork",
        status_code=status.HTTP_201_CREATED,
    )
    def fork_prompt_lab_session(
        session_id: str,
        body: PromptSessionForkBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        with http_errors('prompt session or reference asset not found'):
            return serialize_prompt_session(
                service.fork_session(
                    session_id,
                    model_id=body.model_id,
                    profile_id=body.profile_id,
                    profile_version=body.profile_version,
                    brief_variant_id=body.brief_variant_id,
                    brief_variant_version=body.brief_variant_version,
                    inherit_brief_variant=body.inherit_brief_variant,
                    combat_settings=_combat_settings_value(body.combat_settings),
                    cinematic_settings=_cinematic_settings_value(body.cinematic_settings),
                    sensual_settings=_sensual_settings_value(body.sensual_settings),
                )
            )

    @router.post("/api/prompt-lab/sessions/{session_id}/brief/variant")
    def configure_prompt_brief_variant(
        session_id: str,
        body: BriefVariantBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(lambda: service.configure_brief_variant(
            session_id,
            brief_variant_id=body.brief_variant_id,
            brief_variant_version=body.brief_variant_version,
        ))

    @router.post("/api/prompt-lab/sessions/{session_id}/brief/structure")
    def structure_prompt_brief(
        session_id: str,
        body: BriefStructureBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.structure_brief(
                session_id,
                body.source_text,
                body.creative_freedom,
                body.creative_axes.domain_value() if body.creative_axes else None,
                creative_audacity=body.creative_audacity,
            )
        )

    @router.post("/api/prompt-lab/sessions/{session_id}/brief/structure/stream")
    def stream_prompt_brief(
        session_id: str,
        body: BriefStructureBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_prompt_lab(prompt_lab)
        return stream_response(service.stream_structure_brief(session_id, body.source_text, body.creative_freedom, creative_axes=body.creative_axes.domain_value() if body.creative_axes else None, creative_audacity=body.creative_audacity, include_reasoning=include_reasoning), serialize=serialize_prompt_session, entity='session', fields=('finish_reason', 'max_tokens'))

    @router.post("/api/prompt-lab/sessions/{session_id}/brief/edit")
    def edit_prompt_brief(
        session_id: str,
        body: PromptEditBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(lambda: service.edit_brief(session_id, body.content))

    @router.post("/api/prompt-lab/sessions/{session_id}/brief/revise")
    def revise_prompt_brief(
        session_id: str,
        body: PromptRevisionBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.revise_brief(session_id, body.instruction)
        )

    @router.post("/api/prompt-lab/sessions/{session_id}/brief/revise/stream")
    def stream_prompt_brief_revision(
        session_id: str,
        body: PromptRevisionBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_prompt_lab(prompt_lab)
        return stream_response(service.stream_revise_brief(session_id, body.instruction, include_reasoning=include_reasoning), serialize=serialize_prompt_session, entity='session', fields=('finish_reason', 'max_tokens'))

    @router.post("/api/prompt-lab/sessions/{session_id}/brief/approve")
    def approve_prompt_brief(session_id: str) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(lambda: service.approve_brief(session_id))

    @router.get("/api/prompt-lab/cookbooks")
    def list_prompt_cookbooks() -> dict[str, object]:
        service = _require_prompt_composition(prompt_composition)
        return {
            "cookbooks": [
                {
                    "id": cookbook.reference.cookbook_id,
                    "version": cookbook.reference.version,
                    "display_name": cookbook.display_name,
                    "description": cookbook.description,
                    "target_mode": cookbook.target_mode,
                    "output_contract": cookbook.output_contract,
                    "preset": cookbook.preset,
                    "invalid_camera_target_policy": (
                        cookbook.invalid_camera_target_policy
                    ),
                    "writer_projection": cookbook.writer_projection,
                    "stages": list(cookbook.stages),
                    "preparation_steps": getattr(cookbook, "preparation_steps", 3),
                    "supports_writer_model": supports_writer_model(cookbook.reference.cookbook_id, cookbook.reference.version),
                    "preparation": cookbook.preparation.as_dict(),
                    "vocal_policy_version": getattr(cookbook, "vocal_policy_version", None),
                    "profile": (
                        {"id": cookbook.profile_id, "version": cookbook.profile_version}
                        if getattr(cookbook, "profile_id", None) else None
                    ),
                    "supports_plan_reconciliation": bool(
                        cookbook.beat_sheet_reconcile_system_prompt
                        and cookbook.beat_sheet_reconcile_user_prompt
                    ),
                    "sources": list(cookbook.sources),
                    "engine_contract": {
                        "id": cookbook.reference.engine_contract_id,
                        "version": cookbook.reference.engine_contract_version,
                    },
                    "slots": [
                        {
                            "id": slot.slot_id,
                            "label": slot.label,
                            "description": slot.description,
                            "evidence_policy": slot.evidence_policy.value,
                            "subject_label": slot.subject_label,
                            "accepted_uses": list(slot.accepted_uses),
                            "required_uses": list(slot.required_uses),
                            "required_shots": list(slot.required_shots),
                            "minimum_references": slot.minimum_references,
                            "maximum_references": slot.maximum_references,
                        }
                        for slot in cookbook.slots
                    ],
                }
                for cookbook in service.list_cookbooks()
            ]
        }

    @router.get("/api/prompt-lab/sessions/{session_id}/composition")
    def get_prompt_composition(session_id: str) -> dict[str, object]:
        service = _require_prompt_composition(prompt_composition)
        try:
            composition = service.get(session_id)
        except (KeyError, FileNotFoundError):
            return {"composition": None}
        return {"composition": serialize_prompt_composition(composition, service)}

    @router.post("/api/prompt-lab/sessions/{session_id}/composition")
    def configure_prompt_composition(
        session_id: str,
        body: CompositionConfigureBody,
    ) -> dict[str, object]:
        service = _require_prompt_composition(prompt_composition)
        public_cookbooks = {
            (cookbook.reference.cookbook_id, cookbook.reference.version)
            for cookbook in service.list_cookbooks()
        }
        if (body.cookbook_id, body.cookbook_version) not in public_cookbooks:
            raise HTTPException(
                status_code=422,
                detail="cookbook is not available for manual configuration",
            )
        return _composition_action(
            service,
            lambda: service.configure(
                session_id,
                body.cookbook_id,
                body.cookbook_version,
                tuple(
                    CookbookBinding(
                        slot_id=slot_id,
                        reference_ids=tuple(reference_ids),
                    )
                    for slot_id, reference_ids in body.bindings.items()
                ),
                preparation_intent=(
                    PreparationIntent(
                        source_text=body.preparation_intent.source_text.strip(),
                        creative_freedom=body.preparation_intent.creative_freedom,
                        creative_axes=(body.preparation_intent.creative_axes.domain_value() if body.preparation_intent.creative_axes else None),
                        creative_audacity=body.preparation_intent.creative_audacity,
                    ) if body.preparation_intent is not None else None
                ),
                writer_model_id=body.writer_model_id,
            ),
        )

    @router.put("/api/prompt-lab/sessions/{session_id}/composition/writer-model")
    def set_composition_writer_model(
        session_id: str, body: CompositionWriterModelBody,
    ) -> dict[str, object]:
        service = _require_prompt_composition(prompt_composition)
        return _composition_action(service, lambda: service.set_writer_model(
            session_id, body.writer_model_id,
            expected_writer_model_id=body.expected_writer_model_id,
        ))

    @router.post(
        "/api/prompt-lab/sessions/{session_id}/composition/final-prompt/variants/zh/stream"
    )
    def stream_chinese_prompt_variant(
        session_id: str,
        body: ChinesePromptVariantBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_prompt_composition(prompt_composition)
        return _composition_stream_action(
            service,
            lambda: service.stream_generate_chinese_variant(
                session_id,
                body.model_id,
                include_reasoning=include_reasoning,
            ),
        )

    @router.post("/api/prompt-lab/sessions/{session_id}/super-fast/stream")
    def stream_super_fast_ref2v(
        session_id: str,
        body: SuperFastRef2VBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        lab_service = _require_prompt_lab(prompt_lab)
        composition_service = _require_prompt_composition(prompt_composition)
        with http_errors('prompt session or internal cookbook not found'):
            source_session = lab_service.get_session(session_id)
            if (
                source_session.profile_id != "minimax.h3.ref2v.direct"
                or source_session.profile_version not in {"0.1.0", "0.4.0"}
                or source_session.session_mode.value != "direct_multimodal"
            ):
                raise ValueError(
                    "super-fast generation is only available for Ref2V Direct sessions"
                )
            try:
                existing_composition = composition_service.get(session_id)
            except (KeyError, FileNotFoundError):
                existing_composition = None
            cookbook_version = SUPER_FAST_REF2V_COOKBOOK_VERSION
            if existing_composition is not None:
                if (
                    existing_composition.cookbook.cookbook_id
                    != SUPER_FAST_REF2V_COOKBOOK_ID
                    or existing_composition.cookbook.version not in {"0.1.0", "0.2.0"}
                ):
                    raise ValueError(
                        "this session already uses a non-super-fast cookbook"
                    )
                cookbook_version = existing_composition.cookbook.version
            session = lab_service.create_super_fast_brief(
                session_id,
                body.source_text,
                body.creative_freedom,
                creative_axes=(
                    body.creative_axes.domain_value() if body.creative_axes else None
                ),
                creative_audacity=body.creative_audacity,
                legacy_plan=cookbook_version == "0.1.0",
            )
            composition_service.configure(
                session_id,
                SUPER_FAST_REF2V_COOKBOOK_ID,
                cookbook_version,
                (
                    CookbookBinding(
                        slot_id="references",
                        reference_ids=tuple(
                            reference.reference_id
                            for reference in session.references
                        ),
                    ),
                ),
            )
        return _composition_stream_action(
            composition_service,
            lambda: composition_service.stream_generate_super_fast(
                session_id,
                include_reasoning=include_reasoning,
            ),
        )

    @router.post("/api/prompt-lab/sessions/{session_id}/{stage}/generate/stream")
    def stream_composition_generation(
        session_id: str,
        stage: str,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_prompt_composition(prompt_composition)
        composition_stage = _parse_composition_stage(stage)
        return _composition_stream_action(
            service,
            lambda: service.stream_generate(
                session_id,
                composition_stage,
                include_reasoning=include_reasoning,
            ),
        )

    @router.post(
        "/api/prompt-lab/sessions/{session_id}/beat-sheet/reconcile/stream"
    )
    def stream_action_plan_reconciliation(
        session_id: str,
        body: PlanArbitrationBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_prompt_composition(prompt_composition)
        return _composition_stream_action(
            service,
            lambda: service.stream_reconcile_action_plan(
                session_id,
                body.decisions,
                body.instruction,
                include_reasoning=include_reasoning,
            ),
        )

    @router.post("/api/prompt-lab/sessions/{session_id}/{stage}/edit")
    def edit_composition_stage(
        session_id: str,
        stage: str,
        body: PromptEditBody,
    ) -> dict[str, object]:
        service = _require_prompt_composition(prompt_composition)
        composition_stage = _parse_composition_stage(stage)
        return _composition_action(
            service,
            lambda: service.edit(session_id, composition_stage, body.content),
        )

    @router.post("/api/prompt-lab/sessions/{session_id}/{stage}/revise/stream")
    def stream_composition_revision(
        session_id: str,
        stage: str,
        body: PromptRevisionBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_prompt_composition(prompt_composition)
        composition_stage = _parse_composition_stage(stage)
        return _composition_stream_action(
            service,
            lambda: service.stream_revise(
                session_id,
                composition_stage,
                body.instruction,
                include_reasoning=include_reasoning,
            ),
        )

    @router.post("/api/prompt-lab/sessions/{session_id}/{stage}/approve")
    def approve_composition_stage(
        session_id: str,
        stage: str,
    ) -> dict[str, object]:
        service = _require_prompt_composition(prompt_composition)
        composition_stage = _parse_composition_stage(stage)
        return _composition_action(
            service,
            lambda: service.approve(session_id, composition_stage),
        )

    return router
