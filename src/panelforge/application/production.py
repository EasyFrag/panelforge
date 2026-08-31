"""Application service for restart-safe automated image and video production."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
import json
import re
from threading import Condition, RLock, Thread
import time
from typing import Any, Protocol
from uuid import uuid4

from panelforge.domain.h3_render import H3RenderAttemptStatus, H3RenderInputMode
from panelforge.domain.krea2_assisted import Krea2AssistedAttemptStatus
from panelforge.domain.krea2_batch import Krea2LoraSelection
from panelforge.domain.production import (
    ComputeResource,
    ComputeResourceState,
    ComputeResourceStatus,
    ProductionCandidateAssessment,
    ProductionConfig,
    ProductionDecision,
    ProductionDecisionKind,
    ProductionDecisionOutcome,
    ProductionEvent,
    ProductionEventLevel,
    ProductionJob,
    ProductionLoraChoice,
    ProductionLoraChoiceSource,
    ProductionLoraPlan,
    ProductionMode,
    ProductionStage,
    ProductionStatus,
    ProductionWorkload,
    ThermalSnapshot,
)
from panelforge.domain.prompt_composition import CookbookBinding, CompositionStage
from panelforge.domain.prompt_lab import ReferenceEvidencePolicy, ReferenceUse
from panelforge.domain.video_lab import VideoAspectRatio, VideoLabSettings
from panelforge.application.prompt_lab import (
    CompletionRequest,
    ImageInput,
    NewReference,
    truncated_response_message,
)
from panelforge.application.production_resources import (
    ResourceLeaseManager,
    ResourceRequirement,
    ResourceWaitCancelled,
    llm_compute_resource,
)


_H3_PROFILE_ID = "minimax.h3.fl2va.direct"
_H3_VERSION = "0.3.3"
_H3_CREATIVE_BRIEF_ID = "creative-direction"
_H3_CREATIVE_BRIEF_VERSION = "0.2.0"
_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _resource_operation_label(
    stage: ProductionStage,
    workload: ProductionWorkload,
) -> str:
    """Expose a stable coarse phase instead of internal attempt identifiers."""
    if workload is ProductionWorkload.IMAGE_RENDER:
        return "KREA2"
    if workload in {ProductionWorkload.VIDEO_RENDER, ProductionWorkload.VIDEO_COOLDOWN}:
        return "H3_high" if stage is ProductionStage.VIDEO_FINAL else "H3_low"
    if stage in {ProductionStage.SETUP, ProductionStage.IMAGE_GENERATION, ProductionStage.IMAGE_SELECTION}:
        return "KREA2"
    if stage is ProductionStage.H3_PROMPT:
        return "H3_plan"
    if stage in {ProductionStage.VIDEO_PREVIEW, ProductionStage.VIDEO_EVALUATION}:
        return "H3_low"
    if stage is ProductionStage.VIDEO_FINAL:
        return "H3_high"
    return "LLM"


class ProductionJobStore(Protocol):
    def create(self, job: ProductionJob) -> ProductionJob: ...
    def save(self, job: ProductionJob) -> ProductionJob: ...
    def get(self, job_id: str) -> ProductionJob: ...
    def list(self, limit: int = 30) -> list[ProductionJob]: ...


class ProductionAssetStore(Protocol):
    def get(self, asset_id: str) -> Any: ...
    def read_bytes(self, asset_id: str) -> bytes: ...


class ProductionThermalMonitor(Protocol):
    def snapshot(self) -> ThermalSnapshot: ...


class ProductionLoraMemory(Protocol):
    def context(self, names, *, observations_per_lora: int = 3): ...
    def record_plan(self, *, job_id: str, checkpoint: str, plan: ProductionLoraPlan, timestamp: str | None = None): ...
    def record_observation(self, **values): ...


class _Cancelled(RuntimeError):
    pass


class _ThermalAbort(RuntimeError):
    pass


class ProductionService:
    """Drive one bounded job while retaining every child project and decision."""

    def __init__(
        self,
        *,
        gateway: Any,
        assets: ProductionAssetStore,
        jobs: ProductionJobStore,
        krea2: Any,
        prompt_lab: Any,
        composition: Any,
        h3_render: Any,
        thermal_monitor: ProductionThermalMonitor,
        lora_resources: Any | None = None,
        lora_memory: ProductionLoraMemory | None = None,
        job_id_factory: Callable[[], str] | None = None,
        event_id_factory: Callable[[], str] | None = None,
        decision_id_factory: Callable[[], str] | None = None,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        monitor_interval: float = 2.0,
        resource_leases: ResourceLeaseManager | None = None,
        server_llm_resource: ComputeResource = ComputeResource.REMOTE_GPU,
        max_active_jobs: int = 2,
    ) -> None:
        if monitor_interval <= 0:
            raise ValueError("monitor_interval must be positive")
        if not isinstance(server_llm_resource, ComputeResource):
            raise TypeError("server_llm_resource must be a ComputeResource")
        if isinstance(max_active_jobs, bool) or not isinstance(max_active_jobs, int) or not 1 <= max_active_jobs <= 16:
            raise ValueError("max_active_jobs must be between 1 and 16")
        self.gateway = gateway
        self.assets = assets
        self.jobs = jobs
        self.krea2 = krea2
        self.prompt_lab = prompt_lab
        self.composition = composition
        self.h3_render = h3_render
        self.thermal_monitor = thermal_monitor
        self.lora_resources = lora_resources
        self.lora_memory = lora_memory
        self._job_id = job_id_factory or (lambda: f"production-{uuid4().hex}")
        self._event_id = event_id_factory or (lambda: f"event-{uuid4().hex}")
        self._decision_id = decision_id_factory or (lambda: f"decision-{uuid4().hex}")
        self._now = now or (lambda: datetime.now(UTC))
        self._monotonic = monotonic
        self._sleep = sleep
        self.monitor_interval = monitor_interval
        self.resource_leases = resource_leases or ResourceLeaseManager(
            wait_interval=min(monitor_interval, 0.2),
        )
        self.server_llm_resource = server_llm_resource
        self.max_active_jobs = max_active_jobs
        self._lock = RLock()
        self._slot_condition = Condition(self._lock)
        self._claimed: set[str] = set()
        self._claim_waiters: list[str] = []

    def create_job(
        self,
        *,
        name: str,
        intention: str,
        source_asset_id: str,
        source_filename: str,
        config: ProductionConfig,
    ) -> ProductionJob:
        if not isinstance(config, ProductionConfig):
            raise TypeError("config must be a ProductionConfig")
        for lora in config.image_settings.loras:
            _bounded_number(
                lora.strength,
                f"Production LoRA strength for {lora.name}",
                -1.0,
                1.0,
            )
        asset = self.assets.get(source_asset_id)
        if not asset.media_type.startswith("image/"):
            raise ValueError("the immutable production source must be an image")
        job = ProductionJob(
            job_id=self._job_id(),
            name=name.strip(),
            intention=intention.strip(),
            source_asset_id=source_asset_id,
            source_filename=source_filename.strip(),
            config=config,
        )
        job = self._event(job, "Projet cree; l'image source restera immuable.")
        return self.jobs.create(job)

    def get(self, job_id: str) -> ProductionJob:
        return self.jobs.get(job_id)

    def list(self, limit: int = 30) -> list[ProductionJob]:
        return self.jobs.list(limit)

    def h3_audit(self, job_id: str) -> dict[str, Any]:
        """Return durable H3 documents and the exact render input contract."""

        job = self.jobs.get(job_id)
        selected_index = None
        if job.krea_project_id is not None and job.selected_image_attempt_id is not None:
            try:
                selected_index = self.krea2.get(job.krea_project_id).attempt(
                    job.selected_image_attempt_id
                ).index
            except (KeyError, FileNotFoundError, ValueError):
                pass

        project = None
        if job.h3_project_id is not None:
            try:
                project = self.h3_render.get(job.h3_project_id)
            except (KeyError, FileNotFoundError, ValueError):
                pass

        session = None
        if job.prompt_session_id is not None:
            try:
                session = self.prompt_lab.get_session(job.prompt_session_id)
            except (KeyError, FileNotFoundError, ValueError):
                pass

        documents: dict[str, dict[str, Any]] = {
            "brief": {"status": "missing", "revision_id": None, "content": None},
            "beat_sheet": {"status": "missing", "revision_id": None, "content": None},
            "final_prompt": {"status": "missing", "revision_id": None, "content": None},
        }
        if session is not None and session.active_brief_revision is not None:
            documents["brief"] = {
                "status": "approved" if session.brief_complete else "draft",
                "revision_id": getattr(session.active_brief_revision, "revision_id", None),
                "content": session.active_brief_revision.content,
            }
        if job.prompt_session_id is not None:
            try:
                composition = self.composition.get(job.prompt_session_id)
            except (KeyError, FileNotFoundError, ValueError):
                composition = None
            if composition is not None:
                for key, stage in (
                    ("beat_sheet", CompositionStage.BEAT_SHEET),
                    ("final_prompt", CompositionStage.FINAL_PROMPT),
                ):
                    document = composition.document(stage)
                    revision = document.active_revision
                    if revision is not None:
                        documents[key] = {
                            "status": (
                                "approved"
                                if document.approved_revision_id == document.active_revision_id
                                else "draft"
                            ),
                            "revision_id": document.active_revision_id,
                            "content": revision.content,
                        }

        input_mode = (
            project.input_mode.value
            if project is not None
            else H3RenderInputMode.I2VA.value
        )
        first_frame_asset_id = (
            project.first_frame_asset_id
            if project is not None
            else job.selected_image_asset_id
        )
        last_frame_asset_id = project.last_frame_asset_id if project is not None else None
        return {
            "profile": {"id": _H3_PROFILE_ID, "version": _H3_VERSION},
            "brief_variant": (
                {
                    "id": getattr(session, "brief_variant_id", None),
                    "version": getattr(session, "brief_variant_version", None),
                }
                if session is not None
                and getattr(session, "brief_variant_id", None) is not None
                else None
            ),
            "brief_audacity": getattr(
                getattr(session, "active_brief_revision", None),
                "creative_audacity",
                job.config.creative_audacity,
            ),
            "input": {
                "mode": input_mode,
                "first_frame": (
                    {
                        "asset_id": first_frame_asset_id,
                        "attempt_id": job.selected_image_attempt_id,
                        "attempt_index": selected_index,
                        "url": f"/api/assets/{first_frame_asset_id}/content",
                    }
                    if first_frame_asset_id is not None else None
                ),
                "last_frame": (
                    {
                        "asset_id": last_frame_asset_id,
                        "url": f"/api/assets/{last_frame_asset_id}/content",
                    }
                    if last_frame_asset_id is not None else None
                ),
                "aspect_ratio": job.config.image_settings.aspect_ratio.value,
                "duration_seconds": job.config.duration_seconds,
                "steps": job.config.video_steps,
                "preview_megapixels": job.config.preview_megapixels,
                "final_megapixels": job.config.final_megapixels,
                "seed": str(job.video_seed) if job.video_seed is not None else None,
                "seed_locked": job.video_seed is not None,
                "music_enabled": job.config.music_enabled,
                "h3_video_lora": (
                    {
                        "name": job.config.h3_video_lora.name,
                        "strength": job.config.h3_video_lora.strength,
                        "clip_last_layer": job.config.h3_video_lora.clip_last_layer,
                        "overlay_version": job.config.h3_video_lora.overlay_version,
                    }
                    if job.config.h3_video_lora is not None
                    else None
                ),
            },
            "documents": documents,
            "current_prompt": project.current_prompt if project is not None else None,
        }

    def thermal_snapshot(self) -> ThermalSnapshot:
        return self.thermal_monitor.snapshot()

    def resource_statuses(self) -> tuple[ComputeResourceStatus, ...]:
        snapshot = self.thermal_monitor.snapshot()
        owners = self.resource_leases.owners()
        values: list[ComputeResourceStatus] = []
        for resource in ComputeResource:
            temperature = self._resource_temperature(snapshot, resource)
            error = self._resource_error(snapshot, resource)
            owner = owners.get(resource)
            threshold = 85.0
            if owner is not None:
                try:
                    threshold = self.jobs.get(owner.job_id).config.thermal.stop_temperature_c
                except (KeyError, FileNotFoundError):
                    pass
            if temperature is None:
                state = ComputeResourceState.UNAVAILABLE
            elif temperature >= threshold:
                state = ComputeResourceState.HOT
            elif owner is not None and owner.requirement.workload is ProductionWorkload.VIDEO_COOLDOWN:
                state = ComputeResourceState.COOLING
            elif owner is not None:
                state = ComputeResourceState.BUSY
            else:
                state = ComputeResourceState.IDLE
            values.append(ComputeResourceStatus(
                resource=resource,
                state=state,
                temperature_c=temperature,
                owner_job_id=owner.job_id if owner is not None else None,
                operation=owner.requirement.operation if owner is not None else None,
                error=error,
            ))
        return tuple(values)

    def queue(self, job_id: str) -> ProductionJob:
        with self._lock:
            job = self.jobs.get(job_id)
            if job.status not in {
                ProductionStatus.DRAFT,
                ProductionStatus.WAITING_FOR_REVIEW,
                ProductionStatus.PAUSED_THERMAL,
            }:
                raise ValueError("this production job cannot be queued")
            job = self.jobs.save(replace(
                job,
                status=ProductionStatus.QUEUED,
                pause_reason=None,
                error=None,
                cancel_requested=False,
            ))
            Thread(target=self.run, args=(job_id,), daemon=True).start()
            return job

    def retry_failed(self, job_id: str) -> ProductionJob:
        """Resume the current durable stage without replaying valid predecessors."""

        with self._lock:
            job = self.jobs.get(job_id)
            if job.status is not ProductionStatus.FAILED:
                raise ValueError("only a failed production job can retry its current stage")
            job = self._event(job, "Reprise manuelle de l'etape en echec.")
            job = self.jobs.save(replace(
                job,
                status=ProductionStatus.QUEUED,
                pause_reason=None,
                error=None,
                cancel_requested=False,
                active_child_kind=None,
                active_child_attempt_id=None,
            ))
            Thread(target=self.run, args=(job_id,), daemon=True).start()
            return job

    def run(self, job_id: str) -> ProductionJob:
        claimed = False
        try:
            claimed = self._claim_job_slot(job_id)
            if not claimed:
                return self.jobs.get(job_id)
            job = self.jobs.get(job_id)
            if job.status in {ProductionStatus.DRAFT, ProductionStatus.WAITING_FOR_REVIEW}:
                return job
            job = self.jobs.save(replace(job, status=ProductionStatus.RUNNING))
            while job.status is ProductionStatus.RUNNING:
                self._raise_if_cancelled(job.job_id)
                job = self._advance(self.jobs.get(job.job_id))
            return job
        except _Cancelled:
            job = self.jobs.get(job_id)
            job = self._event(job, "Production annulee.", ProductionEventLevel.WARNING)
            return self.jobs.save(replace(
                job,
                status=ProductionStatus.CANCELLED,
                active_child_kind=None,
                active_child_attempt_id=None,
            ))
        except Exception as error:
            job = self.jobs.get(job_id)
            job = self._event(job, str(error), ProductionEventLevel.ERROR)
            return self.jobs.save(replace(
                job,
                status=ProductionStatus.FAILED,
                error=str(error)[:8_000] or type(error).__name__,
                active_child_kind=None,
                active_child_attempt_id=None,
            ))
        finally:
            if claimed:
                with self._slot_condition:
                    self._claimed.discard(job_id)
                    self._slot_condition.notify_all()

    def cancel(self, job_id: str) -> ProductionJob:
        job = self.jobs.get(job_id)
        if job.status in {
            ProductionStatus.SUCCEEDED,
            ProductionStatus.FAILED,
            ProductionStatus.CANCELLED,
        } or job.cancel_requested:
            return job
        inactive = job.status in {
            ProductionStatus.DRAFT,
            ProductionStatus.WAITING_FOR_REVIEW,
        }
        job = self._event(
            replace(
                job,
                cancel_requested=True,
                status=ProductionStatus.CANCELLED if inactive else job.status,
            ),
            "Arrêt global demandé; aucun nouveau traitement ne sera lancé.",
            ProductionEventLevel.WARNING,
        )
        job = self.jobs.save(job)
        if job.active_child_kind == "krea2" and job.krea_project_id:
            self.krea2.cancel_attempt(job.krea_project_id, job.active_child_attempt_id)
        if job.active_child_kind == "h3" and job.h3_project_id:
            self.h3_render.cancel_attempt(job.h3_project_id, job.active_child_attempt_id)
        return job

    def approve_image(self, job_id: str, attempt_id: str | None = None) -> ProductionJob:
        job = self.jobs.get(job_id)
        if job.status is not ProductionStatus.WAITING_FOR_REVIEW or job.stage is not ProductionStage.IMAGE_SELECTION:
            raise ValueError("the job is not waiting for image review")
        chosen = attempt_id or job.selected_image_attempt_id
        if chosen not in job.krea_attempt_ids or job.krea_project_id is None:
            raise ValueError("the selected image attempt does not belong to the job")
        attempt = self.krea2.get(job.krea_project_id).attempt(chosen)
        if attempt.status is not Krea2AssistedAttemptStatus.SUCCEEDED or attempt.output_asset_id is None:
            raise ValueError("the selected image attempt has no usable output")
        self.krea2.save_image(job.krea_project_id, chosen)
        job = self.jobs.save(replace(
            job,
            selected_image_attempt_id=chosen,
            selected_image_asset_id=attempt.output_asset_id,
            image_review_approved=True,
            stage=ProductionStage.H3_PROMPT,
            status=ProductionStatus.QUEUED,
            pause_reason=None,
        ))
        self._record_lora_observation(job, chosen, "human_selected")
        Thread(target=self.run, args=(job_id,), daemon=True).start()
        return job

    def review_video(
        self,
        job_id: str,
        *,
        accept: bool,
        attempt_id: str | None = None,
        instruction: str | None = None,
    ) -> ProductionJob:
        job = self.jobs.get(job_id)
        if job.status is not ProductionStatus.WAITING_FOR_REVIEW or job.stage is not ProductionStage.VIDEO_EVALUATION:
            raise ValueError("the job is not waiting for video review")
        chosen = attempt_id or job.selected_preview_attempt_id
        if chosen not in job.preview_attempt_ids:
            raise ValueError("the selected preview does not belong to the job")
        if accept:
            job = replace(
                job,
                selected_preview_attempt_id=chosen,
                video_review_approved=True,
                stage=ProductionStage.VIDEO_FINAL,
            )
        else:
            if not isinstance(instruction, str) or not instruction.strip():
                raise ValueError("a revision instruction is required")
            job = replace(
                job,
                selected_preview_attempt_id=chosen,
                manual_revision_instruction=instruction.strip(),
                stage=ProductionStage.VIDEO_PREVIEW,
            )
        job = self.jobs.save(replace(job, status=ProductionStatus.QUEUED, pause_reason=None))
        Thread(target=self.run, args=(job_id,), daemon=True).start()
        return job

    def _advance(self, job: ProductionJob) -> ProductionJob:
        if job.stage is ProductionStage.SETUP:
            return self._transition(job, ProductionStage.IMAGE_GENERATION, "Recherche de trois variantes KREA2.")
        if job.stage is ProductionStage.IMAGE_GENERATION:
            return self._generate_images(job)
        if job.stage is ProductionStage.IMAGE_SELECTION:
            return self._select_image(job)
        if job.stage is ProductionStage.H3_PROMPT:
            return self._build_h3_prompt(job)
        if job.stage is ProductionStage.VIDEO_PREVIEW:
            return self._render_preview(job)
        if job.stage is ProductionStage.VIDEO_EVALUATION:
            return self._evaluate_preview(job)
        if job.stage is ProductionStage.VIDEO_FINAL:
            return self._render_final(job)
        return job

    def _prepare_lora_plan(self, job: ProductionJob) -> ProductionJob:
        manual = tuple(
            ProductionLoraChoice(
                name=value.name,
                strength=value.strength,
                source=ProductionLoraChoiceSource.MANUAL,
                expected_effect="Pinned by the user; preserve this exact LoRA and strength.",
            )
            for value in job.config.image_settings.loras
        )
        remaining_slots = 4 - len(manual)
        resources = tuple(self.lora_resources.list_loras()) if self.lora_resources is not None else ()
        pinned = {_normalized_lora_name(value.name) for value in manual}
        available_by_name = {
            _normalized_lora_name(getattr(resource, "comfy_name", "")): resource
            for resource in resources
            if isinstance(getattr(resource, "comfy_name", None), str)
            and _normalized_lora_name(getattr(resource, "comfy_name")) not in pinned
        }
        model_choices: list[ProductionLoraChoice] = []
        strength_adjustments: list[str] = []
        if remaining_slots > 0 and available_by_name:
            available = list(available_by_name.values())[:200]
            names = [getattr(value, "comfy_name") for value in available]
            memory_values = (
                self.lora_memory.context(names, observations_per_lora=3)
                if self.lora_memory is not None
                else tuple({"name": name} for name in names)
            )
            memory_by_name = {
                _normalized_lora_name(str(value.get("name", ""))): value
                for value in memory_values
                if isinstance(value, dict)
            }
            catalogue = []
            for resource in available:
                name = getattr(resource, "comfy_name")
                safety = getattr(resource, "safety", None)
                catalogue.append({
                    "name": name,
                    "filename": getattr(resource, "filename", name),
                    "favorite": bool(getattr(resource, "favorite", False)),
                    "safety": getattr(safety, "value", str(safety or "unclassified")),
                    "memory": memory_by_name.get(_normalized_lora_name(name), {"name": name}),
                })
            payload = self._json_completion(
                job,
                (
                    "You select optional installed KREA2 LoRAs for an image-generation job. "
                    "Use only exact allowlisted names, prefer zero LoRAs over an unjustified choice, "
                    "and treat observational memory as low-confidence correlation. Return JSON only."
                ),
                (
                    f"Select at most {remaining_slots} additional LoRAs for the immutable source and intention. "
                    "The manually pinned stack cannot be changed. Every strength has a hard absolute limit: "
                    "it must be between -1 and 1 inclusive. Never return a value below -1 or above 1. "
                    "Return exactly {\"selections\":[{\"name\":\"exact allowlisted name\","
                    "\"strength\":0.8,\"expected_effect\":\"...\"}],\"rationale\":\"...\"}.\n\n"
                    f"CHECKPOINT:\n{job.config.image_settings.model_name}\n\n"
                    f"INTENTION:\n{job.intention}\n\n"
                    f"PINNED LORAS:\n{json.dumps([{'name': value.name, 'strength': value.strength} for value in manual], ensure_ascii=False)}\n\n"
                    f"AVAILABLE LORAS AND BOUNDED MEMORY:\n{json.dumps(catalogue, ensure_ascii=False)}"
                ),
                (self._image(job.source_asset_id, "Immutable source — visual evidence"),),
                "production.lora_select@0.2.0",
            )
            raw_selections = payload.get("selections")
            if not isinstance(raw_selections, list) or len(raw_selections) > remaining_slots:
                raise ValueError(f"selections must contain at most {remaining_slots} LoRAs")
            selected_names = set(pinned)
            for raw in raw_selections:
                if not isinstance(raw, dict):
                    raise ValueError("each assisted LoRA selection must be an object")
                requested_name = _required_text(raw.get("name"), "LoRA name", 500)
                normalized = _normalized_lora_name(requested_name)
                resource = available_by_name.get(normalized)
                if resource is None:
                    raise ValueError(f"LoRA is not installed or allowlisted: {requested_name}")
                if normalized in selected_names:
                    raise ValueError("the assisted LoRA selection contains a duplicate")
                requested_strength = _bounded_number(
                    raw.get("strength"),
                    "LoRA strength",
                    -20.0,
                    20.0,
                )
                strength = _production_lora_strength(requested_strength)
                if strength != requested_strength:
                    strength_adjustments.append(
                        f"{getattr(resource, 'comfy_name')}: {requested_strength:g} -> {strength:g}"
                    )
                model_choices.append(ProductionLoraChoice(
                    name=getattr(resource, "comfy_name"),
                    strength=strength,
                    source=ProductionLoraChoiceSource.MODEL,
                    expected_effect=_required_text(raw.get("expected_effect"), "expected_effect", 2_000),
                ))
                selected_names.add(normalized)
            rationale = _required_text(payload.get("rationale"), "LoRA rationale", 4_000)
            if strength_adjustments:
                rationale = (
                    f"{rationale} PanelForge applied the hard -1..1 safety limit: "
                    + "; ".join(strength_adjustments)
                    + "."
                )[:4_000]
        elif remaining_slots == 0:
            rationale = "The four user-selected LoRAs are pinned; no assisted slot remains."
        elif not resources:
            rationale = "The installed LoRA catalogue is unavailable; no assisted LoRA was added."
        else:
            rationale = "No additional LoRA was needed."
        plan = ProductionLoraPlan(choices=(*manual, *model_choices), rationale=rationale)
        job = self._event(
            replace(job, lora_plan=plan),
            (
                "Plan LoRA experimental: "
                + (", ".join(f"{value.name} x {value.strength:g}" for value in plan.choices) or "aucune LoRA")
                + "."
            ),
        )
        job = self.jobs.save(job)
        if self.lora_memory is not None:
            try:
                self.lora_memory.record_plan(
                    job_id=job.job_id,
                    checkpoint=job.config.image_settings.model_name,
                    plan=plan,
                    timestamp=self._timestamp(),
                )
            except Exception as error:
                self._save_event(
                    job.job_id,
                    f"Memoire LoRA indisponible: {type(error).__name__}",
                    ProductionEventLevel.WARNING,
                )
                job = self.jobs.get(job.job_id)
        return job

    def _effective_image_settings(self, job: ProductionJob):
        if job.lora_plan is None:
            return job.config.image_settings
        return replace(
            job.config.image_settings,
            loras=tuple(
                Krea2LoraSelection(
                    name=value.name,
                    strength=_production_lora_strength(value.strength),
                )
                for value in job.lora_plan.choices
            ),
        )

    def _lora_prompt_context(self, job: ProductionJob) -> str:
        if job.lora_plan is None:
            return ""
        stack = "; ".join(
            f"{value.name} x {value.strength:g} ({value.expected_effect})"
            for value in job.lora_plan.choices
        ) or "none"
        return f" The experimental LoRA stack is fixed for all candidates: {stack}. Do not invent other LoRA names."

    def _record_lora_observation(self, job: ProductionJob, attempt_id: str, selection: str) -> None:
        if self.lora_memory is None or job.lora_plan is None or not job.lora_plan.choices:
            return
        try:
            attempt = self.krea2.get(job.krea_project_id).attempt(attempt_id)
            score = None
            decision = next((
                value for value in reversed(job.decisions)
                if value.kind is ProductionDecisionKind.IMAGE_SELECTION
            ), None)
            if decision is not None:
                assessment = next((
                    value for value in decision.assessments if value.attempt_id == attempt_id
                ), None)
                if assessment is not None:
                    score = assessment.score
                elif decision.attempt_id == attempt_id:
                    score = decision.score
            self.lora_memory.record_observation(
                job_id=job.job_id,
                attempt_id=attempt_id,
                checkpoint=job.config.image_settings.model_name,
                prompt=attempt.prompt,
                seed=attempt.seed,
                plan=job.lora_plan,
                score=score,
                selection=selection,
                timestamp=self._timestamp(),
            )
        except Exception as error:
            self._save_event(
                job.job_id,
                f"Observation LoRA non enregistree: {type(error).__name__}",
                ProductionEventLevel.WARNING,
            )

    def _generate_images(self, job: ProductionJob) -> ProductionJob:
        if job.config.assisted_lora_selection and job.lora_plan is None:
            job = self._prepare_lora_plan(job)
        if job.krea_project_id is None:
            project = self.krea2.create_project(
                name=job.name,
                intention=job.intention,
                model_id=job.config.model_id,
                reference_asset_id=job.source_asset_id,
                reference_filename=job.source_filename,
            )
            job = self.jobs.save(replace(job, krea_project_id=project.project_id))
        project = self.krea2.get(job.krea_project_id)
        succeeded = [
            value for value in project.attempts
            if value.attempt_id in job.krea_attempt_ids
            and value.status is Krea2AssistedAttemptStatus.SUCCEEDED
        ]
        if not succeeded and project.current_prompt is None:
            self._run_llm(job, "krea_prompt", lambda: self._retry_llm(lambda: self._krea_chat(
                    project.project_id,
                    "Create a clean, stable first-frame anchor immediately before the requested video action begins. "
                    "Show the subject, identity, environment, lighting and spatial layout clearly in a physically coherent pre-action state. "
                    "Do not depict the later transformation, charge, impact or climax yet. Do not add motion blur, speed lines, afterimages, "
                    "duplicate temporal states or an abstract replacement background. The video model will create the requested action after this frame. "
                    "Use the immutable reference only as visual inspiration; do not describe an edit operation."
                    + self._lora_prompt_context(job),
                )))
            project = self.krea2.get(project.project_id)
        if succeeded and len(succeeded) < job.config.image_attempt_count:
            feedback = succeeded[-1]
            if feedback.attempt_id not in job.krea_feedback_attempt_ids:
                self._run_llm(job, "krea_prompt_revision", lambda: self._retry_llm(lambda: self._krea_chat(
                        project.project_id,
                        "Create another materially distinct clean first-frame candidate immediately before the requested action begins. "
                        "Use the previous rendered image as feedback for identity, composition and environment, but keep the action in its pre-action state. "
                        "Keep the backdrop coherent and readable enough to anchor the later video. Do not show the later transformation or climax, "
                        "and do not add motion blur, speed lines, afterimages, duplicate temporal states or an abstract background."
                        + self._lora_prompt_context(job),
                        feedback_attempt_id=feedback.attempt_id,
                    )))
                job = self.jobs.save(replace(
                    job,
                    krea_feedback_attempt_ids=(*job.krea_feedback_attempt_ids, feedback.attempt_id),
                ))
                project = self.krea2.get(project.project_id)
        if len(succeeded) >= job.config.image_attempt_count:
            return self._transition(job, ProductionStage.IMAGE_SELECTION, "Trois images disponibles; selection du meilleur candidat.")
        if project.current_prompt is None:
            raise ValueError("KREA2 did not produce an image prompt")
        rendered = self._render_krea(job, project.current_prompt)
        if rendered is None:
            return self.jobs.get(job.job_id)
        return self.jobs.get(job.job_id)

    def _render_krea(self, job: ProductionJob, prompt: str):
        last_error = "KREA2 render failed"
        for retry_index in range(2):
            project = self.krea2.prepare_attempt(
                job.krea_project_id,
                prompt=prompt,
                settings=self._effective_image_settings(job),
            )
            attempt = project.attempts[-1]
            job = self.jobs.save(replace(
                job,
                krea_attempt_ids=(*job.krea_attempt_ids, attempt.attempt_id),
            ))
            result = self._execute_child(job, "krea2", attempt.attempt_id)
            if result is None:
                return None
            attempt = self.krea2.get(job.krea_project_id).attempt(attempt.attempt_id)
            if attempt.status is Krea2AssistedAttemptStatus.SUCCEEDED:
                self._save_event(job.job_id, f"Image KREA2 {attempt.index} terminee.")
                return attempt
            last_error = attempt.error or last_error
            self._save_event(job.job_id, f"Nouvel essai KREA2 apres echec: {last_error}", ProductionEventLevel.WARNING)
        raise RuntimeError(last_error)

    def _select_image(self, job: ProductionJob) -> ProductionJob:
        if job.selected_image_attempt_id is None:
            project = self.krea2.get(job.krea_project_id)
            candidates = [
                value for value in project.attempts
                if value.attempt_id in job.krea_attempt_ids
                and value.status is Krea2AssistedAttemptStatus.SUCCEEDED
            ][:job.config.image_attempt_count]
            if len(candidates) < job.config.image_attempt_count:
                return self._transition(job, ProductionStage.IMAGE_GENERATION, "Des variantes KREA2 manquent; reprise de la recherche.")
            images = [self._image(job.source_asset_id, "Immutable source — inspiration only")]
            images.extend(
                self._image(value.output_asset_id, f"Candidate {index}")
                for index, value in enumerate(candidates, 1)
            )
            response_shape = {
                "recommended_candidate": 1,
                "candidates": [
                    {"candidate": index, "score": 0, "summary": "..."}
                    for index in range(1, len(candidates) + 1)
                ],
                "rationale": "...",
            }
            payload = self._json_completion(
                job,
                (
                    "You are a strict visual art director. Score every generated candidate and recommend one, "
                    "never the immutable source. Return one compact JSON object only."
                ),
                (
                    f"Compare the {len(candidates)} generated candidates with the immutable source and the video intention. "
                    "Choose the best true first-frame anchor for a high-quality 10-second I2V result. Prefer a coherent pre-action state, "
                    "stable identity, readable environment and usable spatial depth. Penalize action already underway, completed transformations, "
                    "motion blur, speed lines, afterimages, duplicate temporal states and weak or abstract backgrounds. "
                    "The first frame must not compress the whole video intention into one climax image. Score relative fidelity, "
                    "visual quality, composition and I2V potential. Return each candidate exactly once. "
                    "Every score must be an integer from 0 to 100. Keep each summary under 240 characters "
                    "and the rationale under 400 characters. Do not add markdown or extra keys. "
                    f"Return exactly this complete shape: {json.dumps(response_shape, ensure_ascii=False, separators=(',', ':'))}.\n\n"
                    f"Video intention: {job.intention}"
                ),
                tuple(images),
                "production.image_select@0.2.2",
                max_tokens=None,
            )
            index = _bounded_int(payload.get("recommended_candidate"), "recommended_candidate", 1, len(candidates))
            raw_assessments = payload.get("candidates")
            if not isinstance(raw_assessments, list) or len(raw_assessments) != len(candidates):
                raise ValueError("candidates must score every generated image exactly once")
            by_index: dict[int, ProductionCandidateAssessment] = {}
            for raw in raw_assessments:
                if not isinstance(raw, dict):
                    raise ValueError("each candidate assessment must be an object")
                candidate_index = _bounded_int(raw.get("candidate"), "candidate", 1, len(candidates))
                if candidate_index in by_index:
                    raise ValueError("each candidate must be assessed exactly once")
                by_index[candidate_index] = ProductionCandidateAssessment(
                    attempt_id=candidates[candidate_index - 1].attempt_id,
                    score=_bounded_int(raw.get("score"), "score", 0, 100),
                    summary=_required_text(raw.get("summary"), "summary", 2_000),
                )
            if set(by_index) != set(range(1, len(candidates) + 1)):
                raise ValueError("candidate assessments are incomplete")
            rationale = _required_text(payload.get("rationale"), "rationale", 4_000)
            chosen = candidates[index - 1]
            assessments = tuple(by_index[value] for value in range(1, len(candidates) + 1))
            score = assessments[index - 1].score
            job = job.with_decision(self._decision(
                ProductionDecisionKind.IMAGE_SELECTION,
                ProductionDecisionOutcome.SELECT,
                chosen.attempt_id,
                score,
                rationale,
                assessments=assessments,
            ))
            job = self.jobs.save(replace(
                job,
                selected_image_attempt_id=chosen.attempt_id,
                selected_image_asset_id=chosen.output_asset_id,
            ))
            for candidate in candidates:
                self._record_lora_observation(
                    job,
                    candidate.attempt_id,
                    "model_recommended" if candidate.attempt_id == chosen.attempt_id else "model_assessed",
                )
        if job.config.mode is ProductionMode.HUMAN_REVIEW and not job.image_review_approved:
            job = self._event(job, "Validation humaine de l'image recommandee attendue.")
            return self.jobs.save(replace(
                job,
                status=ProductionStatus.WAITING_FOR_REVIEW,
                pause_reason="image_review",
            ))
        self.krea2.save_image(job.krea_project_id, job.selected_image_attempt_id)
        return self._transition(job, ProductionStage.H3_PROMPT, "Image de depart selectionnee; compilation H3 Base.")

    def _build_h3_prompt(self, job: ProductionJob) -> ProductionJob:
        job = self._record_h3_input_contract(job)
        if job.prompt_session_id is None:
            session = self.prompt_lab.create_session(
                model_id=job.config.model_id,
                profile_id=_H3_PROFILE_ID,
                profile_version=_H3_VERSION,
                brief_variant_id=(
                    _H3_CREATIVE_BRIEF_ID
                    if job.config.creative_direction_enabled
                    else None
                ),
                brief_variant_version=(
                    _H3_CREATIVE_BRIEF_VERSION
                    if job.config.creative_direction_enabled
                    else None
                ),
                references=(NewReference(
                    asset_id=job.selected_image_asset_id,
                    role="first_frame",
                    label="Selected KREA2 starting frame",
                    uses=(ReferenceUse.FIRST_FRAME,),
                    evidence_policy=ReferenceEvidencePolicy.FULL,
                ),),
            )
            job = self.jobs.save(replace(job, prompt_session_id=session.session_id))
        session = self.prompt_lab.get_session(job.prompt_session_id)
        if session.active_brief_revision is None:
            job = self._save_event(
                job.job_id,
                (
                    f"Brief H3 · Direction créative 0.2.0 activée · audace "
                    f"{job.config.creative_audacity}/3; "
                    "Plan et Writer restent en recette standard 0.3.3."
                    if job.config.creative_direction_enabled
                    else "Brief H3 · Standard 0.3.3; aucune direction créative expérimentale."
                ),
            )
            source = f"Create a {job.config.duration_seconds:g}-second video. {job.intention}"
            session = self._run_llm(job, "h3_brief", lambda: self._traced_llm_retry(
                job.job_id,
                "Brief H3",
                lambda: self.prompt_lab.structure_brief(
                    job.prompt_session_id,
                    source,
                    job.config.creative_freedom,
                    job.config.creative_axes,
                    creative_audacity=job.config.creative_audacity,
                ),
            ))
            job = self.jobs.get(job.job_id)
        if not session.brief_complete:
            session = self.prompt_lab.approve_brief(job.prompt_session_id)
            job = self._save_event(
                job.job_id,
                "Brief H3 · document approuvé; passage au Plan JSON.",
            )
        elif not any("Brief H3 · document approuvé" in value.message for value in job.events):
            job = self._save_event(
                job.job_id,
                "Brief H3 · document approuvé existant réutilisé; aucun nouvel appel LLM.",
            )
        try:
            composition = self.composition.get(job.prompt_session_id)
        except (KeyError, FileNotFoundError):
            first_reference = session.references[0]
            composition = self.composition.configure(
                job.prompt_session_id,
                _H3_PROFILE_ID,
                _H3_VERSION,
                (
                    CookbookBinding("first_frame", (first_reference.reference_id,)),
                    CookbookBinding("last_frame", ()),
                ),
            )
        composition = self._ensure_composition_stage(
            job,
            CompositionStage.BEAT_SHEET,
            "h3_plan",
        )
        composition = self._ensure_composition_stage(
            job,
            CompositionStage.FINAL_PROMPT,
            "h3_final_prompt",
        )
        project = self.h3_render.get_or_create_from_session(job.prompt_session_id)
        seed = job.video_seed if job.video_seed is not None else self.h3_render.new_seed()
        job = self.jobs.save(replace(
            self.jobs.get(job.job_id),
            h3_project_id=project.project_id,
            video_seed=seed,
        ))
        job = self._save_event(
            job.job_id,
            (
                f"Prompt H3 final · compilé pour {project.input_mode.value.upper()} · "
                f"ratio {job.config.image_settings.aspect_ratio.value} · "
                f"{job.config.duration_seconds:g} s · {job.config.video_steps} steps · "
                f"seed {seed} verrouillée · musique {'ON' if job.config.music_enabled else 'OFF'} · "
                f"{_h3_video_lora_label(job.config.h3_video_lora)}."
            ),
        )
        return self._transition(
            self.jobs.get(job.job_id),
            ProductionStage.VIDEO_PREVIEW,
            f"Prompt H3 compile; lancement du preview {job.config.preview_megapixels:g} MP.",
        )

    def _ensure_composition_stage(
        self,
        job: ProductionJob,
        stage: CompositionStage,
        operation_id: str,
    ):
        composition = self.composition.get(job.prompt_session_id)
        document = composition.document(stage)
        if (
            document.active_revision is not None
            and document.approved_revision_id == document.active_revision_id
        ):
            self._save_event(
                job.job_id,
                f"{self._composition_stage_label(stage)} · document approuvé existant réutilisé; aucun nouvel appel LLM.",
            )
            return composition
        if document.active_revision is not None:
            try:
                composition = self.composition.approve(job.prompt_session_id, stage)
                self._save_event(
                    job.job_id,
                    f"{self._composition_stage_label(stage)} · brouillon existant validé et approuvé.",
                )
                return composition
            except ValueError:
                pass

        def generate_and_approve():
            self.composition.generate(job.prompt_session_id, stage)
            return self.composition.approve(job.prompt_session_id, stage)

        return self._run_llm(
            job,
            operation_id,
            lambda: self._traced_llm_retry(
                job.job_id,
                self._composition_stage_label(stage),
                generate_and_approve,
            ),
        )

    def _render_preview(self, job: ProductionJob) -> ProductionJob:
        project = self.h3_render.get(job.h3_project_id)
        instruction = job.manual_revision_instruction
        if instruction is None and job.preview_attempt_ids:
            last_id = job.preview_attempt_ids[-1]
            decision = next((
                value for value in reversed(job.decisions)
                if value.kind is ProductionDecisionKind.VIDEO_EVALUATION
                and value.attempt_id == last_id
                and value.outcome is ProductionDecisionOutcome.REVISE
            ), None)
            if decision is not None and project.current_prompt == project.attempt(last_id).prompt:
                instruction = decision.revision_instruction
        if instruction:
            feedback_id = job.selected_preview_attempt_id or job.preview_attempt_ids[-1]
            self._run_llm(job, "h3_prompt_revision", lambda: self._traced_llm_retry(
                job.job_id,
                "Révision du prompt H3",
                lambda: self._h3_chat(
                    project.project_id,
                    instruction,
                    feedback_attempt_id=feedback_id,
                ),
            ))
            project = self.h3_render.get(project.project_id)
            job = self.jobs.save(replace(
                self.jobs.get(job.job_id),
                manual_revision_instruction=None,
            ))
        attempt = None
        for retry_index in range(2):
            project = self.h3_render.get(job.h3_project_id)
            project = self.h3_render.prepare_attempt(
                project.project_id,
                prompt=project.current_prompt,
                settings=self._video_settings(job, job.config.preview_megapixels),
                music_enabled=job.config.music_enabled,
                **(
                    {"video_lora": job.config.h3_video_lora}
                    if job.config.h3_video_lora is not None
                    else {}
                ),
            )
            attempt = project.attempts[-1]
            latest = self.jobs.get(job.job_id)
            job = self.jobs.save(replace(
                latest,
                preview_attempt_ids=(*latest.preview_attempt_ids, attempt.attempt_id),
                selected_preview_attempt_id=attempt.attempt_id,
            ))
            result = self._execute_child(job, "h3", attempt.attempt_id)
            if result is None:
                return self.jobs.get(job.job_id)
            attempt = self.h3_render.get(job.h3_project_id).attempt(attempt.attempt_id)
            if attempt.status is H3RenderAttemptStatus.SUCCEEDED:
                break
            if retry_index == 0:
                self._save_event(
                    job.job_id,
                    f"Nouvel essai H3 apres echec: {attempt.error or 'erreur moteur'}",
                    ProductionEventLevel.WARNING,
                )
                self._wait_for_video_cooldown(job.job_id)
        assert attempt is not None
        if attempt.status is not H3RenderAttemptStatus.SUCCEEDED:
            raise RuntimeError(attempt.error or "H3 preview render failed")
        self._save_event(job.job_id, f"Preview H3 {attempt.index} termine.")
        return self._transition(self.jobs.get(job.job_id), ProductionStage.VIDEO_EVALUATION, "Evaluation visuelle du preview.")

    def _evaluate_preview(self, job: ProductionJob) -> ProductionJob:
        attempt_id = job.preview_attempt_ids[-1]
        prior = next((
            value for value in job.decisions
            if value.kind is ProductionDecisionKind.VIDEO_EVALUATION and value.attempt_id == attempt_id
        ), None)
        if prior is None:
            project = self.h3_render.get(job.h3_project_id)
            attempt = project.attempt(attempt_id)
            images = [self._image(job.selected_image_asset_id, "Selected starting frame")]
            images.extend(
                self._image(frame.asset_id, f"Video keyframe at {frame.timestamp_ms} ms")
                for frame in attempt.keyframes[-3:]
            )
            payload = self._json_completion(
                job,
                "You are a strict I2V review director. Judge only what the supplied frames prove. Return JSON only.",
                (
                    "Evaluate fidelity to the intention, subject identity, composition, visual continuity and the visible evolution. "
                    "Keyframes cannot prove audio or every movement, so do not invent evidence. "
                    "Return exactly {\"decision\":\"accept\"|\"revise\",\"score\":0-100,\"rationale\":\"...\","
                    "\"revision_instruction\":\"specific instruction, empty when accepted\"}.\n\n"
                    f"Intention: {job.intention}\nCurrent H3 prompt: {attempt.prompt}"
                ),
                tuple(images),
                "production.video_evaluate@0.1.0",
            )
            score = _bounded_int(payload.get("score"), "score", 0, 100)
            requested = str(payload.get("decision", "")).strip().lower()
            accepted = requested == "accept" or score >= job.config.video_acceptance_score
            instruction = None if accepted else _required_text(
                payload.get("revision_instruction"),
                "revision_instruction",
                8_000,
            )
            prior = self._decision(
                ProductionDecisionKind.VIDEO_EVALUATION,
                ProductionDecisionOutcome.ACCEPT if accepted else ProductionDecisionOutcome.REVISE,
                attempt_id,
                score,
                _required_text(payload.get("rationale"), "rationale", 4_000),
                instruction,
            )
            job = self.jobs.save(job.with_decision(prior))
        if job.config.mode is ProductionMode.HUMAN_REVIEW and not job.video_review_approved:
            job = self._event(job, "Validation humaine du preview attendue.")
            return self.jobs.save(replace(
                job,
                status=ProductionStatus.WAITING_FOR_REVIEW,
                pause_reason="video_review",
                selected_preview_attempt_id=attempt_id,
            ))
        if prior.outcome is ProductionDecisionOutcome.ACCEPT:
            return self._transition(replace(job, selected_preview_attempt_id=attempt_id), ProductionStage.VIDEO_FINAL, "Preview accepte; rendu final 1.2 MP.")
        evaluation_count = sum(
            value.kind is ProductionDecisionKind.VIDEO_EVALUATION
            and value.outcome is not ProductionDecisionOutcome.FALLBACK
            for value in job.decisions
        )
        if evaluation_count < job.config.video_preview_limit:
            self._wait_for_video_cooldown(job.job_id)
            return self._transition(job, ProductionStage.VIDEO_PREVIEW, "Revision automatique du prompt H3.")
        evaluations = [
            value for value in job.decisions
            if value.kind is ProductionDecisionKind.VIDEO_EVALUATION
        ]
        best = max(evaluations, key=lambda value: value.score)
        fallback = self._decision(
            ProductionDecisionKind.VIDEO_EVALUATION,
            ProductionDecisionOutcome.FALLBACK,
            best.attempt_id,
            best.score,
            "Preview limit reached; using the highest-scoring result.",
        )
        job = self.jobs.save(job.with_decision(fallback))
        return self._transition(replace(job, selected_preview_attempt_id=best.attempt_id), ProductionStage.VIDEO_FINAL, "Limite atteinte; meilleur preview retenu.")

    def _render_final(self, job: ProductionJob) -> ProductionJob:
        if job.final_attempt_id is not None:
            attempt = self.h3_render.get(job.h3_project_id).attempt(job.final_attempt_id)
            if attempt.status is H3RenderAttemptStatus.SUCCEEDED:
                return self._complete(job)
        self._wait_for_video_cooldown(job.job_id)
        attempt = None
        for retry_index in range(2):
            project = self.h3_render.resume_attempt(job.h3_project_id, job.selected_preview_attempt_id)
            project = self.h3_render.prepare_attempt(
                project.project_id,
                prompt=project.current_prompt,
                settings=self._video_settings(job, job.config.final_megapixels),
                music_enabled=job.config.music_enabled,
                **(
                    {"video_lora": job.config.h3_video_lora}
                    if job.config.h3_video_lora is not None
                    else {}
                ),
            )
            attempt = project.attempts[-1]
            job = self.jobs.save(replace(
                self.jobs.get(job.job_id),
                final_attempt_id=attempt.attempt_id,
            ))
            result = self._execute_child(job, "h3", attempt.attempt_id)
            if result is None:
                return self.jobs.get(job.job_id)
            attempt = self.h3_render.get(job.h3_project_id).attempt(attempt.attempt_id)
            if attempt.status is H3RenderAttemptStatus.SUCCEEDED:
                break
            if retry_index == 0:
                self._save_event(
                    job.job_id,
                    f"Nouvel essai final H3 apres echec: {attempt.error or 'erreur moteur'}",
                    ProductionEventLevel.WARNING,
                )
                self._wait_for_video_cooldown(job.job_id)
        assert attempt is not None
        if attempt.status is not H3RenderAttemptStatus.SUCCEEDED:
            raise RuntimeError(attempt.error or "H3 final render failed")
        return self._complete(self.jobs.get(job.job_id))

    def _complete(self, job: ProductionJob) -> ProductionJob:
        job = self._event(job, "Production terminee avec succes.")
        return self.jobs.save(replace(
            job,
            status=ProductionStatus.SUCCEEDED,
            stage=ProductionStage.COMPLETE,
            pause_reason=None,
            active_child_kind=None,
            active_child_attempt_id=None,
        ))

    def _execute_child(self, job: ProductionJob, kind: str, attempt_id: str):
        workload = (
            ProductionWorkload.IMAGE_RENDER
            if kind == "krea2"
            else ProductionWorkload.VIDEO_RENDER
        )
        requirement = ResourceRequirement(
            ComputeResource.REMOTE_GPU,
            workload,
            _resource_operation_label(job.stage, workload),
        )
        with self._resource(job, requirement):
            if kind == "krea2":
                self.krea2.queue_attempt(job.krea_project_id, attempt_id)
                execute = lambda: self.krea2.execute_attempt(job.krea_project_id, attempt_id)
                cancel = lambda: self.krea2.cancel_attempt(job.krea_project_id, attempt_id)
            else:
                self.h3_render.queue_attempt(job.h3_project_id, attempt_id)
                execute = lambda: self.h3_render.execute_attempt(job.h3_project_id, attempt_id)
                cancel = lambda: self.h3_render.cancel_attempt(job.h3_project_id, attempt_id)
            self.jobs.save(replace(
                self.jobs.get(job.job_id),
                active_child_kind=kind,
                active_child_attempt_id=attempt_id,
            ))
            box: list[Any] = []
            errors: list[BaseException] = []

            def execute_child() -> None:
                try:
                    box.append(execute())
                except BaseException as error:
                    errors.append(error)

            worker = Thread(target=execute_child, daemon=True)
            worker.start()
            overheated = False
            while worker.is_alive():
                worker.join(timeout=self.monitor_interval)
                latest = self.jobs.get(job.job_id)
                if latest.cancel_requested:
                    cancel()
                    worker.join(timeout=self.monitor_interval)
                    raise _Cancelled()
                snapshot = self.thermal_monitor.snapshot()
                if self._over_stop(snapshot, latest.config, requirement.resource):
                    overheated = True
                    self._save_event(
                        job.job_id,
                        "Seuil thermique du GPU serveur atteint; rendu enfant annule.",
                        ProductionEventLevel.WARNING,
                    )
                    cancel()
                    worker.join(timeout=self.monitor_interval)
                    break
            self.jobs.save(replace(
                self.jobs.get(job.job_id),
                active_child_kind=None,
                active_child_attempt_id=None,
            ))
            if errors:
                raise errors[0]
        if overheated:
            if workload is ProductionWorkload.VIDEO_RENDER:
                self._wait_for_video_cooldown(job.job_id)
            else:
                self._wait_until_safe(job.job_id, ComputeResource.REMOTE_GPU)
            return None
        return box[0] if box else None

    @contextmanager
    def _resource(self, job: ProductionJob, requirement: ResourceRequirement):
        def cancelled() -> bool:
            return self.jobs.get(job.job_id).cancel_requested

        def waiting() -> None:
            latest = self.jobs.get(job.job_id)
            latest = self._event(
                latest,
                f"Ressource {requirement.resource.value} occupee; mise en attente FIFO.",
            )
            self.jobs.save(replace(
                latest,
                status=ProductionStatus.WAITING_RESOURCE,
                pause_reason=f"{requirement.resource.value}:{requirement.operation}",
            ))

        def acquired() -> None:
            latest = self.jobs.get(job.job_id)
            self.jobs.save(replace(
                latest,
                status=ProductionStatus.RUNNING,
                pause_reason=None,
            ))

        try:
            with self.resource_leases.lease(
                job.job_id,
                requirement,
                cancelled=cancelled,
                on_wait=waiting,
                on_acquired=acquired,
            ):
                # Capacity is claimed before the thermal wait so resource priority
                # remains FIFO even when several jobs are cooling simultaneously.
                self._wait_until_safe(job.job_id, requirement.resource)
                yield
        except ResourceWaitCancelled as error:
            raise _Cancelled() from error

    def _run_llm(self, job: ProductionJob, _operation_name: str, operation: Callable[[], Any]) -> Any:
        requirement = ResourceRequirement(
            llm_compute_resource(
                job.config.model_id,
                server_resource=self.server_llm_resource,
            ),
            ProductionWorkload.LLM,
            _resource_operation_label(job.stage, ProductionWorkload.LLM),
        )
        with self._resource(job, requirement):
            self._raise_if_cancelled(job.job_id)
            result = operation()
            # OpenAI-compatible synchronous requests cannot be forcefully killed
            # once sent. Discard their result after cancellation and never start
            # the next LLM or render stage.
            self._raise_if_cancelled(job.job_id)
            return result

    def _wait_for_video_cooldown(self, job_id: str) -> None:
        job = self.jobs.get(job_id)
        policy = job.config.thermal
        requirement = ResourceRequirement(
            ComputeResource.REMOTE_GPU,
            ProductionWorkload.VIDEO_COOLDOWN,
            _resource_operation_label(job.stage, ProductionWorkload.VIDEO_COOLDOWN),
        )
        with self._resource(job, requirement):
            self._wait_until_safe(
                job_id,
                ComputeResource.REMOTE_GPU,
                stable_seconds=policy.cooldown_seconds,
                reason="cooldown_between_video_renders",
            )

    def _wait_until_safe(
        self,
        job_id: str,
        resource: ComputeResource,
        *,
        stable_seconds: int = 0,
        reason: str = "thermal_guard",
    ) -> None:
        job = self.jobs.get(job_id)
        policy = job.config.thermal
        snapshot = self.thermal_monitor.snapshot()
        unavailable = self._unavailable(snapshot, job.config, resource)
        must_pause = stable_seconds > 0 or self._over_stop(snapshot, job.config, resource) or (
            policy.pause_when_unavailable and unavailable
        )
        if not must_pause:
            return
        job = self._event(
            job,
            f"Pause thermique {resource.value}: attente du seuil de reprise.",
            ProductionEventLevel.WARNING,
        )
        self.jobs.save(replace(job, status=ProductionStatus.PAUSED_THERMAL, pause_reason=reason))
        below_since: float | None = None
        while True:
            self._raise_if_cancelled(job_id)
            current = self.jobs.get(job_id)
            snapshot = self.thermal_monitor.snapshot()
            unavailable = self._unavailable(snapshot, current.config, resource)
            monitored = self._resource_monitored(current.config, resource)
            temperature = self._monitored_temperature(snapshot, current.config, resource)
            safe = (
                True
                if not monitored
                else temperature <= policy.resume_temperature_c
                if temperature is not None
                else not policy.pause_when_unavailable
            )
            if unavailable and policy.pause_when_unavailable:
                safe = False
            now = self._monotonic()
            if safe:
                below_since = now if below_since is None else below_since
                if now - below_since >= stable_seconds:
                    self.jobs.save(replace(current, status=ProductionStatus.RUNNING, pause_reason=None))
                    return
            else:
                below_since = None
            self._sleep(self.monitor_interval)

    def _resource_temperature(self, snapshot: ThermalSnapshot, resource: ComputeResource) -> float | None:
        return (
            snapshot.local_temperature_c
            if resource is ComputeResource.LOCAL_GPU
            else snapshot.remote_temperature_c
        )

    def _resource_error(self, snapshot: ThermalSnapshot, resource: ComputeResource) -> str | None:
        return snapshot.local_error if resource is ComputeResource.LOCAL_GPU else snapshot.remote_error

    def _resource_monitored(self, config: ProductionConfig, resource: ComputeResource) -> bool:
        return config.thermal.monitor_local if resource is ComputeResource.LOCAL_GPU else config.thermal.monitor_remote

    def _monitored_temperature(
        self,
        snapshot: ThermalSnapshot,
        config: ProductionConfig,
        resource: ComputeResource,
    ) -> float | None:
        if not self._resource_monitored(config, resource):
            return None
        return self._resource_temperature(snapshot, resource)

    def _unavailable(
        self,
        snapshot: ThermalSnapshot,
        config: ProductionConfig,
        resource: ComputeResource,
    ) -> bool:
        return self._resource_monitored(config, resource) and self._resource_temperature(snapshot, resource) is None

    def _over_stop(
        self,
        snapshot: ThermalSnapshot,
        config: ProductionConfig,
        resource: ComputeResource,
    ) -> bool:
        temperature = self._monitored_temperature(snapshot, config, resource)
        return temperature is not None and temperature >= config.thermal.stop_temperature_c

    def _video_settings(self, job: ProductionJob, megapixels: float) -> VideoLabSettings:
        return VideoLabSettings(
            aspect_ratio=VideoAspectRatio(job.config.image_settings.aspect_ratio.value),
            megapixels=megapixels,
            duration_seconds=job.config.duration_seconds,
            steps=job.config.video_steps,
            seed=job.video_seed,
            seed_locked=True,
        )

    def _krea_chat(self, project_id: str, message: str, *, feedback_attempt_id: str | None = None):
        terminal = None
        for event in self.krea2.stream_chat(project_id, message, feedback_attempt_id=feedback_attempt_id):
            if event.project is not None:
                terminal = event.project
            if event.error:
                raise ValueError(event.error)
        if terminal is None or terminal.current_prompt is None:
            raise ValueError("KREA2 prompt generation returned no prompt")
        return terminal

    def _h3_chat(self, project_id: str, message: str, *, feedback_attempt_id: str):
        terminal = None
        for event in self.h3_render.stream_chat(project_id, message, feedback_attempt_id=feedback_attempt_id):
            if event.project is not None:
                terminal = event.project
            if event.error:
                raise ValueError(event.error)
        if terminal is None:
            raise ValueError("H3 prompt revision returned no project")
        return terminal

    def _json_completion(
        self,
        job: ProductionJob,
        system_prompt: str,
        user_prompt: str,
        images: tuple[ImageInput, ...],
        operation_id: str,
        *,
        max_tokens: int | None = 16_384,
    ) -> dict[str, Any]:
        attempt_index = 0

        def complete_and_decode() -> dict[str, Any]:
            nonlocal attempt_index
            token_budget = (
                None
                if max_tokens is None
                else min(max_tokens * (2 ** attempt_index), 262_144)
            )
            attempt_index += 1
            result = self.gateway.complete(CompletionRequest(
                model_id=job.config.model_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                images=images,
                temperature=0.1,
                max_tokens=token_budget,
                operation_id=operation_id,
            ))
            if getattr(result, "finish_reason", None) == "length":
                raise ValueError(
                    f"{operation_id} · {truncated_response_message(token_budget)}"
                )
            return _json_object(result.content)

        return self._run_llm(job, operation_id, lambda: self._retry_llm(complete_and_decode))

    def _record_h3_input_contract(self, job: ProductionJob) -> ProductionJob:
        prefix = "Contrat d'entrée H3 ·"
        if any(value.message.startswith(prefix) for value in job.events):
            return job
        attempt_label = job.selected_image_attempt_id or "image sélectionnée"
        if job.krea_project_id is not None and job.selected_image_attempt_id is not None:
            try:
                attempt = self.krea2.get(job.krea_project_id).attempt(
                    job.selected_image_attempt_id
                )
                attempt_label = f"Essai {attempt.index} ({attempt.attempt_id})"
            except (KeyError, FileNotFoundError, ValueError):
                pass
        return self.jobs.save(self._event(
            job,
            (
                f"{prefix} mode I2VA · first frame = {attempt_label} · last frame = aucune · "
                f"ratio {job.config.image_settings.aspect_ratio.value} · "
                f"{job.config.duration_seconds:g} s · {job.config.video_steps} steps · "
                f"preview {job.config.preview_megapixels:g} MP · final {job.config.final_megapixels:g} MP · "
                f"musique {'ON' if job.config.music_enabled else 'OFF'} · "
                f"{_h3_video_lora_label(job.config.h3_video_lora)} · "
                f"direction créative {'ON' if job.config.creative_direction_enabled else 'OFF'} · "
                f"audace {job.config.creative_audacity}/3."
            ),
        ))

    def _traced_llm_retry(
        self,
        job_id: str,
        label: str,
        operation: Callable[[], Any],
    ) -> Any:
        last_error: Exception | None = None
        for index in range(2):
            job = self.jobs.get(job_id)
            self._save_event(
                job_id,
                (
                    f"{label} · thinking · tentative {index + 1}/2 · "
                    f"modèle {job.config.model_id}."
                ),
            )
            started = self._monotonic()
            try:
                result = operation()
            except Exception as error:
                last_error = error
                self._save_event(
                    job_id,
                    (
                        f"{label} · tentative {index + 1}/2 rejetée après "
                        f"{max(0.0, self._monotonic() - started):.1f} s · "
                        f"{type(error).__name__}: {(str(error).strip() or 'erreur sans détail')[:600]}"
                    ),
                    ProductionEventLevel.WARNING if index == 0 else ProductionEventLevel.ERROR,
                )
                continue
            self._save_event(
                job_id,
                (
                    f"{label} · réponse reçue en "
                    f"{max(0.0, self._monotonic() - started):.1f} s; candidat accepté par cette étape."
                ),
            )
            return result
        assert last_error is not None
        raise last_error

    @staticmethod
    def _composition_stage_label(stage: CompositionStage) -> str:
        if stage is CompositionStage.BEAT_SHEET:
            return "Plan JSON H3"
        if stage is CompositionStage.FINAL_PROMPT:
            return "Prompt final H3"
        return stage.value

    def _retry_llm(self, operation: Callable[[], Any]) -> Any:
        first_error: Exception | None = None
        for index in range(2):
            try:
                return operation()
            except Exception as error:
                first_error = error
                if index == 0:
                    continue
        assert first_error is not None
        raise first_error

    def _image(self, asset_id: str, label: str) -> ImageInput:
        asset = self.assets.get(asset_id)
        return ImageInput(asset.media_type, self.assets.read_bytes(asset_id), label)

    def _transition(self, job: ProductionJob, stage: ProductionStage, message: str) -> ProductionJob:
        job = self._event(job, message)
        return self.jobs.save(replace(job, stage=stage, status=ProductionStatus.RUNNING))

    def _event(
        self,
        job: ProductionJob,
        message: str,
        level: ProductionEventLevel = ProductionEventLevel.INFO,
    ) -> ProductionJob:
        return job.with_event(ProductionEvent(
            event_id=self._event_id(),
            timestamp=self._timestamp(),
            stage=job.stage,
            level=level,
            message=message,
        ))

    def _save_event(self, job_id: str, message: str, level: ProductionEventLevel = ProductionEventLevel.INFO) -> ProductionJob:
        return self.jobs.save(self._event(self.jobs.get(job_id), message, level))

    def _decision(
        self,
        kind: ProductionDecisionKind,
        outcome: ProductionDecisionOutcome,
        attempt_id: str,
        score: int,
        rationale: str,
        instruction: str | None = None,
        assessments: tuple[ProductionCandidateAssessment, ...] = (),
    ) -> ProductionDecision:
        return ProductionDecision(
            decision_id=self._decision_id(),
            timestamp=self._timestamp(),
            kind=kind,
            outcome=outcome,
            attempt_id=attempt_id,
            score=score,
            rationale=rationale,
            revision_instruction=instruction,
            assessments=assessments,
        )

    def _timestamp(self) -> str:
        return self._now().astimezone(UTC).isoformat().replace("+00:00", "Z")

    def _raise_if_cancelled(self, job_id: str) -> None:
        if self.jobs.get(job_id).cancel_requested:
            raise _Cancelled()

    def _claim_job_slot(self, job_id: str) -> bool:
        with self._slot_condition:
            if job_id in self._claimed or job_id in self._claim_waiters:
                return False
            self._claim_waiters.append(job_id)
            try:
                while (
                    len(self._claimed) >= self.max_active_jobs
                    or self._claim_waiters[0] != job_id
                ):
                    if self.jobs.get(job_id).cancel_requested:
                        raise _Cancelled()
                    self._slot_condition.wait(min(self.monitor_interval, 0.2))
                self._claim_waiters.pop(0)
                self._claimed.add(job_id)
                self._slot_condition.notify_all()
                return True
            except BaseException:
                if job_id in self._claim_waiters:
                    self._claim_waiters.remove(job_id)
                self._slot_condition.notify_all()
                raise


def _json_object(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise ValueError("model response must be text")
    value = _JSON_FENCE.sub("", raw.strip())
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("model response contains no JSON object")
        decoded = json.loads(value[start:end + 1])
    if not isinstance(decoded, dict):
        raise ValueError("model response must be one JSON object")
    return decoded


def _required_text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return value.strip()


def _bounded_int(value: object, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return value


def _bounded_number(value: object, label: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    number = float(value)
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum:g} and {maximum:g}")
    return number


def _production_lora_strength(value: float) -> float:
    """Keep Production renders safe while legacy plans remain readable."""

    return max(-1.0, min(1.0, float(value)))


def _h3_video_lora_label(value: object) -> str:
    if value is None:
        return "LoRA vidéo H3 Standard"
    clip = " · CLIP -2" if getattr(value, "clip_last_layer", None) == -2 else ""
    return (
        f"LoRA vidéo H3 {getattr(value, 'name', '?')} × "
        f"{float(getattr(value, 'strength', 0)):.2f}{clip}"
    )


def _normalized_lora_name(value: str) -> str:
    return value.replace("\\", "/").strip().casefold()


__all__ = ["ProductionService"]
