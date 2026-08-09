"""Thin FastAPI adapter for the first PanelForge Lab vertical slice."""

from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path
from typing import Annotated

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from panelforge.application import (
    ChangeViewRunRequest,
    ChangeViewRunner,
    CompositionStreamEvent,
    NewReference,
    PromptCompositionService,
    PromptLabService,
    PromptLabStreamEvent,
    composition_picture_mapping,
)
from panelforge.domain import (
    CompositionStage,
    ControlKind,
    CookbookBinding,
    PromptComposition,
    PromptLabSession,
    ReferenceUse,
    RunRecord,
    RunReview,
)
from panelforge.domain.character import (
    CameraAzimuth,
    CameraElevation,
    ChangeView,
    ShotSize,
)


MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_PROMPT_REFERENCES = 8
_STATIC_DIRECTORY = Path(__file__).with_name("static")

_AZIMUTH_LABELS = {
    CameraAzimuth.FRONT: "Face",
    CameraAzimuth.FRONT_RIGHT_QUARTER: "Trois-quarts droit",
    CameraAzimuth.RIGHT_SIDE: "Profil droit",
    CameraAzimuth.BACK_RIGHT_QUARTER: "Dos trois-quarts droit",
    CameraAzimuth.BACK: "Dos",
    CameraAzimuth.BACK_LEFT_QUARTER: "Dos trois-quarts gauche",
    CameraAzimuth.LEFT_SIDE: "Profil gauche",
    CameraAzimuth.FRONT_LEFT_QUARTER: "Trois-quarts gauche",
}
_ELEVATION_LABELS = {
    CameraElevation.LOW: "Contre-plongée",
    CameraElevation.EYE_LEVEL: "À hauteur des yeux",
    CameraElevation.ELEVATED: "Caméra surélevée",
    CameraElevation.HIGH: "Plongée",
}
_SHOT_SIZE_LABELS = {
    ShotSize.CLOSE_UP: "Gros plan",
    ShotSize.MEDIUM: "Plan moyen",
    ShotSize.WIDE: "Plan large",
}


class PreviewBody(BaseModel):
    azimuth: str
    elevation: str
    shot_size: str


class ReviewBody(BaseModel):
    decision: str


class PromptEditBody(BaseModel):
    content: str


class PromptRevisionBody(BaseModel):
    instruction: str


class ReferenceUsesBody(BaseModel):
    uses: list[str]


class BriefStructureBody(BaseModel):
    source_text: str
    creative_freedom: int


class CompositionConfigureBody(BaseModel):
    cookbook_id: str
    cookbook_version: str
    bindings: dict[str, list[str]]


