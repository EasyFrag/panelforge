"""Social lab web for the PanelForge Lab HTTP interface."""

from __future__ import annotations
from typing import TypedDict
from .http_support import http_errors
from typing import Annotated
from fastapi import File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from panelforge.application import SocialLabService
from panelforge.domain import SocialChannelProfile, SocialLanguage, SocialProject
from fastapi import APIRouter
from .http_streaming import stream_response
from .http_support import _serialize_llm_model
from .media_http import MAX_IMAGE_BYTES, MAX_SOCIAL_VIDEO_BYTES, _close_uploads, detect_image_media_type, detect_video_media_type


class SocialProfileBody(BaseModel):
    name: str
    language: str = "en"
    mood: str = ""
    vibe: str = ""
    example: str = ""
    instructions: str = ""


class SocialChatBody(BaseModel):
    message: str
    model_id: str | None = None
    language: str | None = None
    variant_count: int | None = Field(default=None, ge=1, le=8)
    mood: str | None = None
    vibe: str | None = None
    example: str | None = None
    instructions: str | None = None
    channel_profile_id: str | None = None
    update_profile: bool = False


class SocialProfilePayload(TypedDict):
    profile_id: str
    name: str
    language: str
    mood: str
    vibe: str
    example: str
    instructions: str


def serialize_social_profile(profile: SocialChannelProfile) -> SocialProfilePayload:
    return {
        "profile_id": profile.profile_id,
        "name": profile.name,
        "language": profile.language.value,
        "mood": profile.mood,
        "vibe": profile.vibe,
        "example": profile.example,
        "instructions": profile.instructions,
    }


class SocialProjectPayload(TypedDict):
    project_id: str
    id: str
    name: str
    model_id: str
    language: str
    variant_count: int
    video_asset_id: str
    video_filename: str
    video_url: str
    keyframes: list[dict[str, object]]
    mood: str
    vibe: str
    example: str
    instructions: str
    channel_profile_id: str | None
    source_prompt_found: bool
    turns: list[dict[str, object]]
    latest_variants: list[dict[str, object]]


def serialize_social_project(project: SocialProject) -> SocialProjectPayload:
    return {
        "project_id": project.project_id,
        "id": project.project_id,
        "name": project.name,
        "model_id": project.model_id,
        "language": project.language.value,
        "variant_count": project.variant_count,
        "video_asset_id": project.video_asset_id,
        "video_filename": project.video_filename,
        "video_url": f"/api/assets/{project.video_asset_id}/content",
        "keyframes": [
            {
                "asset_id": asset_id,
                "position_percent": (10, 35, 65, 90)[index],
                "content_url": f"/api/assets/{asset_id}/content",
            }
            for index, asset_id in enumerate(project.keyframe_asset_ids)
        ],
        "mood": project.mood,
        "vibe": project.vibe,
        "example": project.example,
        "instructions": project.instructions,
        "channel_profile_id": project.channel_profile_id,
        "source_prompt_found": project.source_prompt is not None,
        "turns": [
            {
                "turn_id": turn.turn_id,
                "role": turn.role.value,
                "content": turn.content,
                "variants": [
                    {
                        "angle": variant.angle,
                        "hook": variant.hook,
                        "caption": variant.caption,
                        "hashtags": list(variant.hashtags),
                        "emojis": list(variant.emojis),
                    }
                    for variant in turn.variants
                ],
            }
            for turn in project.turns
        ],
        "latest_variants": [
            {
                "angle": variant.angle,
                "hook": variant.hook,
                "caption": variant.caption,
                "hashtags": list(variant.hashtags),
                "emojis": list(variant.emojis),
            }
            for variant in project.latest_variants
        ],
    }


def _require_social_lab(value: SocialLabService | None) -> SocialLabService:
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="Social Lab is not configured",
        )
    return value


