"""Story ideation and revision, using the existing LLM gateway only on request."""
from copy import deepcopy
from datetime import UTC, datetime
import json
from threading import Event, RLock, Thread
from time import monotonic
from uuid import uuid4

from panelforge.domain.stories import (
    RECIPE_ID, RECIPE_VERSION, decode_story_json, extract_script_dialogue_cues, parse_response, response_contract,
    scenario_text, scene_intention, story_diagnostics, story_recipe_selection,
    story_recipe_spec, story_recipe_specs, validate_scenario,
)
from .prompt_lab import CompletionRequest, StreamEventKind, LlmCallApplicationOutcome, truncated_response_message
from .revised_documents import strip_markdown_fence


_MAX_LIVE_DRAFT_CHARS = 240_000
_MAX_LIVE_REASONING_CHARS = 144_000
_LIVE_SAVE_INTERVAL_SECONDS = 1.5

_DIALOGUE_REGISTER_POLICIES = {
    1: (
        "REGISTRE DES DIALOGUES — ORAL DIRECT. Dans les dialogues nouvellement écrits, emploie un français "
        "oral, quotidien et moins littéraire lorsque le personnage et la situation s’y prêtent. Garde les actions "
        "et la narration dans leur registre actuel. Ne force pas cette couleur dans chaque réplique."
    ),
    2: (
        "REGISTRE DES DIALOGUES — CRU. Dans les dialogues nouvellement écrits, préfère des formulations franches, "
        "familières ou vulgaires lorsque le personnage et la situation s’y prêtent : par exemple « ça pue » plutôt "
        "que l’euphémisme « ça sent mauvais ». Garde les actions et la narration dans leur registre actuel. "
        "La vulgarité reste naturelle, intelligible et propre à chaque personnage ; ce n’est pas un quota."
    ),
    3: (
        "REGISTRE DES DIALOGUES — TRÈS CRU / ARGOT. Dans les dialogues nouvellement écrits, autorise fortement le "
        "vocabulaire cru, l’argot et les tournures de rue ou internet compatibles avec le personnage — par exemple "
        "« ça schlingue » ou « wesh » — sans transformer automatiquement tous les personnages en caricatures. "
        "Garde les actions et la narration dans leur registre actuel ; ce n’est pas un quota."
    ),
}


class StoryConflict(ValueError):
    pass


class StoryCancelled(Exception):
    pass


def _now():
    return datetime.now(UTC).isoformat()


