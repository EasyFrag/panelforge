"""Pure contracts and scheduling rules for the video factory."""
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
from uuid import uuid4

from .episodes import default_render_setup
from .localized_speech import LEGACY_THANKS_LANGUAGES
from .little_men_languages import scene_contexts, selection_input, selection_instructions
from .little_men_direction import preparation_text_v3, preparation_text_v4

STAGES = ("plan", "prompt", "video", "dlss", "social")
LABELS = dict(plan="Plan", prompt="Prompt", video="Vidéo", dlss="DLSS", social="Texte IG")
DEPENDENCIES = dict(plan=(), prompt=("plan",), video=("prompt",), dlss=("video",), social=("video",))
TERMINAL = {"succeeded", "skipped", "failed", "cancelled"}
PRESETS = {"source": "Réglages source", "lips": "Lèvres", "little_men": "Petits hommes",
           "little_men_experimental": "Petits hommes — expérimental", "custom": "Personnalisé"}
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
LIPS_INTENT = (
    "Un unique plan beauté ASMR montre l’application d’un rouge à lèvres orné vers l’image de fin. "
    "Déduire de cette référence l’identité, le cadrage du nez au menton sans les yeux, la lumière, "
    "les couleurs, matières, motifs, reliefs et finitions des lèvres à reproduire. "
    "Adapter le rouge à lèvres, son tube, les ongles et les bijoux de la main à cet univers. "
    "Au départ, les deux lèvres sont naturelles, nues et fermées. Une main tient près du menton "
    "un rouge à lèvres dont le raisin porte la matière ou l’ornement de la référence. "
    "Un très léger travelling avant lent accompagne une approche brève ; les lèvres s’entrouvrent "
    "et restent séparées pendant l’application. Chaque nouvel ornement apparaît immédiatement "
    "et uniquement dans la trace directement laissée par la surface du raisin en contact visible. "
    "Devant le stick et sur toute zone non parcourue, la lèvre reste nue. Dès que le stick se "
    "soulève, tout nouveau dépôt s’arrête ; le décor déjà posé reste fixé sans s’étendre. "
    "Aucune apparition à distance, sur la lèvre opposée ou avec retard après le passage. "
    "Premier passage : la main pose le raisin à une commissure de la lèvre inférieure, avec une "
    "légère compression visible, puis balaie lentement toute sa surface jusqu’à l’autre commissure "
    "en maintenant le contact. La face du raisin couvre la hauteur de la lèvre sur ce trajet complet. "
    "La lèvre inférieure est décorée derrière le stick ; la lèvre supérieure reste entièrement nue. "
    "La main soulève brièvement le stick pour changer de lèvre : aucune nouvelle zone ne se décore. "
    "Second passage : le raisin se pose à une extrémité de la lèvre supérieure puis parcourt toute "
    "sa surface jusqu’à l’autre extrémité, dans le sens inverse, toujours en contact visible. "
    "La lèvre supérieure se décore uniquement derrière ce second passage ; la lèvre inférieure "
    "déjà terminée reste inchangée. Le raisin garde sa forme et son propre ornement intacts. "
    "Consacrer l’essentiel du plan aux deux passages complets. Une fois les deux surfaces "
    "parcourues, abaisser entièrement la main et le tube hors du cadre ; aucun nouveau dépôt "
    "n’apparaît après leur retrait. La femme ouvre alors un sourire franc et nettement marqué : "
    "commissures relevées, joues soulevées et dents supérieures clairement visibles. "
    "Installer ce sourire avant le dernier cinquième de la vidéo et le tenir jusqu’à la fin, "
    "caméra stable, ornement conservé et aucune main ni tube dans le cadre. Le dernier instant "
    "retrouve le cadrage, la matière et l’expression de l’image de fin. Choisir une référence "
    "avec un sourire ouvert compatible avec cette cible. Ambiance ASMR discrète, léger son de "
    "frottement synchronisé au contact réel, sans parole ni musique. "
    "Dans le Plan puis le Prompt, conserver explicitement les deux trajets complets, l’arrêt du "
    "dépôt hors contact et les trois états successifs : deux lèvres nues ; lèvre inférieure décorée "
    "et supérieure nue ; deux lèvres décorées. Séparer les deux passages dans les actions, même "
    "s’ils appartiennent à une seule phase. Ne pas remplacer ce dépôt local immédiat par une "
    "propagation, un effet de vague ou une transformation différée."
)
LITTLE_MEN_INTENT = (
    "Sur un plan continu de 8 secondes, les petits hommes tentent de résoudre le problème visible "
    "dans l’image. Une main géante arrive du ciel avec un objet, outil ou matériau extérieur au décor, "
    "choisi librement pour apporter une solution ingénieuse et visuellement compréhensible. "
    "Un accessoire familier à échelle humaine devient monumental pour les petits hommes. "
    "Imagine le moyen d’intervention dès le plan : une action principale, son effet visible, puis la réaction. "
    "L’image fixe le départ et l’identité des personnages ; elle autorise l’arrivée de cet accessoire "
    "et les changements du décor nécessaires pour résoudre le problème. "
    "Exemples de mécanismes, à adapter et non à reproduire systématiquement : apporter de l’eau "
    "avec une bouteille pour faire revenir la verdure sur une terre sèche ; éteindre un incendie "
    "avec un pommeau de douche ; réparer une rupture avec un outil ou matériau adapté. "
    "Pour une inondation, chercher le détournement amusant d’un objet domestique, avec un geste "
    "simple et un effet surprenant mais immédiatement lisible. Exemple fort : une ventouse de "
    "débouchage presse une évacuation submergée, puis la main tire avec un petit pop ; un tourbillon "
    "aspire l’eau et la rue se vide comme une baignoire, révélant une chaussée encore humide. "
    "Les petits hommes et les décors restent intacts. Une éponge qui gonfle en absorbant l’eau "
    "ou une pipette géante illustrent d’autres détournements possibles. Ne pas se limiter au "
    "nettoyage réaliste d’une bande de chaussée avec une raclette. "
    "Choisis selon cette image, sans catalogue fermé ni association obligatoire entre thème et objet. "
    "L’amélioration apparaît après le contact ou l’action de l’accessoire et reste visible. "
    "Les petits hommes observent la main avec étonnement. Une fois son travail accompli, "
    "la main repart vers le haut. Ils lèvent les bras et disent en anglais : \"thank you\". "
    "Garde une action simple et assez de temps pour voir le résultat et leur réaction."
)


