"""Media http for the PanelForge Lab HTTP interface."""

from __future__ import annotations
from asyncio import Semaphore
from .http_support import http_errors
from fastapi import Request, UploadFile, status, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from panelforge.application import ChangeViewRunner
from fastapi import APIRouter
from panelforge.infrastructure.image_thumbnails import CachedImageThumbnails


MAX_IMAGE_BYTES = 25 * 1024 * 1024


MAX_SOCIAL_VIDEO_BYTES = 250 * 1024 * 1024


async def _close_uploads(uploads: list[UploadFile]) -> None:
    for upload in uploads:
        await upload.close()


def _parse_byte_range(value: str | None, content_length: int) -> tuple[int, int] | None:
    """Parse one HTTP bytes range, rejecting malformed or unsatisfiable ranges."""
    if value is None:
        return None
    if content_length < 0:
        raise ValueError("content_length must not be negative")
    unit, separator, raw_range = value.partition("=")
    if separator != "=" or unit.strip().lower() != "bytes":
        raise ValueError("unsupported range unit")
    raw_range = raw_range.strip()
    if not raw_range or "," in raw_range:
        raise ValueError("exactly one byte range is supported")
    raw_start, dash, raw_end = raw_range.partition("-")
    if dash != "-":
        raise ValueError("invalid byte range")
    raw_start = raw_start.strip()
    raw_end = raw_end.strip()

    if raw_start:
        if not raw_start.isdecimal() or (raw_end and not raw_end.isdecimal()):
            raise ValueError("invalid byte range")
        start = int(raw_start)
        if start >= content_length:
            raise ValueError("unsatisfiable byte range")
        end = content_length - 1 if not raw_end else int(raw_end)
        if end < start:
            raise ValueError("invalid byte range")
        return start, min(end, content_length - 1)

    if not raw_end or not raw_end.isdecimal():
        raise ValueError("invalid suffix byte range")
    suffix_length = int(raw_end)
    if suffix_length <= 0 or content_length == 0:
        raise ValueError("unsatisfiable suffix byte range")
    return max(content_length - suffix_length, 0), content_length - 1


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


def detect_video_media_type(content: bytes) -> str:
    if len(content) >= 12 and content[4:8] == b"ftyp":
        return "video/mp4"
    if content.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"
    raise ValueError("source must be an MP4 or WebM video")


def media_router(*, runner: ChangeViewRunner) -> APIRouter:
    router = APIRouter()
    thumbnails = CachedImageThumbnails(lambda identity: runner.assets.read_verified(identity))
    thumbnail_slots = Semaphore(2)

    @router.get("/api/assets/{asset_id}/thumbnail")
    async def asset_thumbnail(asset_id: str, request: Request, v: int = Query(1, ge=1, le=1)) -> Response:
        # Wait asynchronously before borrowing a worker thread: many visible
        # history images must not consume all threads needed by launch commands.
        with http_errors("asset not found", invalid=(ValueError, OSError)):
            async with thumbnail_slots:
                thumbnail = await run_in_threadpool(thumbnails.get, asset_id)
        headers = {"Cache-Control": "private, max-age=31536000, immutable", "ETag": thumbnail.etag}
        tags = request.headers.get("if-none-match", "").split(",")
        if any(tag.strip().removeprefix("W/") in {"*", thumbnail.etag} for tag in tags):
            return Response(status_code=304, headers=headers)
        return Response(thumbnail.content, media_type="image/png", headers=headers)

    @router.get("/api/assets/{asset_id}/content")
    def asset_content(asset_id: str, request: Request) -> Response:
        with http_errors('asset not found', invalid=(ValueError,)):
            asset, content = runner.assets.read_verified(asset_id)
        headers = {
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, max-age=31536000, immutable",
        }
        try:
            byte_range = _parse_byte_range(
                request.headers.get("range"),
                len(content),
            )
        except ValueError:
            return Response(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={
                    **headers,
                    "Content-Range": f"bytes */{len(content)}",
                },
            )
        if byte_range is not None:
            start, end = byte_range
            return Response(
                content=content[start : end + 1],
                status_code=status.HTTP_206_PARTIAL_CONTENT,
                media_type=asset.media_type,
                headers={
                    **headers,
                    "Content-Range": f"bytes {start}-{end}/{len(content)}",
                },
            )
        return Response(
            content=content,
            media_type=asset.media_type,
            headers=headers,
        )

    return router
