"""Opt-in visual-state coverage for newly created long stories (wire 2.3)."""
from copy import deepcopy
from . import story_continuity as ledger

CONTRACT_VERSION = "2.3.0"


def enabled(project):
    return (project.get("job") or {}).get("response_contract_version") == CONTRACT_VERSION


def patch_schema(project, identity):
    from .story_contracts import obj, choice, array
    from .long_stories import source_hash
    scenario = project["document"]["episode_scenarios"][identity]
    element = ledger.schema(len(scenario["scenes"]))["properties"]["elements"]["items"]
    return obj(base_hash=choice([source_hash(project, identity)]), elements=array(element, 0, 24))


def projection(project, identity):
    from .long_stories import source_hash
    scenario = project["document"]["episode_scenarios"][identity]
    # No dramatic summary, secret, reason, narrative outcome or character biography.
    return dict(unit_id=identity, base_hash=source_hash(project, identity),
        elements=[{key: deepcopy(e[key]) for key in ("id", "kind", "name", "tracking", "scene_indices", "states")}
                  for e in ledger.elements(scenario)])


def extract_review_patches(project, response):
    """Remove optional patches before narrative validation; malformed metadata never loses a review."""
    from .long_stories import scope, source_hash
    from .story_contracts import structural_issues
    if not enabled(project):
        return {}, {}
    target = scope(project)
    if target == "block":
        entries = response.get("reviews", [])
        allowed = project["job"].get("review_unit_ids", [])
    elif target not in {"outline", "ideas"} and project["job"]["operation"].startswith("review_"):
        review = response.get("review")
        if not isinstance(review, dict):
            return {}, {}
        entries = [{**review, "unit_id": target}]
        # Pop on the actual response as well; the existing narrative schema remains isolated.
        if isinstance(response.get("review"), dict):
            response["review"].pop("visual_patch", None)
        allowed = [target]
    else:
        return {}, {}
    changes, warnings = {}, {}
    if not isinstance(entries, list):
        return {}, {}
    for item in entries:
        if not isinstance(item, dict):
            continue
        patch = item.pop("visual_patch", None)
        identity = item.get("unit_id")
        if patch is None or identity not in allowed:
            continue
        try:
            if structural_issues(patch, patch_schema(project, identity)):
                raise ValueError("La correction visuelle reçue est mal formée ou vise une ancienne révision.")
            if patch["base_hash"] != source_hash(project, identity):
                raise ValueError("La version relue a changé.")
            scenario = project["document"]["episode_scenarios"][identity]
            current = deepcopy(scenario.get("visual_continuity") or ledger.empty())
            known = {e["id"]: e for e in current["elements"]}
            seen = set()
            for element in patch["elements"]:
                if element["id"] in seen:
                    raise ValueError("Élément corrigé plusieurs fois.")
                seen.add(element["id"])
                old = known.get(element["id"])
                if old and (old["kind"] != element["kind"] or not old.get("enabled", True)):
                    raise ValueError("Un élément désactivé ou son identité ne peut pas être remplacé par la relecture.")
                corrected = deepcopy(element)
                if old:
                    # A reviewer can change visual tracking, never identity or author opt-outs.
                    for key in ("kind", "name", "description", "enabled"):
                        if key in old:
                            corrected[key] = deepcopy(old[key])
                known[element["id"]] = corrected
            current["elements"] = list(known.values())
            current = ledger.normalize(current, scenario)
            if current != scenario.get("visual_continuity"):
                changes[identity] = current
        except (ValueError, TypeError, KeyError) as error:
            warnings[identity] = "Suivi visuel à vérifier dans Continuité : " + str(error)[:1200] + " Le scénario et le registre précédents sont conservés."
    return changes, warnings


WRITING_POLICY = """ÉTATS VISUELS REQUIS : vérifie les apparences importantes dès la première apparition visible,
y compris les états déjà acquis avant cet épisode ou pendant une ellipse. Une grossesse explicitement visible
(ventre arrondi), une musculature nouvelle ou une tenue transformée persistante demande tracking=reference et
state.reference=true. N'utilise pas text pour économiser une image nécessaire au raccord. Une émotion ou un
simple geste ne devient pas un état corporel : triste/joyeux appartiennent au jeu dans les scènes.
Une annonce de grossesse seule, un mensonge ou une voix téléphonique ne demande pas un ventre visible ;
n'invente ni stade de grossesse ni saut temporel. scene_indices contient uniquement les apparitions visibles.
Écris aussi l'apparence acquise dans opening_state des scènes concernées. État déjà acquis : at=start ; état
acquis pendant le clip : at=end. Préserve identité et attributs inchangés, réutilise les états hérités identiques.
Pour un état de référence hérité présent à l'ouverture, conserve une ancre reference=true : la fabrication
réutilisera l'image correspondante si elle existe. Les états explicites priment sur l'image d'identité initiale."""

REVIEW_POLICY = """CONTRÔLE VISUEL DE FABRICATION : après ta lecture spectateur, compare les apparences visibles
jouées dans reader_units aux éléments de visual_state_review. Ce registre n'est pas une preuve narrative.
Pour un oubli évident, retourne visual_patch avec base_hash exact et elements (éléments complets à ajouter ou
corriger, mêmes IDs). Conserve les états non concernés ; l'application conserve l'identité et la description
existantes. Pour un nouvel élément, description reste strictement visuelle et reason explique le raccord. Aucun changement de scène, dialogue, événement, durée ou fait raconté.
Vérifie les états majeurs déjà acquis, même sans transformation montrée, et demande leur image avec
tracking=reference / state.reference=true. Une référence ne s'applique qu'aux présences visibles, pas aux voix.
Une annonce seule n'établit pas une silhouette enceinte. Ne devine pas une apparence ambiguë : visual_patch=null,
et remarque warning concise à l'auteur. Une omission visuelle corrigée ici n'est pas un problème bloquant de
réécriture du scénario. Sans correction utile, visual_patch=null. Aucun état émotionnel à figer comme physique."""
