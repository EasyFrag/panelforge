"""Strict loader and deterministic compiler for storyboard prompt recipes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Mapping

from panelforge.domain.storyboard import (
    SUPPORTED_STORYBOARD_PANEL_COUNTS,
    StoryboardSpec,
    storyboard_layout,
)


_COUNT_WORDS = {2: "TWO", 4: "FOUR", 6: "SIX", 9: "NINE"}
_NUMBER_WORDS = {1: "ONE", 2: "TWO", 3: "THREE"}
_TOKEN = re.compile(r"\{\{([a-z_]+)\}\}")
_SEMANTIC_VERSION = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?P<suffix>[-+][0-9A-Za-z.-]+)?$"
)


@dataclass(frozen=True, slots=True)
class StoryboardRecipe:
    schema_version: int
    recipe_id: str
    version: str
    display_name: str
    description: str
    target_model_family: str
    output_contract: str
    panel_counts: tuple[int, ...]
    sources: tuple[str, ...]
    system_prompt_template: str
    user_prompt_template: str
    final_prompt_template: str
    template_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported storyboard recipe schema")
        for name in (
            "recipe_id",
            "version",
            "display_name",
            "description",
            "target_model_family",
            "output_contract",
            "system_prompt_template",
            "user_prompt_template",
            "final_prompt_template",
        ):
            _text(getattr(self, name), name)
        if self.panel_counts != SUPPORTED_STORYBOARD_PANEL_COUNTS:
            raise ValueError("V1 storyboard recipes must support 2, 4, 6, and 9 panels")
        if not isinstance(self.sources, tuple) or not self.sources:
            raise ValueError("sources must be a non-empty tuple")
        for source in self.sources:
            _text(source, "source")
        if not re.fullmatch(r"[0-9a-f]{64}", self.template_sha256):
            raise ValueError("template_sha256 must be a lowercase SHA-256 digest")
        _validate_template_tokens(
            self.system_prompt_template,
            {"panel_count", "schema"},
            "system prompt",
        )
        _validate_template_tokens(
            self.user_prompt_template,
            {
                "intention",
                "panel_count",
                "columns",
                "rows",
                "page_aspect_ratio",
                "page_orientation",
            },
            "user prompt",
        )
        _validate_template_tokens(
            self.final_prompt_template,
            {
                "page_orientation",
                "page_aspect_ratio",
                "columns_word",
                "rows_word",
                "rows_suffix",
                "count_word",
                "sequence_context",
                "continuation_block",
                "characters_block",
                "environment_block",
                "panels_block",
            },
            "final prompt",
        )

    def build_request_prompts(
        self,
        intention: str,
        panel_count: int,
    ) -> tuple[str, str]:
        """Build the one LLM request while keeping geometry application-owned."""

        source = _text(intention, "intention")
        layout = storyboard_layout(panel_count)
        system = _render(
            self.system_prompt_template,
            {
                "panel_count": str(panel_count),
                "schema": json.dumps(
                    _storyboard_schema(panel_count),
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        )
        user = _render(
            self.user_prompt_template,
            {
                "intention": source,
                "panel_count": str(panel_count),
                "columns": str(layout.columns),
                "rows": str(layout.rows),
                "page_aspect_ratio": layout.page_aspect_ratio,
                "page_orientation": layout.page_orientation,
            },
        )
        return system, user

    def parse_spec(self, raw_response: str, panel_count: int) -> StoryboardSpec:
        """Accept one raw or fenced JSON object; never repair invalid content."""

        storyboard_layout(panel_count)
        decoded = _json_object(raw_response)
        try:
            return StoryboardSpec.from_payload(
                decoded,
                expected_panel_count=panel_count,
            )
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid storyboard spec: {error}") from error

    def compile_prompt(
        self,
        spec: StoryboardSpec,
        panel_count: int,
    ) -> str:
        """Compile the proven fixed KREA2 skeleton around authored variables."""

        if not isinstance(spec, StoryboardSpec):
            raise TypeError("spec must be a StoryboardSpec")
        layout = storyboard_layout(panel_count)
        if spec.panel_count != panel_count:
            raise ValueError(f"spec must contain exactly {panel_count} panels")

        continuation = ""
        if spec.avoid_repeats:
            continuation = (
                "CONTINUATION: Do NOT repeat "
                + "; ".join(_without_terminal(item) for item in spec.avoid_repeats)
                + "."
            )
        characters = "\n".join(
            (
                f"{character.label}, never change: "
                f"{_sentence(character.identity_lock)} "
                f"Wardrobe lock: {_sentence(character.wardrobe_lock)} "
                "Clothes and appearance may change only as follows: "
                f"{_sentence(character.allowed_progression)}"
            )
            for character in spec.characters
        )
        props = (
            "; ".join(_without_terminal(item) for item in spec.environment.props_lock)
            if spec.environment.props_lock
            else "No named persistent props"
        )
        environment = (
            f"Location: {_sentence(spec.environment.location_lock)} "
            f"Layout: {_sentence(spec.environment.layout_lock)} "
            f"Lighting: {_sentence(spec.environment.lighting_lock)} "
            f"Persistent props: {props}."
        )
        panel_blocks: list[str] = []
        for panel_number, panel in enumerate(spec.panels, 1):
            row, column = layout.row_and_column(panel_number)
            details = [
                f"Present characters: {', '.join(panel.present_characters) or 'none'}.",
                _sentence(panel.visual_beat),
                f"Emotional beat: {_sentence(panel.emotional_beat)}",
            ]
            if panel.continuity_from_previous is not None:
                details.append(
                    f"Continuity from Panel {panel_number - 1}: "
                    f"{_sentence(panel.continuity_from_previous)}"
                )
            details.append(
                "Visible continuity anchors: "
                + "; ".join(_without_terminal(item) for item in panel.visible_anchors)
                + "."
            )
            panel_blocks.append(
                f"Panel {panel_number}, row {row}, column {column}, "
                f"{layout.position(panel_number)}, 2:3 vertical: "
                f"{_without_terminal(panel.framing)}, "
                f"{_without_terminal(panel.camera_angle)}; "
                + " ".join(details)
            )

        rendered = _render(
            self.final_prompt_template,
            {
                "page_orientation": layout.page_orientation,
                "page_aspect_ratio": layout.page_aspect_ratio,
                "columns_word": _NUMBER_WORDS[layout.columns],
                "rows_word": _NUMBER_WORDS[layout.rows],
                "rows_suffix": "" if layout.rows == 1 else "S",
                "count_word": _COUNT_WORDS[panel_count],
                "sequence_context": _sentence(spec.sequence_context),
                "continuation_block": continuation,
                "characters_block": characters,
                "environment_block": environment,
                "panels_block": "\n\n".join(panel_blocks),
            },
        )
        return re.sub(r"\n{3,}", "\n\n", rendered).strip()

    def warnings_for_spec(
        self,
        spec: StoryboardSpec,
        panel_count: int,
    ) -> tuple[str, ...]:
        """Return conservative quality warnings without blocking compilation."""

        if not isinstance(spec, StoryboardSpec):
            raise TypeError("spec must be a StoryboardSpec")
        storyboard_layout(panel_count)
        if spec.panel_count != panel_count:
            raise ValueError(f"spec must contain exactly {panel_count} panels")
        warnings: list[str] = []
        if len(spec.characters) > 4:
            warnings.append(
                "La distribution contient plus de quatre personnages ; "
                "la cohérence des visages peut diminuer."
            )
        for number, (previous, current) in enumerate(
            zip(spec.panels, spec.panels[1:]),
            2,
        ):
            if (
                previous.framing.casefold() == current.framing.casefold()
                and previous.camera_angle.casefold() == current.camera_angle.casefold()
            ):
                warnings.append(
                    f"Les panels {number - 1} et {number} répètent le même "
                    "cadrage et le même angle."
                )
            if previous.visual_beat.casefold() == current.visual_beat.casefold():
                warnings.append(
                    f"Les panels {number - 1} et {number} répètent le même "
                    "temps visuel."
                )
        for number, panel in enumerate(spec.panels, 1):
            if len(panel.visual_beat.split()) > 80:
                warnings.append(
                    f"Le panel {number} contient une description très dense ; "
                    "une action principale plus courte sera plus lisible."
                )
        return tuple(warnings)


class LocalStoryboardRecipeCatalog:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def list(self) -> tuple[StoryboardRecipe, ...]:
        if not self._root.is_dir():
            return ()
        recipes = [
            self._load(directory)
            for directory in self._root.glob("*/*")
            if directory.is_dir() and (directory / "manifest.json").is_file()
        ]
        return tuple(
            sorted(
                recipes,
                key=lambda item: (item.recipe_id, _semantic_version_key(item.version)),
            )
        )

    def get(self, recipe_id: str, version: str) -> StoryboardRecipe:
        for recipe in self.list():
            if recipe.recipe_id == recipe_id and recipe.version == version:
                return recipe
        raise KeyError((recipe_id, version))

    def _load(self, directory: Path) -> StoryboardRecipe:
        manifest_path = directory / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid storyboard recipe manifest: {manifest_path}") from error
        if not isinstance(manifest, dict):
            raise ValueError(f"invalid storyboard recipe fields: {manifest_path}")
        expected = {
            "schema_version",
            "recipe_id",
            "version",
            "display_name",
            "description",
            "target_model_family",
            "output_contract",
            "panel_counts",
            "sources",
            "templates",
        }
        if set(manifest) != expected:
            raise ValueError(f"invalid storyboard recipe fields: {manifest_path}")
        recipe_id = _text(manifest["recipe_id"], "recipe_id")
        version = _text(manifest["version"], "version")
        if directory.parent.name != recipe_id or directory.name != version:
            raise ValueError(
                f"storyboard recipe identity does not match its path: {manifest_path}"
            )
        raw_templates = manifest["templates"]
        if not isinstance(raw_templates, dict) or set(raw_templates) != {
            "system",
            "user",
            "final_prompt",
        }:
            raise ValueError(f"invalid storyboard recipe templates: {manifest_path}")

        def load_template(key: str) -> str:
            filename = _text(raw_templates[key], f"template {key}")
            path = (directory / filename).resolve()
            if directory.resolve() not in path.parents or not path.is_file():
                raise ValueError(f"invalid storyboard recipe template path: {filename}")
            return _text(path.read_text(encoding="utf-8"), f"template {key}")

        system = load_template("system")
        user = load_template("user")
        final_prompt = load_template("final_prompt")
        template_sha256 = hashlib.sha256(
            "\0".join((system, user, final_prompt)).encode("utf-8")
        ).hexdigest()
        raw_counts = manifest["panel_counts"]
        if not isinstance(raw_counts, list) or any(
            isinstance(item, bool) or not isinstance(item, int) for item in raw_counts
        ):
            raise ValueError(f"invalid storyboard panel counts: {manifest_path}")
        raw_sources = manifest["sources"]
        if not isinstance(raw_sources, list):
            raise ValueError(f"invalid storyboard recipe sources: {manifest_path}")
        return StoryboardRecipe(
            schema_version=manifest["schema_version"],
            recipe_id=recipe_id,
            version=version,
            display_name=manifest["display_name"],
            description=manifest["description"],
            target_model_family=manifest["target_model_family"],
            output_contract=manifest["output_contract"],
            panel_counts=tuple(raw_counts),
            sources=tuple(raw_sources),
            system_prompt_template=system,
            user_prompt_template=user,
            final_prompt_template=final_prompt,
            template_sha256=template_sha256,
        )


def _storyboard_schema(panel_count: int) -> dict[str, object]:
    text = {"type": "string", "minLength": 1}
    text_array = {"type": "array", "items": text, "uniqueItems": True}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "sequence_context",
            "avoid_repeats",
            "characters",
            "environment",
            "panels",
        ],
        "properties": {
            "sequence_context": text,
            "avoid_repeats": text_array,
            "characters": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "label",
                        "identity_lock",
                        "wardrobe_lock",
                        "allowed_progression",
                    ],
                    "properties": {
                        "label": text,
                        "identity_lock": text,
                        "wardrobe_lock": text,
                        "allowed_progression": text,
                    },
                },
            },
            "environment": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "location_lock",
                    "lighting_lock",
                    "layout_lock",
                    "props_lock",
                ],
                "properties": {
                    "location_lock": text,
                    "lighting_lock": text,
                    "layout_lock": text,
                    "props_lock": text_array,
                },
            },
            "panels": {
                "type": "array",
                "minItems": panel_count,
                "maxItems": panel_count,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "present_characters",
                        "framing",
                        "camera_angle",
                        "visual_beat",
                        "emotional_beat",
                        "continuity_from_previous",
                        "visible_anchors",
                    ],
                    "properties": {
                        "present_characters": text_array,
                        "framing": text,
                        "camera_angle": text,
                        "visual_beat": text,
                        "emotional_beat": text,
                        "continuity_from_previous": {
                            "anyOf": [text, {"type": "null"}]
                        },
                        "visible_anchors": {
                            "type": "array",
                            "minItems": 1,
                            "items": text,
                            "uniqueItems": True,
                        },
                    },
                },
            },
        },
    }


def _json_object(content: str) -> dict[str, object]:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("storyboard spec must not be empty")
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise ValueError("invalid storyboard JSON fence")
        if lines[0].strip().lower() not in {"```", "```json"}:
            raise ValueError("invalid storyboard JSON fence")
        value = "\n".join(lines[1:-1]).strip()
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid storyboard spec JSON: {error}") from error
    if not isinstance(decoded, dict):
        raise ValueError("storyboard spec must be one JSON object")
    return decoded


def _render(template: str, values: Mapping[str, str]) -> str:
    expected = set(_TOKEN.findall(template))
    if expected != set(values):
        raise ValueError("storyboard template values do not match its tokens")
    return _TOKEN.sub(lambda match: values[match.group(1)], template)


def _validate_template_tokens(template: str, expected: set[str], name: str) -> None:
    actual = set(_TOKEN.findall(template))
    if actual != expected:
        raise ValueError(f"{name} has invalid template tokens")


def _sentence(value: str) -> str:
    result = value.strip()
    return result if result.endswith((".", "!", "?")) else result + "."


def _without_terminal(value: str) -> str:
    return value.strip().rstrip(".!?").strip()


def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    result = value.strip()
    if not result:
        raise ValueError(f"{name} must not be empty")
    return result


def _semantic_version_key(version: str) -> tuple[int, int, int, int, str]:
    match = _SEMANTIC_VERSION.fullmatch(version)
    if match is None:
        return (1, 0, 0, 0, version)
    suffix = match.group("suffix") or ""
    return (
        0,
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        suffix,
    )


__all__ = ["LocalStoryboardRecipeCatalog", "StoryboardRecipe"]
