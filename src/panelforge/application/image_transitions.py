"""Persistent image friezes, reviewed LLM proposals and idempotent factory handoff."""
from copy import deepcopy
import json
from threading import RLock

from panelforge.domain import image_transitions as policy
from . import image_transition_prompting as prompting
from .prompt_lab import CompletionRequest, ImageInput, StreamEventKind, LlmCallApplicationOutcome


class TransitionConflict(ValueError):
    pass


class ImageTransitionService:
    def __init__(self, *, store, assets, images, gateway, factory, sources):
        self.store, self.assets, self.images = store, assets, images
        self.gateway, self.factory, self.sources = gateway, factory, sources
        self._lock = RLock()
        # Never blindly replay a potentially completed LLM call after a restart.
        for project in store.list():
            changed = False
            for job in project["jobs"]:
                if job["status"] in {"queued", "running"}:
                    job.update(status="failed", error="Analyse interrompue au redémarrage. Relancez les transitions restantes.")
                    changed = True
            if changed:
                self._save(project)

    def _save(self, project):
        project["version"] += 1
        project["updated_at"] = policy.timestamp()
        self.store.save(project)
        return project

    def _load(self, identity, version=None):
        project = self.store.get(identity)
        if version is not None and project["version"] != version:
            raise TransitionConflict("La frise a changé. Rechargez-la avant d’appliquer cette modification.")
        return project

    def get(self, identity):
        with self._lock:
            return self._load(identity)

    def list(self):
        with self._lock:
            return [dict(id=p["id"], name=p["name"], image_count=len(p["frames"]), updated_at=p["updated_at"])
                    for p in self.store.list()]

    def public(self, project):
        result = deepcopy(project)
        result["transitions"] = deepcopy(policy.active(project))
        for transition in result["transitions"]:
            transition["state"] = policy.status(project, transition)
            transition["context_key"] = policy.context_key(project, transition)
            transition["effective"] = policy.effective(project, transition)
            transition["factory_ids"] = [d["factory_id"] for d in project["deliveries"]
                if d["transition_id"] == transition["id"] and d.get("factory_id")]
            transition["stale"] = bool(transition["proposal_context"] and
                transition["proposal_context"] != policy.context_key(project, transition) and
                transition["reviewed"] != policy.context_key(project, transition))
        result["jobs"] = [{k: deepcopy(v) for k, v in j.items() if k != "snapshots"} for j in project["jobs"][-10:]]
        for job in result["jobs"]:
            for item in job["results"]:
                item.pop("raw", None)
        ids = [d["factory_id"] for d in project["deliveries"] if d.get("factory_id")]
        result["factory_items"] = self.factory.describe_items(ids) if self.factory and ids else []
        return result

    def create(self, name):
        with self._lock:
            return self._save(policy.new_project(name))

    def update(self, identity, version, changes):
        if not isinstance(changes, dict) or set(changes) - {"name", "settings"}:
            raise ValueError("Champ de projet inconnu.")
        with self._lock:
            project = self._load(identity, version)
            if "name" in changes:
                project["name"] = policy.clean_text(changes["name"], "Nom", 120, True)
            if "settings" in changes:
                project["settings"] = policy.settings(changes["settings"], project["settings"])
            return self._save(project)

    def _frame(self, item):
        asset_id = item["asset_id"]
        if not self.assets.get(asset_id).media_type.startswith("image/"):
            raise ValueError("La référence doit être une image.")
        dimensions = self.images.dimensions(self.assets.read_bytes(asset_id))
        return dict(id=policy.identity("frame"), asset_id=asset_id,
                    label=policy.clean_text(item["label"], "Nom d’image", 160),
                    dimensions=list(dimensions), origin=deepcopy(item.get("origin", {})))

    def add_frames(self, identity, version, items, replace_id=None):
        frames = [self._frame(item) for item in items]
        with self._lock:
            project = self._load(identity, version)
            if replace_id:
                if len(frames) != 1:
                    raise ValueError("Choisissez une seule image de remplacement.")
                old = next((f for f in project["frames"] if f["id"] == replace_id), None)
                if old is None:
                    raise FileNotFoundError("Image à remplacer introuvable.")
                frames[0]["id"] = replace_id
                project["frames"][project["frames"].index(old)] = frames[0]
            else:
                if not frames or len(project["frames"]) + len(frames) > policy.MAX_IMAGES:
                    raise ValueError("La frise accepte de 1 à 100 images.")
                project["frames"].extend(frames)
            policy.reconcile(project)
            return self._save(project)

    def upload(self, identity, version, content, name, replace_id=None):
        # Check revision before creating any new asset.
        self.get(identity)
        with self._lock:
            self._load(identity, version)
        normalized = self.images.normalize_source(content)
        asset = self.assets.create(normalized, media_type="image/png")
        return self.add_frames(identity, version, [dict(asset_id=asset.asset_id,
            label=name[:160] or "Image importée", origin={"engine": "upload"})], replace_id)

    def order(self, identity, version, ids):
        with self._lock:
            project = self._load(identity, version)
            frames = {f["id"]: f for f in project["frames"]}
            if len(ids) != len(set(ids)) or any(i not in frames for i in ids):
                raise ValueError("Ordre d’images invalide.")
            # Missing IDs are explicitly removed; retained pairs keep their intentions.
            project["frames"] = [frames[i] for i in ids]
            policy.reconcile(project)
            return self._save(project)

    @staticmethod
    def _selected(project, ids):
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("Sélectionnez au moins une transition.")
        selected = [t for t in policy.active(project) if t["id"] in ids]
        if len(selected) != len(ids):
            raise TransitionConflict("Une transition ne fait plus partie de cette frise.")
        return selected

    def edit(self, identity, version, transition_id, changes):
        with self._lock:
            project = self._load(identity, version)
            transition = self._selected(project, [transition_id])[0]
            policy.edit_transition(transition, changes)
            return self._save(project)

    def review(self, identity, version, ids):
        with self._lock:
            project = self._load(identity, version)
            for transition in self._selected(project, ids):
                if not transition["intention"].strip():
                    raise ValueError("Rédigez ou proposez une intention avant de la valider.")
                transition["reviewed"] = policy.context_key(project, transition)
            return self._save(project)

    def apply_suggestion(self, identity, version, transition_id):
        with self._lock:
            project = self._load(identity, version)
            transition = self._selected(project, [transition_id])[0]
            suggestion = transition.get("suggestion")
            if not suggestion or suggestion["context"] != policy.context_key(project, transition):
                raise TransitionConflict("La proposition ne correspond plus aux images ou aux consignes.")
            transition.update(suggestion["value"])
            transition.update(manual=False, reviewed=None, suggestion=None)
            transition["proposal_context"] = policy.context_key(project, transition)
            return self._save(project)

    def begin_proposals(self, identity, version, ids, request_id):
        with self._lock:
            project = self._load(identity)
            previous = next((j for j in project["jobs"] if j["request_id"] == request_id), None)
            if previous:
                return project, previous["id"]
            self._load(identity, version)
            if any(j["status"] in {"queued", "running"} for j in project["jobs"]):
                raise TransitionConflict("Une analyse est déjà en cours pour cette frise.")
            selected = self._selected(project, ids)
            snapshots = []
            for transition in selected:
                first, last = policy.pair_frames(project, transition)
                snapshots.append(dict(transition_id=transition["id"], context=policy.context_key(project, transition),
                    first=deepcopy(first), last=deepcopy(last), transition=deepcopy(transition),
                    settings=policy.effective(project, transition)))
            job = dict(id=policy.identity("analysis"), request_id=request_id, status="queued",
                       completed=0, total=len(snapshots), current=None, error=None,
                       snapshots=snapshots, results=[], created_at=policy.timestamp())
            project["jobs"].append(job)
            return self._save(project), job["id"]

    def _input(self, frame, label):
        content = self.assets.read_bytes(frame["asset_id"])
        width, height = frame["dimensions"]
        scale = min(1.0, 1536 / max(width, height))
        content = self.images.prepare(content, (max(1, round(width * scale)), max(1, round(height * scale))))
        return ImageInput("image/png", content, label)

    def _report(self, call_id, accepted, error=None):
        reporter = getattr(self.gateway, "report_application_outcome", None)
        if reporter and call_id:
            try:
                reporter(call_id, LlmCallApplicationOutcome.ACCEPTED if accepted else LlmCallApplicationOutcome.REJECTED,
                         error_type=type(error).__name__ if error else None, error_message=str(error) if error else None)
            except Exception:
                pass  # Trace errors do not undo persisted proposals.

    def execute_proposals(self, identity, job_id):
        with self._lock:
            project = self._load(identity)
            job = next(j for j in project["jobs"] if j["id"] == job_id)
            if job["status"] != "queued":
                return
            job["status"] = "running"
            snapshots = deepcopy(job["snapshots"])
            overview = [{"index": i + 1, "label": f["label"]} for i, f in enumerate(project["frames"])]
            self._save(project)
        for snapshot in snapshots:
            call_id, raw, completed, accepted = None, "", False, False
            error = None
            try:
                with self._lock:
                    project = self._load(identity)
                    job = next(j for j in project["jobs"] if j["id"] == job_id)
                    job["current"] = snapshot["transition_id"]
                    self._save(project)
                transition = snapshot["transition"]
                user = dict(sequence=overview, settings=snapshot["settings"],
                    current_action=transition["action"], user_note=transition["note"],
                    previous_intention=transition["intention"],
                    start=snapshot["first"], end=snapshot["last"])
                request = CompletionRequest(model_id=snapshot["settings"]["model_id"],
                    system_prompt=prompting.SYSTEM, user_prompt=json.dumps(user, ensure_ascii=False),
                    images=(self._input(snapshot["first"], "Picture 1 — départ"),
                            self._input(snapshot["last"], "Picture 2 — arrivée")),
                    operation_id=prompting.OPERATION, output_schema=prompting.SCHEMA,
                    max_tokens=24000, include_reasoning=False,
                    trace_context=dict(project_id=identity, transition_id=snapshot["transition_id"], job_id=job_id))
                for event in self.gateway.stream(request):
                    if event.kind is StreamEventKind.DELTA:
                        raw += event.text
                    if event.kind in {StreamEventKind.COMPLETED, StreamEventKind.TRUNCATED}:
                        if event.result:
                            raw, call_id = event.result.content, event.result.call_id
                        if event.kind is StreamEventKind.TRUNCATED:
                            raise ValueError("Réponse tronquée ; l’intention précédente est conservée.")
                        completed = True
                        break
                if not completed:
                    raise ValueError("L’analyse a été interrompue avant sa réponse complète.")
                value = prompting.decode(raw)
                with self._lock:
                    project = self._load(identity)
                    transition = self._selected(project, [snapshot["transition_id"]])[0]
                    if policy.context_key(project, transition) != snapshot["context"]:
                        raise TransitionConflict("Images ou consignes modifiées pendant l’analyse ; proposition non appliquée.")
                    if not transition["manual"] or not transition["intention"]:
                        manual_action = transition["action"] if transition["manual"] else ""
                        transition.update(value)
                        if manual_action:
                            transition["action"] = manual_action
                        transition.update(reviewed=None, suggestion=None)
                        transition["proposal_context"] = policy.context_key(project, transition)
                    else:
                        transition["suggestion"] = dict(value=value, context=snapshot["context"])
                    self._save(project)
                    accepted = True
            except Exception as failure:
                error = failure
            finally:
                with self._lock:
                    project = self._load(identity)
                    job = next(j for j in project["jobs"] if j["id"] == job_id)
                    job["results"].append(dict(transition_id=snapshot["transition_id"], call_id=call_id,
                        applied=accepted, error=str(error) if error else None, raw=raw[:60000] if error else ""))
                    job["completed"] += 1
                    self._save(project)
                self._report(call_id, accepted, error)
        with self._lock:
            project = self._load(identity)
            job = next(j for j in project["jobs"] if j["id"] == job_id)
            errors = [r["error"] for r in job["results"] if r["error"]]
            job.update(status="failed" if errors else "succeeded", current=None,
                       error=" · ".join(errors)[:4000] if errors else None, finished_at=policy.timestamp())
            self._save(project)

    def send(self, identity, version, ids):
        if self.factory is None:
            raise ValueError("L’usine n’est pas configurée.")
        with self._lock:
            project = self._load(identity, version)
            selected = self._selected(project, ids)
            active_ids = [t["id"] for t in policy.active(project)]
            deliveries = []
            for transition in selected:
                key = policy.context_key(project, transition)
                if transition["reviewed"] != key:
                    raise TransitionConflict("Relisez et validez chaque transition avant l’envoi.")
                delivery = next((d for d in project["deliveries"]
                                 if d["transition_id"] == transition["id"] and d["key"] == key), None)
                if delivery is None:
                    delivery = dict(transition_id=transition["id"], key=key, factory_id=None,
                        entry=policy.factory_entry(project, transition, active_ids.index(transition["id"])))
                    project["deliveries"].append(delivery)
                deliveries.append(delivery)
            # Persist exact entries before receive: retry after a crash reuses the same dedupe material.
            self._save(project)
            received = self.factory.receive([d["entry"] for d in deliveries])
            for delivery, factory_id in zip(deliveries, received["ids"]):
                delivery.update(factory_id=factory_id, sent_at=policy.timestamp())
            self._save(project)
            return project, received["ids"], received["added"]
