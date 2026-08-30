"""Pure contracts for conversational social-copy projects."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum


class SocialLanguage(StrEnum):
    ENGLISH = "en"
    FRENCH = "fr"


class SocialTurnRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class SocialVariant:
    angle: str
    hook: str
    caption: str
    hashtags: tuple[str, ...]
    emojis: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.angle, "variant angle", 120)
        _text(self.hook, "variant hook", 300)
        _text(self.caption, "variant caption", 5_000)
        _strings(self.hashtags, "variant hashtags", maximum=30)
        _strings(self.emojis, "variant emojis", maximum=12)


@dataclass(frozen=True, slots=True)
class SocialTurn:
    turn_id: str
    role: SocialTurnRole
    content: str
    variants: tuple[SocialVariant, ...] = ()

    def __post_init__(self) -> None:
        _text(self.turn_id, "turn_id", 128)
        if not isinstance(self.role, SocialTurnRole):
            raise TypeError("role must be a SocialTurnRole")
        _text(self.content, "turn content", 20_000)
        if not isinstance(self.variants, tuple) or any(
            not isinstance(value, SocialVariant) for value in self.variants
        ):
            raise TypeError("variants must contain SocialVariant values")
        if self.role is SocialTurnRole.USER and self.variants:
            raise ValueError("user turns cannot contain variants")
        if self.role is SocialTurnRole.ASSISTANT and not self.variants:
            raise ValueError("assistant turns require variants")


@dataclass(frozen=True, slots=True)
class SocialChannelProfile:
    profile_id: str
    name: str
    language: SocialLanguage = SocialLanguage.ENGLISH
    mood: str = ""
    vibe: str = ""
    example: str = ""
    instructions: str = ""

    def __post_init__(self) -> None:
        _text(self.profile_id, "profile_id", 128)
        _text(self.name, "profile name", 120)
        if not isinstance(self.language, SocialLanguage):
            raise TypeError("language must be a SocialLanguage")
        _optional_text(self.mood, "profile mood", 4_000)
        _optional_text(self.vibe, "profile vibe", 4_000)
        _optional_text(self.example, "profile example", 12_000)
        _optional_text(self.instructions, "profile instructions", 8_000)


@dataclass(frozen=True, slots=True)
class SocialProject:
    project_id: str
    name: str
    model_id: str
    language: SocialLanguage
    variant_count: int
    video_asset_id: str
    video_filename: str
    keyframe_asset_ids: tuple[str, ...]
    mood: str = ""
    vibe: str = ""
    example: str = ""
    instructions: str = ""
    channel_profile_id: str | None = None
    source_prompt: str | None = None
    turns: tuple[SocialTurn, ...] = ()

    def __post_init__(self) -> None:
        for value, label, maximum in (
            (self.project_id, "project_id", 128),
            (self.name, "project name", 120),
            (self.model_id, "model_id", 300),
            (self.video_asset_id, "video_asset_id", 128),
            (self.video_filename, "video_filename", 240),
        ):
            _text(value, label, maximum)
        if not isinstance(self.language, SocialLanguage):
            raise TypeError("language must be a SocialLanguage")
        if (
            isinstance(self.variant_count, bool)
            or not isinstance(self.variant_count, int)
            or not 1 <= self.variant_count <= 8
        ):
            raise ValueError("variant_count must be between 1 and 8")
        if not isinstance(self.keyframe_asset_ids, tuple):
            raise TypeError("keyframe_asset_ids must be a tuple")
        if len(self.keyframe_asset_ids) != 4:
            raise ValueError("Social Lab requires exactly four keyframes")
        if len(set(self.keyframe_asset_ids)) != 4:
            raise ValueError("Social Lab keyframes must be distinct assets")
        for asset_id in self.keyframe_asset_ids:
            _text(asset_id, "keyframe asset_id", 128)
        _optional_text(self.mood, "project mood", 4_000)
        _optional_text(self.vibe, "project vibe", 4_000)
        _optional_text(self.example, "project example", 12_000)
        _optional_text(self.instructions, "project instructions", 8_000)
        if self.channel_profile_id is not None:
            _text(self.channel_profile_id, "channel_profile_id", 128)
        if self.source_prompt is not None:
            _text(self.source_prompt, "source_prompt", 50_000)
        if not isinstance(self.turns, tuple) or any(
            not isinstance(value, SocialTurn) for value in self.turns
        ):
            raise TypeError("turns must contain SocialTurn values")
        if len({value.turn_id for value in self.turns}) != len(self.turns):
            raise ValueError("turn IDs must be unique")
    @property
    def latest_variants(self) -> tuple[SocialVariant, ...]:
        for turn in reversed(self.turns):
            if turn.role is SocialTurnRole.ASSISTANT:
                return turn.variants
        return ()

    def add_turn(self, turn: SocialTurn) -> SocialProject:
        if any(value.turn_id == turn.turn_id for value in self.turns):
            raise ValueError("turn already exists")
        return replace(self, turns=(*self.turns, turn))

    def with_editorial(
        self,
        *,
        model_id: str | None = None,
        language: SocialLanguage | None = None,
        variant_count: int | None = None,
        mood: str | None = None,
        vibe: str | None = None,
        example: str | None = None,
        instructions: str | None = None,
        channel_profile_id: str | None = None,
        update_profile: bool = False,
    ) -> SocialProject:
        values = {
            "model_id": self.model_id if model_id is None else model_id,
            "language": self.language if language is None else language,
            "variant_count": self.variant_count if variant_count is None else variant_count,
            "mood": self.mood if mood is None else mood,
            "vibe": self.vibe if vibe is None else vibe,
            "example": self.example if example is None else example,
            "instructions": self.instructions if instructions is None else instructions,
        }
        if update_profile:
            values["channel_profile_id"] = channel_profile_id
        return replace(self, **values)


def _text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if not value.strip():
        raise ValueError(f"{label} must not be empty")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return value


def _optional_text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return value


def _strings(values: object, label: str, *, maximum: int) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{label} must be a tuple")
    if len(values) > maximum:
        raise ValueError(f"{label} contains too many values")
    for value in values:
        _text(value, f"{label} item", 300)


__all__ = [
    "SocialChannelProfile",
    "SocialLanguage",
    "SocialProject",
    "SocialTurn",
    "SocialTurnRole",
    "SocialVariant",
]
