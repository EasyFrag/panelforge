"""Story ideation and revision, using the existing LLM gateway only on request."""
from copy import deepcopy
from datetime import UTC, datetime
import json
from threading import Event, RLock, Thread
from time import monotonic
from uuid import uuid4

from panelforge.domain.stories import RECIPE_ID, RECIPE_VERSION, decode_story_json, parse_response, response_contract, scenario_text, scene_intention
from .prompt_lab import CompletionRequest, StreamEventKind, LlmCallApplicationOutcome, truncated_response_message
from .revised_documents import strip_markdown_fence


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

    def create(self, *, title="Nouvelle histoire", brief="", clip_seconds=10, scene_count=6):
        if not isinstance(title, str) or not title.strip() or len(title) > 160:
            raise ValueError("Donnez un nom à cette histoire (160 caractères maximum).")
        if not isinstance(brief, str) or len(brief) > 12000:
            raise ValueError("Idée trop longue (12 000 caractères maximum).")
        if type(clip_seconds) is not int or not 5 <= clip_seconds <= 15 or type(scene_count) is not int or not 2 <= scene_count <= 12:
            raise ValueError("Choisissez 2 à 12 micro-scènes de 5 à 15 secondes.")
        return self.store.save(dict(project_id=f"story-{uuid4().hex}", title=title.strip(), brief=brief.strip(),
            clip_seconds=clip_seconds, scene_count=scene_count, document=dict(concepts=[], selected_id=None, scenario=None),
            revisions=[], turns=[], job=None, model_id=""))

    def get(self, project_id):
        with self._lock:
            project = self.store.get(project_id)
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
        project["revisions"].append(dict(revision=len(project["revisions"]) + 1, created_at=_now(), label=label,
            document=deepcopy(project["document"]), model_id=model_id, recipe_revision=recipe_revision, call_id=call_id))
        scenario = project["document"]["scenario"]
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

    def restore(self, project_id, revision, expected_version):
        with self._lock:
            project = self._editable(project_id, expected_version)
            if type(revision) is not int or not 1 <= revision <= len(project["revisions"]):
                raise ValueError("Version d’histoire introuvable.")
            project["document"] = deepcopy(project["revisions"][revision - 1]["document"])
            self._snapshot(project, f"Reprise de la version {revision}")
            project["turns"].append(dict(role="assistant", text=f"Version {revision} réappliquée. Les échanges suivants partiront de ce document.", created_at=_now()))
            return self.store.save(project)

    def start(self, project_id, *, operation, instruction, model_id, expected_version, request_id):
        if operation not in {"ideas", "develop", "revise"}:
            raise ValueError("Action d’écriture inconnue.")
        if not isinstance(instruction, str) or len(instruction) > 12000 or (operation == "revise" and not instruction.strip()):
            raise ValueError("Écrivez une demande de 1 à 12 000 caractères.")
        if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 300:
            raise ValueError("Choisissez un modèle LLM.")
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 100:
            raise ValueError("Identifiant de demande invalide.")
        with self._lock:
            project = self.get(project_id)
            if project.get("job", {}) and project["job"]["request_id"] == request_id:
                return project
            project = self._editable(project_id, expected_version)
            if operation == "develop" and not project["document"]["selected_id"]:
                raise ValueError("Sélectionnez une histoire avant de la développer.")
            if operation == "revise" and not project["document"]["concepts"]:
                raise ValueError("Demandez d’abord trois propositions d’histoires.")
            # Read active editorial instructions now; this call retains its snapshot.
            package = self.recipes.get(RECIPE_ID, RECIPE_VERSION)
            label = {"ideas": "Propose trois histoires différentes.", "develop": "Développe l’histoire sélectionnée en scénario complet.", "revise": instruction.strip()}[operation]
            project["turns"].append(dict(role="user", text=instruction.strip() or label, created_at=_now()))
            project["model_id"] = model_id.strip()
            project["job"] = dict(request_id=request_id, status="running", operation=operation, started_at=_now(),
                phase="Préparation de l’écriture…", error=None, draft="", recipe_revision=package["revision"], call_id=None)
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
        has_scenario = bool(project["document"]["scenario"])
        field = {"ideas": "plan.system", "develop": "writer.system", "revise": "revision.system"}[operation]
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
                    seen.extend({"title": c["title"], "hook": c["hook"]} for c in self.store.get(other["project_id"])["document"]["concepts"])
                except (OSError, ValueError):
                    continue
        context = dict(operation=operation, brief=project["brief"], clip_seconds=project["clip_seconds"],
            target_scene_count=project["scene_count"], current_document=document,
            conversation=conversation, recent_concepts_to_avoid=seen[:24],
            response_contract=response_contract(operation, has_scenario),
            contract_notes="Le contrat montre la forme des objets. Développez les listes utiles. Exactement trois concepts ; "
                "1 à 18 scènes, 1 à 12 personnages, 1 à 8 décors. Tous les identifiants de scène et de dialogue doivent exister dans les fiches. "
                "En révision, discussion_only:true avec reply est autorisé pour discuter sans changer le document. "
                "Pour modifier un scénario existant, la sortie minimale est reply + scenario entier ; ne recopiez pas l’enveloppe current_document. "
                "Si les cartes concepts doivent aussi être actualisées, concepts entier est permis en complément du scénario ; "
                "conservez les identifiants et la sélection actuelle. "
                "Le document courant fait foi en cas de divergence avec un ancien échange, notamment après reprise d’une version.")
        return CompletionRequest(model_id=project["model_id"], system_prompt=package["fields"][field],
            user_prompt=json.dumps(context, ensure_ascii=False), temperature=.8 if operation == "ideas" else .65,
            max_tokens=24000, operation_id=f"{RECIPE_ID}.{operation}@{RECIPE_VERSION}",
            trace_context=dict(project_id=project["project_id"], stage=f"story_{operation}", cookbook_id=RECIPE_ID,
                               cookbook_version=RECIPE_VERSION, recipe_revision=package["revision"], turn_id=project["job"]["request_id"]))

    def _run(self, project, package, cancel):
        project_id = project["project_id"]
        stream, call_id, raw, completed, failure = None, None, "", False, None
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
                if cancel.is_set():
                    raise StoryCancelled()
                if len(raw) > 240000:
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
                    reply, document = parse_response(data, project["job"]["operation"], bool(project["document"]["scenario"]),
                                                     selected_id=project["document"]["selected_id"])
                    with self._lock:
                        if cancel.is_set():
                            raise StoryCancelled()
                        current = self.store.get(project_id)
                        if document:
                            current["document"].update(document)
                            if "concepts" in document and "scenario" not in document:
                                current["document"]["scenario"] = None
                                if current["job"]["operation"] == "ideas":
                                    current["document"]["selected_id"] = None
                            self._snapshot(current, {"ideas": "Trois propositions", "develop": "Scénario développé", "revise": "Révision avec le LLM"}[current["job"]["operation"]],
                                           model_id=event.result.model_id, recipe_revision=package["revision"], call_id=call_id)
                        current["turns"].append(dict(role="assistant", text=reply, created_at=_now()))
                        current["job"].update(status="succeeded", phase="Écriture enregistrée", draft="", call_id=call_id, finished_at=_now())
                        self.store.save(current)
                        completed = True
                    break
                if monotonic() - last_save >= 1:
                    with self._lock:
                        current = self.store.get(project_id)
                        current["job"].update(draft=raw[:240000], phase=(event.text[:240] if event.kind is StreamEventKind.STATUS and event.text else "Écriture en cours…"))
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
                    draft=raw[:240000], call_id=call_id, finished_at=_now())
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
