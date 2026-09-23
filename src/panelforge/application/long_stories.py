"""Compact context projections for the long-story V2 editorial workflow."""
from copy import deepcopy
import json

from panelforge.domain import long_stories as narrative
from panelforge.domain import story_contracts as contracts
from panelforge.domain.story_diagnostics import project_quality
from panelforge.domain import story_continuity as continuity
from panelforge.domain.stories import response_contract, story_recipe_spec
from .prompt_lab import CompletionRequest


def _review_followup(project, identities):
    """Reuse saved versions; expose only actual changes to playable material."""
    result = []
    for identity in identities:
        review = project["document"].get("reviews", {}).get(identity)
        if not review or narrative.review_current(project, identity):
            continue
        for revision in reversed(project.get("revisions", [])):
            document = revision.get("document", {})
            before = document.get("episode_scenarios", {}).get(identity)
            if not before:
                continue
            snapshot = dict(project, document=document, long_options=revision.get("long_options", project["long_options"]))
            if narrative.source_hash(snapshot, identity) != review.get("source_hash"):
                continue
            previous = continuity.reader_view(before)["scenes"]
            current = continuity.reader_view(project["document"]["episode_scenarios"][identity])["scenes"]
            changes = []
            for index in range(max(len(previous), len(current))):
                old = previous[index] if index < len(previous) else None
                new = current[index] if index < len(current) else None
                if old != new:
                    changes.append(dict(scene_index=index, before=old, after=new))
            result.append(dict(unit_id=identity, previous_issues=deepcopy(review["issues"]), changes=changes))
            break
    return result


def _fruit_naming(project, operation):
    doc = project["document"]
    mode = "preserve"
    if project.get("fruit_naming_version") == 1 and not doc.get("episode_scenarios"):
        if operation in {"ideas", "compose", "outline"} and not doc.get("series_outline"):
            mode = "invent"
        elif operation == "edit_outline" and not doc.get("reviews", {}).get("outline"):
            mode = "check_new_cast"
    if mode == "preserve":
        rule = "Conserve les noms des personnages existants, même s'ils sont simplement le nom d'un fruit. Ne les renomme pas pour appliquer une nouvelle préférence."
    else:
        rule = ("Uniquement pour les personnages fruités nouvellement inventés : invente un prénom dérivé du fruit, "
                "avec une terminaison mignonne : Bananito, Kiwina, Cerisa, Cerisetto, Noisettine. "
                "Le nom brut du fruit ne suffit pas. Ne fixe pas tous les personnages à ces exemples. "
                "Conserve les noms explicitement fournis par l'auteur et ceux du récit précédent. "
                "Un univers humain, animal ou de gouttes d'eau conserve ses propres noms.")
        if mode == "check_new_cast":
            rule += " Vérifie ce nommage dans cette passe d'édition déjà prévue ; corrige seulement les noms que tu viens d'inventer et leurs mentions, en conservant les IDs."
    return dict(mode=mode, rule=rule)


