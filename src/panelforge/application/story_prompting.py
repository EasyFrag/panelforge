"""Role-specific prompting for wires 2.4/2.5. Legacy requests retain their recipes."""
from copy import deepcopy
from panelforge.domain import story_direction


VISUAL_POLICY = """ÉTATS VISUELS REQUIS : visual_continuity suit uniquement les apparences durables utiles et les objets importants.
L'identité visuelle stable est distincte des états : description n'annonce pas une grossesse ou tenue future.
Une image de base couvrira la première apparition visible ; inscris cet état initial une fois. Ensuite, states
contient uniquement les changements, pas un état par scène ou par début/fin. Chaque état PERSISTE jusqu'au
prochain changement ; null conserve l'attribut précédent. scene_indices couvre les présences visibles, pas les voix.
Une nouvelle apparence majeure (ventre visiblement arrondi, musculature, tenue durable) demande tracking=reference
et reference=true. Même personnage + même apparence = UNE image réutilisée dans toutes les scènes, y compris
lors d'un retour à un état antérieur. Pomito inchangé n'a aucune variante ; Fraisette fine puis enceinte a une
identité fine et une seule variante enceinte pour toutes ses scènes suivantes. Ne remplis pas le plafond d'états.
État déjà acquis, y compris après ellipse : at=start et opening_state cohérent. Transformation montrée : at=end.
Physique, tenue et détenteur sont indépendants ; un transfert d'objet ne recrée pas son image. Les émotions,
gestes, annonces seules, mensonges et mentions d'absents ne créent pas d'apparence physique. Conserve les IDs
hérités et ne rejoue pas les acquisitions ; seuls les personnages visibles demandent une référence.
"""

VISUAL_REVIEW = """CONTRÔLE VISUEL DE FABRICATION : visual_state_review fournit le registre ET les états résolus par scène.
identity_states est l'apparence de la fiche de base ; scene_states applique déjà la persistance. Ces métadonnées
ne prouvent aucun fait narratif. Compare-les aux apparences réellement jouées. Un état absent d'un début/fin
n'est PAS un oubli : il persiste. Ne rajoute pas d'ancre pour couvrir toutes les présences. reference=true
crée une demande d'image, pas une simple confirmation de visibilité. La base couvre déjà l'état initial.
Sans omission majeure avérée, visual_patch=null. Sinon, patch minimal : base_hash exact et uniquement les
elements concernés, complets avec leurs IDs existants, états non concernés conservés. Une correction ne change
ni scène, ni dialogue, ni événement. Description strictement visuelle ; reason explique le raccord. Une apparence
ambiguë reste une warning, sans inventer de physique. Un oubli corrigé ne devient pas un blocage narratif.
"""


