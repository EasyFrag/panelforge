"""Small fabrication API; generation delegates to the existing application services."""
from typing import Annotated, Literal
from dataclasses import asdict

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from panelforge.application.episodes import EpisodeConflict
from panelforge.domain.episodes import REFERENCE_ROLES
from panelforge.domain.krea2_batch import Krea2AspectRatio, Krea2LoraSelection
from panelforge.domain.krea2_sampling import Krea2AssistedSettings, sampling_from_dict
from panelforge.domain.krea2_assisted_workflows import workflow_selection_from_dict
from panelforge.domain.video_lab import VideoLabSettings, VideoAspectRatio
from panelforge.domain.h3_bunny import H3BunnySettings, bunny_geometry
from panelforge.domain.h3_render import H3VideoLoraStack
from panelforge.domain.production import ThermalPolicy


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateBody(StrictBody):
    expected_version: int = Field(ge=1, strict=True)


class RevisionBody(StrictBody):
    expected_revision: int = Field(ge=1, strict=True)


class ReferenceBody(RevisionBody):
    description: str = Field(min_length=1, max_length=6000)
    prompt: str = Field(default="", max_length=40000)
    model_id: str = Field(min_length=1, max_length=300)
    render_settings: dict | None = None
    inherit_image_settings: bool | None = Field(default=None, strict=True)


class ContinuityBody(RevisionBody):
    visual_continuity: dict


class VariantSelectionBody(RevisionBody):
    asset_id: str = Field(min_length=1, max_length=120)


class BindingBody(StrictBody):
    reference_id: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=80)


class CreativeAxesBody(StrictBody):
    scene_life: int = Field(ge=0, le=3, strict=True)
    camera: int = Field(ge=0, le=3, strict=True)
    extra_motion: int = Field(ge=0, le=3, strict=True)
    dialogue: int = Field(default=0, ge=0, le=3, strict=True)


class SceneBody(RevisionBody):
    intention: str = Field(min_length=1, max_length=16000)
    duration: float = Field(ge=5, le=15, allow_inf_nan=False)
    references: list[BindingBody] = Field(min_length=1, max_length=9)
    plan_model_id: str = Field(min_length=1, max_length=300)
    writer_model_id: str = Field(min_length=1, max_length=300)
    shot_count: int | None = Field(default=None, ge=1, le=6, strict=True)
    audacity: int = Field(default=2, ge=0, le=3, strict=True)
    creative_axes: CreativeAxesBody | None = None


class StartBody(RevisionBody):
    request_id: str = Field(min_length=8, max_length=100)
    instruction: str = Field(default="", max_length=3000)
    resume: bool = False
    expected_visual_revision: int | None = Field(default=None, ge=1, strict=True)


class RenderImageBody(RevisionBody):
    request_id: str = Field(min_length=8, max_length=100)
    settings: dict
    expected_visual_revision: int | None = Field(default=None, ge=1, strict=True)


class ImageBody(RevisionBody):
    asset_id: str = Field(min_length=1, max_length=100)


class StyleBody(StrictBody):
    style: str = Field(max_length=3000)
    expected_style: str = Field(max_length=3000)


class RenderSetupBody(RevisionBody):
    parameters: dict


class VisualBody(RevisionBody):
    style: str = Field(default="", max_length=3000)
    settings: dict


class StylePresetBody(RevisionBody):
    preset_id: str | None = Field(default=None, max_length=128)


class StyleImageBody(RevisionBody):
    reference_id: str | None = Field(default=None, max_length=80)


class ReferenceBatchProfileBody(StrictBody):
    model_id: str = Field(min_length=1, max_length=300)
    settings: dict
    inherit_technical: bool = Field(default=False, strict=True)


class ReferenceBatchThermalBody(StrictBody):
    stop_temperature_c: float = Field(default=85.0, ge=30, le=110, allow_inf_nan=False)
    resume_temperature_c: float = Field(default=40.0, ge=15, le=109, allow_inf_nan=False)
    cooldown_seconds: int = Field(default=120, ge=0, le=86400, strict=True)
    monitor_local: bool = True
    monitor_remote: bool = True
    pause_when_unavailable: bool = False


class ReferenceBatchBody(StrictBody):
    expected_visual_revision: int = Field(ge=1, strict=True)
    request_id: str = Field(min_length=8, max_length=100)
    reference_ids: list[str] = Field(min_length=1)
    profiles: dict[str, ReferenceBatchProfileBody]
    thermal: ReferenceBatchThermalBody = Field(default_factory=ReferenceBatchThermalBody)


