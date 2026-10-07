"""Small screenplay contracts; no provider or persistence dependencies."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator

from .story_v2_settings import ImageOptions, VideoOptions, CHECKPOINT

VERSION = "1.6.1"
LEGACY_WRITING_VERSION = "2.0"
DEFAULT_WRITING_VERSION = "2.1"
DEFAULT_MODEL = "local::unsloth/Qwen3.8-27B-GGUF"
DEFAULT_PROMPT_MODEL = "local::unsloth/gemma-4-31B-it-qat-GGUF"
ACTIVE = {"queued", "writing", "reviewing", "repairing", "polishing", "references", "producing"}

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class Settings(Contract):
    writing_version: Literal["2.0", "2.1"] = DEFAULT_WRITING_VERSION
    tone_profile: Literal["from_idea", "provocative_sketch"] = "from_idea"
    idea: str = Field(min_length=3, max_length=12000)
    universe: str = Field(min_length=2, max_length=1500)
    style: str = Field(min_length=2, max_length=1500)
    duration: int = Field(default=60, ge=10, le=180, strict=True)
    scene_duration: int | None = Field(default=10, ge=5, le=15, strict=True)
    final_review_enabled: bool = Field(default=False, strict=True)
    polish_enabled: bool = Field(default=False, strict=True)
    polish_model: str = Field(default=DEFAULT_PROMPT_MODEL, min_length=1, max_length=300)
    mode: Literal["manual", "automatic"] = "manual"
    language: Literal["French", "English", "Korean", "Japanese", "Russian"] = "French"
    writer_model: str = Field(default=DEFAULT_MODEL, min_length=1, max_length=300)
    reader_model: str = Field(default=DEFAULT_MODEL, min_length=1, max_length=300)
    prompt_model: str = Field(default=DEFAULT_PROMPT_MODEL, min_length=1, max_length=300)
    image_model: str = Field(default=CHECKPOINT, min_length=1, max_length=300)
    dlss: bool = True
    images: ImageOptions = Field(default_factory=ImageOptions)
    video: VideoOptions = Field(default_factory=VideoOptions)

    @model_validator(mode="after")
    def scene_budget(self):
        durations = scene_durations(dict(duration=self.duration, scene_duration=self.scene_duration))
        if durations is not None and len(durations) > 18:
            raise ValueError("18 scènes maximum : augmente la durée par scène ou réduis la durée totale.")
        return self

class Entity(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,49}$")
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=2, max_length=650)

class Character(Entity):
    relationship: str = Field(min_length=2, max_length=180)

class Dialogue(Contract):
    speaker_id: str = Field(min_length=1, max_length=50)
    text: str = Field(min_length=1, max_length=450)
    delivery: Literal["spoken", "off_screen", "voice_over", "thought", "mediated"] = "spoken"

    # Narrative recipients are independent of visible presence and vocal delivery.
    addressee_ids: list[str] = Field(default_factory=list, max_length=10)
    address_cue: str = Field(default="", max_length=180, pattern=r"^[^\r\n]*$")

    @model_serializer(mode="wrap")
    def compact_addressing(self, handler):
        # Empty defaults must not change legacy script hashes or episode identities.
        data = handler(self)
        for key in ("addressee_ids", "address_cue"):
            if not data.get(key):
                data.pop(key, None)
        return data

class VisualState(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,49}$")
    character_id: str = Field(min_length=1, max_length=50)
    kind: Literal["clothing", "hair", "physical"]
    description: str = Field(min_length=2, max_length=240)

class Appearance(Contract):
    character_id: str = Field(min_length=1, max_length=50)
    state: str = Field(min_length=2, max_length=240)
    state_id: str = Field(default="", max_length=50)

    @model_serializer(mode="wrap")
    def compact_state(self, handler):
        data = handler(self)
        if not self.state_id:
            data.pop("state_id", None)
        return data

class Sequence(Contract):
    id: str = Field(pattern=r"^seq-[0-9]+$")
    title: str = Field(min_length=1, max_length=90)
    setting: str = Field(min_length=2, max_length=200)
    action: str = Field(min_length=2, max_length=420)
    intention: str = Field(min_length=2, max_length=320)
    duration: int = Field(ge=5, le=15, strict=True)
    location_id: str = Field(min_length=1, max_length=50)
    character_ids: list[str] = Field(max_length=8)
    object_ids: list[str] = Field(default_factory=list, max_length=5)
    appearances: list[Appearance] = Field(default_factory=list, max_length=8)
    dialogue: list[Dialogue] = Field(max_length=6)

    @field_validator("action", "intention")
    @classmethod
    def sentence(cls, text):
        # Deterministic display limit, not a heuristic claim about story quality.
        if "\n" in text or len(re.findall(r"[.!?](?:[\"»])?\s+(?=[A-ZÀ-Ý])", text)) > 0:
            raise ValueError("Une seule phrase est attendue pour l'action et l'intention.")
        return text

class Script(Contract):
    title: str = Field(min_length=1, max_length=120)
    summary: list[str] = Field(min_length=1, max_length=2)
    characters: list[Character] = Field(min_length=1, max_length=10)
    locations: list[Entity] = Field(min_length=1, max_length=6)
    objects: list[Entity] = Field(default_factory=list, max_length=10)
    visual_states: list[VisualState] = Field(default_factory=list, max_length=24)
    sequences: list[Sequence] = Field(min_length=1, max_length=18)

    @model_serializer(mode="wrap")
    def compact_visual_states(self, handler):
        data = handler(self)
        if not self.visual_states:
            data.pop("visual_states", None)
        return data

    @field_validator("summary")
    @classmethod
    def short_summary(cls, lines):
        for text in lines:
            if not text.strip() or len(text) > 320:
                raise ValueError("Le résumé contient une ou deux phrases courtes.")
            Sequence.sentence(text)
        return lines

    @model_validator(mode="after")
    def coherent_ids(self):
        all_ids = [e.id for group in (self.characters, self.locations, self.objects) for e in group]
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("Chaque personnage, décor et objet possède son propre identifiant.")
        people = {p.id for p in self.characters}
        locations = {p.id for p in self.locations}
        objects = {p.id for p in self.objects}
        for i, s in enumerate(self.sequences, 1):
            if s.id != f"seq-{i}" or s.location_id not in locations:
                raise ValueError("Séquences ordonnées seq-1… et décors connus attendus.")
            for ids, known in ((s.character_ids, people), (s.object_ids, objects)):
                if len(ids) != len(set(ids)) or not set(ids) <= known:
                    raise ValueError(f"{s.id} : présence inconnue ou répétée.")
            if len(s.character_ids) + len(s.object_ids) + 1 > 9:
                raise ValueError(f"{s.id} : neuf références maximum, décor compris.")
            states = [a.character_id for a in s.appearances]
            if len(states) != len(set(states)) or not set(states) <= set(s.character_ids):
                raise ValueError(f"{s.id} : apparence réservée aux personnages présents.")
            for line in s.dialogue:
                if line.speaker_id not in people or (line.delivery == "spoken" and line.speaker_id not in s.character_ids):
                    raise ValueError(f"{s.id} : locuteur inconnu ou absent sans mode hors champ.")
                if (len(line.addressee_ids) != len(set(line.addressee_ids))
                        or not set(line.addressee_ids) <= people or line.speaker_id in line.addressee_ids):
                    raise ValueError(f"{s.id} : destinataire inconnu, répété ou identique au locuteur.")
                if line.address_cue and not line.addressee_ids:
                    raise ValueError(f"{s.id} : une indication de regard nécessite un destinataire identifié.")
            # French typography separates !, ? and : with spaces; these are not spoken words.
            words = sum(any(c.isalnum() for c in token) for d in s.dialogue for token in d.text.split())
            if words > s.duration * 3.5:
                raise ValueError(f"{s.id} : trop de paroles pour laisser jouer la scène en {s.duration} s "
                                 f"({words} mots, limite {int(s.duration * 3.5)}).")
        return self

class Review(Contract):
    understood: str = Field(min_length=1, max_length=900)
    issues: list[str] = Field(max_length=6)

    @field_validator("issues")
    @classmethod
    def concise_issues(cls, value):
        if any(not item.strip() or len(item) > 500 for item in value):
            raise ValueError("Les remarques de relecture doivent être courtes et concrètes.")
        return value

def scene_durations(settings):
    """Exact total; full target-length scenes, with the tail adjusted to valid 5–15 s clips."""
    target = settings.get("scene_duration")
    if target is None:
        return None  # Explicit free timing, also used for existing stories without this setting.
    total = settings["duration"]
    count = min((total + target - 1) // target, total // 5)
    result = [target] * (count - 1) + [total - target * (count - 1)]
    missing = max(0, 5 - result[-1])
    for i in range(len(result) - 2, -1, -1):
        borrowed = min(missing, result[i] - 5)
        result[i] -= borrowed
        result[-1] += borrowed
        missing -= borrowed
    return result


def writing_schema(settings):
    if settings.get("writing_version", LEGACY_WRITING_VERSION) == DEFAULT_WRITING_VERSION:
        from .story_v21 import WritingScript
        schema = WritingScript.model_json_schema()
        schema["required"].append("visual_states")
    else:
        schema = Script.model_json_schema()
        schema["properties"].pop("visual_states")
        schema["$defs"].pop("VisualState")
        schema["$defs"]["Appearance"]["properties"].pop("state_id")
    # Require the author to decide explicitly; old stored scripts remain optional.
    schema["$defs"]["Dialogue"]["required"].extend(["addressee_ids", "address_cue"])
    timing = scene_durations(settings)
    if timing is not None:
        schema["properties"]["sequences"].update(minItems=len(timing), maxItems=len(timing))
        sequence_type = schema["properties"]["sequences"]["items"]["$ref"].rsplit("/", 1)[-1]
        schema["$defs"][sequence_type]["properties"]["duration"]["enum"] = sorted(set(timing))
    return schema


def parse_script(value, settings):
    dense = settings.get("writing_version", LEGACY_WRITING_VERSION) == DEFAULT_WRITING_VERSION
    if dense:
        from .story_v21 import normalize_script
        value = normalize_script(value)
    script = Script.model_validate(value)
    if not dense and (script.visual_states or any(a.state_id for s in script.sequences for a in s.appearances)):
        raise ValueError("Le catalogue d'états visuels appartient à la version V2.1.")
    return script


def validate_script(value, settings):
    script = parse_script(value, settings)
    durations = [s.duration for s in script.sequences]
    expected = scene_durations(settings)
    if expected is not None and durations != expected:
        raise ValueError("Découpage attendu : " + " / ".join(map(str, expected))
                         + f" s, soit {settings['duration']} s au total. Retravaille le découpage.")
    total = sum(durations)
    if abs(total - settings["duration"]) > max(5, settings["duration"] * .1):
        raise ValueError(f"Durée écrite {total} s trop éloignée des {settings['duration']} s demandées.")
    return script.model_dump()


class PolishedSequence(Contract):
    id: str = Field(pattern=r"^seq-[0-9]+$")
    action: str = Field(min_length=2, max_length=420)
    dialogue: list[str] = Field(max_length=6)

    @field_validator("action")
    @classmethod
    def sentence(cls, value):
        return Sequence.sentence(value)


class Polish(Contract):
    sequences: list[PolishedSequence] = Field(min_length=1, max_length=18)


def validate_polish(value, original, settings):
    """Dispatch the selected retouching contract; legacy turns remain immutable."""
    if settings.get("writing_version", LEGACY_WRITING_VERSION) == DEFAULT_WRITING_VERSION:
        from .story_v21 import polish
        return polish(value, original, settings)
    patch = Polish.model_validate(value)
    if [s.id for s in patch.sequences] != [s["id"] for s in original["sequences"]]:
        raise ValueError("La retouche doit conserver toutes les scènes, dans leur ordre.")
    result = deepcopy(original)
    for revised, scene in zip(patch.sequences, result["sequences"], strict=True):
        if len(revised.dialogue) != len(scene["dialogue"]):
            raise ValueError(f"{scene['id']} : la retouche doit conserver les tours de parole.")
        scene["action"] = revised.action
        for text, line in zip(revised.dialogue, scene["dialogue"], strict=True):
            line["text"] = text
    return validate_script(result, settings)


def polish_schema(settings):
    if settings.get("writing_version", LEGACY_WRITING_VERSION) == DEFAULT_WRITING_VERSION:
        from .story_v21 import Polish as DensePolish
        schema = DensePolish.model_json_schema()
        schema["$defs"]["Dialogue"]["required"].extend(["addressee_ids", "address_cue"])
        return schema
    return Polish.model_json_schema()


def audience_view(script):
    # The reader cannot rely on author intentions, summaries or character roles as evidence.
    names = {p["id"]: p["name"] for p in script["characters"]}
    return [dict(sequence=s["id"], visible=s["action"],
        present=[names[x] for x in s["character_ids"]],
        dialogue=[dict(speaker=names[d["speaker_id"]], text=d["text"], delivery=d["delivery"],
                       **({"visible_address":d["address_cue"]} if d.get("address_cue") else {}))
                  for d in s["dialogue"]]) for s in script["sequences"]]


def default_settings():
    return Settings.model_construct(idea="", universe="", style="").model_dump()
