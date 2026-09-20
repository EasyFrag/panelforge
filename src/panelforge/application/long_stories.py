"""Compact context projections for the long-story V2 editorial workflow."""
from copy import deepcopy
import json

from panelforge.domain import long_stories as narrative
from panelforge.domain.stories import response_contract, story_recipe_spec
from .prompt_lab import CompletionRequest


def request(project, package, language_policy, register_policy=""):
    doc, operation = project["document"], project["job"]["operation"]
    target = narrative.scope(project)
    review = operation.startswith("review_")
    stage = "review" if review else "ideas" if target == "ideas" else "outline" if target == "outline" else "write"
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
    outline = doc.get("series_outline")
    if target == "ideas":
        context["response_contract"] = response_contract("ideas", False, project["recipe"]["id"],
                                                         project["recipe"]["version"])
        context["previous_pitches"] = [{"title": c["title"], "hook": c["hook"]} for c in doc["concepts"]]
    elif target in {"outline", "block"}:
        context["current_outline"] = outline
        context["response_contract"] = narrative.outline_example(project)
        context["outline_entry_contracts"] = narrative.outline_entry_contracts()
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
    if review:
        context["response_contract"] = narrative.review_example()
        context["review_target"] = target
        if target == "block":
            context["response_contract"] = {"reply": "Bilan du bloc et de ses raccords",
                "reviews": [{"unit_id": identity, **narrative.review_example()["review"]}
                            for identity in project["job"]["review_unit_ids"]]}
        else:
            context["allowed_review_targets"] = sorted(narrative.review_targets(project, target))
    elif operation.startswith("repair_"):
        context["review_to_address"] = deepcopy(doc["reviews"][target])
        context["correction_policy"] = "Une seule correction ciblée pour cet appel. Une nouvelle relecture sera nécessaire."
    profile = project["long_options"]["profile"]
    profile_prompt = package["profiles"].get(profile) or ("Choisis le profil adapté parmi : " + json.dumps(package["profiles"], ensure_ascii=False))
    system = "\n\n".join([package["prompts"]["common"], profile_prompt,
                              package["prompts"][stage], language_policy, register_policy])
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
        system += "\n" + package["prompts"]["review"]
        system += ("\nÉDITION EN UNE PASSE : examine l'arc puis corrige directement les petits défauts locaux. "
                   "Renvoie reply, series_outline corrigé complet et review portant sur CE RÉSULTAT. "
                   "Les issues ne listent que les problèmes encore présents, jamais ceux que tu viens de corriger. "
                   "N'invente pas une modification pour justifier ton rôle. Préserve les IDs, le brief, les options et les événements déjà rédigés. "
                   "Un choix majeur incompatible avec l'intention reste une remarque blocking. Résume les changements dans reply. "
                   "N'étends pas la mythologie pour résoudre un problème qui peut être clarifié par un geste ou une parole.")
    elif operation == "review_block":
        system += ("\nRelis ensemble units_to_review et leurs raccords. Renvoie reply et reviews, une entrée par unit_id demandé. "
                   "Une remarque scene-N se rapporte à la séquence de son entrée. N'écris aucun scénario dans cette réponse.")
    elif operation == "discuss":
        context["response_contract"] = {"reply": "Réponse à la question, sans réécrire le document", "discussion_only": True}
        system += "\nQUESTION DE L'AUTEUR : réponds uniquement avec reply et discussion_only:true. Ne modifie aucun document."
    if context["feedback_target"]:
        system += ("\nLe retour courant ne s'applique qu'à feedback_target. Préserve le reste ; explique les conséquences utiles. "
                   "Si une demande locale exige de changer l'architecture, réponds en discussion_only plutôt que de changer silencieusement les événements réservés.")
    if context["visual_universe"]:
        system += "\nUnivers explicitement choisi par l'auteur : " + context["visual_universe"] + ". Cet univers prévaut sur celui de la famille par défaut."
    if family.get("dialogue_policy") == "forbidden":
        system += "\nFamille muette : dialogue reste vide dans chaque scène."
    if project["recipe"]["id"] == "story.brainrot" and not context["visual_universe"]:
        system += "\nPar défaut : fruits anthropomorphes, noms fruités inventés en un mot, espèce visuelle explicite. Préserve les noms et identités explicitement imposés par le brief. Aucun quota de répliques."
    return CompletionRequest(model_id=project["model_id"], system_prompt=system,
        # Reasoning and the final JSON share the same output budget.
        user_prompt=json.dumps(context, ensure_ascii=False), max_tokens=80_000,
        temperature=.3 if review else .75 if stage == "ideas" else .6, include_reasoning=True,
        operation_id=f"story.long.{operation}@2.0.0",
        trace_context=dict(project_id=project["project_id"], stage=f"story_long_{operation}",
            cookbook_id="story.long", cookbook_version="2.0.0", recipe_revision=package["revision"],
            turn_id=project["job"]["request_id"]))