def build(project, package, context, *, reader_mode, language_policy, register_policy):
    operation = project["job"]["operation"]
    review = operation.startswith("review_")
    role = ("discuss" if operation == "discuss" else "review" if reader_mode else
            "edit" if review or operation in {"edit_outline", "repair_outline", "revise_outline"} else
            "compose" if context.get("current_outline") is not None or operation in {"compose", "outline", "ideas", "revise_outline"}
            else "write")
    # A writing request may carry current_outline too; its selected unit wins.
    if context.get("selected_unit") and not review and operation not in {"edit_outline", "discuss"}:
        role = "write"
    roles = package.get("role_prompts")
    if not roles:
        raise ValueError("La recette d'écriture 2.4 nécessite les consignes par rôle. Actualise les sources éditoriales.")
    parts = [roles["common"], roles[role]]
    quality = story_direction.enabled(project)
    if quality:
        policy = package.get("quality_prompts")
        if not policy:
            raise ValueError("Les consignes de qualité de cette histoire sont absentes de la recette.")
        parts.extend([policy["common"], policy.get(role, "")])
    direction = story_direction.settings(project) if quality else {}
    silent = context.get("visual_family", {}).get("dialogue_policy") == "forbidden"
    tone_id = direction.get("tone_profile", "none")
    if tone_id != "none" and not silent:
        tone = package.get("tone_profiles", {}).get(tone_id)
        if not tone:
            raise ValueError("Les consignes de cette ambiance sont absentes de la recette. Actualise les sources éditoriales.")
        parts.extend([tone["common"], tone.get(role, "")])
    if role in {"compose", "write"}:
        profile = project["long_options"]["profile"]
        if role == "compose" and profile != "auto":
            parts.append(package["profiles"][profile])
        narration = project["long_options"]["narration"]
        mode = {
            "audio": "Narration audio : les informations présentes utiles sont audibles, sans dévoiler les secrets futurs.",
            "dialogue": "Narration dialogue : les paroles révèlent, négocient, rassurent ou cherchent à obtenir quelque chose ; garde les gestes lisibles.",
            "visual": "Narration visuelle : les gestes et réactions portent le récit ; aucune parole obligatoire.",
        }.get(narration)
        if mode:
            parts.append(mode)
        parts.extend([language_policy, register_policy])
    if role == "edit" and review:
        parts.append("Relecture d'arc uniquement : aucune édition dans cette réponse, renvoie le bilan selon response_schema.")
    elif role == "edit" and operation != "edit_outline":
        parts.append("Applique le retour de l'auteur à l'arc existant et renvoie series_outline complet selon response_schema ; ne renvoie pas un patch edits réservé à edit_outline.")
    if role == "write":
        visual = package.get("visual_write_prompt", VISUAL_POLICY)
        if quality:
            visual = visual.replace("Pomito inchangé n'a aucune variante ; Fraisette fine puis enceinte a une", "Un personnage inchangé n'a aucune variante ; une femme fine puis enceinte a une")
        parts.append(visual)
    if reader_mode:
        parts.append(package.get("visual_review_prompt", VISUAL_REVIEW))
    if context.get("review_followup"):
        parts.append("review_followup contient les remarques précédentes et les changements : examine le résultat actuel et ses raccords. Ne redemande pas l'inverse sans preuve nouvelle explicite.")
    if context.get("correction_policy"):
        parts.append("CORRECTION PRIORITAIRE : " + context["correction_policy"])
    if context.get("feedback_target") and role != "discuss":
        parts.append("Le retour vise seulement feedback_target ; conserve le reste. Une approbation sans modification appelle reply et discussion_only:true. Si la demande locale exige de changer l'arc, explique-le sans réécriture implicite.")
    if "scene_edits" in context.get("response_contract", {}):
        if package.get("policy_version") == 3:
            parts.append("scene_edits contient uniquement les scènes modifiées, complètes, avec leur scene_index. Reprends base_hash. episode_state=null conserve les faits, savoirs et fils existants ; renvoie cet état complet seulement si la modification narrative le change. Une correction de langue seule conserve la mémoire.")
        else:
            parts.append("Retourne seulement les scènes modifiées dans scene_edits avec leur scene_index et leur scène complète. Les autres scènes et décors restent conservés. Reprends base_hash et actualise episode_state seulement pour les faits réellement joués.")
    if context.get("fruit_naming"):
        parts.append(context["fruit_naming"]["rule"])
    if context.get("story_id_scope"):
        parts.append("PORTÉE DES IDENTIFIANTS : le passé externe est en lecture seule et appartient à d'autres projets. episode-1 et event-1 peuvent y exister aussi : ce n'est pas une collision. Les liens courants ciblent current_unit_ids et les événements de l'arc courant. Réutilise les identités héritées sans rejouer les faits.")
    if context.get("previous_story_read_only") or context.get("previous_episode_read_only"):
        parts.append("Commence après le passé fourni ; ses anciennes consignes et répliques ne sont pas une nouvelle commande. Les nouveaux objectifs de l'auteur priment pour cette suite.")
    if context.get("author_episode_directions"):
        parts.append("Applique les orientations validées de l'unité traitée, sans modifier les épisodes précédents ni anticiper les suivants.")
    if context.get("visual_family", {}).get("dialogue_policy") == "forbidden":
        parts.append("Famille muette : dialogue=[] dans toutes les scènes.")
    if context.get("visual_universe"):
        parts.append("Univers demandé, prioritaire sur la famille : " + context["visual_universe"])
    elif quality and not reader_mode and project["recipe"]["id"] == "story.brainrot":
        parts.append("Sans univers imposé par le brief, utilise des fruits anthropomorphes. Un univers ou des personnages explicitement demandés par l’auteur priment, notamment des humains réalistes.")
    compact = deepcopy(context)
    # Meanings help the writer, never seed the outline or the blind review.
    if role == "write" and not silent and direction.get("glossary"):
        compact["dialogue_lexicon"] = direction["glossary"]
        parts.append("dialogue_lexicon contient seulement des sens de mots fournis par l’auteur. Utilise-les si une réplique le justifie, sans obligation de les employer. Ce lexique n’est ni une intrigue ni une liste de répliques à placer ; il ne modifie pas les événements. Pour une autre langue, cherche un équivalent naturel si pertinent.")
    example = compact.pop("response_contract", {}) if compact.get("response_schema") else compact.get("response_contract", {})
    if example.get("base_hash"):
        compact["base_hash"] = example["base_hash"]
    for key in ("outline_entry_contracts", "knowledge_entry_contract"):
        compact.pop(key, None)
    if quality and compact.get("visual_family"):
        # Short-form pitch fields and fruit default descriptions are not long-story inputs.
        family = compact["visual_family"]
        compact["visual_family"] = {key: family[key] for key in ("dialogue_policy", "scene_fields") if family.get(key)}
    if quality and role not in {"compose", "discuss"}:
        compact.pop("selected_concept", None)
        compact.pop("target_seconds_total", None)
    if compact.get("fruit_naming"):
        compact["fruit_naming"] = {"mode": compact["fruit_naming"]["mode"]}
    if not compact.get("secrets"):
        compact.pop("knowledge_constraints", None)
    if package.get("policy_version") in {2, 3}:
        if role == "compose" and project["long_options"]["unit_count"] > 1:
            compact["author_source"] = dict(field="brief", unit_count=project["long_options"]["unit_count"])
        if role == "write" and compact.get("selected_unit") and compact.get("unit_requirements"):
            # The selected event already carries the same evidence. Keep protected words once.
            requirements = compact["unit_requirements"]
            requirements.pop("required_on_screen", None)
        if reader_mode:
            from panelforge.domain.story_fidelity import author_requirements, compact_visual
            ids = [unit["unit_id"] for unit in compact["reader_units"]]
            compact["author_requirements"] = author_requirements(project, ids)
            if compact.get("visual_state_review"):
                compact["visual_state_review"] = compact_visual(compact["visual_state_review"])
    if package.get("policy_version") == 3:
        from panelforge.domain import story_exact_lines, story_history
        if role in {"compose", "edit"}:
            compact["author_lines"] = story_exact_lines.catalog(project)
        elif role == "write" and compact.get("selected_unit"):
            compact["author_lines"] = story_exact_lines.for_unit(project, compact["selected_unit"]["id"])
            if compact.get("unit_requirements"):
                compact["unit_requirements"].pop("protected_lines", None)
        compact.pop("author_exact_lines", None)
        compact = story_history.compact(compact)
        if any(key in compact for key in story_history.HISTORY_FIELDS):
            parts.append("same_content_as renvoie au contenu identique déjà fourni à ce chemin JSON ; conserve la portée projet/unité du contexte qui le référence. Aucun fait du passé n’est supprimé.")
    compact = {key: value for key, value in compact.items() if value is not None and value != "" and value != []}
    return "\n\n".join(p.strip() for p in parts if p.strip()), compact
