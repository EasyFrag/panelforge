"""HTTP boundary for visual analysis, independent of render and prompt routes."""
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
from threading import Event
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from starlette.background import BackgroundTask

from panelforge.application.media_analysis import MediaAnalysisConflict
from panelforge.application.media_transcription import TranscriptionCancelled
from panelforge.domain.media_analysis import AnalysisFrame, MediaAnalysisInput, MediaTranscript, SpeechInput, MAX_FRAMES, MAX_CLIP_SECONDS, MIN_TARGET_SECONDS, MAX_TARGET_SECONDS, ANALYSIS_VERSION, SPEECH_ANALYSIS_VERSION

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_UPLOAD_BYTES = 64 * 1024 * 1024
MAX_VIDEO_BYTES = 1024 * 1024 * 1024


class FrameBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=240)
    time_seconds: float | None = Field(default=None, ge=0, le=86_400, allow_inf_nan=False, strict=True)


class AnalysisBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frames: list[FrameBody] = Field(min_length=1, max_length=MAX_FRAMES)
    model_id: str = Field(min_length=1, max_length=300)
    instruction: str = Field(default="", max_length=12_000)
    source_kind: str = "images"
    source_name: str = Field(default="Images", min_length=1, max_length=240)
    duration_seconds: float = Field(default=8, ge=MIN_TARGET_SECONDS, le=MAX_TARGET_SECONDS, strict=True, allow_inf_nan=False)
    clip_start_seconds: float | None = Field(default=None, ge=0, strict=True, allow_inf_nan=False)
    clip_end_seconds: float | None = Field(default=None, ge=0, strict=True, allow_inf_nan=False)
    source_duration_seconds: float | None = Field(default=None, ge=.1, strict=True, allow_inf_nan=False)
    transcript: dict | None = None


class SpeechBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clip_start_seconds: float = Field(ge=0, strict=True, allow_inf_nan=False)
    clip_end_seconds: float = Field(ge=.1, strict=True, allow_inf_nan=False)
    language: str = "en"
    device: str = "cpu"


class IntentionBody(BaseModel):
    intention: str = Field(min_length=1, max_length=16_000)


