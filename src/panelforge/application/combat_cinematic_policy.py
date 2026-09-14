"""Pinned Combat 1.3 teaching policy; no classifier or additional model call."""

from .prompt_recipe_text import prompt_text
import json
import re


def action_policy(settings) -> str:
    level = (
        prompt_text('combat_cinematic_policy.action_policy.01', 'MODERATE: a few developed exchanges with visible recovery, readable travel and force. Respect the requested attacks.'),
        prompt_text('combat_cinematic_policy.action_policy.02', 'DYNAMIC: linked combinations and a clear initiative reversal; change range or position as a consequence of attacks.'),
        prompt_text('combat_cinematic_policy.action_policy.03', 'INTENSE: sustained multi-action pressure, defence feeding a counter, rapid re-entry, travelling combinations and emphatic impacts. Keep acceleration and displacement perceptible.'),
        prompt_text('combat_cinematic_policy.action_policy.04', 'UNLEASHED: a decisive increase in speed contrast, travel distance, attack amplitude and overlapping offence/defence. Explosive departures, crossing passes, abrupt redirections, counterfire during evasions and immediate pursuit drive the encounter through the setting. In supernatural fantasy, use established powers at battlefield scale, aerial redirections or energy barrages when compatible with the intention and anatomy. In grounded combat, express the same ambition through committed footwork, weapon inertia, rapid combinations and near misses. Brief resistance or speed contrasts make the next acceleration hit harder; avoid a steady parade of isolated blows or a routine return to guard.'),
    )[settings.action_level]
    orientation = {
        "mixed": prompt_text('combat_cinematic_policy.action_policy.05', 'Follow the dominant means of combat in the intention. Powers described as weapons should drive ranged exchanges; do not turn them automatically into glowing punches. Mix ranges only when tactically motivated.'),
        "hand_to_hand": prompt_text('combat_cinematic_policy.action_policy.06', 'Build combinations from the established anatomy and fighting style: entries, off-line evasions, counters, grips, weight transfer and displacement. Every defensive motion opens a next action; avoid a fixed jab-block loop. No weapons or supernatural powers unless requested.'),
        "weapons": prompt_text('combat_cinematic_policy.action_policy.07', 'Let weapon geometry and inertia shape the fight. A heavy swing commits weight and carries into terrain or recovery; a lighter weapon changes line, range and initiative through that opening. With fast blades, chain height, side, grip and passing-direction changes. Keep ownership and contact readable; effects originate from the weapon action.'),
        "magic": prompt_text('combat_cinematic_policy.action_policy.08', 'POWERS / MAGIC are the primary weapons. Use breath streams, volleys, fire jets, lightning paths, ice spears or zones only from the actual established abilities. Each attack has an emitter, trajectory/area, target, visible consequence and adversary response. Evasion, cover, interception, sustained beams and counterfire change distance and geography. Contact is optional, not the default climax of every exchange. Powers do not add body parts, forehead flames, eyes, costumes or a new species; preserve reference morphology.'),
    }[settings.orientation]
    count = prompt_text('combat_cinematic_policy.action_policy.09', 'Choose 1-6 shots for the duration and encounter.') if settings.shot_count is None else f"Use exactly {settings.shot_count} shot(s)."
    return (prompt_text('combat_cinematic_policy.action_policy.10', '\n\nCOMBAT 1.3 SAVED CONTROLS\nACTION QUANTITY: ') + level + "\nORIENTATION: " + orientation
        + "\nSHOT COUNT: " + count
        + prompt_text('combat_cinematic_policy.action_policy.11', " Action level, shot count, camera permission and tactical audacity remain independent. A shot may contain several connected combinations; a continuous camera phase is not a cut. No hit quota, evenly spaced gesture timestamps or hidden close-up cuts. Camera permission 0 permits static framing with maximal action. Invent techniques from the delegated global arc. Preserve the requested advantage, reversal and ending. Unleashed never means compulsory gore, death, new powers, new enemies or explosions. If multiple opponents are requested, use a coherent main trajectory and staggered pressure; retain opponents' resulting states. Use explicit actor names/reference associations when a pronoun could transfer an attack to the wrong fighter. Write ALL compiled fields in English, including opening, cue, pacing, end state, transition and actor designations."))


def example_key(settings, intention: str = "") -> str:
    """Select a teaching example, never classify or modify the saved orientation."""
    if settings.orientation != "hand_to_hand" and re.search(r"(?i)\b(cultivator|cultivatrice|cultivateur|wuxia|xianxia|sword[- ]qi|sword fantasy)\b", intention):
        return "aerial_fantasy"
    if settings.orientation == "magic" or (settings.orientation == "mixed" and re.search(
            r"(?i)\b(magic|magie|magique|feu|fire|ice|glace|lightning|électri\w*|pokemon|pokémon|qi)\b", intention)):
        return "powers"
    if settings.orientation == "hand_to_hand":
        return "hand_to_hand"
    if re.search(r"(?i)\b(axe|hache|hammer|marteau|heavy|lourd\w*|shield|bouclier)\b", intention):
        return "heavy_weapons"
    return "fast_weapons"


def demonstration(settings, stage: str, intention: str = "") -> str:
    from .combat_cinematic_examples import example
    key = example_key(settings, intention)
    sample = example(key, unleashed=settings.action_level == 3)
    payload = {"example_intention": sample["intention"], "approved_plan" if stage != "beat_sheet" else "expected_json": sample["plan"]}
    if stage != "beat_sheet":
        payload["expected_json"] = sample["writer"]
    return ("\n\nCOMBAT 1.3 WORKED EXAMPLE (" + key + prompt_text('combat_cinematic_policy.demonstration.01', ")\nLearn causal density, camera/action separation and output shape. This example has its own duration, two shots, free camera and no reference images. Follow the REAL user's shot count, duration, camera permissions, reference mapping, identities, powers, audio and outcome instead. Do not copy these characters, terrain, attacks, shot count or any LoRA trigger. Intense links attacks with rapid re-entry. Unleashed also changes speed, travel and scale, within the genre.\n")
        + json.dumps(payload, ensure_ascii=False))
