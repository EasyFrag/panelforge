"""Dance imports and prompt editing, without a second rendering API."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, ConfigDict, Field
from panelforge.application.dance import DanceService


class PromptBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str = Field(min_length=1, max_length=60000)


class PolishBody(PromptBody):
    instruction: str = Field(min_length=1, max_length=4000)
    model_id: str = Field(min_length=1, max_length=240)


class FinalizeBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    megapixels: float = Field(gt=0.1, le=16, allow_inf_nan=False)


def dance_router(render, serialize_project):
    router = APIRouter(prefix='/api/dance')

    def service():
        if render is None or render.dance_media is None or not render.reference_video_workflows:
            raise HTTPException(503, 'L’atelier Danse est indisponible.')
        return DanceService(render)

    def call(fn):
        try:
            return fn()
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(404, 'Projet, référence ou essai introuvable.') from error
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from error

    @router.get('/projects')
    def projects():
        current = service()
        return {'available': current.media.available, 'projects': [
            {'id': p.project_id, 'title': p.dance_reference.label} for p in current.list()]}

    @router.post('/videos')
    def video(file: UploadFile = File(...)):
        return call(lambda: service().import_video(file.file.read(256 * 1024 * 1024 + 1)))

    @router.post('/projects')
    def create(image: UploadFile = File(...), video_asset_id: str = Form(...),
               start: float = Form(0), duration: float = Form(8), keep_audio: bool = Form(True),
               title: str = Form('Nouvelle danse')):
        return call(lambda: {'project': serialize_project(service().create(
            image=image.file.read(32 * 1024 * 1024 + 1), video_asset_id=video_asset_id,
            start=start, duration=duration, keep_audio=keep_audio, title=title))})

    @router.put('/projects/{project_id}/prompt')
    def save_prompt(project_id: str, body: PromptBody):
        return call(lambda: {'project': serialize_project(service().save_prompt(project_id, body.prompt))})

    @router.post('/projects/{project_id}/polish')
    def polish(project_id: str, body: PolishBody):
        return call(lambda: {'prompt': service().polish(project_id, **body.model_dump())})

    @router.post('/projects/{project_id}/attempts/{attempt_id}/finalize')
    def finalize(project_id: str, attempt_id: str, body: FinalizeBody):
        return call(lambda: {'project': serialize_project(service().finalize(project_id, attempt_id, body.megapixels))})

    return router
