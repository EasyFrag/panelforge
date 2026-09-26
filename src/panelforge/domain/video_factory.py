"""Pure contracts and scheduling rules for the video factory."""
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
from uuid import uuid4

from .episodes import default_render_setup

STAGES = ("plan", "prompt", "video", "dlss", "social")
LABELS = dict(plan="Plan", prompt="Prompt", video="Vidéo", dlss="DLSS", social="Texte IG")
DEPENDENCIES = dict(plan=(), prompt=("plan",), video=("prompt",), dlss=("video",), social=("video",))
TERMINAL = {"succeeded", "skipped", "failed", "cancelled"}
PRESETS = {"source": "Réglages source", "lips": "Lèvres", "little_men": "Petits hommes", "custom": "Personnalisé"}
ROLES = {
    "unassigned": "Rôle à choisir",
    "first_frame": "Première frame", "last_frame": "Dernière frame",
    "subject_reference": "Sujet / identité", "environment_reference": "Décor",
    "style_reference": "Style", "composition_reference": "Composition",
    "motion_reference": "Mouvement", "keyframe_reference": "Keyframe",
}
ROLE_USES = {**{key: key.removesuffix("_reference") for key in ROLES},
             "keyframe_reference": "keyframe"}
PLAN_MODEL = "local::unsloth/Qwen3.8-27B-GGUF"
WRITER_MODEL = "local::unsloth/gemma-4-31B-it-qat-GGUF"
LIPS_INTENT = ("Gros plan sur les lèvres. Un seul plan continu, un mouvement lent et naturel. "
               "Rejoindre l’image de fin en conservant l’identité, la lumière et les textures.")
LITTLE_MEN_INTENT = (
    "Sur un plan de 8 secondes, les petits hommes tentent de résoudre le problème visible "
    "dans l’image. Une main géante arrive du ciel et intervient pour les aider. "
    "Les petits hommes observent la main avec attention et étonnement. "
    'Une fois son travail accompli, la main repart vers le haut. '
    'Les petits hommes lèvent les bras vers le ciel et acclament la main : "thank you".'
)


def timestamp():
    return datetime.now(UTC).isoformat()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def configuration(mode="h3"):
    return dict(mode=mode, preset="source", preset_origin=None, intention="", final_prompt="",
                references=[], shot_count=None, plan_model_id=PLAN_MODEL, writer_model_id=WRITER_MODEL,
                profile={"id": f"minimax.h3.{'fl2va' if mode == 'h3' else 'ref2v'}.classic.cinematic", "version": "1.0.0"},
                cookbook={"id": f"minimax.h3.{'fl2va' if mode == 'h3' else 'ref2v'}.classic.cinematic.planned", "version": "1.0.0"},
                creative_axes=dict(scene_life=3, camera=3, extra_motion=3, dialogue=1),
                creative_audacity=3, creative_freedom=90,
                cinematic_settings={"shot_count": None}, combat_settings=None, sensual_settings=None,
                brief_variant_id=None, brief_variant_version=None,
                render=default_render_setup(8), dlss={"enabled": False},
                social=dict(enabled=False, language="en", variant_count=3, model_id=WRITER_MODEL))


