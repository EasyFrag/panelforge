"""Immutable provenance for local compositions of Assisted images."""

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class AssistedComposition:
    original_attempt_id: str
    parent_attempt_id: str
    source_asset_id: str
    generated_asset_id: str
    mask_asset_id: str
    request_id: str
    submitted_mask_sha256: str
    width: int
    height: int
    harmonize: bool = False
    harmonize_strength: int = 100
    color_method: str = "reinhard_lab_rgb@1.0.0"

    def __post_init__(self):
        for name in ("original_attempt_id", "parent_attempt_id", "source_asset_id", "generated_asset_id", "mask_asset_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"composition {name} must not be empty")
        if not isinstance(self.request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", self.request_id):
            raise ValueError("invalid composition request_id")
        if not isinstance(self.submitted_mask_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.submitted_mask_sha256):
            raise ValueError("invalid composition mask digest")
        if any(type(v) is not int or v < 1 for v in (self.width, self.height)):
            raise ValueError("composition dimensions must be positive integers")
        if type(self.harmonize) is not bool or type(self.harmonize_strength) is not int or not 0 <= self.harmonize_strength <= 100:
            raise ValueError("invalid composition harmonization")
        if self.color_method != "reinhard_lab_rgb@1.0.0":
            raise ValueError("unsupported composition color method")
