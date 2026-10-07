"""Pure contracts for a fixed-view, construction-oriented image journey."""
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
import re
from uuid import NAMESPACE_URL, uuid4, uuid5

MAX_IMAGES = 30
DEFAULT_IMAGES = 5
DEFAULT_JOURNEY_VERSION = "2"
DEFAULT_JOURNEY_DIRECTION = "forward"
JOURNEY_DIRECTIONS = {"forward": "Construction", "reverse": "À rebours"}
JOURNEY_VERSIONS = {"1": "V1 — Actuelle", "2": "V2 — Scène vivante"}
DEFAULT_MASK_MODEL_ID = "local::unsloth/Qwen3.8-27B-GGUF"
JOURNEY_PRESETS = {"miniature": "Miniature", "realistic": "Aménagement réaliste"}
PRESET = "construction"
ACTIVE = {"running", "pausing"}


def journey_version(record):
    """Old journals retain V1 without a write or an implicit migration."""
    value = record.get("journey_version", "1")
    if not isinstance(value, str) or value not in JOURNEY_VERSIONS:
        raise ValueError("Version du parcours invalide : choisis V1 ou V2.")
    return value


def journey_direction(record):
    """Missing direction is the historical forward construction behavior."""
    value = record.get("journey_direction", DEFAULT_JOURNEY_DIRECTION)
    if not isinstance(value, str) or value not in JOURNEY_DIRECTIONS:
        raise ValueError("Sens du parcours invalide : choisis Construction ou À rebours.")
    return value


def journey_preset(record):
    """Missing preset keeps every historical journey on its original policies."""
    value = record.get("journey_preset", "miniature")
    if not isinstance(value, str) or value not in JOURNEY_PRESETS:
        raise ValueError("Preset invalide : choisis Miniature ou Aménagement réaliste.")
    return value


def finished_label(record):
    return "Aménagement terminé" if journey_preset(record) == "realistic" else "Bâtiment terminé"


def direction_snapshot(project):
    values = dict(journey_direction=journey_direction(project))
    if "journey_preset" in project:
        values["journey_preset"] = journey_preset(project)
    if values["journey_direction"] == "reverse":
        # The prepared original stays fixed, never the latest generated state.
        values["finished_reference_asset_id"] = project["source_asset_id"]
    return values


def timestamp():
    return datetime.now(UTC).isoformat()


def identity(prefix):
    return f"{prefix}-{uuid4().hex}"


def text(value, label, limit, required=False):
    if not isinstance(value, str) or len(value) > limit or required and not value.strip():
        raise ValueError(f"{label} invalide (maximum {limit} caractères).")
    return value.strip()


def request_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise ValueError("Identifiant de commande invalide.")
    return value


def project_id(command):
    return "journey-" + uuid5(NAMESPACE_URL, "panelforge/image-journey/" + request_id(command)).hex


def configuration(intention, count, progression_model_id, prompt_model_id, mask_model_id=None):
    if type(count) is not int or not 1 <= count <= MAX_IMAGES:
        raise ValueError(f"Choisis de 1 à {MAX_IMAGES} nouvelles images.")
    config = dict(intention=text(intention, "Intention", 6000), count=count,
                progression_model_id=text(progression_model_id, "Modèle de progression", 300, True),
                prompt_model_id=text(prompt_model_id, "Modèle MiniMax", 300, True))
    # Omission preserves legacy callers and their progression-model fallback.
    if mask_model_id is not None:
        config["mask_model_id"] = text(mask_model_id, "Modèle d’analyse du masque", 300, True)
    return config


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def new_project(command, config, source_asset_id, dimensions, creation_key):
    return dict(schema_version=1, id=project_id(command), version=0, preset=PRESET,
                name=config["intention"][:100] or "Parcours de travaux", **config,
                created_at=timestamp(), updated_at=timestamp(), creation_key=creation_key,
                source_asset_id=source_asset_id, source_dimensions=list(dimensions),
                current_asset_id=source_asset_id, status="running", phase="planning",
                pause_requested=False, error=None, warning=None, intent_revision=0,
                plan_revision=None, destination="", milestones=[], completed_milestones=0,
                summary="", next_action=None, steps=[], abandoned_steps=[], analyses=[],
                commands=[], transition_exports={})


