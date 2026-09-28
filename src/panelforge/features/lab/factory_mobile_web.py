"""Dedicated mobile HTTP surface; no access to arbitrary Lab commands or files."""
from contextlib import asynccontextmanager
import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from panelforge.application.video_factory import FactoryConflict

STATIC = Path(__file__).with_name("static") / "factory-mobile"


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[str] = Field(default_factory=list, max_length=500)
    revisions: dict[str, int] | None = None
    active_runs: dict[str, str] | None = None


class PushKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")
    p256dh: str = Field(max_length=128)
    auth: str = Field(max_length=64)


class Subscription(BaseModel):
    model_config = ConfigDict(extra="ignore")
    endpoint: str = Field(max_length=4096)
    keys: PushKeys


class Thresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_gpu: float = Field(ge=40, le=110, allow_inf_nan=False)
    remote_gpu: float = Field(ge=40, le=110, allow_inf_nan=False)


class Subscribe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subscription: Subscription
    thresholds: Thresholds


def create_mobile_app(service):
    @asynccontextmanager
    async def lifespan(app):
        service.start()
        try:
            yield
        finally:
            await asyncio.to_thread(service.stop)

    app = FastAPI(title="Usine mobile", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def private_surface(request, call_next):
        host = request.url.hostname or ""
        if host not in {"localhost", "127.0.0.1", "::1"} and not host.endswith(".ts.net"):
            return JSONResponse({"detail": "Adresse mobile non autorisée."}, status_code=403)
        if request.method not in {"GET", "HEAD"}:
            origin = request.headers.get("origin", "")
            if (origin != str(request.base_url).rstrip("/") or
                    request.headers.get("x-panelforge-mobile") != "1" or
                    request.headers.get("sec-fetch-site") == "cross-site"):
                return JSONResponse({"detail": "Rechargez l’interface mobile pour effectuer cette action."}, status_code=403)
            try:
                length = int(request.headers.get("content-length") or 0)
            except ValueError:
                return JSONResponse({"detail": "Requête invalide."}, status_code=400)
            if length > 12000:
                return JSONResponse({"detail": "Requête trop volumineuse."}, status_code=413)
        response = await call_next(request)
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; worker-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"})
        return response

    def invoke(fn):
        try:
            return fn()
        except FactoryConflict as error:
            raise HTTPException(409, str(error)) from error
        except (KeyError, FileNotFoundError) as error:
            raise HTTPException(404, "Vidéo ou fichier indisponible.") from error
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from error
        except OSError as error:
            raise HTTPException(503, "Accès temporairement indisponible ; consulter le PC.") from error

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/app.js")
    def script():
        return FileResponse(STATIC / "app.js", media_type="text/javascript")

    @app.get("/app.css")
    def style():
        return FileResponse(STATIC / "app.css", media_type="text/css")

    @app.get("/sw.js")
    def worker():
        return FileResponse(STATIC / "sw.js", media_type="text/javascript")

    @app.get("/manifest.webmanifest")
    def manifest():
        return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")

    @app.get("/icon.svg")
    def icon():
        return FileResponse(STATIC / "icon.svg", media_type="image/svg+xml")

    @app.get("/icon-{size}.png")
    def png_icon(size: int):
        if size not in {192, 512}:
            raise HTTPException(404, "Icône inconnue.")
        return FileResponse(STATIC / f"icon-{size}.png", media_type="image/png")

    @app.get("/api/state")
    def state(limit: int = 24):
        if not 1 <= limit <= 200:
            raise HTTPException(422, "Limite de résultats invalide.")
        return invoke(lambda: service.snapshot(limit))

    @app.post("/api/commands/{action}")
    def command(action: str, body: Command):
        return invoke(lambda: service.command(action, body.ids, body.revisions, body.active_runs))

    @app.get("/api/items/{identity}/{kind}")
    def media(identity: str, kind: str):
        if kind not in {"video", "poster"}:
            raise HTTPException(404, "Média inconnu.")
        asset, path = invoke(lambda: service.asset(identity, kind))
        expected = "video/" if kind == "video" else "image/"
        if not asset.media_type.startswith(expected):
            raise HTTPException(415, "Format de média incompatible.")
        if kind == "poster":
            from panelforge.infrastructure.factory_mobile import mobile_thumbnail
            stat = path.stat()
            content = invoke(lambda: mobile_thumbnail(str(path), stat.st_mtime_ns, stat.st_size))
            return Response(content, media_type="image/jpeg")
        return FileResponse(path, media_type=asset.media_type)

    @app.get("/api/push")
    def push_config(id: str | None = None):
        return service.push_config(id)

    @app.post("/api/push")
    def subscribe(body: Subscribe, request: Request):
        if request.url.scheme != "https":
            raise HTTPException(422, "Ouvrez l’adresse HTTPS Tailscale pour activer les notifications.")
        return invoke(lambda: service.subscribe(body.subscription.model_dump(),
                      body.thresholds.model_dump(), "https://" + request.url.hostname))

    @app.delete("/api/push/{identity}")
    def unsubscribe(identity: str):
        invoke(lambda: service.unsubscribe(identity))
        return {"registered": False}

    return app
