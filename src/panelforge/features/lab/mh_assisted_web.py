"""HTTP boundary for assisted still compositions, catalogues and frozen attempts."""
import json
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool

from panelforge.application.qwen_edit import QwenEditConflict
from panelforge.domain import mh_assisted as policy
from panelforge.infrastructure.qwen_project_exports import project_zip
from .qwen_edit_web import RequestBody, RevisionBody, UpdateBody


class CreativeBody(RevisionBody):
    changes: dict


def mh_assisted_router(service):
    router = APIRouter(prefix="/api/image-lab/mh-assisted")

    def require():
        if service is None:
            raise HTTPException(503, "Création Assistée MH n’est pas configurée. Redémarre le Lab après la mise à jour.")

    def action(callback, *, project=True):
        require()
        try:
            result = callback()
            return {"project": service.public(result)} if project else result
        except QwenEditConflict as error:
            raise HTTPException(409, str(error)) from error
        except (FileNotFoundError, KeyError, StopIteration) as error:
            raise HTTPException(404, "Projet, référence ou élément du catalogue introuvable.") from error
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from error
        except OSError as error:
            raise HTTPException(503, str(error)) from error

    async def content(upload):
        if upload is None:
            return None
        try:
            data = await upload.read(policy.MAX_UPLOAD_BYTES + 1)
            if not data or len(data) > policy.MAX_UPLOAD_BYTES:
                raise HTTPException(422, "Choisis une image de 25 Mo maximum.")
            return data
        finally:
            await upload.close()

    async def reference_uploads(files, details):
        try:
            if len(files) > policy.MAX_ASSISTANT_IMAGES:
                raise HTTPException(422, "Choisis au maximum 32 images par ajout.")
            try:
                metadata = json.loads(details) if details else [{} for _ in files]
            except ValueError as error:
                raise HTTPException(422, "Description des références invalide.") from error
            if (not isinstance(metadata, list) or len(metadata) != len(files)
                    or any(not isinstance(m, dict) or set(m) - {"name", "role", "usage"} for m in metadata)):
                raise HTTPException(422, "Chaque image doit avoir sa propre description.")
            result, total = [], 0
            for upload, meta in zip(files, metadata):
                data = await content(upload)
                total += len(data)
                if total > policy.MAX_REFERENCE_BATCH_BYTES:
                    raise HTTPException(422, "Choisis au maximum 100 Mo d’images par ajout.")
                result.append({"name": (upload.filename or "Référence")[:70], **meta, "content": data})
            return result
        finally:
            for upload in files:
                await upload.close()

    @router.get("/spec")
    def spec():
        return action(lambda: dict(defaults=policy.Settings().record(), aspect_ratios=policy.RATIOS,
            max_render_images=policy.MAX_RENDER_IMAGES, max_assistant_images=policy.MAX_ASSISTANT_IMAGES,
            max_upload_bytes=policy.MAX_UPLOAD_BYTES, max_reference_batch_bytes=policy.MAX_REFERENCE_BATCH_BYTES,
            default_model_id=policy.DEFAULT_ASSISTANT_MODEL,
            prompt_languages=["en", "zh"], pose_catalog=service.poses.status()), project=False)

    @router.get("/models")
    def models():
        return action(lambda: dict(models=[dict(id=m.model_id, source=m.source, label=m.display_name or m.model_id)
            for m in service.list_models()]), project=False)

    @router.get("/loras")
    def loras(refresh: bool = False):
        return action(lambda: service.lora_inventory(refresh=refresh), project=False)

    @router.get("/poses")
    def poses():
        return action(lambda: dict(catalog=service.poses.status(), entries=service.poses.entries()
            if service.poses.status()["state"] == "ready" else []), project=False)

    @router.post("/poses/install")
    async def install_poses(force: bool = False):
        return await run_in_threadpool(action, lambda: dict(catalog=service.poses.install(force=force)), project=False)

    @router.get("/poses/{entry_id}/thumbnail")
    def thumbnail(entry_id: str):
        return action(lambda: FileResponse(service.poses.image_path(entry_id, thumbnail=True)), project=False)

    @router.get("/poses/{entry_id}/original")
    def original(entry_id: str):
        return action(lambda: FileResponse(service.poses.image_path(entry_id)), project=False)

    @router.get("/projects")
    def projects():
        return action(lambda: dict(projects=service.list()), project=False)

    @router.post("/projects", status_code=201)
    async def create(request_id: Annotated[str, Form(max_length=80)], name: Annotated[str, Form(max_length=120)],
                     intention: Annotated[str, Form(max_length=12000)] = "", model_id: Annotated[str, Form(max_length=300)] = "",
                     prompt_language: Annotated[Literal["en", "zh"], Form()] = "en",
                     preset_id: Annotated[str, Form(max_length=128)] = "",
                     art_style_id: Annotated[str, Form(max_length=240)] = "", pose_id: Annotated[str, Form(max_length=100)] = "",
                     reference: Annotated[UploadFile | None, File()] = None,
                     references: Annotated[list[UploadFile] | None, File()] = None,
                     reference_details: Annotated[str, Form(max_length=30000)] = ""):
        require()
        if reference is not None and (references or reference_details):
            for upload in [reference, *(references or [])]:
                await upload.close()
            raise HTTPException(422, "Utilise une seule liste d’images de référence.")
        data = await content(reference)
        uploads = await reference_uploads(references or [], reference_details) if references or reference_details else None
        return await run_in_threadpool(action, lambda: service.create_assisted(request_id=request_id, name=name,
            intention=intention, model_id=model_id, prompt_language=prompt_language, preset_id=preset_id,
            art_style_id=art_style_id, pose_id=pose_id, content=data, references=uploads))

    @router.get("/projects/{project_id}")
    def get(project_id: str):
        return action(lambda: service.get(project_id))

    @router.patch("/projects/{project_id}/stages/{stage_id}")
    def update(project_id: str, stage_id: str, body: UpdateBody):
        return action(lambda: service.update(project_id, stage_id, **body.model_dump()))

    @router.patch("/projects/{project_id}/stages/{stage_id}/creative")
    def creative(project_id: str, stage_id: str, body: CreativeBody):
        return action(lambda: service.configure(project_id, stage_id, **body.model_dump()))

    @router.post("/projects/{project_id}/stages/{stage_id}/references", status_code=201)
    async def reference(project_id: str, stage_id: str, image: Annotated[UploadFile, File()],
                        revision: Annotated[int, Form(ge=0)], usage: Annotated[Literal["render", "assistant"], Form()] = "render",
                        name: Annotated[str, Form(max_length=80)] = "Référence", role: Annotated[str, Form(max_length=300)] = ""):
        require()
        data = await content(image)
        return await run_in_threadpool(action, lambda: service.add_reference(project_id, stage_id,
            revision=revision, name=name, role=role, usage=usage, content=data))

    @router.post("/projects/{project_id}/stages/{stage_id}/references/batch", status_code=201)
    async def references_batch(project_id: str, stage_id: str,
                               revision: Annotated[int, Form(ge=0)], request_id: Annotated[str, Form(max_length=80)],
                               images: Annotated[list[UploadFile], File()],
                               reference_details: Annotated[str, Form(max_length=30000)] = "",
                               replace_id: Annotated[str, Form(max_length=80)] = ""):
        require()
        uploads = await reference_uploads(images, reference_details)
        return await run_in_threadpool(action, lambda: service.add_references(project_id, stage_id,
            revision=revision, request_id=request_id, references=uploads, replace_id=replace_id or None))

    @router.post("/projects/{project_id}/stages/{stage_id}/messages", status_code=202)
    def message(project_id: str, stage_id: str, body: RequestBody, tasks: BackgroundTasks):
        def start():
            project, message_id = service.begin_message(project_id, stage_id, **body.model_dump())
            tasks.add_task(service.execute_message, project_id, stage_id, message_id)
            return project
        return action(start)

    @router.post("/projects/{project_id}/stages/{stage_id}/messages/{message_id}/recover")
    def recover(project_id: str, stage_id: str, message_id: str, body: RevisionBody):
        return action(lambda: service.recover_message(project_id, stage_id, message_id, revision=body.revision))

    @router.get("/projects/{project_id}/stages/{stage_id}/messages/{message_id}")
    def message_detail(project_id: str, stage_id: str, message_id: str):
        def detail():
            stage = next(s for s in service.get(project_id)["stages"] if s["id"] == stage_id)
            return {"message": next(m for m in stage["messages"] if m["id"] == message_id)}
        return action(detail, project=False)

    @router.post("/projects/{project_id}/stages/{stage_id}/attempts", status_code=202)
    def generate(project_id: str, stage_id: str, body: RequestBody):
        return action(lambda: service.queue_attempt(project_id, stage_id, **body.model_dump()))

    @router.post("/projects/{project_id}/stages/{stage_id}/attempts/{attempt_id}/cancel")
    def cancel(project_id: str, stage_id: str, attempt_id: str):
        return action(lambda: service.cancel_attempt(project_id, stage_id, attempt_id))

    @router.post("/projects/{project_id}/stages/{stage_id}/attempts/{attempt_id}/restore")
    def restore(project_id: str, stage_id: str, attempt_id: str, body: RevisionBody):
        return action(lambda: service.restore_attempt(project_id, stage_id, attempt_id, revision=body.revision))

    @router.get("/projects/{project_id}/download")
    def download(project_id: str):
        data = action(lambda: project_zip(service.get(project_id), service.assets, service.projects), project=False)
        return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{project_id}.zip"'})

    return router
