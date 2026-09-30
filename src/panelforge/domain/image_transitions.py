"""Pure contracts for ordered image states and reviewed video transitions."""
from copy import deepcopy
import math
from uuid import uuid4

from .video_factory import configuration, fingerprint, timestamp, PLAN_MODEL, WRITER_MODEL
from .video_lab import VideoAspectRatio
from .worker_visual_policy import VERSION as VISUAL_WORKER_VERSION, WorkerVisualPolicy
from .image_transition_references import CREWS, crew_contract, reference_state, require_references

KINDS = {"work": "Travaux", "cleaning": "Nettoyage", "installation": "Installation",
         "camera": "Déplacement caméra", "other": "Autre"}
MAX_IMAGES = 100

PACE_PRESETS = {
    "slow": dict(
        label="Slow — accéléré modéré",
        description="Progression posée, gestes fluides et travaux lisibles.",
        pace="La captation entière est modérément accélérée. Les déplacements et gestes restent fluides, "
             "lisibles et continus ; quelques opérations essentielles montrent la progression du chantier. "
             "Les sons des outils suivent ce rythme mesuré. Conserver un bref départ et une brève arrivée "
             "conformes aux deux images, dans la durée choisie.",
        h3_guidance="Describe the whole shot as a moderately accelerated recording with fluid, readable motion. "
                    "Use a few clear work beats across the supplied duration, with measured synchronized tool sounds. "
                    "Keep the first and last states exact. Slow is the gentler preset, not slow motion."),
    "fast": dict(
        label="Fast — avance rapide",
        description="Time-lapse très accéléré : sauts de pose, gestes saccadés et sons en rafales.",
        pace="Toute la séquence ressemble à une captation de chantier passée en avance rapide extrême, "
             "un time-lapse fortement comprimé. Les gestes et déplacements se succèdent par rafales "
             "saccadées : changements de pose et de position entre les instants, comme des images sautées, "
             "avec un bref flou des membres et des outils. Plusieurs opérations successives font avancer "
             "visiblement les travaux par bonds causés par les gestes. Les mouvements déjà présents dans "
             "le décor suivent la même compression temporelle. Les impacts et frottements des outils "
             "deviennent des impulsions sonores brèves et rapprochées. L’entrée et la sortie sont expéditives ; "
             "seuls le tout début et la toute fin marquent brièvement les états de référence.",
        h3_guidance="Make global time compression explicit at the start of the shot description: "
                    "'aggressively fast-forwarded time-lapse', 'staccato, frame-jumping beats', abrupt pose "
                    "and position changes with brief limb/tool motion blur, as if frames were dropped. "
                    "Carry this through several short timed beats distributed across the supplied duration "
                    "and through compressed, closely spaced tool-sound pulses. Compress the recording, not "
                    "just the worker's effort. Preserve the requested camera path in one continuous shot; "
                    "temporal skips are not camera cuts or magical self-assembly. Accelerate existing "
                    "environmental motion when visible, without inventing clouds or moving scenery. "
                    "Reach the exact last image only at the closing instant, without a long idle finish.")
}


def pace_presets():
    return [dict(id=key, **{field: preset[field] for field in ("label", "description", "pace")})
            for key, preset in PACE_PRESETS.items()]


def temporal_contract(options):
    """Only an explicitly selected preset adds new preparation instructions."""
    key = options.get("pace_preset")
    if key not in PACE_PRESETS:
        return None
    return dict(version="1.0.0", preset=key, **deepcopy(PACE_PRESETS[key]))


def identity(prefix):
    return f"{prefix}-{uuid4().hex}"


