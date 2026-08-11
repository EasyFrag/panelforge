"""Pure, immutable vocabulary for the MiniMax H3 prompt protocol."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re


class H3CameraMotion(StrEnum):
    ZOOM_IN = "zoom.in"
    ZOOM_OUT = "zoom.out"
    PUSH_IN = "push.in"
    PULL_OUT = "pull.out"
    PAN_LEFT = "pan.left"
    PAN_RIGHT = "pan.right"
    TRUCK_LEFT = "truck.left"
    TRUCK_RIGHT = "truck.right"
    TILT_UP = "tilt.up"
    TILT_DOWN = "tilt.down"
    PEDESTAL_UP = "pedestal.up"
    PEDESTAL_DOWN = "pedestal.down"
    ARC_SHOT = "arc_shot"
    TRACKING_SHOT = "tracking_shot"
    STATIC_SHOT = "static_shot"
    SHAKE_SLIGHTLY = "shake.slightly"
    SHAKE_STRONGLY = "shake.strongly"
    POV = "pov"
    ROLL_CLOCKWISE = "roll.clockwise"
    ROLL_COUNTERCLOCKWISE = "roll.counterclockwise"


class H3CameraAmplitude(StrEnum):
    SMALL = "small"
    LARGE = "large"


class H3CameraSpeed(StrEnum):
    SLOW = "slow"
    FAST = "fast"


class H3TaskType(StrEnum):
    KEYFRAME_COMPLETION = "keyframe completion"
    REFERENCE_GENERATION = "reference generation"
    VIDEO_EDITING = "video editing"
    VIDEO_CONTINUATION = "video continuation"
    AUDIO_REUSE = "audio reuse"
    AUDIO_REFERENCE = "audio reference"


class H3VisualRetention(StrEnum):
    FULLY_PRESERVED = "fully_preserved"
    PARTIALLY_PRESERVED = "partially_preserved"
    ATTRIBUTE_TRANSFER = "attribute_transfer"
    WEAK_REFERENCE = "weak_reference"


class H3AudioRetention(StrEnum):
    FULLY_COPY = "fully_copy"
    PARTIALLY_COPY = "partially_copy"
    REFERENCE = "reference"
    WEAK_REFERENCE = "weak_reference"


class H3MediaKind(StrEnum):
    PICTURE = "Picture"
    SUBJECT = "Subject"
    VIDEO = "Video"
    AUDIO = "Audio"


_MOVEMENTS_WITH_BUILT_IN_OR_NO_DYNAMICS = frozenset(
    {
        H3CameraMotion.STATIC_SHOT,
        H3CameraMotion.SHAKE_SLIGHTLY,
        H3CameraMotion.SHAKE_STRONGLY,
        H3CameraMotion.POV,
    }
)
_MOVEMENTS_WITHOUT_TARGET = frozenset(
    {
        H3CameraMotion.SHAKE_SLIGHTLY,
        H3CameraMotion.SHAKE_STRONGLY,
        H3CameraMotion.POV,
    }
)
_DIRECTIVE_ID = re.compile(r"camera_[1-9]\d{0,2}")
_CAMERA_TERMS = re.compile(
    r"(?i)\b(?:camera|zoom(?:s|ed|ing)?|push(?:es|ed|ing)?|"
    r"pull(?:s|ed|ing)?|pan(?:s|ned|ning)?|truck(?:s|ed|ing)?|"
    r"tilt(?:s|ed|ing)?|pedestal(?:s|ed|ing)?|arc(?:s|ed|ing)?|"
    r"track(?:s|ed|ing)?|shake(?:s|n|ing)?|pov|point[- ]of[- ]view|"
    r"roll(?:s|ed|ing)?|doll(?:y|ies|ied|ying)|orbit(?:s|ed|ing)?|"
    r"crane(?:s|d|ing)?|handheld)\b"
)
_TARGET_PREFIX = re.compile(
    r"(?i)^(?:to|toward|onto|into|from|behind|beside|above|below|away\s+from|"
    r"around|along|across|past|through|following|keeping|maintaining|revealing|"
    r"showing|centered\s+on|focused\s+on|ending\s+on|framing|holding|leaving|"
    r"placing|as|while|until|with)\b"
)


@dataclass(frozen=True, slots=True)
class H3CameraDirective:
    """A typed camera instruction; prose compilation belongs to the application."""

    directive_id: str
    motion: H3CameraMotion
    target_clause: str = ""
    amplitude: H3CameraAmplitude | None = None
    speed: H3CameraSpeed | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.directive_id, str) or not _DIRECTIVE_ID.fullmatch(
            self.directive_id
        ):
            raise ValueError("camera directive id must match camera_N")
        if not isinstance(self.motion, H3CameraMotion):
            raise TypeError("motion must be an H3CameraMotion")
        if self.amplitude is not None and not isinstance(
            self.amplitude, H3CameraAmplitude
        ):
            raise TypeError("amplitude must be an H3CameraAmplitude or None")
        if self.speed is not None and not isinstance(self.speed, H3CameraSpeed):
            raise TypeError("speed must be an H3CameraSpeed or None")
        if not isinstance(self.target_clause, str):
            raise TypeError("target_clause must be a string")
        target = self.target_clause.strip()
        if len(target) > 240:
            raise ValueError("target_clause must not exceed 240 characters")
        if "\n" in target or "\r" in target or "[[" in target or "]]" in target:
            raise ValueError("target_clause must be one plain-text clause")
        if target and _CAMERA_TERMS.search(target):
            raise ValueError("target_clause must not contain camera terminology")
        if target and not _TARGET_PREFIX.match(target):
            raise ValueError(
                "target_clause must begin with a spatial or visual continuation"
            )
        if self.motion in _MOVEMENTS_WITH_BUILT_IN_OR_NO_DYNAMICS and (
            self.amplitude is not None or self.speed is not None
        ):
            raise ValueError(
                f"{self.motion.value} does not accept amplitude or speed modifiers"
            )
        if self.motion in _MOVEMENTS_WITHOUT_TARGET and target:
            raise ValueError(f"{self.motion.value} does not accept a target clause")
        object.__setattr__(self, "target_clause", target)


def h3_media_label(kind: H3MediaKind, number: int) -> str:
    if not isinstance(kind, H3MediaKind):
        raise TypeError("kind must be an H3MediaKind")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise ValueError("media label number must be a positive integer")
    return f"<{kind.value} {number}>"


__all__ = [
    "H3AudioRetention",
    "H3CameraAmplitude",
    "H3CameraDirective",
    "H3CameraMotion",
    "H3CameraSpeed",
    "H3MediaKind",
    "H3TaskType",
    "H3VisualRetention",
    "h3_media_label",
]
