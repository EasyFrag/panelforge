"""Pure contracts for text-to-storyboard prompt generation."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping


SUPPORTED_STORYBOARD_PANEL_COUNTS = (2, 4, 6, 9)
_PORTRAIT_FRAMING = re.compile(
    r"\b(?:full[ -]?body|three[ -]?quarter|3\s*/\s*4)\b",
    re.IGNORECASE,
)
_FORBIDDEN_FRAMING = re.compile(r"\b(?:wide|landscape|square)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class StoryboardLayout:
    """Application-owned geometry for a page of vertical 2:3 panels."""

    panel_count: int
    columns: int
    rows: int
    page_aspect_ratio: str
    page_orientation: str

    def __post_init__(self) -> None:
        if self.panel_count not in SUPPORTED_STORYBOARD_PANEL_COUNTS:
            raise ValueError("panel_count must be one of 2, 4, 6, or 9")
        if isinstance(self.columns, bool) or not isinstance(self.columns, int):
            raise TypeError("columns must be an integer")
        if isinstance(self.rows, bool) or not isinstance(self.rows, int):
            raise TypeError("rows must be an integer")
        if self.columns * self.rows != self.panel_count:
            raise ValueError("columns multiplied by rows must equal panel_count")
        if self.page_aspect_ratio not in {"4:3", "2:3", "1:1"}:
            raise ValueError("unsupported storyboard page aspect ratio")
        if self.page_orientation not in {"landscape", "portrait", "square"}:
            raise ValueError("unsupported storyboard page orientation")

    @property
    def grid_label(self) -> str:
        column_word = "column" if self.columns == 1 else "columns"
        row_word = "row" if self.rows == 1 else "rows"
        return f"{self.columns} {column_word} × {self.rows} {row_word}"

    def row_and_column(self, panel_number: int) -> tuple[int, int]:
        if (
            isinstance(panel_number, bool)
            or not isinstance(panel_number, int)
            or not 1 <= panel_number <= self.panel_count
        ):
            raise ValueError("panel_number is outside the storyboard layout")
        zero_based = panel_number - 1
        return zero_based // self.columns + 1, zero_based % self.columns + 1

    def position(self, panel_number: int) -> str:
        row, column = self.row_and_column(panel_number)
        if self.rows == 1:
            return ("left", "right")[column - 1]
        row_label = {
            1: "top",
            self.rows: "bottom",
        }.get(row, "middle")
        column_label = {
            1: "left",
            self.columns: "right",
        }.get(column, "middle")
        if self.rows == self.columns == 3 and row == column == 2:
            return "center"
        return f"{row_label}-{column_label}"


_LAYOUTS = {
    2: StoryboardLayout(2, 2, 1, "4:3", "landscape"),
    4: StoryboardLayout(4, 2, 2, "2:3", "portrait"),
    6: StoryboardLayout(6, 3, 2, "1:1", "square"),
    9: StoryboardLayout(9, 3, 3, "2:3", "portrait"),
}


def storyboard_layout(panel_count: int) -> StoryboardLayout:
    """Return the one V1 page geometry compatible with 2:3 panel cells."""

    if isinstance(panel_count, bool) or not isinstance(panel_count, int):
        raise TypeError("panel_count must be an integer")
    try:
        return _LAYOUTS[panel_count]
    except KeyError as error:
        raise ValueError("panel_count must be one of 2, 4, 6, or 9") from error


@dataclass(frozen=True, slots=True)
class StoryboardCharacter:
    label: str
    identity_lock: str
    wardrobe_lock: str
    allowed_progression: str

    def __post_init__(self) -> None:
        for field_name in (
            "label",
            "identity_lock",
            "wardrobe_lock",
            "allowed_progression",
        ):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True, slots=True)
class StoryboardEnvironment:
    location_lock: str
    lighting_lock: str
    layout_lock: str
    props_lock: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("location_lock", "lighting_lock", "layout_lock"):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "props_lock",
            _text_tuple(self.props_lock, "props_lock", allow_empty=True),
        )


@dataclass(frozen=True, slots=True)
class StoryboardPanel:
    present_characters: tuple[str, ...]
    framing: str
    camera_angle: str
    visual_beat: str
    emotional_beat: str
    continuity_from_previous: str | None
    visible_anchors: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "present_characters",
            _text_tuple(
                self.present_characters,
                "present_characters",
                allow_empty=True,
            ),
        )
        for field_name in (
            "framing",
            "camera_angle",
            "visual_beat",
            "emotional_beat",
        ):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )
        if _FORBIDDEN_FRAMING.search(self.framing) or not _PORTRAIT_FRAMING.search(
            self.framing
        ):
            raise ValueError(
                "framing must be full-body or three-quarter and must not be wide, "
                "landscape, or square"
            )
        if self.continuity_from_previous is not None:
            object.__setattr__(
                self,
                "continuity_from_previous",
                _text(self.continuity_from_previous, "continuity_from_previous"),
            )
        object.__setattr__(
            self,
            "visible_anchors",
            _text_tuple(self.visible_anchors, "visible_anchors"),
        )


@dataclass(frozen=True, slots=True)
class StoryboardSpec:
    """LLM-authored semantics; all page geometry remains application-owned."""

    sequence_context: str
    avoid_repeats: tuple[str, ...]
    characters: tuple[StoryboardCharacter, ...]
    environment: StoryboardEnvironment
    panels: tuple[StoryboardPanel, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "sequence_context",
            _text(self.sequence_context, "sequence_context"),
        )
        object.__setattr__(
            self,
            "avoid_repeats",
            _text_tuple(self.avoid_repeats, "avoid_repeats", allow_empty=True),
        )
        if not isinstance(self.characters, tuple) or not self.characters:
            raise ValueError("characters must be a non-empty tuple")
        if any(not isinstance(item, StoryboardCharacter) for item in self.characters):
            raise TypeError("characters must contain StoryboardCharacter values")
        labels = tuple(character.label for character in self.characters)
        if len({label.casefold() for label in labels}) != len(labels):
            raise ValueError("character labels must be unique")
        if not isinstance(self.environment, StoryboardEnvironment):
            raise TypeError("environment must be a StoryboardEnvironment")
        if not isinstance(self.panels, tuple):
            raise TypeError("panels must be a tuple")
        storyboard_layout(len(self.panels))
        if any(not isinstance(item, StoryboardPanel) for item in self.panels):
            raise TypeError("panels must contain StoryboardPanel values")
        if self.panels[0].continuity_from_previous is not None:
            raise ValueError("Panel 1 continuity_from_previous must be null")
        known_labels = set(labels)
        for panel_number, panel in enumerate(self.panels, 1):
            unknown = set(panel.present_characters) - known_labels
            if unknown:
                raise ValueError(
                    f"Panel {panel_number} references unknown characters: "
                    + ", ".join(sorted(unknown))
                )
            if panel_number > 1 and panel.continuity_from_previous is None:
                raise ValueError(
                    f"Panel {panel_number} continuity_from_previous must be provided"
                )

    @property
    def panel_count(self) -> int:
        return len(self.panels)

    def to_payload(self) -> dict[str, object]:
        return {
            "sequence_context": self.sequence_context,
            "avoid_repeats": list(self.avoid_repeats),
            "characters": [
                {
                    "label": character.label,
                    "identity_lock": character.identity_lock,
                    "wardrobe_lock": character.wardrobe_lock,
                    "allowed_progression": character.allowed_progression,
                }
                for character in self.characters
            ],
            "environment": {
                "location_lock": self.environment.location_lock,
                "lighting_lock": self.environment.lighting_lock,
                "layout_lock": self.environment.layout_lock,
                "props_lock": list(self.environment.props_lock),
            },
            "panels": [
                {
                    "present_characters": list(panel.present_characters),
                    "framing": panel.framing,
                    "camera_angle": panel.camera_angle,
                    "visual_beat": panel.visual_beat,
                    "emotional_beat": panel.emotional_beat,
                    "continuity_from_previous": panel.continuity_from_previous,
                    "visible_anchors": list(panel.visible_anchors),
                }
                for panel in self.panels
            ],
        }

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, object],
        *,
        expected_panel_count: int | None = None,
    ) -> StoryboardSpec:
        """Build the strict domain contract from one decoded JSON object."""

        data = _mapping(payload, "storyboard spec")
        _exact_keys(
            data,
            {"sequence_context", "avoid_repeats", "characters", "environment", "panels"},
            "storyboard spec",
        )
        raw_characters = _list(data["characters"], "characters", allow_empty=False)
        characters: list[StoryboardCharacter] = []
        for index, raw_character in enumerate(raw_characters, 1):
            character = _mapping(raw_character, f"character {index}")
            _exact_keys(
                character,
                {"label", "identity_lock", "wardrobe_lock", "allowed_progression"},
                f"character {index}",
            )
            characters.append(StoryboardCharacter(**character))

        environment = _mapping(data["environment"], "environment")
        _exact_keys(
            environment,
            {"location_lock", "lighting_lock", "layout_lock", "props_lock"},
            "environment",
        )
        parsed_environment = StoryboardEnvironment(
            location_lock=environment["location_lock"],
            lighting_lock=environment["lighting_lock"],
            layout_lock=environment["layout_lock"],
            props_lock=_text_tuple_from_json(environment["props_lock"], "props_lock", True),
        )

        raw_panels = _list(data["panels"], "panels", allow_empty=False)
        panels: list[StoryboardPanel] = []
        for index, raw_panel in enumerate(raw_panels, 1):
            panel = _mapping(raw_panel, f"panel {index}")
            _exact_keys(
                panel,
                {
                    "present_characters",
                    "framing",
                    "camera_angle",
                    "visual_beat",
                    "emotional_beat",
                    "continuity_from_previous",
                    "visible_anchors",
                },
                f"panel {index}",
            )
            continuity = panel["continuity_from_previous"]
            if continuity is not None and not isinstance(continuity, str):
                raise TypeError("continuity_from_previous must be a string or null")
            panels.append(
                StoryboardPanel(
                    present_characters=_text_tuple_from_json(
                        panel["present_characters"],
                        "present_characters",
                        True,
                    ),
                    framing=panel["framing"],
                    camera_angle=panel["camera_angle"],
                    visual_beat=panel["visual_beat"],
                    emotional_beat=panel["emotional_beat"],
                    continuity_from_previous=continuity,
                    visible_anchors=_text_tuple_from_json(
                        panel["visible_anchors"],
                        "visible_anchors",
                        False,
                    ),
                )
            )
        if expected_panel_count is not None:
            storyboard_layout(expected_panel_count)
            if len(panels) != expected_panel_count:
                raise ValueError(
                    f"panels must contain exactly {expected_panel_count} items"
                )
        return cls(
            sequence_context=data["sequence_context"],
            avoid_repeats=_text_tuple_from_json(
                data["avoid_repeats"],
                "avoid_repeats",
                True,
            ),
            characters=tuple(characters),
            environment=parsed_environment,
            panels=tuple(panels),
        )


def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    result = " ".join(value.split())
    if not result:
        raise ValueError(f"{name} must not be empty")
    return result


def _text_tuple(
    value: object,
    name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    if not value and not allow_empty:
        raise ValueError(f"{name} must not be empty")
    result = tuple(_text(item, f"{name} item") for item in value)
    if len(result) != len(set(result)):
        raise ValueError(f"{name} must not contain duplicates")
    return result


def _text_tuple_from_json(
    value: object,
    name: str,
    allow_empty: bool,
) -> tuple[str, ...]:
    raw = _list(value, name, allow_empty=allow_empty)
    return _text_tuple(tuple(raw), name, allow_empty=allow_empty)


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise TypeError(f"{name} keys must be strings")
    return value


def _list(value: object, name: str, *, allow_empty: bool) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be an array")
    if not value and not allow_empty:
        raise ValueError(f"{name} must not be empty")
    return value


def _exact_keys(value: Mapping[str, object], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} has invalid fields")


__all__ = [
    "SUPPORTED_STORYBOARD_PANEL_COUNTS",
    "StoryboardCharacter",
    "StoryboardEnvironment",
    "StoryboardLayout",
    "StoryboardPanel",
    "StoryboardSpec",
    "storyboard_layout",
]