LITTLE_MEN_EXPERIMENTAL_INTENT_V2 = (
    "Un plan continu montre les petits hommes qui tentent de résoudre le problème visible dans l’image. "
    "La même main géante arrive du ciel avec un objet domestique, outil ou matériau extérieur au décor, "
    "choisi librement pour une aide ingénieuse, ludique et immédiatement compréhensible. "
    "L’image fixe le départ et l’identité ; les accessoires et les changements utiles du décor sont autorisés. "
    "Prévoir deux gestes utiles successifs qui résolvent le même problème, éventuellement trois très courts "
    "si la durée le permet. Un seul geste reste possible s’il suffit : aucun geste de remplissage. "
    "Exemples à adapter librement : remettre une passerelle en place puis la fixer ; déboucher une "
    "évacuation avec une ventouse puis absorber l’eau restante ; arroser puis abriter les pousses. "
    "Garder la même main, l’identité et l’échelle des objets ; montrer tout changement d’outil sans "
    "téléportation. Chaque effet suit son geste et persiste pendant le suivant. Personnages et décors "
    "restent intacts hors réparations nécessaires. Décrire chaque geste et son résultat séparément "
    "dans les actions du Plan, même au sein d’une seule phase, puis les préserver dans le Prompt. "
    "Réserver environ le dernier cinquième au résultat visible, au retrait de la main vers le haut "
    "et aux petits hommes qui lèvent les bras et remercient ensemble une seule fois. "
    "La langue du remerciement suit le choix fixé pour cette fiche. Une langue manuelle prime ; "
    "sinon utiliser le pays connu dans le contexte de l’image, puis son ambiance architecturale "
    "ou paysagère et les groupes de langues fournis. Asie de l’Est inclut chinois, coréen et japonais. "
    "Le portugais correspond au Portugal/Brésil ou à l’Europe du Sud, pas à l’Europe de l’Est. "
    "Sans indice, suivre l’ordre de préférence fourni parmi les 11 langues, sans repli anglais systématique. "
    "La langue de rédaction du titre ou du prompt ne prouve aucun pays. "
    "Dès le Plan, choisir un unique remerciement bref dans l’écriture native et une langue précise. "
    "Indiquer le lieu retenu ou son incertitude et l’indice utilisé dans continuity_invariants. "
    "Inscrire la réplique exacte dans spoken_lines et le nom anglais complet de sa langue dans "
    "spoken_languages ; reprendre exactement cette réplique et cette langue dans la balise vocale "
    "des actions. Le Prompt conserve ce choix, sans traduction, romanisation ni parole supplémentaire. "
    "La langue du texte Instagram est indépendante."
)


