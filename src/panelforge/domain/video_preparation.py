"""Pinned creative families, independent of ComfyUI render recipes."""

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class VideoPreparationRef:
    family: str = "classic"
    version: str | None = None

    def __post_init__(self) -> None:
        if self.family not in {"classic", "combat", "sensual"}:
            raise ValueError("unknown video preparation family")
        if self.family == "classic":
            if self.version not in (None, "1.0.0"):
                raise ValueError("unknown Classic cinematic version")
        elif self.family == "sensual":
            if self.version != "1.0.0":
                raise ValueError("unknown Sensual cinematic version")
        elif not isinstance(self.version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", self.version):
            raise ValueError("combat preparation requires an exact version")

    @classmethod
    def from_dict(cls, value: object) -> "VideoPreparationRef":
        if not isinstance(value, dict) or set(value) != {"family", "version"}:
            raise ValueError("invalid video preparation reference")
        return cls(family=value["family"], version=value["version"])

    def as_dict(self) -> dict[str, str | None]:
        return {"family": self.family, "version": self.version}

    @property
    def is_combat(self) -> bool:
        return self.family == "combat"

    @property
    def is_classic_cinematic(self) -> bool:
        return self.family == "classic" and self.version == "1.0.0"

    @property
    def is_sensual(self) -> bool:
        return self.family == "sensual" and self.version == "1.0.0"

    @property
    def uses_cinematic_phases(self) -> bool:
        return self.is_classic_cinematic or self.is_sensual or (self.is_combat and self.version == "1.3.0")


@dataclass(frozen=True, slots=True)
class SensualSettings:
    """Pinned V1 controls; explicitness is intentionally not a free slider yet."""

    explicitness: str = "explicit_maximal"
    shot_count: int | None = None

    def __post_init__(self) -> None:
        if self.explicitness != "explicit_maximal":
            raise ValueError("Sensual 1.0 supports only explicit_maximal")
        if self.shot_count is not None and (type(self.shot_count) is not int or not 1 <= self.shot_count <= 6):
            raise ValueError("sensual shot_count must be 1-6 or null (Auto)")

    def as_dict(self) -> dict:
        return {"explicitness": self.explicitness, "shot_count": self.shot_count}

    @classmethod
    def from_dict(cls, value: object) -> "SensualSettings":
        if not isinstance(value, dict) or set(value) != {"explicitness", "shot_count"}:
            raise ValueError("invalid Sensual settings")
        return cls(**value)


def validate_sensual_settings(preparation: VideoPreparationRef, settings: SensualSettings | None) -> None:
    if preparation.is_sensual:
        if not isinstance(settings, SensualSettings):
            raise ValueError("Sensual 1.0 requires its saved explicitness and shot setting")
    elif settings is not None:
        raise ValueError("these controls belong to Sensual 1.0")


@dataclass(frozen=True, slots=True)
class ClassicCinematicSettings:
    """An explicit count overrides intention; None delegates to intention/Plan."""

    shot_count: int | None = None

    def __post_init__(self) -> None:
        if self.shot_count is not None and (type(self.shot_count) is not int or not 1 <= self.shot_count <= 6):
            raise ValueError("classic shot_count must be 1-6 or null (Auto)")

    def as_dict(self) -> dict:
        return {"shot_count": self.shot_count}

    @classmethod
    def from_dict(cls, value: object) -> "ClassicCinematicSettings":
        if not isinstance(value, dict) or set(value) != {"shot_count"}:
            raise ValueError("invalid Classic cinematic settings")
        return cls(**value)


def validate_cinematic_settings(preparation: VideoPreparationRef, settings: ClassicCinematicSettings | None) -> None:
    if preparation.is_classic_cinematic:
        if not isinstance(settings, ClassicCinematicSettings):
            raise ValueError("Classic cinematic requires its saved shot setting")
    elif settings is not None:
        raise ValueError("these controls belong to Classic cinematic 1.0")


@dataclass(frozen=True, slots=True)
class CombatSettings:
    """Saved controls; 1.2 adds orientation, None shot_count delegates 1-6 shots."""

    action_level: int = 1
    shot_count: int | None = 1
    orientation: str | None = None

    def __post_init__(self) -> None:
        if type(self.action_level) is not int or not 0 <= self.action_level <= 3:
            raise ValueError("combat action_level must be between 0 and 3")
        if self.shot_count is not None and (type(self.shot_count) is not int or not 1 <= self.shot_count <= 6):
            raise ValueError("combat shot_count must be 1-6 or null (Auto)")
        if self.orientation is not None and self.orientation not in ("mixed", "hand_to_hand", "weapons", "magic"):
            raise ValueError("combat orientation must be mixed, hand_to_hand, weapons or magic")

    def as_dict(self) -> dict:
        value = {"action_level": self.action_level, "shot_count": self.shot_count}
        if self.orientation is not None:
            value["orientation"] = self.orientation
        return value

    @classmethod
    def from_dict(cls, value: object) -> "CombatSettings":
        if not isinstance(value, dict) or set(value) not in ({"action_level", "shot_count"}, {"action_level", "shot_count", "orientation"}):
            raise ValueError("invalid Combat settings")
        return cls(**value)


def validate_combat_settings(preparation: VideoPreparationRef, settings: CombatSettings | None) -> None:
    if preparation.is_combat and preparation.version in {"1.1.0", "1.1.1", "1.2.0", "1.3.0"}:
        if not isinstance(settings, CombatSettings):
            raise ValueError("Combat 1.1 requires its saved action and shot settings")
        if (preparation.version in {"1.2.0", "1.3.0"}) != (settings.orientation is not None):
            raise ValueError("Combat 1.2 requires an orientation; earlier versions keep their original settings")
        if settings.orientation == "magic" and preparation.version != "1.3.0":
            raise ValueError("Magic orientation belongs to Combat 1.3")
    elif settings is not None:
        raise ValueError("these controls belong to Combat 1.1")
