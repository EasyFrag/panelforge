"""Deterministic opaque placeholders for model-facing spoken text."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re


_FENCE = re.compile(r"^\s*```(?:json|text)?\s*\n(?P<body>.*)\n```\s*$", re.DOTALL)


@dataclass(frozen=True, slots=True)
class DialoguePlaceholders:
    replacements: tuple[tuple[str, str], ...]

    @classmethod
    def from_lines(cls, lines) -> DialoguePlaceholders:
        unique: list[str] = []
        for value in lines:
            if isinstance(value, str) and value and value not in unique:
                unique.append(value)
        fingerprint = sha256("\x1f".join(unique).encode("utf-8")).hexdigest()[:12]
        return cls(tuple(
            (f"__PF_SPEECH_{fingerprint}_{index:03d}__", line)
            for index, line in enumerate(unique, 1)
        ))

    @property
    def active(self) -> bool:
        return bool(self.replacements)

    @property
    def instruction(self) -> str:
        if not self.active:
            return ""
        return (
            "\n\nPROTECTED SPEECH TOKENS: Every token beginning with "
            "__PF_SPEECH_ is an opaque, immutable spoken payload. Copy each token "
            "character-for-character wherever that line is spoken. Never translate, "
            "transliterate, inflect, split, merge, paraphrase or complete a token."
        )

    def protect(self, content: str) -> str:
        protected = content
        for token, line in sorted(
            self.replacements,
            key=lambda item: len(item[1]),
            reverse=True,
        ):
            escaped = json.dumps(line, ensure_ascii=False)[1:-1]
            if escaped != line:
                protected = protected.replace(escaped, token)
            protected = protected.replace(line, token)
        return protected

    def restore(self, content: str) -> str:
        fenced = _FENCE.match(content)
        candidate = fenced.group("body") if fenced else content
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            return self._restore_text(content)
        return json.dumps(
            self._restore_value(value),
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def _restore_value(self, value):
        if isinstance(value, str):
            return self._restore_text(value)
        if isinstance(value, list):
            return [self._restore_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self._restore_value(item) for key, item in value.items()}
        return value

    def _restore_text(self, content: str) -> str:
        restored = content
        for token, line in self.replacements:
            restored = restored.replace(token, line)
        return restored

