"""Pure contracts for ordered image states and reviewed video transitions."""
from copy import deepcopy
import math
from uuid import uuid4

from .video_factory import configuration, fingerprint, timestamp, PLAN_MODEL, WRITER_MODEL
from .video_lab import VideoAspectRatio

KINDS = {"work": "Travaux", "cleaning": "Nettoyage", "installation": "Installation",
         "camera": "Déplacement caméra", "other": "Autre"}
MAX_IMAGES = 100


def identity(prefix):
    return f"{prefix}-{uuid4().hex}"


def defaults():
    return dict(duration=7.0, worker="Un ouvrier en jean bleu, tee-shirt blanc et casquette bleue.",
                pace="Captation fortement accélérée de toute l’action, gestes rapides et saccadés.",
                camera="Caméra fixe pour les travaux ; déplacement cohérent pour changer de lieu.",
                audio="Sons des outils et du lieu synchronisés aux actions, sans parole.",
                music=False, preserve="Préserver les éléments du décor qui ne sont pas concernés.",
                model_id=WRITER_MODEL, plan_model_id=PLAN_MODEL, writer_model_id=WRITER_MODEL,
                aspect_ratio="auto", dlss=False)


def clean_text(value, name, limit, required=False):
    if not isinstance(value, str) or len(value) > limit or required and not value.strip():
        raise ValueError(f"{name} invalide (maximum {limit} caractères).")
    return value.strip()


def duration(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 5 <= value <= 15:
        raise ValueError("La durée doit être comprise entre 5 et 15 secondes.")
    return float(value)


def settings(changes, base=None):
    result = deepcopy(base or defaults())
    if not isinstance(changes, dict) or set(changes) - set(result):
        raise ValueError("Réglage inconnu.")
    for key, value in changes.items():
        if key == "duration":
            value = duration(value)
        elif key in {"music", "dlss"}:
            if type(value) is not bool:
                raise ValueError("Activation invalide.")
        elif key == "aspect_ratio":
            if value != "auto":
                VideoAspectRatio(value)
        else:
            value = clean_text(value, key, 300 if key.endswith("model_id") else 2000,
                               required=key.endswith("model_id"))
        result[key] = value
    return result


def new_project(name):
    return dict(schema_version=1, id=identity("transitions"), name=clean_text(name, "Nom", 120) or "Transitions d’images",
                version=0, created_at=timestamp(), updated_at=timestamp(), settings=defaults(),
                frames=[], transitions=[], jobs=[], deliveries=[])


def active(project):
    pairs = list(zip(project["frames"], project["frames"][1:]))
    by_pair = {(t["left"], t["right"]): t for t in project["transitions"]}
    return [by_pair[(a["id"], b["id"])] for a, b in pairs]


def reconcile(project):
    known = {(t["left"], t["right"]) for t in project["transitions"]}
    for first, last in zip(project["frames"], project["frames"][1:]):
        pair = (first["id"], last["id"])
        if pair not in known:
            project["transitions"].append(dict(id=identity("transition"), left=pair[0], right=pair[1],
                action="", note="", intention="", kind="work", duration=None, camera="", pace="",
                observations="", uncertainties="", manual=False, suggestion=None,
                proposal_context=None, reviewed=None))
            known.add(pair)


def pair_frames(project, transition):
    by_id = {f["id"]: f for f in project["frames"]}
    return by_id[transition["left"]], by_id[transition["right"]]


def effective(project, transition):
    result = deepcopy(project["settings"])
    for key in ("duration", "camera", "pace"):
        if transition.get(key) not in ("", None):
            result[key] = transition[key]
    return result


def context_key(project, transition):
    first, last = pair_frames(project, transition)
    common = effective(project, transition)
    common.pop("model_id", None)  # Changing the proposer alone does not undo human review.
    return fingerprint(dict(first=first, last=last, settings=common,
        content={key: transition[key] for key in ("action", "note", "intention", "kind", "duration", "camera", "pace")}))


def status(project, transition):
    key = context_key(project, transition)
    if any(d["transition_id"] == transition["id"] and d["key"] == key and d.get("factory_id")
           for d in project["deliveries"]):
        return "sent"
    if transition["reviewed"] == key:
        return "ready"
    return "review" if transition["intention"].strip() else "empty"


def edit_transition(transition, changes):
    limits = dict(action=240, note=4000, intention=14000, camera=2000, pace=2000)
    if not isinstance(changes, dict) or set(changes) - {*limits, "duration", "kind"}:
        raise ValueError("Champ de transition inconnu.")
    for key, value in changes.items():
        if key == "duration":
            value = None if value is None else duration(value)
        elif key == "kind":
            if value not in KINDS:
                raise ValueError("Type de transition inconnu.")
        else:
            value = clean_text(value, key, limits[key])
        if transition[key] != value:
            transition[key] = value
            transition["reviewed"] = None
            if key in {"intention", "action"}:
                transition["manual"] = True


def factory_entry(project, transition, index):
    first, last = pair_frames(project, transition)
    options = effective(project, transition)
    config = configuration("h3")
    config.update(preset="custom", shot_count=1, cinematic_settings={"shot_count": 1},
                  plan_model_id=options["plan_model_id"], writer_model_id=options["writer_model_id"],
                  creative_audacity=1, creative_freedom=25,
                  creative_axes=dict(scene_life=1, camera=1, extra_motion=1, dialogue=0))
    config["references"] = [dict(asset_id=f["asset_id"], role=role, label=f["label"])
                            for f, role in ((first, "first_frame"), (last, "last_frame"))]
    seconds = options["duration"]
    config["intention"] = (
        f"Un seul plan continu de {seconds:g} secondes. Première image à 0 s, dernière image à {seconds:g} s.\n"
        f"Action : {transition['action']}\n{transition['intention']}\n"
        f"Indication utilisateur : {transition['note']}\n"
        f"Ouvrier, si nécessaire à cette action : {options['worker']}\n"
        f"Rythme : {options['pace']}\nCaméra : {options['camera']}\n"
        f"Son : {options['audio']}\nMusique : {'autorisée' if options['music'] else 'aucune'}.\n"
        f"Conservation : {options['preserve']}\n"
        "Respecter les états montrés aux deux extrémités. Pour les travaux, rendre les transformations "
        "causales : apport des matériaux, outil en contact, effet après le geste, évacuation des résidus. "
        "Si les images montrent le lieu vide, faire entrer puis sortir l’ouvrier et son matériel. "
        "Pour un déplacement de caméra, conserver la géographie du lieu sans inventer des travaux."
    )
    config["render"]["settings"]["duration_seconds"] = seconds
    ratio = options["aspect_ratio"]
    if ratio == "auto":
        width, height = first["dimensions"]
        ratio = min(VideoAspectRatio, key=lambda r: abs(math.log(
            (r.dimensions[0] / r.dimensions[1]) / (width / height)))).value
    config["render"]["settings"]["aspect_ratio"] = ratio
    config["render"]["music_enabled"] = options["music"]
    config["dlss"]["enabled"] = options["dlss"]
    return dict(name=f"{project['name']} · {index + 1} → {index + 2} · {transition['action']}"[:160],
                config=config, source=dict(kind="image_transition", id=project["id"],
                transition_id=transition["id"], version=context_key(project, transition), index=index,
                group=project["name"], view="image-transitions"))
