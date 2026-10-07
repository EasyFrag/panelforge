"""V2.1 contracts: reusable material appearances and conversational retouching."""
from copy import deepcopy
from pydantic import Field
from .story_v2 import Contract, Dialogue, Script, Sequence, PolishedSequence, validate_script


class StateBinding(Contract):
    character_id: str = Field(min_length=1, max_length=50)
    state_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,49}$")


class WritingSequence(Sequence):
    appearances: list[StateBinding] = Field(default_factory=list, max_length=8)


class WritingScript(Script):
    sequences: list[WritingSequence] = Field(min_length=1, max_length=18)


def normalized_description(text):
    return " ".join(text.casefold().split()).rstrip(" .!?…")


def normalize_script(value):
    """Resolve explicit states; never infer a variant from performance directions."""
    data = deepcopy(value)
    # Persisted/editor payloads include the resolved text; the catalog is authoritative.
    for scene in data.get("sequences", []):
        for binding in scene.get("appearances", []):
            binding.pop("state", None)
    script = WritingScript.model_validate(data)
    people = {p.id: p for p in script.characters}
    entity_ids = {e.id for group in (script.characters, script.locations, script.objects) for e in group}
    states, canonical, aliases = {}, {}, {}
    for state in script.visual_states:
        if state.id in states or state.id in entity_ids or state.character_id not in people:
            raise ValueError("État visuel inconnu, répété ou personnage absent du catalogue.")
        states[state.id] = state
        description = normalized_description(state.description)
        if description == normalized_description(people[state.character_id].description):
            aliases[state.id] = None  # Repeating the base never warrants another image.
        else:
            key = (state.character_id, description)
            aliases[state.id] = canonical.setdefault(key, state.id)
    result = script.model_dump()
    used_states, used_objects = set(), set()
    for source, scene in zip(script.sequences, result["sequences"], strict=True):
        scene["appearances"] = []
        used_objects.update(source.object_ids)
        for binding in source.appearances:
            state = states.get(binding.state_id)
            if state is None or state.character_id != binding.character_id:
                raise ValueError(f"{source.id} : état visuel inconnu ou attribué au mauvais personnage.")
            identity = aliases[state.id]
            if identity is not None:
                used_states.add(identity)
                scene["appearances"].append(dict(character_id=state.character_id,
                    state_id=identity, state=states[identity].description))
    result["objects"] = [o for o in result["objects"] if o["id"] in used_objects]
    result["visual_states"] = [state.model_dump() for state in script.visual_states if state.id in used_states]
    return result


class PolishedScene(PolishedSequence):
    dialogue: list[Dialogue] = Field(max_length=6)


class Polish(Contract):
    sequences: list[PolishedScene] = Field(min_length=1, max_length=18)


def polish(value, original, settings):
    patch = Polish.model_validate(value)
    if [s.id for s in patch.sequences] != [s["id"] for s in original["sequences"]]:
        raise ValueError("La retouche doit conserver toutes les scènes, dans leur ordre.")
    result = deepcopy(original)
    for revised, scene in zip(patch.sequences, result["sequences"], strict=True):
        # New turns may develop an existing exchange, never invent a speaking role
        # (e.g. give a silent newborn dialogue) or change a phone call to on-screen speech.
        voices = {(d["speaker_id"], d["delivery"]) for d in scene["dialogue"]}
        revised_voices = {(d.speaker_id, d.delivery) for d in revised.dialogue}
        if revised_voices != voices:
            raise ValueError(f"{scene['id']} : conserver les interlocuteurs et leurs modes de parole.")
        participants = set(scene["character_ids"]) | {speaker for speaker, _ in voices}
        participants.update(x for line in scene["dialogue"] for x in line.get("addressee_ids", []))
        if any(not set(d.addressee_ids) <= participants for d in revised.dialogue):
            raise ValueError(f"{scene['id']} : destinataire ajouté hors de l'échange existant.")
        scene["action"] = revised.action
        scene["dialogue"] = [d.model_dump() for d in revised.dialogue]
    return validate_script(result, settings)
