"""Opt-in writing policy. Saved stories without this version retain their behavior."""
from copy import deepcopy

VERSION = 1
REVIEW_CATEGORIES = ("clarity", "fidelity", "continuity", "speech_estimate", "style", "other")
DEFAULTS = dict(dialogue_style="natural", dialogue_notes="", dialogue_pace="fast",
                visual_render="story", visual_notes="", protected_lines=[],
                tone_profile="none", glossary="")
RENDERS = {
    "story": "",
    "animation_3d": "Animation 3D expressive, personnages et décors cohérents dans toutes les images.",
    "live_action": "Film en prises de vues réelles, matières et éclairage cinématographiques. Les humains sont des acteurs photoréalistes ; les créatures sont adaptées comme dans un film live action. Préserver les traits et espèces demandés, sans aspect de dessin animé.",
    "custom": "",
}


def enabled(project):
    return project.get("story_quality_version") == VERSION


def normalize(value=None):
    if value is not None and not isinstance(value, dict):
        raise ValueError("Direction d’écriture invalide.")
    value = value or {}
    if set(value) - set(DEFAULTS):
        raise ValueError("Réglage de direction inconnu.")
    result = deepcopy(DEFAULTS)
    result.update(value)
    for key, allowed in (("dialogue_style", {"natural", "street", "custom"}),
                         ("dialogue_pace", {"natural", "fast"}), ("visual_render", set(RENDERS)),
                         ("tone_profile", {"none", "black_comedy_street_v1"})):
        if not isinstance(result[key], str) or result[key] not in allowed:
            raise ValueError(f"Choix invalide pour {key}.")
    for key in ("dialogue_notes", "visual_notes", "glossary"):
        if not isinstance(result[key], str) or len(result[key]) > 2000:
            raise ValueError("Une direction doit tenir dans 2 000 caractères.")
        result[key] = result[key].strip()
    lines = result["protected_lines"]
    if (not isinstance(lines, list) or len(lines) > 24 or
            any(not isinstance(line, str) or not line.strip() or len(line) > 1500 for line in lines)):
        raise ValueError("Indique au plus 24 répliques exactes de 1 à 1 500 caractères.")
    result["protected_lines"] = list(dict.fromkeys(line.strip() for line in lines))
    return result


def settings(project):
    saved = project.get("writing_direction")
    result = normalize(saved)
    # These values participate in saved review/dependency hashes. Adding absent
    # optional defaults would invalidate every existing quality-v1 story.
    for key in ("tone_profile", "glossary"):
        if key not in (saved or {}):
            result.pop(key)
    return result


def for_followup(project):
    direction = settings(project)
    # Directions persist; exact lines belonged to the previous episode, not the sequel.
    direction["protected_lines"] = []
    return direction


def words_per_second(project):
    return 4.8 if enabled(project) and settings(project)["dialogue_pace"] == "fast" else 2.4


def speech_budget(project):
    return dict(pace=settings(project)["dialogue_pace"], words_per_second_estimate=words_per_second(project),
        advisory_only=True,
        rule="Estimation empirique, pas un quota ni une capacité vidéo garantie. Compter seulement les pauses, réactions et actions réellement successives dans action_seconds ; les gestes simultanés à la parole ne s’ajoutent pas. Préserver les changements de locuteur. Répartir les moments utiles dans les clips disponibles avant de supprimer un gag ou une réplique imposée. Un dépassement estimé seul ne bloque pas et ne justifie pas une réécriture.")


def visual_style(project):
    direction = settings(project)
    return " ".join(part for part in (RENDERS[direction["visual_render"]], direction["visual_notes"]) if part)


def voice_instruction(project):
    if settings(project)["dialogue_pace"] == "fast":
        return "Débit vocal rapide et articulé (repère indicatif : 4,8 mots/s), échanges vifs ; gestes simples simultanés aux paroles. Préserver les mots exacts, les changements de locuteur et les réactions indispensables. Ne pas ajouter de sous-titres à l’image."
    return "Débit vocal naturel et articulé ; conserver les répliques exactes et les pauses expressives utiles."


def unit_requirements(project, identity):
    """Only the current unit's public evidence; never the bible or future secrets."""
    units = (project["document"].get("series_outline") or {}).get("episodes", [])
    unit = next((unit for unit in units if unit["id"] == identity), {})
    events = [dict(event_id=event["id"], evidence=event["evidence"]) for event in unit.get("events", [])]
    from .story_editions import refined
    if refined(project) and "author_line_assignments" in (project["document"].get("series_outline") or {}):
        from .story_exact_lines import catalog
        sources = {row["id"]: row["text"] for row in catalog(project)}
        # Diagnostics and UI must remain readable after source edits. The
        # writing contract validates the complete attribution before any call.
        rows = project["document"]["series_outline"]["author_line_assignments"]
        return dict(unit_id=identity, required_on_screen=events, protected_lines=[sources[row["line_id"]]
            for row in rows if row["unit_id"] == identity and row["line_id"] in sources])
    required = settings(project)["protected_lines"]
    # Conception assigns exact lines to public evidence. Single-unit stories need no assignment.
    lines = [line for line in required if len(units) == 1 or any(line in event["evidence"] for event in events)]
    return dict(unit_id=identity, required_on_screen=events, protected_lines=lines)