class StoryService:
    def __init__(self, *, gateway, store, recipes, traces=None, application_outcomes=None):
        self.gateway, self.store, self.recipes = gateway, store, recipes
        self.traces, self.application_outcomes = traces, application_outcomes
        self._lock = RLock()
        self._active = {}

    @staticmethod
    def _normalize(project):
        project.setdefault("recipe", {"id": RECIPE_ID, "version": RECIPE_VERSION})
        recipe = story_recipe_selection(project["recipe"])
        project["recipe"] = recipe
        legacy_model = project.get("model_id", "")
        project.setdefault("architect_model_id", legacy_model)
        project.setdefault("writer_model_id", legacy_model)
        project.setdefault("creation_mode", "ideas")
        project.setdefault("proposal_count", 3)
        project.setdefault("dialogue_register", 0)
        if story_recipe_spec(recipe["id"], recipe["version"]).get("dialogue_policy") == "forbidden":
            project["dialogue_register"] = 0
        project.setdefault("diagnostics", story_diagnostics(project.get("document", {}).get("scenario"),
            clip_seconds=project.get("clip_seconds", 10), target_scene_count=project.get("scene_count", 6),
            recipe_id=recipe["id"]))
        if isinstance(project.get("job"), dict):
            project["job"].setdefault("draft", "")
            project["job"].setdefault("reasoning", "")
        return project

    def recipe_specs(self):
        available = {(item["id"], item["version"]) for item in self.recipes.list()}
        return [spec for spec in story_recipe_specs() if (spec["id"], spec["version"]) in available]

    def create(self, *, title="Nouvelle histoire", brief="", clip_seconds=10, scene_count=6,
               recipe_id=RECIPE_ID, recipe_version=RECIPE_VERSION,
               architect_model_id="", writer_model_id="", creation_mode="ideas", proposal_count=3,
               dialogue_register=0):
        if not isinstance(title, str) or not title.strip() or len(title) > 160:
            raise ValueError("Donnez un nom à cette histoire (160 caractères maximum).")
        if not isinstance(brief, str) or len(brief) > 12000:
            raise ValueError("Idée trop longue (12 000 caractères maximum).")
        if type(clip_seconds) is not int or not 5 <= clip_seconds <= 15 or type(scene_count) is not int or not 1 <= scene_count <= 12:
            raise ValueError("Choisissez 1 à 12 micro-scènes de 5 à 15 secondes.")
        if creation_mode not in {"ideas", "script"}:
            raise ValueError("Mode de création inconnu.")
        if type(proposal_count) is not int or not 1 <= proposal_count <= 3:
            raise ValueError("Choisissez entre 1 et 3 propositions.")
        if type(dialogue_register) is not int or not 0 <= dialogue_register <= 3:
            raise ValueError("Le registre des dialogues doit être compris entre 0 et 3.")
        if creation_mode == "script" and not brief.strip():
            raise ValueError("Collez un script complet à suivre.")
        if creation_mode == "script":
            dialogue_register = 0
        recipe = story_recipe_selection({"id": recipe_id, "version": recipe_version})
        if story_recipe_spec(recipe["id"], recipe["version"]).get("dialogue_policy") == "forbidden":
            dialogue_register = 0
        if not any((item["id"], item["version"]) == (recipe["id"], recipe["version"])
                   for item in self.recipes.list()):
            raise ValueError("Cette famille d’histoire n’est pas installée dans ce Lab.")
        for model_id in (architect_model_id, writer_model_id):
            if not isinstance(model_id, str) or len(model_id) > 300:
                raise ValueError("Identifiant de modèle LLM invalide.")
        return self.store.save(dict(project_id=f"story-{uuid4().hex}", title=title.strip(), brief=brief.strip(),
            clip_seconds=clip_seconds, scene_count=scene_count, document=dict(concepts=[], selected_id=None, scenario=None),
            revisions=[], turns=[], job=None, model_id=writer_model_id.strip(), recipe=recipe,
            architect_model_id=architect_model_id.strip(), writer_model_id=writer_model_id.strip(), diagnostics=[],
            creation_mode=creation_mode, proposal_count=proposal_count, dialogue_register=dialogue_register))

    def get(self, project_id):
        with self._lock:
            project = self._normalize(self.store.get(project_id))
            job = project.get("job")
            if job and job["status"] in {"running", "cancelling"} and project_id not in self._active:
                job.update(status="interrupted", error="Le service a été interrompu. La dernière version et le brouillon sont conservés.")
                project = self.store.save(project)
            return project

    def _editable(self, project_id, expected_version):
        project = self.get(project_id)
        if project_id in self._active:
            raise StoryConflict("Un échange est déjà en cours pour cette histoire.")
        if type(expected_version) is not int or expected_version != project["version"]:
            raise StoryConflict("Cette histoire a changé dans un autre onglet. Rechargez-la avant de continuer.")
        return project

    def _snapshot(self, project, label, *, model_id=None, recipe_revision=None, call_id=None):
        recipe = story_recipe_selection(project.get("recipe"))
        project["revisions"].append(dict(revision=len(project["revisions"]) + 1, created_at=_now(), label=label,
            document=deepcopy(project["document"]), model_id=model_id, recipe=deepcopy(recipe),
            recipe_revision=recipe_revision, call_id=call_id))
        scenario = project["document"]["scenario"]
        project["diagnostics"] = story_diagnostics(scenario, clip_seconds=project["clip_seconds"],
            target_scene_count=project["scene_count"], recipe_id=recipe["id"])
        chosen = next((c for c in project["document"]["concepts"] if c["id"] == project["document"]["selected_id"]), None)
        if scenario or chosen:
            project["title"] = (scenario or chosen)["title"][:160]

    def select(self, project_id, concept_id, expected_version):
        with self._lock:
            project = self._editable(project_id, expected_version)
            document = project["document"]
            if concept_id not in {c["id"] for c in document["concepts"]}:
                raise ValueError("Choisissez une des propositions disponibles.")
            if document["selected_id"] == concept_id:
                return project
            document.update(selected_id=concept_id, scenario=None)
            self._snapshot(project, "Choix de l’histoire")
            return self.store.save(project)

    def edit_scene(self, project_id, index, expected_version, changes):
        with self._lock:
            project = self._editable(project_id, expected_version)
            scenario = deepcopy(project["document"].get("scenario"))
            if scenario is None:
                raise ValueError("Développez d’abord le scénario.")
            if type(index) is not int or not 0 <= index < len(scenario["scenes"]):
                raise ValueError("Micro-scène introuvable.")
            allowed = {"title", "opening_state", "action", "dialogue", "ending_state",
                       "relationship_state", "appearance_state", "sexual_state"}
            if not isinstance(changes, dict) or not changes or set(changes) - allowed:
                raise ValueError("Champs de micro-scène inconnus.")
            scenario["scenes"][index].update(deepcopy(changes))
            recipe = story_recipe_selection(project["recipe"])
            project["document"]["scenario"] = validate_scenario(scenario, recipe["id"], recipe["version"])
            self._snapshot(project, f"Édition manuelle de la scène {index + 1}")
            project["turns"].append(dict(role="assistant",
                text=f"La scène {index + 1} a été modifiée manuellement sans appel LLM.", created_at=_now()))
            return self.store.save(project)

    def restore(self, project_id, revision, expected_version):
        with self._lock:
            project = self._editable(project_id, expected_version)
            if type(revision) is not int or not 1 <= revision <= len(project["revisions"]):
                raise ValueError("Version d’histoire introuvable.")
            project["document"] = deepcopy(project["revisions"][revision - 1]["document"])
            self._snapshot(project, f"Reprise de la version {revision}")
            project["turns"].append(dict(role="assistant", text=f"Version {revision} réappliquée. Les échanges suivants partiront de ce document.", created_at=_now()))
            return self.store.save(project)

    def start(self, project_id, *, operation, instruction, model_id=None, expected_version, request_id):
        if operation not in {"ideas", "develop", "script", "revise"}:
            raise ValueError("Action d’écriture inconnue.")
        if not isinstance(instruction, str) or len(instruction) > 12000 or (operation == "revise" and not instruction.strip()):
            raise ValueError("Écrivez une demande de 1 à 12 000 caractères.")
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 100:
            raise ValueError("Identifiant de demande invalide.")
        with self._lock:
            project = self.get(project_id)
            if project.get("job", {}) and project["job"]["request_id"] == request_id:
                return project
            project = self._editable(project_id, expected_version)
            if operation == "ideas" and project["creation_mode"] != "ideas":
                raise ValueError("Ce projet suit un script fourni et ne génère pas de pistes.")
            if operation == "script" and project["creation_mode"] != "script":
                raise ValueError("Ce projet n’est pas configuré pour suivre un script.")
            if operation == "develop" and not project["document"]["selected_id"]:
                raise ValueError("Sélectionnez une histoire avant de la développer.")
            if operation == "revise" and not (project["document"]["concepts"] or project["document"]["scenario"]):
                raise ValueError("Créez d’abord une proposition ou structurez le script fourni.")
            role = "architect_model_id" if operation == "ideas" else "writer_model_id"
            chosen_model = model_id.strip() if isinstance(model_id, str) else project.get(role, "")
            if not chosen_model:
                chosen_model = project.get("model_id", "")
            if not chosen_model or len(chosen_model) > 300:
                raise ValueError("Choisissez un modèle LLM pour cette étape.")
            # Read active editorial instructions now; this call retains its snapshot.
            recipe = story_recipe_selection(project["recipe"])
            package = self.recipes.get(recipe["id"], recipe["version"])
            count = project["proposal_count"]
            label = {"ideas": f"Propose {count} histoire{'s' if count > 1 else ''} différente{'s' if count > 1 else ''}.",
                     "develop": "Développe l’histoire sélectionnée en scénario complet.",
                     "script": "Structure fidèlement le script fourni sans omettre ni réécrire ses dialogues.",
                     "revise": instruction.strip()}[operation]
            project["turns"].append(dict(role="user", text=instruction.strip() or label, created_at=_now()))
            project[role] = chosen_model
            project["model_id"] = chosen_model
            project["job"] = dict(request_id=request_id, status="running", operation=operation, started_at=_now(),
                phase="Préparation de l’écriture…", error=None, draft="", reasoning="", model_role=role,
                recipe=deepcopy(recipe), recipe_revision=package["revision"], call_id=None)
            cancel = Event()
            self._active[project_id] = cancel
            try:
                project = self.store.save(project)
                worker = Thread(target=self._run, args=(deepcopy(project), package, cancel), daemon=True,
                                name=f"story-{project_id[-8:]}")
                worker.start()
            except BaseException:
                self._active.pop(project_id, None)
                raise
            return project

    def cancel(self, project_id):
        with self._lock:
            project = self.get(project_id)
            event = self._active.get(project_id)
            if event:
                event.set()
                project["job"].update(status="cancelling", phase="Annulation demandée ; attente du moteur LLM…")
                project = self.store.save(project)
            return project

    def _request(self, project, package):
        operation = project["job"]["operation"]
        recipe = story_recipe_selection(project["recipe"])
        has_scenario = bool(project["document"]["scenario"])
        field = {"ideas": "plan.system", "develop": "writer.system", "script": "writer.system",
                 "revise": "revision.system"}[operation]
        seen = []
        document = project["document"]
        conversation = project["turns"][-16:]
        if operation == "ideas":
            # New pitches start from the author's brief and feedback. Previous
            # generated jokes/style are references to avoid, not a fresh brief.
            seen = [{"title": c["title"], "hook": c["hook"]} for c in document["concepts"]]
            document = dict(concepts=[], selected_id=None, scenario=None)
            conversation = [turn for turn in conversation if turn["role"] == "user"]
            for other in self.store.list(8):
                if other["project_id"] == project["project_id"]:
                    continue
                try:
                    previous = self._normalize(self.store.get(other["project_id"]))
                    if previous["recipe"] != recipe:
                        continue
                    seen.extend({"title": c["title"], "hook": c["hook"]} for c in previous["document"]["concepts"])
                except (OSError, ValueError):
                    continue
        count = project["proposal_count"]
        target_scene_count = project["scene_count"]
        clip_seconds = project["clip_seconds"]
        source_dialogues = extract_script_dialogue_cues(project["brief"]) if operation == "script" else []
        if operation == "script":
            contract_notes = (
                "MODE SCRIPT FIDÈLE. Le champ brief est le script source complet et prévaut sur le ton éditorial par défaut. "
                "Conserver tous ses événements, sa fin et l’intégralité de ses dialogues mot pour mot, dans le même ordre et avec les mêmes locuteurs. "
                "Chaque entrée source_dialogues possède un dialogue_id autoritaire. Recopier son text sans y ajouter une indication comme (Voix off). "
                "Stocker séparément le canal dans delivery (spoken, voice_over, off_screen, thought ou mediated) et l’indication originale facultative dans delivery_note. "
                f"La sortie doit contenir exactement {target_scene_count} micro-scène{'s' if target_scene_count > 1 else ''} "
                f"de {clip_seconds} secondes. Les titres, numéros, scènes ou rubriques du brief sont des événements source, pas un découpage imposé. "
                "Regrouper plusieurs événements successifs dans une même micro-scène lorsque nécessaire. Condenser uniquement leur mise en scène et leur description : "
                "ne supprimer aucun événement, ne paraphraser aucun dialogue et ne changer ni leur ordre ni la fin. "
                "Ne jamais augmenter le nombre de micro-scènes pour suivre le nombre de rubriques du brief. JSON strict conforme au contrat. "
                "1–12 personnages, 1–8 décors ; tous les identifiants référencés doivent exister."
            )
        elif operation == "develop" or (operation == "revise" and has_scenario):
            contract_notes = (
                f"JSON strict conforme au contrat. Tout scenario renvoyé contient exactement {target_scene_count} micro-scène"
                f"{'s' if target_scene_count > 1 else ''} de {clip_seconds} secondes dans scenario.scenes ; "
                "1–12 personnages, 1–8 décors. Tous les identifiants référencés doivent exister. "
                "En révision, discussion_only:true ne modifie rien et ne renvoie pas scenario ; sinon renvoyer le document entier. "
                "Le document courant et selected_id font foi."
            )
        else:
            contract_notes = (
                f"JSON strict conforme au contrat. Exactement {count} concept{'s' if count > 1 else ''} ; "
                "1–12 personnages, 1–8 décors. Tous les identifiants référencés doivent exister. "
                "En révision, discussion_only:true ne modifie rien ; sinon renvoyer le document entier. "
                "Le document courant et selected_id font foi."
            )
        context = dict(operation=operation, creation_mode=project["creation_mode"], proposal_count=count,
            brief=project["brief"], clip_seconds=project["clip_seconds"],
            target_scene_count=project["scene_count"], current_document=document,
            conversation=conversation, recent_concepts_to_avoid=seen[:24],
            response_contract=response_contract(operation, has_scenario, recipe["id"], recipe["version"], count),
            contract_notes=contract_notes)
        if source_dialogues:
            context["source_dialogues"] = source_dialogues
        system_prompt = package["fields"][field]
        if operation == "ideas" and count != 3:
            system_prompt += (f"\n\nCONTRAT DE CET APPEL : produis exactement {count} proposition"
                              f"{'s' if count > 1 else ''}, avec les identifiants concept-1"
                              f"{' à concept-' + str(count) if count > 1 else ''}. Cette quantité remplace toute mention de trois pistes ci-dessus.")
        elif operation == "script":
            system_prompt += (
                "\n\nMODE SCRIPT FIDÈLE POUR CET APPEL : le brief contient un script complet. Il est la source narrative autoritaire "
                "et remplace toute demande de développer une piste ou d’appliquer le ton par défaut. N’omets, ne reformule et n’invente aucun dialogue. "
                f"Produis exactement {target_scene_count} micro-scène{'s' if target_scene_count > 1 else ''} de {clip_seconds} secondes. "
                "Les sections du script sont des événements à regrouper, pas des micro-scènes obligatoires. Préserve mot pour mot tous les dialogues, "
                "dans leur ordre, ainsi que chaque événement et la fin ; compresse le découpage et les descriptions plutôt que le contenu. "
                "Pour chaque source_dialogues, conserve dialogue_id et text. delivery et delivery_note portent les indications de voix off, hors champ, pensée ou média ; "
                "ces indications ne doivent jamais être ajoutées au début de text."
            )
        elif operation == "revise" and not has_scenario and count != 3:
            system_prompt += (f"\n\nCONTRAT DE CE PROJET : le document contient exactement {count} proposition"
                              f"{'s' if count > 1 else ''}, identifiée{'s' if count > 1 else ''} de concept-1"
                              f"{' à concept-' + str(count) if count > 1 else ''}. Conserve cette quantité.")
        if operation == "develop" or (operation == "revise" and has_scenario):
            system_prompt += (
                f"\n\nFORMAT DE L’ÉPISODE : scenario.scenes contient exactement {target_scene_count} micro-scène"
                f"{'s' if target_scene_count > 1 else ''} de {clip_seconds} secondes. Ce nombre est obligatoire, même si le contenu "
                "doit être regroupé ou densifié. Une discussion_only peut ne renvoyer aucun scénario."
            )
        dialogue_register = project.get("dialogue_register", 0)
        if story_recipe_spec(recipe["id"], recipe["version"]).get("dialogue_policy") == "forbidden":
            dialogue_register = 0
        if operation in {"develop", "revise"} and dialogue_register:
            context["dialogue_register"] = dialogue_register
            system_prompt += "\n\n" + _DIALOGUE_REGISTER_POLICIES[dialogue_register]
            if operation == "revise":
                system_prompt += (
                    " Les dialogues déjà validés restent inchangés sauf si la demande de révision vise explicitement "
                    "leur formulation ; applique surtout ce registre aux nouvelles répliques."
                )
        return CompletionRequest(model_id=project["model_id"], system_prompt=system_prompt,
            user_prompt=json.dumps(context, ensure_ascii=False), temperature=.8 if operation == "ideas" else (.35 if operation == "script" else .65),
            max_tokens=24000, include_reasoning=True,
            operation_id=f"{recipe['id']}.{operation}@{recipe['version']}",
            trace_context=dict(project_id=project["project_id"], stage=f"story_{operation}", cookbook_id=recipe["id"],
                               cookbook_version=recipe["version"], recipe_revision=package["revision"], turn_id=project["job"]["request_id"]))

    def _run(self, project, package, cancel):
        project_id = project["project_id"]
        stream, call_id, raw, reasoning, completed, failure = None, None, "", "", False, None
        phase = "Préparation de l’écriture…"
        try:
            request = self._request(project, package)
            if cancel.is_set():
                raise StoryCancelled()
            stream = self.gateway.stream(request)
            last_save = monotonic()
            for event in stream:
                if event.result:
                    call_id = event.result.call_id
                    raw = event.result.content
                elif event.kind is StreamEventKind.DELTA:
                    raw += event.text or ""
                elif event.kind is StreamEventKind.REASONING and event.text:
                    remaining = _MAX_LIVE_REASONING_CHARS - len(reasoning)
                    if remaining > 0:
                        reasoning += event.text[:remaining]
                if event.kind is StreamEventKind.STATUS and event.text:
                    phase = event.text[:240]
                elif event.kind is StreamEventKind.REASONING:
                    phase = "Écriture du plan…"
                elif event.kind is StreamEventKind.DELTA:
                    phase = "Écriture de la réponse structurée…"
                if cancel.is_set():
                    raise StoryCancelled()
                if len(raw) > _MAX_LIVE_DRAFT_CHARS:
                    raise ValueError("Réponse trop volumineuse. Le brouillon est conservé.")
                if event.kind is StreamEventKind.TRUNCATED:
                    raise ValueError(truncated_response_message(request.max_tokens))
                if event.kind is StreamEventKind.COMPLETED:
                    if event.result is None:
                        raise ValueError("Le modèle n’a pas fourni de réponse finale.")
                    try:
                        data = decode_story_json(strip_markdown_fence(raw.strip()))
                    except ValueError as error:
                        raise ValueError("Le modèle n’a pas renvoyé un JSON valide. La dernière version et le brouillon sont conservés.") from error
                    recipe = story_recipe_selection(project["recipe"])
                    reply, document = parse_response(data, project["job"]["operation"], bool(project["document"]["scenario"]),
                        selected_id=project["document"]["selected_id"], recipe_id=recipe["id"], recipe_version=recipe["version"],
                        proposal_count=project["proposal_count"], source_script=project["brief"],
                        target_scene_count=project["scene_count"])
                    with self._lock:
                        if cancel.is_set():
                            raise StoryCancelled()
                        current = self.store.get(project_id)
                        if document:
                            current["document"].update(document)
                            if "concepts" in document and "scenario" not in document:
                                current["document"]["scenario"] = None
                                if current["job"]["operation"] == "ideas":
                                    current["document"]["selected_id"] = (document["concepts"][0]["id"]
                                        if current["proposal_count"] == 1 else None)
                            proposal_label = (f"{current['proposal_count']} proposition"
                                f"{'s' if current['proposal_count'] > 1 else ''}")
                            self._snapshot(current, {"ideas": proposal_label,
                                            "develop": "Scénario développé", "script": "Script structuré fidèlement",
                                            "revise": "Révision avec le LLM"}[current["job"]["operation"]],
                                           model_id=event.result.model_id, recipe_revision=package["revision"], call_id=call_id)
                        current["turns"].append(dict(role="assistant", text=reply, created_at=_now()))
                        current["job"].update(status="succeeded", phase="Écriture enregistrée",
                                              draft=raw[:_MAX_LIVE_DRAFT_CHARS],
                                              reasoning=reasoning, call_id=call_id, finished_at=_now())
                        self.store.save(current)
                        completed = True
                    break
                if (event.kind is StreamEventKind.STATUS
                        or monotonic() - last_save >= _LIVE_SAVE_INTERVAL_SECONDS):
                    with self._lock:
                        current = self.store.get(project_id)
                        current["job"].update(draft=raw[:_MAX_LIVE_DRAFT_CHARS], reasoning=reasoning, phase=phase)
                        self.store.save(current)
                    last_save = monotonic()
            if not completed:
                raise ValueError("L’échange a été interrompu avant la réponse complète. Vous pouvez réessayer.")
        except Exception as error:
            failure = error
            with self._lock:
                current = self.store.get(project_id)
                current["job"].update(status="cancelled" if isinstance(error, StoryCancelled) else "failed",
                    error="Échange annulé. La dernière version est conservée." if isinstance(error, StoryCancelled) else str(error),
                    draft=raw[:_MAX_LIVE_DRAFT_CHARS], reasoning=reasoning,
                    call_id=call_id, finished_at=_now())
                self.store.save(current)
        finally:
            try:
                if stream is not None and hasattr(stream, "close"):
                    stream.close()
                if call_id and self.application_outcomes:
                    self.application_outcomes.report_application_outcome(call_id,
                        LlmCallApplicationOutcome.ACCEPTED if completed else LlmCallApplicationOutcome.REJECTED,
                        error_type=type(failure).__name__ if failure else None, error_message=str(failure) if failure else None)
            finally:
                with self._lock:
                    self._active.pop(project_id, None)

    def export(self, project_id, *, include_duration=True):
        project = self.get(project_id)
        scenario = project["document"]["scenario"]
        if not scenario:
            raise ValueError("Développez d’abord le scénario.")
        duration = project["clip_seconds"] if include_duration else None
        return dict(text=scenario_text(scenario, duration), intentions=[scene_intention(scenario, i, duration) for i in range(len(scenario["scenes"]))])
