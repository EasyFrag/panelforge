"""Pure contracts for a fixed-view, construction-oriented image journey."""
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
import re
from uuid import NAMESPACE_URL, uuid4, uuid5

MAX_IMAGES = 30
DEFAULT_IMAGES = 5
PRESET = "construction"
ACTIVE = {"running", "pausing"}


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


def configuration(intention, count, progression_model_id, prompt_model_id):
    if type(count) is not int or not 1 <= count <= MAX_IMAGES:
        raise ValueError(f"Choisis de 1 à {MAX_IMAGES} nouvelles images.")
    return dict(intention=text(intention, "Intention", 6000), count=count,
                progression_model_id=text(progression_model_id, "Modèle de progression", 300, True),
                prompt_model_id=text(prompt_model_id, "Modèle MiniMax", 300, True))


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


def sequence(project):
    """Versioned handoff of reviewed states; no video intentions are implied."""
    frames = [dict(asset_id=project["source_asset_id"], label="Départ",
                   origin=dict(engine="image-journey", project_id=project["id"], index=0))]
    for index, step in enumerate(ordered_steps(project), 1):
        if (step.get("review") or {}).get("assessment") not in {"usable", "similar"}:
            break
        frames.append(dict(asset_id=step["output_asset_id"], label=step["action"]["title"],
            origin=dict(engine="image-journey", project_id=project["id"], step_id=step["id"],
                        index=index, source_asset_id=step["source_asset_id"],
                        action=step["action"]["change"], observation=step["review"]["observation"])))
    return dict(schema_version=1, project_id=project["id"], destination=project["destination"], frames=frames)


def validate_decision(value, project, *, allow_missing_next=False):
    fields = {"destination", "milestones", "completed_milestones", "summary", "observation", "assessment", "next_action"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("La progression doit contenir un cap, des jalons et une décision structurée.")
    result = deepcopy(value)
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
    if project["milestones"] and project["plan_revision"] == project["intent_revision"]:
        if result["milestones"] != project["milestones"] or result["destination"] != project["destination"]:
            raise ValueError("Le cap et les jalons restent fixes jusqu’à une modification de l’intention.")
    assessment = result["assessment"]
    if assessment not in {"initial", "usable", "similar", "unusable"}:
        raise ValueError("Constat visuel invalide.")
    reviewing = project["phase"] == "reviewing"
    if (reviewing and assessment == "initial") or (not reviewing and assessment != "initial"):
        raise ValueError("Le résultat généré doit recevoir une véritable relecture.")
    remaining = project["count"] - generated(project)
    action = result["next_action"]
    if remaining == 0 or assessment == "unusable":
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
        if type(through) is not int or not min(len(milestones), done + 1) <= through <= len(milestones):
            raise ValueError("La prochaine transformation doit respecter l’ordre des jalons.")
    return result
