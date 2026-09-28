"""Local, version-pinned catalog adapter for modular KREA2 art directions."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from threading import RLock
from urllib.request import Request, urlopen
from uuid import uuid4
from zipfile import ZipFile, ZipInfo

from panelforge.domain.krea2_art_direction import Krea2ArtDirection


CLIO_PROVIDER_ID = "clio"
LOCAL_PROVIDER_ID = "panelforge-local"
CLIO_REPOSITORY = "https://github.com/lumenastrum/clio-style-preview"
CLIO_REVISION = "82b8b79a2e52d3a53d52ba11c99c100c991dc15f"
CLIO_ARCHIVE_URL = f"https://codeload.github.com/lumenastrum/clio-style-preview/zip/{CLIO_REVISION}"
_MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
_MAX_CATALOG_BYTES = 2 * 1024 * 1024
_MAX_THUMB_BYTES = 2 * 1024 * 1024
_MAX_THUMB_TOTAL = 64 * 1024 * 1024


class LocalKrea2StyleCatalog:
    """Downloads only prompt metadata, thumbnails and attribution files."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        downloader: Callable[[str, Path], None] | None = None,
        revision: str = CLIO_REVISION,
        archive_url: str | None = None,
    ) -> None:
        workspace = Path(workspace_root).resolve()
        self._catalogs_root = workspace / "catalogs"
        self._root = self._catalogs_root / "clio"
        self._local_root = self._catalogs_root / LOCAL_PROVIDER_ID
        self._revision = revision
        self._archive_url = archive_url or (
            CLIO_ARCHIVE_URL if revision == CLIO_REVISION
            else f"https://codeload.github.com/lumenastrum/clio-style-preview/zip/{revision}"
        )
        self._downloader = downloader or _download
        self._lock = RLock()

    def status(self) -> dict[str, object]:
        with self._lock:
            if not self._root.is_dir():
                return self._status("unavailable", error=None)
            try:
                styles = self._load()
                source = json.loads((self._root / "SOURCE.json").read_text(encoding="utf-8"))
                return self._status(
                    "ready",
                    style_count=len(styles),
                    local_style_count=sum(
                        style.provider_id == LOCAL_PROVIDER_ID for style in styles
                    ),
                    categories=sorted({style.category for style in styles}),
                    revision=str(source["revision"]),
                    error=None,
                )
            except Exception as error:
                return self._status("failed", error=str(error))

    def install(self, *, force: bool = False) -> dict[str, object]:
        with self._lock:
            current = self.status()
            if (
                not force
                and current["state"] == "ready"
                and current.get("revision") == self._revision
            ):
                return current
            self._catalogs_root.mkdir(parents=True, exist_ok=True)
            temporary_root = Path(tempfile.mkdtemp(prefix=".clio-install-", dir=self._catalogs_root))
            archive = temporary_root / "source.zip"
            staged = temporary_root / "catalog"
            try:
                self._downloader(self._archive_url, archive)
                if not archive.is_file() or archive.stat().st_size > _MAX_ARCHIVE_BYTES:
                    raise ValueError("archive Clio absent ou trop volumineux")
                staged.mkdir()
                self._extract_catalog(archive, staged)
                self._replace(staged)
            finally:
                shutil.rmtree(temporary_root, ignore_errors=True)
            return self.status()

    def list_styles(
        self,
        *,
        query: str = "",
        category: str | None = None,
    ) -> tuple[Krea2ArtDirection, ...]:
        with self._lock:
            values = self._load()
        terms = tuple(term for term in query.casefold().split() if term)
        category_key = category.casefold() if isinstance(category, str) and category.strip() else None
        selected = []
        for value in values:
            if category_key and value.category.casefold() != category_key:
                continue
            haystack = f"{value.name} {value.category} {value.prompt}".casefold()
            if terms and not all(term in haystack for term in terms):
                continue
            selected.append(value)
        return tuple(sorted(selected, key=lambda item: (item.category.casefold(), item.name.casefold())))

    def get(self, style_id: str) -> Krea2ArtDirection:
        with self._lock:
            value = next((item for item in self._load() if item.style_id == style_id), None)
        if value is None:
            raise KeyError(style_id)
        return value

    def thumbnail_path(self, style_id: str) -> Path:
        style = self.get(style_id)
        root = self._root if style.provider_id == CLIO_PROVIDER_ID else self._local_root
        index = self._index() if style.provider_id == CLIO_PROVIDER_ID else self._local_index()
        item = next(value for value in index["styles"] if value["style_id"] == style_id)
        candidate = (root / item["thumbnail"]).resolve()
        candidate.relative_to(root.resolve())
        if (
            candidate.suffix.casefold() not in {".jpg", ".jpeg", ".png", ".webp"}
            or not candidate.is_file()
            or candidate.is_symlink()
        ):
            raise FileNotFoundError(style_id)
        return candidate

    def _load(self) -> tuple[Krea2ArtDirection, ...]:
        values = (
            *self._directions(self._index(), CLIO_PROVIDER_ID),
            *(
                self._directions(self._local_index(), LOCAL_PROVIDER_ID)
                if (self._local_root / "catalog.json").is_file()
                else ()
            ),
        )
        if not values:
            raise ValueError("catalogue de directions artistiques vide")
        if len({value.style_id for value in values}) != len(values):
            raise ValueError("identifiants de directions artistiques dupliqués")
        return tuple(values)

    @staticmethod
    def _directions(
        index: dict[str, object],
        provider_id: str,
    ) -> tuple[Krea2ArtDirection, ...]:
        revision = str(index["revision"])
        return tuple(
            Krea2ArtDirection(
                provider_id=provider_id,
                style_id=item["style_id"],
                name=item["name"],
                category=item["category"],
                prompt=item["prompt"],
                catalog_revision=revision,
            )
            for item in index["styles"]
        )

    def _index(self) -> dict[str, object]:
        return self._read_index(self._root, CLIO_PROVIDER_ID, "Clio")

    def _local_index(self) -> dict[str, object]:
        return self._read_index(self._local_root, LOCAL_PROVIDER_ID, "local")

    @staticmethod
    def _read_index(root: Path, provider_id: str, label: str) -> dict[str, object]:
        path = root / "catalog.json"
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError("catalog.json")
        value = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != 1
            or value.get("provider_id") != provider_id
            or not isinstance(value.get("revision"), str)
            or not isinstance(value.get("styles"), list)
        ):
            raise ValueError(f"index {label} invalide")
        for item in value["styles"]:
            if (
                not isinstance(item, dict)
                or not all(
                    isinstance(item.get(field), str) and item[field].strip()
                    for field in ("style_id", "name", "category", "prompt", "thumbnail")
                )
            ):
                raise ValueError(f"entrée de style {label} invalide")
        return value

    def _extract_catalog(self, archive_path: Path, staged: Path) -> None:
        with ZipFile(archive_path) as bundle:
            styles_info = _member(bundle, "styles.json", maximum=_MAX_CATALOG_BYTES)
            manifest_info = _member(bundle, "gallery/manifest.json", maximum=_MAX_CATALOG_BYTES)
            license_info = _member(bundle, "LICENSE", maximum=128 * 1024)
            styles = json.loads(bundle.read(styles_info).decode("utf-8"))
            manifest = json.loads(bundle.read(manifest_info).decode("utf-8"))
            if not isinstance(styles, list) or not styles:
                raise ValueError("styles.json Clio invalide")
            images = manifest.get("sections", {}).get("krea2", {}).get("images", [])
            if not isinstance(images, list):
                raise ValueError("manifest Clio invalide")
            image_by_style = {
                item.get("style"): item.get("thumb") or item.get("file")
                for item in images
                if isinstance(item, dict)
            }
            thumb_root = staged / "thumbs"
            thumb_root.mkdir()
            compiled: list[dict[str, str]] = []
            total = 0
            for item in styles:
                if not isinstance(item, dict):
                    raise ValueError("entrée de style Clio invalide")
                name, prompt, category = item.get("name"), item.get("prompt"), item.get("section")
                if not all(isinstance(value, str) and value.strip() for value in (name, prompt, category)):
                    raise ValueError("métadonnées de style Clio incomplètes")
                Krea2ArtDirection(
                    provider_id=CLIO_PROVIDER_ID,
                    style_id=name,
                    name=name,
                    category=category,
                    prompt=prompt,
                    catalog_revision=self._revision,
                )
                relative = image_by_style.get(name)
                if not isinstance(relative, str):
                    raise ValueError(f"miniature Clio absente : {name}")
                relative_path = PurePosixPath(relative)
                if relative_path.is_absolute() or ".." in relative_path.parts:
                    raise ValueError("chemin de miniature Clio invalide")
                info = _member(bundle, f"gallery/{relative_path.as_posix()}", maximum=_MAX_THUMB_BYTES)
                total += info.file_size
                if total > _MAX_THUMB_TOTAL:
                    raise ValueError("miniatures Clio trop volumineuses")
                suffix = Path(relative_path.name).suffix.casefold()
                if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
                    raise ValueError("format de miniature Clio invalide")
                filename = hashlib.sha256(name.encode("utf-8")).hexdigest() + suffix
                with bundle.open(info) as source, (thumb_root / filename).open("wb") as target:
                    shutil.copyfileobj(source, target)
                compiled.append({
                    "style_id": name,
                    "name": name,
                    "category": category,
                    "prompt": prompt,
                    "thumbnail": f"thumbs/{filename}",
                })
            if len({item["style_id"] for item in compiled}) != len(compiled):
                raise ValueError("identifiants de styles Clio dupliqués")
            (staged / "styles.json").write_bytes(bundle.read(styles_info))
            (staged / "manifest.json").write_bytes(bundle.read(manifest_info))
            (staged / "LICENSE").write_bytes(bundle.read(license_info))
        source = {
            "provider_id": CLIO_PROVIDER_ID,
            "repository": CLIO_REPOSITORY,
            "revision": self._revision,
            "archive_url": self._archive_url,
            "installed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "style_count": len(compiled),
            "style_text_credit": "Community prompt library credited by Clio to u/Dear-Spend-2865",
            "license_note": "MIT applies to repository code; style descriptions are community-shared prompt text. See the upstream repository and bundled LICENSE.",
        }
        _write_json(staged / "catalog.json", {
            "schema_version": 1,
            "provider_id": CLIO_PROVIDER_ID,
            "revision": self._revision,
            "styles": compiled,
        })
        _write_json(staged / "SOURCE.json", source)

    def _replace(self, staged: Path) -> None:
        root = self._root.resolve()
        root.parent.mkdir(parents=True, exist_ok=True)
        root.relative_to(self._catalogs_root.resolve())
        backup = self._catalogs_root / f".clio-backup-{uuid4().hex}"
        if self._root.exists():
            os.replace(self._root, backup)
        try:
            os.replace(staged, self._root)
        except Exception:
            if backup.exists() and not self._root.exists():
                os.replace(backup, self._root)
            raise
        finally:
            if backup.exists():
                shutil.rmtree(backup)

    def _status(
        self,
        state: str,
        *,
        style_count: int = 0,
        local_style_count: int = 0,
        categories: list[str] | None = None,
        revision: str | None = None,
        error: str | None,
    ) -> dict[str, object]:
        return {
            "provider_id": CLIO_PROVIDER_ID,
            "state": state,
            "style_count": style_count,
            "local_style_count": local_style_count,
            "categories": categories or [],
            "revision": revision,
            "target_revision": self._revision,
            "repository": CLIO_REPOSITORY,
            "error": error,
        }


def _member(bundle: ZipFile, suffix: str, *, maximum: int) -> ZipInfo:
    normalized = suffix.replace("\\", "/")
    matches = [
        item for item in bundle.infolist()
        if not item.is_dir() and item.filename.replace("\\", "/").endswith("/" + normalized)
    ]
    if len(matches) != 1:
        raise ValueError(f"fichier Clio introuvable ou ambigu : {suffix}")
    info = matches[0]
    if info.file_size < 1 or info.file_size > maximum:
        raise ValueError(f"fichier Clio trop volumineux : {suffix}")
    return info


def _download(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": "PanelForge-Clio-Catalog/1.0"})
    total = 0
    with urlopen(request, timeout=90) as response, destination.open("wb") as target:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_ARCHIVE_BYTES:
                raise ValueError("archive Clio trop volumineux")
            target.write(chunk)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