def media_analysis_router(service):
    router = APIRouter(prefix="/api/media-analysis")
    pending_workers = set()

    def available():
        if service is None:
            raise HTTPException(503, "L’analyse de médias n’est pas configurée.")
        return service

    def invoke(operation, *args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except FileNotFoundError as error:
            raise HTTPException(404, "Analyse ou image introuvable.") from error
        except MediaAnalysisConflict as error:
            raise HTTPException(409, str(error)) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(422, str(error)) from error

    @router.get("/spec")
    def spec():
        current = available()
        models = current.gateway.list_models()
        speech = current.transcription.availability() if current.transcription else dict(available=False, message="La transcription locale n’est pas configurée.")
        return dict(version=SPEECH_ANALYSIS_VERSION, transcription={**speech, "video_bytes": MAX_VIDEO_BYTES}, llm_models=[dict(id=m.model_id, label=m.display_name or m.model_id, source=m.source) for m in models],
            limits=dict(frames=MAX_FRAMES, clip_seconds=MAX_CLIP_SECONDS, target_seconds=dict(min=MIN_TARGET_SECONDS,max=MAX_TARGET_SECONDS), image_bytes=MAX_IMAGE_BYTES, upload_bytes=MAX_UPLOAD_BYTES))

    @router.get("/analyses")
    def recent(limit: int = 3):
        return dict(analyses=invoke(available().store.list, limit))

    @router.get("/analyses/{analysis_id}")
    def get(analysis_id: str):
        return invoke(available().store.get, analysis_id)

    @router.post("/analyses", status_code=201)
    async def create(metadata: Annotated[str, Form(max_length=100_000)], files: Annotated[list[UploadFile], File()]):
        current = available()
        try:
            body = AnalysisBody.model_validate_json(metadata)
            if len(files) != len(body.frames):
                raise ValueError("Chaque image doit avoir sa vignette et son repère associé.")
            draft = body.model_dump(exclude={"frames"})
            if draft.get("transcript") is not None:
                draft["transcript"] = MediaTranscript.from_dict(draft["transcript"])
            # Validate times and bounds before decoding/storing any upload.
            MediaAnalysisInput(frames=tuple(AnalysisFrame(f"pending-{i}", **f.model_dump()) for i, f in enumerate(body.frames)), **draft)
            contents, total = [], 0
            for file in files:
                content = await file.read(MAX_IMAGE_BYTES + 1)
                total += len(content)
                if not content or len(content) > MAX_IMAGE_BYTES or total > MAX_UPLOAD_BYTES:
                    raise ValueError("Images trop volumineuses : 20 Mio par image, 64 Mio au total.")
                media_type, _ = await run_in_threadpool(current.images.prepare, content)
                contents.append((content, media_type))
            frames = []
            for frame, (content, media_type) in zip(body.frames, contents):
                asset = await run_in_threadpool(current.assets.create, content, media_type=media_type)
                frames.append(AnalysisFrame(asset.asset_id, frame.label, frame.time_seconds))
            return await run_in_threadpool(current.create, MediaAnalysisInput(frames=tuple(frames), **draft))
        except (TypeError, ValueError) as error:
            raise HTTPException(422, str(error)) from error
        finally:
            for file in files:
                await file.close()

    @router.post("/transcriptions/stream")
    async def transcribe(request: Request, metadata: Annotated[str, Form(max_length=2000)], file: Annotated[UploadFile, File()]):
        current = available().transcription
        temporary = None
        try:
            if current is None or not current.availability()["available"]:
                raise HTTPException(503, "Faster Whisper XXL ou son modèle est indisponible. L’analyse visuelle reste utilisable.")
            speech = SpeechInput(**SpeechBody.model_validate_json(metadata).model_dump())
            temporary = tempfile.TemporaryDirectory(prefix="panelforge-speech-upload-")
            source = Path(temporary.name) / "source.media"
            total = 0
            with source.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_VIDEO_BYTES:
                        raise HTTPException(413, "La vidéo dépasse 1 Gio. Exportez un extrait plus court avant de l’importer.")
                    await run_in_threadpool(output.write, chunk)
            if not total:
                raise ValueError("La vidéo est vide.")
            if await request.is_disconnected():
                raise HTTPException(499, "Transfert interrompu.")
        except BaseException as error:
            if temporary:
                temporary.cleanup()
            if isinstance(error, (TypeError, ValueError)):
                raise HTTPException(422, str(error)) from error
            raise
        finally:
            await file.close()

        cancelled, started = Event(), Event()

        async def events():
            loop, queue = asyncio.get_running_loop(), asyncio.Queue()

            def emit(value):
                if not cancelled.is_set():
                    loop.call_soon_threadsafe(queue.put_nowait, value)

            def run():
                try:
                    result = current.transcribe(source, speech, cancelled,
                        lambda phase, text: emit(dict(kind="status", phase=phase, text=text)))
                    outcome = dict(kind="completed", transcript=asdict(result))
                except TranscriptionCancelled:
                    outcome = dict(kind="error", message="Transcription annulée. Le brouillon est conservé.")
                except Exception as error:
                    outcome = dict(kind="error", message=str(error))
                finally:
                    try:
                        temporary.cleanup()
                    except OSError:
                        outcome = dict(kind="error", message="Le nettoyage du fichier temporaire a échoué. Réessayez après la fermeture du moteur local.")
                emit(outcome)

            started.set()
            worker = asyncio.create_task(asyncio.to_thread(run))
            # Keep a reference until completion, including after client disconnect.
            pending_workers.add(worker)
            worker.add_done_callback(pending_workers.discard)
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=1)
                    except asyncio.TimeoutError:
                        yield ": waiting\n\n"
                        continue
                    yield f"event: {event['kind']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                    if event["kind"] in ("completed", "error"):
                        break
            finally:
                cancelled.set()

        def close():
            cancelled.set()
            if not started.is_set():
                temporary.cleanup()

        return StreamingResponse(events(), media_type="text/event-stream", background=BackgroundTask(close),
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})

    @router.patch("/analyses/{analysis_id}/intention")
    def save(analysis_id: str, body: IntentionBody):
        return invoke(available().save_intention, analysis_id, body.intention)

    @router.post("/analyses/{analysis_id}/stream")
    def analyze(analysis_id: str, include_reasoning: bool = False):
        events = invoke(available().stream, analysis_id, include_reasoning=include_reasoning)
        def encoded():
            try:
                for event in events:
                    yield f"event: {event['kind']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            finally:
                if hasattr(events, "close"):
                    events.close()
        return StreamingResponse(encoded(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})

    return router
