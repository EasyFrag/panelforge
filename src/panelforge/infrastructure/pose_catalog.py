"""Explicit gallery index and personal pose references. No site JS executes."""
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from threading import RLock
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from PIL import Image

from .storage.local import _atomic_write, _json_bytes
from .pose_catalog_fr import display_entry

SOURCE_URL = "https://ai-pose-gallery.pages.dev/"
MAX_INDEX_BYTES = 8 * 1024**2
MAX_IMAGE_BYTES = 25 * 1024**2
ANGLES = {"正面": "Face", "上から": "Plongée", "下から": "Contre-plongée", "横": "Profil", "斜め": "Trois-quarts"}
FAMILIES = {"全身1人・標準系": "Corps entier", "全身1人・セクシー系": "Corps entier · expressif",
            "上半身1人": "Buste", "2人絡み": "Duo"}
CATEGORIES = {"立ち": "Debout", "座り": "Assis", "膝立ち": "À genoux", "しゃがみ": "Accroupi",
              "寝そべり": "Allongé", "ひねり": "Torsion", "前かがみ": "Penché en avant",
              "のけぞり・反り": "Cambrure", "特殊": "Autres", "かわいい系": "Expressif"}
_ID = re.compile(r"[A-Za-z0-9_-]{1,100}")


class _SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl)[:2] != urlsplit(SOURCE_URL)[:2]:
            raise ValueError("Le catalogue redirige vers un autre site.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, limit):
    if urlsplit(url)[:2] != urlsplit(SOURCE_URL)[:2]:
        raise ValueError("Source de catalogue inconnue.")
    request = Request(url, headers={"User-Agent": "PanelForge/1.0 personal pose reference cache"})
    with build_opener(_SameOriginRedirect()).open(request, timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Fichier de catalogue trop volumineux.")
    return data


def parse_catalog(content):
    if len(content) > MAX_INDEX_BYTES:
        raise ValueError("Catalogue trop volumineux.")
    text = content.decode("utf-8-sig")
    match = re.search(r"\bconst\s+D\s*=\s*", text)
    if not match:
        raise ValueError("Le format du catalogue de poses a changé.")
    values, end = json.JSONDecoder().raw_decode(text[match.end():])
    if not text[match.end() + end:].lstrip().startswith(";"):
        raise ValueError("Déclaration de catalogue invalide.")
    if not isinstance(values, list) or not 1 <= len(values) <= 10000:
        raise ValueError("Catalogue de poses vide ou trop volumineux.")
    entries, ids = [], set()
    for item in values:
        if not isinstance(item, dict):
            raise ValueError("Entrée de pose invalide.")
        identity = item.get("id", "")
        if not isinstance(identity, str) or not _ID.fullmatch(identity) or identity in ids:
            raise ValueError("Identifiant de pose invalide ou dupliqué.")
        ids.add(identity)
        # Paths come from the catalogue, and must match their explicit identity.
        if item.get("サムネ") != f"thumbs/{identity}.jpg" or item.get("原寸") != f"img/{identity}.png":
            raise ValueError("Chemin de pose incompatible avec le catalogue.")
        for key in ("系統", "ポーズ番号", "分類", "ポーズ名", "アングル"):
            if not isinstance(item.get(key), str) or not item[key].strip() or len(item[key]) > 240:
                raise ValueError("Métadonnées de pose invalides.")
        if item["アングル"] not in ANGLES:
            raise ValueError("Angle de pose inconnu.")
        entries.append(dict(id=identity, pose_id=identity.rsplit("_", 1)[0], number=item["ポーズ番号"],
            name=item["ポーズ名"], family=FAMILIES.get(item["系統"], item["系統"]),
            category=CATEGORIES.get(item["分類"], item["分類"]), angle=ANGLES[item["アングル"]],
            thumbnail=item["サムネ"], original=item["原寸"]))
    revision = hashlib.sha256(_json_bytes(entries)).hexdigest()
    return dict(schema_version=1, source_url=SOURCE_URL, revision=revision,
                installed_at=datetime.now(UTC).isoformat(), entries=entries)


class LocalPoseCatalog:
    def __init__(self, workspace, *, downloader=download):
        self.root = Path(workspace).resolve() / "catalogs" / "ai-pose-gallery"
        self.downloader = downloader
        self._lock = RLock()
        self._cached = None
        self._stamp = None
        self._personal_cached = None
        self._personal_stamp = None

    def _load(self):
        path = self.root / "catalog.json"
        stamp = path.stat().st_mtime_ns
        if self._cached is None or self._stamp != stamp:
            if path.is_symlink() or path.stat().st_size > MAX_INDEX_BYTES:
                raise ValueError("Catalogue local invalide.")
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("schema_version") != 1 or value.get("source_url") != SOURCE_URL:
                raise ValueError("Version du catalogue local inconnue.")
            if not re.fullmatch(r"[0-9a-f]{64}", value.get("revision", "")):
                raise ValueError("Révision du catalogue invalide.")
            self._cached, self._stamp = value, stamp
        return self._cached

    def _personal_index(self):
        path = self.root / "personal" / "catalog.json"
        if not path.exists():
            return None
        stamp = (path.stat().st_mtime_ns, path.stat().st_size)
        if self._personal_cached is None or self._personal_stamp != stamp:
            if path.is_symlink() or path.parent.is_symlink() or stamp[1] > MAX_INDEX_BYTES:
                raise ValueError("Catalogue de poses personnelles invalide.")
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("schema_version") != 1 or value.get("source") != "personal":
                raise ValueError("Version des poses personnelles inconnue.")
            entries = value.get("entries")
            if not isinstance(entries, list) or len(entries) > 1000:
                raise ValueError("Liste de poses personnelles invalide.")
            if value.get("revision") != hashlib.sha256(_json_bytes(entries)).hexdigest():
                raise ValueError("Révision des poses personnelles invalide.")
            ids = set()
            for item in entries:
                if not isinstance(item, dict):
                    raise ValueError("Entrée de pose personnelle invalide.")
                identity = item.get("id", "")
                if (not isinstance(identity, str) or not _ID.fullmatch(identity)
                        or not identity.startswith("personal_") or identity in ids):
                    raise ValueError("Identifiant de pose personnelle invalide.")
                ids.add(identity)
                for key in ("pose_id", "number", "name", "family", "category", "angle"):
                    if not isinstance(item.get(key), str) or not item[key].strip() or len(item[key]) > 240:
                        raise ValueError("Métadonnées de pose personnelle invalides.")
                if item["angle"] not in ANGLES.values() or item["family"] != "Mes poses":
                    raise ValueError("Classement de pose personnelle invalide.")
                if not _ID.fullmatch(item["pose_id"]) or not identity.startswith(item["pose_id"] + "_"):
                    raise ValueError("Groupe de pose personnelle invalide.")
                if item.get("original") != f"img/{identity}.png" or item.get("thumbnail") != item["original"]:
                    raise ValueError("Chemin de pose personnelle invalide.")
                if not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")):
                    raise ValueError("Empreinte de pose personnelle invalide.")
            self._personal_cached, self._personal_stamp = value, stamp
        return self._personal_cached

    @staticmethod
    def _personal_entry(item, index):
        return {**deepcopy(item), "catalog_revision": index["revision"],
                "source_kind": "personal", "source_url": None}

    def status(self):
        with self._lock:
            try:
                entries = self.entries()
                revisions = sorted({x["catalog_revision"] for x in entries})
                revision = revisions[0] if len(revisions) == 1 else hashlib.sha256(_json_bytes(revisions)).hexdigest()
                return dict(state="ready", source_url=SOURCE_URL, revision=revision,
                    pose_count=len({x["pose_id"] for x in entries}), image_count=len(entries),
                    personal_pose_count=len({x["pose_id"] for x in entries if x.get("source_kind") == "personal"}),
                    categories=sorted({x["category"] for x in entries}), families=sorted({x["family"] for x in entries}),
                    angles=list(ANGLES.values()))
            except FileNotFoundError:
                return dict(state="unavailable", source_url=SOURCE_URL, pose_count=0, image_count=0)
            except (ValueError, KeyError, TypeError, OSError) as error:
                return dict(state="failed", source_url=SOURCE_URL, error=str(error), pose_count=0, image_count=0)

    def install(self, *, force=False):
        # Network I/O only on explicit installation, browsing or selection; never at startup.
        with self._lock:
            if not force and (self.root / "catalog.json").is_file() and self.status()["state"] == "ready":
                return self.status()
        value = parse_catalog(self.downloader(SOURCE_URL, MAX_INDEX_BYTES))
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            _atomic_write(self.root / "catalog.json", _json_bytes(value))
            self._cached, self._stamp = None, None
            return self.status()

    def entries(self):
        with self._lock:
            try:
                index = self._load()
            except FileNotFoundError:
                index = None
            personal = self._personal_index()
            if index is None and personal is None:
                raise FileNotFoundError("Aucun catalogue de poses installé.")
            entries = [{**display_entry(deepcopy(x)), "catalog_revision": index["revision"]}
                       for x in index["entries"]] if index else []
            return entries + [self._personal_entry(x, personal) for x in personal["entries"]] if personal else entries

    def get(self, entry_id):
        if not isinstance(entry_id, str) or not _ID.fullmatch(entry_id):
            raise ValueError("Identifiant de pose invalide.")
        with self._lock:
            if entry_id.startswith("personal_"):
                personal = self._personal_index()
                item = next((x for x in personal["entries"] if x["id"] == entry_id), None) if personal else None
                return self._personal_entry(item, personal) if item else self._missing(entry_id)
            index = self._load()
            item = next((x for x in index["entries"] if x["id"] == entry_id), None)
            if item is None:
                return self._missing(entry_id)
            return {**display_entry(deepcopy(item)), "catalog_revision": index["revision"]}

    @staticmethod
    def _missing(entry_id):
        raise FileNotFoundError("Pose absente du catalogue : " + entry_id)

    def image_path(self, entry_id, *, thumbnail=False):
        item = self.get(entry_id)
        if item.get("source_kind") == "personal":
            # Use the supplied PNG unchanged for both the preview and the reference.
            path = self.root / "personal" / item["original"]
            if path.is_symlink() or not path.resolve().is_relative_to((self.root / "personal").resolve()):
                raise ValueError("Chemin de pose personnelle invalide.")
            if path.stat().st_size > MAX_IMAGE_BYTES:
                raise ValueError("Pose personnelle trop volumineuse.")
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError("L’image de la pose personnelle a été modifiée.")
            with Image.open(BytesIO(data)) as image:
                if image.format != "PNG" or image.width * image.height > 40_000_000:
                    raise ValueError("Format ou dimensions de pose personnelle invalides.")
                image.verify()
            return path
        kind, suffix = ("thumbs", ".jpg") if thumbnail else ("img", ".png")
        relative = item["thumbnail" if thumbnail else "original"]
        if relative != f"{kind}/{entry_id}{suffix}":
            raise ValueError("Chemin de pose invalide.")
        path = self.root / item["catalog_revision"] / kind / (entry_id + suffix)
        if path.resolve().is_relative_to(self.root.resolve()) is False or path.is_symlink():
            raise ValueError("Chemin de cache invalide.")
        with self._lock:
            if path.is_file():
                return path
        data = self.downloader(urljoin(SOURCE_URL, relative), 2 * 1024**2 if thumbnail else MAX_IMAGE_BYTES)
        if not (data.startswith(b"\xff\xd8\xff") if thumbnail else data.startswith(b"\x89PNG\r\n\x1a\n")):
            raise ValueError("Le site n’a pas renvoyé l’image attendue.")
        with Image.open(BytesIO(data)) as image:
            if image.format != ("JPEG" if thumbnail else "PNG") or image.width * image.height > 40_000_000:
                raise ValueError("Format ou dimensions de pose invalides.")
            image.verify()
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(path, data)
        return path

    def reference(self, entry_id):
        with self._lock:
            item = self.get(entry_id)
            content = self.image_path(entry_id).read_bytes()
            return {**item, "source_url": None if item.get("source_kind") == "personal" else urljoin(SOURCE_URL, item["original"]),
                    "sha256": hashlib.sha256(content).hexdigest()}, content
