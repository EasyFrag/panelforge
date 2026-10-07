"""Durable visual journeys, independent of browser polling and video preparation."""
from copy import deepcopy
import hashlib
import logging
from threading import Event, RLock, Thread
import time

from panelforge.domain import image_journeys as policy
from . import image_journey_policies as policies
from .prompt_lab import CompletionRequest, ImageInput, StreamEventKind, LlmCallApplicationOutcome

logger = logging.getLogger(__name__)


class JourneyConflict(ValueError):
    pass


class ImageJourneyService:
    def __init__(self, *, store, assets, images, gateway, renderer, transitions=None, mask_compositor=None):
        self.store, self.assets, self.images = store, assets, images
        self.gateway, self.renderer, self.transitions = gateway, renderer, transitions
        self._lock, self._wake, self._stop = RLock(), Event(), Event()
        self._worker, self._claims = None, set()
        from .image_journey_trials import ImageJourneyTrials
        self.trials = ImageJourneyTrials(self)
        from .image_journey_edits import ImageJourneyEdits
        self.edits = ImageJourneyEdits(self)
        from .image_journey_protection import ImageJourneyProtection
        self.protection = ImageJourneyProtection(self, mask_compositor)

    def _save(self, project):
        project["version"] += 1
        project["updated_at"] = policy.timestamp()
        self.store.save(project)
        return project

    def _load(self, identity, version=None):
        project = self.store.get(identity)
        if version is not None and project["version"] != version:
            raise JourneyConflict("Le parcours a changé. Actualise-le ; ton intention saisie est conservée.")
        return project

    def get(self, identity):
        with self._lock:
            project = self._load(identity)
            self._refresh_comparisons(project)
            return project

    @staticmethod
    def _comparison_result(comparison, attempt):
        values = {key: attempt.get(key) for key in
                  ("status", "error", "output_asset_id", "output_dimensions", "started_at", "finished_at", "workflow_sha256")}
        values["attempt_id"] = attempt["id"]
        changed = any(comparison.get(key) != value for key, value in values.items())
        comparison.update(values)
        return changed

    def _refresh_comparisons(self, project):
        changed = False
        for comparison in project.get("comparisons", []):
            if comparison["status"] in {"succeeded", "failed", "cancelled"}:
                continue
            attempt = self.renderer.comparison_result(comparison)
            if attempt:
                changed = self._comparison_result(comparison, attempt) or changed
            elif comparison["status"] == "preparing":
                comparison.update(status="failed", error="Préparation interrompue. Tu peux relancer la comparaison.")
                changed = True
        if changed:
            self._save(project)

    def compare(self, identity, *, version, command, step_id, reference_megapixels):
        from uuid import NAMESPACE_URL, uuid5
        from panelforge.domain.minimax_edit import MinimaxEditSettings
        policy.request_id(command)
        MinimaxEditSettings(reference_megapixels=reference_megapixels)
        with self._lock:
            project = self._load(identity)
            comparisons = project.setdefault("comparisons", [])
            previous = next((c for c in comparisons if c["command"] == command), None)
            if previous:
                if previous["step_id"] != step_id or previous["settings"]["reference_megapixels"] != reference_megapixels:
                    raise JourneyConflict("Cette commande correspond déjà à une autre comparaison.")
                self._refresh_comparisons(project)
                return project
            self._load(identity, version)
            self._refresh_comparisons(project)
            if any(c["status"] not in {"succeeded", "failed", "cancelled"} for c in comparisons):
                raise JourneyConflict("Une comparaison est déjà en cours dans ce parcours.")
            step = next(s for s in project["steps"] if s["id"] == step_id)
            if not step.get("output_asset_id"):
                raise ValueError("Choisis une image déjà produite.")
            snapshot = self.renderer.comparison_snapshot(step, reference_megapixels)
            comparison_id = "journey-comparison-" + uuid5(NAMESPACE_URL, identity + "/" + command).hex
            comparison = dict(snapshot, id=comparison_id, command=command, journey_id=identity,
                step_id=step_id, render_request_id=comparison_id, status="preparing", created_at=policy.timestamp(),
                output_asset_id=None, error=None)
            comparisons.append(comparison)
            self._save(project)
            try:
                attempt = self.renderer.queue_comparison(comparison)
                self._comparison_result(comparison, attempt)
            except Exception as error:
                # The queue may have persisted its attempt before losing acknowledgement.
                attempt = self.renderer.comparison_result(comparison)
                if attempt:
                    self._comparison_result(comparison, attempt)
                else:
                    comparison.update(status="failed", error=str(error))
            self._save(project)
            return project

    def list(self):
        with self._lock:
            return [dict(id=p["id"], name=p["name"], status=p["status"], count=p["count"],
                         generated=policy.generated(p), updated_at=p["updated_at"],
                         thumbnail_asset_id=p["current_asset_id"]) for p in self.store.list()]

    def public(self, project):
        result = deepcopy(project)
        for key in ("creation_key", "commands", "abandoned_steps"):
            result.pop(key, None)
        result["analyses"] = [{k: v for k, v in c.items() if k not in {"raw", "context", "input_assets"}}
                              for c in result["analyses"][-10:]]
        from panelforge.domain import image_journey_edits as edits_policy
        result['ordered_steps'] = deepcopy(policy.ordered_steps(project))
        result['manual_generated'] = len(project.get('manual_steps', []))
        result['can_edit_sequence'] = edits_policy.can_edit(project) and project['id'] not in self._claims
        for operation in result.get('image_operations', []):
            operation.pop('request_key', None)
            operation.pop('analyses', None)
        for step in [*result['steps'], *result['ordered_steps'], *result.get('manual_steps', []), *result.get('image_operations', [])]:
            if 'protection' in step:
                step['protection'].pop('raw', None)
        result.update(journey_version=policy.journey_version(project),
                      journey_direction=policy.journey_direction(project),
                      journey_preset=policy.journey_preset(project),
                      generated=policy.generated(project), transitions_available=self.transitions is not None,
                      transferable_images=len(policy.sequence(project)["frames"]),
                      transferable_frame_ids=policy.transferable_frame_ids(project))
        return result

    def create(self, *, command, content, intention, count, progression_model_id, prompt_model_id,
               auto_mask=False, mask_model_id=None, journey_version=None, journey_direction=None, journey_preset=None):
        if journey_preset is not None:
            policy.journey_preset(dict(journey_preset=journey_preset))
        if journey_direction is not None:
            policy.journey_direction(dict(journey_direction=journey_direction))
        if journey_version is not None:
            policy.journey_version(dict(journey_version=journey_version))
        config = policy.configuration(intention, count, progression_model_id, prompt_model_id, mask_model_id)
        if type(auto_mask) is not bool:
            raise ValueError('Le réglage du masque automatique doit être un booléen.')
        config['auto_mask'] = auto_mask
        identity = policy.project_id(command)
        if not isinstance(content, bytes) or not content or len(content) > 25 * 1024**2:
            raise ValueError("Choisis une image de moins de 25 Mio.")
        with self._lock:
            try:
                previous = self.store.get(identity)
            except FileNotFoundError:
                previous = None
            selected_version = journey_version or (policy.journey_version(previous) if previous
                                                   else policy.DEFAULT_JOURNEY_VERSION)
            # An old client retrying a legacy creation must keep its original fingerprint.
            if not previous or "journey_version" in previous or selected_version != "1":
                config["journey_version"] = selected_version
            selected_preset = journey_preset or (policy.journey_preset(previous) if previous else "miniature")
            selected_direction = journey_direction or (policy.journey_direction(previous) if previous
                else "reverse" if selected_preset == "realistic" else policy.DEFAULT_JOURNEY_DIRECTION)
            if selected_preset == "realistic" and selected_direction != "reverse":
                raise ValueError("Aménagement réaliste utilise le parcours À rebours, depuis l’image terminée.")
            # Keep historical fingerprints, including explicit retries with the legacy preset.
            if selected_preset != "miniature" or previous and "journey_preset" in previous:
                config["journey_preset"] = selected_preset
            if not previous or "journey_direction" in previous or selected_direction != "forward":
                config["journey_direction"] = selected_direction
            key = policy.fingerprint(dict(config=config, source=hashlib.sha256(content).hexdigest()))
            if previous:
                if previous["creation_key"] != key:
                    raise JourneyConflict("Cette commande correspond déjà à un autre parcours.")
                return previous
            normalized = self.images.normalize_source(content)
            original_dimensions = self.images.dimensions(normalized)
            prepared, profile = self.renderer.prepare_source(normalized, journey_direction=selected_direction)
            original = self.assets.create(normalized, media_type="image/png", source_run_id=identity)
            source = original if prepared == normalized else self.assets.create(prepared, media_type="image/png", source_run_id=identity)
            project = policy.new_project(command, config, source.asset_id, profile['dimensions'], key)
            project.update(original_source_asset_id=original.asset_id, original_source_dimensions=list(original_dimensions),
                           render_profile=profile)
            self._save(project)
        self._wake.set()
        return project

    def pause(self, identity):
        with self._lock:
            project = self._load(identity)
            if project["status"] not in policy.ACTIVE:
                return project
            project["pause_requested"] = True
            project["status"] = "pausing" if identity in self._claims or project["phase"] == "rendering" else "paused"
            self._save(project)
        self._wake.set()
        return project

    def resume(self, identity, *, version, command, intention, progression_model_id, prompt_model_id, mask_model_id=None):
        policy.request_id(command)
        with self._lock:
            project = self._load(identity)
            if command in project["commands"]:
                return project
            self._load(identity, version)
            if project["status"] != "paused" or identity in self._claims:
                raise JourneyConflict("Attends la suspension du parcours avant de reprendre.")
            from panelforge.domain.image_journey_edits import pending
            if pending(project, sequence_only=True):
                raise JourneyConflict('Termine ou abandonne l’ajout en cours avant de reprendre le parcours.')
            config = policy.configuration(intention, project["count"], progression_model_id, prompt_model_id, mask_model_id)
            # A textarea submits LF even when its saved default originally contained CRLF.
            # Equivalent line endings must not discard an action or unlock its plan on Resume.
            changed = (project["intention"].replace("\r\n", "\n").replace("\r", "\n")
                       != config["intention"].replace("\r\n", "\n").replace("\r", "\n"))
            prompt_changed = project["prompt_model_id"] != config["prompt_model_id"]
            step = project["steps"][-1] if project["steps"] else None
            if step and not step.get("output_asset_id"):
                # A submitted render must be collected, even if the intention has changed.
                attempt = self.renderer.result(step) if project["phase"] == "rendering" else None
                if project["phase"] == "protecting" and step.get("raw_output_asset_id"):
                    pass  # Retry only localization/composition, keeping the finished render and its action.
                elif attempt and attempt["status"] not in {"failed", "cancelled"}:
                    pass
                elif changed or prompt_changed:
                    project["abandoned_steps"].append(project["steps"].pop())
                    project.update(phase="planning", next_action=None)
                else:
                    step.update(self.renderer.retry_failed(step))
                    if project["phase"] == "rendering" and (not attempt or attempt["status"] in {"failed", "cancelled"}):
                        project["phase"] = "queueing"
            elif changed and project["phase"] != "reviewing":
                project.update(phase="planning", next_action=None)
            if changed:
                project["intent_revision"] += 1
            project.update(config)
            project.update(status="running", pause_requested=False, error=None)
            project["commands"].append(command)
            self._save(project)
        self._wake.set()
        return project

    def sequence(self, identity):
        return policy.sequence(self.get(identity))

    def prepare_transitions(self, identity, *, frame_ids=None, frame_order="generation"):
        if self.transitions is None:
            raise ValueError("L’atelier de transitions n’est pas encore disponible.")
        with self._lock:
            project = self._load(identity)
            sequence = policy.sequence(project, frame_ids, frame_order=frame_order)
            if len(sequence["frames"]) < 2:
                raise ValueError("Une première image relue est nécessaire pour préparer les transitions.")
            key = policy.fingerprint(sequence)
            delivery = project["transition_exports"].get(key)
            if delivery is None:
                target = self.transitions.create(project["name"][:100] + " · transitions")["id"]
                delivery = dict(project_id=target, filled=False)
                project["transition_exports"][key] = delivery
                self._save(project)
            if not delivery["filled"]:
                transition_project = self.transitions.get(delivery["project_id"])
                if not transition_project["frames"]:
                    self.transitions.add_frames(delivery["project_id"], transition_project["version"], sequence["frames"])
                delivery["filled"] = True
                self._save(project)
            return dict(project_id=delivery["project_id"])

    def recover(self):
        """A restart never silently replays an interrupted model call."""
        with self._lock:
            for project in self.store.list():
                changed = self.trials.recover(project)
                changed = self.edits.recover(project) or changed
                for call in project["analyses"]:
                    if call["status"] == "running":
                        call.update(status="failed", error="Analyse interrompue au redémarrage.")
                        changed = True
                if project["status"] in policy.ACTIVE:
                    project.update(status="paused", pause_requested=True,
                        error="Parcours suspendu au redémarrage. Les images enregistrées sont conservées ; tu peux reprendre.")
                    changed = True
                if changed:
                    self._save(project)

    def start_worker(self):
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self.recover()
            self._stop.clear()
            self._worker = Thread(target=self._work, name="image-journeys", daemon=True)
            self._worker.start()

    def stop_worker(self):
        self._stop.set()
        self._wake.set()
        if self._worker:
            self._worker.join(timeout=2)

    def _work(self):
        while not self._stop.is_set():
            try:
                with self._lock:
                    candidates = [p["id"] for p in self.store.list()
                                  if p["status"] in policy.ACTIVE or p["phase"] == "rendering"
                                  or self.trials.needs_work(p) or self.edits.needs_work(p)]
                for identity in candidates:
                    if self._stop.is_set():
                        break
                    self.trials.advance(identity)
                    self.edits.advance(identity)
                    self.advance(identity)
            except Exception:
                logger.exception("Unable to advance the image journey journal")
            self._wake.wait(1)
            self._wake.clear()

    def _settle_pause(self, project):
        if project["status"] != "completed" and (project["pause_requested"] or self._stop.is_set()):
            project.update(status="paused", pause_requested=True)

    def advance(self, identity):
        """Advance one durable operation; also usable with fake gateways in user-run tests."""
        with self._lock:
            project = self._load(identity)
            if identity in self._claims or self._stop.is_set() or project["status"] == "completed":
                return
            if project["phase"] != "rendering" and (project["pause_requested"] or project["status"] == "paused"):
                if project["status"] == "pausing":
                    project["status"] = "paused"
                    self._save(project)
                return
            self._claims.add(identity)
        try:
            phase = project["phase"]
            if phase in {"planning", "reviewing"}:
                self._analyze(project)
            elif phase == "ready":
                with self._lock:
                    current = self._load(identity)
                    if current["pause_requested"] or self._stop.is_set():
                        self._settle_pause(current)
                    elif policy.reverse_endpoint_reached(current, dict(assessment="initial",
                            milestones=current["milestones"], completed_milestones=current["completed_milestones"])):
                        self._complete_reverse(current)
                    else:
                        current["steps"].append(dict(id=policy.identity("journey-step"), journey_id=identity, index=policy.generated(current) + 1,
                            source_asset_id=current["current_asset_id"], destination=current["destination"],
                            render_profile=deepcopy(current.get("render_profile")),
                            auto_mask=current.get("auto_mask", False),
                            journey_version=policy.journey_version(current), **policy.direction_snapshot(current),
                            action=deepcopy(current["next_action"]), output_asset_id=None, review=None,
                            prompt_model_id=current["prompt_model_id"], prompt="",
                            progression_model_id=current["analyses"][-1]["model_id"],
                            decision_analysis_id=current["analyses"][-1]["id"], intent_revision=current["intent_revision"],
                            prompt_request_id=policy.identity("prompt"), render_request_id=policy.identity("render"),
                            created_at=policy.timestamp()))
                        current.update(phase="prompting", next_action=None)
                    self._save(current)
            elif phase == "prompting":
                values = self.renderer.prepare(project["steps"][-1])
                with self._lock:
                    current = self._load(identity)
                    current["steps"][-1].update(values)
                    current["phase"] = "queueing"
                    self._settle_pause(current)
                    self._save(current)
            elif phase == "queueing":
                with self._lock:
                    current = self._load(identity)
                    if current["pause_requested"] or self._stop.is_set():
                        self._settle_pause(current)
                        self._save(current)
                        return
                    # Persist an idempotent request before handing it to the existing render queue.
                    current["phase"] = "rendering"
                    self._save(current)
                    attempt = self.renderer.queue(current["steps"][-1])
                    current["steps"][-1]["attempt_id"] = attempt["id"]
                    self._save(current)
            elif phase == "rendering":
                self._collect(project)
            elif phase == "protecting":
                self.protection.advance(identity, project["steps"][-1]["id"])
            else:
                raise ValueError("État du parcours inconnu.")
        except Exception as error:
            with self._lock:
                current = self._load(identity)
                current.update(status="paused", pause_requested=True, error=str(error))
                self._save(current)
        finally:
            with self._lock:
                self._claims.discard(identity)

    def _collect(self, project):
        attempt = self.renderer.result(project["steps"][-1])
        with self._lock:
            current = self._load(project["id"])
            if attempt is None:
                current["phase"] = "queueing"
                self._settle_pause(current)
                self._save(current)
            elif attempt["status"] == "succeeded":
                if not attempt.get("output_asset_id"):
                    raise ValueError("Le rendu terminé ne contient pas d’image.")
                profile = current.get('render_profile')
                if profile and list(self.images.dimensions(self.assets.read_bytes(attempt['output_asset_id']))) != profile['dimensions']:
                    raise ValueError('Le moteur a renvoyé une image aux dimensions différentes de celles du parcours.')
                current["steps"][-1].update(output_asset_id=attempt["output_asset_id"],
                    output_dimensions=attempt.get("output_dimensions"), attempt_id=attempt["id"],
                    settings=deepcopy(attempt["settings"]), recipe=deepcopy(attempt.get("recipe")),
                    generated_at=policy.timestamp())
                step = current["steps"][-1]
                if step.get("auto_mask", False):
                    step.update(raw_output_asset_id=step["output_asset_id"], output_asset_id=None)
                    current["phase"] = "protecting"
                else:
                    current["phase"] = "reviewing"
                self._settle_pause(current)
                self._save(current)
            elif attempt["status"] in {"failed", "cancelled"}:
                error = attempt.get("error") or "La génération a été annulée."
                if current["status"] != "paused" or current["error"] != error:
                    current.update(status="paused", pause_requested=True, error=error)
                    self._save(current)

    def _inputs(self, project):
        if project["phase"] == "reviewing":
            step = project["steps"][-1]
            items = [(step["source_asset_id"], "BEFORE — source de cette transformation"),
                     (step["output_asset_id"], "RESULT — résultat réellement généré à relire")]
            if project["source_asset_id"] != step["source_asset_id"]:
                items.append((project["source_asset_id"], "ORIGINAL — cadrage et identité du lieu"))
        else:
            items = [(project["current_asset_id"], "CURRENT — état actuel du décor")]
            if project["source_asset_id"] != project["current_asset_id"]:
                items.append((project["source_asset_id"], "ORIGINAL — cadrage et identité du lieu"))
        if policy.journey_direction(project) == "reverse":
            items = [(asset_id, label + (" — FINISHED_REFERENCE, " + policy.finished_label(project).lower() + " fourni"
                      if asset_id == project["source_asset_id"] else "")) for asset_id, label in items]
        images = []
        for asset_id, label in items:
            content = self.assets.read_bytes(asset_id)
            width, height = self.images.dimensions(content)
            scale = min(1, 1536 / max(width, height))
            content = self.images.prepare(content, (max(1, round(width * scale)), max(1, round(height * scale))))
            images.append(ImageInput("image/png", content, label))
        return items, tuple(images)

    def _analyze(self, snapshot):
        prompting = policies.progression(snapshot)
        identity = snapshot["id"]
        context = prompting.user_prompt(snapshot)
        call = dict(id=policy.identity("analysis"), status="running", created_at=policy.timestamp(),
                    model_id=snapshot["progression_model_id"], phase=snapshot["phase"],
                    policy_version=prompting.VERSION, journey_version=policy.journey_version(snapshot),
                    journey_direction=policy.journey_direction(snapshot), journey_preset=policy.journey_preset(snapshot),
                    context=context, input_assets=[], raw="", call_id=None)
        with self._lock:
            current = self._load(identity)
            current["analyses"].append(call)
            self._save(current)
        raw, call_id, last_save = "", None, time.monotonic()
        try:
            items, images = self._inputs(snapshot)
            self._call_update(identity, call["id"], input_assets=items)
            request = CompletionRequest(model_id=call["model_id"], system_prompt=prompting.SYSTEM,
                user_prompt=context, images=images, max_tokens=24000, include_reasoning=False,
                operation_id=prompting.OPERATION, output_schema=prompting.schema(snapshot),
                trace_context=dict(project_id=identity, analysis_id=call["id"]))
            completed = False
            for event in self.gateway.stream(request):
                if event.kind is StreamEventKind.DELTA:
                    raw += event.text
                if time.monotonic() - last_save >= 1:
                    self._call_update(identity, call["id"], raw=raw[:100000])
                    last_save = time.monotonic()
                if event.kind in {StreamEventKind.COMPLETED, StreamEventKind.TRUNCATED}:
                    if event.result:
                        raw, call_id = event.result.content, event.result.call_id
                    if event.kind is StreamEventKind.TRUNCATED:
                        raise ValueError("Analyse tronquée. Le parcours est suspendu et les images sont conservées.")
                    completed = True
                    break
            if not completed:
                raise ValueError("L’analyse s’est interrompue avant de fournir une réponse complète.")
            decision = prompting.decode(raw, snapshot)
            with self._lock:
                current = self._load(identity)
                current.update(destination=decision["destination"], milestones=decision["milestones"],
                    completed_milestones=decision["completed_milestones"], summary=decision["summary"],
                    plan_revision=current["intent_revision"], next_action=decision["next_action"], error=None)
                if snapshot["phase"] == "reviewing":
                    step = current["steps"][-1]
                    step["review"] = dict(assessment=decision["assessment"], observation=decision["observation"],
                        model_id=call["model_id"], analysis_id=call["id"], reviewed_at=policy.timestamp())
                    if decision["assessment"] != "unusable":
                        # Manual additions may exist after this automatic image (e.g. after a failed review).
                        current['current_asset_id'] = policy.ordered_steps(current)[-1]['output_asset_id']
                current["warning"] = ("Changement faible : la prochaine transformation sera renforcée."
                                      if decision["assessment"] == "similar" else None)
                if decision["assessment"] == "unusable":
                    current.update(status="paused", pause_requested=True, error=decision["observation"])
                elif policy.reverse_endpoint_reached(snapshot, decision):
                    self._complete_reverse(current)
                elif policy.generated(current) == current["count"]:
                    current.update(status="completed", phase="completed", pause_requested=False)
                    current["warning"] = ("Le parcours est terminé ; certains jalons restent inachevés."
                        if decision["completed_milestones"] < len(decision["milestones"])
                        else "La dernière image présente peu de changement." if decision["assessment"] == "similar" else None)
                else:
                    manual_tail = (policy.ordered_steps(current)[-1].get('manual', False)
                                   if current['steps'] else bool(current.get('manual_steps')))
                    current['phase'] = ('planning' if decision['next_action'] is None
                        or snapshot['phase'] == 'reviewing' and manual_tail else 'ready')
                    if current['phase'] == 'planning':
                        current['next_action'] = None
                    self._settle_pause(current)
                analysis = next(c for c in current["analyses"] if c["id"] == call["id"])
                analysis.update(status="succeeded", raw=raw[:100000], call_id=call_id, finished_at=policy.timestamp())
                if decision.get("next_action_error"):
                    analysis["next_action_error"] = decision["next_action_error"]
                self._save(current)
            self._report(call_id, True)
        except Exception as error:
            self._call_update(identity, call["id"], status="failed", raw=raw[:100000], call_id=call_id,
                              error=str(error), finished_at=policy.timestamp())
            self._report(call_id, False, error)
            raise

    @staticmethod
    def _complete_reverse(project):
        project.update(status="completed", phase="completed", pause_requested=False,
                       next_action=None, completion_reason="reverse_endpoint", error=None)
        if policy.generated(project) < project["count"]:
            endpoint = "État de départ" if policy.journey_preset(project) == "realistic" else "Terrain dégagé"
            project["warning"] = (f"{endpoint} atteint après {policy.generated(project)} images sur {project['count']} demandées. "
                                  "Tu peux ajouter une étape intermédiaire avec +.")

    def _call_update(self, identity, analysis_id, **changes):
        with self._lock:
            project = self._load(identity)
            next(c for c in project["analyses"] if c["id"] == analysis_id).update(changes)
            self._save(project)

    def _report(self, call_id, accepted, error=None):
        reporter = getattr(self.gateway, "report_application_outcome", None)
        if reporter and call_id:
            try:
                reporter(call_id, LlmCallApplicationOutcome.ACCEPTED if accepted else LlmCallApplicationOutcome.REJECTED,
                    error_type=type(error).__name__ if error else None, error_message=str(error) if error else None)
            except Exception:
                logger.debug("Unable to record the journey analysis outcome", exc_info=True)
