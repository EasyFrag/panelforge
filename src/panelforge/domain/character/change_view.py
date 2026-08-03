"""Pure domain contract for deriving a new view of a character asset."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


OPERATION_ID = "character.change_view"


class CameraAzimuth(StrEnum):
    FRONT = "front"
    FRONT_RIGHT_QUARTER = "front_right_quarter"
    RIGHT_SIDE = "right_side"
    BACK_RIGHT_QUARTER = "back_right_quarter"
    BACK = "back"
    BACK_LEFT_QUARTER = "back_left_quarter"
    LEFT_SIDE = "left_side"
    FRONT_LEFT_QUARTER = "front_left_quarter"


class CameraElevation(StrEnum):
    LOW = "low"
    EYE_LEVEL = "eye_level"
    ELEVATED = "elevated"
    HIGH = "high"


class ShotSize(StrEnum):
    CLOSE_UP = "close_up"
    MEDIUM = "medium"
    WIDE = "wide"


@dataclass(frozen=True, slots=True)
class ChangeView:
    """Request a supported camera view from one approved source asset."""

    source_asset_id: str
    azimuth: CameraAzimuth
    elevation: CameraElevation
    shot_size: ShotSize

    def __post_init__(self) -> None:
        if not isinstance(self.source_asset_id, str) or not self.source_asset_id.strip():
            raise ValueError("source_asset_id must not be empty")
        expected_types = (
            ("azimuth", self.azimuth, CameraAzimuth),
            ("elevation", self.elevation, CameraElevation),
            ("shot_size", self.shot_size, ShotSize),
        )
        for name, value, expected_type in expected_types:
            if not isinstance(value, expected_type):
                raise TypeError(f"{name} must be a {expected_type.__name__}")
