"""Versioned visual recipe catalogue for KREA2 batch generation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from panelforge.domain.krea2_batch import (
    Krea2BatchSettings,
    Krea2LoraSelection,
    Krea2PromptLanguage,
)
from panelforge.domain.krea2_assisted import Krea2AssistedRecipeDraft
from panelforge.domain.krea2_lab import Krea2AspectRatio


_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")


@dataclass(frozen=True, slots=True)
class Krea2VisualRecipe:
    recipe_id: str
    version: str
    display_name: str
    description: str
    identity: str
    invariants: tuple[str, ...]
    variables: tuple[str, ...]
    risks: tuple[str, ...]
    canonical_prompt: str
    settings: Krea2BatchSettings
    content_sha256: str
    prompt_language: Krea2PromptLanguage = Krea2PromptLanguage.ENGLISH
    parent_version: str | None = None
    status: str = "published"

    def build_generation_prompts(
        self,
        *,
        image_count: int,
        direction: str,
        recent_signatures: tuple[str, ...],
    ) -> tuple[str, str]:
        language = _prompt_language_label(self.prompt_language)
        system = (
            "You create controlled variations of one proven KREA2 image recipe. "
            "Keep the fixed visual skeleton, composition, depth hierarchy, rendering style, "
            "and all negative constraints. Change only variables explicitly allowed by the recipe. "
            "Each candidate must be meaningfully different from every other candidate and from "
            "the recent signatures, without drifting into a different visual family. Return raw "
            "JSON only with exactly this shape: "
            '{"prompts":[{"signature":"short unique variation signature",'
            f'"prompt":"complete standalone {language} prompt"}}]}}. '
            "Write only the prompt field in the target language; keep signatures concise. Preserve "
            "LoRA trigger phrases, proper names, filenames and quoted literal text verbatim. Never "
            "duplicate a prompt bilingually. Never return fragments, commentary, markdown or seed values."
        )
        user = "\n\n".join(
            (
                f"RECIPE: {self.recipe_id}@{self.version}",
                f"IDENTITY:\n{self.identity}",
                "FIXED INVARIANTS:\n- " + "\n- ".join(
                    _project_prompt_ratio(value, self.settings.aspect_ratio, prefix_if_missing=False)
                    for value in self.invariants
                ),
                "ALLOWED VARIABLES:\n- " + "\n- ".join(self.variables),
                "KNOWN FAILURE MODES TO AVOID:\n- " + "\n- ".join(self.risks),
                "CANONICAL PROVEN PROMPT — preserve its architecture and rewrite it in full:\n"
                + _project_prompt_ratio(self.canonical_prompt, self.settings.aspect_ratio),
                "RENDER FORMAT — authoritative for every generated prompt:\n"
                + self.settings.aspect_ratio.value,
                f"OPTIONAL DIRECTION FOR THIS BATCH:\n{direction.strip() or 'None. Vary safely.'}",
                "RECENT VARIATIONS NOT TO REPEAT:\n"
                + ("\n".join(f"- {value}" for value in recent_signatures) or "None."),
                f"Produce exactly {image_count} complete prompts and {image_count} distinct signatures.",
            )
        )
        return system, user

    def parse_prompts(
        self,
        raw_response: str,
        image_count: int,
    ) -> tuple[tuple[str, str], ...]:
        value = _decode_json_object(raw_response)
        if set(value) != {"prompts"} or not isinstance(value["prompts"], list):
            raise ValueError("batch response must contain only a prompts array")
        if len(value["prompts"]) != image_count:
            raise ValueError(f"batch response must contain exactly {image_count} prompts")
        result: list[tuple[str, str]] = []
        signatures: set[str] = set()
        for index, raw in enumerate(value["prompts"], start=1):
            if not isinstance(raw, Mapping) or set(raw) != {"signature", "prompt"}:
                raise ValueError(f"prompt {index} must contain signature and prompt")
            signature = _text(raw.get("signature"), f"prompt {index} signature")
            prompt = _text(raw.get("prompt"), f"prompt {index} content")
            normalized = " ".join(signature.casefold().split())
            if normalized in signatures:
                raise ValueError("variation signatures must be unique")
            signatures.add(normalized)
            ratio = self.settings.aspect_ratio.value.split(" ", 1)[0]
            width, height = ratio.split(":", 1)
            if re.search(rf"(?<!\d){re.escape(width)}\s*:\s*{re.escape(height)}(?!\d)", prompt) is None:
                raise ValueError(f"prompt {index} lost the required {ratio} format")
            minimum_length = (
                80
                if self.prompt_language is Krea2PromptLanguage.CHINESE_SIMPLIFIED
                else 350
            )
            if len(prompt) < minimum_length:
                raise ValueError(f"prompt {index} is not a complete standalone prompt")
            result.append((signature, prompt))
        return tuple(result)

    def build_revision_prompts(
        self,
        *,
        feedback: str,
        reviews: tuple[dict[str, str], ...],
        conversation: tuple[dict[str, str], ...] = (),
    ) -> tuple[str, str]:
        language = _prompt_language_label(self.prompt_language)
        system = (
            "You are the collaborative editor of a versioned KREA2 visual recipe. Use the discussion "
            "and image-level test feedback to improve the current candidate without losing its proven "
            "visual family. Preserve identity and fixed architecture unless the user explicitly rejects "
            "them. Technical render settings are controlled separately by the user. Return raw JSON only "
            "with exactly this shape: {\"reply\":\"concise explanation and useful questions\"," 
            "\"recipe\":{\"identity\":\"...\",\"invariants\":[\"...\"],\"variables\":[\"...\"],"
            f"\"risks\":[\"...\"],\"canonical_prompt\":\"complete {language} prompt\"}}}}. "
            "Preserve LoRA trigger phrases, proper names, filenames and quoted literal text verbatim, "
            "and never duplicate the canonical prompt bilingually. "
            "The recipe must always be directly testable even when your reply contains questions."
        )
        observations = "\n".join(
            f"- {item['decision'].upper()} · {item['signature']} · {item['comment'] or 'no comment'}"
            for item in reviews
        ) or "No per-image reviews."
        history = "\n".join(
            f"- {item['role'].upper()}: {item['message']}"
            for item in conversation[-12:]
        ) or "No earlier discussion."
        user = "\n\n".join(
            (
                f"CURRENT CANDIDATE {self.recipe_id}@{self.version}",
                f"IDENTITY:\n{self.identity}",
                "INVARIANTS:\n- " + "\n- ".join(self.invariants),
                "VARIABLES:\n- " + "\n- ".join(self.variables),
                "RISKS:\n- " + "\n- ".join(self.risks),
                "CANONICAL PROMPT:\n" + self.canonical_prompt,
                "WORKSHOP DISCUSSION:\n" + history,
                "SOURCE AND TEST-BATCH REVIEWS:\n" + observations,
                "NEW USER MESSAGE:\n" + feedback.strip(),
            )
        )
        return system, user


class LocalKrea2VisualRecipeCatalog:
    """Load shipped recipes and immutable user-approved revisions."""

    def __init__(
        self,
        shipped_root: str | Path,
        *,
        workspace_root: str | Path,
    ) -> None:
        self.shipped_root = Path(shipped_root).resolve()
        self.local_root = Path(workspace_root).resolve() / "krea2_batch_recipes"
        self.local_root.mkdir(parents=True, exist_ok=True)

    def list(self) -> tuple[Krea2VisualRecipe, ...]:
        recipes: dict[tuple[str, str], Krea2VisualRecipe] = {}
        for root in (self.shipped_root, self.local_root):
            if not root.is_dir():
                continue
            for path in root.glob("*/*/recipe.json"):
                recipe = _load_recipe(path)
                key = (recipe.recipe_id, recipe.version)
                if key in recipes and recipes[key].content_sha256 != recipe.content_sha256:
                    raise ValueError(f"conflicting recipe {recipe.recipe_id}@{recipe.version}")
                recipes[key] = recipe
        return tuple(
            sorted(
                recipes.values(),
                key=lambda recipe: (recipe.display_name.casefold(), _version_key(recipe.version)),
            )
        )

    def current(self) -> tuple[Krea2VisualRecipe, ...]:
        latest: dict[str, Krea2VisualRecipe] = {}
        for recipe in self.list():
            current = latest.get(recipe.recipe_id)
            if current is None or _version_key(recipe.version) > _version_key(current.version):
                latest[recipe.recipe_id] = recipe
        return tuple(sorted(latest.values(), key=lambda value: value.display_name.casefold()))

    def get(self, recipe_id: str, version: str) -> Krea2VisualRecipe:
        for recipe in self.list():
            if recipe.recipe_id == recipe_id and recipe.version == version:
                return recipe
        raise KeyError(f"unknown KREA2 visual recipe {recipe_id}@{version}")

    def create_technical_revision(
        self,
        base: Krea2VisualRecipe,
        settings: Krea2BatchSettings,
    ) -> Krea2VisualRecipe:
        if settings == base.settings:
            return base
        for candidate in self.list():
            if (
                candidate.recipe_id == base.recipe_id
                and candidate.parent_version == base.version
                and candidate.settings == settings
                and candidate.identity == base.identity
                and candidate.invariants == base.invariants
                and candidate.variables == base.variables
                and candidate.risks == base.risks
                and candidate.canonical_prompt == base.canonical_prompt
                and candidate.prompt_language is base.prompt_language
            ):
                return candidate
        version = self._next_version(base.recipe_id)
        return self._persist(replace(
            base,
            version=version,
            settings=settings,
            parent_version=base.version,
            status="published",
            content_sha256="0" * 64,
        ))

    def parse_revision_draft(self, base: Krea2VisualRecipe, raw: str) -> Krea2VisualRecipe:
        value = _decode_json_object(raw)
        required = {"identity", "invariants", "variables", "risks", "canonical_prompt"}
        if set(value) != required:
            raise ValueError("recipe proposal has invalid fields")
        return replace(
            base,
            version=self._next_version(base.recipe_id),
            identity=_text(value["identity"], "identity"),
            invariants=_strings(value["invariants"], "invariants"),
            variables=_strings(value["variables"], "variables"),
            risks=_strings(value["risks"], "risks"),
            canonical_prompt=_text(value["canonical_prompt"], "canonical_prompt"),
            parent_version=base.version,
            status="draft",
            content_sha256="0" * 64,
        )

    def publish(self, proposal: Krea2VisualRecipe) -> Krea2VisualRecipe:
        return self._persist(replace(proposal, status="published"))

    def publish_new(
        self,
        draft: Krea2AssistedRecipeDraft,
        settings: Krea2BatchSettings,
    ) -> Krea2VisualRecipe:
        """Publish an explicitly approved assisted-creation draft as Batch V0.1.0."""
        if not isinstance(draft, Krea2AssistedRecipeDraft):
            raise TypeError("draft must be a Krea2AssistedRecipeDraft")
        if not isinstance(settings, Krea2BatchSettings):
            raise TypeError("settings must be Krea2BatchSettings")
        if any(recipe.recipe_id == draft.recipe_id for recipe in self.list()):
            raise ValueError(
                f"recipe_id {draft.recipe_id!r} already exists; publish a revision from Batch instead"
            )
        return self._persist(Krea2VisualRecipe(
            recipe_id=draft.recipe_id,
            version="0.1.0",
            display_name=draft.display_name,
            description=draft.description,
            identity=draft.identity,
            invariants=draft.invariants,
            variables=draft.variables,
            risks=draft.risks,
            canonical_prompt=draft.canonical_prompt,
            settings=settings,
            content_sha256="0" * 64,
            prompt_language=draft.prompt_language,
            parent_version=None,
            status="published",
        ))

    def _next_version(self, recipe_id: str) -> str:
        versions = [_version_key(recipe.version) for recipe in self.list() if recipe.recipe_id == recipe_id]
        if not versions:
            return "0.1.0"
        major, minor, patch = max(versions)
        return f"{major}.{minor}.{patch + 1}"

    def _persist(self, recipe: Krea2VisualRecipe) -> Krea2VisualRecipe:
        payload = _recipe_payload(recipe)
        digest = _payload_digest(payload)
        recipe = replace(recipe, content_sha256=digest)
        payload["content_sha256"] = digest
        directory = self.local_root / recipe.recipe_id / recipe.version
        directory.mkdir(parents=True, exist_ok=False)
        _atomic_write(directory / "recipe.json", _json_bytes(payload))
        return recipe


def _load_recipe(path: Path) -> Krea2VisualRecipe:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain an object")
    loras_raw = value.get("loras", [])
    if not isinstance(loras_raw, list):
        raise ValueError(f"{path} loras must be an array")
    loras = tuple(
        Krea2LoraSelection(
            name=_text(item.get("name"), "LoRA name"),
            strength=item.get("strength"),
        )
        for item in loras_raw
        if isinstance(item, Mapping)
    )
    recipe = Krea2VisualRecipe(
        recipe_id=_text(value.get("recipe_id"), "recipe_id"),
        version=_text(value.get("version"), "version"),
        display_name=_text(value.get("display_name"), "display_name"),
        description=_text(value.get("description"), "description"),
        identity=_text(value.get("identity"), "identity"),
        invariants=_strings(value.get("invariants"), "invariants"),
        variables=_strings(value.get("variables"), "variables"),
        risks=_strings(value.get("risks"), "risks"),
        canonical_prompt=_text(value.get("canonical_prompt"), "canonical_prompt"),
        settings=Krea2BatchSettings(
            model_name=_text(value.get("model_name"), "model_name"),
            aspect_ratio=Krea2AspectRatio(value.get("aspect_ratio")),
            megapixels=value.get("megapixels"),
            loras=loras,
        ),
        content_sha256=_text(value.get("content_sha256"), "content_sha256"),
        prompt_language=Krea2PromptLanguage(value.get("prompt_language", "en")),
        parent_version=(
            _text(value.get("parent_version"), "parent_version")
            if value.get("parent_version") is not None
            else None
        ),
        status=_text(value.get("status", "published"), "status"),
    )
    payload = dict(value)
    expected = payload.pop("content_sha256")
    if _payload_digest(payload) != expected:
        raise ValueError(f"recipe hash mismatch in {path}")
    return recipe


def _recipe_payload(recipe: Krea2VisualRecipe) -> dict[str, Any]:
    payload = {
        "recipe_id": recipe.recipe_id,
        "version": recipe.version,
        "display_name": recipe.display_name,
        "description": recipe.description,
        "identity": recipe.identity,
        "invariants": list(recipe.invariants),
        "variables": list(recipe.variables),
        "risks": list(recipe.risks),
        "canonical_prompt": recipe.canonical_prompt,
        "model_name": recipe.settings.model_name,
        "aspect_ratio": recipe.settings.aspect_ratio.value,
        "megapixels": recipe.settings.megapixels,
        "loras": [
            {"name": lora.name, "strength": lora.strength}
            for lora in recipe.settings.loras
        ],
        "parent_version": recipe.parent_version,
        "status": recipe.status,
    }
    if recipe.prompt_language is not Krea2PromptLanguage.ENGLISH:
        payload["prompt_language"] = recipe.prompt_language.value
    return payload


def recipe_document(
    *,
    recipe_id: str,
    version: str,
    display_name: str,
    description: str,
    identity: str,
    invariants: list[str],
    variables: list[str],
    risks: list[str],
    canonical_prompt: str,
    model_name: str,
    aspect_ratio: str = "9:16 (Portrait Widescreen)",
    megapixels: float = 2.1,
    loras: list[dict[str, object]] | None = None,
    prompt_language: Krea2PromptLanguage = Krea2PromptLanguage.ENGLISH,
) -> dict[str, Any]:
    """Build a hash-complete document for shipped recipe authoring/tests."""
    payload = {
        "recipe_id": recipe_id,
        "version": version,
        "display_name": display_name,
        "description": description,
        "identity": identity,
        "invariants": invariants,
        "variables": variables,
        "risks": risks,
        "canonical_prompt": canonical_prompt,
        "model_name": model_name,
        "aspect_ratio": aspect_ratio,
        "megapixels": megapixels,
        "loras": loras or [],
        "parent_version": None,
        "status": "published",
    }
    if prompt_language is not Krea2PromptLanguage.ENGLISH:
        payload["prompt_language"] = prompt_language.value
    return {**payload, "content_sha256": _payload_digest(payload)}


def _prompt_language_label(language: Krea2PromptLanguage) -> str:
    if language is Krea2PromptLanguage.CHINESE_SIMPLIFIED:
        return "Simplified Chinese (简体中文)"
    return "English"


def _decode_json_object(raw: str) -> Mapping[str, Any]:
    text = _text(raw, "model response")
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or not lines[-1].strip() == "```":
            raise ValueError("JSON fence is not closed")
        text = "\n".join(lines[1:-1])
        if text.lstrip().startswith("json\n"):
            text = text.lstrip()[5:]
    value = json.loads(text)
    if not isinstance(value, Mapping):
        raise ValueError("model response must be a JSON object")
    return value


def _project_prompt_ratio(
    prompt: str,
    target: Krea2AspectRatio,
    *,
    prefix_if_missing: bool = True,
) -> str:
    """Replace only the leading format declaration; keep the proven skeleton."""
    width, height = target.dimensions
    orientation = "Vertical" if height > width else "Landscape" if width > height else "Square"
    ratios = "|".join(
        re.escape(value.value.split(" ", 1)[0]).replace(r"\:", r"\s*:\s*")
        for value in Krea2AspectRatio
    )
    pattern = re.compile(rf"\b(?:vertical|landscape|square)?\s*(?:{ratios})\b", re.IGNORECASE)
    projected, count = pattern.subn(f"{orientation} {width}:{height}", prompt, count=1)
    if count:
        return projected
    return f"{orientation} {width}:{height}. {prompt}" if prefix_if_missing else prompt


def _strings(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty array")
    return tuple(_text(item, f"{label} item") for item in value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    return value.strip()


def _payload_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _version_key(value: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(value)
    if match is None:
        raise ValueError(f"invalid recipe version {value!r}")
    return tuple(int(part) for part in match.groups())


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def _atomic_write(path: Path, content: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