class VideoDefaultsBody(StrictBody):
    expected_video_revision: int = Field(ge=1, strict=True)
    parameters: dict


class VideoInheritanceBody(RevisionBody):
    inherit: bool = Field(strict=True)


class VideoChainBody(StrictBody):
    expected_video_revision: int = Field(ge=1, strict=True)
    request_id: str = Field(min_length=8, max_length=100)
    scene_ids: list[str] = Field(min_length=1)
    inter_video_cooldown_seconds: int = Field(default=30, ge=1, le=3600, strict=True)
    auto_dlss: bool = Field(default=False, strict=True)


class PauseVideoChainBody(StrictBody):
    mode: Literal["after_active", "after_queue"] = "after_active"


def episodes_router(service, *, serialize_image_project, validate_image, image_body, render_body):
    router = APIRouter(prefix="/api/episodes")

    def current():
        if service is None:
            raise HTTPException(503, "L’atelier Fabrication sera disponible après le redémarrage du Lab à jour.")
        return service

    def invoke(action):
        try:
            return action()
        except (FileNotFoundError, KeyError) as error:
            raise HTTPException(404, "Fabrication, fiche ou scène introuvable.") from error
        except EpisodeConflict as error:
            raise HTTPException(409, str(error)) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(422, str(error)) from error

    def image_settings(raw):
        body = image_body.model_validate(raw)
        workflow = workflow_selection_from_dict(body.workflow)
        default_sampling = "moody_beta" if workflow.recipe_id == "krea2-flux-klein" else "current"
        return body, Krea2AssistedSettings(model_name=body.model_id,
            aspect_ratio=Krea2AspectRatio(body.aspect_ratio), megapixels=body.megapixels,
            sampling=sampling_from_dict(body.sampling, default_preset_id=default_sampling), workflow=workflow,
            loras=tuple(Krea2LoraSelection(name=l.name, strength=l.strength) for l in (body.loras or [])))

    def video_setup(raw):
        p = render_body.model_validate(raw)
        settings = VideoLabSettings(aspect_ratio=VideoAspectRatio(p.aspect_ratio), megapixels=p.megapixels,
            duration_seconds=p.duration_seconds, steps=p.steps, seed=int(p.seed) if p.seed is not None and str(p.seed).strip() else 0,
            seed_locked=p.seed_locked)
        if p.bunny:
            H3BunnySettings(**p.bunny.model_dump())
            bunny_geometry(settings, p.initial_megapixels)
        stack = H3VideoLoraStack.from_dict(p.video_loras.model_dump() if p.video_loras else None)
        if stack:
            stack.validate_mode(p.bunny is not None)
        return dict(recipe=dict(id=p.recipe_id, version=p.recipe_version), checkpoint=p.checkpoint,
            settings=dict(aspect_ratio=p.aspect_ratio, megapixels=p.megapixels,
                duration_seconds=p.duration_seconds, steps=p.steps, seed=p.seed or 0),
            seed_locked=p.seed_locked, initial_megapixels=p.initial_megapixels, music_enabled=p.music_enabled,
            spectrum_enabled=p.spectrum_enabled, force_upscale=p.force_upscale,
            bunny=p.bunny.model_dump() if p.bunny else None,
            video_loras=p.video_loras.model_dump() if p.video_loras else None,
            video_lora=p.video_lora.model_dump() if p.video_lora else None)

    @router.get("/stories/{story_id}")
    def list_episodes(story_id: str):
        return invoke(lambda: dict(episodes=current().store.list(story_id)))

    @router.post("/stories/{story_id}", status_code=201)
    def create(story_id: str, body: CreateBody):
        return invoke(lambda: current().create(story_id, body.expected_version))

    @router.get("/{identity}")
    def get(identity: str):
        return invoke(lambda: current().get(identity))

    @router.put("/{identity}/style")
    def style(identity: str, body: StyleBody):
        return invoke(lambda: current().set_style(identity, **body.model_dump()))

    @router.put("/{identity}/visual")
    def visual(identity: str, body: VisualBody):
        def save():
            if set(body.settings) not in ({"model_id", "loras", "sampling"},
                                          {"model_id", "loras", "sampling", "workflow"}):
                raise ValueError("Les réglages communs attendent workflow, checkpoint, LoRA et sampling.")
            # Reuse the same validation and bounds as KREA2 Assisted.
            _, validated = image_settings({**body.settings, "workflow": body.settings.get("workflow"),
                                           "prompt": "Réglages communs", "aspect_ratio": Krea2AspectRatio.PORTRAIT_WIDESCREEN.value,
                                           "megapixels": 2.1})
            settings = dict(model_id=validated.model_name, loras=[asdict(l) for l in validated.loras],
                            sampling=asdict(validated.sampling), workflow=asdict(validated.workflow))
            return current().update_visual(identity, body.expected_revision, body.style, settings)
        return invoke(save)

    @router.put("/{identity}/style-preset")
    def style_preset(identity: str, body: StylePresetBody):
        return invoke(lambda: current().apply_style_preset(identity, **body.model_dump()))

    @router.put("/{identity}/style-image")
    def style_image(identity: str, body: StyleImageBody):
        return invoke(lambda: current().select_style_image(identity, **body.model_dump()))

    @router.post("/{identity}/style-image", status_code=201)
    async def import_style_image(identity: str, expected_revision: Annotated[int, Form()], image: Annotated[UploadFile, File()]):
        try:
            content = await image.read(25 * 1024 * 1024 + 1)
            if not content or len(content) > 25 * 1024 * 1024:
                raise ValueError("Choisissez une image de moins de 25 Mo.")
            media_type = validate_image(content)
            return invoke(lambda: current().import_style_image(identity, expected_revision, content,
                media_type, (image.filename or "Style visuel")[:240]))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            await image.close()

    @router.put("/{identity}/continuity")
    def continuity(identity: str, body: ContinuityBody):
        return invoke(lambda: current().update_continuity(identity, body.expected_revision, body.visual_continuity))

    @router.post("/{identity}/references/{ref_id}/variant")
    def create_variant(identity: str, ref_id: str, body: RevisionBody):
        return invoke(lambda: current().create_continuity_variant(identity, ref_id, body.expected_revision))

    @router.get("/{identity}/references/{ref_id}/variant-results")
    def variant_results(identity: str, ref_id: str):
        return invoke(lambda: current().continuity_variant_results(identity, ref_id))

    @router.post("/{identity}/references/{ref_id}/variant-select")
    def variant_select(identity: str, ref_id: str, body: VariantSelectionBody):
        return invoke(lambda: current().select_continuity_variant(identity, ref_id, body.expected_revision, body.asset_id))

    @router.put("/{identity}/references/{ref_id}")
    def update_reference(identity: str, ref_id: str, body: ReferenceBody):
        def save():
            if body.render_settings:
                image_settings({**body.render_settings, "prompt": body.prompt or "Prompt à préparer"})
            return current().update_reference(identity, ref_id, **body.model_dump())
        return invoke(save)

    @router.get("/{identity}/references/{ref_id}/project")
    def image_project(identity: str, ref_id: str):
        def read():
            project = current().reference_project(identity, ref_id)
            return dict(project=serialize_image_project(project) if project else None)
        return invoke(read)

    @router.post("/{identity}/references/{ref_id}/prompt", status_code=202)
    def image_prompt(identity: str, ref_id: str, body: StartBody):
        return invoke(lambda: current().prepare_reference(identity, ref_id, body.expected_revision, body.request_id, body.instruction,
                                                          expected_visual_revision=body.expected_visual_revision))

    @router.get("/{identity}/references/{ref_id}/calls")
    def image_calls(identity: str, ref_id: str):
        def load():
            value = current()
            ref = value._item(value.store.get(identity), "references", ref_id)
            traces = value.stories.traces
            return dict(calls=traces.list(project_id=ref["krea_project_id"]) if traces and ref["krea_project_id"] else [],
                        scope="Échanges KREA2 de cette fiche")
        return invoke(load)

    @router.post("/{identity}/references/{ref_id}/render", status_code=202)
    def render_image(identity: str, ref_id: str, body: RenderImageBody):
        def start():
            parsed, settings = image_settings(body.settings)
            seed = int(parsed.seed) if parsed.seed is not None and str(parsed.seed).strip() else None
            return current().render_reference(identity, ref_id, body.expected_revision, body.request_id, settings, seed,
                                              expected_visual_revision=body.expected_visual_revision)
        return invoke(start)

    @router.post("/{identity}/reference-batches", status_code=202)
    def start_reference_batch(identity: str, body: ReferenceBatchBody):
        def start():
            if set(body.profiles) != {"character", "location"}:
                raise ValueError("Configurez exactement un profil Personnages et un profil Décors.")
            profiles = {}
            for kind, profile in body.profiles.items():
                allowed = {"workflow", "model_id", "aspect_ratio", "megapixels", "seed", "loras", "sampling"}
                unexpected = set(profile.settings) - allowed
                if unexpected:
                    raise ValueError(f"Réglage de profil inattendu : {sorted(unexpected)[0]}.")
                parsed, settings = image_settings({**profile.settings, "prompt": f"Profil {kind}"})
                seed = int(parsed.seed) if parsed.seed is not None and str(parsed.seed).strip() else None
                profiles[kind] = dict(model_id=profile.model_id, settings=settings, seed=seed,
                                      inherit_technical=profile.inherit_technical)
            return current().start_reference_batch(identity,
                expected_visual_revision=body.expected_visual_revision,
                request_id=body.request_id, reference_ids=body.reference_ids,
                profiles=profiles, thermal=ThermalPolicy(**body.thermal.model_dump()))
        return invoke(start)

    @router.post("/{identity}/reference-batches/{batch_id}/cancel", status_code=202)
    def cancel_reference_batch(identity: str, batch_id: str):
        return invoke(lambda: current().cancel_reference_batch(identity, batch_id))

    @router.post("/{identity}/references/{ref_id}/select")
    def select_image(identity: str, ref_id: str, body: ImageBody):
        return invoke(lambda: current().select_image(identity, ref_id, **body.model_dump()))

    @router.post("/{identity}/references/{ref_id}/image", status_code=201)
    async def import_image(identity: str, ref_id: str, expected_revision: Annotated[int, Form()], image: Annotated[UploadFile, File()]):
        try:
            content = await image.read(25 * 1024 * 1024 + 1)
            if not content or len(content) > 25 * 1024 * 1024:
                raise ValueError("Choisissez une image de moins de 25 Mo.")
            media_type = validate_image(content)
            return invoke(lambda: current().import_image(identity, ref_id, expected_revision, content,
                                                         media_type, (image.filename or "Image importée")[:240]))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            await image.close()

    @router.put("/{identity}/scenes/{scene_id}")
    def update_scene(identity: str, scene_id: str, body: SceneBody):
        if any(b.role not in REFERENCE_ROLES for b in body.references):
            raise HTTPException(422, "Rôle de référence inconnu.")
        changes = body.model_dump()
        if changes["creative_axes"] is None:
            changes.pop("creative_axes")
        return invoke(lambda: current().update_scene(identity, scene_id, **changes))

    @router.post("/{identity}/scenes/{scene_id}/prompt", status_code=202)
    def scene_prompt(identity: str, scene_id: str, body: StartBody):
        return invoke(lambda: current().prepare_scene(identity, scene_id, body.expected_revision, body.request_id, body.resume))

    @router.put("/{identity}/scenes/{scene_id}/render-setup")
    def save_render(identity: str, scene_id: str, body: RenderSetupBody):
        return invoke(lambda: current().save_render_setup(identity, scene_id, body.expected_revision,
                                                          video_setup(body.parameters)))

    @router.put("/{identity}/video-defaults")
    def save_video_defaults(identity: str, body: VideoDefaultsBody):
        return invoke(lambda: current().save_video_defaults(identity, body.expected_video_revision,
                                                            video_setup(body.parameters)))

    @router.put("/{identity}/scenes/{scene_id}/render-inheritance")
    def video_inheritance(identity: str, scene_id: str, body: VideoInheritanceBody):
        return invoke(lambda: current().set_scene_video_inheritance(identity, scene_id,
                                                                    body.expected_revision, body.inherit))

    @router.post("/{identity}/video-chain", status_code=202)
    def start_video_chain(identity: str, body: VideoChainBody):
        return invoke(lambda: current().start_video_chain(identity,
            expected_video_revision=body.expected_video_revision, request_id=body.request_id,
            scene_ids=body.scene_ids,
            inter_video_cooldown_seconds=body.inter_video_cooldown_seconds,
            auto_dlss=body.auto_dlss))

    @router.post("/{identity}/video-chains/{chain_id}/pause", status_code=202)
    def pause_video_chain(identity: str, chain_id: str, body: PauseVideoChainBody | None = None):
        return invoke(lambda: current().pause_video_chain(
            identity, chain_id, mode=body.mode if body is not None else "after_active",
        ))

    @router.post("/{identity}/video-chains/{chain_id}/resume", status_code=202)
    def resume_video_chain(identity: str, chain_id: str):
        return invoke(lambda: current().resume_video_chain(identity, chain_id))

    return router
