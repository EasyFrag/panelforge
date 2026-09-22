"""Narrow data-only recovery of malformed story responses; never execute model code."""
import json
import re

from .stories import decode_story_json


class StoryJsonError(ValueError):
    pass


def decode_response(raw):
    try:
        return decode_story_json(raw), []
    except json.JSONDecodeError as original:
        decoder = json.JSONDecoder()
        parts, position, repaired, size = [], 0, 0, 0
        try:
            while position < len(raw):
                if raw[position] != '"':
                    parts.append(raw[position])
                    size += 1
                    if size > 240_000:
                        raise ValueError("response exceeds limit")
                    position += 1
                    continue
                value, end = decoder.raw_decode(raw, position)
                suffix = re.match(r"\s*\.replace\(\s*", raw[end:])
                if suffix:
                    old, cursor = decoder.raw_decode(raw, end + suffix.end())
                    separator = re.match(r"\s*,\s*", raw[cursor:])
                    if not separator:
                        raise ValueError("literal separator required")
                    new, cursor = decoder.raw_decode(raw, cursor + separator.end())
                    closing = re.match(r"\s*\)", raw[cursor:])
                    if not closing or not all(isinstance(item, str) for item in (value, old, new)):
                        raise ValueError("literal strings required")
                    if not old or len(value) + value.count(old) * len(new) > 240_000:
                        raise ValueError("replacement exceeds response limit")
                    # This is a whitelisted operation on decoded data, not eval/exec.
                    value = value.replace(old, new)
                    parts.append(json.dumps(value, ensure_ascii=False))
                    end = cursor + closing.end()
                    repaired += 1
                else:
                    parts.append(raw[position:end])
                size += len(parts[-1])
                if size > 240_000:
                    raise ValueError("response exceeds limit")
                position = end
            if repaired:
                data = decode_story_json("".join(parts))
                return data, [f"{repaired} remplacement(s) de chaînes littérales résolu(s) localement ; original conservé."]
        except (ValueError, TypeError):
            pass
        raise StoryJsonError(
            f"JSON invalide, ligne {original.lineno}, colonne {original.colno} : {original.msg}. "
            "Le brouillon original est conservé."
        ) from original


def assert_format_only(original, corrected):
    """A last-resort model repair may change punctuation, never scalar values."""
    token = re.compile(r'"(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null')
    def scalars(value):
        return tuple(match.group() for match in token.finditer(value))
    if scalars(original) != scalars(corrected):
        raise ValueError("La correction du format modifie le contenu ; le brouillon original est conservé.")
