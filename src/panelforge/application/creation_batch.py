"""Durable, bounded orchestration over the existing assisted creation services."""
from dataclasses import asdict, replace
from datetime import UTC, datetime
import hashlib
import json
import logging
from threading import Event, Lock, RLock, Thread
from typing import Protocol
from uuid import UUID

from panelforge.domain.creation_batch import (
    CreationBatch, CreationBatchConfig, CreationBatchItem, CreationBatchRender, CreationBatchRenderMode,
    CreationIntent, MAX_BATCH_ITEMS, TERMINAL_IMAGE_STATES,
)
from panelforge.domain.krea2_batch import Krea2PromptLanguage
from panelforge.domain.krea2_sampling import Krea2AssistedSettings, sampling_from_dict
from panelforge.domain.video_factory import configuration
from .work_context import llm_owner_prefix

logger = logging.getLogger(__name__)


class CreationBatchStore(Protocol):
    def list(self) -> tuple[CreationBatch, ...]: ...
    def save(self, batch: CreationBatch) -> CreationBatch: ...


class CreationBatchConflict(ValueError):
    pass


class CreationBatchService:
    def __init__(self, store: CreationBatchStore, assisted, *, thumbnails=None, factory=None, render_progress=None):
        self.store, self.assisted = store, assisted
        self.thumbnails = thumbnails
        self.factory = factory
        self.render_progress = render_progress
        self._lock, self._execution = RLock(), Lock()
        self._render_execution, self._factory_lock = Lock(), Lock()
        self._stop, self._wake = Event(), Event()
        self._thread = None
        self._monitor_thread = None
        self._progress = {}
        self._batches = None
        self._worker_errors = {"prompt": None, "render": None}

    @property
    def worker_error(self):
        return next((value for value in self._worker_errors.values() if value), None)

    def _load(self):
        if self._batches is None:
            self._batches = {batch.batch_id: batch for batch in self.store.list()}

    def start_worker(self):
        with self._lock:
            self._load()
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = Thread(target=self._loop, name="creation-batch", daemon=True)
            self._thread.start()
            self._monitor_thread = Thread(target=self._monitor_loop, name="creation-batch-renders", daemon=True)
            self._monitor_thread.start()

    def stop_worker(self):
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        if self.render_progress:
            self.render_progress.stop()

    def create(self, *, request_id, name, intentions, model_id, recipe_version="6.0.0",
               language="en", local_inspiration=False, preset_id, preset_revision, art_style_id=None,
               render_mode=CreationBatchRenderMode.FLUX_KLEIN):
        render_mode = CreationBatchRenderMode(render_mode)
        try:
            batch_id = "creation-batch-" + UUID(request_id).hex
        except (ValueError, TypeError, AttributeError) as error:
            raise ValueError("Identifiant de lancement invalide.") from error
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValueError("Le nom doit contenir entre 1 et 120 caractères.")
        if not 1 <= len(intentions) <= MAX_BATCH_ITEMS:
            raise ValueError(f"Le batch doit contenir de 1 à {MAX_BATCH_ITEMS} intentions.")
        intents = tuple(CreationIntent(**value) for value in intentions)
        request = dict(name=name.strip(), intentions=[asdict(item) for item in intents], model_id=model_id,
                       recipe_version=recipe_version, language=language, local_inspiration=local_inspiration,
                       preset_id=preset_id, preset_revision=preset_revision, art_style_id=art_style_id)
        # Keep the historical request digest for omitted/default Flux mode, so a
        # retry issued by an older client still adopts its original frozen batch.
        if render_mode is not CreationBatchRenderMode.FLUX_KLEIN:
            request["render_mode"] = render_mode.value
        digest = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with self._lock:
            self._load()
            previous = self._batches.get(batch_id)
            if previous:
                if previous.request_digest != digest:
                    raise CreationBatchConflict("Ce lancement existe avec d'autres paramètres.")
                return previous
        # Catalog calls are outside the state lock; polling remains cheap.
        if recipe_version not in {r["version"] for r in self.assisted.list_assistance_recipes()}:
            raise ValueError("Recette d'assistance inconnue.")
        if model_id not in {model.model_id for model in self.assisted.list_models()}:
            raise ValueError("Le modèle LLM sélectionné n'est plus disponible.")
        preset, settings = self.assisted.snapshot_batch_preset(preset_id, preset_revision, render_mode=render_mode)
        if art_style_id and self.assisted.style_catalog is None:
            raise ValueError("Catalogue de directions artistiques indisponible.")
        art = self.assisted.style_catalog.get(art_style_id) if art_style_id else None
        config = CreationBatchConfig(model_id, recipe_version, Krea2PromptLanguage(language),
                                     local_inspiration, preset, settings, art)
        batch = CreationBatch(batch_id, digest, name.strip(), datetime.now(UTC).isoformat(), config,
                              tuple(CreationBatchItem(str(i + 1), item.name, item.intention)
                                    for i, item in enumerate(intents)))
        with self._lock:
            previous = self._batches.get(batch_id)
            if previous:
                if previous.request_digest != digest:
                    raise CreationBatchConflict("Ce lancement existe avec d'autres paramètres.")
                return previous
            self.store.save(batch)
            self._batches[batch_id] = batch
        self._wake.set()
        return batch

    def get(self, batch_id):
        with self._lock:
            self._load()
            if batch_id not in self._batches:
                raise FileNotFoundError(batch_id)
            return self._batches[batch_id]

    def latest(self):
        with self._lock:
            self._load()
            return max(self._batches.values(), key=lambda b: b.created_at, default=None)

    def _item(self, batch_id, item_id):
        batch = self.get(batch_id)
        for index, item in enumerate(batch.items):
            if item.item_id == item_id:
                return batch, index, item
        raise FileNotFoundError(item_id)

    @staticmethod
    def _render(item, render_id):
        if render_id == "initial":
            return item
        for render in item.renders:
            if render.render_id == render_id:
                return render
        raise FileNotFoundError(render_id)

    def thumbnail(self, batch_id, item_id, render_id="initial", *, large=False):
        _, _, item = self._item(batch_id, item_id)
        render = self._render(item, render_id)
        if not render.output_asset_id or self.thumbnails is None:
            raise FileNotFoundError(item_id)
        return self.thumbnails(render.output_asset_id, size=840) if large else self.thumbnails(render.output_asset_id)

    def _save(self, batch):
        self.store.save(batch)
        self._batches[batch.batch_id] = batch
        return batch

    @staticmethod
    def _command(request_id, values):
        identity = UUID(str(request_id)).hex
        digest = hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return identity, digest

    def _previous_command(self, batch, identity, digest):
        for item in batch.items:
            records = [(item.request_id, item.request_digest)] + [(r.render_id, r.request_digest) for r in item.renders]
            for previous_id, previous_digest in records:
                if previous_id == identity:
                    if previous_digest != digest:
                        raise CreationBatchConflict("Cette action existe avec d’autres paramètres.")
                    return True
        return False

    def add_variant(self, batch_id, item_id, *, request_id, source_render_id="initial", kind,
                    preset_id=None, preset_revision=None, art_style_id=None):
        if kind not in {"render", "art", "preset"}:
            raise ValueError("Type de variante inconnu.")
        if kind == "preset" and (not preset_id or not preset_revision):
            raise ValueError("Choisis un preset créatif.")
        if kind == "art" and not art_style_id:
            raise ValueError("Choisis une direction artistique.")
        identity, digest = self._command(request_id, dict(item_id=item_id, source_render_id=source_render_id,
            kind=kind, preset_id=preset_id, preset_revision=preset_revision, art_style_id=art_style_id))
        with self._lock:
            batch, index, item = self._item(batch_id, item_id)
            if self._previous_command(batch, identity, digest):
                return batch
            source = self._render(item, source_render_id)
            if not source.output_asset_id or not source.project_id or not source.attempt_id:
                raise ValueError("Choisis une image terminée.")
        # Freeze the actual source attempt; later catalogue/project edits cannot change this action.
        attempt = self.assisted.projects.get(source.project_id).attempt(source.attempt_id)
        config = source.config if isinstance(source, CreationBatchRender) else item.config or batch.config
        config = replace(config, settings=attempt.settings, art_direction=attempt.art_direction,
                         preset=attempt.style_preset or config.preset,
                         language=attempt.conversation_prompt_language or config.language)
        prompt = attempt.canonical_prompt or attempt.prompt
        if kind == "render":
            settings = config.settings
            sampling = sampling_from_dict(None, default_preset_id="finish_4")
            settings = replace(settings, sampling=sampling) if isinstance(settings, Krea2AssistedSettings) else Krea2AssistedSettings(
                settings.model_name, settings.aspect_ratio, settings.megapixels, settings.loras, sampling=sampling)
            config = replace(config, settings=settings)
            render = CreationBatchRender(identity, "Finition 4 steps · 8 + 4", config, prompt, digest)
        elif kind == "art":
            if self.assisted.style_catalog is None:
                raise ValueError("Catalogue artistique indisponible.")
            config = replace(config, recipe_version="6.0.0", art_direction=self.assisted.style_catalog.get(art_style_id))
            label = config.art_direction.display_name
        else:
            preset, settings = self.assisted.snapshot_batch_preset(
                preset_id, preset_revision, render_mode=config.render_mode)
            config = replace(config, preset=preset, settings=settings, art_direction=preset.art_direction,
                             recipe_version="6.0.0", language=preset.prompt_language)
            label = preset.name
        with self._lock:
            batch, index, item = self._item(batch_id, item_id)
            if self._previous_command(batch, identity, digest):
                return batch
            if kind == "render":
                if len(item.renders) >= 50:
                    raise ValueError("Une ligne accepte au maximum 50 variantes de rendu.")
                self._update(batch_id, index, renders=(*item.renders, render))
            else:
                if len(batch.items) >= MAX_BATCH_ITEMS * 4:
                    raise ValueError("Ce batch a atteint sa limite de variantes.")
                parent = item.parent_id or item.item_id
                number = 1 + sum(i.parent_id == parent for i in batch.items)
                child = CreationBatchItem(f"{parent}.{number}", f"{item.name} · {label}"[:120], item.intention,
                    parent_id=parent, config=config, source_prompt=prompt if kind == "art" else None,
                    prompt_status="succeeded" if kind == "art" else "queued", request_id=identity, request_digest=digest)
                self._save(replace(batch, items=(*batch.items, child), revision=batch.revision + 1))
        self._wake.set()
        return self.get(batch_id)

    def send_to_factory(self, batch_id, item_id, render_id):
        self._send_factory_image(batch_id, item_id, render_id)
        return self.get(batch_id)

    def send_all_to_factory(self, batch_id):
        """Send the currently available originals and variants, retaining per-image receipts."""
        batch = self.get(batch_id)
        if self.factory is None:
            raise ValueError("L’Usine n’est pas configurée.")
        candidates = []
        report = dict(sent=0, already_sent=0, failed=0, errors=[])
        for item in batch.items:
            for render_id, render in [("initial", item), *((r.render_id, r) for r in item.renders)]:
                status = render.status if isinstance(render, CreationBatchRender) else render.image_status
                if status != "succeeded" or not render.output_asset_id:
                    continue
                if render.factory_item_id:
                    report["already_sent"] += 1
                else:
                    candidates.append((item.item_id, render_id))
        # Take a fixed snapshot: images completing during delivery belong to the
        # next click. The shared per-image lock also protects concurrent bulk and
        # individual requests, without holding the batch state lock over I/O.
        for item_id, render_id in candidates:
            try:
                sent = self._send_factory_image(batch_id, item_id, render_id)
                report["sent" if sent else "already_sent"] += 1
            except Exception as error:
                logger.exception("Batch factory delivery failed for %s/%s/%s", batch_id, item_id, render_id)
                report["failed"] += 1
                report["errors"].append(dict(item_id=item_id, render_id=render_id, message=str(error)[:500]))
        return self.get(batch_id), report

    def _send_factory_image(self, batch_id, item_id, render_id):
        if self.factory is None:
            raise ValueError("L’Usine n’est pas configurée.")
        with self._factory_lock:
            _, index, item = self._item(batch_id, item_id)
            render = self._render(item, render_id)
            if render.factory_item_id:
                return False
            if not render.output_asset_id:
                raise ValueError("L’image n’est pas encore disponible.")
            config = configuration()
            config["references"] = [dict(asset_id=render.output_asset_id, role="unassigned", label=item.name)]
            receipt = self.factory.receive([dict(name=item.name, config=config, source=dict(kind="image",
                id=f"{batch_id}/{item_id}/{render_id}", view="creation-batch"))], compact=True)
            factory_id = receipt["ids"][0]
            # A lost batch receipt is safe to retry: the factory deduplicates the immutable source/config.
            self._update_render(batch_id, index, render_id, factory_item_id=factory_id)
            return True

    def _update_render(self, batch_id, index, render_id, **changes):
        with self._lock:
            if render_id == "initial":
                if "status" in changes:
                    changes["image_status"] = changes.pop("status")
                return self._update(batch_id, index, **changes)
            item = self._batches[batch_id].items[index]
            renders = tuple(replace(r, **changes) if r.render_id == render_id else r for r in item.renders)
            return self._update(batch_id, index, renders=renders)

    def _update(self, batch_id, index, **changes):
        with self._lock:
            batch = self._batches[batch_id]
            item = replace(batch.items[index], **changes)
            if item == batch.items[index]:
                return item
            items = list(batch.items)
            items[index] = item
            saved = replace(batch, items=tuple(items), revision=batch.revision + 1)
            self.store.save(saved)  # Publish only after durable save.
            self._batches[batch_id] = saved
            return item

    def _loop(self):
        while not self._stop.is_set():
            self._wake.clear()
            try:
                immediate = self.process_next()
                self._worker_errors["prompt"] = None
            except Exception as error:
                logger.exception("Creation batch worker failed")
                self._worker_errors["prompt"] = str(error)[:1000]
                immediate = False
            if not immediate:
                self._wake.wait(2)

    def _monitor_loop(self):
        while not self._stop.is_set():
            try:
                self.process_renders()
                self._worker_errors["render"] = None
            except Exception as error:
                logger.exception("Creation batch render tracking failed")
                self._worker_errors["render"] = str(error)[:1000]
            self._stop.wait(1)

    def process_next(self):
        """Prepare the next prompt without waiting for any preceding image."""
        if not self._execution.acquire(blocking=False):
            return False
        try:
            changed = self.process_renders()
            with self._lock:
                self._load()
                active = sorted((b for b in self._batches.values() if not b.terminal), key=lambda b: b.created_at)
                pending = next(((b, n) for b in active for n, i in enumerate(b.items)
                                if i.prompt_status in {"queued", "running"} and not i.source_prompt
                                and i.image_status not in TERMINAL_IMAGE_STATES), None)
            if pending is None or self._stop.is_set():
                return changed
            batch, index = pending
            result = self._advance(batch, index)
            with self._lock:
                more = any(i.prompt_status == "queued" for b in self._batches.values() for i in b.items)
            return result or more or changed
        finally:
            self._execution.release()

    def _advance(self, batch, index):
        item = batch.items[index]
        config = item.config or batch.config
        try:
            project = self.assisted.create_batch_project(
                config=config, name=item.name, intention=item.intention,
                managed_key=f"{batch.batch_id}/{item.item_id}",
            ) if item.project_id is None else self.assisted.projects.get(item.project_id)
            item = self._update(batch.batch_id, index, project_id=project.project_id)
            if not project.current_prompt:
                if item.prompt_status == "running":
                    # A previous process may have called the LLM: never replay an ambiguous call.
                    raise ValueError("Préparation interrompue avant sauvegarde du prompt. Cette intention n'a pas été relancée.")
                item = self._update(batch.batch_id, index, prompt_status="running", message="Préparation du prompt")
                token = llm_owner_prefix.set(f"batch-llm:{batch.batch_id}:{item.item_id}")
                try:
                    for event in self.assisted.stream_chat(project.project_id, item.intention,
                                                           prompt_language=config.language):
                        if event.error:
                            raise ValueError(event.error)
                        kind = getattr(event.kind, "value", event.kind)
                        if kind == "status":
                            phase = getattr(getattr(event, "phase", None), "value", "preparing")
                            with self._lock:
                                self._progress[(batch.batch_id, item.item_id)] = dict(
                                    phase=phase, message=event.text[:280], progress=getattr(event, "progress", None))
                        if self._stop.is_set():
                            return False
                finally:
                    llm_owner_prefix.reset(token)
                project = self.assisted.projects.get(project.project_id)
                if not project.current_prompt:
                    raise ValueError("Le LLM n'a pas fourni de prompt exploitable.")
            if item.prompt_status != "succeeded":
                self._update(batch.batch_id, index, prompt_status="succeeded", message="")
            if self._stop.is_set():
                return False
            self.process_renders()
            return self.get(batch.batch_id).items[index].image_status in TERMINAL_IMAGE_STATES
        except OSError:
            # Persistence problems must not turn into a fresh generation or a misleading failure receipt.
            raise
        except Exception as error:
            current = self.get(batch.batch_id).items[index]
            self._update(batch.batch_id, index, image_status="failed",
                         prompt_status="failed" if current.prompt_status != "succeeded" else "succeeded",
                         error=str(error)[:1500], message="")
            return True

    def process_renders(self):
        """Prepare and follow render tasks independently of a blocking LLM call."""
        if not self._render_execution.acquire(blocking=False):
            return False
        try:
            with self._lock:
                self._load()
                batches = sorted(self._batches.values(), key=lambda b: b.created_at)
            coordinator = getattr(self.assisted, "work_coordinator", None)
            activities = coordinator.activity_statuses() if coordinator is not None else {}
            changed = False
            for batch in batches:
                if batch.terminal or self._stop.is_set():
                    continue
                for index, item in enumerate(batch.items):
                    if self._stop.is_set():
                        return changed
                    if item.prompt_status == "succeeded" and item.image_status not in TERMINAL_IMAGE_STATES:
                        changed = self._advance_render(batch, index, "initial", activities) or changed
                    for render in item.renders:
                        if not render.terminal:
                            changed = self._advance_render(batch, index, render.render_id, activities) or changed
            return changed
        finally:
            self._render_execution.release()

    def _advance_render(self, batch, index, render_id, activities=None):
        item = self.get(batch.batch_id).items[index]
        render = self._render(item, render_id)
        status = render.status if isinstance(render, CreationBatchRender) else item.image_status
        activity = (activities or {}).get(f"krea2:{render.project_id}:{render.attempt_id}", {})
        if status == "queued" and activity.get("position", 0) > 0:
            return False  # Queue position lives in memory; do not reread all queued project files.
        config = render.config if isinstance(render, CreationBatchRender) else item.config or batch.config
        prompt = render.prompt if isinstance(render, CreationBatchRender) else item.source_prompt
        try:
            project = self.assisted.projects.get(render.project_id) if render.project_id else self.assisted.create_batch_project(
                config=config, name=item.name, intention=item.intention,
                managed_key=f"{batch.batch_id}/{item.item_id}" + (f"/{render_id}" if render_id != "initial" else ""))
            self._update_render(batch.batch_id, index, render_id, project_id=project.project_id)
            if not project.attempts:
                project = self.assisted.prepare_attempt(project.project_id, prompt=prompt or project.current_prompt,
                    settings=config.settings, expected_branch_id=project.active_branch_id, prompt_language=config.language)
            # Each render has its own managed project: a crash can safely adopt its only attempt.
            attempt = project.attempt(render.attempt_id) if render.attempt_id else project.attempts[0]
            self._update_render(batch.batch_id, index, render_id, attempt_id=attempt.attempt_id)
            if self.render_progress:
                try:
                    self.render_progress.watch(project.project_id, attempt)
                except Exception:
                    logger.debug("Batch progress unavailable", exc_info=True)
            if attempt.status.value == "created" and not self._stop.is_set():
                project = self.assisted.queue_attempt(project.project_id, attempt.attempt_id)
                attempt = project.attempt(attempt.attempt_id)
            previous = render.status if isinstance(render, CreationBatchRender) else render.image_status
            self._update_render(batch.batch_id, index, render_id, status=attempt.status.value,
                                error=attempt.error, output_asset_id=attempt.output_asset_id)
            return previous != attempt.status.value and attempt.status.value in TERMINAL_IMAGE_STATES
        except OSError:
            raise
        except Exception as error:
            self._update_render(batch.batch_id, index, render_id, status="failed", error=str(error)[:1500])
            if self.render_progress:
                current = self._render(self.get(batch.batch_id).items[index], render_id)
                self.render_progress.forget(current.project_id, current.attempt_id)
            return True

    def monitoring(self, batch):
        coordinator = getattr(self.assisted, "work_coordinator", None)
        activities = coordinator.activity_statuses() if coordinator is not None else {}
        with self._lock:
            live = dict(self._progress)

        def stage(status, activity=None, progress=None, message=""):
            value = dict(status=status, progress=progress, position=None, message=message)
            if status == "succeeded":
                return {**value, "progress": 1.0}
            if status in TERMINAL_IMAGE_STATES:
                return {**value, "progress": None}
            if activity:
                position = activity.get("position")
                waiting = bool(position) or activity.get("status") == "queued"
                value.update(status="queued" if waiting else "running" if activity.get("status") == "running" else "starting",
                             position=position if waiting else None,
                             progress=0.0 if waiting else activity.get("progress"), message=activity.get("stage", ""))
            return value

        values = {}
        for item in batch.items:
            prefix = f"batch-llm:{batch.batch_id}:{item.item_id}-"
            activity = next((a for key, a in activities.items() if key.startswith(prefix)), None)
            prompt = live.get((batch.batch_id, item.item_id), {})
            status = item.prompt_status
            if status == "running" and not activity:
                status = "queued" if prompt.get("phase") == "queued" else "starting"
            elif status == "queued":
                status = "waiting"
            images = {}
            for identity, render, image_status in [("initial", item, item.image_status),
                                                   *((r.render_id, r, r.status) for r in item.renders)]:
                activity_id = f"krea2:{render.project_id}:{render.attempt_id}"
                images[identity] = stage(image_status, activities.get(activity_id))
            values[item.item_id] = dict(prompt=stage(status, activity, prompt.get("progress"), prompt.get("message", "")), images=images)
        return values
