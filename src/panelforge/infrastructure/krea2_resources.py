"""Read-only KREA2 model/LoRA inventory with optional CivitAI metadata.

Filesystem discovery is deliberately restricted to the two configured roots.
Remote lookups are explicit and cached; opening the Lab never hashes multi-GB
checkpoints or requires CivitAI to be reachable.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from threading import RLock
from typing import Any, Protocol
import urllib.parse
import urllib.request


_MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth"}
_BF16_THRESHOLD_BYTES = 16 * 1024**3
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")


class Krea2ResourceKind(StrEnum):
    MODEL = "model"
    LORA = "lora"


class Krea2ResourceSafety(StrEnum):
    SFW = "sfw"
    NSFW = "nsfw"
    UNCLASSIFIED = "unclassified"


class Krea2ResourcePrecision(StrEnum):
    BF16 = "bf16"
    INT8 = "int8"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Krea2Resource:
    resource_id: str
    kind: Krea2ResourceKind
    comfy_name: str
    filename: str
    relative_path: str
    size_bytes: int
    favorite: bool
    category: str
    safety: Krea2ResourceSafety
    precision: Krea2ResourcePrecision | None = None
    precision_source: str | None = None
    source_url: str | None = None
    sha256: str | None = None
    current_version_id: int | None = None
    latest_version_id: int | None = None
    latest_version_name: str | None = None
    update_available: bool | None = None
    remote_checked_at: str | None = None
    warning: str | None = None


@dataclass(frozen=True, slots=True)
class Krea2ResourcePreference:
    favorite: bool = False
    safety: Krea2ResourceSafety | None = None
    precision: Krea2ResourcePrecision | None = None


class Krea2ComfyInventory(Protocol):
    def list_unet_models(self) -> tuple[str, ...]: ...
    def list_lora_models(self) -> tuple[str, ...]: ...


class CivitaiMetadataClient:
    """Small public CivitAI API reader used only on explicit refresh."""

    def __init__(
        self,
        *,
        base_url: str = "https://civitai.com/api/v1",
        timeout: float = 15.0,
        opener: Callable[[urllib.request.Request, float], bytes] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        if not self.base_url:
            raise ValueError("base_url must not be empty")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.timeout = float(timeout)
        self._opener = opener or self._open

    def inspect(
        self,
        *,
        filename: str,
        sha256: str | None,
        known_version_id: int | None = None,
    ) -> dict[str, object]:
        version = (
            self._get(f"/model-versions/by-hash/{sha256}")
            if sha256 is not None
            else self._find_exact_file(filename)
        )
        if version is None:
            return {
                "source_url": _civitai_search_url(filename),
                "warning": "Source CivitAI exacte non identifiée.",
            }
        version_id = _positive_int(version.get("id")) or known_version_id
        model_id = _positive_int(version.get("modelId"))
        if model_id is None:
            nested = version.get("model")
            if isinstance(nested, Mapping):
                model_id = _positive_int(nested.get("id"))
        latest_id = version_id
        latest_name = _optional_text(version.get("name"))
        if model_id is not None:
            model = self._get(f"/models/{model_id}")
            versions = model.get("modelVersions") if isinstance(model, Mapping) else None
            if isinstance(versions, list):
                latest = next(
                    (
                        candidate
                        for candidate in versions
                        if isinstance(candidate, Mapping)
                        and str(candidate.get("status", "Published")).casefold()
                        not in {"deleted", "archived"}
                    ),
                    None,
                )
                if latest is not None:
                    latest_id = _positive_int(latest.get("id")) or latest_id
                    latest_name = _optional_text(latest.get("name")) or latest_name
        source_url = (
            f"https://civitai.com/models/{model_id}?modelVersionId={version_id}"
            if model_id is not None and version_id is not None
            else _civitai_search_url(filename)
        )
        return {
            "source_url": source_url,
            "current_version_id": version_id,
            "latest_version_id": latest_id,
            "latest_version_name": latest_name,
            "update_available": (
                latest_id != version_id
                if latest_id is not None and version_id is not None
                else None
            ),
            "warning": None,
        }

    def _find_exact_file(self, filename: str) -> Mapping[str, Any] | None:
        payload = self._get(
            "/models?"
            + urllib.parse.urlencode({"query": Path(filename).stem, "limit": 20})
        )
        items = payload.get("items") if isinstance(payload, Mapping) else None
        if not isinstance(items, list):
            return None
        target = filename.casefold()
        for model in items:
            if not isinstance(model, Mapping):
                continue
            versions = model.get("modelVersions")
            if not isinstance(versions, list):
                continue
            for version in versions:
                if not isinstance(version, Mapping):
                    continue
                files = version.get("files")
                if not isinstance(files, list):
                    continue
                if any(
                    isinstance(file, Mapping)
                    and str(file.get("name", "")).casefold() == target
                    for file in files
                ):
                    enriched = dict(version)
                    enriched.setdefault("modelId", model.get("id"))
                    return enriched
        return None

    def _get(self, path: str) -> Mapping[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            headers={"Accept": "application/json", "User-Agent": "PanelForge/0.1"},
            method="GET",
        )
        payload = json.loads(self._opener(request, self.timeout))
        if not isinstance(payload, Mapping):
            raise ValueError("CivitAI returned a non-object response")
        return payload

    @staticmethod
    def _open(request: urllib.request.Request, timeout: float) -> bytes:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()


class LocalKrea2ResourceCatalog:
    """Discover KREA2 resources below explicit roots and persist UI metadata."""

    def __init__(
        self,
        *,
        models_root: str | Path,
        loras_root: str | Path,
        workspace_root: str | Path,
        comfy: Krea2ComfyInventory | None = None,
        civitai: CivitaiMetadataClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.models_root = Path(models_root)
        self.loras_root = Path(loras_root)
        self._state_path = Path(workspace_root).resolve() / "krea2_resources.json"
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self.comfy = comfy
        self.civitai = civitai or CivitaiMetadataClient()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = RLock()
        self._inventory_warnings: dict[Krea2ResourceKind, tuple[str, ...]] = {}

    def list_models(self) -> tuple[Krea2Resource, ...]:
        return self._scan(Krea2ResourceKind.MODEL)

    def list_loras(self) -> tuple[Krea2Resource, ...]:
        return self._scan(Krea2ResourceKind.LORA)

    def inventory_warnings(self) -> tuple[str, ...]:
        return tuple(
            warning
            for kind in (Krea2ResourceKind.MODEL, Krea2ResourceKind.LORA)
            for warning in self._inventory_warnings.get(kind, ())
        )

    def get(self, resource_id: str) -> Krea2Resource:
        for resource in self.list_models():
            if resource.resource_id == resource_id:
                return resource
        for resource in self.list_loras():
            if resource.resource_id == resource_id:
                return resource
        raise KeyError(resource_id)

    def set_preference(
        self,
        resource_id: str,
        *,
        favorite: bool | None = None,
        safety: Krea2ResourceSafety | None = None,
        precision: Krea2ResourcePrecision | None = None,
        reset_precision: bool = False,
    ) -> Krea2Resource:
        if favorite is not None and not isinstance(favorite, bool):
            raise TypeError("favorite must be a boolean")
        if safety is not None and not isinstance(safety, Krea2ResourceSafety):
            raise TypeError("safety must be a Krea2ResourceSafety")
        if precision is not None and not isinstance(precision, Krea2ResourcePrecision):
            raise TypeError("precision must be a Krea2ResourcePrecision")
        if precision is Krea2ResourcePrecision.UNKNOWN:
            raise ValueError("unknown cannot be used as a manual precision")
        with self._lock:
            resource = self.get(resource_id)
            if (
                precision is not None or reset_precision
            ) and resource.kind is not Krea2ResourceKind.MODEL:
                raise ValueError("precision can only classify a checkpoint")
            state = self._load_state()
            preferences = state.setdefault("preferences", {})
            current = preferences.get(resource_id, {})
            if not isinstance(current, dict):
                current = {}
            if favorite is not None:
                current["favorite"] = favorite
            if safety is not None:
                current["safety"] = safety.value
            if reset_precision:
                current.pop("precision", None)
            elif precision is not None:
                current["precision"] = precision.value
            preferences[resource_id] = current
            self._save_state(state)
            return self._reload_resource(resource, state)

    def refresh_remote(self, resource_id: str) -> Krea2Resource:
        with self._lock:
            resource = self.get(resource_id)
            checked_at = self._clock().astimezone(UTC).isoformat().replace("+00:00", "Z")
            try:
                remote = self.civitai.inspect(
                    filename=resource.filename,
                    sha256=resource.sha256,
                    known_version_id=resource.current_version_id,
                )
            except Exception as error:
                remote = {
                    "warning": f"CivitAI indisponible : {type(error).__name__}",
                    "source_url": resource.source_url,
                }
            state = self._load_state()
            remote_state = state.setdefault("remote", {})
            remote_state[resource_id] = {**remote, "checked_at": checked_at}
            self._save_state(state)
            return self._reload_resource(resource, state)

    def _reload_resource(
        self,
        resource: Krea2Resource,
        state: Mapping[str, Any],
    ) -> Krea2Resource:
        root = self.models_root if resource.kind is Krea2ResourceKind.MODEL else self.loras_root
        path = root / resource.relative_path
        if path.is_file() and not path.is_symlink():
            return self._resource(path, root=root, kind=resource.kind, state=state)
        return self._remote_resource(resource.comfy_name, kind=resource.kind, state=state)

    def _scan(self, kind: Krea2ResourceKind) -> tuple[Krea2Resource, ...]:
        root = self.models_root if kind is Krea2ResourceKind.MODEL else self.loras_root
        with self._lock:
            state = self._load_state()
            warnings: list[str] = []
            local_root_available = root.is_dir()
            if local_root_available:
                result = [
                    self._resource(path, root=root, kind=kind, state=state)
                    for path in root.rglob("*")
                    if path.is_file()
                    and not path.is_symlink()
                    and path.suffix.casefold() in _MODEL_EXTENSIONS
                ]
            else:
                result = []
            if self.comfy is not None:
                try:
                    remote_names = (
                        self.comfy.list_unet_models()
                        if kind is Krea2ResourceKind.MODEL
                        else self.comfy.list_lora_models()
                    )
                except Exception as error:
                    remote_names = ()
                    warnings.append(
                        "Inventaire ComfyUI des "
                        + ("checkpoints" if kind is Krea2ResourceKind.MODEL else "LoRA")
                        + f" indisponible : {type(error).__name__}."
                    )
                known = {_normalized_name(value.comfy_name) for value in result}
                for raw_name in remote_names:
                    comfy_name = _krea2_comfy_name(raw_name, kind)
                    if comfy_name is None or _normalized_name(comfy_name) in known:
                        continue
                    result.append(
                        self._remote_resource(comfy_name, kind=kind, state=state)
                    )
                    known.add(_normalized_name(comfy_name))
            if not local_root_available and not result:
                label = "checkpoints" if kind is Krea2ResourceKind.MODEL else "LoRA"
                warnings.append(
                    f"Dossier local KREA2 des {label} inaccessible : {root}."
                )
            if not result:
                warnings.append(
                    "Aucun "
                    + ("checkpoint" if kind is Krea2ResourceKind.MODEL else "LoRA")
                    + " KREA2 détecté."
                )
            self._inventory_warnings[kind] = tuple(warnings)
        result.sort(
            key=lambda item: (
                not item.favorite,
                item.category.casefold(),
                item.filename.casefold(),
            )
        )
        return tuple(result)

    def _remote_resource(
        self,
        comfy_name: str,
        *,
        kind: Krea2ResourceKind,
        state: Mapping[str, Any],
    ) -> Krea2Resource:
        relative = comfy_name.split("/", 1)[1]
        resource_id = _resource_id(kind, comfy_name)
        preferences = state.get("preferences")
        preference = (
            preferences.get(resource_id, {})
            if isinstance(preferences, Mapping)
            else {}
        )
        favorite = bool(preference.get("favorite", False))
        try:
            safety = Krea2ResourceSafety(
                preference.get("safety", Krea2ResourceSafety.UNCLASSIFIED.value)
            )
        except ValueError:
            safety = Krea2ResourceSafety.UNCLASSIFIED
        remote_values = state.get("remote")
        remote = (
            remote_values.get(resource_id, {})
            if isinstance(remote_values, Mapping)
            else {}
        )
        if not isinstance(remote, Mapping):
            remote = {}
        source_url = _optional_text(remote.get("source_url"))
        source_url = _preferred_civitai_host(source_url, safety)
        if source_url is None:
            source_url = _civitai_search_url(Path(relative).name, safety=safety)
        if kind is Krea2ResourceKind.MODEL:
            precision, precision_source = _model_precision(
                Path(relative).name,
                preference,
            )
            category = f"favorite_{precision.value}" if favorite else precision.value
        else:
            category = "favorite" if favorite else safety.value
            precision = None
            precision_source = None
        return Krea2Resource(
            resource_id=resource_id,
            kind=kind,
            comfy_name=comfy_name,
            filename=Path(relative).name,
            relative_path=relative,
            size_bytes=0,
            favorite=favorite,
            category=category,
            safety=safety,
            precision=precision,
            precision_source=precision_source,
            source_url=source_url,
            current_version_id=_positive_int(remote.get("current_version_id")),
            latest_version_id=_positive_int(remote.get("latest_version_id")),
            latest_version_name=_optional_text(remote.get("latest_version_name")),
            update_available=(
                remote.get("update_available")
                if isinstance(remote.get("update_available"), bool)
                else None
            ),
            remote_checked_at=_optional_text(remote.get("checked_at")),
            warning=(
                _optional_text(remote.get("warning"))
                or (
                    "Disponible dans ComfyUI ; fichier local inaccessible, "
                    + (
                        "précision déduite du nom, taille et métadonnées non vérifiables."
                        if precision_source == "filename"
                        else "taille, précision et métadonnées non vérifiables."
                    )
                )
            ),
        )

    def _resource(
        self,
        path: Path,
        *,
        root: Path,
        kind: Krea2ResourceKind,
        state: Mapping[str, Any],
    ) -> Krea2Resource:
        relative = path.relative_to(root).as_posix()
        prefix = "Krea2" if kind is Krea2ResourceKind.MODEL else "krea2"
        comfy_name = f"{prefix}/{relative}"
        resource_id = _resource_id(kind, comfy_name)
        preferences = state.get("preferences")
        preference = (
            preferences.get(resource_id, {})
            if isinstance(preferences, Mapping)
            else {}
        )
        favorite = bool(preference.get("favorite", False))
        sidecar, warning = _read_rgthree_sidecar(path)
        sidecar_safety = _sidecar_safety(sidecar)
        try:
            safety = Krea2ResourceSafety(
                preference.get("safety", sidecar_safety.value)
            )
        except ValueError:
            safety = sidecar_safety
        source_url = _sidecar_source_url(sidecar, safety)
        sha256 = _sidecar_sha256(sidecar)
        version_id = _sidecar_version_id(sidecar)
        remote_values = state.get("remote")
        remote = (
            remote_values.get(resource_id, {})
            if isinstance(remote_values, Mapping)
            else {}
        )
        if not isinstance(remote, Mapping):
            remote = {}
        source_url = _optional_text(remote.get("source_url")) or source_url
        source_url = _preferred_civitai_host(source_url, safety)
        if source_url is None:
            source_url = _civitai_search_url(path.name, safety=safety)
        if kind is Krea2ResourceKind.MODEL:
            precision, precision_source = _model_precision(
                path.name,
                preference,
                size_bytes=path.stat().st_size,
            )
            category = f"favorite_{precision.value}" if favorite else precision.value
        else:
            category = "favorite" if favorite else safety.value
            precision = None
            precision_source = None
        return Krea2Resource(
            resource_id=resource_id,
            kind=kind,
            comfy_name=comfy_name,
            filename=path.name,
            relative_path=relative,
            size_bytes=path.stat().st_size,
            favorite=favorite,
            category=category,
            safety=safety,
            precision=precision,
            precision_source=precision_source,
            source_url=source_url,
            sha256=sha256,
            current_version_id=(
                _positive_int(remote.get("current_version_id")) or version_id
            ),
            latest_version_id=_positive_int(remote.get("latest_version_id")),
            latest_version_name=_optional_text(remote.get("latest_version_name")),
            update_available=(
                remote.get("update_available")
                if isinstance(remote.get("update_available"), bool)
                else None
            ),
            remote_checked_at=_optional_text(remote.get("checked_at")),
            warning=_optional_text(remote.get("warning")) or warning,
        )

    def _load_state(self) -> dict[str, Any]:
        if not self._state_path.is_file():
            return {"schema_version": 1, "preferences": {}, "remote": {}}
        try:
            value = json.loads(self._state_path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("schema_version") != 1:
                raise ValueError("unsupported resource state")
            return value
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return {"schema_version": 1, "preferences": {}, "remote": {}}

    def _save_state(self, state: Mapping[str, Any]) -> None:
        content = (
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
            + b"\n"
        )
        descriptor, temporary = tempfile.mkstemp(
            dir=self._state_path.parent,
            prefix=f".{self._state_path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self._state_path)
        finally:
            temporary_path.unlink(missing_ok=True)


def serialize_krea2_resource(resource: Krea2Resource) -> dict[str, object]:
    value = asdict(resource)
    value["kind"] = resource.kind.value
    value["safety"] = resource.safety.value
    value["precision"] = resource.precision.value if resource.precision else None
    value["size_gib"] = round(resource.size_bytes / 1024**3, 2)
    return value


def _resource_id(kind: Krea2ResourceKind, comfy_name: str) -> str:
    return hashlib.sha256(
        f"{kind.value}:{_normalized_name(comfy_name)}".encode("utf-8")
    ).hexdigest()[:24]


def _normalized_name(value: str) -> str:
    return value.replace("\\", "/").casefold()


def _model_precision(
    filename: str,
    preference: Mapping[str, Any],
    *,
    size_bytes: int | None = None,
) -> tuple[Krea2ResourcePrecision, str]:
    try:
        manual = Krea2ResourcePrecision(preference.get("precision"))
    except (TypeError, ValueError):
        manual = None
    if manual in {Krea2ResourcePrecision.BF16, Krea2ResourcePrecision.INT8}:
        return manual, "manual"
    if size_bytes is not None:
        return (
            Krea2ResourcePrecision.BF16
            if size_bytes > _BF16_THRESHOLD_BYTES
            else Krea2ResourcePrecision.INT8,
            "size",
        )
    normalized = re.sub(r"[^a-z0-9]+", "", filename.casefold())
    if any(token in normalized for token in ("int8", "int4", "fp8")):
        return Krea2ResourcePrecision.INT8, "filename"
    if "bf16" in normalized:
        return Krea2ResourcePrecision.BF16, "filename"
    return Krea2ResourcePrecision.UNKNOWN, "unavailable"


def _krea2_comfy_name(
    value: object,
    kind: Krea2ResourceKind,
) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().replace("\\", "/").lstrip("/")
    prefix, separator, relative = normalized.partition("/")
    if separator != "/" or prefix.casefold() != "krea2" or not relative:
        return None
    if any(part in {"", ".", ".."} for part in relative.split("/")):
        return None
    if Path(relative).suffix.casefold() not in _MODEL_EXTENSIONS:
        return None
    canonical_prefix = "Krea2" if kind is Krea2ResourceKind.MODEL else "krea2"
    return f"{canonical_prefix}/{relative}"


def _read_rgthree_sidecar(path: Path) -> tuple[Mapping[str, Any], str | None]:
    sidecar_path = path.with_name(f"{path.name}.rgthree-info.json")
    if not sidecar_path.is_file() or sidecar_path.is_symlink():
        return {}, None
    try:
        value = json.loads(sidecar_path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise TypeError("sidecar root is not an object")
        return value, None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
        return {}, f"Métadonnées locales illisibles : {type(error).__name__}"


def _sidecar_source_url(
    sidecar: Mapping[str, Any],
    safety: Krea2ResourceSafety,
) -> str | None:
    links = sidecar.get("links")
    if isinstance(links, list):
        for link in links:
            if isinstance(link, str) and "/models/" in link:
                candidate = _preferred_civitai_host(link, safety)
                if candidate is not None:
                    return candidate
    return None


def _sidecar_sha256(sidecar: Mapping[str, Any]) -> str | None:
    value = sidecar.get("sha256")
    if isinstance(value, str) and _SHA256.fullmatch(value):
        return value.casefold()
    raw = sidecar.get("raw")
    civitai = raw.get("civitai") if isinstance(raw, Mapping) else None
    value = civitai.get("_sha256") if isinstance(civitai, Mapping) else None
    return value.casefold() if isinstance(value, str) and _SHA256.fullmatch(value) else None


def _sidecar_version_id(sidecar: Mapping[str, Any]) -> int | None:
    raw = sidecar.get("raw")
    civitai = raw.get("civitai") if isinstance(raw, Mapping) else None
    return _positive_int(civitai.get("id")) if isinstance(civitai, Mapping) else None


def _sidecar_safety(sidecar: Mapping[str, Any]) -> Krea2ResourceSafety:
    raw = sidecar.get("raw")
    civitai = raw.get("civitai") if isinstance(raw, Mapping) else None
    levels: list[int] = []
    if isinstance(civitai, Mapping):
        level = _positive_int(civitai.get("nsfwLevel"))
        if level is not None:
            levels.append(level)
        model = civitai.get("model")
        if isinstance(model, Mapping) and model.get("nsfw") is True:
            return Krea2ResourceSafety.NSFW
    images = sidecar.get("images")
    if isinstance(images, list):
        levels.extend(
            level
            for image in images
            if isinstance(image, Mapping)
            for level in [_positive_int(image.get("nsfwLevel"))]
            if level is not None
        )
    if any(level >= 4 for level in levels):
        return Krea2ResourceSafety.NSFW
    if levels:
        return Krea2ResourceSafety.SFW
    return Krea2ResourceSafety.UNCLASSIFIED


def _preferred_civitai_host(
    url: str | None,
    safety: Krea2ResourceSafety,
) -> str | None:
    if not url:
        return None
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or host not in {"civitai.com", "www.civitai.com", "civitai.red", "www.civitai.red"}:
        return None
    preferred_host = "civitai.red" if safety is Krea2ResourceSafety.NSFW else "civitai.com"
    return urllib.parse.urlunsplit(("https", preferred_host, parsed.path, parsed.query, ""))


def _civitai_search_url(
    filename: str,
    *,
    safety: Krea2ResourceSafety = Krea2ResourceSafety.UNCLASSIFIED,
) -> str:
    host = "https://civitai.red" if safety is Krea2ResourceSafety.NSFW else "https://civitai.com"
    return f"{host}/search/models?{urllib.parse.urlencode({'query': Path(filename).stem})}"


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdecimal() and int(value) > 0:
        return int(value)
    return None


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
