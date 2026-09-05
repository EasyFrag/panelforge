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
import html
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

_DEFAULT_LORA_CATEGORIES = {
    # SFW utilities and detailers.
    "detailer-krea2.safetensors": "sfw_utility",
    "zy_backgrounddetail_k2.safetensors": "sfw_utility",
    "krea2-masterpieces-v51.safetensors": "sfw_utility",
    "wetness_krea2_loraholic.safetensors": "sfw_utility",
    # SFW styles.
    "dc vast expanse [krea2][gpt4.1captioned][trigger=dcvstexp.][rank32] v1.safetensors": "sfw_style",
    "flat_anime_krea_@.safetensors": "sfw_style",
    "impressionismkrea2raw.safetensors": "sfw_style",
    "krea2mythp0rtr4itstyle.safetensors": "sfw_style",
    "moriimee_krea_epoch_10.safetensors": "sfw_style",
    "vhs_krea2.safetensors": "sfw_style",
    "krea2-fx-monster-oldschool-v1.safetensors": "sfw_style",
    "midjounreynsfwkrea2raw.safetensors": "sfw_style",
    # NSFW utility/global/detail categories.
    "krea2_textfusion_refusal_reduction.safetensors": "nsfw_utility",
    "bondage_aio_-_krea_2_epoch_10.safetensors": "nsfw_global",
    "krea2_nud3.safetensors": "nsfw_global",
    "mysticxxx_krea2_v3.safetensors": "nsfw_global",
    "realism_engine_krea2_v3.1.safetensors": "nsfw_global",
    "snofs_krea_v1_3.safetensors": "nsfw_global",
    "snofs_krea_v1_4.safetensors": "nsfw_global",
    "pornmaster_breasts_slider_krea2_v1.safetensors": "nsfw_sliders",
    "pornmaster_krea2_realism_slider_v1.safetensors": "nsfw_sliders",
    "pornmaster_krea2_skin_tone_slider_v1.safetensors": "nsfw_sliders",
    "pornmaster_low_resolution_slider_krea2_v1.safetensors": "nsfw_sliders",
    "eastern innie_pussy_epoch_10.safetensors": "nsfw_details",
    "western_innie_pussy_epoch_10.safetensors": "nsfw_details",
    "m99_labiaplasty_pussy_8a_krea2.safetensors": "nsfw_details",
    "realcumk4.safetensors": "nsfw_details",
    "transparent_clothes_krea2_v2.safetensors": "nsfw_details",
    "krea2 masturbation.safetensors": "nsfw_poses",
    # Technical KREA Edit LoRAs remain inspectable but are not selectable.
    "krea2 edit anime to real_000001500.safetensors": "excluded_krea_edit",
    "krea2_identity_edit_v1_2.safetensors": "excluded_krea_edit",
}
_NSFW_SLIDER_TOKENS = ("penis", "cumamount", "cleavage", "underboob")


class Krea2ResourceKind(StrEnum):
    MODEL = "model"
    LORA = "lora"


class Krea2ResourceSafety(StrEnum):
    SFW = "sfw"
    NSFW = "nsfw"
    UNCLASSIFIED = "unclassified"


class Krea2LoraCategory(StrEnum):
    SFW_UTILITY = "sfw_utility"
    SFW_STYLE = "sfw_style"
    SFW_SLIDERS = "sfw_sliders"
    NSFW_UTILITY = "nsfw_utility"
    NSFW_GLOBAL = "nsfw_global"
    NSFW_SLIDERS = "nsfw_sliders"
    NSFW_DETAILS = "nsfw_details"
    NSFW_POSES = "nsfw_poses"
    EXCLUDED_KREA_EDIT = "excluded_krea_edit"
    UNCLASSIFIED = "unclassified"


class Krea2ResourcePrecision(StrEnum):
    BF16 = "bf16"
    INT8 = "int8"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class _CivitaiCheckpointOverride:
    model_id: int
    version_id: int
    safety: Krea2ResourceSafety


