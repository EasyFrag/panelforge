"""Bounded JSON recovery. Repairs punctuation, never guesses content or executes code."""
import json
import math
import re


class StoryJsonError(ValueError):
    pass


class _Reader:
    def __init__(self, raw):
        self.raw, self.pos, self.notes = raw, 0, []
        self.decoder = json.JSONDecoder()

    def fail(self, message):
        raise json.JSONDecodeError(message, self.raw, self.pos)

    def peek(self):
        while self.pos < len(self.raw) and self.raw[self.pos].isspace():
            self.pos += 1
        return self.raw[self.pos:self.pos + 1]

    def repair(self, message, start):
        if len(self.notes) >= 64:
            self.fail("Trop de réparations structurelles")
        self.notes.append(f"{message} (position {start}) ; original conservé.")

    def string(self):
        if self.peek() != '"':
            self.fail("Chaîne JSON attendue")
        value, self.pos = self.decoder.raw_decode(self.raw, self.pos)
        return value

    def value(self, depth=0):
        if depth > 64:
            self.fail("Imbrication JSON excessive")
        char = self.peek()
        if char in {"{", "["}:
            return self.container(char, depth + 1)
        if char == '"':
            value = self.string()
            start = self.pos
            suffix = re.match(r"\s*\.replace\(\s*", self.raw[self.pos:])
            if suffix:
                self.pos += suffix.end()
                old = self.string()
                if self.peek() != ",":
                    self.fail("Virgule requise dans le remplacement littéral")
                self.pos += 1
                new = self.string()
                if self.peek() != ")" or not old or len(value) + value.count(old) * len(new) > 240_000:
                    self.fail("Remplacement littéral invalide")
                self.pos += 1
                value = value.replace(old, new)
                self.repair("Remplacement de chaînes littérales résolu localement", start)
            return value
        if char and (char in "-0123456789" or self.raw.startswith(("true", "false", "null"), self.pos)):
            value, self.pos = self.decoder.raw_decode(self.raw, self.pos)
            if isinstance(value, float) and not math.isfinite(value):
                self.fail("Nombre JSON non fini")
            return value
        self.fail("Valeur JSON attendue")

    def container(self, opening, depth):
        closing = "}" if opening == "{" else "]"
        result = {} if opening == "{" else []
        self.pos += 1
        if self.peek() == closing:
            self.pos += 1
            return result
        while True:
            if opening == "{":
                key = self.string()
                if key in result:
                    self.fail("Clé JSON dupliquée et ambiguë : " + key)
                if self.peek() != ":":
                    self.fail("Deux-points attendu après une clé")
                self.pos += 1
                start = self.pos
                # Only remove a repeated current key followed by ':', outside strings.
                if self.peek() == '"':
                    candidate = self.string()
                    if candidate == key and self.peek() == ":":
                        self.pos += 1
                        self.repair("Clé répétée supprimée : " + key, start)
                    else:
                        self.pos = start
                result[key] = self.value(depth)
            else:
                result.append(self.value(depth))
            char = self.peek()
            if char == closing:
                self.pos += 1
                return result
            if char == ",":
                self.pos += 1
                if self.peek() == closing:
                    self.pos += 1
                    # The historical decoder already accepted trailing commas.
                    return result
                continue
            if opening == "{" and char == '"':
                self.repair("Virgule entre champs rétablie", self.pos)
                continue
            self.fail("Séparateur ou fermeture JSON attendu")


def decode_response(raw):
    if not isinstance(raw, str) or len(raw) > 240_000:
        raise StoryJsonError("Réponse absente ou trop volumineuse ; original conservé.")
    reader = _Reader(raw)
    try:
        result = reader.value()
        if reader.peek():
            reader.fail("Texte inattendu après le JSON")
        return result, reader.notes
    except (json.JSONDecodeError, RecursionError) as error:
        if isinstance(error, json.JSONDecodeError):
            detail = f"ligne {error.lineno}, colonne {error.colno} : {error.msg}"
        else:
            detail = "imbrication excessive"
        raise StoryJsonError(f"JSON invalide, {detail}. Le brouillon original est conservé.") from error


def assert_format_only(original, corrected):
    """Compare decoded structure and typed values, not a flat sequence of tokens."""
    try:
        before, _ = decode_response(original)
        after, _ = decode_response(corrected)
    except StoryJsonError as error:
        raise ValueError("La fidélité de la correction ne peut pas être établie ; original conservé.") from error
    canonical = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if canonical(before) != canonical(after):
        raise ValueError("La correction du format modifie le contenu ; le brouillon original est conservé.")