def social_lab_router(*, social_lab: SocialLabService | None) -> APIRouter:
    router = APIRouter()

    @router.get("/api/social-lab/spec")
    def social_lab_spec() -> dict[str, object]:
        service = _require_social_lab(social_lab)
        return {
            "llm_models": [
                _serialize_llm_model(model) for model in service.list_models()
            ],
            "languages": [
                {"id": SocialLanguage.ENGLISH.value, "label": "English"},
                {"id": SocialLanguage.FRENCH.value, "label": "Français"},
            ],
            "defaults": {
                "language": SocialLanguage.ENGLISH.value,
                "variant_count": 3,
                "keyframe_positions": [10, 35, 65, 90],
            },
            "limits": {
                "video_bytes": MAX_SOCIAL_VIDEO_BYTES,
                "keyframe_bytes": MAX_IMAGE_BYTES,
                "variant_count": {"minimum": 1, "maximum": 8},
            },
        }

    @router.get("/api/social-lab/profiles")
    def list_social_profiles(limit: int = 100) -> dict[str, object]:
        service = _require_social_lab(social_lab)
        try:
            return {
                "profiles": [
                    serialize_social_profile(profile)
                    for profile in service.list_profiles(limit)
                ]
            }
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post(
        "/api/social-lab/profiles",
        status_code=status.HTTP_201_CREATED,
    )
    def create_social_profile(body: SocialProfileBody) -> dict[str, object]:
        service = _require_social_lab(social_lab)
        try:
            return {
                "profile": serialize_social_profile(service.save_profile(
                    profile_id=None,
                    name=body.name,
                    language=SocialLanguage(body.language),
                    mood=body.mood,
                    vibe=body.vibe,
                    example=body.example,
                    instructions=body.instructions,
                ))
            }
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.put("/api/social-lab/profiles/{profile_id}")
    def update_social_profile(
        profile_id: str,
        body: SocialProfileBody,
    ) -> dict[str, object]:
        service = _require_social_lab(social_lab)
        with http_errors('channel profile not found'):
            service.get_profile(profile_id)
            return {
                "profile": serialize_social_profile(service.save_profile(
                    profile_id=profile_id,
                    name=body.name,
                    language=SocialLanguage(body.language),
                    mood=body.mood,
                    vibe=body.vibe,
                    example=body.example,
                    instructions=body.instructions,
                ))
            }

    @router.post(
        "/api/social-lab/projects",
        status_code=status.HTTP_201_CREATED,
    )
    async def create_social_project(
        name: Annotated[str, Form()],
        model_id: Annotated[str, Form()],
        language: Annotated[str, Form()],
        variant_count: Annotated[int, Form()],
        video: Annotated[UploadFile, File()],
        keyframes: Annotated[list[UploadFile], File()],
        mood: Annotated[str, Form()] = "",
        vibe: Annotated[str, Form()] = "",
        example: Annotated[str, Form()] = "",
        instructions: Annotated[str, Form()] = "",
        channel_profile_id: Annotated[str | None, Form()] = None,
    ) -> dict[str, object]:
        service = _require_social_lab(social_lab)
        try:
            video_content = await video.read(MAX_SOCIAL_VIDEO_BYTES + 1)
            if len(video_content) > MAX_SOCIAL_VIDEO_BYTES:
                raise ValueError("video exceeds the 250 MiB Social Lab limit")
            video_media_type = detect_video_media_type(video_content)
            if len(keyframes) != 4:
                raise ValueError("provide exactly four video keyframes")
            frame_values: list[tuple[bytes, str]] = []
            for keyframe in keyframes:
                content = await keyframe.read(MAX_IMAGE_BYTES + 1)
                if len(content) > MAX_IMAGE_BYTES:
                    raise ValueError("a Social Lab keyframe exceeds 25 MiB")
                frame_values.append((content, detect_image_media_type(content)))
            video_asset = service.assets.create(
                video_content,
                media_type=video_media_type,
            )
            frame_assets = tuple(
                service.assets.create(content, media_type=media_type).asset_id
                for content, media_type in frame_values
            )
            project = service.create_project(
                name=name,
                model_id=model_id,
                language=SocialLanguage(language),
                variant_count=variant_count,
                video_asset_id=video_asset.asset_id,
                video_filename=video.filename or "video",
                keyframe_asset_ids=frame_assets,
                mood=mood,
                vibe=vibe,
                example=example,
                instructions=instructions,
                channel_profile_id=channel_profile_id or None,
            )
            return {"project": serialize_social_project(project)}
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        finally:
            await video.close()
            await _close_uploads(keyframes)

    @router.get("/api/social-lab/projects")
    def list_social_projects(limit: int = 30) -> dict[str, object]:
        service = _require_social_lab(social_lab)
        try:
            return {
                "projects": [
                    serialize_social_project(project)
                    for project in service.list_projects(limit)
                ]
            }
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/api/social-lab/projects/{project_id}")
    def get_social_project(project_id: str) -> dict[str, object]:
        service = _require_social_lab(social_lab)
        try:
            return {
                "project": serialize_social_project(
                    service.get_project(project_id)
                )
            }
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(status_code=404, detail="Social Lab project not found") from error

    @router.post("/api/social-lab/projects/{project_id}/chat/stream")
    def stream_social_chat(
        project_id: str,
        body: SocialChatBody,
        include_reasoning: bool = False,
    ) -> StreamingResponse:
        service = _require_social_lab(social_lab)
        try:
            language = (
                SocialLanguage(body.language)
                if body.language is not None
                else None
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return stream_response(service.stream_chat(project_id, body.message, model_id=body.model_id, language=language, variant_count=body.variant_count, mood=body.mood, vibe=body.vibe, example=body.example, instructions=body.instructions, channel_profile_id=body.channel_profile_id, update_profile=body.update_profile, include_reasoning=include_reasoning), serialize=serialize_social_project)

    return router