_CIVITAI_CHECKPOINT_OVERRIDES = {
    # Local conversions and renames whose public CivitAI filename differs.
    "cielbleukrea2_v1bf16.safetensors": _CivitaiCheckpointOverride(
        2812328,
        3171612,
        Krea2ResourceSafety.NSFW,
    ),
    "chimeracenterkroma_v20bf16andfp8.safetensors": _CivitaiCheckpointOverride(
        2883206,
        3269650,
        Krea2ResourceSafety.SFW,
    ),
    "darkbeast30bf16_darkbeast330krea2.safetensors": _CivitaiCheckpointOverride(
        2242173,
        3173268,
        Krea2ResourceSafety.NSFW,
    ),
    "darkbeast30bf16int8_darkbeastkrea2fp8.safetensors": _CivitaiCheckpointOverride(
        2242173,
        3078453,
        Krea2ResourceSafety.NSFW,
    ),
    "krea2gptgrandpussytruth_gptint4int8convrot.safetensors": _CivitaiCheckpointOverride(
        452459,
        3123514,
        Krea2ResourceSafety.NSFW,
    ),
}


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
    lora_category: Krea2LoraCategory | None = None
    selectable: bool = True
    display_name: str | None = None
    base_model: str | None = None
    trained_words: tuple[str, ...] = ()
    description: str | None = None
    strength_min: float | None = None
    strength_max: float | None = None
    notes: str | None = None
    preview_urls: tuple[str, ...] = ()
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
    lora_category: Krea2LoraCategory | None = None
    precision: Krea2ResourcePrecision | None = None


class Krea2ComfyInventory(Protocol):
    def list_unet_models(self) -> tuple[str, ...]: ...
    def list_lora_models(self) -> tuple[str, ...]: ...
    def get_cached_model_info(
        self,
        kind: str,
        comfy_name: str,
    ) -> Mapping[str, Any] | None: ...