def merge_settings(base, changes):
    result = deepcopy(base)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_settings(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def apply_preset(config, preset, source):
    if preset not in PRESETS:
        raise ValueError("Preset inconnu.")
    if preset == "source":
        return deepcopy(source)
    result = deepcopy(config)
    if preset == "custom":
        result["preset"] = preset
        return result
    if len(result["references"]) != 1:
        raise ValueError("Ce preset attend une seule image. Ajustez la sélection avant de l’appliquer.")
    fresh = configuration()
    for key in ("profile", "cookbook", "cinematic_settings", "combat_settings", "sensual_settings",
                "brief_variant_id", "brief_variant_version", "plan_model_id", "writer_model_id",
                "creative_axes", "creative_audacity", "creative_freedom", "render"):
        result[key] = fresh[key]
    result.update(mode="h3", preset=preset, preset_origin=preset, shot_count=1,
                  final_prompt="", intention=LIPS_INTENT if preset == "lips" else LITTLE_MEN_INTENT)
    result["cinematic_settings"] = {"shot_count": 1}
    for ref in result["references"]:
        ref["role"] = "last_frame" if preset == "lips" else "first_frame"
    return result


def validate_shape(config):
    if set(config) - set(configuration()):
        raise ValueError("Champ de configuration inconnu.")
    for key in ("profile", "cookbook", "creative_axes", "render", "dlss", "social"):
        if not isinstance(config.get(key), dict):
            raise ValueError(f"Réglage {key} invalide.")
    for key in ("plan_model_id", "writer_model_id"):
        if not isinstance(config.get(key), str) or len(config[key]) > 300:
            raise ValueError("Identifiant de modèle invalide.")
    for key in ("profile", "cookbook"):
        if set(config[key]) != {"id", "version"} or not all(isinstance(v, str) and v for v in config[key].values()):
            raise ValueError("Recette de préparation invalide.")
    if config["mode"] not in {"h3", "ref2v"} or config["preset"] not in PRESETS:
        raise ValueError("Mode ou preset inconnu.")
    for key in ("intention", "final_prompt"):
        if not isinstance(config[key], str) or len(config[key]) > 60000:
            raise ValueError("Texte trop long ou invalide.")
    count = config["shot_count"]
    if count is not None and (type(count) is not int or not 1 <= count <= 6):
        raise ValueError("Nombre de plans : Auto ou 1 à 6.")
    refs = config["references"]
    if not isinstance(refs, list) or len(refs) > 9:
        raise ValueError("Neuf références au maximum.")
    for ref in refs:
        if not isinstance(ref, dict) or ref.get("role") not in ROLES:
            raise ValueError("Rôle d’image invalide.")
        if not isinstance(ref.get("asset_id"), str) or not ref["asset_id"].startswith("asset-"):
            raise ValueError("Image invalide.")
    if type(config["creative_audacity"]) is not int or not 0 <= config["creative_audacity"] <= 3:
        raise ValueError("Audace : 0 à 3.")
    if type(config["creative_freedom"]) is not int or not 0 <= config["creative_freedom"] <= 100:
        raise ValueError("Liberté créative : 0 à 100.")
    social = config["social"]
    if not isinstance(social.get("model_id"), str) or not social["model_id"].strip():
        raise ValueError("Modèle Instagram manquant.")
    if type(social.get("enabled")) is not bool or social.get("language") not in {"en", "fr"}:
        raise ValueError("Langue Instagram : anglais ou français.")
    if type(social.get("variant_count")) is not int or not 1 <= social["variant_count"] <= 6:
        raise ValueError("Instagram : 1 à 6 variantes.")
    if type(config["dlss"].get("enabled")) is not bool:
        raise ValueError("Activation DLSS invalide.")
    fingerprint(config)


def readiness(config):
    errors = []
    if not config["intention"].strip() and not config["final_prompt"].strip():
        errors.append("Renseigner l’intention ou le prompt final.")
    if any(ref["role"] == "unassigned" for ref in config["references"]):
        errors.append("Attribuer un rôle à chaque image.")
    if config["mode"] == "h3":
        roles = [ref["role"] for ref in config["references"]]
        if any(role not in {"first_frame", "last_frame"} for role in roles):
            errors.append("H3 attend une première et/ou dernière frame.")
        if len(roles) != len(set(roles)):
            errors.append("Une seule image par rôle de frame.")
    elif not config["references"]:
        errors.append("Associer au moins une référence REF2V.")
    if not config.get("plan_model_id") or not config.get("writer_model_id"):
        errors.append("Choisir les modèles de préparation.")
    return errors


def new_item(name, config, source, dedupe_key):
    validate_shape(config)
    return dict(id=f"factory-{uuid4().hex}", kind="video", name=name[:160],
                revision=1, created_at=timestamp(), updated_at=timestamp(),
                status="preparation", config=deepcopy(config), source_config=deepcopy(config),
                source=deepcopy(source), dedupe_key=dedupe_key, runtime={}, steps=initial_steps(config),
                cancel_requested=False, waiting_reason=None, history=[])


def initial_steps(config):
    result = {stage: dict(status="pending", error=None, progress=None, output={}) for stage in STAGES}
    if config.get("final_prompt", "").strip():
        result["plan"]["status"] = "skipped"
        result["prompt"].update(status="succeeded", output={"text": config["final_prompt"]})
    for stage in ("dlss", "social"):
        if not config[stage]["enabled"]:
            result[stage]["status"] = "skipped"
    return result


def next_steps(item):
    if item["status"] not in {"queued", "active"} or item["cancel_requested"]:
        return []
    return [stage for stage in STAGES if item["steps"][stage]["status"] == "pending"
            and all(item["steps"][dep]["status"] in {"succeeded", "skipped"}
                    for dep in DEPENDENCIES[stage])]


def settle(item):
    if item["cancel_requested"]:
        if not any(step["status"] == "running" for step in item["steps"].values()):
            item["status"] = "cancelled"
        return
    # Terminal failures block only dependent branches; independent finishing still runs.
    for stage in STAGES:
        if item["steps"][stage]["status"] == "pending" and any(
                item["steps"][dep]["status"] in {"failed", "cancelled"} for dep in DEPENDENCIES[stage]):
            item["steps"][stage].update(status="cancelled", error="Étape précédente à reprendre.")
    statuses = {step["status"] for step in item["steps"].values()}
    if statuses <= TERMINAL:
        item["status"] = "failed" if "failed" in statuses else "cancelled" if "cancelled" in statuses else "succeeded"
    else:
        item["status"] = "active" if "running" in statuses else "queued"


def stage_signature(config, stage):
    keys = set(config) - {"preset", "preset_origin", "render", "dlss", "social"}
    if stage in {"video", "dlss", "social"}:
        keys.add("render")
    if stage in {"dlss", "social"}:
        keys.add(stage)
    return fingerprint({key: config[key] for key in keys})


def invalidate(item, before):
    """Invalidate only outputs depending on changed inputs."""
    after = item["config"]
    changed = {key for key in after if after[key] != before.get(key)}
    content = changed - {"preset", "preset_origin", "render", "dlss", "social"}
    affected = set(STAGES) if content else set()
    if "render" in changed:
        affected.update(("video", "dlss", "social"))
    if "dlss" in changed:
        affected.add("dlss")
    if "social" in changed:
        affected.add("social")
    defaults = initial_steps(after)
    for stage in STAGES:
        if stage not in affected:
            continue
        if item["steps"][stage]["status"] == "succeeded":
            item["history"].append({"stage": stage, "output": deepcopy(item["steps"][stage]["output"]),
                                    "at": timestamp(), "input_hash": stage_signature(before, stage),
                                    "runtime": deepcopy(item["runtime"])})
        item["steps"][stage] = defaults[stage]
    if content:
        item["runtime"] = {}
    else:
        for key in (("attempt_id", "render_project_id") if "render" in changed else ()):
            item["runtime"].pop(key, None)
        if "dlss" in affected:
            item["runtime"].pop("dlss_job_id", None)
        if "social" in affected:
            item["runtime"].pop("social_project_id", None)
    # Undoing an edit can restore a matching output, without paying for it again.
    for stage in STAGES:
        if stage not in affected or defaults[stage]["status"] != "pending":
            continue
        saved = next((entry for entry in reversed(item["history"]) if entry["stage"] == stage
                      and entry.get("input_hash") == stage_signature(after, stage)), None)
        if saved is None:
            continue
        item["steps"][stage].update(status="succeeded", output=deepcopy(saved["output"]))
        keys = {"session_id", "source_session_id", "saved_plan", "saved_reference_plan", "episode_inputs", "episode_preparation_id"}
        if stage == "video":
            keys.update(("render_project_id", "attempt_id"))
        if stage == "dlss":
            keys = {"dlss_job_id"}
        if stage == "social":
            keys = {"social_project_id"}
        item["runtime"].update({key: deepcopy(value) for key, value in saved.get("runtime", {}).items() if key in keys})
    return affected