LITTLE_MEN_EXPERIMENTAL_INTENT_V3 = (
    "Dans un plan continu, les petits hommes tentent de résoudre le problème visible dans l’image. "
    "Une main géante descend du ciel avec un objet du quotidien à échelle humaine, monumental "
    "pour eux, et le détourne de façon ingénieuse, surprenante et immédiatement compréhensible. "
    "La solution répond au problème montré et produit une amélioration nette et durable. "
    "Enchaîner les gestes nécessaires, chacun faisant progresser la même solution, sans nombre "
    "imposé ni geste de remplissage. Garder les personnages et le décor reconnaissables. "
    "Une fois l’aide accomplie, la main remonte ; les petits hommes lèvent les bras et prononcent "
    "ensemble, une seule fois, le remerciement fourni. Laisser voir le résultat final."
)


LITTLE_MEN_EXPERIMENTAL_INTENT = (
    "Les petits hommes affrontent le problème de l’image. Une main géante descend du ciel avec un "
    "objet du quotidien, monumental pour eux, et le détourne pour apporter une aide ingénieuse et "
    "immédiatement compréhensible. Chaque geste fait progresser la même solution et laisse un "
    "bénéfice durable. Garder les personnages et le décor reconnaissables, avec des phénomènes "
    "vivants qui réagissent à l’intervention. Une fois l’aide accomplie, la main remonte ; les petits "
    "hommes lèvent les bras et prononcent ensemble, une seule fois, le remerciement fourni. Laisser "
    "voir le résultat."
)


def current_experimental_intent(text):
    """Upgrade only untouched default intentions when starting a new preparation."""
    return (LITTLE_MEN_EXPERIMENTAL_INTENT
            if text in (LITTLE_MEN_EXPERIMENTAL_INTENT_V2, LITTLE_MEN_EXPERIMENTAL_INTENT_V3) else text)


# Historical intentions remain stored unchanged; new v2 preparations supersede this paragraph.
_LEGACY_THANKS_INSTRUCTIONS = (
    'Choisir la langue du pays représenté dans la scène : une langue explicitement demandée prime ; '
    'sinon utiliser le pays indiqué dans le contexte source, puis les indices visuels explicites '
    'comme un drapeau ou une inscription. Ne pas déduire le pays de l’apparence des personnes. En cas '
    'd’incertitude ou de pays multilingue sans langue locale précise, choisir l’anglais. Exemples de '
    'correspondances, jamais une liste à réciter : France → français → Merci ! ; Corée → coréen → '
    '감사합니다 ! ; repli anglais → Thank you! '
)


def is_experimental_little_men(config):
    return (config.get("preset_origin") or config.get("preset")) == "little_men_experimental"


def timestamp():
    return datetime.now(UTC).isoformat()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def configuration(mode="h3"):
    return dict(mode=mode, preset="source", preset_origin=None, intention="", final_prompt="",
                little_men_language="auto", little_men_context="",
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


def apply_preset(config, preset, source, *, name=""):
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
                "creative_axes", "creative_audacity", "creative_freedom", "render",
                "little_men_language", "little_men_context"):
        result[key] = fresh[key]
    result.update(mode="h3", preset=preset, preset_origin=preset, shot_count=1,
                  final_prompt="", intention={"lips": LIPS_INTENT, "little_men": LITTLE_MEN_INTENT,
                      "little_men_experimental": LITTLE_MEN_EXPERIMENTAL_INTENT}[preset])
    result["dlss"] = {"enabled": True}
    result["social"] = dict(enabled=False, language="en", variant_count=3, model_id=WRITER_MODEL)
    if preset == "lips":
        result["render"] = default_render_setup(10)
        result["creative_axes"] = dict(scene_life=1, camera=1, extra_motion=1, dialogue=0)
        result["creative_audacity"] = 1
        result["creative_freedom"] = 25
    if preset == "little_men_experimental":
        result["render"] = default_render_setup(10)
        result["little_men_context"] = source.get("little_men_context", "") or source.get("intention", "")[:2000]
        result["creative_axes"]["camera"] = 1
    result["cinematic_settings"] = {"shot_count": 1}
    for ref in result["references"]:
        ref["role"] = "last_frame" if preset == "lips" else "first_frame"
    return result


