"""Persistent, bounded screenplay workflow with shared production services."""
from copy import deepcopy
import json
import time
from datetime import datetime
from threading import Event, RLock, Thread
from uuid import uuid4, uuid5, NAMESPACE_URL
from panelforge.domain import story_v2 as policy
from . import story_v2_prompting as prompts
from .prompt_lab import CompletionRequest, StreamEventKind, LlmCallApplicationOutcome
from .revised_documents import strip_markdown_fence

class StoryV2Conflict(ValueError):
    pass

class StoryV2Service:
    def __init__(self, store, gateway, production):
        self.store, self.gateway, self.production = store, gateway, production
        self._lock, self._wake, self._stop = RLock(), Event(), Event()
        self._thread = None

    def _save(self, p):
        p.update(version=p["version"]+1, updated_at=policy.now())
        self.store.save(p)
        return p

    def _load(self, identity, version=None, editable=False):
        p = self.store.get(identity)
        if not p["settings"].get("image_model"):
            p["settings"]["image_model"] = policy.Settings.model_fields["image_model"].default
        # Keep an already-started legacy cycle's final check when explicitly resumed.
        narrative = {"queued", "writing", "reviewing", "repairing", "polishing"}
        legacy_control = ((p.get("scenario") or {}).get("next_step") in {"write", "review", "repair", "polish", "final_review"}
            or p["status"] in narrative or (p["status"] in {"paused", "failed"} and p.get("resume_stage") in narrative))
        p["settings"].setdefault("final_review_enabled", legacy_control)
        # Existing stories keep their timing until an explicit target is chosen.
        p["settings"] = policy.Settings.model_validate({"scene_duration":None, **p["settings"]}).model_dump()
        if version is not None and p["version"] != version:
            raise StoryV2Conflict("Le projet a changé. Actualisez avant de réessayer.")
        if editable and p["status"] in policy.ACTIVE:
            raise StoryV2Conflict("Mettez le parcours en pause avant de modifier son scénario.")
        return p

    def list(self):
        with self._lock:
            return [dict(id=p["id"], title=p["script"]["title"] if p.get("script") else p["settings"]["idea"][:75],
                status=p["status"], updated_at=p["updated_at"]) for p in self.store.list()]

    def get(self, identity):
        with self._lock:
            p = deepcopy(self._load(identity))
        p.pop("factory_entries", None)
        p.pop("raw", None)
        p["calls"] = [{k:v for k,v in c.items() if k != "result"} for c in p["calls"]]
        if p.get("scenario"):
            p["scenario"].pop("pre_polish", None)
        p["history"] = [{k:v for k,v in h.items() if k != "script"} for h in p["history"]]
        if p.get("episode_id"):
            p["episode"] = self.production.episodes.get(p["episode_id"])
        p["videos"] = self.production.results(p)
        return p

    def preferences(self):
        return {**policy.default_settings(), **self.store.preferences(), "idea":""}

    def create(self, command, settings):
        settings = policy.Settings.model_validate(settings).model_dump()
        if settings["mode"] == "automatic" and not settings["image_model"]:
            raise ValueError("Choisissez le modèle image dans Réglages pour le parcours automatique.")
        identity = "storyv2-" + uuid5(NAMESPACE_URL, "panelforge:story-v2:"+command).hex
        with self._lock:
            try:
                old = self.store.get(identity)
                if old["settings"] != settings:
                    raise StoryV2Conflict("Cette commande a déjà créé une autre histoire.")
                return old
            except FileNotFoundError:
                pass
            p = dict(id=identity, schema_version=1, policy_version=policy.VERSION, version=0,
                created_at=policy.now(), settings=settings, status="queued", script=None, review=None,
                approved=None, episode_id=None, history=[], calls=[], factory_ids=[], factory_entries=[],
                pause_requested=False, error=None, feedback="", resume_stage="queued",
                needs_review=False, repair_attempt=0)
            self._reset_scenario(p)
            self._save(p)
            self.store.save_preferences(settings)
            self._wake.set()
            return p

    def update(self, identity, version, script, settings):
        with self._lock:
            p = self._load(identity, version, editable=True)
            settings = policy.Settings.model_validate(settings).model_dump()
            parsed, timing_pending = None, False
            if script is not None:
                parsed = policy.Script.model_validate(script).model_dump()
                try:
                    policy.validate_script(parsed, settings)
                except ValueError:
                    changed_timing = any(settings[k] != p["settings"].get(k) for k in ("duration", "scene_duration"))
                    if not (changed_timing or p.get("timing_pending")):
                        raise
                    timing_pending = True  # Rewriting remains an explicit action after saving the new target.
            if p.get("script"):
                p["history"].append(dict(at=policy.now(), script=deepcopy(p["script"]),
                    episode_id=p["episode_id"], factory_ids=p["factory_ids"], settings=deepcopy(p["settings"]), reason="Modification"))
            p.update(settings=settings, script=parsed, review=None, approved=None,
                     status="awaiting_review" if parsed else "draft", error=None, pause_requested=False,
                     factory_ids=[], factory_entries=[], scenario=None, progress=None, timing_pending=timing_pending)
            self.store.save_preferences(settings)
            return self._save(p)

    def restore(self, identity, version, index):
        with self._lock:
            p = self._load(identity, version, editable=True)
            if not 0 <= index < len(p["history"]):
                raise ValueError("Version introuvable.")
            entry = deepcopy(p["history"][index])
            return self.update(identity, version, entry["script"], {"scene_duration":None, **entry.get("settings", p["settings"])})

    def revise(self, identity, version, feedback, sequence_id=None):
        with self._lock:
            p = self._load(identity, version, editable=True)
            if sequence_id and (not p["script"] or sequence_id not in [s["id"] for s in p["script"]["sequences"]]):
                raise ValueError("Séquence inconnue.")
            if p.get("script"):
                p["history"].append(dict(at=policy.now(), script=deepcopy(p["script"]),
                    episode_id=p["episode_id"], factory_ids=p["factory_ids"], settings=deepcopy(p["settings"]), reason="Réécriture"))
            p.update(feedback=feedback, feedback_sequence=sequence_id, approved=None, review=None,
                     status="queued", error=None, pause_requested=False, factory_entries=[], factory_ids=[],
                     needs_review=False, repair_attempt=0)
            self._reset_scenario(p)
            self._save(p); self._wake.set()
            return p

    def _approve(self, p):
        if not p.get("script"):
            raise ValueError("Écrivez le scénario avant de préparer les références.")
        policy.validate_script(p["script"], p["settings"])
        p["approved"] = policy.digest(p["script"])
        p["episode_id"] = self.production.export(p)
        p.update(status="references_ready", error=None, watch_images=False)
        self._save(p)

    def approve(self, identity, version):
        with self._lock:
            p = self._load(identity, version, editable=True)
            self._approve(p)
            if p["settings"]["mode"] == "automatic":
                p["status"] = "references"; self._save(p)
                self._wake.set()
            return p

    def generate_references(self, identity, version, ids, command):
        with self._lock:
            p = self._load(identity, version, editable=True)
            self._require_approved(p)
            self.production.start_references(p, ids, command)
            if p["factory_ids"]:
                p["history"].append(dict(at=policy.now(), script=deepcopy(p["script"]), settings=deepcopy(p["settings"]),
                    episode_id=p["episode_id"], factory_ids=p["factory_ids"], reason="Références retravaillées"))
            p.update(status="references", error=None, pause_requested=False, watch_images=True, factory_ids=[], factory_entries=[])
            self._save(p); self._wake.set()
            return p

    @staticmethod
    def _require_approved(p):
        if not p.get("script") or p.get("approved") != policy.digest(p["script"]) or not p.get("episode_id"):
            raise ValueError("Validez le scénario courant avant de préparer sa production.")

    def _send(self, p):
        self._require_approved(p)
        if not self.production.references(p):
            raise ValueError("Choisissez une image pour chaque référence avant les vidéos.")
        thumb = self.production.episodes.get(p["episode_id"]).get("story_v2_thumbnail") or {}
        if p["settings"]["images"]["thumbnail"] and not thumb.get("image_asset_id"):
            raise ValueError("La miniature est encore à préparer dans Références.")
        if not p["factory_entries"]:
            p["factory_entries"] = self.production.send(p)
            self._save(p)
        received = self.production.factory.receive(p["factory_entries"])
        p.update(factory_ids=received["ids"], status="prepared", error=None, watch_images=False)
        self._save(p)

    def produce(self, identity, version):
        with self._lock:
            p = self._load(identity, version, editable=True)
            self._send(p)
            self._wake.set()
            return p

    def pause(self, identity):
        with self._lock:
            p = self._load(identity)
            if p["status"] in policy.ACTIVE:
                p["pause_requested"] = True
                self._save(p); self._wake.set()
            return p

    def resume(self, identity, version):
        with self._lock:
            p = self._load(identity, version)
            if p["status"] not in {"paused", "failed"}:
                raise StoryV2Conflict("Ce parcours n'est pas interrompu.")
            stage = p.get("resume_stage", "queued")
            if stage in {"writing", "repairing", "reviewing", "polishing"}: stage = "queued"
            if stage == "references_ready": stage = "references"
            p.update(status=stage, pause_requested=False, error=None)
            if stage == "references": p["retry_references"] = True
            self._save(p); self._wake.set()
            return p

    def start_worker(self):
        with self._lock:
            if self._thread and self._thread.is_alive(): return
            # An interrupted call is never replayed automatically after server restart.
            for p in self.store.list():
                if p["status"] in policy.ACTIVE or (p["status"] == "references_ready" and p.get("watch_images")):
                    for call in p.get("calls", []):
                        if call.get("status") == "running":
                            finished = policy.now()
                            call.update(status="interrupted", accepted=False, finished_at=finished,
                                elapsed_seconds=max(0, (datetime.fromisoformat(finished) - datetime.fromisoformat(call["started_at"])).total_seconds()),
                                error="Appel interrompu par le redémarrage.")
                            if (p.get("progress") or {}).get("id") == call.get("id"):
                                p["progress"].update({k:v for k,v in call.items() if k != "result"})
                    p.update(resume_stage=p["status"], status="paused", pause_requested=False,
                             error="Serveur redémarré : reprenez explicitement le parcours.")
                    self._save(p)
            self._stop.clear()
            self._thread = Thread(target=self._run, daemon=True, name="story-v2")
            self._thread.start()

    def stop_worker(self):
        self._stop.set(); self._wake.set()
        if self._thread: self._thread.join(timeout=2)

    def _run(self):
        while not self._stop.is_set():
            for p in self.store.list():
                if self._stop.is_set(): break
                if p["status"] in policy.ACTIVE or (p["status"] == "references_ready" and p.get("watch_images")):
                    self.tick(p["id"])
            self._wake.wait(2); self._wake.clear()

    def _boundary(self, p, stage):
        if p.get("pause_requested") or self._stop.is_set():
            p.update(resume_stage=stage, status="paused", pause_requested=False)
            self._save(p)
            return False
        p["status"] = stage
        self._save(p)
        return True

    @staticmethod
    def _reset_scenario(p):
        p["scenario"] = dict(id=uuid4().hex, next_step="write", call_start=len(p["calls"]),
                             polish=p["settings"]["polish_enabled"], final_review=p["settings"]["final_review_enabled"])
        p["progress"] = None

    def _scenario(self, p):
        if not p.get("scenario"):
            self._reset_scenario(p)
            previous_write = [i for i,c in enumerate(p["calls"]) if c["role"] == "write"]
            p["scenario"]["call_start"] = previous_write[-1] if previous_write else len(p["calls"])
            p["scenario"]["next_step"] = ("final_review" if p.get("repair_attempt") else "review") if p.get("needs_review") else (
                "repair" if p.get("repair_attempt") else "write")
        p["scenario"].setdefault("final_review", p["settings"]["final_review_enabled"])
        return p["scenario"]

    @staticmethod
    def _snapshot(p, reason):
        p["history"].append(dict(at=policy.now(), script=deepcopy(p["script"]), settings=deepcopy(p["settings"]),
            episode_id=p["episode_id"], factory_ids=deepcopy(p["factory_ids"]), reason=reason))

    def _call(self, identity, role, system, payload, schema, validator):
        with self._lock:
            p = self._load(identity)
            cycle = self._scenario(p)
            step = cycle["next_step"]
            # A restart between accepted response and application must not replay the LLM call.
            prior = next((c for c in reversed(p["calls"]) if c.get("cycle_id") == cycle["id"]
                          and c.get("step") == step and c.get("accepted") and "result" in c), None)
            if prior:
                return deepcopy(prior["result"])
            model = p["settings"]["reader_model" if role == "review" else "polish_model" if role == "polish" else "writer_model"]
            polish, final = int(cycle["polish"]), int(cycle["final_review"])
            remaining = dict(write=2+polish*(1+final), review=1+polish*(1+final),
                             repair=1+polish+final, polish=1+final, final_review=1)[step]
            index = len(p["calls"]) - cycle["call_start"] + 1
            labels = dict(write="Écriture", review="Relecture", repair="Correction ciblée",
                          polish="Retouche des dialogues", final_review="Relecture finale")
            record = dict(id=uuid4().hex, cycle_id=cycle["id"], step=step, role=role, model=model,
                          index=index, total=index+remaining-1, label=labels[step], started_at=policy.now(),
                          status="running", accepted=False, call_id=None, error=None)
            p["calls"].append(record)
            p["progress"] = deepcopy(record)
            self._save(p)
        raw, call_id, accepted, error, value = "", None, False, None, None
        started = time.monotonic()
        try:
            request = CompletionRequest(model_id=model, system_prompt=system,
                user_prompt=json.dumps(payload, ensure_ascii=False), temperature=.25 if role=="review" else .4 if role=="polish" else .55,
                max_tokens=24000, include_reasoning=False, output_schema=schema,
                operation_id=f"story.v2.{role}@{prompts.VERSION}", trace_context=dict(project_id=identity, role=role,
                    scenario_cycle=cycle["id"], scenario_step=step, call_index=index))
            complete = False
            for event in self.gateway.stream(request):
                if event.kind is StreamEventKind.DELTA: raw += event.text
                if event.kind in {StreamEventKind.COMPLETED, StreamEventKind.TRUNCATED}:
                    if event.result: raw, call_id = event.result.content, event.result.call_id
                    if event.kind is StreamEventKind.TRUNCATED:
                        raise ValueError("Réponse tronquée : brouillon conservé, aucune production lancée.")
                    complete = True
                    break
            if not complete: raise ValueError("Écriture interrompue avant une réponse complète.")
            value = validator(json.loads(strip_markdown_fence(raw)))
            accepted = True
            return value
        except Exception as failure:
            error = failure
            raise
        finally:
            with self._lock:
                p = self._load(identity)
                current = next(c for c in p["calls"] if c.get("id") == record["id"])
                current.update(call_id=call_id, at=policy.now(), finished_at=policy.now(),
                    status="succeeded" if accepted else "failed", elapsed_seconds=max(0, time.monotonic()-started),
                    accepted=accepted, error=str(error)[:1500] if error else None)
                if accepted:
                    current["result"] = deepcopy(value)
                p["progress"] = {k:v for k,v in current.items() if k != "result"}
                p["raw"] = raw[:200000]
                self._save(p)
            reporter = getattr(self.gateway, "report_application_outcome", None)
            if reporter and call_id:
                try:
                    reporter(call_id, LlmCallApplicationOutcome.ACCEPTED if accepted else LlmCallApplicationOutcome.REJECTED,
                        error_type=type(error).__name__ if error else None, error_message=str(error) if error else None)
                except Exception:
                    pass

    def _write(self, identity):
        statuses = dict(write="writing", review="reviewing", repair="repairing", polish="polishing", final_review="reviewing")
        while True:
            with self._lock:
                p = self._load(identity)
                cycle = self._scenario(p)
                step = cycle["next_step"]
                if step == "done":
                    p.update(status="awaiting_review", error=None)
                    self._save(p)
                    if p["settings"]["mode"] == "automatic" and not (p.get("review") or {}).get("issues"):
                        if not self._boundary(p, "references"): return
                        self._approve(p)
                        p["status"] = "references"; self._save(p)
                        self.production.start_references(p)
                    elif p.get("pause_requested"):
                        p.update(pause_requested=False); self._save(p)
                    return
                if not self._boundary(p, statuses[step]): return
                settings, script = deepcopy(p["settings"]), deepcopy(p["script"])
                brief = {k:settings[k] for k in ("idea", "universe", "style", "duration", "scene_duration", "language")}
                if step == "polish" and "pre_polish" not in cycle:
                    cycle["pre_polish"] = deepcopy(script)
                    self._snapshot(p, "A · avant retouche")
                    self._save(p)
                before_polish = deepcopy(cycle.get("pre_polish"))
                payload = dict(brief=brief, previous=script, feedback=p["feedback"],
                    sequence=p.get("feedback_sequence"), editorial_issues=(p.get("review") or {}).get("issues", []),
                    scene_durations=policy.scene_durations(settings))
            if step in {"write", "repair"}:
                value = self._call(identity, step, prompts.WRITER, payload, policy.writing_schema(settings),
                                   lambda v:policy.validate_script(v, settings))
            elif step == "polish":
                value = self._call(identity, "polish", prompts.POLISH,
                    dict(brief=brief, screenplay=script, feedback=p["feedback"]), policy.Polish.model_json_schema(),
                    lambda v:policy.validate_polish(v, script, settings))
            else:
                evidence = dict(brief=brief, scenes=policy.audience_view(script))
                if step == "final_review" and before_polish:
                    evidence["pre_polish_scenes"] = policy.audience_view(before_polish)
                value = self._call(identity, "review", prompts.READER, evidence, policy.Review.model_json_schema(),
                                   lambda v:policy.Review.model_validate(v).model_dump())
            with self._lock:
                p = self._load(identity)
                cycle = p["scenario"]
                if step in {"write", "repair"}:
                    p.update(script=value, timing_pending=False, review=None)
                    if step == "write": following = "review"
                    elif cycle["polish"]: following = "polish"
                    else: following = "final_review" if cycle["final_review"] else "done"
                elif step == "review":
                    p["review"] = value
                    if value["issues"]:
                        p["repair_attempt"] = 1
                        following = "repair"
                    else:
                        following = "polish" if cycle["polish"] else "done"
                elif step == "polish":
                    p.update(script=value, review=None)
                    self._snapshot(p, "B · après retouche")
                    following = "final_review" if cycle["final_review"] else "done"
                else:
                    p["review"] = value
                    following = "done"
                cycle["next_step"] = following
                p["needs_review"] = following in {"review", "final_review"}
                self._save(p)


    def tick(self, identity):
        try:
            with self._lock:
                p = self._load(identity)
                stage = p["status"]
                if stage not in policy.ACTIVE and stage != "references_ready": return
                if p.get("pause_requested") or self._stop.is_set():
                    self._boundary(p, stage)
                    return
            if stage == "queued":
                self._write(identity)
            elif stage in {"references", "references_ready"}:
                with self._lock:
                    p = self._load(identity)
                    automatic = p["settings"]["mode"] == "automatic"
                    if not p.get("episode_id") or p.get("approved") != policy.digest(p["script"]):
                        self._approve(p)
                        p["status"] = "references"; self._save(p)
                    episode = self.production.episodes.get(p["episode_id"])
                    batch = episode.get("reference_batch") or {}
                    selection = episode.get("story_v2_selection")
                    if stage == "references_ready" and not selection:
                        return
                    retry_requested = p.get("retry_references", False)
                    if retry_requested and batch.get("status") in {"running", "rendering", "cancelling"}:
                        return  # Submitted image work continues; resuming must not duplicate its batch.
                    if retry_requested and hasattr(self.production, "failed_images"):
                        failed_images = self.production.failed_images(p)
                        episode = self.production.episodes.get(p["episode_id"])
                        batch = episode.get("reference_batch") or {}
                        for ref_id in failed_images:
                            target = next((r for r in episode["references"] if r["id"] == ref_id), None)
                            if target is not None:target.setdefault("story_v2_edit", {})["status"] = "failed"
                            else:episode.setdefault("story_v2_thumbnail", {}).setdefault("story_v2_edit", {})["status"] = "failed"
                    retry = retry_requested and (batch.get("status") in {"failed", "cancelled", "interrupted"}
                        or any(i.get("status") == "failed" for i in batch.get("items", []))
                        or any((r.get("story_v2_edit") or {}).get("status") in {"failed", "cancelled", "interrupted"}
                            for r in [*episode["references"], episode.get("story_v2_thumbnail") or {}]))
                    if retry_requested:
                        p.pop("retry_references", None); self._save(p)
                    if not selection or retry:
                        retry_ids = None
                        if retry and selection:
                            failures = {i["reference_id"] for i in batch.get("items", []) if i.get("status") == "failed"}
                            retry_ids = [r["id"] for r in episode["references"] if r["id"] in selection["ids"]
                                and (not r.get("image_asset_id") or r["id"] in failures
                                    or (r.get("story_v2_edit") or {}).get("status") in {"failed", "cancelled", "interrupted"})]
                        retry_thumbnail = retry and ((episode.get("story_v2_thumbnail") or {}).get("story_v2_edit") or {}).get("status") in {"failed", "cancelled", "interrupted"}
                        self.production.start_references(p, ids=retry_ids, request_id=p["id"]+"-"+uuid4().hex,
                                                         retry_thumbnail=retry_thumbnail, resume=retry)
                        self._save(p)
                    self.production.references(p, automatic)
                    busy = self.production.advance_images(p, automatic)
                    ready = self.production.references(p, automatic)
                    episode = self.production.episodes.get(p["episode_id"])
                    batch = episode.get("reference_batch") or {}
                    if ready and automatic and not busy:
                        self._send(p)
                    else:
                        target = "references" if busy or batch.get("status") in {"running", "rendering", "cancelling"} else "references_ready"
                        selected = set((episode.get("story_v2_selection") or {}).get("ids", []))
                        pending_states = any(r["id"] in selected and r.get("story_v2_state")
                            and (r.get("story_v2_edit") or {}).get("status") != "succeeded" for r in episode["references"])
                        pending_thumb = p["settings"]["images"]["thumbnail"] and not (episode.get("story_v2_thumbnail") or {}).get("image_asset_id")
                        watch = bool(pending_states or pending_thumb)
                        if p["status"] != target or p.get("watch_images") != watch:
                            p.update(status=target, watch_images=watch); self._save(p)
            elif stage == "producing":
                with self._lock:
                    p = self._load(identity)
                    # Legacy in-flight projects are observed, never relaunched from Histoire.
                    rows = self.production.results(p)
                    if len(rows) != len(p["factory_ids"]):
                        raise ValueError("Une vidéo envoyée n'est plus disponible dans l'usine.")
                    if any(r["status"] in {"failed", "cancelled"} for r in rows):
                        raise ValueError("Une vidéo est interrompue ; reprenez-la dans l'usine, puis reprenez ce suivi.")
                    p.update(status="complete" if rows and all(r["status"] == "succeeded" for r in rows) else "prepared", error=None)
                    self._save(p)
        except Exception as failure:
            with self._lock:
                p = self._load(identity)
                p.update(resume_stage=p["status"], status="failed", error=str(failure)[:2500])
                self._save(p)
