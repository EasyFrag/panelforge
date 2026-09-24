"""Dialogue-only localization. No rendering or model dependencies."""
from copy import deepcopy
from dataclasses import asdict
import re

from .stories import DIALOGUE_LANGUAGES

DEFAULT_MODEL = "local::unsloth/gemma-4-31B-it-qat-GGUF"
_DIALOGUE = re.compile(r"<d>\s*\[([^]\r\n]+)\]\s*(.*?)\s*</d>", re.DOTALL)
_TAG = re.compile(r"</?d(?:\s[^>]*)?>", re.IGNORECASE)


def dialogue_slots(prompt, scene_id):
    matches = list(_DIALOGUE.finditer(prompt))
    if len(_TAG.findall(prompt)) != 2 * len(matches):
        raise ValueError("Balises de dialogue incomplètes : choisissez un autre essai source.")
    result = []
    for index, match in enumerate(matches, 1):
        language, text = match.group(1).strip(), match.group(2).strip()
        if not text or "<" in text or ">" in text:
            raise ValueError("Réplique source ambiguë : choisissez un autre essai source.")
        result.append(dict(id=f"{scene_id}:d{index}", language=language, text=text,
                           start=match.start(), end=match.end()))
    return result


def translations(value, slots):
    if not isinstance(value, dict) or set(value) != {"translations"} or not isinstance(value["translations"], list):
        raise ValueError("La réponse doit contenir une liste translations, avec id et text pour chaque réplique.")
    expected = {slot["id"] for slot in slots}
    result = {}
    for line in value["translations"]:
        if not isinstance(line, dict) or set(line) != {"id", "text"}:
            raise ValueError("Chaque traduction doit contenir uniquement id et text.")
        identity, text = line["id"], line["text"]
        if not isinstance(identity, str) or identity not in expected or identity in result:
            raise ValueError("Traduction inconnue ou dupliquée ; aucun prompt modifié.")
        if not isinstance(text, str) or not text.strip() or len(text) > 4000 or any(c in text for c in "<>\r\n"):
            raise ValueError("Une traduction doit être une réplique non vide, sans balise ni saut de ligne.")
        result[identity] = text.strip()
    if set(result) != expected:
        raise ValueError("Des répliques manquent à la traduction ; aucun prompt modifié.")
    return result


def inject(prompt, scene_id, language, translated):
    if language not in DIALOGUE_LANGUAGES:
        raise ValueError("Langue de dialogue non prise en charge.")
    slots = dialogue_slots(prompt, scene_id)
    checked = translations({"translations": [dict(id=k, text=v) for k, v in translated.items()]}, slots)
    # Reverse replacement preserves every byte outside the original dialogue spans.
    for slot in reversed(slots):
        prompt = prompt[:slot["start"]] + f"<d>[{language}] {checked[slot['id']]}</d>" + prompt[slot["end"]:]
    return prompt


def frozen_inputs(scene):
    data = deepcopy(scene["localization"]["inputs"])
    data["localization"] = dict(language=scene["localization"]["language"],
                                translations=scene["localization"].get("translations", {}))
    return data


def attempt_setup(attempt, fallback):
    if attempt.recipe is None:
        raise ValueError("Cet ancien essai n’enregistre pas sa recette de rendu ; choisissez un essai plus récent.")
    setup = deepcopy(fallback)
    setup.update(settings=asdict(attempt.settings), seed_locked=True,
                 recipe=dict(id=attempt.recipe.recipe_id, version=attempt.recipe.version) if attempt.recipe else setup["recipe"])
    for field in ("bunny", "video_lora", "video_loras", "model_loading"):
        value = getattr(attempt, field, None)
        setup[field] = asdict(value) if value is not None else None
    for field in ("music_enabled", "spectrum_enabled", "initial_megapixels", "force_upscale", "checkpoint"):
        setup[field] = getattr(attempt, field)
    setup["settings"]["seed_locked"] = True
    setup["settings"]["seed"] = str(attempt.settings.seed)
    return setup


def translation_schema(slots):
    return {"type": "object", "additionalProperties": False, "required": ["translations"], "properties": {
        "translations": {"type": "array", "minItems": len(slots), "maxItems": len(slots), "items": {
            "type": "object", "additionalProperties": False, "required": ["id", "text"], "properties": {
                "id": {"type": "string", "enum": [slot["id"] for slot in slots]},
                "text": {"type": "string", "minLength": 1}}}}}}


def length_warning(slots, translated, duration):
    total = sum(len(re.findall(r"\w+", translated[slot["id"]])) for slot in slots)
    if slots and total > duration * 3:
        return "Débit estimé élevé : relisez les répliques avant de produire la vidéo."
    return None


def setup_matches_attempt(setup, attempt):
    """A changed technical setup requires a new video, even for a silent copy."""
    actual = attempt_setup(attempt, setup)
    requested = deepcopy(setup)
    if bool(requested.get("seed_locked", True)):
        if str(requested["settings"].get("seed", 0)) != str(attempt.settings.seed):
            return False
    for key in ("aspect_ratio", "megapixels", "duration_seconds", "steps"):
        if requested["settings"][key] != actual["settings"][key]:
            return False
    return all(requested.get(key) == actual.get(key) for key in (
        "recipe", "bunny", "checkpoint", "video_loras", "video_lora", "music_enabled",
        "spectrum_enabled", "initial_megapixels", "force_upscale"))