def generated(project):
    return sum(bool(s.get("output_asset_id")) for s in project["steps"])


def ordered_steps(project):
    """Display order is independent of the original automatic generation budget."""
    steps = [*project['steps'], *project.get('manual_steps', [])]
    lookup = {step['id']: step for step in steps}
    order = project.get('sequence_order', [])
    return [lookup[key] for key in order if key in lookup] + [step for step in steps if step['id'] not in order]


def transferable_frame_ids(project):
    """Explicit frame identities, including reviewed states after an excluded gap."""
    return ['source', *[step['id'] for step in ordered_steps(project)
                       if step.get('output_asset_id') and
                       (step.get('review') or {}).get('assessment') in {'usable', 'similar'}]]


def sequence(project, frame_ids=None, *, frame_order="generation"):
    """Reviewed states in an explicit order; defaults preserve historical exports."""
    if frame_order not in ("generation", "reverse_generation"):
        raise ValueError("L’ordre des images pour les transitions est invalide.")
    available = set(transferable_frame_ids(project))
    selected = None
    if frame_ids is not None:
        if not isinstance(frame_ids, list) or len(frame_ids) < 2:
            raise ValueError('Sélectionne au moins deux images pour préparer les transitions.')
        if any(not isinstance(identity, str) or identity not in available for identity in frame_ids):
            raise ValueError('Une image sélectionnée est introuvable ou pas encore disponible pour les transitions.')
        selected = set(frame_ids)
        if len(selected) != len(frame_ids):
            raise ValueError('Chaque image ne peut être sélectionnée qu’une fois.')
    frames = [dict(asset_id=project["source_asset_id"], label="Départ",
                   origin=dict(engine="image-journey", project_id=project["id"], index=0))]
    for index, step in enumerate(ordered_steps(project), 1):
        if step['id'] not in available:
            if selected is None:
                break
            continue
        frames.append(dict(asset_id=step["output_asset_id"], label=step["action"]["title"],
            origin=dict(engine="image-journey", project_id=project["id"], step_id=step["id"],
                        index=index, source_asset_id=step["source_asset_id"],
                        action=step["action"]["change"], observation=step["review"]["observation"])))
    if selected is not None:
        frames = [frame for frame in frames if frame['origin'].get('step_id', 'source') in selected]
    if frame_order == "reverse_generation":
        frames.reverse()
        # Origin indexes remain generation identities, independent of export positions.
        if journey_direction(project) == "reverse":
            for frame in frames:
                if frame["origin"]["index"] == 0:
                    frame["label"] = finished_label(project)
    if journey_preset(project) == "realistic":
        for frame in frames:
            frame["origin"].update(journey_preset="realistic", journey_direction=journey_direction(project))
            if frame["origin"]["index"] == 0:
                frame["label"] = finished_label(project)
    return dict(schema_version=1, project_id=project["id"], destination=project["destination"], frames=frames)


def plan_locked(project):
    return bool(project["milestones"] and project["plan_revision"] == project["intent_revision"])


def reverse_endpoint_reached(project, decision):
    """A real, accepted endpoint can finish reverse generation before its image budget."""
    if (journey_direction(project) != "reverse" or not generated(project)
            or not decision["milestones"]
            or decision["completed_milestones"] != len(decision["milestones"])):
        return False
    tail = ordered_steps(project)[-1]
    # A manual tail may represent a different state than the automatic image being reviewed.
    if tail.get("manual") or tail["id"] != project["steps"][-1]["id"] or not tail.get("output_asset_id"):
        return False
    if project["phase"] == "reviewing":
        return decision["assessment"] in {"usable", "similar"}
    # Recover old planning checkpoints only when this same source was already accepted.
    return (project["phase"] in {"planning", "ready"} and decision["assessment"] == "initial"
            and plan_locked(project) and project["completed_milestones"] == len(project["milestones"])
            and project["current_asset_id"] == tail["output_asset_id"]
            and (tail.get("review") or {}).get("assessment") in {"usable", "similar"})