def request(project, package, language_policy, register_policy=""):
    doc, operation = project["document"], project["job"]["operation"]
    target = narrative.scope(project)
    review = operation.startswith("review_")
    stage = "review" if review or operation == "edit_outline" else "ideas" if target == "ideas" else "outline" if target == "outline" else "write"
    structured = contracts.structured(project)
    family = story_recipe_spec(project["recipe"]["id"], project["recipe"]["version"])
    context = {"operation": operation, "brief": project["brief"], "creation_mode": project["creation_mode"],
        "long_options": project["long_options"], "visual_family": family,
        "dialogue_language": project["dialogue_language"], "dialogue_register": project.get("dialogue_register", 0),
        "clip_budget": {"scope": "per_unit", "max_clips": project["scene_count"], "clip_seconds": project["clip_seconds"],
                        "unit_count": project["long_options"]["unit_count"],
                        "max_seconds_per_unit": project["scene_count"] * project["clip_seconds"],
                        "max_seconds_total": project["scene_count"] * project["clip_seconds"] * project["long_options"]["unit_count"]},
        "author_feedback": project["job"].get("instruction", ""),
        "feedback_target": project["job"].get("feedback_target"),
        "visual_universe": project.get("visual_universe", ""),
        "target_seconds_total": project.get("target_seconds"),
        "selected_concept": next((c for c in doc["concepts"] if c["id"] == doc["selected_id"]), None)}
    if project.get("prior_story"):
        context["previous_story_read_only"] = project["prior_story"]
    if doc.get("prior_story_snapshot"):
        context["previous_episode_read_only"] = doc["prior_story_snapshot"]
    outline = doc.get("series_outline")
    if target == "ideas":
        context["response_contract"] = response_contract("ideas", False, project["recipe"]["id"],
                                                         project["recipe"]["version"])
        context["previous_pitches"] = [{"title": c["title"], "hook": c["hook"]} for c in doc["concepts"]]
    elif target in {"outline", "block"}:
        context["current_outline"] = deepcopy(outline)
        if context["current_outline"]:
            for unit in context["current_outline"]["episodes"]:
                unit.pop("beats", None)
        context["response_contract"] = narrative.outline_example(project)
        context["outline_entry_contracts"] = narrative.outline_entry_contracts()
        context["outline_entry_contracts"]["events"] = {
            "id": "ID stable de l’événement", "trigger": "Cause ou but", "change": "Changement produit",
            "evidence": "Preuve visible ou audible", "depends_on": ["ID d’un événement antérieur"]}
        if target == "block":
            context["units_to_review"] = [{"unit_id": identity,
                "scenario": doc["episode_scenarios"][identity], "episode_state": doc["episode_states"][identity],
                "allowed_review_targets": sorted(narrative.review_targets(project, identity))}
                for identity in project["job"]["review_unit_ids"]]
            first = min(project["job"]["review_unit_ids"], key=lambda identity: int(identity.split("-")[-1]))
            context["canonical_history"] = [{"unit_id": identity, "state": doc["episode_states"][identity]}
                for identity in narrative.previous_ids(project, first)]
    else:
        context["selected_unit"] = next(u for u in outline["episodes"] if u["id"] == target)
        context["contract"] = outline["contract"]
        context["characters"] = outline["characters"]
        context["world_rules"] = outline["world_rules"]
        context["secrets"] = outline["secrets"]
        context["overall_arc"] = outline["overall_arc"]
        context["canonical_history"] = [
            {"unit_id": identity, "state": doc["episode_states"][identity],
             "reviewed": narrative.review_clear(project, identity),
             "ending_state": doc["episode_scenarios"][identity]["scenes"][-1]["ending_state"]}
            for identity in narrative.previous_ids(project, target)]
        prior = narrative.previous_ids(project, target)
        if prior:
            context["visual_state_inherited"] = continuity.carry_forward(doc["episode_scenarios"][prior[-1]])
        elif doc.get("visual_state_inherited"):
            context["visual_state_inherited"] = deepcopy(doc["visual_state_inherited"])
        past = set(narrative.previous_ids(project, target)) | {target}
        context["future_reservations"] = [{"id": u["id"], "promise": u["promise"], "ending_type": u["ending_type"],
                                          "events": u["events"]} for u in outline["episodes"] if u["id"] not in past]
        context["current_scenario"] = doc.get("episode_scenarios", {}).get(target)
        context["current_episode_state"] = doc.get("episode_states", {}).get(target)
        fmt = doc["episode_formats"][target]
        context["clip_budget"] = {"scope": "selected_unit", "max_clips": fmt["scene_count"],
                                 "clip_seconds": fmt["clip_seconds"], "max_seconds": fmt["scene_count"] * fmt["clip_seconds"]}
        context["response_contract"] = narrative.episode_example(project)
        context["knowledge_entry_contract"] = {"secret_id": "ID d’un secret de la bible",
            "character_ids": ["ID d’un personnage qui apprend cette vérité"], "event_id": "ID de l’événement source dans cette unité"}
        context["knowledge_constraints"] = {
            "allowed_secret_ids": [secret["id"] for secret in outline["secrets"]],
            "allowed_event_ids": [event["id"] for event in context["selected_unit"]["events"]],
            "rule": "knowledge suit uniquement les secrets déclarés, pas toute prise de conscience. "
                    "Sans secret déclaré, knowledge doit être []. Ne jamais créer une entrée avec secret_id:null.",
        }
        seconds = fmt["clip_seconds"]
        context["speech_budget"] = {"clip_seconds": seconds, "words_per_second_estimate": 2.4,
            "example": f"Avec 3 secondes de gestes non simultanés, viser au plus {max(0, int((seconds - 3) * 2.4))} mots au total dans le clip, tous locuteurs réunis.",
            "rule": "Réserver aussi les réactions. Si nécessaire, raccourcir les paroles ou répartir dans la limite du nombre de clips. Ce budget est une estimation, pas un quota à remplir."}
    if outline and target != "ideas":
        context["local_diagnostics"] = ({identity: project_quality(project, identity) for identity in project["job"].get("review_unit_ids", [])}
            if target == "block" else project_quality(project, target))
    reader_mode = review and target not in {"outline", "ideas"} and project["job"].get("response_contract_version") == contracts.VERSION
    if reader_mode:
        identities = project["job"].get("review_unit_ids", []) if target == "block" else [target]
        # Unlike a prompt asking the reader to "forget" the bible, this projection
        # actually withholds the secrets, metadata evidence and declared outcomes.
        context = {k: v for k, v in context.items() if k in {
            "operation", "dialogue_language", "dialogue_register", "clip_budget", "local_diagnostics"}}
        def readable_diagnostics(items):
            return [item for item in items if not item.get("path", "").startswith("scenario.visual_continuity")]
        diagnostics = context.get("local_diagnostics", [])
        context["local_diagnostics"] = ({identity: readable_diagnostics(items) for identity, items in diagnostics.items()}
            if isinstance(diagnostics, dict) else readable_diagnostics(diagnostics))
        context["reader_units"] = [dict(unit_id=identity, **continuity.reader_view(doc["episode_scenarios"][identity]),
            allowed_review_targets=sorted(narrative.review_targets(project, identity))) for identity in identities]
        previous = narrative.previous_ids(project, identities[0]) if identities else []
        context["reader_history"] = [dict(unit_id=identity, **continuity.reader_view(doc["episode_scenarios"][identity]))
            for identity in previous if identity in doc["episode_scenarios"]]
        if doc.get("prior_story_snapshot"):
            context["reader_history"].insert(0, dict(unit_id="previous-story", **continuity.reader_view(doc["prior_story_snapshot"])))
    if review and target not in {"outline", "ideas"}:
        identities = project["job"].get("review_unit_ids", []) if target == "block" else [target]
        context["review_followup"] = _review_followup(project, identities)
    if review:
        context["response_contract"] = narrative.review_example()
        context["review_target"] = target
        if target == "block":
            context["response_contract"] = {"reply": "Bilan du bloc et de ses raccords",
                "reviews": [{"unit_id": identity, **narrative.review_example()["review"]}
                            for identity in project["job"]["review_unit_ids"]]}
        else:
            context["allowed_review_targets"] = sorted(narrative.review_targets(project, target))
    correcting = operation.startswith("repair_") or (operation == "edit_outline"
        and narrative.review_current(project, "outline")
        and any(item["severity"] == "blocking" for item in doc["reviews"]["outline"]["issues"]))
    if correcting:
        context["review_to_address"] = dict(summary="Corriger uniquement les problèmes bloquants.",
            issues=[deepcopy(item) for item in doc["reviews"][target]["issues"] if item["severity"] == "blocking"])
        context["local_diagnostics"] = [item for item in context.get("local_diagnostics", []) if item["level"] == "blocking"]
        context["correction_policy"] = ("Une seule correction ciblée des problèmes bloquants. Les warnings restent informatifs. "
            "Préserve le reste, notamment les relations et la propriété des objets. Ne polis pas le style. "
            "Ajuste seulement les raccords nécessaires à la correction. Une nouvelle relecture sera nécessaire.")
    profile = project["long_options"]["profile"]
    profile_prompt = package["profiles"].get(profile) or ("Choisis le profil adapté parmi : " + json.dumps(package["profiles"], ensure_ascii=False))
    system = "\n\n".join([package["prompts"]["common"], profile_prompt,
                              package["prompts"][stage], language_policy, register_policy])
    if reader_mode:
        system += ("\nRELECTURE SPECTATEUR : reader_units contient uniquement les situations jouables, gestes et paroles. "
            "La bible, les secrets et les conclusions du scénariste sont volontairement absents. "
            "reader_history contient les épisodes déjà vus : ne redemande pas une présentation déjà claire dans ce passé. "
            "Dans summary, explique brièvement qui est lié à qui, le changement réellement compris et ce qui reste ambigu, "
            "avec la parole ou le geste qui t'a permis de le comprendre. Ne complète pas les maillons manquants par une supposition. "
            "Priorité : relations indispensables, désir, occasion, acte ou ellipse lisible, conséquence. "
            "Un clin d'œil ne prouve pas à lui seul une liaison ; une proximité ne nomme pas forcément un couple. "
            "Signale les participants visibles non déclarés et les changements physiques sans raccord. "
            "Nommer le propriétaire absent d’un objet ne rend pas ce personnage visible et n’impose pas de l’ajouter au casting. "
            "Une information volontairement cachée n'est pas un défaut. Les préférences de style sont des warnings, jamais une invitation à complexifier.")
    system += ("\nFORMAT : uniquement du JSON, jamais d’expression de code ou de méthode comme .replace(). "
               "Écris directement les chaînes finales. Respecte les IDs autorisés et laisse les listes facultatives vides lorsqu’elles ne s’appliquent pas.")
    if "outline_entry_contracts" in context:
        system += ("\nLes entrées d’arc suivent outline_entry_contracts. Chaque événement contient exactement id, trigger, change, evidence, depends_on. "
                   "depends_on est obligatoire même vide ([]). Lors d’une relecture, recopie les dépendances "
                   "de current_outline tant que la causalité ne change pas ; ne les omets jamais.")
    if operation == "compose":
        resolved_example = {key: f"CHOISIR_{key.upper()}" if project["long_options"][key] == "auto" else project["long_options"][key]
                            for key in ("profile", "narration", "ending_type")}
        context["response_contract"]["resolved_options"] = resolved_example
        context["response_contract"]["series_outline"]["episodes"][-1]["ending_type"] = resolved_example["ending_type"]
        context["available_choices"] = {"profile": narrative.PROFILES, "narration": narrative.NARRATIONS,
                                        "ending_type": sorted(narrative.ENDINGS)}
        system += ("\nCONCEPTION EN UN APPEL : invente une seule histoire et son architecture. Pas de liste de propositions. "
                   "Renvoie reply, series_outline et resolved_options. Résous uniquement les options auto ; préserve chaque choix explicite. "
                   "resolved_options contient profile, narration, ending_type parmi available_choices. L'arc respecte ces choix. "
                   "CHOISIR_* est un emplacement de format à remplacer, jamais une valeur ni une préférence de l'auteur. "
                   "Aucun profil, narration ou type de fin n'est présélectionné quand long_options indique auto. "
                   "Dans reply, présente brièvement le début, la bascule et la fin et explique les choix automatiques. "
                   "Les must_keep proviennent du brief, pas de toutes tes inventions. Une opposition abstraite ne devient pas un personnage à fabriquer.")
    elif operation == "edit_outline":
        context["response_contract"]["review"] = narrative.review_example()["review"]
        context["allowed_review_targets"] = sorted(narrative.review_targets(project, "outline"))
        system += ("\nÉDITION EN UNE PASSE : examine l'arc puis corrige directement les petits défauts locaux. "
                   + ("Renvoie les edits ciblés sur allowed_edit_paths, base_hash, reply et review portant sur le résultat après ces changements. "
                      "Chaque edit contient path et value (la valeur complète du champ). Une liste vide signifie aucun changement. "
                      "Conserve tout champ non ciblé ; ne modifie pas la causalité sans ajuster ses dépendances. " if structured else
                      "Renvoie reply, series_outline corrigé complet et review portant sur CE RÉSULTAT. ") +
                   "Les issues ne listent que les problèmes encore présents, jamais ceux que tu viens de corriger. "
                   "N'invente pas une modification pour justifier ton rôle. Préserve les IDs, le brief, les options et les événements déjà rédigés. "
                   "Un choix majeur incompatible avec l'intention reste une remarque blocking. Résume les changements dans reply. "
                   "N'étends pas la mythologie pour résoudre un problème qui peut être clarifié par un geste ou une parole.")
        if structured:
            context["allowed_edit_paths"] = sorted(contracts.outline_edit_targets(project))
    elif operation == "review_block":
        units_key = "reader_units" if reader_mode else "units_to_review"
        system += (f"\nRelis ensemble {units_key} et leurs raccords. Renvoie reply et reviews, une entrée par unit_id demandé. "
                   "Une remarque scene-N se rapporte à la séquence de son entrée. N'écris aucun scénario dans cette réponse.")
    elif operation == "discuss":
        context["response_contract"] = {"reply": "Réponse à la question, sans réécrire le document", "discussion_only": True}
        flow = project.get("workflow") or {}
        stop_target = flow.get("wait_target")
        stopped_review = doc.get("reviews", {}).get(stop_target, {})
        context["workflow_context"] = dict(
            mode=flow.get("mode"), status=flow.get("status"), message=flow.get("message"),
            wait_target=stop_target, previous_step=project["job"].get("discussion_previous_step"),
            blocking_issues=[deepcopy(item) for item in stopped_review.get("issues", []) if item["severity"] == "blocking"],
            validation_action="Valider / Continuer")
        system += ("\nQUESTION DE L'AUTEUR : réponds uniquement avec reply et discussion_only:true. Ne modifie aucun document. "
                   "workflow_context donne l'état réel du parcours et la raison de son arrêt. Explique ce motif et les "
                   "blocking_issues pertinents ; distingue une erreur technique d'un choix narratif. "
                   "N'invente pas une validation du ton, du rythme ou des personnages à obtenir. "
                   "Une question conserve le mode choisi. Tu ne peux ni valider ni lancer la production depuis cette réponse. "
                   "Si l'auteur exprime son accord, indique le bouton Valider / Continuer ; ne promets aucune réécriture.")
    if correcting:
        system += "\nCORRECTION CIBLÉE PRIORITAIRE : " + context["correction_policy"]
    if operation == "revise" and context.get("feedback_target"):
        system += ("\nUne simple approbation sans changement demandé appelle uniquement reply et discussion_only:true. "
                   "Indique le bouton Valider / Continuer ; ne réécris pas le scénario pour un simple accord.")
    if context.get("feedback_target"):
        system += ("\nLe retour courant ne s'applique qu'à feedback_target. Préserve le reste ; explique les conséquences utiles. "
                   "Si une demande locale exige de changer l'architecture, réponds en discussion_only plutôt que de changer silencieusement les événements réservés.")
    if context.get("visual_universe"):
        system += "\nUnivers explicitement choisi par l'auteur : " + context["visual_universe"] + ". Cet univers prévaut sur celui de la famille par défaut."
    if family.get("dialogue_policy") == "forbidden":
        system += "\nFamille muette : dialogue reste vide dans chaque scène."
    if project["recipe"]["id"] == "story.brainrot" and not project.get("visual_universe"):
        system += "\nPar défaut : fruits anthropomorphes, espèce visuelle explicite. Préserve les identités explicitement imposées par le brief. Aucun quota de répliques."
    if not review and project["recipe"]["id"] == "story.brainrot":
        context["fruit_naming"] = _fruit_naming(project, operation)
        system += "\nNOMMAGE DES PERSONNAGES : " + context["fruit_naming"]["rule"]
    schema = contracts.response_schema(project) if structured else None
    if structured:
        context["contract_version"] = project["job"]["response_contract_version"]
        context["response_contract"] = contracts.wire_example(project, context["response_contract"])
        context["response_schema"] = schema
        if target not in {"outline", "block", "ideas"} and not review and operation != "discuss":
            system += ("\nCONTRAT D’ÉCRITURE : chaque scène porte narrative avec purpose (progression, reaction ou transition), "
                "event_ids, anchor_scene_index, evidence, action_seconds, reveals et hints. Les indices publics hints ne sont pas une confirmation reveals "
                "et ne donnent aucun savoir au héros. Une progression doit servir un événement. Une réaction ou transition sans nouvel événement "
                "doit viser une scène antérieure par anchor_scene_index (index à partir de zéro). "
                "Ne recopie ni characters dans scenario ni scene_events dans episode_state : l’application les assemble. "
                "Suis speech_budget ; une phrase naturelle courte et une réaction valent mieux que trois longues répliques.")
            if project["job"].get("response_contract_version") == contracts.VERSION:
                system += ("\nCONTINUITÉ VISUELLE 1 : fournis visual_continuity dans scenario (ou à la racine avec scene_edits). "
                    "dramatic_summary résume en une phrase le drame compris par le public et la croyance éventuelle du héros. "
                    "elements ne contient que les personnages qui changent d'apparence/tenue et les objets importants à reconnaître ou transmettre. "
                    "Ne fiche pas tous les accessoires. Pour un personnage, id est son ID canonique ; chaque objet distinct a son propre ID stable. "
                    "description décrit l'identité visuelle stable, reason explique l'utilité du suivi. scene_indices liste les scènes où il est visible, "
                    "même muet ; déclare aussi tous les participants visibles dans character_ids. "
                    "states décrit les changements datés : scene_index commence à zéro, at=start pour un état déjà acquis à l'ouverture, "
                    "at=end pour un état acquis pendant cette scène. appearance suit le physique ou l'état de l'objet, clothing suit la tenue, "
                    "holder_id suit la possession (ID personnage ou none pour aucun). null signifie conserver la valeur précédente, jamais revenir à zéro. "
                    "tracking=text suffit normalement ; tracking=reference justifie une image, et state.reference=true une variante majeure persistante. "
                    "Sans nouvelle variante, la dernière ancre visuelle reste utilisée avec les états textuels actualisés ; demande une nouvelle variante pour un changement majeur, y compris un retour à l'apparence initiale. "
                    "Une seule identité avec plusieurs états, jamais plusieurs Citron concurrents. Une pièce cassée échangée contre une invention reste un autre objet. "
                    "Réutilise visual_state_inherited pour la suite sans rejouer les acquisitions ; ses anciens scene_indices ne concernent pas la nouvelle unité. "
                    "Ne décris pas une émotion par une transformation involontaire : abattu=attitude découragée, pas corps au sol ; humilié, pas rétréci.")
        if "scene_edits" in context["response_contract"]:
            system += ("\nCORRECTION LOCALE : renvoie uniquement les scènes changées dans scene_edits, avec leur scene_index et leur scène complète. "
                "Les autres scènes et décors sont conservés automatiquement. episode_state actualise seulement les faits et connaissances effectivement joués. "
                "Reprends base_hash exactement. N’invente pas une correction de contenu lorsqu’une métadonnée suffit.")
    return CompletionRequest(model_id=project["model_id"], system_prompt=system,
        # Reasoning and the final JSON share the same output budget.
        user_prompt=json.dumps(context, ensure_ascii=False), max_tokens=80_000,
        temperature=.3 if review or operation == "edit_outline" else .75 if stage == "ideas" else .6, include_reasoning=True,
        output_schema=schema,
        operation_id=f"story.long.{operation}@{project['job']['response_contract_version'] if structured else '2.0.0'}",
        trace_context=dict(project_id=project["project_id"], stage=f"story_long_{operation}",
            cookbook_id="story.long", cookbook_version="2.0.0", recipe_revision=package["revision"],
            turn_id=project["job"]["request_id"]))