class CivitaiMetadataClient:
    """Small public CivitAI API reader used only on explicit refresh."""

    def __init__(
        self,
        *,
        base_url: str = "https://civitai.red/api/v1",
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
        matched_model: Mapping[str, Any] | None = None
        matched_safety = Krea2ResourceSafety.UNCLASSIFIED
        filename_verified = True
        if sha256 is not None:
            version = self._get(f"/model-versions/by-hash/{sha256}")
        else:
            override = _CIVITAI_CHECKPOINT_OVERRIDES.get(filename.casefold())
            if override is not None:
                selected = self._find_override(override)
                if selected is None:
                    version = None
                else:
                    version, matched_model = selected
                    matched_safety = override.safety
                    filename_verified = False
            else:
                matches = self._find_exact_files(filename)
                if len(matches) > 1:
                    return {
                        "source_url": _civitai_search_url(filename),
                        "warning": (
                            "Plusieurs fiches CivitAI utilisent exactement ce nom de fichier ; "
                            "aucune n'a été sélectionnée automatiquement."
                        ),
                    }
                if matches:
                    version, matched_model, filename_verified = matches[0]
                else:
                    version = None
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
        model = matched_model
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
        detected_safety = _civitai_safety(version, model)
        if matched_safety is Krea2ResourceSafety.UNCLASSIFIED:
            matched_safety = detected_safety
        source_host = (
            "https://civitai.red"
            if matched_safety is Krea2ResourceSafety.NSFW
            else "https://civitai.com"
        )
        source_url = (
            f"{source_host}/models/{model_id}?modelVersionId={version_id}"
            if model_id is not None and version_id is not None
            else _civitai_search_url(filename)
        )
        return {
            "source_url": source_url,
            "display_name": (
                _optional_text(model.get("name"))
                if isinstance(model, Mapping)
                else None
            ) or _optional_text(version.get("name")),
            "base_model": _optional_text(version.get("baseModel")),
            "trained_words": list(_metadata_trained_words(version)),
            "description": _metadata_description(version, model),
            "preview_urls": list(_metadata_preview_urls(version, model)),
            "current_version_id": version_id,
            "latest_version_id": latest_id,
            "latest_version_name": latest_name,
            "update_available": (
                latest_id != version_id
                if latest_id is not None and version_id is not None
                else None
            ),
            "safety": matched_safety.value,
            "warning": (
                None
                if filename_verified
                else (
                    "Fiche CivitAI rattachée au nom installé ; "
                    "identité du fichier non vérifiée par hash."
                )
            ),
        }

    def _find_override(
        self,
        override: _CivitaiCheckpointOverride,
    ) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
        model = self._get(f"/models/{override.model_id}")
        versions = model.get("modelVersions") if isinstance(model, Mapping) else None
        if not isinstance(versions, list):
            return None
        for version in versions:
            if (
                isinstance(version, Mapping)
                and _positive_int(version.get("id")) == override.version_id
            ):
                enriched = dict(version)
                enriched.setdefault("modelId", override.model_id)
                return enriched, model
        return None

    def _find_exact_files(
        self,
        filename: str,
    ) -> tuple[tuple[Mapping[str, Any], Mapping[str, Any], bool], ...]:
        targets = {
            candidate.casefold(): candidate.casefold() == filename.casefold()
            for candidate in _civitai_filename_candidates(filename)
        }
        matches: dict[
            tuple[int | None, int | None],
            tuple[Mapping[str, Any], Mapping[str, Any], bool],
        ] = {}
        for query in _civitai_search_queries(filename):
            payload = self._get(
                "/models?"
                + urllib.parse.urlencode(
                    {"query": query, "limit": 20, "nsfw": "true"}
                )
            )
            items = payload.get("items") if isinstance(payload, Mapping) else None
            if not isinstance(items, list):
                continue
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
                    matched_names = {
                        str(file.get("name", "")).casefold()
                        for file in files
                        if isinstance(file, Mapping)
                        and str(file.get("name", "")).casefold() in targets
                    }
                    if not matched_names:
                        continue
                    enriched = dict(version)
                    enriched.setdefault("modelId", model.get("id"))
                    key = (
                        _positive_int(model.get("id")),
                        _positive_int(version.get("id")),
                    )
                    verified = any(targets[name] for name in matched_names)
                    previous = matches.get(key)
                    matches[key] = (
                        enriched,
                        model,
                        verified or (previous[2] if previous is not None else False),
                    )
        return tuple(matches.values())

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
        lora_category: Krea2LoraCategory | None = None,
        precision: Krea2ResourcePrecision | None = None,
        reset_precision: bool = False,
    ) -> Krea2Resource:
        if favorite is not None and not isinstance(favorite, bool):
            raise TypeError("favorite must be a boolean")
        if safety is not None and not isinstance(safety, Krea2ResourceSafety):
            raise TypeError("safety must be a Krea2ResourceSafety")
        if lora_category is not None and not isinstance(lora_category, Krea2LoraCategory):
            raise TypeError("lora_category must be a Krea2LoraCategory")
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
            if (
                lora_category is not None
                and resource.kind is not Krea2ResourceKind.LORA
            ):
                raise ValueError("lora_category can only classify a LoRA")
            state = self._load_state()
            preferences = state.setdefault("preferences", {})
            current = preferences.get(resource_id, {})
            if not isinstance(current, dict):
                current = {}
            if favorite is not None:
                current["favorite"] = favorite
            if safety is not None:
                current["safety"] = safety.value
            if lora_category is not None:
                current["lora_category"] = lora_category.value
            if reset_precision:
                current.pop("precision", None)
            elif precision is not None:
                current["precision"] = precision.value
            preferences[resource_id] = current
            self._save_state(state)
            return self._reload_resource(resource, state)

    def set_annotations(
        self,
        resource_id: str,
        annotations: Mapping[str, object],
    ) -> Krea2Resource:
        allowed = {"display_name", "strength_min", "strength_max", "notes"}
        unexpected = set(annotations) - allowed
        if unexpected:
            raise ValueError(f"unsupported resource annotation: {sorted(unexpected)[0]}")
        normalized: dict[str, str | float | None] = {}
        if "display_name" in annotations:
            normalized["display_name"] = _annotation_text(
                annotations["display_name"],
                "display_name",
                maximum=200,
            )
        if "notes" in annotations:
            normalized["notes"] = _annotation_text(
                annotations["notes"],
                "notes",
                maximum=4_000,
            )
        for field in ("strength_min", "strength_max"):
            if field in annotations:
                normalized[field] = _annotation_strength(annotations[field], field)
        with self._lock:
            resource = self.get(resource_id)
            if resource.kind is not Krea2ResourceKind.LORA and any(
                field in annotations for field in ("strength_min", "strength_max")
            ):
                raise ValueError("strength annotations can only edit a LoRA")
            state = self._load_state()
            preferences = state.setdefault("preferences", {})
            current = preferences.get(resource_id, {})
            if not isinstance(current, dict):
                current = {}
            proposed = dict(current)
            for field, value in normalized.items():
                if value is None:
                    proposed.pop(field, None)
                else:
                    proposed[field] = value
            strength_min = _stored_strength(proposed.get("strength_min"))
            strength_max = _stored_strength(proposed.get("strength_max"))
            if (
                strength_min is not None
                and strength_max is not None
                and strength_min > strength_max
            ):
                raise ValueError("strength_min must be lower than or equal to strength_max")
            preferences[resource_id] = proposed
            self._save_state(state)
            return self._reload_resource(resource, state)

    def refresh_remote(self, resource_id: str) -> Krea2Resource:
        with self._lock:
            resource = self.get(resource_id)
            checked_at = self._clock().astimezone(UTC).isoformat().replace("+00:00", "Z")
            remote: dict[str, object] = {}
            cached_info = getattr(self.comfy, "get_cached_model_info", None)
            if callable(cached_info):
                try:
                    info = cached_info(resource.kind.value, resource.comfy_name)
                    if isinstance(info, Mapping):
                        remote = _rgthree_remote_metadata(info, resource.safety)
                except Exception:
                    # rgthree is optional. Its absence must not hide the
                    # explicit CivitAI-by-name fallback below.
                    pass
            if not remote.get("preview_urls"):
                try:
                    civitai = self.civitai.inspect(
                        filename=resource.filename,
                        sha256=resource.sha256,
                        known_version_id=resource.current_version_id,
                    )
                    remote = {**remote, **civitai}
                except Exception as error:
                    remote = {
                        **remote,
                        "warning": f"CivitAI indisponible : {type(error).__name__}",
                        "source_url": remote.get("source_url") or resource.source_url,
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
        lora_category = None
        selectable = True
        if kind is Krea2ResourceKind.LORA:
            lora_category = _lora_category(relative, preference)
            safety = _lora_category_safety(lora_category) or safety
            selectable = lora_category is not Krea2LoraCategory.EXCLUDED_KREA_EDIT
        remote_values = state.get("remote")
        remote = (
            remote_values.get(resource_id, {})
            if isinstance(remote_values, Mapping)
            else {}
        )
        if not isinstance(remote, Mapping):
            remote = {}
        remote_safety = _stored_resource_safety(remote.get("safety"))
        if (
            "safety" not in preference
            and remote_safety is not None
            and (
                kind is Krea2ResourceKind.MODEL
                or _lora_category_safety(lora_category) is None
            )
        ):
            safety = remote_safety
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
            assert lora_category is not None
            category = "favorite" if favorite else lora_category.value
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
            lora_category=lora_category,
            selectable=selectable,
            display_name=(
                _preference_text(preference.get("display_name"))
                or _optional_text(remote.get("display_name"))
                or Path(relative).stem
            ),
            base_model=_optional_text(remote.get("base_model")),
            trained_words=_stored_text_items(remote.get("trained_words")),
            description=_optional_text(remote.get("description")),
            strength_min=_stored_strength(preference.get("strength_min")),
            strength_max=_stored_strength(preference.get("strength_max")),
            notes=_preference_text(preference.get("notes")),
            preview_urls=_stored_https_urls(remote.get("preview_urls")),
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
        lora_category = None
        selectable = True
        if kind is Krea2ResourceKind.LORA:
            lora_category = _lora_category(relative, preference)
            safety = _lora_category_safety(lora_category) or safety
            selectable = lora_category is not Krea2LoraCategory.EXCLUDED_KREA_EDIT
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
        remote_safety = _stored_resource_safety(remote.get("safety"))
        if (
            "safety" not in preference
            and sidecar_safety is Krea2ResourceSafety.UNCLASSIFIED
            and remote_safety is not None
            and (
                kind is Krea2ResourceKind.MODEL
                or _lora_category_safety(lora_category) is None
            )
        ):
            safety = remote_safety
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
            assert lora_category is not None
            category = "favorite" if favorite else lora_category.value
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
            lora_category=lora_category,
            selectable=selectable,
            display_name=(
                _preference_text(preference.get("display_name"))
                or _sidecar_display_name(sidecar)
                or _optional_text(remote.get("display_name"))
                or path.stem
            ),
            base_model=(
                _sidecar_base_model(sidecar)
                or _optional_text(remote.get("base_model"))
            ),
            trained_words=(
                _sidecar_trained_words(sidecar)
                or _stored_text_items(remote.get("trained_words"))
            ),
            description=(
                _sidecar_description(sidecar)
                or _optional_text(remote.get("description"))
            ),
            strength_min=_stored_strength(preference.get("strength_min")),
            strength_max=_stored_strength(preference.get("strength_max")),
            notes=_preference_text(preference.get("notes")),
            preview_urls=(
                _sidecar_preview_urls(sidecar)
                or _stored_https_urls(remote.get("preview_urls"))
            ),
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
    value["lora_category"] = (
        resource.lora_category.value if resource.lora_category else None
    )
    value["precision"] = resource.precision.value if resource.precision else None
    value["size_gib"] = round(resource.size_bytes / 1024**3, 2)
    return value


def _resource_id(kind: Krea2ResourceKind, comfy_name: str) -> str:
    return hashlib.sha256(
        f"{kind.value}:{_normalized_name(comfy_name)}".encode("utf-8")
    ).hexdigest()[:24]


def _normalized_name(value: str) -> str:
    return value.replace("\\", "/").casefold()


def _annotation_text(value: object, field: str, *, maximum: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field} must be text or null")
    text = value.strip()
    if not text:
        return None
    if len(text) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    return text


def _annotation_strength(value: object, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be a number or null")
    normalized = float(value)
    if normalized < -1 or normalized > 1:
        raise ValueError(f"{field} must be between -1 and 1")
    return normalized


def _preference_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _stored_strength(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    normalized = float(value)
    return normalized if -1 <= normalized <= 1 else None


def _lora_category(
    relative_path: str,
    preference: Mapping[str, Any],
) -> Krea2LoraCategory:
    try:
        return Krea2LoraCategory(preference.get("lora_category"))
    except (TypeError, ValueError):
        pass
    normalized = _normalized_name(relative_path)
    filename = normalized.rsplit("/", 1)[-1]
    explicit = _DEFAULT_LORA_CATEGORIES.get(filename)
    if explicit is not None:
        return Krea2LoraCategory(explicit)
    if normalized.startswith("poses/"):
        return Krea2LoraCategory.NSFW_POSES
    if normalized.startswith("sliders/"):
        if any(token in filename for token in _NSFW_SLIDER_TOKENS):
            return Krea2LoraCategory.NSFW_SLIDERS
        return Krea2LoraCategory.SFW_SLIDERS
    return Krea2LoraCategory.UNCLASSIFIED


def _lora_category_safety(
    category: Krea2LoraCategory,
) -> Krea2ResourceSafety | None:
    if category.value.startswith("sfw_"):
        return Krea2ResourceSafety.SFW
    if category.value.startswith("nsfw_"):
        return Krea2ResourceSafety.NSFW
    return None


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


def _sidecar_display_name(sidecar: Mapping[str, Any]) -> str | None:
    return _optional_text(sidecar.get("name"))


def _sidecar_base_model(sidecar: Mapping[str, Any]) -> str | None:
    direct = _optional_text(sidecar.get("baseModel"))
    if direct is not None:
        return direct
    raw = sidecar.get("raw")
    civitai = raw.get("civitai") if isinstance(raw, Mapping) else None
    return _optional_text(civitai.get("baseModel")) if isinstance(civitai, Mapping) else None


def _sidecar_trained_words(sidecar: Mapping[str, Any]) -> tuple[str, ...]:
    return _metadata_trained_words(sidecar)


def _metadata_trained_words(metadata: Mapping[str, Any]) -> tuple[str, ...]:
    values = metadata.get("trainedWords")
    if not isinstance(values, list):
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, str):
            candidate = _optional_text(value)
        elif isinstance(value, Mapping):
            candidate = _optional_text(value.get("word") or value.get("name"))
        else:
            candidate = None
        if candidate is None or len(candidate) > 200:
            continue
        key = candidate.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
        if len(result) >= 50:
            break
    return tuple(result)


def _sidecar_description(sidecar: Mapping[str, Any]) -> str | None:
    raw = sidecar.get("raw")
    civitai = raw.get("civitai") if isinstance(raw, Mapping) else None
    if not isinstance(civitai, Mapping):
        return None
    value = _optional_text(civitai.get("description"))
    if value is None:
        model = civitai.get("model")
        value = _optional_text(model.get("description")) if isinstance(model, Mapping) else None
    if value is None:
        return None
    return _plain_description(value)


def _metadata_description(
    version: Mapping[str, Any],
    model: Mapping[str, Any] | None,
) -> str | None:
    value = _optional_text(version.get("description"))
    if value is None and isinstance(model, Mapping):
        value = _optional_text(model.get("description"))
    return _plain_description(value)


def _plain_description(value: str | None) -> str | None:
    if value is None:
        return None
    plain = html.unescape(re.sub(r"<[^>]+>", " ", value))
    compact = re.sub(r"\s+", " ", plain).strip()
    compact = re.sub(r"\s+([.,;:!?])", r"\1", compact)
    return compact[:4_000] or None


def _sidecar_preview_urls(sidecar: Mapping[str, Any]) -> tuple[str, ...]:
    return _metadata_preview_urls(sidecar)


def _rgthree_remote_metadata(
    info: Mapping[str, Any],
    safety: Krea2ResourceSafety,
) -> dict[str, object]:
    """Translate rgthree's cached info file without requesting a hash refresh."""

    values: dict[str, object] = {
        "source_url": _sidecar_source_url(info, safety),
        "display_name": _sidecar_display_name(info),
        "base_model": _sidecar_base_model(info),
        "trained_words": list(_sidecar_trained_words(info)),
        "description": _sidecar_description(info),
        "preview_urls": list(_sidecar_preview_urls(info)),
        "current_version_id": _sidecar_version_id(info),
        "warning": None,
    }
    return {
        key: value
        for key, value in values.items()
        if value not in (None, "", [], ()) or key == "warning"
    }


def _metadata_preview_urls(
    version: Mapping[str, Any],
    model: Mapping[str, Any] | None = None,
) -> tuple[str, ...]:
    values = version.get("images")
    if not isinstance(values, list) and isinstance(model, Mapping):
        values = model.get("images")
    if not isinstance(values, list):
        return ()
    result: list[str] = []
    for value in values:
        candidate = _optional_text(value.get("url")) if isinstance(value, Mapping) else None
        if candidate is None:
            continue
        try:
            parsed = urllib.parse.urlsplit(candidate)
        except ValueError:
            continue
        if parsed.scheme != "https" or not parsed.hostname:
            continue
        result.append(candidate)
        if len(result) >= 3:
            break
    return tuple(result)


def _stored_text_items(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        candidate = _optional_text(item)
        if candidate is None or len(candidate) > 200:
            continue
        key = candidate.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
        if len(result) >= 50:
            break
    return tuple(result)


def _stored_https_urls(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    result: list[str] = []
    for item in value:
        candidate = _optional_text(item)
        if candidate is None:
            continue
        try:
            parsed = urllib.parse.urlsplit(candidate)
        except ValueError:
            continue
        if parsed.scheme != "https" or not parsed.hostname:
            continue
        result.append(candidate)
        if len(result) >= 3:
            break
    return tuple(result)


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


def _civitai_filename_candidates(filename: str) -> tuple[str, ...]:
    path = Path(filename)
    stem = path.stem.strip()
    if not stem:
        return (path.name,)
    values = [path.name]
    stripped = re.sub(
        r"(?i)(?:[_-]?(?:bf16|fp8|int8|int4|convrot))+\Z",
        "",
        stem,
    ).rstrip("_-")
    if stripped and stripped.casefold() != stem.casefold():
        values.append(f"{stripped}{path.suffix}")
    return tuple(dict.fromkeys(values))


def _civitai_search_queries(filename: str) -> tuple[str, ...]:
    stems = [Path(value).stem for value in _civitai_filename_candidates(filename)]
    human = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", Path(filename).stem)
    human = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", human)
    human = re.sub(r"[_-]+", " ", human)
    noise = {
        "and",
        "bf16",
        "checkpoint",
        "convrot",
        "fp8",
        "int4",
        "int8",
        "krea",
        "krea2",
        "nsfw",
    }
    family = " ".join(
        token
        for token in human.split()
        if token.casefold() not in noise
        and re.fullmatch(r"(?i)v?\d+(?:\.\d+)?", token) is None
    )
    values = [*stems, family]
    return tuple(
        dict.fromkeys(value.strip() for value in values if value and value.strip())
    )


def _civitai_safety(
    version: Mapping[str, Any],
    model: Mapping[str, Any] | None,
) -> Krea2ResourceSafety:
    if isinstance(model, Mapping) and model.get("nsfw") is True:
        return Krea2ResourceSafety.NSFW
    levels = [
        level
        for value in (
            version.get("images"),
            model.get("images") if isinstance(model, Mapping) else None,
        )
        if isinstance(value, list)
        for image in value
        if isinstance(image, Mapping)
        for level in [_positive_int(image.get("nsfwLevel"))]
        if level is not None
    ]
    if any(level >= 4 for level in levels):
        return Krea2ResourceSafety.NSFW
    if levels or (isinstance(model, Mapping) and model.get("nsfw") is False):
        return Krea2ResourceSafety.SFW
    return Krea2ResourceSafety.UNCLASSIFIED


def _stored_resource_safety(value: object) -> Krea2ResourceSafety | None:
    try:
        return Krea2ResourceSafety(value)
    except (TypeError, ValueError):
        return None


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