def create_app(
    runner: ChangeViewRunner,
    *,
    prompt_lab: PromptLabService | None = None,
    prompt_composition: PromptCompositionService | None = None,
    static_directory: Path | None = None,
) -> FastAPI:
    """Create an app around injected application services."""
    static_root = (static_directory or _STATIC_DIRECTORY).resolve()
    index_path = static_root / "index.html"
    if not index_path.is_file():
        raise FileNotFoundError(index_path)

    app = FastAPI(title="PanelForge Lab", version="0.1.0")
    app.mount("/static", StaticFiles(directory=static_root), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(index_path)

    @app.get("/api/change-view/spec")
    def change_view_spec() -> dict[str, object]:
        policy = runner.recipe.variation_policy
        controls: dict[str, object] = {}
        for control in policy.controls:
            serialized = {
                "id": control.control_id,
                "label": control.label,
                "kind": control.kind.value,
                "method": control.method.value,
                "default": (
                    str(control.default)
                    if control.control_id == "seed"
                    else control.default
                ),
                "advanced": control.advanced,
            }
            if control.kind is ControlKind.CHOICE:
                serialized["options"] = _choice_options(control.control_id)
            else:
                serialized.update(
                    {
                        "minimum": (
                            str(control.minimum)
                            if control.control_id == "seed"
                            else control.minimum
                        ),
                        "maximum": (
                            str(control.maximum)
                            if control.control_id == "seed"
                            else control.maximum
                        ),
                        "step": control.step,
                    }
                )
            controls[control.control_id] = serialized

        default_prompt = runner.recipe.render_prompt(
            ChangeView(
                source_asset_id="preview",
                azimuth=CameraAzimuth.FRONT,
                elevation=CameraElevation.EYE_LEVEL,
                shot_size=ShotSize.MEDIUM,
            )
        )
        lora_control = controls["multiple_angles_lora_strength"]
        controls["lora_strength"] = lora_control
        return {
            "operation_id": runner.recipe.reference.operation_id,
            "recipe": {
                "id": runner.recipe.reference.recipe_id,
                "version": runner.recipe.reference.version,
                "workflow_sha256": runner.recipe.reference.workflow_sha256,
                "status": "experimental",
            },
            "prompt_policy": runner.recipe.prompt_policy.value,
            "variation_method_order": [
                method.value for method in policy.method_order
            ],
            "controls": controls,
            "compiled_prompt": default_prompt,
        }

    @app.post("/api/change-view/preview")
    def preview_prompt(body: PreviewBody) -> dict[str, str]:
        try:
            change = ChangeView(
                source_asset_id="preview",
                azimuth=CameraAzimuth(body.azimuth),
                elevation=CameraElevation(body.elevation),
                shot_size=ShotSize(body.shot_size),
            )
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "compiled_prompt": runner.recipe.render_prompt(change),
            "prompt_policy": runner.recipe.prompt_policy.value,
        }

    @app.post("/api/runs", status_code=status.HTTP_202_ACCEPTED)
    async def create_run(
        background_tasks: BackgroundTasks,
        source_image: Annotated[UploadFile | None, File()] = None,
        source_asset_id: Annotated[str | None, Form()] = None,
        azimuth: Annotated[str, Form()] = CameraAzimuth.FRONT.value,
        elevation: Annotated[str, Form()] = CameraElevation.EYE_LEVEL.value,
        shot_size: Annotated[str, Form()] = ShotSize.MEDIUM.value,
        lora_strength: Annotated[str, Form()] = "1.0",
        seed: Annotated[str, Form()] = "151020854543467",
    ) -> dict[str, object]:
        if (source_image is None) == (source_asset_id is None):
            raise HTTPException(
                status_code=422,
                detail="provide exactly one source_image or source_asset_id",
            )
        try:
            parsed_azimuth = CameraAzimuth(azimuth)
            parsed_elevation = CameraElevation(elevation)
            parsed_shot_size = ShotSize(shot_size)
            parsed_lora_strength = float(lora_strength)
            parsed_seed = _parse_seed(seed)
            runner.recipe.is_experimental_lora_override(parsed_lora_strength)

            if source_image is not None:
                content = await source_image.read(MAX_IMAGE_BYTES + 1)
                await source_image.close()
                if len(content) > MAX_IMAGE_BYTES:
                    raise ValueError("source image exceeds the 25 MiB limit")
                media_type = detect_image_media_type(content)
                source = runner.assets.create(content, media_type=media_type)
                resolved_asset_id = source.asset_id
            else:
                assert source_asset_id is not None
                source = runner.assets.get(source_asset_id)
                resolved_asset_id = source.asset_id

            request = ChangeViewRunRequest(
                source_asset_id=resolved_asset_id,
                azimuth=parsed_azimuth,
                elevation=parsed_elevation,
                shot_size=parsed_shot_size,
                lora_strength=parsed_lora_strength,
                seed=parsed_seed,
            )
            run = runner.prepare(request)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="source asset not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        background_tasks.add_task(runner.execute, run.run_id)
        return serialize_run(run)

    @app.get("/api/runs")
    def list_runs(limit: int = 20) -> dict[str, object]:
        try:
            records = runner.runs.list(limit)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"runs": [serialize_run(run) for run in records]}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, object]:
        return serialize_run(_get_run_or_404(runner, run_id))

    @app.post("/api/runs/{run_id}/review")
    def review_run(run_id: str, body: ReviewBody) -> dict[str, object]:
        try:
            decision = RunReview(body.decision)
            if decision is RunReview.PENDING:
                raise ValueError("decision must be kept or rejected")
            return serialize_run(runner.review(run_id, decision))
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="run not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/runs/{run_id}/reuse")
    def reuse_run(run_id: str) -> dict[str, str]:
        try:
            asset = runner.reusable_asset(run_id)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="run not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "source_asset_id": asset.asset_id,
            "content_url": f"/api/assets/{asset.asset_id}/content",
        }

    @app.get("/api/assets/{asset_id}/content")
    def asset_content(asset_id: str) -> Response:
        try:
            asset = runner.assets.get(asset_id)
            content = runner.assets.read_bytes(asset_id)
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="asset not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return Response(
            content=content,
            media_type=asset.media_type,
            headers={"Cache-Control": "private, max-age=31536000, immutable"},
        )

    @app.get("/api/prompt-lab/spec")
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
                    "supports_interpretation": (
                        profile.interpretation_system_prompt is not None
                    ),
                    "supports_brief": profile.brief_system_prompt is not None,
                }
                for profile in service.list_profiles()
            ],
        }

    @app.get("/api/prompt-lab/models")
    def prompt_lab_models() -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return {
            "models": [
                {"id": model.model_id}
                for model in service.list_models()
            ]
        }

    @app.post("/api/prompt-lab/sessions", status_code=status.HTTP_201_CREATED)
    async def create_prompt_lab_session(
        images: Annotated[list[UploadFile], File()],
        roles: Annotated[list[str], Form()],
        model_id: Annotated[str, Form()],
        profile_id: Annotated[str, Form()],
        profile_version: Annotated[str, Form()],
        usages: Annotated[list[str] | None, Form()] = None,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        if not images or len(images) > MAX_PROMPT_REFERENCES:
            raise HTTPException(
                status_code=422,
                detail=f"provide between 1 and {MAX_PROMPT_REFERENCES} images",
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

        uploaded: list[
            tuple[bytes, str, str, str, tuple[ReferenceUse, ...]]
        ] = []
        try:
            service.get_profile(profile_id, profile_version)
            usage_values = usages or [ReferenceUse.SUBJECT.value] * len(images)
            for index, (image, role, raw_uses) in enumerate(
                zip(images, roles, usage_values, strict=True),
                1,
            ):
                content = await image.read(MAX_IMAGE_BYTES + 1)
                await image.close()
                if len(content) > MAX_IMAGE_BYTES:
                    raise ValueError(f"image {index} exceeds the 25 MiB limit")
                media_type = detect_image_media_type(content)
                label = (image.filename or "").strip() or f"Image {index}"
                uploaded.append(
                    (content, media_type, role, label, _parse_reference_uses(raw_uses))
                )

            references = tuple(
                NewReference(
                    asset_id=service.create_asset(content, media_type).asset_id,
                    role=role,
                    label=label,
                    uses=reference_uses,
                )
                for content, media_type, role, label, reference_uses in uploaded
            )
            session = service.create_session(
                model_id=model_id,
                profile_id=profile_id,
                profile_version=profile_version,
                references=references,
            )
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="prompt profile not found") from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return serialize_prompt_session(session)

    @app.get("/api/prompt-lab/sessions")
    def list_prompt_lab_sessions(limit: int = 20) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        try:
            sessions = service.list_sessions(limit)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "sessions": [serialize_prompt_session(session) for session in sessions]
        }

    @app.get("/api/prompt-lab/sessions/{session_id}")
    def get_prompt_lab_session(session_id: str) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        try:
            return serialize_prompt_session(service.get_session(session_id))
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="prompt session not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/analyze"
    )
    def analyze_prompt_reference(session_id: str, reference_id: str) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.analyze_reference(session_id, reference_id)
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/analyze/stream"
    )
    def stream_prompt_reference_analysis(
        session_id: str,
        reference_id: str,
    ) -> StreamingResponse:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_stream_response(
            service.stream_analyze_reference(session_id, reference_id)
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/edit"
    )
    def edit_prompt_reference(
        session_id: str,
        reference_id: str,
        body: PromptEditBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.edit_reference(session_id, reference_id, body.content)
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/revise"
    )
    def revise_prompt_reference(
        session_id: str,
        reference_id: str,
        body: PromptRevisionBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.revise_reference(
                session_id,
                reference_id,
                body.instruction,
            )
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/revise/stream"
    )
    def stream_prompt_reference_revision(
        session_id: str,
        reference_id: str,
        body: PromptRevisionBody,
    ) -> StreamingResponse:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_stream_response(
            service.stream_revise_reference(
                session_id,
                reference_id,
                body.instruction,
            )
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/approve"
    )
    def approve_prompt_reference(session_id: str, reference_id: str) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.approve_reference(session_id, reference_id)
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/uses"
    )
    def set_prompt_reference_uses(
        session_id: str,
        reference_id: str,
        body: ReferenceUsesBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.set_reference_uses(
                session_id,
                reference_id,
                tuple(ReferenceUse(value) for value in body.uses),
            )
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/interpret"
    )
    def interpret_prompt_reference(
        session_id: str,
        reference_id: str,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.interpret_reference(session_id, reference_id)
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/interpret/stream"
    )
    def stream_prompt_reference_interpretation(
        session_id: str,
        reference_id: str,
    ) -> StreamingResponse:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_stream_response(
            service.stream_interpret_reference(session_id, reference_id)
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/interpretation/edit"
    )
    def edit_prompt_interpretation(
        session_id: str,
        reference_id: str,
        body: PromptEditBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.edit_interpretation(
                session_id,
                reference_id,
                body.content,
            )
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/interpretation/revise"
    )
    def revise_prompt_interpretation(
        session_id: str,
        reference_id: str,
        body: PromptRevisionBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.revise_interpretation(
                session_id,
                reference_id,
                body.instruction,
            )
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/interpretation/revise/stream"
    )
    def stream_prompt_interpretation_revision(
        session_id: str,
        reference_id: str,
        body: PromptRevisionBody,
    ) -> StreamingResponse:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_stream_response(
            service.stream_revise_interpretation(
                session_id,
                reference_id,
                body.instruction,
            )
        )

    @app.post(
        "/api/prompt-lab/sessions/{session_id}/references/{reference_id}/interpretation/approve"
    )
    def approve_prompt_interpretation(
        session_id: str,
        reference_id: str,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.approve_interpretation(session_id, reference_id)
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/brief/structure")
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
            )
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/brief/structure/stream")
    def stream_prompt_brief(
        session_id: str,
        body: BriefStructureBody,
    ) -> StreamingResponse:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_stream_response(
            service.stream_structure_brief(
                session_id,
                body.source_text,
                body.creative_freedom,
            )
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/brief/edit")
    def edit_prompt_brief(
        session_id: str,
        body: PromptEditBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(lambda: service.edit_brief(session_id, body.content))

    @app.post("/api/prompt-lab/sessions/{session_id}/brief/revise")
    def revise_prompt_brief(
        session_id: str,
        body: PromptRevisionBody,
    ) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(
            lambda: service.revise_brief(session_id, body.instruction)
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/brief/revise/stream")
    def stream_prompt_brief_revision(
        session_id: str,
        body: PromptRevisionBody,
    ) -> StreamingResponse:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_stream_response(
            service.stream_revise_brief(session_id, body.instruction)
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/brief/approve")
    def approve_prompt_brief(session_id: str) -> dict[str, object]:
        service = _require_prompt_lab(prompt_lab)
        return _prompt_action(lambda: service.approve_brief(session_id))

    @app.get("/api/prompt-lab/cookbooks")
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
                    "stages": list(cookbook.stages),
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

    @app.get("/api/prompt-lab/sessions/{session_id}/composition")
    def get_prompt_composition(session_id: str) -> dict[str, object]:
        service = _require_prompt_composition(prompt_composition)
        try:
            composition = service.get(session_id)
        except (KeyError, FileNotFoundError):
            return {"composition": None}
        return {"composition": serialize_prompt_composition(composition, service)}

    @app.post("/api/prompt-lab/sessions/{session_id}/composition")
    def configure_prompt_composition(
        session_id: str,
        body: CompositionConfigureBody,
    ) -> dict[str, object]:
        service = _require_prompt_composition(prompt_composition)
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
            ),
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/{stage}/generate/stream")
    def stream_composition_generation(
        session_id: str,
        stage: str,
    ) -> StreamingResponse:
        service = _require_prompt_composition(prompt_composition)
        composition_stage = _parse_composition_stage(stage)
        return _composition_stream_action(
            service,
            lambda: service.stream_generate(session_id, composition_stage),
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/{stage}/edit")
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

    @app.post("/api/prompt-lab/sessions/{session_id}/{stage}/revise/stream")
    def stream_composition_revision(
        session_id: str,
        stage: str,
        body: PromptRevisionBody,
    ) -> StreamingResponse:
        service = _require_prompt_composition(prompt_composition)
        composition_stage = _parse_composition_stage(stage)
        return _composition_stream_action(
            service,
            lambda: service.stream_revise(
                session_id,
                composition_stage,
                body.instruction,
            ),
        )

    @app.post("/api/prompt-lab/sessions/{session_id}/{stage}/approve")
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

    return app


def serialize_run(run: RunRecord) -> dict[str, object]:
    controls = {
        control.control_id: (
            str(control.value) if control.control_id == "seed" else control.value
        )
        for control in run.controls
    }
    output_asset_id = run.output_asset_ids[0] if run.output_asset_ids else None
    return {
        "id": run.run_id,
        "run_id": run.run_id,
        "status": run.status.value,
        "decision": run.review_status.value,
        "recipe": {
            "id": run.recipe.recipe_id,
            "version": run.recipe.version,
            "workflow_sha256": run.recipe.workflow_sha256,
        },
        "source_asset_id": run.source_asset_ids[0],
        "source_url": f"/api/assets/{run.source_asset_ids[0]}/content",
        "output_asset_id": output_asset_id,
        "result_asset_id": output_asset_id,
        "result_url": (
            f"/api/assets/{output_asset_id}/content" if output_asset_id else None
        ),
        "parent_run_id": run.parent_run_id,
        "controls": controls,
        "compiled_prompt": run.prompt.positive,
        "negative_prompt": run.prompt.negative,
        "prompt_policy": run.prompt.policy.value,
        "experimental_overrides": list(run.experimental_overrides),
        "execution_id": run.execution_id,
        "compiled_workflow_sha256": run.compiled_workflow_sha256,
        "error": run.error,
    }


def detect_image_media_type(content: bytes) -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if (
        len(content) >= 12
        and content.startswith(b"RIFF")
        and content[8:12] == b"WEBP"
    ):
        return "image/webp"
    raise ValueError("source must be a PNG, JPEG or WebP image")


def serialize_prompt_session(session: PromptLabSession) -> dict[str, object]:
    return {
        "id": session.session_id,
        "session_id": session.session_id,
        "model_id": session.model_id,
        "profile": {
            "id": session.profile_id,
            "version": session.profile_version,
        },
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
                "origin": revision.origin.value,
                "parent_revision_id": revision.parent_revision_id,
                "instruction": revision.instruction,
                "references": [
                    {
                        "reference_id": reference.reference_id,
                        "analysis_revision_id": reference.analysis_revision_id,
                        "uses": [use.value for use in reference.uses],
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


def serialize_prompt_composition(
    composition: PromptComposition,
    service: PromptCompositionService,
) -> dict[str, object]:
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
                }
                for revision in document.revisions
            ],
        }
    return {
        "source_session_id": composition.source_session_id,
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
        "documents": documents,
    }


def _require_prompt_lab(value: PromptLabService | None) -> PromptLabService:
    if value is None:
        raise HTTPException(status_code=503, detail="Prompt Lab is not configured")
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
    try:
        return serialize_prompt_session(action())
    except (KeyError, FileNotFoundError) as error:
        raise HTTPException(status_code=404, detail="prompt session or reference not found") from error
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _prompt_stream_response(
    events: Iterator[PromptLabStreamEvent],
) -> StreamingResponse:
    def encoded_events() -> Iterator[str]:
        try:
            for event in events:
                payload: dict[str, object] = {
                    "kind": event.kind.value,
                    "phase": event.phase.value,
                    "text": event.text,
                    "progress": event.progress,
                    "finish_reason": event.finish_reason,
                    "max_tokens": event.max_tokens,
                }
                if event.session is not None:
                    payload["session"] = serialize_prompt_session(event.session)
                yield _encode_sse(event.kind.value, payload)
        except Exception as error:
            yield _encode_sse(
                "error",
                {
                    "kind": "error",
                    "phase": "failed",
                    "message": str(error),
                },
            )

    return StreamingResponse(
        encoded_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _composition_action(service: PromptCompositionService, action) -> dict[str, object]:
    try:
        composition = action()
        return {"composition": serialize_prompt_composition(composition, service)}
    except (KeyError, FileNotFoundError) as error:
        raise HTTPException(
            status_code=404,
            detail="prompt session, composition or cookbook not found",
        ) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _composition_stream_response(
    service: PromptCompositionService,
    events: Iterator[CompositionStreamEvent],
) -> StreamingResponse:
    def encoded_events() -> Iterator[str]:
        try:
            for event in events:
                payload: dict[str, object] = {
                    "kind": event.kind.value,
                    "phase": event.phase.value,
                    "text": event.text,
                    "progress": event.progress,
                    "finish_reason": event.finish_reason,
                    "max_tokens": event.max_tokens,
                }
                if event.composition is not None:
                    payload["composition"] = serialize_prompt_composition(
                        event.composition,
                        service,
                    )
                yield _encode_sse(event.kind.value, payload)
        except Exception as error:
            yield _encode_sse(
                "error",
                {
                    "kind": "error",
                    "phase": "failed",
                    "message": str(error),
                },
            )

    return StreamingResponse(
        encoded_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _composition_stream_action(
    service: PromptCompositionService,
    action,
) -> StreamingResponse:
    try:
        events = action()
    except (KeyError, FileNotFoundError) as error:
        raise HTTPException(
            status_code=404,
            detail="prompt session, composition or cookbook not found",
        ) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _composition_stream_response(service, events)


def _parse_composition_stage(value: str) -> CompositionStage:
    try:
        return CompositionStage(value.replace("-", "_"))
    except ValueError as error:
        raise HTTPException(status_code=404, detail="composition stage not found") from error


def _encode_sse(event: str, payload: dict[str, object]) -> str:
    return (
        f"event: {event}\n"
        f"data: {json.dumps(payload, ensure_ascii=False, allow_nan=False)}\n\n"
    )


def _parse_reference_uses(value: str) -> tuple[ReferenceUse, ...]:
    if not isinstance(value, str):
        raise TypeError("reference uses must be a string")
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        raise ValueError("reference uses must not be empty")
    return tuple(ReferenceUse(part) for part in parts)


def _choice_options(control_id: str) -> list[dict[str, str]]:
    if control_id == "azimuth":
        return [
            {"value": value.value, "label": _AZIMUTH_LABELS[value]}
            for value in CameraAzimuth
        ]
    if control_id == "elevation":
        return [
            {"value": value.value, "label": _ELEVATION_LABELS[value]}
            for value in CameraElevation
        ]
    if control_id == "shot_size":
        return [
            {"value": value.value, "label": _SHOT_SIZE_LABELS[value]}
            for value in ShotSize
        ]
    return []


def _parse_seed(value: str) -> int:
    if not isinstance(value, str) or not value or not value.isdecimal():
        raise ValueError("seed must be an unsigned decimal integer")
    seed = int(value)
    if not 0 <= seed < 2**64:
        raise ValueError("seed must be between 0 and 2^64 - 1")
    return seed


def _get_run_or_404(runner: ChangeViewRunner, run_id: str) -> RunRecord:
    try:
        return runner.runs.get(run_id)
    except (KeyError, FileNotFoundError) as error:
        raise HTTPException(status_code=404, detail="run not found") from error
