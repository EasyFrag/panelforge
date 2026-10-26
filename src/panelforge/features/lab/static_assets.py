"""A coherent, content-addressed snapshot of the Lab's HTML, JS and CSS.

The snapshot belongs to one app instance. Deploying assets requires restarting
that instance; a delayed tab cannot receive new bytes under an old version URL.
No scan of the workspace or runtime media is involved.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

from starlette.responses import HTMLResponse, Response
from starlette.staticfiles import StaticFiles


_REFERENCE = re.compile(r'(?P<prefix>\b(?:src|href)=["\'])(?P<url>/static/[^"\']+)(?P<suffix>["\'])')


class LabAssets(StaticFiles):
    """Cache only known, verified JS/CSS versions; keep other assets revalidatable."""

    def __init__(self, directory: Path):
        super().__init__(directory=directory)
        root = directory.resolve()
        self.assets: dict[str, tuple[bytes, str, str]] = {}
        source = (root / "index.html").read_text(encoding="utf-8")

        def version(match: re.Match) -> str:
            url = urlsplit(match["url"])
            name = url.path.removeprefix("/static/")
            path = (root / name).resolve()
            if path.suffix not in (".js", ".css") or not path.is_relative_to(root):
                return match[0]
            if name not in self.assets:
                data = path.read_bytes()
                media_type = "text/javascript" if path.suffix == ".js" else "text/css"
                self.assets[name] = (data, sha256(data).hexdigest(), media_type)
            digest = self.assets[name][1]
            return f'{match["prefix"]}/static/{name}?v={digest}{match["suffix"]}'

        self.html = _REFERENCE.sub(version, source)

    def index(self) -> HTMLResponse:
        return HTMLResponse(self.html, headers={"Cache-Control": "no-store"})

    async def get_response(self, path: str, scope) -> Response:
        version = parse_qs(scope.get("query_string", b"").decode("ascii", errors="replace")).get("v", [])
        asset = self.assets.get(path)
        if asset is not None and scope["method"] in ("GET", "HEAD"):
            data, digest, media_type = asset
            if version and version != [digest]:
                # Old manual versions and tabs from another app revision must
                # reload HTML; never label different bytes with the old digest.
                return Response("Version du Lab expirée. Rechargez la page.", status_code=409,
                                headers={"Cache-Control": "no-store"})
            headers = {"Cache-Control": "private, max-age=31536000, immutable" if version else "no-cache",
                       "ETag": f'"{digest}"'}
            request_headers = dict(scope.get("headers", []))
            etags = request_headers.get(b"if-none-match", b"").decode("latin1").split(",")
            if any(tag.strip().removeprefix("W/") in (headers["ETag"], "*") for tag in etags):
                return Response(status_code=304, headers=headers)
            headers["Content-Length"] = str(len(data))
            return Response(data if scope["method"] != "HEAD" else b"", media_type=media_type, headers=headers)
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response