def validate_decision(value, project, *, allow_missing_next=False):
    fields = {"destination", "milestones", "completed_milestones", "summary", "observation", "assessment", "next_action"}
    reverse = journey_direction(project) == "reverse"
    result = deepcopy(value)
    if reverse and plan_locked(project) and isinstance(result, dict):
        # The saved plan is authoritative. Old models may still echo these fields;
        # their prose is not a command to replace the plan or renumber its milestones.
        result.update(destination=project["destination"], milestones=deepcopy(project["milestones"]))
    if not isinstance(result, dict) or set(result) != fields:
        raise ValueError("La progression doit contenir un cap, des jalons et une décision structurée.")
    for key, limit in (("destination", 1000), ("summary", 4000), ("observation", 4000)):
        result[key] = text(result[key], key, limit, True)
    milestones = result["milestones"]
    if not isinstance(milestones, list) or not 1 <= len(milestones) <= 20:
        raise ValueError("Le chantier doit avoir de 1 à 20 grands jalons ordonnés.")
    result["milestones"] = [text(m, "Jalon", 500, True) for m in milestones]
    if len(set(result["milestones"])) != len(milestones):
        raise ValueError("Les jalons doivent être distincts.")
    done = result["completed_milestones"]
    if type(done) is not int or not 0 <= done <= len(milestones):
        raise ValueError("Avancement des jalons invalide.")
    if plan_locked(project):
        if result["milestones"] != project["milestones"] or result["destination"] != project["destination"]:
            raise ValueError("Le cap et les jalons restent fixes jusqu’à une modification de l’intention.")
    assessment = result["assessment"]
    if assessment not in {"initial", "usable", "similar", "unusable"}:
        raise ValueError("Constat visuel invalide.")
    reviewing = project["phase"] == "reviewing"
    if reviewing and assessment == "initial":
        raise ValueError("Le résultat généré doit recevoir une véritable relecture.")
    if not reviewing and assessment != "initial":
        raise ValueError("La préparation de la prochaine étape doit utiliser le statut initial, sans relire un nouveau résultat.")
    remaining = project["count"] - generated(project)
    action = result["next_action"]
    if reverse_endpoint_reached(project, result):
        # Do not render a no-op or any other proposal after the observed endpoint.
        result["next_action"] = None
    elif remaining == 0 or assessment == "unusable":
        if action is not None:
            raise ValueError("La relecture finale ou bloquante ne doit pas demander une image supplémentaire.")
    elif action is None and reviewing and allow_missing_next:
        # A valid image review remains useful even when the model prematurely ends the plan.
        # The application persists it, then asks for the remaining action in a planning call.
        pass
    else:
        if not isinstance(action, dict) or set(action) != {"title", "change", "preserve", "through_milestone"}:
            raise ValueError("La prochaine transformation est manquante ou invalide.")
        for key, limit in (("title", 160), ("change", 4000), ("preserve", 2000)):
            action[key] = text(action[key], key, limit, True)
        through = action["through_milestone"]
        minimum = done if reverse else min(len(milestones), done + 1)
        maximum = len(milestones) - (1 if reverse and remaining > 1 else 0)
        if type(through) is not int or not minimum <= through <= maximum:
            if reverse and type(through) is int and through == len(milestones) and remaining > 1:
                if journey_preset(project) == "realistic":
                    raise ValueError("Réserve l’état de départ à la dernière image : conserve encore une partie visible de l’aménagement.")
                raise ValueError("Réserve le terrain dégagé à la dernière image : propose un retrait partiel en conservant une structure visible.")
            raise ValueError("La prochaine transformation doit respecter l’ordre des jalons.")
    return result