def defaults():
    return dict(duration=7.0,
                worker="Un ouvrier en jean bleu, tee-shirt blanc et casquette bleue.",
                crew_size="solo",
                pace_preset="fast", pace=PACE_PRESETS["fast"]["pace"],
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
    if not isinstance(changes, dict) or set(changes) - set(defaults()):
        raise ValueError("Réglage inconnu.")
    for key, value in changes.items():
        if key == "duration":
            value = duration(value)
        elif key in {"music", "dlss"}:
            if type(value) is not bool:
                raise ValueError("Activation invalide.")
        elif key == "crew_size":
            if not isinstance(value, str) or value not in CREWS:
                raise ValueError("Organisation du chantier inconnue.")
        elif key == "pace_preset":
            if not isinstance(value, str) or value not in {*PACE_PRESETS, "custom"}:
                raise ValueError("Preset de rythme inconnu.")
        elif key == "aspect_ratio":
            if value != "auto":
                VideoAspectRatio(value)
        else:
            value = clean_text(value, key, 300 if key.endswith("model_id") else 2000,
                               required=key.endswith("model_id"))
        result[key] = value
    selected = changes.get("pace_preset")
    if selected in PACE_PRESETS:
        canonical = PACE_PRESETS[selected]["pace"]
        if "pace" in changes and result["pace"] != canonical:
            raise ValueError("Pour un rythme libre, choisis le preset Personnalisé.")
        result["pace"] = canonical
    elif "pace" in changes and "pace_preset" not in changes:
        current = result.get("pace_preset")
        if current not in PACE_PRESETS or result["pace"] != PACE_PRESETS[current]["pace"]:
            result["pace_preset"] = "custom"
    # Legacy settings retain their exact shape until the user changes their rhythm.
    return result


def new_project(name):
    return dict(schema_version=1, id=identity("transitions"), name=clean_text(name, "Nom", 120) or "Transitions d’images",
                version=0, created_at=timestamp(), updated_at=timestamp(), settings=defaults(),
                frames=[], transitions=[], jobs=[], deliveries=[])


def active(project):
    pairs = list(zip(project["frames"], project["frames"][1:]))
    by_pair = {(t["left"], t["right"]): t for t in project["transitions"]}
    return [by_pair[(a["id"], b["id"])] for a, b in pairs]


def reconcile(project, *, inherit_scale=False):
    previous = None
    known = {(t["left"], t["right"]) for t in project["transitions"]}
    for first, last in zip(project["frames"], project["frames"][1:]):
        pair = (first["id"], last["id"])
        if pair not in known:
            project["transitions"].append(dict(id=identity("transition"), left=pair[0], right=pair[1],
                action="", note="", intention="", kind="work", duration=None, camera="", pace="",
                observations="", uncertainties="", manual=False, suggestion=None,
                proposal_context=None, reviewed=None))
            if inherit_scale and previous and previous.get("scale_setup_id") and previous["kind"] != "camera":
                project["transitions"][-1]["scale_setup_id"] = previous["scale_setup_id"]
            known.add(pair)
        previous = next(t for t in project["transitions"] if (t["left"], t["right"]) == pair)


def pair_frames(project, transition):
    by_id = {f["id"]: f for f in project["frames"]}
    return by_id[transition["left"]], by_id[transition["right"]]


def effective(project, transition):
    result = deepcopy(project["settings"])
    for key in ("duration", "camera", "pace"):
        if transition.get(key) not in ("", None):
            result[key] = transition[key]
            if key == "pace":
                # A per-pair free-text override replaces the common preset completely.
                result.pop("pace_preset", None)
    return result


def context_key(project, transition):
    first, last = pair_frames(project, transition)
    common = effective(project, transition)
    common.pop("model_id", None)  # Changing the proposer alone does not undo human review.
    if project.get("worker_reference"):
        common.pop("worker", None)  # An inactive text field must not affect visual preparations.
        common["worker_policy"] = VISUAL_WORKER_VERSION
    value = dict(first=first, last=last, settings=common,
        content={key: transition[key] for key in ("action", "note", "intention", "kind", "duration", "camera", "pace")})
    if project.get("worker_reference") or transition.get("scale_setup_id"):
        value["visual_references"] = reference_state(project, transition)
    return fingerprint(value)


def needs_visual_refresh(project, transition):
    return bool(project.get("worker_reference") and transition.get("intention", "").strip()
                and transition.get("worker_visual_version") != VISUAL_WORKER_VERSION)


def require_current_visual_intention(project, transition):
    if needs_visual_refresh(project, transition):
        raise ValueError("Reproposez cette intention avec les références visuelles, puis relisez-la. "
                         "L’ancienne description de l’ouvrier ne doit plus être réutilisée.")


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
    require_current_visual_intention(project, transition)
    first, last = pair_frames(project, transition)
    options = effective(project, transition)
    visual = require_references(project, transition)
    config = configuration(visual["mode"])
    config.update(preset="custom", shot_count=1, cinematic_settings={"shot_count": 1},
                  plan_model_id=options["plan_model_id"], writer_model_id=options["writer_model_id"],
                  creative_audacity=1, creative_freedom=25,
                  creative_axes=dict(scene_life=1, camera=1, extra_motion=1, dialogue=0))
    config["references"] = [dict(asset_id=f["asset_id"], role=role, label=f["label"])
                            for f, role in ((first, "first_frame"), (last, "last_frame"))]
    if visual["worker"]:
        config["references"].append(dict(asset_id=visual["worker"]["asset_id"],
            role="subject_reference", label="Ouvrier — apparence et tenue"))
    if visual["scale"]:
        config["references"].append(dict(asset_id=visual["scale"]["asset_id"],
            role="composition_reference", label="Échelle de l’ouvrier dans le décor — montage de référence"))
    crew = crew_contract(options) if "crew_size" in options else None
    people_text = (f"Organisation du chantier : {crew['label']}. {crew['description']} "
                   "Adapter les engins, la coopération et les matériaux à la taille des ouvriers ; "
                   "l’ampleur du chantier ne change pas leur échelle.\n") if crew else ""
    if visual["worker"]:
        config["worker_visual_policy"] = WorkerVisualPolicy(
            identity_asset_id=visual["worker"]["asset_id"],
            scale_asset_id=visual["scale"]["asset_id"] if visual["scale"] else None,
            depict_worker=transition["kind"] != "camera").as_dict()
        people_text += "Utiliser uniquement le personnage de <Picture 3>"
        people_text += (", à l’échelle et au placement montrés dans <Picture 4>.\n"
                        if visual["scale"] else ".\n")
        people_text += ("L’image porte intégralement son identité, son apparence, son corps et sa tenue : "
                        "ne les redécrire dans aucun champ du Plan ou du prompt. "
                        "Conserver les liens vers ces images lorsque le personnage agit. "
                        "Décrire ses actions et adapter outils, engins et manutention aux références.\n")
        if visual["scale"]:
            people_text += "Le montage porte l’échelle : ne la traduire ni en taille textuelle ni en ratio.\n"
    worker_text = "" if visual["worker"] else f"Ouvrier, si nécessaire à cette action : {options['worker']}\n"
    seconds = options["duration"]
    temporal = temporal_contract(options)
    temporal_text = (f"Traitement temporel prioritaire : {temporal['label']}.\n"
                     f"{temporal['pace']}\n"
                     f"Consigne Plan et Prompt H3 : {temporal['h3_guidance']}\n") if temporal else ""
    rhythm_text = "" if temporal else f"Rythme : {options['pace']}\n"
    config["intention"] = (
        f"Un seul plan continu de {seconds:g} secondes. Première image à 0 s, dernière image à {seconds:g} s.\n"
        f"{temporal_text}{people_text}"
        f"Action : {transition['action']}\n{transition['intention']}\n"
        f"Indication utilisateur : {transition['note']}\n"
        f"{worker_text}"
        f"{rhythm_text}Caméra : {options['camera']}\n"
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
