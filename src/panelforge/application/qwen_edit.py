"""Iterative Qwen workshop using the shared media, LLM and machine services."""

from collections import deque
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import UTC, datetime
import secrets
from threading import Event, RLock, Thread
import time
from uuid import uuid4

from panelforge.domain.qwen_edit import (ACTIVE_ATTEMPTS, MAX_ASSISTANT_IMAGES, QwenEditSettings,
    context_fingerprint, context_snapshot, prompt_is_ready, render_inputs, validate_prompt, validate_references)
from panelforge.domain.production import ComputeResource, ProductionWorkload
from .prompt_lab import (CompletionRequest, ImageInput, StreamEventKind, LlmCallApplicationOutcome,
                         truncated_response_message)
from .production_resources import ResourceWaitCancelled
from . import qwen_edit_assistance as assistance


class QwenEditConflict(ValueError):
    pass


def _id(prefix):
    return f"{prefix}-{uuid4().hex}"


def _now():
    return datetime.now(UTC).isoformat()


def _stage(project, stage_id):
    return next((s for s in project["stages"] if s["id"] == stage_id), None) or _missing("Étape introuvable.")


def _attempt(stage, attempt_id):
    return next((a for a in stage["attempts"] if a["id"] == attempt_id), None) or _missing("Essai introuvable.")


def _missing(message):
    raise ValueError(message)


def _new_stage(index, source_asset_id, *, settings=None, model_id="", mode="edit"):
    return {"id": _id("stage"), "index": index, "mode": mode, "source_asset_id": source_asset_id,
            "source_dimensions": None,
            "label": "Composition" if mode == "composition" else f"Modification {index}", "revision": 0,
            "settings": settings or QwenEditSettings(seed=str(secrets.randbits(64))).record(), "model_id": model_id,
            "draft": "", "prompt": "", "prompt_fingerprint": None, "summary": "", "references": [],
            "messages": [], "attempts": [], "accepted_attempt_id": None, "feedback_attempt_id": None}


