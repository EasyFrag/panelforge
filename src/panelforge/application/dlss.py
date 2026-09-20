"""A durable, single-worker post-processing queue shared by image and video workshops."""

from dataclasses import asdict
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from threading import Event, RLock, Thread
import time
import uuid

from panelforge.domain.dlss import DlssSettings
from panelforge.domain.production import ComputeResource, ProductionWorkload

from .production_resources import ResourceWaitCancelled


ACTIVE = {"queued", "starting", "submitting", "running", "receiving", "importing"}


class DlssCancelled(Exception):
    pass


class DlssService:
    def __init__(self, *, jobs, runtime, comfy, assets, media, workflows, candidates, progress=None,
                 video_exporter=None, outputs=None, run_timeout=7200, poll_interval=1,
                 work_coordinator=None):
        self.jobs, self.runtime, self.comfy = jobs, runtime, comfy
        self.assets, self.media, self.workflows, self.candidates = assets, media, workflows, candidates
        self.run_timeout, self.poll_interval = run_timeout, poll_interval
        self.progress, self.video_exporter = progress, video_exporter
        self.outputs = outputs
        self.work_coordinator = work_coordinator
        self._lock = RLock()
        self._worker = None
        self._export_worker = None

    def workflow(self, job):
        key = "video-smooth" if job["snapshot"]["media_type"].startswith("video") and job["settings"]["interpolate"] else (
            "video" if job["snapshot"]["media_type"].startswith("video") else "image")
        workflow = self.workflows[key]
        if job.get("workflow") and job["workflow"] != asdict(workflow.reference):
            raise ValueError("Cette tâche utilise une autre version du workflow DLSS.")
        return workflow

    def preview(self, owner, owner_id, attempt_id, settings):
        snapshot = self.candidates.prepare(owner, owner_id, attempt_id, settings)
        content = self.assets.read_bytes(snapshot["input_asset_id"])
        video = snapshot["media_type"].startswith("video")
        metadata = self.media.probe(content) if video else dict(zip(("width", "height"), self.media.dimensions(content)))
        source_size = self.media.dimensions(self.assets.read_bytes(snapshot["source_asset_id"])) if settings.size == "source" else None
        if source_size and abs((metadata["width"] / metadata["height"]) / (source_size[0] / source_size[1]) - 1) > 0.010000001:
            raise ValueError("Les proportions de la génération et de la source diffèrent de plus de 1 %. Utilise un agrandissement de finition.")
        native, final = self.media.target((metadata["width"], metadata["height"]), settings, video=video, source_size=source_size)
        return {"snapshot": snapshot, "input_metadata": metadata, "native_dimensions": list(native), "output_dimensions": list(final)}

    def queue(self, *, owner, owner_id, attempt_id, settings, request_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", request_id):
            raise ValueError("Identifiant de demande DLSS invalide.")
        request = {"owner": owner, "owner_id": owner_id, "attempt_id": attempt_id, "settings": asdict(settings)}
        job_id = "dlss-" + hashlib.sha256((owner + ":" + owner_id + ":" + request_id).encode()).hexdigest()[:32]
        try:
            existing = self.jobs.get(job_id)
        except FileNotFoundError:
            existing = None
        if existing:
            if existing["request"] != request:
                raise ValueError("Cette demande DLSS correspond déjà à d’autres réglages.")
            self.wake()
            return existing
        # Decode/probe outside the journal lease so another process can persist a finishing job.
        preview = self.preview(owner, owner_id, attempt_id, settings)
        with self._lock, self.jobs.lease("requests"):
            try:
                existing = self.jobs.get(job_id)
            except FileNotFoundError:
                existing = None
            if existing:
                if existing["request"] != request:
                    raise ValueError("Cette demande DLSS correspond déjà à d’autres réglages.")
                result = existing
            else:
                self.candidates.validate_current(preview["snapshot"])
                result = dict(preview, schema_version=1, job_id=job_id, request=request, settings=asdict(settings),
                              created_at=datetime.now(timezone.utc).isoformat(), status="queued", error=None,
                              endpoint=self.comfy.base_url, execution_id=None, output_asset_id=None, candidate_id=None)
                result["workflow"] = asdict(self.workflow(result).reference)
                self.jobs.save(result)
        self.wake()
        return result

    def wake(self):
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = Thread(target=self._drain, name="panelforge-dlss", daemon=True)
                self._worker.start()

    def list(self, owner=None, owner_id=None):
        jobs = self.jobs.list()
        if any(j["status"] in ACTIVE for j in jobs):
            self.wake()
        if any(j.get("video_export", {}).get("status") in {"queued", "copying"} for j in jobs):
            self.wake_exports()
        return [j for j in jobs if (owner is None or j["snapshot"]["owner"] == owner)
                and (owner_id is None or j["snapshot"]["owner_id"] == owner_id)]

    def retry(self, job_id):
        with self._lock, self.jobs.lease("requests"):
            job = self.jobs.get(job_id)
            if job["status"] not in {"failed", "unconfirmed", "cancelled"}:
                return job
            if job.get("execution_id") and not job.get("output_asset_id"):
                # An explicit retry may rerun a proven terminal failure. Unknown/lost replies are reconciled only.
                history = self.comfy.get_history(job["execution_id"])
                record = history.get(job["execution_id"], {})
                if record.get("status", {}).get("status_str") == "error":
                    job.setdefault("previous_execution_ids", []).append(job["execution_id"])
                    job["execution_id"] = None
                    job["cancel_requested"] = False
            job["status"] = "importing" if job.get("report_asset_id") and job.get("output_metadata") and "keyframes" in job else (
                "running" if job.get("execution_id") else "queued")
            job["error"] = None
            job["cancel_requested"] = False
            job["progress"] = None
            job["finished_at"] = None
            self.jobs.save(job)
        self.wake()
        return job

    def cancel(self, job_id):
        with self._lock, self.jobs.lease("requests"):
            job = self.jobs.get(job_id)
            if job["status"] in {"succeeded", "cancelled", "receiving", "importing"}:
                return job
            job["cancel_requested"] = True
            if job["status"] == "queued" and not job.get("execution_id"):
                job["status"] = "cancelled"
                job["finished_at"] = datetime.now(timezone.utc).isoformat()
            elif job["status"] == "failed":
                job["status"] = "running" if job.get("execution_id") else "queued"
            self.jobs.save(job)
        self.wake()
        return job

    def cancel_queued(self, job_id):
        """Cancel only work that has not acquired or submitted to the local machine."""
        with self._lock, self.jobs.lease("requests"):
            job = self.jobs.get(job_id)
            if job["status"] != "queued" or job.get("execution_id"):
                return job
            job["cancel_requested"] = True
            job["status"] = "cancelled"
            job["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.jobs.save(job)
        if self.work_coordinator is not None:
            self.work_coordinator.cancel_queued(f"dlss:{job_id}")
        return job

    def control(self, action):
        with self._lock, self.jobs.lease("worker"), self.jobs.lease("requests"):
            if any(j["status"] in ACTIVE for j in self.jobs.list()):
                raise ValueError("Une tâche DLSS est encore en cours ou en attente.")
            self.runtime.control(action)
        return self.runtime.status()

    def _drain(self):
        try:
            with self.jobs.lease("worker"):
                if self.work_coordinator is None:
                    while True:
                        pending = next((j for j in self.jobs.list() if j["status"] in ACTIVE), None)
                        if pending is None:
                            return
                        self._execute(pending)
                workers = {}
                while True:
                    pending = [j for j in self.jobs.list() if j["status"] in ACTIVE]
                    for job in pending:
                        worker = workers.get(job["job_id"])
                        if worker is not None:
                            continue
                        registered = Event()
                        worker = Thread(
                            target=self._execute,
                            args=(job, registered),
                            name=f"panelforge-{job['job_id']}",
                            daemon=True,
                        )
                        workers[job["job_id"]] = worker
                        worker.start()
                        # Preserve DLSS journal order in the global local FIFO
                        # before announcing the following job.
                        registered.wait(timeout=max(2, self.poll_interval * 2))
                    alive = [worker for worker in workers.values() if worker.is_alive()]
                    if not alive and (not pending or all(job["job_id"] in workers for job in pending)):
                        break
                    for worker in alive:
                        worker.join(timeout=min(0.2, self.poll_interval))
        except BlockingIOError:
            pass  # Another Lab process owns the worker; polling will observe its journal.

    def _save(self, job, **changes):
        with self._lock, self.jobs.lease("requests", wait_timeout=45):
            current = self.jobs.get(job["job_id"])
            current.update(changes)
            job.update(current)
            saved = self.jobs.save(job)
        if self.work_coordinator is not None and changes.get("status"):
            stage = {
                "starting": "Démarrage de Comfy local",
                "submitting": "Envoi du workflow DLSS",
                "running": "Traitement DLSS",
                "receiving": "Récupération du résultat",
                "importing": "Enregistrement du résultat",
                "succeeded": "DLSS terminé",
                "failed": "Échec DLSS",
                "cancelled": "DLSS annulé",
            }.get(changes["status"])
            if stage:
                self.work_coordinator.report_stage(f"dlss:{job['job_id']}", stage)
        return saved

    def _record_progress(self, job_id, execution_id, progress):
        with self._lock, self.jobs.lease("requests", wait_timeout=5):
            current = self.jobs.get(job_id)
            if current.get("execution_id") != execution_id or current["status"] not in {"submitting", "running"}:
                return
            previous = current.get("progress") or {}
            if previous.get("stage_index", -1) > progress["stage_index"]:
                return
            if previous.get("stage") == progress["stage"] and previous.get("percent") is not None:
                progress = dict(progress, percent=max(previous["percent"], progress.get("percent") or 0))
            current["progress"] = dict(progress, updated_at=datetime.now(timezone.utc).isoformat())
            self.jobs.save(current)
        if self.work_coordinator is not None:
            percent = progress.get("percent")
            stage_index = progress.get("stage_index")
            stage_count = progress.get("stage_count")
            normalized = None
            if (
                isinstance(stage_index, int)
                and isinstance(stage_count, int)
                and stage_count > 0
            ):
                stage_progress = 0.0 if percent is None else min(100.0, max(0.0, float(percent))) / 100.0
                normalized = min(1.0, max(0.0, (stage_index + stage_progress) / stage_count))
            self.work_coordinator.report_progress(
                f"dlss:{job_id}",
                normalized,
                progress.get("label") or progress.get("stage") or "Traitement DLSS",
            )

    def _succeeded(self, job, candidate_id):
        changes = dict(status="succeeded", candidate_id=candidate_id, error=None,
                       finished_at=datetime.now(timezone.utc).isoformat())
        if self.video_exporter and job["snapshot"]["media_type"].startswith("video") and not job.get("video_export"):
            day = datetime.now().astimezone().date().isoformat()
            changes["video_export"] = {"status": "queued", "date": day,
                "path": str(self.video_exporter.target(job["job_id"], day)), "error": None}
        self._save(job, **changes)
        if job.get("video_export", {}).get("status") == "queued":
            self.wake_exports()

    def wake_exports(self):
        if not self.video_exporter:
            return
        with self._lock:
            if self._export_worker is None or not self._export_worker.is_alive():
                self._export_worker = Thread(target=self._drain_exports, name="panelforge-dlss-export", daemon=True)
                self._export_worker.start()

    def retry_export(self, job_id):
        if not self.video_exporter:
            raise ValueError("L’export vidéo DLSS n’est pas configuré.")
        with self._lock, self.jobs.lease("requests"):
            job = self.jobs.get(job_id)
            export = job.get("video_export")
            if not export or job["status"] != "succeeded":
                raise ValueError("Aucune vidéo DLSS prête à copier pour cette tâche.")
            if export["status"] == "failed":
                job["video_export"] = dict(export, status="queued", error=None)
                self.jobs.save(job)
        self.wake_exports()
        return job

    def _drain_exports(self):
        try:
            with self.jobs.lease("exports"):
                while True:
                    job = next((j for j in self.jobs.list() if j["status"] == "succeeded"
                        and j.get("video_export", {}).get("status") in {"queued", "copying"}), None)
                    if job is None:
                        return
                    export = dict(job["video_export"], status="copying", error=None)
                    self._save(job, video_export=export)
                    try:
                        self.video_exporter.export(job, self.assets.read_bytes(job["output_asset_id"]),
                                                   self.assets.read_bytes(job["report_asset_id"]))
                    except Exception as error:
                        export = dict(export, status="failed", error=str(error) or type(error).__name__)
                    else:
                        export = dict(export, status="succeeded", finished_at=datetime.now(timezone.utc).isoformat())
                    self._save(job, video_export=export)
        except BlockingIOError:
            pass

    def _execute(self, job, registered=None):
        if self.work_coordinator is not None:
            try:
                with self.work_coordinator.lease(
                    f"dlss:{job['job_id']}",
                    ComputeResource.LOCAL_GPU,
                    ProductionWorkload.DLSS,
                    "DLSS vidéo" if job["snapshot"]["media_type"].startswith("video") else "DLSS image",
                    cancelled=lambda: self.jobs.get(job["job_id"]).get("cancel_requested", False),
                    on_wait=registered.set if registered is not None else None,
                    on_acquired=registered.set if registered is not None else None,
                ):
                    return self._execute_owned(job)
            except ResourceWaitCancelled:
                return None
            finally:
                if registered is not None:
                    registered.set()
        if registered is not None:
            registered.set()
        return self._execute_owned(job)

    def _execute_owned(self, job):
        try:
            if job["endpoint"] != self.comfy.base_url:
                raise ValueError("La tâche appartient à une autre instance Comfy locale. Rétablis son adresse avant de reprendre.")
            workflow = self.workflow(job)
            if job["status"] == "importing":
                candidate_id = self.candidates.attach(job, workflow)
                self._succeeded(job, candidate_id)
                return
            settings = DlssSettings(**job["settings"])
            needs_submit = False
            if not job.get("execution_id"):
                if self.jobs.get(job["job_id"]).get("cancel_requested"):
                    raise DlssCancelled()
                self.candidates.validate_current(job["snapshot"])
                self._save(job, status="starting")
                self.runtime.ensure_ready(workflow.manifest["required_nodes"])
                if self.jobs.get(job["job_id"]).get("cancel_requested"):
                    raise DlssCancelled()
                content = self.assets.read_bytes(job["snapshot"]["input_asset_id"])
                is_video = job["snapshot"]["media_type"].startswith("video")
                if not is_video:
                    content = self.media.png(content)
                uploaded = self.comfy.upload_image(content, filename=job["job_id"] + (".mp4" if is_video else ".png"))
                source_name = (uploaded.subfolder + "/" if uploaded.subfolder else "") + uploaded.filename
                graph = workflow.build(source_name, "dlss/" + job["job_id"], settings)
                if self.jobs.get(job["job_id"]).get("cancel_requested"):
                    raise DlssCancelled()
                # Persist the exact execution ID BEFORE the POST. An ambiguous POST is never replayed automatically.
                execution_id = str(uuid.uuid4())
                self._save(job, status="submitting", execution_id=execution_id, compiled_workflow=graph,
                           progress=None, started_at=datetime.now(timezone.utc).isoformat())
                needs_submit = True
            elif not self.runtime.ready():
                raise ValueError("Comfy local ne répond plus. L’exécution enregistrée ne sera pas relancée automatiquement.")
            execution_id = job["execution_id"]
            watcher = self.progress.watch(execution_id, workflow.manifest.get("progress_stages", []),
                lambda value: self._record_progress(job["job_id"], execution_id, value)) if self.progress else nullcontext()
            with watcher:
                if needs_submit:
                    returned_id = self.comfy.submit_workflow(job["compiled_workflow"], prompt_id=execution_id)
                    if returned_id != execution_id:
                        self._save(job, execution_id=returned_id)
                    self._save(job, status="running")
                record = self._wait(job)
            self._save(job, status="receiving", progress=None)
            output = workflow.output(record)
            self._save(job, comfy_output=output)
            reports = workflow.reports(record)
            content = self.comfy.download_output(filename=output["filename"], subfolder=output.get("subfolder", ""), folder_type="output")
            self._import(job, content, reports, workflow)
        except DlssCancelled:
            self._save(job, status="cancelled", error=None, finished_at=datetime.now(timezone.utc).isoformat())
        except Exception as error:
            self._save(job, status="failed", error=str(error) or type(error).__name__, finished_at=datetime.now(timezone.utc).isoformat())

    def _wait(self, job):
        deadline = time.monotonic() + self.run_timeout
        missing = 0
        cancel_sent = False
        while time.monotonic() < deadline:
            cancelling = self.jobs.get(job["job_id"]).get("cancel_requested", False)
            if cancelling and not cancel_sent:
                self.comfy.cancel_execution(job["execution_id"])
                cancel_sent = True
            history = self.comfy.get_history(job["execution_id"])
            record = history.get(job["execution_id"])
            if record:
                status = record.get("status", {})
                if status.get("status_str") == "error":
                    if cancel_sent:
                        raise DlssCancelled()
                    errors = [data.get("exception_message", str(data)) for kind, data in status.get("messages", []) if kind == "execution_error"]
                    raise RuntimeError("DLSS : " + ("; ".join(errors) or "échec ou interruption du traitement local."))
                if status.get("completed"):
                    return record
            queue = self.comfy.get_queue()
            present = any(p.prompt_id == job["execution_id"] for p in (*queue.running, *queue.pending))
            missing = 0 if present else missing + 1
            if missing >= 4:
                if cancel_sent:
                    raise DlssCancelled()
                raise RuntimeError("Exécution DLSS introuvable dans Comfy local. Reprendre vérifiera le même identifiant sans soumettre un doublon.")
            time.sleep(self.poll_interval)
        raise TimeoutError("Le suivi DLSS a dépassé son délai. Reprendre retrouvera cette même exécution.")

    def _import(self, job, content, reports, workflow):
        snapshot = job["snapshot"]
        video = snapshot["media_type"].startswith("video")
        expected = tuple(job["native_dimensions"])
        if video:
            metadata = self.media.probe(content)
            if (metadata["width"], metadata["height"]) != expected:
                raise ValueError("La vidéo DLSS n’a pas les dimensions attendues.")
            before = job["input_metadata"]
            expected_fps = 60 if job["settings"]["interpolate"] else before["fps"]
            if abs(metadata["fps"] - expected_fps) > 0.05 or abs(metadata["duration_seconds"] - before["duration_seconds"]) > max(0.15, 2 / expected_fps):
                raise ValueError("La vidéo DLSS a changé de durée ou de cadence de manière inattendue.")
            if before["audio"] and not metadata["audio"]:
                raise ValueError("La piste audio manque dans le résultat DLSS.")
            enhanced = content
        else:
            if self.media.dimensions(content) != expected:
                raise ValueError("L’image DLSS n’a pas les dimensions attendues.")
            enhanced = content if tuple(job["output_dimensions"]) == expected else self.media.png(content, job["output_dimensions"])
            content = self.candidates.compose(snapshot, enhanced, self.assets)
            metadata = dict(zip(("width", "height"), self.media.dimensions(content)))
        paths = {}
        if self.outputs:
            source = job.get("comfy_output") if video or tuple(job["output_dimensions"]) == expected else None
            enhanced_asset, enhanced_path = self.outputs.save(job, enhanced, role="enhanced", source=source)
            if content == enhanced:
                output_asset, output_path = enhanced_asset, enhanced_path
            else:
                output_asset, output_path = self.outputs.save(job, content, role="result")
            paths = {"local_output_path": output_path, "enhanced_output_path": enhanced_path}
        else:
            enhanced_asset = self.assets.create(enhanced, media_type=snapshot["media_type"], source_run_id=job["job_id"])
            output_asset = enhanced_asset if content == enhanced else self.assets.create(content, media_type=snapshot["media_type"], source_run_id=job["job_id"])
        self._save(job, output_asset_id=output_asset.asset_id, enhanced_asset_id=enhanced_asset.asset_id, output_metadata=metadata, **paths)
        keyframes = []
        if video:
            last = max(0, math.floor((metadata["duration_seconds"] - 1 / metadata["fps"]) * 1000))
            requested = snapshot.get("keyframe_timestamps_ms", [])
            timestamps = sorted({0, last, *(min(t, last) for t in requested)})
            frames = self.media.frames(content, timestamps)
            for timestamp, frame in zip(timestamps, frames, strict=True):
                asset = self.assets.create(frame, media_type="image/png", source_run_id=job["job_id"])
                keyframes.append({"asset_id": asset.asset_id, "timestamp_ms": timestamp,
                                  "label": "fin · DLSS" if timestamp == last else "début · DLSS" if timestamp == 0 else "DLSS"})
        warnings = []
        if job["settings"]["size"] != "1" and reports and not reports[0].get("nr_upscaling_active", False):
            warnings.append("DLSS a utilisé son mode de repli ; upscale neural non confirmé.")
        report = {"schema_version": 1, "job_id": job["job_id"], "endpoint": job["endpoint"], "execution_id": job["execution_id"],
                  "previous_execution_ids": job.get("previous_execution_ids", []),
                  "workflow": job["workflow"], "settings": job["settings"], "source": snapshot,
                  "input_metadata": job["input_metadata"], "output_metadata": metadata, "reports": reports,
                  "started_at": job.get("started_at"), "finished_at": datetime.now(timezone.utc).isoformat()}
        asset = self.assets.create(json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"), media_type="application/json", source_run_id=job["job_id"])
        self._save(job, status="importing", report_asset_id=asset.asset_id, keyframes=keyframes, warnings=warnings)
        candidate_id = self.candidates.attach(job, workflow)
        self._succeeded(job, candidate_id)
