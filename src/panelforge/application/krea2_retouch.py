"""Image composition boundary, with no image library in the domain."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PreparedRetouch:
    source_png: bytes
    generated_png: bytes
    width: int
    height: int
    harmonized_png: bytes


@dataclass(frozen=True, slots=True)
class ComposedRetouch:
    mask_png: bytes
    output_png: bytes
    width: int
    height: int


class RetouchCompositor(Protocol):
    def prepare(self, source: bytes, generated: bytes) -> PreparedRetouch: ...
    def compose(self, source: bytes, generated: bytes, mask: bytes, *,
                harmonize: bool = False, harmonize_strength: int = 100) -> ComposedRetouch: ...