class QwenEditService:
    def __init__(self, *, gateway, workflow, comfy, assets, projects, images, exporter=None,
                 work_coordinator=None, run_timeout=3600, poll_interval=1):
        self.gateway, self.workflow, self.comfy = gateway, workflow, comfy
        self.assets, self.projects, self.images = assets, projects, images
        self.exporter, self.work_coordinator = exporter, work_coordinator
        self.run_timeout, self.poll_interval = run_timeout, poll_interval
        self._lock = RLock()
        self._wake, self._stop = Event(), Event()
        self._worker = None
        self._prompt_claims = set()
        self._render_queue = deque()

    def list_models(self):
        return self.gateway.list_models()

    def _save(self, project):
        project["version"] += 1
        project["updated_at"] = _now()
        return self.projects.save(project)

    def get(self, project_id):
        with self._lock:
            return self.projects.get(project_id)

    def list(self):
        with self._lock:
            return [{"id": p["id"], "name": p["name"], "updated_at": p["updated_at"],
                     "active_stage_id": p["active_stage_id"], "stage_count": len(p["stages"]),
                     "parent_project_id": p.get("parent_project_id"),
                     "thumbnail_asset_id": p["stages"][-1]["source_asset_id"]}
                    for p in self.projects.list()]

    def create(self, *, name, content=None, composition=False):
        source_id = None
        if content is not None:
            source_id = self.assets.create(self.images.normalize_source(content), media_type="image/png").asset_id
        if not composition and source_id is None:
            raise ValueError("Choisis une image source.")
        if composition and source_id:
            raise ValueError("Une nouvelle composition utilise des références, sans source.")
        stage = _new_stage(1, source_id, mode="composition" if composition else "edit")
        if source_id:
            stage["source_dimensions"] = list(self.images.dimensions(self.assets.read_bytes(source_id)))
        if composition:
            stage["settings"]["resolution"] = "1"
        project = {"schema_version": 1, "id": _id("qwen"), "name": name.strip() or "Projet Qwen",
                   "version": 0, "created_at": _now(), "updated_at": _now(), "active_stage_id": stage["id"],
                   "stages": [stage], "export_path": None, "export_error": None}
        with self._lock:
            return self._save(project)

    def _editable(self, project, stage_id, revision=None):
        stage = _stage(project, stage_id)
        if project["active_stage_id"] != stage_id or stage["accepted_attempt_id"]:
            raise QwenEditConflict("Cette étape est validée. Utilise « Reprendre d’ici » pour créer une version.")
        if revision is not None and stage["revision"] != revision:
            raise QwenEditConflict("L’étape a changé dans une autre fenêtre. Ton brouillon local est conservé ; recharge le projet.")
        return stage

    def update(self, project_id, stage_id, *, revision, changes):
        allowed = {"name", "label", "settings", "model_id", "draft", "prompt", "references", "feedback_attempt_id"}
        if set(changes) - allowed:
            raise ValueError("Modification de projet non prise en charge.")
        with self._lock:
            project = self.projects.get(project_id)
            stage = self._editable(project, stage_id, revision)
            old_signature = context_fingerprint(stage)
            for key, value in changes.items():
                if key == "settings":
                    stage[key] = QwenEditSettings(**value).record()
                elif key == "references":
                    validate_references(value)
                    known = {ref["id"]: ref for ref in stage["references"]}
                    if any(ref["id"] not in known or ref["asset_id"] != known[ref["id"]]["asset_id"] for ref in value):
                        raise ValueError("Ajoute les images avant de modifier leurs usages.")
                    if set(known) != {ref["id"] for ref in value}:
                        raise ValueError("Désactive une image pour la retirer ; son historique est conservé.")
                    stage[key] = deepcopy(value)
                elif key == "feedback_attempt_id":
                    if value is not None and _attempt(stage, value)["status"] != "succeeded":
                        raise ValueError("Choisis un essai terminé comme retour visuel.")
                    stage[key] = value
                else:
                    limit = {"name": 120, "label": 120, "model_id": 300, "draft": 12000, "prompt": 24000}[key]
                    if not isinstance(value, str) or len(value) > limit:
                        raise ValueError(f"Champ {key} invalide (maximum {limit} caractères).")
                    if key in {"name", "label"} and not value.strip():
                        raise ValueError("Le nom ne peut pas être vide.")
                    (project if key == "name" else stage)[key] = value
            render_inputs(stage)
            if len([r for r in stage["references"] if r["active"]]) + bool(stage["source_asset_id"]) > MAX_ASSISTANT_IMAGES:
                raise ValueError("L’assistant accepte au maximum 32 images dans cet atelier.")
            if old_signature != context_fingerprint(stage):
                stage["prompt_fingerprint"] = None
            if "prompt" in changes:
                if stage["prompt"].strip():
                    validate_prompt(stage["prompt"], render_inputs(stage))
                    stage["prompt_fingerprint"] = context_fingerprint(stage)
                    stage["summary"] = "Prompt personnalisé, prêt pour le rendu."
                else:
                    stage["prompt_fingerprint"] = None
            stage["revision"] += 1
            return self._save(project)

    def add_reference(self, project_id, stage_id, *, revision, name, usage, role="", content=None, reuse_id=None):
        with self._lock:
            project = self.projects.get(project_id)
            stage = self._editable(project, stage_id, revision)
            if reuse_id:
                previous = next((r for s in project["stages"] for r in s["references"] if r["id"] == reuse_id), None)
                if previous is None:
                    raise ValueError("Référence précédente introuvable.")
                asset_id = previous["asset_id"]
                name, role = name or previous["name"], role or previous["role"]
            else:
                if not content:
                    raise ValueError("Choisis une image.")
                asset_id = self.assets.create(self.images.normalize_source(content), media_type="image/png").asset_id
            label = name.strip()[:70] or "Référence"
            existing = {r["name"].casefold() for r in stage["references"] if r["active"]}
            unique, suffix = label, 2
            while unique.casefold() in existing:
                unique, suffix = f"{label} {suffix}", suffix + 1
            stage["references"].append({"id": _id("ref"), "asset_id": asset_id, "name": unique,
                                        "role": role, "usage": usage, "active": True})
            validate_references(stage["references"])
            render_inputs(stage)
            if len([r for r in stage["references"] if r["active"]]) + bool(stage["source_asset_id"]) > MAX_ASSISTANT_IMAGES:
                raise ValueError("L’assistant accepte au maximum 32 images dans cet atelier.")
            stage["prompt_fingerprint"] = None
            stage["revision"] += 1
            return self._save(project)

    def begin_message(self, project_id, stage_id, *, revision, request_id):
        with self._lock:
            project = self.projects.get(project_id)
            stage = self._editable(project, stage_id)
            previous = next((m for m in stage["messages"] if m["request_id"] == request_id), None)
            if previous:
                return project, previous["id"]
            self._editable(project, stage_id, revision)
            if any(m["status"] in {"queued", "running"} for m in stage["messages"]):
                raise QwenEditConflict("L’assistant prépare déjà une instruction pour cette étape.")
            if not stage["draft"].strip() or not stage["model_id"]:
                raise ValueError("Écris une demande et choisis le modèle de l’assistant.")
            inputs = render_inputs(stage)
            if not inputs:
                raise ValueError("Ajoute au moins une référence de génération pour composer l’image.")
            feedback = _attempt(stage, stage["feedback_attempt_id"]) if stage["feedback_attempt_id"] else None
            feedback_id = feedback["output_asset_id"] if feedback else None
            snapshot = context_snapshot(stage)
            image_count = len(snapshot["references"]) + bool(stage["source_asset_id"]) + bool(feedback_id)
            if image_count > MAX_ASSISTANT_IMAGES:
                raise ValueError("Trop d’images pour l’assistant : désactive une référence ou le retour visuel.")
            message = {"id": _id("message"), "request_id": request_id, "created_at": _now(),
                       "text": stage["draft"].strip(), "model_id": stage["model_id"], "status": "queued",
                       "context": snapshot, "fingerprint": context_fingerprint(stage), "base_prompt": stage["prompt"],
                       "feedback_asset_id": feedback_id, "reply": "", "raw": "", "reasoning": "", "error": None,
                       "user_prompt": assistance.user_prompt(stage, stage["draft"].strip(),
                                                           {"attempt_id": feedback["id"]} if feedback else None),
                       "system_prompt": assistance.SYSTEM, "policy_version": assistance.VERSION}
            stage["messages"].append(message)
            stage["draft"] = ""
            stage["prompt_fingerprint"] = None
            stage["revision"] += 1
            self._save(project)
            return project, message["id"]

    def execute_message(self, project_id, stage_id, message_id):
        key = (project_id, message_id)
        with self._lock:
            project = self.projects.get(project_id)
            message = next(m for m in _stage(project, stage_id)["messages"] if m["id"] == message_id)
            if message["status"] != "queued" or key in self._prompt_claims:
                return
            self._prompt_claims.add(key)
            message["status"] = "running"
            self._save(project)
        request = None
        call_id = None
        raw, reasoning = "", ""
        try:
            images = []
            context = message["context"]
            for ref in context["render_inputs"]:
                images.append(ImageInput("image/png", self.assets.read_bytes(ref["asset_id"]),
                                         f"RENDER {ref['tag']} — {ref['name']} — {ref['role']}"))
            for ref in context["references"]:
                if ref["usage"] == "assistant":
                    images.append(ImageInput("image/png", self.assets.read_bytes(ref["asset_id"]),
                                             f"ASSISTANT ONLY — {ref['name']} — {ref['role']}"))
            if message["feedback_asset_id"]:
                images.append(ImageInput("image/png", self.assets.read_bytes(message["feedback_asset_id"]), "GENERATED FEEDBACK ONLY"))
            request = CompletionRequest(model_id=message["model_id"], system_prompt=message["system_prompt"],
                user_prompt=message["user_prompt"], images=tuple(images), max_tokens=80000, include_reasoning=True,
                operation_id=assistance.OPERATION, output_schema=assistance.SCHEMA,
                trace_context={"project_id": project_id, "stage_id": stage_id, "message_id": message_id})
            raw, reasoning, last_save, last_phase = "", "", time.monotonic(), None
            completed = False
            for event in self.gateway.stream(request):
                if event.kind is StreamEventKind.DELTA:
                    raw += event.text
                elif event.kind is StreamEventKind.REASONING:
                    reasoning += event.text
                if time.monotonic() - last_save > 1 or event.phase.value != last_phase:
                    self._message_update(project_id, stage_id, message_id, raw=raw, reasoning=reasoning,
                                         phase=event.phase.value)
                    last_save = time.monotonic()
                    last_phase = event.phase.value
                if event.kind in {StreamEventKind.COMPLETED, StreamEventKind.TRUNCATED}:
                    if event.result is not None:
                        raw, call_id = event.result.content, event.result.call_id
                        reasoning = event.result.reasoning_text or reasoning
                    self._message_update(project_id, stage_id, message_id, raw=raw, reasoning=reasoning, call_id=call_id)
                    if event.kind is StreamEventKind.TRUNCATED:
                        raise ValueError(truncated_response_message(request.max_tokens))
                    reply, prompt = assistance.decode(raw, context["render_inputs"])
                    with self._lock:
                        project = self.projects.get(project_id)
                        stage = _stage(project, stage_id)
                        current = next(m for m in stage["messages"] if m["id"] == message_id)
                        apply = (project["active_stage_id"] == stage_id and not stage["accepted_attempt_id"]
                                 and context_fingerprint(stage) == message["fingerprint"]
                                 and stage["prompt"] == message["base_prompt"])
                        current.update(status="succeeded", reply=reply, prompt=prompt, applied=apply,
                                       recovery_available=True, finished_at=_now())
                        if apply:
                            stage.update(prompt=prompt, prompt_fingerprint=message["fingerprint"], summary=reply)
                        self._save(project)
                    completed = True
                    self._report(call_id, True)
                    break
            if not completed:
                self._message_update(project_id, stage_id, message_id, raw=raw, reasoning=reasoning)
                raise ValueError("Le flux de l’assistant s’est interrompu. Le brouillon reste disponible.")
        except Exception as error:
            recoverable = False
            try:
                assistance.decode(raw, message["context"]["render_inputs"])
                recoverable = True
            except (ValueError, TypeError):
                pass
            self._message_update(project_id, stage_id, message_id, status="failed", error=str(error),
                                 raw=raw, reasoning=reasoning, recovery_available=recoverable, finished_at=_now())
            self._report(call_id, False, error)
        finally:
            with self._lock:
                self._prompt_claims.discard(key)

    def _report(self, call_id, accepted, error=None):
        reporter = getattr(self.gateway, "report_application_outcome", None)
        if reporter and call_id:
            try:
                reporter(call_id, LlmCallApplicationOutcome.ACCEPTED if accepted else LlmCallApplicationOutcome.REJECTED,
                         error_type=type(error).__name__ if error else None,
                         error_message=str(error) if error else None)
            except Exception:
                pass  # A trace reporting failure must not invalidate an accepted instruction.

    def _message_update(self, project_id, stage_id, message_id, **changes):
        with self._lock:
            project = self.projects.get(project_id)
            message = next(m for m in _stage(project, stage_id)["messages"] if m["id"] == message_id)
            message.update(changes)
            self._save(project)

    def recover_message(self, project_id, stage_id, message_id, *, revision):
        with self._lock:
            project = self.projects.get(project_id)
            stage = self._editable(project, stage_id, revision)
            message = next(m for m in stage["messages"] if m["id"] == message_id)
            if message["status"] in {"queued", "running"}:
                raise QwenEditConflict("Attends la fin de cet appel.")
            if context_fingerprint(stage) != message["fingerprint"]:
                raise QwenEditConflict("Les images ou leurs rôles ont changé. Actualise l’instruction avec le contexte actuel.")
            reply, prompt = assistance.decode(message["raw"], render_inputs(stage))
            stage.update(prompt=prompt, prompt_fingerprint=context_fingerprint(stage), summary=reply)
            stage["revision"] += 1
            return self._save(project)

    def queue_attempt(self, project_id, stage_id, *, revision, request_id):
        with self._lock:
            project = self.projects.get(project_id)
            stage = self._editable(project, stage_id)
            previous = next((a for a in stage["attempts"] if a["request_id"] == request_id), None)
            if previous:
                return project
            self._editable(project, stage_id, revision)
            if any(a["status"] in ACTIVE_ATTEMPTS | {"submitting"} for a in stage["attempts"]):
                raise QwenEditConflict("Un rendu de cette étape est déjà planifié ou en cours.")
            if any(m["status"] in {"queued", "running"} for m in stage["messages"]):
                raise QwenEditConflict("L’assistant prépare encore l’instruction de cette étape.")
            if not prompt_is_ready(stage):
                raise ValueError("L’instruction est à actualiser après le changement des images ou de leurs rôles.")
            if stage["draft"].strip():
                raise ValueError("Une demande n’a pas encore été envoyée à l’assistant. Envoie-la ou efface ce brouillon avant de générer.")
            inputs = render_inputs(stage)
            if not inputs:
                raise ValueError("Ajoute une référence de génération.")
            validate_prompt(stage["prompt"], inputs)
            settings = QwenEditSettings(**stage["settings"])
            if not settings.reuse_seed:
                settings = replace(settings, seed=str(secrets.randbits(64)))
                stage["settings"] = settings.record()
            source_size = self.images.dimensions(self.assets.read_bytes(stage["source_asset_id"])) if stage["source_asset_id"] else None
            attempt = {"id": _id("attempt"), "request_id": request_id, "created_at": _now(), "status": "queued",
                       "work_operation": "Qwen · " + project["name"],
                       "prompt": stage["prompt"], "summary": stage["summary"], "settings": settings.record(), "context": context_snapshot(stage),
                       "dimensions": list(settings.dimensions(source_size)), "message_ids": [m["id"] for m in stage["messages"]],
                       "feedback_asset_id": (_attempt(stage, stage["feedback_attempt_id"])["output_asset_id"]
                                             if stage["feedback_attempt_id"] else None),
                       "recipe": asdict(self.workflow.reference), "execution_id": None, "workflow_sha256": None,
                       "output_asset_id": None, "error": None, "cancel_requested": False}
            stage["attempts"].append(attempt)
            stage["revision"] += 1
            self._save(project)
            if self.work_coordinator:
                try:
                    self.work_coordinator.enqueue(attempt["id"], ComputeResource.REMOTE_GPU, ProductionWorkload.IMAGE_RENDER, attempt["work_operation"])
                except Exception as error:
                    attempt.update(status="failed", error="Planification impossible : " + str(error))
                    self._save(project)
                    raise
            self._render_queue.append((project_id, stage_id, attempt["id"]))
            self._wake.set()
            return project

    def start_worker(self):
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._stop.clear()
            pending = []
            for project in self.projects.list():
                changed = False
                for stage in project["stages"]:
                    for message in stage["messages"]:
                        if message["status"] in {"queued", "running"}:
                            message.update(status="failed", error="L’application a été arrêtée pendant cet appel. Le brouillon reçu est conservé.")
                            try:
                                assistance.decode(message.get("raw", ""), message["context"]["render_inputs"])
                                message["recovery_available"] = True
                            except (ValueError, TypeError):
                                message["recovery_available"] = False
                            changed = True
                    for attempt in stage["attempts"]:
                        if attempt["status"] == "submitting":
                            attempt.update(status="failed", error="Envoi interrompu avant réception de l’identifiant. Vérifie la file ComfyUI avant de relancer.")
                            changed = True
                        elif attempt["status"] in ACTIVE_ATTEMPTS:
                            pending.append((attempt["created_at"], project["id"], stage["id"], attempt["id"]))
                if changed:
                    self._save(project)
            self._render_queue = deque(value[1:] for value in sorted(pending))
            self._worker = Thread(target=self._work, name="qwen-edit-render", daemon=True)
            self._worker.start()

    def stop_worker(self):
        self._stop.set()
        self._wake.set()
        if self._worker:
            self._worker.join(timeout=2)

    def _work(self):
        while not self._stop.is_set():
            with self._lock:
                candidate = self._render_queue.popleft() if self._render_queue else None
            if candidate:
                self.execute_attempt(*candidate)
                if not self._stop.is_set() and self._attempt_record(*candidate)["status"] in ACTIVE_ATTEMPTS:
                    with self._lock:
                        self._render_queue.appendleft(candidate)
            else:
                self._wake.wait(1)
                self._wake.clear()

    def _attempt_record(self, project_id, stage_id, attempt_id):
        with self._lock:
            return _attempt(_stage(self.projects.get(project_id), stage_id), attempt_id)

    def _attempt_update(self, project_id, stage_id, attempt_id, **changes):
        with self._lock:
            project = self.projects.get(project_id)
            _attempt(_stage(project, stage_id), attempt_id).update(changes)
            return self._save(project)

    def execute_attempt(self, project_id, stage_id, attempt_id):
        cancelled = lambda: (self._stop.is_set() or self._attempt_record(project_id, stage_id, attempt_id)["status"] == "cancelled")
        try:
            with self._lock:
                project = self.projects.get(project_id)
                attempt = _attempt(_stage(project, stage_id), attempt_id)
                # Admission must reuse the queued requirement, even after a rename.
                # Older saved attempts predate this snapshot field.
                operation = attempt.get("work_operation", "Qwen · " + project["name"])
            lease = (self.work_coordinator.lease(attempt_id, ComputeResource.REMOTE_GPU, ProductionWorkload.IMAGE_RENDER,
                     operation, cancelled=cancelled) if self.work_coordinator else nullcontext())
            with lease:
                self._render(project_id, stage_id, attempt_id)
        except ResourceWaitCancelled:
            return
        except Exception as error:
            if self.work_coordinator:
                # Admission can fail before the lease takes ownership of its reservation.
                self.work_coordinator.cancel_queued(attempt_id)
            attempt = self._attempt_record(project_id, stage_id, attempt_id)
            if attempt["status"] == "cancelled":
                return
            if attempt["status"] == "submitting" and not attempt["execution_id"]:
                self._attempt_update(project_id, stage_id, attempt_id, status="failed", finished_at=_now(),
                    error="La confirmation d’envoi à ComfyUI n’est pas parvenue. Vérifie sa file avant de relancer : " + str(error))
                return
            if attempt["execution_id"]:
                try:
                    self.comfy.cancel_execution(attempt["execution_id"])
                except Exception as cancel_error:
                    self._attempt_update(project_id, stage_id, attempt_id, status="cancel_pending",
                                         error=f"{error} · Annulation à vérifier : {cancel_error}")
                    self._stop.wait(self.poll_interval)
                    return
            self._attempt_update(project_id, stage_id, attempt_id, status="failed", error=str(error), finished_at=_now())

    def _render(self, project_id, stage_id, attempt_id):
        attempt = self._attempt_record(project_id, stage_id, attempt_id)
        if attempt["status"] not in ACTIVE_ATTEMPTS or self._stop.is_set():
            return
        if attempt["status"] == "queued":
            settings = QwenEditSettings(**attempt["settings"])
            uploaded = []
            for ref in attempt["context"]["render_inputs"]:
                if self._stop.is_set() or self._attempt_record(project_id, stage_id, attempt_id)["cancel_requested"]:
                    return
                content = self.assets.read_bytes(ref["asset_id"])
                dimensions = tuple(attempt["dimensions"]) if ref["id"] == "source" else settings.dimensions(self.images.dimensions(content))
                prepared = self.images.prepare(content, dimensions)
                result = self.comfy.upload_image(prepared, filename=f"{attempt_id}-{len(uploaded) + 1}.png", subfolder="panelforge/qwen-edit")
                uploaded.append(result.workflow_value)
            graph = self.workflow.build(images=uploaded, prompt=attempt["prompt"], settings=settings,
                dimensions=tuple(attempt["dimensions"]), composition=attempt["context"]["mode"] == "composition",
                output_prefix=f"image/qwen-edit/{project_id}/{attempt_id}")
            digest = self.projects.save_workflow(project_id, attempt_id, graph)
            with self._lock:
                current = self._attempt_record(project_id, stage_id, attempt_id)
                if current["cancel_requested"] or self._stop.is_set():
                    return
                self._attempt_update(project_id, stage_id, attempt_id, status="submitting", workflow_sha256=digest)
            execution_id = self.comfy.submit_workflow(graph)
            self._attempt_update(project_id, stage_id, attempt_id, execution_id=execution_id, status="running", started_at=_now())
        else:
            execution_id = attempt["execution_id"]
        if self.work_coordinator:
            self.work_coordinator.report_execution_id(attempt_id, execution_id)
            self.work_coordinator.report_stage(attempt_id, "Génération Qwen")
        deadline = time.monotonic() + self.run_timeout
        while not self._stop.is_set():
            current = self._attempt_record(project_id, stage_id, attempt_id)
            entry = self.comfy.get_history(execution_id).get(execution_id)
            if entry:
                status = entry.get("status", {})
                if status.get("status_str") in {"error", "failed"}:
                    raise ValueError("ComfyUI : " + str(status.get("messages") or "le rendu a échoué"))
                output = entry.get("outputs", {}).get(self.workflow.output_node_id, {}).get("images", [])
                if output:
                    file = output[0]
                    content = self.comfy.download_output(filename=file["filename"], subfolder=file.get("subfolder", ""), folder_type=file.get("type", "output"))
                    size = self.images.dimensions(content)
                    asset = self.assets.create(self.images.normalize_source(content), media_type="image/png")
                    self._attempt_update(project_id, stage_id, attempt_id, status="succeeded", output_asset_id=asset.asset_id,
                                         output_dimensions=list(size), error=None, finished_at=_now())
                    return
                events = [event[0] for event in status.get("messages", []) if isinstance(event, (list, tuple)) and event]
                if "execution_interrupted" in events or status.get("status_str") in {"cancelled", "interrupted"}:
                    self._attempt_update(project_id, stage_id, attempt_id, status="cancelled", finished_at=_now())
                    return
                if status.get("completed"):
                    raise ValueError("Le rendu s’est terminé sans l’image attendue.")
            if current["cancel_requested"] or current["status"] == "cancel_pending":
                result = self.comfy.cancel_execution(execution_id)
                action = getattr(getattr(result, "action", None), "value", getattr(result, "action", None))
                if action == "already_finished" and time.monotonic() < deadline:
                    # The history may become visible on the next poll.
                    self._stop.wait(self.poll_interval)
                    continue
                self._attempt_update(project_id, stage_id, attempt_id, status="cancelled", finished_at=_now())
                return
            if time.monotonic() > deadline:
                raise TimeoutError("Le rendu Qwen a dépassé le délai configuré.")
            self._stop.wait(self.poll_interval)

    def cancel_attempt(self, project_id, stage_id, attempt_id):
        with self._lock:
            project = self.projects.get(project_id)
            attempt = _attempt(_stage(project, stage_id), attempt_id)
            if attempt["status"] not in ACTIVE_ATTEMPTS | {"submitting"}:
                return project
            attempt["cancel_requested"] = True
            if attempt["status"] == "queued":
                attempt["status"] = "cancelled"
                if self.work_coordinator:
                    self.work_coordinator.cancel_queued(attempt_id)
            self._save(project)
            self._wake.set()
            return project

    def accept(self, project_id, stage_id, attempt_id, *, revision):
        with self._lock:
            project = self.projects.get(project_id)
            previous = _stage(project, stage_id)
            if previous["accepted_attempt_id"] == attempt_id:
                return project
            stage = self._editable(project, stage_id, revision)
            attempt = _attempt(stage, attempt_id)
            if attempt["status"] != "succeeded":
                raise ValueError("Seul un résultat terminé peut être validé.")
            if any(a["status"] in ACTIVE_ATTEMPTS | {"submitting"} for a in stage["attempts"]) or any(m["status"] in {"queued", "running"} for m in stage["messages"]):
                raise QwenEditConflict("Attends la fin des traitements de cette étape.")
            stage["accepted_attempt_id"] = attempt_id
            stage["revision"] += 1
            next_stage = _new_stage(stage["index"] + 1, attempt["output_asset_id"],
                                    settings=deepcopy(attempt["settings"]), model_id=stage["model_id"])
            next_stage["source_dimensions"] = deepcopy(attempt["output_dimensions"])
            project["stages"].append(next_stage)
            project["active_stage_id"] = next_stage["id"]
            self._save(project)
        return self.export(project_id)

    def restore_attempt(self, project_id, stage_id, attempt_id, *, revision):
        with self._lock:
            project = self.projects.get(project_id)
            stage = self._editable(project, stage_id, revision)
            attempt = _attempt(stage, attempt_id)
            restored = {r["id"]: deepcopy(r) for r in attempt["context"]["references"]}
            stage["references"] = [restored.pop(r["id"], {**r, "active": False}) for r in stage["references"]]
            stage["references"].extend(restored.values())
            # Preserve snapshot order, which determines <imageN> in the saved prompt.
            order = {r["id"]: i for i, r in enumerate(attempt["context"]["references"])}
            stage["references"].sort(key=lambda r: order.get(r["id"], len(order)))
            stage["settings"] = deepcopy(attempt["settings"])
            stage.update(prompt=attempt["prompt"], summary=attempt["summary"], draft="", feedback_attempt_id=None)
            stage["prompt_fingerprint"] = context_fingerprint(stage)
            stage["revision"] += 1
            return self._save(project)

    def resume(self, project_id, stage_id, *, request_id):
        with self._lock:
            for existing in self.projects.list():
                if existing.get("resume_request_id") == request_id and existing.get("parent_project_id") == project_id:
                    return existing
            old = self.projects.get(project_id)
            selected = _stage(old, stage_id)
            project = deepcopy(old)
            project.update(id=_id("qwen"), name=old["name"] + " · reprise", parent_project_id=project_id,
                           resume_request_id=request_id, created_at=_now(), export_path=None, export_error=None,
                           stages=deepcopy(old["stages"][:selected["index"] - 1]))
            stage = _new_stage(selected["index"], selected["source_asset_id"], settings=deepcopy(selected["settings"]),
                               model_id=selected["model_id"], mode=selected["mode"])
            stage["source_dimensions"] = deepcopy(selected["source_dimensions"])
            stage["references"] = [{**r, "active": False} for r in selected["references"]]
            project["stages"].append(stage)
            project["active_stage_id"] = stage["id"]
            for previous in project["stages"][:-1]:
                for attempt in previous["attempts"]:
                    if attempt.get("workflow_sha256"):
                        import json
                        self.projects.save_workflow(project["id"], attempt["id"], json.loads(self.projects.read_workflow(project_id, attempt["id"])))
            return self._save(project)

    def export(self, project_id):
        if self.exporter is None:
            return self.get(project_id)
        with self._lock:
            project = self.projects.get(project_id)
            try:
                project["export_path"] = self.exporter.export(project, self.assets, self.projects)
                project["export_error"] = None
            except Exception as error:
                project["export_error"] = str(error)
            return self._save(project)

    def public(self, project):
        value = deepcopy(project)
        for stage in value["stages"]:
            stage["prompt_ready"] = prompt_is_ready(stage)
            stage["render_inputs"] = render_inputs(stage)
            stage["render_dimensions"] = list(QwenEditSettings(**stage["settings"]).dimensions(stage["source_dimensions"]))
            for message in stage["messages"]:
                # Full request is in the journal/export; avoid sending it on every poll.
                message["can_recover"] = bool(message.get("recovery_available")
                    and message["fingerprint"] == context_fingerprint(stage))
                message["has_draft"] = bool(message.get("raw"))
                message["has_reasoning"] = bool(message.get("reasoning"))
                message.pop("raw", None)
                message.pop("reasoning", None)
                message.pop("system_prompt", None)
                message.pop("user_prompt", None)
        return value