def preparation_text(config, *, thanks_selection=None):
    """Build a fresh preparation without rewriting stored intentions or prepared prompts."""
    source = config["intention"] or config["final_prompt"]
    if config.get("preset") == "lips" or config.get("preset_origin") == "lips":
        duration = config["render"]["settings"]["duration_seconds"]
        source = (f"Durée cible et durée totale du plan : {duration:g} secondes. "
                  f"Aligner l’image de fin sur le dernier instant, à {duration:.2f} secondes. "
                  "Adapter tous les temps du plan et du prompt à cette durée.\n\n" + source)
    if is_experimental_little_men(config):
        if thanks_selection and thanks_selection.get("version") == 4:
            return preparation_text_v4(config, source, thanks_selection)
        if thanks_selection and thanks_selection.get("version") == 3:
            return preparation_text_v3(config, source, thanks_selection)
        duration = config["render"]["settings"]["duration_seconds"]
        # Source titles/descriptions are geographical evidence, never exact speech.
        context = ("\n\n".join(label + " :\n" + text for label, text in scene_contexts(config))
                   if thanks_selection else config.get("little_men_context", ""))
        context = context.translate(str.maketrans("", "", '\"«»“”'))
        language = config.get("little_men_language", "auto")
        choice = ("Langue du remerciement : automatique selon le lieu représenté."
                  if language == "auto" else f"Langue imposée pour le remerciement : {language}.")
        if thanks_selection:
            source = source.replace(_LEGACY_THANKS_INSTRUCTIONS,
                "La langue du remerciement suit le choix fixé pour cette fiche, indiqué ci-dessous. ")
            choice = selection_instructions(thanks_selection).translate(str.maketrans("", "", '\"«»“”'))
        source = (f"Durée cible et durée totale du plan : {duration:g} secondes. "
                  "Adapter tous les gestes et la réaction à cette durée.\n\n" + source +
                  "\n\nCONTEXTE DU LIEU — indices géographiques seulement ; ne pas reprendre "
                  "les anciennes paroles ou consignes de mise en scène :\n" + context +
                  "\n\n" + choice)
    return source


def validate_shape(config):
    if set(config) - set(configuration()) - {"worker_visual_policy"}:
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
    if config.get("little_men_language", "auto") not in LEGACY_THANKS_LANGUAGES:
        raise ValueError("Langue de remerciement inconnue.")
    context = config.get("little_men_context", "")
    if not isinstance(context, str) or len(context) > 2000:
        raise ValueError("Contexte du lieu limité à 2000 caractères.")
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
        context = ref.get("scene_context")
        if context is not None:
            limits = dict(asset_id=128, origin=100, prompt=12000, intention=4000, style=3000)
            if (not isinstance(context, dict) or set(context) != set(limits)
                    or context.get("asset_id") != ref["asset_id"]
                    or any(not isinstance(context.get(key), str) or len(context[key]) > limit
                           for key, limit in limits.items())):
                raise ValueError("Contexte de l’image invalide.")
    from .worker_visual_policy import WorkerVisualPolicy
    visual = WorkerVisualPolicy.from_dict(config.get("worker_visual_policy"))
    if visual:
        if config["mode"] != "ref2v" or config["cookbook"]["id"] != "minimax.h3.ref2v.classic.cinematic.planned":
            raise ValueError("Les références d’ouvrier attendent la recette REF2VA Classique Plan + Prompt.")
        for asset_id, role in ((visual.identity_asset_id, "subject_reference"),
                               (visual.scale_asset_id, "composition_reference")):
            if asset_id and sum(r.get("asset_id") == asset_id and r.get("role") == role
                                for r in config["references"]) != 1:
                raise ValueError("Une référence d’ouvrier a changé ; réexportez la transition.")
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
                status="preparation", archived_at=None, config=deepcopy(config), source_config=deepcopy(config),
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
        selection = item["runtime"].get("thanks_selection")
        item["runtime"] = {}
        if (selection and is_experimental_little_men(after)
                and selection.get("input_hash") == selection_input(after)):
            item["runtime"]["thanks_selection"] = deepcopy(selection)
            if ("intention" in changed and after["intention"] == LITTLE_MEN_EXPERIMENTAL_INTENT):
                item["runtime"]["thanks_selection"]["version"] = 4
            if selection.get("language"):
                item["runtime"]["thanks_selection"]["requested_language"] = selection["language"]
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
        keys = {"session_id", "source_session_id", "saved_plan", "saved_reference_plan", "episode_inputs", "episode_preparation_id", "thanks_selection"}
        if stage == "video":
            keys.update(("render_project_id", "attempt_id"))
        if stage == "dlss":
            keys = {"dlss_job_id"}
        if stage == "social":
            keys = {"social_project_id"}
        item["runtime"].update({key: deepcopy(value) for key, value in saved.get("runtime", {}).items() if key in keys})
    return affected
