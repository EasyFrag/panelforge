"""Human-guided, restart-safe Production V2 workshop orchestration."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import json
import re
import secrets
from threading import RLock, Thread
from time import monotonic
from typing import Any, Callable, Protocol
from uuid import uuid4

from panelforge.domain import (
    CompositionStage,
    CookbookBinding,
    CreativeFreedomAxes,
    H3RenderAttemptStatus,
    H3VideoLoraSelection,
    Krea2AssistedAttemptStatus,
    Krea2BatchSettings,
    KREA2_BATCH_RGTHREE_MAX_SEED,
    Krea2LoraSelection,
    ProductionV2Anchor,
    ProductionV2AnchorRole,
    ProductionV2Candidate,
    ProductionV2CandidateKind,
    ProductionV2CandidateStatus,
    ProductionV2Event,
    ProductionV2LlmTrace,
    ProductionV2LlmTraceStatus,
    ProductionV2MemoryObservation,
    ProductionV2MemoryProfile,
    ProductionV2Preference,
    ProductionV2PromptStrategy,
    ProductionV2Project,
    ProductionV2ReferenceMode,
    ProductionV2Route,
    ProductionV2Stage,
    ProductionV2Status,
    ProductionV2VisualRecipeRevision,
    ProductionLoraChoice,
    ProductionLoraChoiceSource,
    ProductionLoraPlan,
    ReferenceEvidencePolicy,
    ReferenceUse,
    VideoAspectRatio,
    VideoLabSettings,
)
from .prompt_lab import CompletionRequest, NewReference, StreamEventKind, truncated_response_message
from .h3_render import h3_prompt_duration_warning


_H3_BASE_PROFILE = ("minimax.h3.fl2va.direct", "0.3.3")
_REF2V_PROFILE = ("minimax.h3.ref2v.direct", "0.4.0")
_CREATIVE_BRIEF = ("creative-direction", "0.2.0")
_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class _OperationCancelled(RuntimeError):
    """Stop a stale worker without changing the current project state."""


class ProductionV2Store(Protocol):
    def create_project(self, project: ProductionV2Project) -> ProductionV2Project: ...
    def save_project(self, project: ProductionV2Project) -> ProductionV2Project: ...
    def get_project(self, project_id: str) -> ProductionV2Project: ...
    def list_projects(self, limit: int = 30) -> list[ProductionV2Project]: ...
    def create_profile(self, profile: ProductionV2MemoryProfile) -> ProductionV2MemoryProfile: ...
    def save_profile(self, profile: ProductionV2MemoryProfile) -> ProductionV2MemoryProfile: ...
    def get_profile(self, profile_id: str) -> ProductionV2MemoryProfile: ...
    def list_profiles(self) -> list[ProductionV2MemoryProfile]: ...


class ProductionV2Service:
    """Coordinate manual choices while retaining all generated child artifacts."""

    def __init__(
        self,
        *,
        assets: Any,
        store: ProductionV2Store,
        krea2: Any,
        prompt_lab: Any,
        composition: Any,
        h3_render: Any,
        thermal_monitor: Any | None = None,
        gateway: Any | None = None,
        lora_resources: Any | None = None,
        lora_memory: Any | None = None,
        project_id_factory: Callable[[], str] | None = None,
        candidate_id_factory: Callable[[], str] | None = None,
        revision_id_factory: Callable[[], str] | None = None,
        event_id_factory: Callable[[], str] | None = None,
        batch_id_factory: Callable[[], str] | None = None,
        trace_id_factory: Callable[[], str] | None = None,
        operation_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.assets = assets
        self.store = store
        self.krea2 = krea2
        self.prompt_lab = prompt_lab
        self.composition = composition
        self.h3_render = h3_render
        self.thermal_monitor = thermal_monitor
        self.gateway = gateway
        self.lora_resources = lora_resources
        self.lora_memory = lora_memory
        self._project_id = project_id_factory or (lambda: f"production-v2-{uuid4().hex}")
        self._candidate_id = candidate_id_factory or (lambda: f"candidate-{uuid4().hex}")
        self._revision_id = revision_id_factory or (lambda: f"visual-recipe-{uuid4().hex}")
        self._event_id = event_id_factory or (lambda: f"event-{uuid4().hex}")
        self._batch_id = batch_id_factory or (lambda: f"batch-{uuid4().hex}")
        self._trace_id = trace_id_factory or (lambda: f"llm-trace-{uuid4().hex}")
        self._operation_id = operation_id_factory or (lambda: f"operation-{uuid4().hex}")
        self._lock = RLock()
        self._claimed: dict[str, str] = {}
        self._ensure_default_profiles()

    def create_project(
        self,
        *,
        name: str,
        intention: str,
        source_asset_id: str,
        source_filename: str,
        initial_model_id: str,
        memory_profile_id: str,
        music_enabled: bool = False,
        video_lora: Any | None = None,
        stop_temperature_c: float = 85.0,
        resume_temperature_c: float = 40.0,
        cooldown_seconds: int = 120,
    ) -> ProductionV2Project:
        asset = self.assets.get(source_asset_id)
        if not asset.media_type.startswith("image/"):
            raise ValueError("the immutable Production V2 source must be an image")
        self.store.get_profile(memory_profile_id)
        if not 30 <= float(stop_temperature_c) <= 110:
            raise ValueError("stop_temperature_c must be between 30 and 110")
        if not 15 <= float(resume_temperature_c) < float(stop_temperature_c):
            raise ValueError("resume_temperature_c must be below the stop temperature")
        if not 0 <= int(cooldown_seconds) <= 86_400:
            raise ValueError("cooldown_seconds must be between 0 and 86400")
        initial_model = _text(initial_model_id, "initial_model_id", 300)
        project = ProductionV2Project(
            project_id=self._project_id(),
            name=_text(name, "name", 120),
            intention=_text(intention, "intention", 20_000),
            source_asset_id=source_asset_id,
            source_filename=_text(source_filename, "source_filename", 240),
            initial_model_id=initial_model,
            memory_profile_id=memory_profile_id,
            video_compile_model_id=initial_model,
            music_enabled=bool(music_enabled),
            video_lora=video_lora,
            stop_temperature_c=float(stop_temperature_c),
            resume_temperature_c=float(resume_temperature_c),
            cooldown_seconds=int(cooldown_seconds),
        )
        project = self._event(project, "Projet V2 créé; la source restera immuable.")
        return self.store.create_project(project)

    def get(self, project_id: str) -> ProductionV2Project:
        return self.store.get_project(project_id)

    def list(self, limit: int = 30) -> list[ProductionV2Project]:
        return self.store.list_projects(limit)

    def list_profiles(self) -> list[ProductionV2MemoryProfile]:
        return self.store.list_profiles()

    def create_profile(self, name: str) -> ProductionV2MemoryProfile:
        clean = _text(name, "profile name", 80)
        profile = ProductionV2MemoryProfile(
            profile_id=f"memory-{uuid4().hex}",
            name=clean,
            created_at=_timestamp(),
        )
        return self.store.create_profile(profile)

    def select_memory_profile(self, project_id: str, profile_id: str) -> ProductionV2Project:
        self.store.get_profile(profile_id)
        project = self.store.get_project(project_id)
        if project.status is ProductionV2Status.BUSY:
            raise ValueError("cannot change memory profile while an operation is active")
        return self.store.save_project(replace(project, memory_profile_id=profile_id))

    def queue_candidates(
        self,
        project_id: str,
        *,
        role: ProductionV2AnchorRole,
        instruction: str,
        model_id: str | None,
        settings: tuple[Krea2BatchSettings, ...],
        feedback_parent_id: str | None = None,
        technical_comparison: bool = False,
        freeze_prompt_seed: bool | None = None,
        prompt_strategy: ProductionV2PromptStrategy | None = None,
        preserve_seed: bool | None = None,
        preserve_model: bool = False,
        explore_models: bool = False,
        preserve_loras: bool = False,
        reference_mode: ProductionV2ReferenceMode = ProductionV2ReferenceMode.RECIPE,
        guidance_candidate_id: str | None = None,
        assisted_lora_selection: bool = False,
        lora_instruction: str = "",
    ) -> ProductionV2Project:
        if not 1 <= len(settings) <= 6:
            raise ValueError("a Production V2 batch requires 1 to 6 candidates")
        for image_settings in settings:
            for lora in image_settings.loras:
                if not -1 <= lora.strength <= 1:
                    raise ValueError("KREA2 LoRA strength must be between -1 and 1")
        project = self.store.get_project(project_id)
        self._require_idle(project)
        self._require_worker_released(project_id)
        parent = project.candidate(feedback_parent_id) if feedback_parent_id else None
        if parent is not None and parent.status is not ProductionV2CandidateStatus.SUCCEEDED:
            raise ValueError("feedback parent must be a completed candidate")
        if parent is not None and parent.role is not role:
            raise ValueError(
                "the feedback parent must belong to the same role; use it as explicit visual guidance instead"
            )
        if not isinstance(reference_mode, ProductionV2ReferenceMode):
            raise TypeError("reference_mode must be a ProductionV2ReferenceMode")
        guidance = (
            project.candidate(guidance_candidate_id)
            if guidance_candidate_id else None
        )
        if guidance is not None and guidance.status is not ProductionV2CandidateStatus.SUCCEEDED:
            raise ValueError("visual guidance must be a completed candidate")
        if reference_mode is ProductionV2ReferenceMode.RECIPE_AND_GUIDANCE and guidance is None:
            raise ValueError("recipe_and_guidance requires a completed guidance candidate")

        legacy_frozen = technical_comparison if freeze_prompt_seed is None else bool(freeze_prompt_seed)
        strategy = prompt_strategy or (
            ProductionV2PromptStrategy.PRESERVE_CURRENT
            if legacy_frozen else ProductionV2PromptStrategy.EVOLVE_BETWEEN
        )
        if not isinstance(strategy, ProductionV2PromptStrategy):
            raise TypeError("prompt_strategy must be a ProductionV2PromptStrategy")
        keep_seed = legacy_frozen if preserve_seed is None else bool(preserve_seed)
        recipe = project.active_recipe
        source_candidate = parent
        if source_candidate is None and recipe is not None:
            source_candidate = project.candidate(recipe.source_candidate_id)
        source_prompt = (
            parent.prompt if parent is not None
            else recipe.prompt if recipe is not None else None
        )
        source_seed = (
            parent.seed if parent is not None
            else recipe.seed if recipe is not None else None
        )
        source_settings = (
            parent.settings if parent is not None
            else recipe.settings if recipe is not None else None
        )
        if strategy is ProductionV2PromptStrategy.PRESERVE_CURRENT and not source_prompt:
            raise ValueError("preserving the prompt requires a parent or a validated visual recipe")
        if keep_seed and source_seed is None:
            # On a first comparison there is no inherited seed yet: create one
            # batch seed and reuse it for every candidate.
            source_seed = secrets.randbelow(KREA2_BATCH_RGTHREE_MAX_SEED + 1)
        if assisted_lora_selection and preserve_loras:
            raise ValueError("assisted LoRA exploration requires Conserver LoRA to be disabled")
        if assisted_lora_selection and len(settings) < 2:
            raise ValueError("assisted LoRA exploration requires at least two candidates")
        if explore_models and preserve_model:
            raise ValueError("random model exploration requires Conserver Modèle to be disabled")

        normalized_settings = tuple(
            replace(
                value,
                model_name=(
                    source_settings.model_name
                    if preserve_model and source_settings is not None
                    else value.model_name
                ),
                loras=(
                    source_settings.loras
                    if preserve_loras and source_settings is not None
                    else value.loras
                ),
            )
            for value in settings
        )
        if explore_models:
            model_names = self._exploratory_model_names(
                project.memory_profile_id,
                len(normalized_settings),
                fallback=tuple(value.model_name for value in normalized_settings),
                first_model=normalized_settings[0].model_name,
            )
            normalized_settings = tuple(
                replace(value, model_name=model_name)
                for value, model_name in zip(normalized_settings, model_names, strict=True)
            )
        chosen_model = _text(model_id or project.initial_model_id, "model_id", 300)
        round_index = 1 + max(
            (value.round_index for value in project.candidates if value.role is role),
            default=0,
        )
        batch_id = self._batch_id()
        candidate_ids = tuple(self._candidate_id() for _ in normalized_settings)
        trace_specs: list[tuple[str, str, str | None]] = []
        if strategy is ProductionV2PromptStrategy.REWRITE_ONCE:
            trace_specs.append(("prompt", "Réécriture du prompt commun", candidate_ids[0]))
        elif strategy is ProductionV2PromptStrategy.EVOLVE_BETWEEN:
            trace_specs.append(("prompt", "Prompt du rendu 1", candidate_ids[0]))
        if assisted_lora_selection:
            trace_specs.append(("lora_plan", "Planification des variantes LoRA", None))
        if strategy is ProductionV2PromptStrategy.EVOLVE_BETWEEN:
            trace_specs.extend(
                ("prompt", f"Prompt du rendu {index + 1}", candidate_ids[index])
                for index in range(1, len(candidate_ids))
            )
        trace_total = len(trace_specs)
        traces = tuple(ProductionV2LlmTrace(
            trace_id=self._trace_id(), batch_id=batch_id,
            sequence=index + 1, total=trace_total,
            purpose=purpose, label=label, model_id=chosen_model,
            status=ProductionV2LlmTraceStatus.PENDING, created_at=_timestamp(),
            candidate_id=candidate_id,
        ) for index, (purpose, label, candidate_id) in enumerate(trace_specs))
        trace_by_candidate = {
            value.candidate_id: value.trace_id
            for value in traces
            if value.purpose == "prompt" and value.candidate_id is not None
        }
        pending = tuple(ProductionV2Candidate(
            candidate_id=candidate_id,
            index=len(project.candidates) + offset + 1,
            round_index=round_index,
            role=role,
            memory_profile_id=project.memory_profile_id,
            requested_model_id=chosen_model,
            actual_model_id=(
                source_candidate.actual_model_id
                if strategy is ProductionV2PromptStrategy.PRESERVE_CURRENT
                and source_candidate is not None
                else None
            ),
            settings=value,
            status=(
                ProductionV2CandidateStatus.PROMPTING
                if trace_total
                else ProductionV2CandidateStatus.RENDERING
            ),
            generation_kind=(
                ProductionV2CandidateKind.TECHNICAL_LORA
                if assisted_lora_selection
                else ProductionV2CandidateKind.CREATIVE
            ),
            feedback_parent_id=feedback_parent_id,
            instruction=instruction.strip()[:8_000],
            batch_id=batch_id,
            prompt_strategy=strategy,
            reference_mode=reference_mode,
            guidance_candidate_id=(
                guidance_candidate_id
                if reference_mode is ProductionV2ReferenceMode.RECIPE_AND_GUIDANCE
                else None
            ),
            preserve_seed=keep_seed,
            preserve_model=bool(preserve_model),
            preserve_loras=bool(preserve_loras),
            prompt_trace_id=trace_by_candidate.get(candidate_id),
        ) for offset, (candidate_id, value) in enumerate(zip(candidate_ids, normalized_settings, strict=True)))
        operation_id = self._operation_id()
        project = replace(
            project,
            candidates=(*project.candidates, *pending),
            llm_traces=(*project.llm_traces, *traces),
            active_llm_trace_id=None,
            status=ProductionV2Status.BUSY,
            active_operation="krea2_candidates",
            active_operation_id=operation_id,
            error=None,
        )
        project = self.store.save_project(self._event(
            project,
            f"Batch KREA2 {round_index} lancé: {len(pending)} candidat(s), rôle {role.value}"
            + f" · stratégie {strategy.value} · {trace_total} appel(s) LLM"
            + (" · checkpoints aléatoires équilibrés" if explore_models else "")
            + (" · LoRA assistées." if assisted_lora_selection else "."),
        ))
        Thread(
            target=self._run_candidates,
            args=(
                project_id, tuple(value.candidate_id for value in pending), instruction,
                strategy, keep_seed, assisted_lora_selection,
                lora_instruction.strip()[:4_000], source_prompt, source_seed,
                operation_id,
            ),
            daemon=True,
        ).start()
        return project

    def _exploratory_model_names(
        self,
        profile_id: str,
        count: int,
        *,
        fallback: tuple[str, ...],
        first_model: str | None = None,
    ) -> tuple[str, ...]:
        try:
            resources = tuple(self.krea2.resources.list_models())
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            resources = ()
        all_names = _unique_model_names(
            getattr(resource, "comfy_name", "") for resource in resources
        )
        bf16_names = _unique_model_names(
            getattr(resource, "comfy_name", "")
            for resource in resources
            if _is_bf16_model(resource)
        )
        pool = bf16_names or all_names or _unique_model_names(fallback)
        if not pool:
            raise ValueError("no KREA2 checkpoint is available for model exploration")
        usage: dict[str, int] = {}
        for prior_project in self.store.list_projects(limit=10_000):
            for candidate in prior_project.candidates:
                if candidate.memory_profile_id != profile_id:
                    continue
                key = _normalized_model_name(candidate.settings.model_name)
                usage[key] = usage.get(key, 0) + 1
        fixed_values = _unique_model_names((first_model,)) if first_model else ()
        fixed = fixed_values[0] if fixed_values else None
        if fixed is None or count < 1:
            return _weighted_model_sample(pool, usage, count)
        alternatives = tuple(
            name for name in pool
            if _normalized_model_name(name) != _normalized_model_name(fixed)
        )
        if not alternatives:
            return tuple(fixed for _ in range(count))
        return (
            fixed,
            *_weighted_model_sample(alternatives, usage, count - 1),
        )

    def queue_resolution_clone(
        self,
        project_id: str,
        candidate_id: str,
        *,
        megapixels: float = 2.1,
    ) -> ProductionV2Project:
        project = self.store.get_project(project_id)
        self._require_idle(project)
        self._require_worker_released(project_id)
        parent = project.candidate(candidate_id)
        if (
            parent.status is not ProductionV2CandidateStatus.SUCCEEDED
            or parent.prompt is None
            or parent.seed is None
            or parent.child_project_id is None
        ):
            raise ValueError("only a completed rendered candidate can be regenerated")
        target_mp = float(megapixels)
        if not 0.5 <= target_mp <= 4.0:
            raise ValueError("megapixels must be between 0.5 and 4")
        clone = ProductionV2Candidate(
            candidate_id=self._candidate_id(), index=len(project.candidates) + 1,
            round_index=parent.round_index, role=parent.role,
            memory_profile_id=parent.memory_profile_id,
            requested_model_id=parent.requested_model_id,
            actual_model_id=parent.actual_model_id,
            settings=replace(parent.settings, megapixels=target_mp),
            status=ProductionV2CandidateStatus.RENDERING,
            generation_kind=ProductionV2CandidateKind.RESOLUTION_CLONE,
            feedback_parent_id=parent.candidate_id,
            child_project_id=parent.child_project_id,
            prompt=parent.prompt, seed=parent.seed,
            instruction=f"Exact resolution clone of candidate {parent.index}.",
        )
        operation_id = self._operation_id()
        project = replace(
            project, candidates=(*project.candidates, clone),
            status=ProductionV2Status.BUSY,
            active_operation="krea2_resolution_clone",
            active_operation_id=operation_id, error=None,
        )
        project = self.store.save_project(self._event(
            project,
            f"Candidat {parent.index} relancé à {target_mp:g} MP avec prompt, seed et recette identiques.",
        ))
        Thread(
            target=self._run_candidates,
            args=(
                project_id, (clone.candidate_id,), "",
                ProductionV2PromptStrategy.PRESERVE_CURRENT, True,
                False, "", parent.prompt, parent.seed, operation_id,
            ),
            daemon=True,
        ).start()
        return project

    def review_candidate(
        self,
        project_id: str,
        candidate_id: str,
        *,
        preference: ProductionV2Preference,
        comment: str = "",
    ) -> ProductionV2Project:
        project = self.store.get_project(project_id)
        candidate = project.candidate(candidate_id)
        if candidate.status is not ProductionV2CandidateStatus.SUCCEEDED:
            raise ValueError("only a completed candidate can receive feedback")
        candidate = replace(candidate, preference=preference, comment=comment.strip()[:8_000])
        project = self.store.save_project(project.replace_candidate(candidate))
        profile = self.store.get_profile(candidate.memory_profile_id)
        observation = ProductionV2MemoryObservation(
            project_id=project_id,
            candidate_id=candidate_id,
            timestamp=_timestamp(),
            preference=preference,
            comment=candidate.comment,
            prompt=candidate.prompt or "",
            model_id=candidate.actual_model_id or candidate.requested_model_id,
            settings=candidate.settings,
            role=candidate.role,
        )
        self.store.save_profile(profile.with_observation(observation))
        self._record_lora_observation(project, candidate, preference)
        return project

    def validate_visual_recipe(self, project_id: str, candidate_id: str) -> ProductionV2Project:
        project = self.store.get_project(project_id)
        self._require_idle(project)
        candidate = project.candidate(candidate_id)
        if candidate.status is not ProductionV2CandidateStatus.SUCCEEDED:
            raise ValueError("visual recipe must come from a completed candidate")
        revision = ProductionV2VisualRecipeRevision(
            revision_id=self._revision_id(),
            index=len(project.recipe_revisions) + 1,
            created_at=_timestamp(),
            source_candidate_id=candidate_id,
            settings=candidate.settings,
            prompt=candidate.prompt or "",
            seed=candidate.seed,
            asset_id=candidate.output_asset_id,
        )
        invalidated = bool(project.anchors or project.prompt_session_id or project.preview_attempt_ids)
        archived_sessions, archived_h3 = self._archived_video_ids(project)
        project = replace(
            project,
            recipe_revisions=(*project.recipe_revisions, revision),
            active_recipe_revision_id=revision.revision_id,
            anchors=() if invalidated else project.anchors,
            prompt_session_id=None if invalidated else project.prompt_session_id,
            h3_project_id=None if invalidated else project.h3_project_id,
            preview_attempt_ids=() if invalidated else project.preview_attempt_ids,
            selected_preview_attempt_id=None if invalidated else project.selected_preview_attempt_id,
            final_attempt_id=None if invalidated else project.final_attempt_id,
            archived_prompt_session_ids=archived_sessions,
            archived_h3_project_ids=archived_h3,
            stage=ProductionV2Stage.ANCHOR_WORKSHOP,
            status=ProductionV2Status.READY,
            error=None,
        )
        message = (
            f"Base visuelle r{revision.index} validée depuis le candidat {candidate.index}."
            + (" Les ancres et rendus aval ont été invalidés." if invalidated else "")
        )
        return self.store.save_project(self._event(project, message, "warning" if invalidated else "info"))

    def use_candidate_as_direct_reference(
        self,
        project_id: str,
        candidate_id: str,
    ) -> ProductionV2Project:
        project = self.validate_visual_recipe(project_id, candidate_id)
        return self.promote_anchor(
            project.project_id,
            role=ProductionV2AnchorRole.REFERENCE,
            candidate_id=candidate_id,
        )

    def unlock_visual_recipe(self, project_id: str) -> ProductionV2Project:
        project = self.store.get_project(project_id)
        self._require_idle(project)
        archived_sessions, archived_h3 = self._archived_video_ids(project)
        project = replace(
            project,
            active_recipe_revision_id=None,
            anchors=(), prompt_session_id=None, h3_project_id=None,
            preview_attempt_ids=(), selected_preview_attempt_id=None, final_attempt_id=None,
            stage=ProductionV2Stage.IMAGE_CALIBRATION,
            archived_prompt_session_ids=archived_sessions,
            archived_h3_project_ids=archived_h3,
        )
        return self.store.save_project(self._event(
            project,
            "Base active retirée; les étapes aval ont été invalidées, l’historique est conservé.",
            "warning",
        ))

    def promote_anchor(
        self,
        project_id: str,
        *,
        role: ProductionV2AnchorRole,
        candidate_id: str | None = None,
        use_source: bool = False,
    ) -> ProductionV2Project:
        if role not in {
            ProductionV2AnchorRole.FIRST_FRAME,
            ProductionV2AnchorRole.LAST_FRAME,
            ProductionV2AnchorRole.REFERENCE,
        }:
            raise ValueError("calibration candidates cannot be promoted as calibration anchors")
        project = self.store.get_project(project_id)
        self._require_idle(project)
        if project.active_recipe is None:
            raise ValueError("validate a visual recipe before promoting anchors")
        if use_source == (candidate_id is not None):
            raise ValueError("choose either the immutable source or one candidate")
        has_references = any(value.role is ProductionV2AnchorRole.REFERENCE for value in project.anchors)
        has_frames = any(value.role in {
            ProductionV2AnchorRole.FIRST_FRAME, ProductionV2AnchorRole.LAST_FRAME,
        } for value in project.anchors)
        if role is ProductionV2AnchorRole.REFERENCE and has_frames:
            raise ValueError("remove first/last anchors before choosing the Ref2V route")
        if role in {ProductionV2AnchorRole.FIRST_FRAME, ProductionV2AnchorRole.LAST_FRAME} and has_references:
            raise ValueError("remove Ref2V references before choosing the H3 Base route")
        if use_source:
            asset_id, label, source_kind = project.source_asset_id, project.source_filename, "source"
            selected_candidate_id = None
        else:
            candidate = project.candidate(candidate_id or "")
            if candidate.status is not ProductionV2CandidateStatus.SUCCEEDED or candidate.output_asset_id is None:
                raise ValueError("anchor candidate must be completed")
            asset_id = candidate.output_asset_id
            label = f"Candidate {candidate.index} · {candidate.role.value}"
            source_kind = "candidate"
            selected_candidate_id = candidate.candidate_id
        anchors = list(project.anchors)
        if role in {ProductionV2AnchorRole.FIRST_FRAME, ProductionV2AnchorRole.LAST_FRAME}:
            anchors = [value for value in anchors if value.role is not role]
        if role is ProductionV2AnchorRole.REFERENCE and len([
            value for value in anchors if value.role is role
        ]) >= 9:
            raise ValueError("Ref2V accepts at most 9 references")
        if any(value.role is role and value.asset_id == asset_id for value in anchors):
            raise ValueError("this image already has the selected anchor role")
        anchors.append(ProductionV2Anchor(
            anchor_id=f"anchor-{uuid4().hex}", role=role, asset_id=asset_id,
            label=label, source_kind=source_kind, candidate_id=selected_candidate_id,
            recipe_revision_id=project.active_recipe_revision_id, created_at=_timestamp(),
        ))
        invalidated = bool(project.prompt_session_id or project.preview_attempt_ids)
        archived_sessions, archived_h3 = self._archived_video_ids(project)
        project = replace(
            project, anchors=tuple(anchors), prompt_session_id=None, h3_project_id=None,
            preview_attempt_ids=(), selected_preview_attempt_id=None, final_attempt_id=None,
            stage=ProductionV2Stage.VIDEO_PROMPT,
            archived_prompt_session_ids=archived_sessions,
            archived_h3_project_ids=archived_h3,
        )
        return self.store.save_project(self._event(
            project,
            f"{label} promu comme {role.value}; route détectée {project.route.value.upper()}."
            + (" Les rendus vidéo aval ont été invalidés." if invalidated else ""),
            "warning" if invalidated else "info",
        ))

    def remove_anchor(self, project_id: str, anchor_id: str) -> ProductionV2Project:
        project = self.store.get_project(project_id)
        self._require_idle(project)
        anchors = tuple(value for value in project.anchors if value.anchor_id != anchor_id)
        if len(anchors) == len(project.anchors):
            raise KeyError(anchor_id)
        archived_sessions, archived_h3 = self._archived_video_ids(project)
        project = replace(
            project, anchors=anchors, prompt_session_id=None, h3_project_id=None,
            preview_attempt_ids=(), selected_preview_attempt_id=None, final_attempt_id=None,
            stage=ProductionV2Stage.ANCHOR_WORKSHOP if not anchors else ProductionV2Stage.VIDEO_PROMPT,
            archived_prompt_session_ids=archived_sessions,
            archived_h3_project_ids=archived_h3,
        )
        return self.store.save_project(self._event(
            project, "Ancre retirée; les étapes vidéo aval ont été invalidées.", "warning"
        ))

    def configure_video(
        self,
        project_id: str,
        *,
        video_intention: str,
        aspect_ratio: VideoAspectRatio,
        duration_seconds: float,
        preview_megapixels: float,
        final_megapixels: float,
        steps: int,
        seed_locked: bool,
        spectrum_enabled: bool,
        music_enabled: bool,
        video_lora: H3VideoLoraSelection | None,
        compile_model_id: str | None = None,
        creative_audacity: int = 3,
        revision_audacity: int = 3,
        invalidate_compilation: bool = False,
    ) -> ProductionV2Project:
        project = self.store.get_project(project_id)
        self._require_idle(project)
        intention = _text(video_intention, "video_intention", 20_000)
        if not isinstance(aspect_ratio, VideoAspectRatio):
            raise TypeError("aspect_ratio must be a VideoAspectRatio")
        if not isinstance(video_lora, (H3VideoLoraSelection, type(None))):
            raise TypeError("video_lora must be an H3VideoLoraSelection or None")
        compile_model = _text(
            compile_model_id or project.effective_video_compile_model_id,
            "compile_model_id",
            300,
        )
        creative_audacity = _audacity(creative_audacity, "creative_audacity")
        revision_audacity = _audacity(revision_audacity, "revision_audacity")
        seed = project.video_seed or 0
        for megapixels in (preview_megapixels, final_megapixels):
            VideoLabSettings(
                aspect_ratio=aspect_ratio, megapixels=float(megapixels),
                duration_seconds=float(duration_seconds), steps=int(steps),
                seed=seed, seed_locked=bool(seed_locked),
            )
        duration_changed = float(duration_seconds) != project.duration_seconds
        compilation_changed = (
            intention != project.effective_video_intention
            or aspect_ratio != project.effective_video_aspect_ratio
            or creative_audacity != project.creative_audacity
            or compile_model != project.effective_video_compile_model_id
        )
        if project.h3_project_id is not None and compilation_changed and not invalidate_compilation:
            raise ValueError("intention, ratio, duration, audacity or compilation model changed; recompile Brief → Plan → Prompt")
        archived_sessions, archived_h3 = self._archived_video_ids(project)
        invalidate = bool(
            project.h3_project_id is not None
            and (
                compilation_changed
                or (duration_changed and invalidate_compilation)
            )
        )
        project = replace(
            project,
            video_intention=intention,
            video_aspect_ratio=aspect_ratio,
            duration_seconds=float(duration_seconds),
            preview_megapixels=float(preview_megapixels),
            final_megapixels=float(final_megapixels),
            video_steps=int(steps),
            video_seed_locked=bool(seed_locked),
            spectrum_enabled=bool(spectrum_enabled),
            music_enabled=bool(music_enabled),
            video_lora=video_lora,
            video_compile_model_id=compile_model,
            creative_audacity=creative_audacity,
            revision_audacity=revision_audacity,
            prompt_session_id=None if invalidate else project.prompt_session_id,
            h3_project_id=None if invalidate else project.h3_project_id,
            preview_attempt_ids=() if invalidate else project.preview_attempt_ids,
            selected_preview_attempt_id=None if invalidate else project.selected_preview_attempt_id,
            final_attempt_id=None if invalidate else project.final_attempt_id,
            archived_prompt_session_ids=archived_sessions if invalidate else project.archived_prompt_session_ids,
            archived_h3_project_ids=archived_h3 if invalidate else project.archived_h3_project_ids,
            stage=ProductionV2Stage.VIDEO_PROMPT if invalidate else project.stage,
        )
        duration_warning = self.video_duration_warning(project)
        return self.store.save_project(self._event(
            project,
            "Réglages vidéo enregistrés."
            + (" La compilation précédente a été archivée." if invalidate else "")
            + (f" {duration_warning}" if duration_warning else ""),
            "warning" if invalidate or duration_warning else "info",
        ))

    def video_duration_warning(
        self,
        project: ProductionV2Project,
    ) -> str | None:
        if project.h3_project_id is None:
            return None
        try:
            prompt = self.h3_render.get(project.h3_project_id).current_prompt
        except (AttributeError, KeyError, FileNotFoundError, StopIteration, ValueError):
            return None
        return h3_prompt_duration_warning(prompt, project.duration_seconds)

    def regenerate_video_seed(self, project_id: str) -> ProductionV2Project:
        project = self.store.get_project(project_id)
        self._require_idle(project)
        project = replace(project, video_seed=self.h3_render.new_seed())
        return self.store.save_project(self._event(project, "Nouvelle seed vidéo créée."))

    def queue_video_compile(
        self,
        project_id: str,
        *,
        render_preview: bool = False,
    ) -> ProductionV2Project:
        project = self.store.get_project(project_id)
        self._require_idle(project)
        self._require_worker_released(project_id)
        if project.route is ProductionV2Route.PENDING:
            raise ValueError("promote at least one first, last or reference image")
        archived_sessions, archived_h3 = self._archived_video_ids(project)
        recompiling = project.h3_project_id is not None
        operation_id = self._operation_id()
        trace_batch_id = self._batch_id()
        project = replace(
            project, status=ProductionV2Status.BUSY, stage=ProductionV2Stage.VIDEO_PROMPT,
            active_operation="h3_compile_preview" if render_preview else "h3_compile", error=None,
            active_operation_id=operation_id,
            prompt_session_id=None if recompiling else project.prompt_session_id,
            h3_project_id=None if recompiling else project.h3_project_id,
            preview_attempt_ids=() if recompiling else project.preview_attempt_ids,
            selected_preview_attempt_id=None if recompiling else project.selected_preview_attempt_id,
            final_attempt_id=None if recompiling else project.final_attempt_id,
            archived_prompt_session_ids=archived_sessions if recompiling else project.archived_prompt_session_ids,
            archived_h3_project_ids=archived_h3 if recompiling else project.archived_h3_project_ids,
        )
        project = self.store.save_project(self._event(
            project,
            f"{'Recompilation' if recompiling else 'Compilation'} {project.route.value.upper()} lancée "
            f"avec {project.effective_video_compile_model_id}: Brief → Plan → Prompt final"
            + (f" → preview {project.preview_megapixels:g} MP." if render_preview else "."),
        ))
        Thread(
            target=self._run_video_compile,
            args=(project_id, render_preview, operation_id, trace_batch_id),
            daemon=True,
        ).start()
        return project

    def queue_preview(
        self,
        project_id: str,
        *,
        instruction: str = "",
        model_id: str | None = None,
        feedback_attempt_id: str | None = None,
        revision_audacity: int | None = None,
    ) -> ProductionV2Project:
        project = self.store.get_project(project_id)
        self._require_idle(project)
        self._require_worker_released(project_id)
        if project.h3_project_id is None:
            raise ValueError("compile the video prompt before rendering a preview")
        audacity = _audacity(
            project.revision_audacity if revision_audacity is None else revision_audacity,
            "revision_audacity",
        )
        if instruction.strip() and feedback_attempt_id is None and project.preview_attempt_ids:
            feedback_attempt_id = project.selected_preview_attempt_id or project.preview_attempt_ids[-1]
        operation_id = self._operation_id()
        project = replace(
            project, status=ProductionV2Status.BUSY, stage=ProductionV2Stage.VIDEO_PREVIEW,
            active_operation="h3_preview", active_operation_id=operation_id,
            error=None, revision_audacity=audacity,
        )
        project = self.store.save_project(self._event(
            project,
            f"Révision vidéo en un appel puis preview {project.preview_megapixels:g} MP." if instruction.strip()
            else (
                f"Preview {project.preview_megapixels:g} MP · {project.duration_seconds:g} s · "
                f"{project.video_steps} + 3 steps · Spectrum {'ON' if project.spectrum_enabled else 'OFF'}."
            ),
        ))
        Thread(
            target=self._run_preview,
            args=(
                project_id, instruction.strip(), model_id, feedback_attempt_id,
                audacity, operation_id,
            ),
            daemon=True,
        ).start()
        return project

    def queue_video_revision(
        self,
        project_id: str,
        *,
        instruction: str,
        model_id: str | None = None,
        feedback_attempt_id: str | None = None,
        revision_audacity: int | None = None,
        repair_rejected: bool = False,
    ) -> ProductionV2Project:
        project = self.store.get_project(project_id)
        self._require_idle(project)
        self._require_worker_released(project_id)
        if project.h3_project_id is None:
            raise ValueError("compile the video prompt before starting the video chat")
        message = (
            "Corrige la structure de la dernière proposition refusée sans changer mon intention."
            if repair_rejected
            else _text(instruction, "video revision message", 20_000)
        )
        audacity = _audacity(
            project.revision_audacity if revision_audacity is None else revision_audacity,
            "revision_audacity",
        )
        if feedback_attempt_id is None and project.preview_attempt_ids:
            feedback_attempt_id = project.selected_preview_attempt_id or project.preview_attempt_ids[-1]
        operation_id = self._operation_id()
        project = replace(
            project, status=ProductionV2Status.BUSY,
            stage=ProductionV2Stage.VIDEO_PREVIEW,
            active_operation="h3_revision", active_operation_id=operation_id,
            error=None, revision_audacity=audacity,
        )
        audacity_label = "standard historique" if audacity == 0 else f"audace {audacity}/3"
        project = self.store.save_project(self._event(
            project,
            (
                "Correction explicite du brouillon refusé envoyée au chat H3 · "
                f"{audacity_label}; 1 appel LLM, aucun rendu automatique."
                if repair_rejected else
                f"Message envoyé au chat H3 · {audacity_label}; aucun rendu ne sera lancé automatiquement."
            ),
        ))
        Thread(
            target=self._run_video_revision,
            args=(
                project_id, message, model_id, feedback_attempt_id, audacity,
                repair_rejected, operation_id,
            ),
            daemon=True,
        ).start()
        return project

    def select_preview(self, project_id: str, attempt_id: str) -> ProductionV2Project:
        project = self.store.get_project(project_id)
        if attempt_id not in project.preview_attempt_ids:
            raise ValueError("preview attempt does not belong to this project")
        attempt = self.h3_render.get(project.h3_project_id).attempt(attempt_id)
        if attempt.status is not H3RenderAttemptStatus.SUCCEEDED:
            raise ValueError("only a completed preview can be selected")
        return self.store.save_project(replace(project, selected_preview_attempt_id=attempt_id))

    def queue_final(self, project_id: str, attempt_id: str | None = None) -> ProductionV2Project:
        project = self.store.get_project(project_id)
        self._require_idle(project)
        self._require_worker_released(project_id)
        selected = attempt_id or project.selected_preview_attempt_id
        if selected is None or selected not in project.preview_attempt_ids:
            raise ValueError("select a completed preview before the final render")
        operation_id = self._operation_id()
        project = replace(
            project, selected_preview_attempt_id=selected, status=ProductionV2Status.BUSY,
            active_operation="h3_final", active_operation_id=operation_id, error=None,
        )
        project = self.store.save_project(self._event(
            project,
            f"Rendu final {project.final_megapixels:g} MP demandé explicitement par l’utilisateur.",
        ))
        Thread(target=self._run_final, args=(project_id, operation_id), daemon=True).start()
        return project

    def cancel(self, project_id: str) -> ProductionV2Project:
        project = self.store.get_project(project_id)
        if project.status is not ProductionV2Status.BUSY:
            return project
        operation_id = project.active_operation_id
        if project.active_operation in {"krea2_candidates", "krea2_resolution_clone"} and project.active_child_project_id and project.active_child_attempt_id:
            self.krea2.cancel_attempt(project.active_child_project_id, project.active_child_attempt_id)
        if project.active_operation in {"h3_preview", "h3_final"} and project.h3_project_id and project.active_child_attempt_id:
            self.h3_render.cancel_attempt(project.h3_project_id, project.active_child_attempt_id)
        with self._lock:
            project = self.store.get_project(project_id)
            if (
                project.status is not ProductionV2Status.BUSY
                or project.active_operation_id != operation_id
            ):
                return project
            candidates = tuple(
                replace(value, status=ProductionV2CandidateStatus.CANCELLED)
                if value.status in {
                    ProductionV2CandidateStatus.PROMPTING,
                    ProductionV2CandidateStatus.RENDERING,
                } else value
                for value in project.candidates
            )
            traces = tuple(
                replace(
                    value, status=ProductionV2LlmTraceStatus.CANCELLED,
                    completed_at=_timestamp(), error="Arrêt demandé par l’utilisateur.",
                )
                if value.status in {
                    ProductionV2LlmTraceStatus.PENDING,
                    ProductionV2LlmTraceStatus.THINKING,
                } else value
                for value in project.llm_traces
            )
            project = replace(
                project, status=ProductionV2Status.CANCELLED, active_operation=None,
                active_operation_id=None,
                active_child_project_id=None, active_child_attempt_id=None,
                active_llm_trace_id=None, candidates=candidates, llm_traces=traces,
            )
            return self.store.save_project(self._event(
                project, "Arrêt demandé; aucun traitement aval ne sera lancé.", "warning"
            ))

    def _run_candidates(
        self,
        project_id: str,
        candidate_ids: tuple[str, ...],
        instruction: str,
        prompt_strategy: ProductionV2PromptStrategy,
        preserve_seed: bool,
        assisted_lora_selection: bool,
        lora_instruction: str,
        source_prompt: str | None,
        source_seed: int | None,
        operation_id: str,
    ) -> None:
        if not self._claim(project_id, operation_id):
            return
        try:
            self._ensure_current_operation(project_id, operation_id)
            initial = self.store.get_project(project_id)
            candidates = [initial.candidate(value) for value in candidate_ids]
            if all(
                value.generation_kind is ProductionV2CandidateKind.RESOLUTION_CLONE
                for value in candidates
            ):
                for candidate in candidates:
                    self._render_candidate(
                        project_id, candidate.candidate_id,
                        candidate.prompt or "", candidate.seed, operation_id,
                    )
            elif prompt_strategy is ProductionV2PromptStrategy.PRESERVE_CURRENT:
                assert source_prompt is not None
                self._assign_shared_prompt(
                    project_id, candidate_ids, source_prompt,
                    candidates[0].actual_model_id or candidates[0].requested_model_id,
                    operation_id,
                )
                if assisted_lora_selection:
                    self._apply_assisted_lora_variants(
                        project_id, candidate_ids, lora_instruction, source_prompt,
                        operation_id,
                    )
                for candidate_id in candidate_ids:
                    if self._cancelled(project_id, operation_id):
                        return
                    self._render_candidate(
                        project_id, candidate_id, source_prompt,
                        source_seed if preserve_seed else None, operation_id,
                    )
            elif prompt_strategy is ProductionV2PromptStrategy.REWRITE_ONCE:
                prompt, actual_model = self._prepare_candidate_prompt(
                    project_id, candidate_ids[0], instruction, operation_id,
                )
                self._assign_shared_prompt(
                    project_id, candidate_ids, prompt, actual_model, operation_id,
                )
                if assisted_lora_selection:
                    self._apply_assisted_lora_variants(
                        project_id, candidate_ids, lora_instruction, prompt,
                        operation_id,
                    )
                for candidate_id in candidate_ids:
                    if self._cancelled(project_id, operation_id):
                        return
                    self._render_candidate(
                        project_id, candidate_id, prompt,
                        source_seed if preserve_seed else None, operation_id,
                    )
            else:
                previous_id: str | None = None
                for index, candidate_id in enumerate(candidate_ids):
                    if self._cancelled(project_id, operation_id):
                        return
                    if previous_id is not None:
                        project = self.store.get_project(project_id)
                        candidate = replace(
                            project.candidate(candidate_id),
                            feedback_parent_id=previous_id,
                            guidance_candidate_id=previous_id,
                        )
                        self._ensure_current_operation(project_id, operation_id)
                        self._save_current(
                            project.replace_candidate(candidate), operation_id,
                        )
                    prompt, _ = self._prepare_candidate_prompt(
                        project_id, candidate_id, instruction, operation_id,
                    )
                    if index == 0 and assisted_lora_selection:
                        self._apply_assisted_lora_variants(
                            project_id, candidate_ids, lora_instruction, prompt,
                            operation_id,
                        )
                    self._render_candidate(
                        project_id, candidate_id, prompt,
                        source_seed if preserve_seed else None, operation_id,
                    )
                    previous_id = candidate_id
            self._ensure_current_operation(project_id, operation_id)
            project = self.store.get_project(project_id)
            if not self._cancelled(project_id, operation_id):
                project = replace(
                    project, status=ProductionV2Status.READY, active_operation=None,
                    active_operation_id=None,
                    active_child_project_id=None, active_child_attempt_id=None, error=None,
                    active_llm_trace_id=None,
                )
                self._save_current(
                    self._event(project, "Batch KREA2 terminé; choix humain attendu."),
                    operation_id,
                )
        except _OperationCancelled:
            return
        except Exception as error:
            self._fail(project_id, error, operation_id)
        finally:
            self._release(project_id, operation_id)

    def _assign_shared_prompt(
        self,
        project_id: str,
        candidate_ids: tuple[str, ...],
        prompt: str,
        actual_model: str,
        operation_id: str,
    ) -> None:
        self._ensure_current_operation(project_id, operation_id)
        project = self.store.get_project(project_id)
        for candidate_id in candidate_ids:
            candidate = replace(
                project.candidate(candidate_id), prompt=prompt,
                actual_model_id=actual_model,
                status=ProductionV2CandidateStatus.RENDERING,
            )
            project = project.replace_candidate(candidate)
        self._save_current(project, operation_id)

    def _prepare_candidate_prompt(
        self,
        project_id: str,
        candidate_id: str,
        instruction: str,
        operation_id: str,
    ) -> tuple[str, str]:
        self._ensure_current_operation(project_id, operation_id)
        project = self.store.get_project(project_id)
        candidate = project.candidate(candidate_id)
        parent = project.candidate(candidate.feedback_parent_id) if candidate.feedback_parent_id else None
        child_project_id = self._ensure_candidate_child(
            project_id, candidate_id, operation_id,
        )
        project = self.store.get_project(project_id)
        candidate = project.candidate(candidate_id)
        guidance_asset_id = None
        if candidate.guidance_candidate_id is not None:
            guidance = project.candidate(candidate.guidance_candidate_id)
            guidance_asset_id = guidance.output_asset_id
        message = self._candidate_message(project, candidate, instruction, parent)
        reference_asset_id, _ = self._candidate_reference(project, candidate)
        references = tuple(dict.fromkeys(
            value for value in (reference_asset_id, guidance_asset_id) if value is not None
        ))
        trace_id = candidate.prompt_trace_id
        if trace_id is not None:
            self._begin_trace(
                project_id, trace_id, message, references, operation_id,
            )
        terminal = None
        raw_output = ""
        thinking: list[str] = []
        try:
            for event in self.krea2.stream_chat(
                child_project_id,
                message,
                guidance_asset_id=guidance_asset_id,
                guidance_filename="selected-visual-guidance.png" if guidance_asset_id else None,
                model_id=candidate.requested_model_id,
                include_reasoning=True,
            ):
                kind = getattr(event, "kind", None)
                if kind == StreamEventKind.REASONING:
                    thinking.append(getattr(event, "text", ""))
                if kind == StreamEventKind.COMPLETED:
                    raw_output = getattr(event, "text", "") or raw_output
                if getattr(event, "project", None) is not None:
                    terminal = event.project
                if getattr(event, "error", None):
                    raise ValueError(event.error)
            if terminal is None or terminal.current_prompt is None:
                raise ValueError("KREA2 candidate prompt generation returned no prompt")
            self._ensure_current_operation(project_id, operation_id)
            prompt = terminal.current_prompt
            actual_model = next(
                (turn.model_id for turn in reversed(terminal.turns) if turn.model_id),
                candidate.requested_model_id,
            )
            project = self.store.get_project(project_id)
            candidate = replace(
                project.candidate(candidate_id), prompt=prompt,
                actual_model_id=actual_model,
                status=ProductionV2CandidateStatus.RENDERING,
            )
            self._save_current(project.replace_candidate(candidate), operation_id)
            if trace_id is not None:
                self._complete_trace(
                    project_id, trace_id,
                    thinking="".join(thinking), output=raw_output or prompt,
                    model_id=actual_model, operation_id=operation_id,
                )
            return prompt, actual_model
        except _OperationCancelled:
            raise
        except Exception as error:
            if trace_id is not None:
                self._fail_trace(
                    project_id, trace_id, error, "".join(thinking), raw_output,
                    operation_id=operation_id,
                )
            raise

    def _render_candidate(
        self,
        project_id: str,
        candidate_id: str,
        prompt: str,
        forced_seed: int | None,
        operation_id: str,
    ) -> None:
        self._ensure_current_operation(project_id, operation_id)
        project = self.store.get_project(project_id)
        candidate = project.candidate(candidate_id)
        child_project_id = self._ensure_candidate_child(
            project_id, candidate_id, operation_id,
        )
        project = self.store.get_project(project_id)
        candidate = replace(
            project.candidate(candidate_id), prompt=prompt,
            status=ProductionV2CandidateStatus.RENDERING,
        )
        project = self._save_current(
            project.replace_candidate(candidate), operation_id,
        )
        self._assert_remote_temperature(project, operation_id)
        child = self.krea2.prepare_attempt(
            child_project_id, prompt=prompt, settings=candidate.settings,
            **({"seed": forced_seed} if forced_seed is not None else {}),
        )
        self._ensure_current_operation(project_id, operation_id)
        attempt = child.attempts[-1]
        candidate = replace(candidate, child_attempt_id=attempt.attempt_id, seed=attempt.seed)
        project = self.store.get_project(project_id).replace_candidate(candidate)
        project = replace(project, active_child_attempt_id=attempt.attempt_id)
        self._save_current(project, operation_id)
        self.krea2.queue_attempt(child_project_id, attempt.attempt_id)
        result = self.krea2.execute_attempt(child_project_id, attempt.attempt_id)
        self._ensure_current_operation(project_id, operation_id)
        attempt = result.attempt(attempt.attempt_id)
        project = self.store.get_project(project_id)
        if attempt.status is Krea2AssistedAttemptStatus.SUCCEEDED:
            candidate = replace(
                project.candidate(candidate_id), status=ProductionV2CandidateStatus.SUCCEEDED,
                output_asset_id=attempt.output_asset_id, error=None,
            )
            self._save_current(project.replace_candidate(candidate), operation_id)
            return
        if attempt.status is Krea2AssistedAttemptStatus.CANCELLED:
            candidate = replace(project.candidate(candidate_id), status=ProductionV2CandidateStatus.CANCELLED)
            self._save_current(project.replace_candidate(candidate), operation_id)
            return
        raise RuntimeError(attempt.error or "KREA2 candidate render failed")

    def _ensure_candidate_child(
        self,
        project_id: str,
        candidate_id: str,
        operation_id: str,
    ) -> str:
        self._ensure_current_operation(project_id, operation_id)
        project = self.store.get_project(project_id)
        candidate = project.candidate(candidate_id)
        if candidate.child_project_id is not None:
            return candidate.child_project_id
        reference_asset_id, reference_filename = self._candidate_reference(project, candidate)
        child = self.krea2.create_project(
            name=f"{project.name} · candidat {candidate.index}",
            intention=project.intention,
            model_id=candidate.requested_model_id,
            reference_asset_id=reference_asset_id,
            reference_filename=reference_filename,
        )
        self._ensure_current_operation(project_id, operation_id)
        project = self.store.get_project(project_id)
        candidate = replace(project.candidate(candidate_id), child_project_id=child.project_id)
        project = project.replace_candidate(candidate)
        project = replace(project, active_child_project_id=child.project_id)
        self._save_current(project, operation_id)
        return child.project_id

    @staticmethod
    def _candidate_reference(
        project: ProductionV2Project,
        candidate: ProductionV2Candidate,
    ) -> tuple[str | None, str | None]:
        if candidate.reference_mode is ProductionV2ReferenceMode.NONE:
            return None, None
        recipe = project.active_recipe
        if recipe is not None and recipe.asset_id is not None:
            return recipe.asset_id, f"validated-base-r{recipe.index}.png"
        return project.source_asset_id, project.source_filename

    def _run_video_compile(
        self,
        project_id: str,
        render_preview: bool,
        operation_id: str,
        trace_batch_id: str,
    ) -> None:
        if not self._claim(project_id, operation_id):
            return
        try:
            self._ensure_current_operation(project_id, operation_id)
            project = self.store.get_project(project_id)
            route = project.route
            if route is ProductionV2Route.REF2VA:
                profile_id, version = _REF2V_PROFILE
                anchors = [value for value in project.anchors if value.role is ProductionV2AnchorRole.REFERENCE]
                references = tuple(NewReference(
                    asset_id=value.asset_id, role="subject_reference", label=value.label,
                    uses=(ReferenceUse.SUBJECT,), evidence_policy=ReferenceEvidencePolicy.FULL,
                ) for value in anchors)
            else:
                profile_id, version = _H3_BASE_PROFILE
                anchors = [value for value in project.anchors if value.role in {
                    ProductionV2AnchorRole.FIRST_FRAME, ProductionV2AnchorRole.LAST_FRAME,
                }]
                references = tuple(NewReference(
                    asset_id=value.asset_id, role=value.role.value, label=value.label,
                    uses=((ReferenceUse.FIRST_FRAME,) if value.role is ProductionV2AnchorRole.FIRST_FRAME
                          else (ReferenceUse.LAST_FRAME,)),
                    evidence_policy=ReferenceEvidencePolicy.FULL,
                ) for value in anchors)
            session = self.prompt_lab.create_session(
                model_id=project.effective_video_compile_model_id, profile_id=profile_id,
                profile_version=version,
                brief_variant_id=_CREATIVE_BRIEF[0],
                brief_variant_version=_CREATIVE_BRIEF[1],
                references=references,
            )
            self._ensure_current_operation(project_id, operation_id)
            project = self.store.get_project(project_id)
            project = replace(project, prompt_session_id=session.session_id)
            self._save_current(self._event(
                project,
                f"Brief H3 · direction créative {_CREATIVE_BRIEF[1]} · "
                f"audace {project.creative_audacity}/3 · thinking · tentative 1/2.",
            ), operation_id)
            brief_input = (
                f"Create a {project.duration_seconds:g}-second video. "
                f"{project.effective_video_intention}"
            )
            session = self._retry_traced_stream(
                project_id=project_id,
                batch_id=trace_batch_id,
                purpose="video_brief",
                label="Brief H3",
                model_id=project.effective_video_compile_model_id,
                input_text=brief_input,
                reference_asset_ids=tuple(value.asset_id for value in anchors),
                operation_id=operation_id,
                stream_factory=lambda: self.prompt_lab.stream_structure_brief(
                    session.session_id,
                    brief_input,
                    100,
                    creative_axes=CreativeFreedomAxes(3, 3, 3),
                    creative_audacity=project.creative_audacity,
                    include_reasoning=True,
                ),
                terminal_attribute="session",
                after_stream=lambda _session: self.prompt_lab.approve_brief(session.session_id),
            )
            self._ensure_current_operation(project_id, operation_id)
            project = self.store.get_project(project_id)
            self._save_current(
                self._event(project, "Brief H3 approuvé; génération du Plan JSON."),
                operation_id,
            )
            refs = self.prompt_lab.get_session(session.session_id).references
            bindings = (
                (CookbookBinding("references", tuple(value.reference_id for value in refs)),)
                if route is ProductionV2Route.REF2VA else (
                    CookbookBinding("first_frame", tuple(
                        value.reference_id for value in refs if value.role == "first_frame"
                    )),
                    CookbookBinding("last_frame", tuple(
                        value.reference_id for value in refs if value.role == "last_frame"
                    )),
                )
            )
            self.composition.configure(session.session_id, profile_id, version, bindings)
            self._generate_and_approve(
                project_id, session.session_id, CompositionStage.BEAT_SHEET,
                "Plan JSON H3", operation_id, trace_batch_id,
            )
            self._generate_and_approve(
                project_id, session.session_id, CompositionStage.FINAL_PROMPT,
                "Prompt final H3", operation_id, trace_batch_id,
            )
            h3_project = self.h3_render.get_or_create_from_session(session.session_id)
            self._ensure_current_operation(project_id, operation_id)
            project = self.store.get_project(project_id)
            project = replace(
                project, h3_project_id=h3_project.project_id,
                video_seed=project.video_seed or self.h3_render.new_seed(),
                stage=ProductionV2Stage.VIDEO_PREVIEW,
                status=(ProductionV2Status.BUSY if render_preview else ProductionV2Status.READY),
                active_operation="h3_preview" if render_preview else None,
                active_operation_id=operation_id if render_preview else None,
                error=None,
            )
            self._save_current(self._event(
                project,
                f"Prompt final prêt · {route.value.upper()} · "
                f"{project.effective_video_aspect_ratio.value} · "
                f"{project.duration_seconds:g} s · preview {project.preview_megapixels:g} MP · "
                f"Spectrum {'ON' if project.spectrum_enabled else 'OFF'}"
                + (" · lancement automatique du preview." if render_preview else "."),
            ), operation_id)
            if render_preview:
                self._execute_preview(project_id, operation_id)
        except _OperationCancelled:
            return
        except Exception as error:
            self._fail(project_id, error, operation_id)
        finally:
            self._release(project_id, operation_id)

    def _generate_and_approve(
        self,
        project_id: str,
        session_id: str,
        stage: CompositionStage,
        label: str,
        operation_id: str,
        trace_batch_id: str,
    ) -> None:
        self._ensure_current_operation(project_id, operation_id)
        self._save_current(
            self._event(
                self.store.get_project(project_id),
                f"{label} · thinking · tentative 1/2.",
            ),
            operation_id,
        )
        self._retry_traced_stream(
            project_id=project_id,
            batch_id=trace_batch_id,
            purpose=f"video_{stage.value}",
            label=label,
            model_id=self.store.get_project(project_id).effective_video_compile_model_id,
            input_text=(
                f"Compilation {label} pour la session {session_id}. "
                "Le Brief approuvé et les ancres de la session constituent l’entrée autoritative."
            ),
            reference_asset_ids=tuple(
                value.asset_id for value in self.store.get_project(project_id).anchors
            ),
            operation_id=operation_id,
            stream_factory=lambda: self.composition.stream_generate(
                session_id, stage, include_reasoning=True,
            ),
            terminal_attribute="composition",
            after_stream=lambda _composition: self.composition.approve(session_id, stage),
        )
        self._ensure_current_operation(project_id, operation_id)
        self._save_current(
            self._event(self.store.get_project(project_id), f"{label} approuvé."),
            operation_id,
        )

    def _run_preview(
        self,
        project_id: str,
        instruction: str,
        model_id: str | None,
        feedback_attempt_id: str | None,
        revision_audacity: int,
        operation_id: str,
    ) -> None:
        if not self._claim(project_id, operation_id):
            return
        try:
            self._ensure_current_operation(project_id, operation_id)
            project = self.store.get_project(project_id)
            if instruction:
                self._revise_video_prompt(
                    project_id,
                    instruction,
                    model_id,
                    feedback_attempt_id,
                    revision_audacity,
                    operation_id=operation_id,
                )
            self._execute_preview(project_id, operation_id)
        except _OperationCancelled:
            return
        except Exception as error:
            self._fail(project_id, error, operation_id)
        finally:
            self._release(project_id, operation_id)

    def _execute_preview(self, project_id: str, operation_id: str) -> None:
        self._ensure_current_operation(project_id, operation_id)
        project = self.store.get_project(project_id)
        self._assert_remote_temperature(project, operation_id)
        if not project.video_seed_locked:
            project = replace(project, video_seed=self.h3_render.new_seed())
            self._save_current(project, operation_id)
        h3_project = self.h3_render.get(project.h3_project_id)
        h3_project = self.h3_render.prepare_attempt(
            h3_project.project_id, prompt=h3_project.current_prompt,
            settings=self._video_settings(project, project.preview_megapixels),
            music_enabled=project.music_enabled,
            spectrum_enabled=project.spectrum_enabled,
            **({"video_lora": project.video_lora} if project.video_lora is not None else {}),
        )
        self._ensure_current_operation(project_id, operation_id)
        attempt = h3_project.attempts[-1]
        project = self.store.get_project(project_id)
        project = replace(
            project, preview_attempt_ids=(*project.preview_attempt_ids, attempt.attempt_id),
            selected_preview_attempt_id=attempt.attempt_id,
            active_child_project_id=h3_project.project_id,
            active_child_attempt_id=attempt.attempt_id,
        )
        self._save_current(project, operation_id)
        self.h3_render.queue_attempt(h3_project.project_id, attempt.attempt_id)
        result = self.h3_render.execute_attempt(h3_project.project_id, attempt.attempt_id)
        self._ensure_current_operation(project_id, operation_id)
        attempt = result.attempt(attempt.attempt_id)
        if attempt.status is not H3RenderAttemptStatus.SUCCEEDED:
            raise RuntimeError(attempt.error or "H3 preview render failed")
        project = self.store.get_project(project_id)
        project = replace(
            project, status=ProductionV2Status.READY, active_operation=None,
            active_operation_id=None,
            active_child_project_id=None, active_child_attempt_id=None,
        )
        self._save_current(self._event(
            project,
            f"Preview H3 {attempt.index} terminé; validation humaine attendue.",
        ), operation_id)

    def _run_video_revision(
        self,
        project_id: str,
        instruction: str,
        model_id: str | None,
        feedback_attempt_id: str | None,
        revision_audacity: int,
        repair_rejected: bool,
        operation_id: str,
    ) -> None:
        if not self._claim(project_id, operation_id):
            return
        try:
            self._ensure_current_operation(project_id, operation_id)
            self._revise_video_prompt(
                project_id,
                instruction,
                model_id,
                feedback_attempt_id,
                revision_audacity,
                repair_rejected,
                operation_id,
            )
            self._ensure_current_operation(project_id, operation_id)
            project = self.store.get_project(project_id)
            project = replace(
                project, status=ProductionV2Status.READY, active_operation=None,
                active_operation_id=None, error=None,
            )
            self._save_current(
                self._event(
                    project,
                    "Réponse H3 reçue; le rendu reste à lancer manuellement.",
                ),
                operation_id,
            )
        except _OperationCancelled:
            return
        except Exception as error:
            self._fail(project_id, error, operation_id)
        finally:
            self._release(project_id, operation_id)

    def _revise_video_prompt(
        self,
        project_id: str,
        instruction: str,
        model_id: str | None,
        feedback_attempt_id: str | None,
        revision_audacity: int,
        repair_rejected: bool = False,
        operation_id: str | None = None,
    ) -> None:
        if operation_id is not None:
            self._ensure_current_operation(project_id, operation_id)
        project = self.store.get_project(project_id)
        terminal = None
        for event in self.h3_render.stream_chat(
            project.h3_project_id, instruction,
            feedback_attempt_id=feedback_attempt_id,
            model_id=model_id or project.initial_model_id,
            creative_audacity=None if revision_audacity == 0 else revision_audacity,
            repair_rejected=repair_rejected,
        ):
            if event.project is not None:
                terminal = event.project
            if event.error:
                raise ValueError(event.error)
        if operation_id is not None:
            self._ensure_current_operation(project_id, operation_id)
        if terminal is None:
            raise ValueError("H3 revision returned no prompt")
        audacity_label = (
            "standard historique"
            if revision_audacity == 0
            else f"audace {revision_audacity}/3"
        )
        updated = self._event(
            self.store.get_project(project_id),
            (
                "Structure du brouillon H3 corrigée explicitement en un appel avec "
                f"{model_id or project.initial_model_id} · {audacity_label}."
                if repair_rejected else
                f"Prompt H3 révisé en un appel avec {model_id or project.initial_model_id} · {audacity_label}."
            ),
        )
        if operation_id is None:
            self.store.save_project(updated)
        else:
            self._save_current(updated, operation_id)

    def _run_final(self, project_id: str, operation_id: str) -> None:
        if not self._claim(project_id, operation_id):
            return
        try:
            self._ensure_current_operation(project_id, operation_id)
            project = self.store.get_project(project_id)
            self._assert_remote_temperature(project, operation_id)
            source_project = self.h3_render.get(project.h3_project_id)
            source_attempt = source_project.attempt(project.selected_preview_attempt_id)
            h3_project = self.h3_render.resume_attempt(project.h3_project_id, project.selected_preview_attempt_id)
            h3_project = self.h3_render.prepare_attempt(
                h3_project.project_id, prompt=h3_project.current_prompt,
                settings=replace(source_attempt.settings, megapixels=project.final_megapixels),
                music_enabled=source_attempt.music_enabled,
                spectrum_enabled=source_attempt.spectrum_enabled,
                **({"video_lora": source_attempt.video_lora} if source_attempt.video_lora is not None else {}),
            )
            self._ensure_current_operation(project_id, operation_id)
            attempt = h3_project.attempts[-1]
            project = self.store.get_project(project_id)
            project = replace(
                project, final_attempt_id=attempt.attempt_id,
                active_child_project_id=h3_project.project_id,
                active_child_attempt_id=attempt.attempt_id,
            )
            self._save_current(project, operation_id)
            self.h3_render.queue_attempt(h3_project.project_id, attempt.attempt_id)
            result = self.h3_render.execute_attempt(h3_project.project_id, attempt.attempt_id)
            self._ensure_current_operation(project_id, operation_id)
            attempt = result.attempt(attempt.attempt_id)
            if attempt.status is not H3RenderAttemptStatus.SUCCEEDED:
                raise RuntimeError(attempt.error or "H3 final render failed")
            project = self.store.get_project(project_id)
            project = replace(
                project, stage=ProductionV2Stage.COMPLETE, status=ProductionV2Status.READY,
                active_operation=None, active_operation_id=None,
                active_child_project_id=None, active_child_attempt_id=None,
            )
            self._save_current(self._event(
                project, f"Rendu final {project.final_megapixels:g} MP terminé depuis le snapshot du preview sélectionné."
            ), operation_id)
        except _OperationCancelled:
            return
        except Exception as error:
            self._fail(project_id, error, operation_id)
        finally:
            self._release(project_id, operation_id)

    def _apply_assisted_lora_variants(
        self,
        project_id: str,
        candidate_ids: tuple[str, ...],
        instruction: str,
        prompt: str,
        operation_id: str,
    ) -> None:
        self._ensure_current_operation(project_id, operation_id)
        if self.gateway is None or self.lora_resources is None:
            raise RuntimeError("assisted LoRA exploration is not configured")
        project = self.store.get_project(project_id)
        candidates = [project.candidate(value) for value in candidate_ids]
        if len(candidates) < 2:
            raise ValueError("assisted LoRA exploration requires a baseline and one variant")
        baseline = candidates[0].settings
        manual = tuple(baseline.loras)
        if len(manual) > 10:
            raise ValueError("KREA2 supports at most ten LoRAs")
        pinned = {_normalized_lora_name(value.name) for value in manual}
        resources = tuple(self.lora_resources.list_loras())
        available_by_name = {
            _normalized_lora_name(getattr(value, "comfy_name", "")): value
            for value in resources
            if isinstance(getattr(value, "comfy_name", None), str)
            and getattr(value, "selectable", True)
            and _normalized_lora_name(getattr(value, "comfy_name")) not in pinned
        }
        if not available_by_name:
            raise ValueError("no additional installed KREA2 LoRA is available")
        names = [getattr(value, "comfy_name") for value in available_by_name.values()]
        memory_values = (
            self.lora_memory.context(
                names, observations_per_lora=3,
                profile_id=project.memory_profile_id,
            )
            if self.lora_memory is not None else tuple({"name": name} for name in names)
        )
        catalogue = []
        memory_by_name = {
            _normalized_lora_name(str(value.get("name", ""))): value
            for value in memory_values if isinstance(value, dict)
        }
        for name in names:
            resource = available_by_name[_normalized_lora_name(name)]
            safety = getattr(resource, "safety", None)
            catalogue.append({
                "name": name,
                "filename": getattr(resource, "filename", name),
                "favorite": bool(getattr(resource, "favorite", False)),
                "safety": getattr(safety, "value", str(safety or "unclassified")),
                "category": getattr(
                    getattr(resource, "lora_category", None),
                    "value",
                    "unclassified",
                ),
                "memory": memory_by_name.get(_normalized_lora_name(name), {"name": name}),
            })
        variant_count = len(candidates) - 1
        trace_id = next((
            value.trace_id for value in project.llm_traces
            if value.batch_id == candidates[0].batch_id and value.purpose == "lora_plan"
        ), None)

        request = CompletionRequest(
            model_id=candidates[0].requested_model_id,
            system_prompt=(
                "You plan controlled KREA2 LoRA variants. Use only exact allowlisted names. "
                "The manually selected baseline LoRAs are pinned in every image. Prefer a small "
                "justified addition and make the variants meaningfully different. Every strength "
                "must be between -1 and 1. Return one JSON object only."
            ),
            user_prompt=(
                f"Create exactly {variant_count} LoRA variants for this render batch. "
                f"Each variant may add at most {max(0, 10 - len(manual))} LoRAs. "
                "Return exactly {\"variants\":[{\"additions\":[{\"name\":\"exact allowlisted name\","
                "\"strength\":0.5,\"expected_effect\":\"...\"}],\"rationale\":\"...\"}]}.\n\n"
                f"BATCH CHECKPOINTS IN RENDER ORDER:\n"
                f"{json.dumps([value.settings.model_name for value in candidates], ensure_ascii=False)}\n\n"
                f"REFERENCE PROMPT:\n{prompt}\n\n"
                f"USER LORA CONSTRAINT:\n{instruction or 'No required LoRA; choose only useful controlled variants.'}\n\n"
                f"PINNED MANUAL LORAS:\n{json.dumps([{'name': value.name, 'strength': value.strength} for value in manual], ensure_ascii=False)}\n\n"
                f"AVAILABLE LORAS AND MEMORY:\n{json.dumps(catalogue, ensure_ascii=False)}"
            ),
            temperature=0.1,
            max_tokens=262_144,
            operation_id="production.v2.lora_variants@0.2.0",
            include_reasoning=True,
        )
        if trace_id is not None:
            self._begin_trace(
                project_id, trace_id, request.user_prompt, (), operation_id,
            )

        def completion() -> tuple[dict[str, Any], str, str, str]:
            result, thinking, output = self._complete_gateway(request)
            if getattr(result, "finish_reason", None) == "length":
                raise ValueError(truncated_response_message(262_144))
            return _json_object(result.content), result.model_id, thinking, output

        try:
            payload, actual_model, thinking, raw_output = completion()
            self._ensure_current_operation(project_id, operation_id)
        except _OperationCancelled:
            raise
        except Exception as error:
            if trace_id is not None:
                self._fail_trace(
                    project_id, trace_id, error, operation_id=operation_id,
                )
            raise
        if trace_id is not None:
            self._update_trace_payload(
                project_id, trace_id, thinking=thinking,
                output=raw_output, model_id=actual_model,
                operation_id=operation_id,
            )
        raw_variants = payload.get("variants")
        if not isinstance(raw_variants, list) or len(raw_variants) != variant_count:
            raise ValueError(f"LoRA planner must return exactly {variant_count} variants")
        updated = [replace(candidates[0], status=(
                           ProductionV2CandidateStatus.RENDERING
                           if candidates[0].prompt else ProductionV2CandidateStatus.PROMPTING
                       ),
                           assisted_lora_rationale="Baseline: manually selected LoRAs only.")]
        for candidate, raw_variant in zip(candidates[1:], raw_variants, strict=True):
            if not isinstance(raw_variant, dict):
                raise ValueError("each LoRA variant must be an object")
            raw_additions = raw_variant.get("additions")
            if not isinstance(raw_additions, list) or len(raw_additions) > 10 - len(manual):
                raise ValueError("LoRA variant additions exceed the available slots")
            additions: list[Krea2LoraSelection] = []
            assisted_names: list[str] = []
            seen = set(pinned)
            effects: list[str] = []
            for raw in raw_additions:
                if not isinstance(raw, dict):
                    raise ValueError("each LoRA addition must be an object")
                requested = _text(raw.get("name", ""), "LoRA name", 500)
                normalized = _normalized_lora_name(requested)
                resource = available_by_name.get(normalized)
                if resource is None or normalized in seen:
                    raise ValueError(f"LoRA is duplicated or not allowlisted: {requested}")
                strength = _bounded_strength(raw.get("strength"))
                name = getattr(resource, "comfy_name")
                additions.append(Krea2LoraSelection(name=name, strength=strength))
                assisted_names.append(name)
                effects.append(_text(raw.get("expected_effect", ""), "expected_effect", 2_000))
                seen.add(normalized)
            rationale = _text(raw_variant.get("rationale", ""), "LoRA rationale", 4_000)
            planned = replace(
                candidate,
                settings=replace(candidate.settings, loras=(*manual, *additions)),
                status=(ProductionV2CandidateStatus.RENDERING
                        if candidate.prompt else ProductionV2CandidateStatus.PROMPTING),
                assisted_lora_names=tuple(assisted_names),
                assisted_lora_rationale=rationale,
            )
            updated.append(planned)
            if self.lora_memory is not None and additions:
                plan = ProductionLoraPlan(
                    choices=tuple(ProductionLoraChoice(
                        name=value.name, strength=value.strength,
                        source=ProductionLoraChoiceSource.MODEL,
                        expected_effect=effect,
                    ) for value, effect in zip(additions, effects, strict=True)),
                    rationale=rationale,
                )
                self.lora_memory.record_plan(
                    job_id=f"{project_id}:{candidate.candidate_id}",
                    checkpoint=planned.settings.model_name, plan=plan, timestamp=_timestamp(),
                    profile_id=project.memory_profile_id,
                )
        current = self.store.get_project(project_id)
        self._ensure_current_operation(project_id, operation_id)
        for candidate in updated:
            current = current.replace_candidate(candidate)
        self._save_current(self._event(
            current,
            f"Plan LoRA assisté prêt: une baseline manuelle et {variant_count} variante(s) contrôlée(s).",
        ), operation_id)
        if trace_id is not None:
            self._complete_trace(
                project_id, trace_id, thinking=thinking,
                output=raw_output, model_id=actual_model,
                operation_id=operation_id,
            )

    def _record_lora_observation(
        self,
        project: ProductionV2Project,
        candidate: ProductionV2Candidate,
        preference: ProductionV2Preference,
    ) -> None:
        if self.lora_memory is None or not candidate.settings.loras or candidate.seed is None:
            return
        assisted = {_normalized_lora_name(value) for value in candidate.assisted_lora_names}
        choices = tuple(ProductionLoraChoice(
            name=value.name,
            strength=value.strength,
            source=(ProductionLoraChoiceSource.MODEL
                    if _normalized_lora_name(value.name) in assisted
                    else ProductionLoraChoiceSource.MANUAL),
            expected_effect=(candidate.assisted_lora_rationale or "Human-selected KREA2 LoRA."),
        ) for value in candidate.settings.loras)
        try:
            self.lora_memory.record_observation(
                job_id=project.project_id,
                attempt_id=candidate.candidate_id,
                checkpoint=candidate.settings.model_name,
                prompt=candidate.prompt or "",
                seed=candidate.seed,
                plan=ProductionLoraPlan(
                    choices=choices,
                    rationale=candidate.assisted_lora_rationale or "Human Production V2 feedback.",
                ),
                score=None,
                selection=preference.value,
                timestamp=_timestamp(),
                profile_id=candidate.memory_profile_id,
            )
        except Exception:
            return

    def _candidate_message(
        self,
        project: ProductionV2Project,
        candidate: ProductionV2Candidate,
        instruction: str,
        parent: ProductionV2Candidate | None,
    ) -> str:
        role_guidance = {
            ProductionV2AnchorRole.CALIBRATION: "Explore a compelling still-image direction and do not depict the whole motion already completed.",
            ProductionV2AnchorRole.FIRST_FRAME: "Create the exact calm pre-action starting frame, before the requested video action begins.",
            ProductionV2AnchorRole.LAST_FRAME: "Create the exact final visual state after the requested action, without motion blur.",
            ProductionV2AnchorRole.REFERENCE: "Create a strong reusable subject/style reference image, not a timed video frame.",
        }[candidate.role]
        memory = self._memory_context(candidate.memory_profile_id, candidate.role)
        parent_context = ""
        if parent is not None:
            parent_context = (
                f"\nSelected parent prompt: {parent.prompt or ''}\n"
                f"Human feedback on it: {parent.comment or 'Use it as the visual branch to improve.'}"
            )
        return (
            "Write one production-ready English KREA2 image prompt. The uploaded source is immutable inspiration: "
            "preserve its useful identity and visual facts while applying the requested direction. "
            "When a turn guidance image is attached, use it only as explicitly selected visual context. "
            "Do not inherit wounds, action state, props or temporal outcomes unless the current instruction requests them. "
            f"{role_guidance}\nVideo intention: {project.intention}\n"
            f"Current human instruction: {instruction.strip() or 'Propose a strong coherent visual interpretation.'}"
            f"{parent_context}{memory}"
        )

    def _memory_context(
        self,
        profile_id: str,
        role: ProductionV2AnchorRole,
    ) -> str:
        profile = self.store.get_profile(profile_id)
        useful = [value for value in profile.observations if value.preference is not ProductionV2Preference.NONE][-12:]
        if not useful:
            return f"\nMemory profile: {profile.name}; no prior preferences yet."
        lines = [
            f"\nAesthetic memory profile: {profile.name}. Use these only as global style/resource signals; "
            "never import their depicted scene state:"
        ]
        for item in useful:
            loras = ", ".join(
                f"{value.name} x {value.strength:g}" for value in item.settings.loras
            ) or "none"
            lines.append(
                f"- {item.preference.value.upper()} · checkpoint {item.settings.model_name} · "
                f"LoRAs {loras}"
            )
        role_notes = [
            value for value in profile.observations
            if value.preference is not ProductionV2Preference.NONE
            and value.role is role and value.comment.strip()
        ][-6:]
        if role_notes:
            lines.append(f"Role-local notes for {role.value} only:")
            lines.extend(
                f"- {item.preference.value.upper()} · {item.comment.strip()}"
                for item in role_notes
            )
        return "\n".join(lines)

    @staticmethod
    def _archived_video_ids(project: ProductionV2Project) -> tuple[tuple[str, ...], tuple[str, ...]]:
        sessions = project.archived_prompt_session_ids
        h3_projects = project.archived_h3_project_ids
        if project.prompt_session_id is not None and project.prompt_session_id not in sessions:
            sessions = (*sessions, project.prompt_session_id)
        if project.h3_project_id is not None and project.h3_project_id not in h3_projects:
            h3_projects = (*h3_projects, project.h3_project_id)
        return sessions, h3_projects

    @staticmethod
    def _video_settings(project: ProductionV2Project, megapixels: float) -> VideoLabSettings:
        return VideoLabSettings(
            aspect_ratio=project.effective_video_aspect_ratio, megapixels=megapixels,
            duration_seconds=project.duration_seconds, steps=project.video_steps,
            seed=project.video_seed or 0, seed_locked=project.video_seed_locked,
        )

    def _assert_remote_temperature(
        self,
        project: ProductionV2Project,
        operation_id: str,
    ) -> None:
        if self.thermal_monitor is None:
            return
        snapshot = self.thermal_monitor.snapshot()
        temperature = getattr(snapshot, "remote_temperature_c", None)
        if temperature is None:
            return
        if temperature >= project.stop_temperature_c:
            if not project.remote_thermal_latched:
                self._save_current(
                    replace(
                        project, remote_thermal_latched=True,
                        remote_thermal_latched_at=_timestamp(),
                    ),
                    operation_id,
                )
            raise RuntimeError(
                f"GPU serveur à {temperature:.0f} °C: lancement bloqué au seuil {project.stop_temperature_c:.0f} °C."
            )
        if project.remote_thermal_latched and project.remote_thermal_latched_at:
            started = datetime.fromisoformat(project.remote_thermal_latched_at.replace("Z", "+00:00"))
            elapsed = (datetime.now(UTC) - started).total_seconds()
            if elapsed < project.cooldown_seconds:
                raise RuntimeError(
                    f"Refroidissement serveur: encore {max(1, round(project.cooldown_seconds - elapsed))} s avant reprise."
                )
        if project.remote_thermal_latched and temperature > project.resume_temperature_c:
            raise RuntimeError(
                f"GPU serveur à {temperature:.0f} °C: reprise sous {project.resume_temperature_c:.0f} °C attendue."
            )
        if project.remote_thermal_latched:
            self._save_current(
                replace(
                    project, remote_thermal_latched=False,
                    remote_thermal_latched_at=None,
                ),
                operation_id,
            )

    def _ensure_default_profiles(self) -> None:
        existing = {value.profile_id for value in self.store.list_profiles()}
        for profile_id, name in (("sfw", "SFW"), ("nsfw", "NSFW")):
            if profile_id not in existing:
                self.store.create_profile(ProductionV2MemoryProfile(
                    profile_id=profile_id, name=name, created_at=_timestamp()
                ))

    def _retry_traced_stream(
        self,
        *,
        project_id: str,
        batch_id: str,
        purpose: str,
        label: str,
        model_id: str,
        input_text: str,
        reference_asset_ids: tuple[str, ...],
        operation_id: str,
        stream_factory: Callable[[], Any],
        terminal_attribute: str,
        after_stream: Callable[[Any], Any] | None = None,
    ) -> Any:
        error: Exception | None = None
        for attempt in range(1, 3):
            trace_id = self._append_runtime_trace(
                project_id=project_id,
                batch_id=batch_id,
                purpose=purpose,
                label=f"{label} · tentative {attempt}/2",
                model_id=model_id,
                input_text=input_text,
                reference_asset_ids=reference_asset_ids,
                operation_id=operation_id,
            )
            thinking = ""
            output = ""
            terminal = None
            last_flush = monotonic()
            try:
                for event in stream_factory():
                    self._ensure_current_operation(project_id, operation_id)
                    if event.kind is StreamEventKind.REASONING:
                        thinking += event.text
                    elif event.kind is StreamEventKind.DELTA:
                        output += event.text
                    elif event.kind is StreamEventKind.TRUNCATED:
                        output = event.text or output
                        self._update_trace_payload(
                            project_id, trace_id, thinking=thinking, output=output,
                            model_id=model_id, operation_id=operation_id,
                        )
                        raise ValueError(truncated_response_message(event.max_tokens or 262_144))
                    elif event.kind is StreamEventKind.COMPLETED:
                        output = event.text or output
                        terminal = getattr(event, terminal_attribute, None)
                    now = monotonic()
                    if now - last_flush >= 0.25:
                        self._update_trace_payload(
                            project_id, trace_id, thinking=thinking, output=output,
                            model_id=model_id, operation_id=operation_id,
                        )
                        last_flush = now
                if terminal is None:
                    raise ValueError(f"{label} stream completed without a persisted result")
                if after_stream is not None:
                    after_stream(terminal)
                self._complete_trace(
                    project_id, trace_id, thinking=thinking, output=output,
                    model_id=model_id, operation_id=operation_id,
                )
                return terminal
            except _OperationCancelled:
                raise
            except Exception as current:
                error = current
                self._fail_trace(
                    project_id, trace_id, current, thinking=thinking, output=output,
                    operation_id=operation_id,
                )
        assert error is not None
        raise error

    def _append_runtime_trace(
        self,
        *,
        project_id: str,
        batch_id: str,
        purpose: str,
        label: str,
        model_id: str,
        input_text: str,
        reference_asset_ids: tuple[str, ...],
        operation_id: str,
    ) -> str:
        self._ensure_current_operation(project_id, operation_id)
        project = self.store.get_project(project_id)
        sequence = 1 + sum(value.batch_id == batch_id for value in project.llm_traces)
        previous = tuple(
            replace(value, total=sequence) if value.batch_id == batch_id else value
            for value in project.llm_traces
        )
        trace = ProductionV2LlmTrace(
            trace_id=self._trace_id(), batch_id=batch_id,
            sequence=sequence, total=sequence, purpose=purpose, label=label,
            model_id=model_id, status=ProductionV2LlmTraceStatus.PENDING,
            created_at=_timestamp(),
        )
        self._save_current(replace(project, llm_traces=(*previous, trace)), operation_id)
        self._begin_trace(
            project_id, trace.trace_id, input_text, reference_asset_ids, operation_id,
        )
        return trace.trace_id

    def _retry(self, operation: Callable[[], Any]) -> Any:
        error: Exception | None = None
        for _ in range(2):
            try:
                return operation()
            except _OperationCancelled:
                raise
            except Exception as current:
                error = current
        assert error is not None
        raise error

    def _complete_gateway(self, request: CompletionRequest) -> tuple[Any, str, str]:
        stream = getattr(self.gateway, "stream", None)
        if not callable(stream):
            result = self.gateway.complete(request)
            return result, "", result.content
        thinking: list[str] = []
        output: list[str] = []
        terminal = None
        for event in stream(request):
            if event.kind is StreamEventKind.REASONING:
                thinking.append(event.text)
            elif event.kind is StreamEventKind.DELTA:
                output.append(event.text)
            elif event.kind is StreamEventKind.TRUNCATED:
                raise ValueError(truncated_response_message(request.max_tokens))
            elif event.kind is StreamEventKind.COMPLETED:
                terminal = event.result
        if terminal is None:
            raise ValueError("LLM stream completed without a result")
        return terminal, "".join(thinking), terminal.content or "".join(output)

    def _begin_trace(
        self,
        project_id: str,
        trace_id: str,
        input_text: str,
        reference_asset_ids: tuple[str, ...],
        operation_id: str,
    ) -> None:
        self._ensure_current_operation(project_id, operation_id)
        project = self.store.get_project(project_id)
        trace = replace(
            project.trace(trace_id), status=ProductionV2LlmTraceStatus.THINKING,
            input_text=input_text, reference_asset_ids=reference_asset_ids,
            started_at=_timestamp(), error=None,
        )
        project = project.replace_trace(trace)
        project = replace(project, active_llm_trace_id=trace_id)
        self._save_current(self._event(
            project,
            f"Appel LLM {trace.sequence}/{trace.total} · {trace.label} · "
            f"{trace.model_id} · thinking · {len(reference_asset_ids)} référence(s).",
        ), operation_id)

    def _complete_trace(
        self,
        project_id: str,
        trace_id: str,
        *,
        thinking: str,
        output: str,
        model_id: str,
        operation_id: str,
    ) -> None:
        self._ensure_current_operation(project_id, operation_id)
        project = self.store.get_project(project_id)
        trace = replace(
            project.trace(trace_id), status=ProductionV2LlmTraceStatus.SUCCEEDED,
            thinking=thinking, output=output, model_id=model_id,
            completed_at=_timestamp(), error=None,
        )
        project = project.replace_trace(trace)
        project = replace(
            project,
            active_llm_trace_id=(
                None if project.active_llm_trace_id == trace_id
                else project.active_llm_trace_id
            ),
        )
        self._save_current(self._event(
            project,
            f"Appel LLM {trace.sequence}/{trace.total} · {trace.label} · output enregistré.",
        ), operation_id)

    def _update_trace_payload(
        self,
        project_id: str,
        trace_id: str,
        *,
        thinking: str,
        output: str,
        model_id: str,
        operation_id: str,
    ) -> None:
        self._ensure_current_operation(project_id, operation_id)
        project = self.store.get_project(project_id)
        trace = replace(
            project.trace(trace_id), thinking=thinking,
            output=output, model_id=model_id,
        )
        self._save_current(project.replace_trace(trace), operation_id)

    def _fail_trace(
        self,
        project_id: str,
        trace_id: str,
        error: Exception,
        thinking: str = "",
        output: str = "",
        operation_id: str | None = None,
    ) -> None:
        if operation_id is not None:
            self._ensure_current_operation(project_id, operation_id)
        project = self.store.get_project(project_id)
        trace = replace(
            project.trace(trace_id), status=ProductionV2LlmTraceStatus.FAILED,
            thinking=thinking, output=output,
            error=(str(error).strip() or type(error).__name__), completed_at=_timestamp(),
        )
        project = project.replace_trace(trace)
        project = replace(project, active_llm_trace_id=None)
        updated = self._event(
            project,
            f"Appel LLM {trace.sequence}/{trace.total} · {trace.label} · erreur: {trace.error}",
            "error",
        )
        if operation_id is None:
            self.store.save_project(updated)
        else:
            self._save_current(updated, operation_id)

    def _event(self, project: ProductionV2Project, message: str, level: str = "info") -> ProductionV2Project:
        return replace(project, events=(*project.events, ProductionV2Event(
            event_id=self._event_id(), timestamp=_timestamp(), stage=project.stage,
            level=level, message=message[:4_000],
        )))

    def _fail(self, project_id: str, error: Exception, operation_id: str) -> None:
        project = self.store.get_project(project_id)
        if self._cancelled(project_id, operation_id):
            return
        message = str(error).strip() or type(error).__name__
        candidates = tuple(
            replace(value, status=ProductionV2CandidateStatus.FAILED, error=message[:8_000])
            if value.status in {
                ProductionV2CandidateStatus.PROMPTING,
                ProductionV2CandidateStatus.RENDERING,
            } else value
            for value in project.candidates
        )
        traces = tuple(
            replace(
                value, status=ProductionV2LlmTraceStatus.FAILED,
                error=message[:8_000], completed_at=_timestamp(),
            )
            if value.status in {
                ProductionV2LlmTraceStatus.PENDING,
                ProductionV2LlmTraceStatus.THINKING,
            } else value
            for value in project.llm_traces
        )
        project = replace(
            project, status=ProductionV2Status.FAILED, error=message[:8_000],
            active_operation=None, active_operation_id=None,
            active_child_project_id=None, active_child_attempt_id=None,
            active_llm_trace_id=None, candidates=candidates, llm_traces=traces,
        )
        self._save_current(self._event(project, message, "error"), operation_id)

    @staticmethod
    def _require_idle(project: ProductionV2Project) -> None:
        if project.status is ProductionV2Status.BUSY:
            raise ValueError("another Production V2 operation is active")

    def _require_worker_released(self, project_id: str) -> None:
        with self._lock:
            if project_id in self._claimed:
                raise ValueError(
                    "Annulation en cours : le traitement précédent n’est pas encore arrêté. "
                    "Réessayez dans quelques instants."
                )

    def _save_current(
        self,
        project: ProductionV2Project,
        operation_id: str,
    ) -> ProductionV2Project:
        with self._lock:
            current = self.store.get_project(project.project_id)
            if (
                current.status is not ProductionV2Status.BUSY
                or current.active_operation_id != operation_id
            ):
                raise _OperationCancelled()
            return self.store.save_project(project)

    def _claim(self, project_id: str, operation_id: str) -> bool:
        with self._lock:
            if project_id in self._claimed:
                return False
            project = self.store.get_project(project_id)
            if (
                project.status is not ProductionV2Status.BUSY
                or project.active_operation_id != operation_id
            ):
                return False
            self._claimed[project_id] = operation_id
            return True

    def _release(self, project_id: str, operation_id: str) -> None:
        with self._lock:
            if self._claimed.get(project_id) == operation_id:
                self._claimed.pop(project_id, None)

    def _cancelled(self, project_id: str, operation_id: str) -> bool:
        project = self.store.get_project(project_id)
        return (
            project.status is not ProductionV2Status.BUSY
            or project.active_operation_id != operation_id
        )

    def _ensure_current_operation(self, project_id: str, operation_id: str) -> None:
        if self._cancelled(project_id, operation_id):
            raise _OperationCancelled()


def _text(value: str, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    clean = value.strip()
    if len(clean) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return clean


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


def _normalized_lora_name(value: str) -> str:
    return value.strip().replace("\\", "/").casefold()


def _normalized_model_name(value: str) -> str:
    return value.strip().replace("\\", "/").casefold()


def _unique_model_names(values) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        name = value.strip()
        normalized = _normalized_model_name(name)
        if normalized in seen:
            continue
        seen.add(normalized)
        selected.append(name)
    return tuple(selected)


def _is_bf16_model(resource: object) -> bool:
    precision = getattr(resource, "precision", "")
    precision_value = getattr(precision, "value", precision)
    description = " ".join((
        str(precision_value or ""),
        str(getattr(resource, "comfy_name", "") or ""),
        str(getattr(resource, "filename", "") or ""),
    ))
    return "bf16" in description.casefold()


def _weighted_model_sample(
    names: tuple[str, ...],
    usage: dict[str, int],
    count: int,
    *,
    draw: Callable[[int], int] | None = None,
) -> tuple[str, ...]:
    if not names or count < 1:
        return ()
    picker = draw or secrets.randbelow
    normalized_usage = {
        name: max(0, int(usage.get(_normalized_model_name(name), 0)))
        for name in names
    }
    remaining = list(names)
    selected: list[str] = []
    while len(selected) < count:
        if not remaining:
            remaining = list(names)
        maximum = max(normalized_usage[name] for name in remaining)
        weights = tuple((maximum - normalized_usage[name] + 1) ** 2 for name in remaining)
        ticket = picker(sum(weights))
        cursor = 0
        chosen = remaining[-1]
        for name, weight in zip(remaining, weights, strict=True):
            cursor += weight
            if ticket < cursor:
                chosen = name
                break
        selected.append(chosen)
        normalized_usage[chosen] += 1
        remaining.remove(chosen)
    return tuple(selected)


def _bounded_strength(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("LoRA strength must be a number between -1 and 1")
    strength = float(value)
    if not -1 <= strength <= 1:
        raise ValueError("LoRA strength must be between -1 and 1")
    return strength


def _audacity(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 3:
        raise ValueError(f"{label} must be between 0 and 3")
    return value


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


__all__ = ["ProductionV2Service", "ProductionV2Store"]
