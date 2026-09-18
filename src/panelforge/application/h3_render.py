"""Conversational prompt iteration and Latent Speed rendering for H3 Base."""

from __future__ import annotations

from panelforge.domain.video_preparation import VideoPreparationRef
from .combat_preparation import CombatRevisionPolicy
from .prompt_recipes import PromptRecipeStore
from panelforge.domain.h3_render import h3_upscale_plan, validate_h3_initial_megapixels
from panelforge.domain.h3_bunny import BUNNY_RECIPE_ID, H3BunnySettings, bunny_geometry

from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from panelforge.application.h3_checkpoints import H3CheckpointInventory
from panelforge.domain.h3_render import H3VideoLoraStack, validate_video_lora_stack

from dataclasses import asdict, dataclass, replace
import json
import re
import secrets
from threading import RLock
import time
from typing import Any, Protocol
from uuid import uuid4

from panelforge.domain.assets import Asset
from panelforge.domain.h3_render import (
    H3RenderAttempt,
    H3RenderAttemptStatus,
    H3RenderInputMode,
    H3RenderKeyframe,
    H3RenderProject,
    H3RenderRevisionVersion,
    H3RenderTurn,
    H3RenderTurnRole,
    H3VideoLoraSelection,
    canonical_h3_video_lora_name,
    derive_h3_render_input_mode,
)
from panelforge.domain.prompt_composition import CompositionStage, PromptComposition
from panelforge.domain.prompt_lab import PromptLabSession
from panelforge.domain.minimax_h3 import (
    H3CameraAmplitude,
    H3CameraDirective,
    H3CameraMotion,
    H3CameraSpeed,
)
from panelforge.domain.video_lab import VIDEO_FPS, VideoLabSettings
from panelforge.domain.production import ComputeResource, ProductionWorkload

from .minimax_h3_protocol import (
    H3IssueSeverity,
    H3ProtocolMode,
    compile_camera_motion,
    extract_compiled_camera_clauses,
    lint_h3_prompt,
)
from .production_resources import ResourceWaitCancelled
from .direct_ref2v_prompt import lint_direct_ref2v_prompt
from .vocal_policy import vocal_policy, validate_vocal_level, validate_revision_speech
from .prompt_lab import (
    CompletionRequest,
    ImageInput,
    LlmCallApplicationOutcome,
    LlmCallApplicationOutcomeReporter,
    ModelDescriptor,
    MultimodalGateway,
    StreamEventKind,
    StreamPhase,
    truncated_response_message,
)
from .video_lab import extract_bound_video


_H3_REVISION_SYSTEM_LEGACY = """You are a collaborative MiniMax H3 video prompt editor.
Return raw JSON only, with exactly these fields:
{"message":"concise helpful reply in French","questions":["up to three useful questions"],"prompt":"complete standalone English MiniMax H3 prompt","recommendations":["optional concise advice"]}

The complete prompt is always required and immediately runnable, even when questions remain. Rewrite the CURRENT H3 PROMPT directly; never return a Brief, JSON action plan, patch, diff or commentary inside the prompt. Preserve the exact input-mode reference-alignment header, canonical Picture labels, the three sections integrated_multimodal_description, overall_soundscape and non_diegetic_music, and every explicit quoted dialogue unless the user explicitly asks to change it. Preserve the shot count and cut timestamps unless the user explicitly requests a structural change.

GENERATED KEYFRAMES are visual evidence sampled away from expected cut boundaries. Compare them with the user's goal and the exact render settings. They reveal composition, continuity and visible motion states, but not voice quality, music, sound, fine lip sync or everything occurring between samples. Never claim to have heard the video. Treat the newest user message as authoritative for audiovisual problems that keyframes cannot prove.

Keep H3 prose chronological, physically achievable and concise. Each timed event appears once. Maintain object-state consistency, clean dialogue tags and continuous-motion constraints where requested. Do not introduce labels such as <Image N>, @image or <Subject N>. Do not output Markdown or text outside the JSON."""

_H3_REVISION_SYSTEM_CAMERA_LOCKED = """You are a collaborative MiniMax H3 video prompt editor.
Return raw JSON only, with exactly these fields:
{"message":"concise helpful reply in French","questions":["up to three useful questions"],"prompt":"complete standalone English MiniMax H3 prompt containing the supplied camera tokens","recommendations":["optional concise advice"],"camera_directives":null}

The complete prompt is always required and immediately runnable after application compilation. Rewrite the CURRENT H3 PROMPT directly; never return a Brief, JSON action plan, patch, diff or commentary inside the prompt. Preserve the exact input-mode reference-alignment header, canonical Picture labels, the three sections integrated_multimodal_description, overall_soundscape and non_diegetic_music, and every explicit quoted dialogue unless the user explicitly asks to change it. Preserve the shot count and cut timestamps unless the user explicitly requests a structural change.

Camera tokens such as [[camera:camera_1]] are application-owned. Copy every supplied token exactly once at the same chronological position and write no additional camera-control or lens instructions outside these tokens. Scene composition is allowed in the action prose: say which subjects and surroundings remain visible together at the relevant moment, without adding a camera movement. If a visibility-only correction leaves the compiled movement unchanged, camera_directives may remain null; do not replace a requested slight shake with static_shot merely to keep the scene visible. When the user does not explicitly request a camera change, camera_directives must be null. When changing a directive, return one object per supplied token in the same order with exactly id, start_ms, motion, amplitude, speed and target_clause. Use only the motion enum shown in the CAMERA CONTRACT. Never add or remove a camera token.
camera_directives must always be a JSON array when it is not null, including when there is exactly one camera token. Apply the motion-specific null requirements from the CAMERA CONTRACT before considering a target_clause; its prefix rules only apply when that motion accepts a target.

GENERATED KEYFRAMES are visual evidence sampled away from expected cut boundaries. Compare them with the user's goal and the exact render settings. They reveal composition, continuity and visible motion states, but not voice quality, music, sound, fine lip sync or everything occurring between samples. Never claim to have heard the video. Treat the newest user message as authoritative for audiovisual problems that keyframes cannot prove.

Keep H3 prose chronological, physically achievable and concise. Each timed event appears once. Maintain object-state consistency, clean dialogue tags and continuous-motion constraints where requested. Do not introduce labels such as <Image N>, @image or <Subject N>. Do not output Markdown or text outside the JSON."""

_REF2V_REVISION_SYSTEM = """You are a collaborative MiniMax H3 Ref2V prompt editor.
Return raw JSON only, with exactly these fields:
{"message":"concise helpful reply in French","questions":["up to three useful questions"],"prompt":"complete standalone English MiniMax H3 Ref2V prompt","recommendations":["optional concise advice"]}

The complete prompt is always required and immediately runnable. Rewrite the CURRENT H3 PROMPT directly; never return a Brief, action plan, patch or diff. Preserve the application-owned opening <Picture N> reference rules exactly, followed by the scene setup, Shot 1, overall_soundscape and non_diegetic_music. Preserve every explicit quoted dialogue unless the user explicitly asks to change it. Never invent, remove, renumber or reinterpret a reference.

GENERATED KEYFRAMES are visual samples, not audio evidence. Use them to compare composition, continuity and visible motion with the user's goal and exact render settings. Never claim to have heard the video. Keep the Ref2V shot chronological, physically achievable and concise; each timed event appears once and ongoing motion remains visible through the cut when requested. Do not output Markdown or text outside the JSON."""

_REF2V_REVISION_SYSTEM_CAMERA_LOCKED = """You are a collaborative MiniMax H3 Ref2V prompt editor.
Return raw JSON only, with exactly these fields:
{"message":"concise helpful reply in French","questions":["up to three useful questions"],"prompt":"complete standalone English MiniMax H3 Ref2V prompt containing the supplied camera tokens","recommendations":["optional concise advice"],"camera_directives":null}

The complete prompt is always required and immediately runnable after application compilation. Rewrite the CURRENT H3 PROMPT directly; never return a Brief, action plan, patch or diff. Preserve the application-owned opening <Picture N> reference rules exactly, followed by the scene setup, Shot 1, overall_soundscape and non_diegetic_music. Preserve every explicit quoted dialogue unless the user explicitly asks to change it. Never invent, remove, renumber or reinterpret a reference.

Camera tokens such as [[camera:camera_1]] are application-owned. Copy every supplied token exactly once at the same chronological position and write no additional camera-control or lens instructions outside these tokens. Scene composition is allowed in the action prose: say which subjects and surroundings remain visible together at the relevant moment, without adding a camera movement. If a visibility-only correction leaves the compiled movement unchanged, camera_directives may remain null; do not replace a requested slight shake with static_shot merely to keep the scene visible. When the user does not explicitly request a camera change, camera_directives must be null. When changing a directive, return one object per supplied token in the same order with exactly id, start_ms, motion, amplitude, speed and target_clause. Use only the motion enum shown in the CAMERA CONTRACT. Never add or remove a camera token.
camera_directives must always be a JSON array when it is not null, including when there is exactly one camera token. Apply the motion-specific null requirements from the CAMERA CONTRACT before considering a target_clause; its prefix rules only apply when that motion accepts a target.

GENERATED KEYFRAMES are visual samples, not audio evidence. Use them to compare composition, continuity and visible motion with the user's goal and exact render settings. Never claim to have heard the video. Keep the Ref2V shot chronological, physically achievable and concise; each timed event appears once and ongoing motion remains visible through the cut when requested. Do not output Markdown or text outside the JSON."""

_SHOT_CUT_RE = re.compile(
    r"(?im)^\[Shot\s+(?P<number>[2-9][0-9]*)\]\s+At\s+"
    r"(?P<minutes>[0-9]{2}):(?P<seconds>[0-5][0-9])\.(?P<milliseconds>[0-9]{3})\s*,"
)
_FIELD_RE = re.compile(
    r"(?im)^(integrated_multimodal_description|overall_soundscape|non_diegetic_music):\s*"
)


class H3RenderAssets(Protocol):
    def create(self, content: bytes, *, media_type: str, source_run_id: str | None = None) -> Asset: ...
    def get(self, asset_id: str) -> Asset: ...
    def read_bytes(self, asset_id: str) -> bytes: ...


class UploadedImage(Protocol):
    @property
    def workflow_value(self) -> str: ...


class H3RenderQueue(Protocol):
    def find(self, prompt_id: str) -> object | None: ...


class H3RenderComfy(Protocol):
    def describe_node(self, class_type: str) -> dict[str, Any]: ...
    def list_lora_models(self) -> tuple[str, ...]: ...
    def upload_image(self, content: bytes, *, filename: str, subfolder: str = "") -> UploadedImage: ...
    def submit_workflow(self, workflow: Mapping[str, Any]) -> str: ...
    def get_history(self, prompt_id: str) -> dict[str, Any]: ...
    def get_queue(self) -> H3RenderQueue: ...
    def download_output(self, *, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes: ...
    def cancel_execution(self, prompt_id: str) -> object | None: ...


class H3RenderProjects(Protocol):
    def create(self, project: H3RenderProject) -> H3RenderProject: ...
    def save(self, project: H3RenderProject) -> H3RenderProject: ...
    def get(self, project_id: str) -> H3RenderProject: ...
    def list(self, limit: int = 30) -> list[H3RenderProject]: ...
    def find_source_revision(self, source_session_id: str, source_prompt_revision_id: str) -> H3RenderProject | None: ...
    def save_compiled_workflow(self, project_id: str, attempt_id: str, workflow: Mapping[str, Any]) -> str: ...


class H3RenderSessions(Protocol):
    def get(self, session_id: str) -> PromptLabSession: ...


class H3RenderCompositions(Protocol):
    def get(self, source_session_id: str) -> PromptComposition: ...


class H3RenderPreset(Protocol):
    preset_id: str
    label: str
    aspect_ratio: object
    megapixels: float
    duration_seconds: float
    steps: int


class H3RenderRecipe(Protocol):
    @property
    def reference(self) -> object: ...
    @property
    def status(self) -> str: ...
    @property
    def presets(self) -> Mapping[str, H3RenderPreset]: ...
    @property
    def output_node_id(self) -> str: ...
    @property
    def output_history_field(self) -> str: ...
    @property
    def keyframe_margin_ms(self) -> int: ...
    @property
    def maximum_keyframes(self) -> int: ...
    @property
    def supports_video_lora(self) -> bool: ...
    @property
    def supports_initial_megapixels(self) -> bool: ...
    @property
    def supports_upscale_bypass(self) -> bool: ...
    def keyframe_output_nodes(self, count: int) -> tuple[str, ...]: ...
    def build_workflow(
        self,
        *,
        input_mode: H3RenderInputMode,
        first_frame: str | None,
        last_frame: str | None,
        prompt: str,
        settings: VideoLabSettings,
        output_filename_prefix: str,
        keyframe_indices: tuple[int, ...],
        spectrum_enabled: bool = False,
        video_lora: H3VideoLoraSelection | None = None,
        initial_megapixels: float = 0.2,
        force_upscale: bool = False,
    ) -> dict[str, Any]: ...


class Ref2VRenderRecipe(Protocol):
    @property
    def reference(self) -> object: ...
    @property
    def status(self) -> str: ...
    @property
    def presets(self) -> Mapping[str, H3RenderPreset]: ...
    @property
    def output_node_id(self) -> str: ...
    @property
    def output_history_field(self) -> str: ...
    @property
    def keyframe_margin_ms(self) -> int: ...
    @property
    def maximum_keyframes(self) -> int: ...
    @property
    def minimum_reference_images(self) -> int: ...
    @property
    def maximum_reference_images(self) -> int: ...
    @property
    def supports_video_lora(self) -> bool: ...
    @property
    def supports_initial_megapixels(self) -> bool: ...
    @property
    def supports_upscale_bypass(self) -> bool: ...
    def keyframe_output_nodes(self, count: int) -> tuple[str, ...]: ...
    def build_workflow(
        self,
        *,
        source_images: tuple[str, ...],
        prompt: str,
        settings: VideoLabSettings,
        output_filename_prefix: str,
        keyframe_indices: tuple[int, ...],
        spectrum_enabled: bool = False,
        video_lora: H3VideoLoraSelection | None = None,
        initial_megapixels: float = 0.2,
        force_upscale: bool = False,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class H3RenderStreamEvent:
    kind: StreamEventKind
    phase: StreamPhase
    text: str = ""
    progress: float | None = None
    project: H3RenderProject | None = None
    error: str | None = None


class H3RenderService:
    def __init__(
        self,
        *,
        gateway: MultimodalGateway,
        workflow: H3RenderRecipe,
        ref2v_workflow: Ref2VRenderRecipe | None = None,
        additional_workflows: tuple[H3RenderRecipe, ...] = (),
        historical_ref2v_workflows: tuple[Ref2VRenderRecipe, ...] = (),
        historical_h3_workflows: tuple[H3RenderRecipe, ...] = (),
        checkpoints: H3CheckpointInventory | None = None,
        list_video_loras: Callable[[], tuple[str, ...]] | None = None,
        comfy: H3RenderComfy,
        assets: H3RenderAssets,
        projects: H3RenderProjects,
        sessions: H3RenderSessions,
        compositions: H3RenderCompositions,
        combat_revision_policies: tuple[CombatRevisionPolicy, ...] = (),
        application_outcomes: LlmCallApplicationOutcomeReporter | None = None,
        prompt_recipes: PromptRecipeStore | None = None,
        llm_traces=None,
        run_timeout: float = 3600.0,
        poll_interval: float = 1.0,
        project_id_factory: Callable[[], str] | None = None,
        turn_id_factory: Callable[[], str] | None = None,
        attempt_id_factory: Callable[[], str] | None = None,
        seed_factory: Callable[[], int] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        work_coordinator=None,
    ) -> None:
        if run_timeout <= 0 or poll_interval <= 0:
            raise ValueError("timeouts must be positive")
        self.combat_revision_policies = {policy.preparation: policy for policy in combat_revision_policies}
        self.gateway = gateway
        self.workflow = workflow
        self.ref2v_workflow = ref2v_workflow
        self.additional_workflows = additional_workflows
        self.historical_ref2v_workflows = historical_ref2v_workflows
        self.historical_h3_workflows = historical_h3_workflows
        self.checkpoints = checkpoints
        self.comfy = comfy
        self.assets = assets
        self.projects = projects
        self.sessions = sessions
        self.compositions = compositions
        self.application_outcomes = application_outcomes
        self.prompt_recipes = prompt_recipes
        self.llm_traces = llm_traces
        self.run_timeout = run_timeout
        self.poll_interval = poll_interval
        self._project_id_factory = project_id_factory or (lambda: f"h3-render-{uuid4().hex}")
        self._turn_id_factory = turn_id_factory or (lambda: f"turn-{uuid4().hex}")
        self._attempt_id_factory = attempt_id_factory or (lambda: f"attempt-{uuid4().hex}")
        self._seed_factory = seed_factory or (lambda: secrets.randbits(64))
        self._monotonic = monotonic
        self._sleep = sleep
        self.work_coordinator = work_coordinator
        self._lock = RLock()
        self._claimed: set[tuple[str, str]] = set()
        self._list_video_loras = list_video_loras or (lambda: self.comfy.list_lora_models())
        self._lora_inventory_lock = RLock()
        self._lora_inventory_expires = 0.0
        self._lora_inventory = None

    @staticmethod
    def revision_versions_for_mode(
        input_mode: H3RenderInputMode,
        preparation: VideoPreparationRef = VideoPreparationRef(),
    ) -> tuple[H3RenderRevisionVersion, ...]:
        if preparation.is_classic_cinematic:
            return (H3RenderRevisionVersion.CLASSIC_CINEMATIC,)
        if preparation.is_sensual:
            return (H3RenderRevisionVersion.SENSUAL,)
        if preparation.is_combat:
            if preparation.version == "1.3.0":
                return (H3RenderRevisionVersion.COMBAT_1_3,)
            if preparation.version == "1.2.0":
                return (H3RenderRevisionVersion.COMBAT_1_2,)
            if preparation.version == "1.1.1":
                return (H3RenderRevisionVersion.COMBAT_1_1_1,)
            if preparation.version == "1.1.0":
                return (H3RenderRevisionVersion.COMBAT_1_1,)
            if preparation.version != "1.0.0":
                raise ValueError("unavailable Combat revision policy version")
            return (H3RenderRevisionVersion.COMBAT,)
        return (
            H3RenderRevisionVersion.VOCAL,
            H3RenderRevisionVersion.CAMERA_LOCKED,
            H3RenderRevisionVersion.LEGACY,
        )

    @classmethod
    def default_revision_version(
        cls,
        input_mode: H3RenderInputMode,
        preparation: VideoPreparationRef = VideoPreparationRef(),
    ) -> H3RenderRevisionVersion:
        return cls.revision_versions_for_mode(input_mode, preparation)[0]

    def get_or_create_from_session(self, session_id: str) -> H3RenderProject:
        session = self.sessions.get(session_id)
        composition = self.compositions.get(session_id)
        final = composition.document(CompositionStage.FINAL_PROMPT).active_revision
        if final is None:
            raise ValueError("generate an H3 prompt before opening the render project")
        with self._lock:
            ref2v_classic = (
                session.profile_id == "minimax.h3.ref2v.classic.cinematic"
                and session.session_mode.value == "direct_multimodal"
            )
            existing = self.projects.find_source_revision(session_id, final.revision_id)
            if existing is not None and not (
                ref2v_classic and existing.input_mode is not H3RenderInputMode.REF2VA
            ):
                return self._refresh_detached(existing)
            if existing is not None and existing.attempts:
                raise ValueError(
                    "Cet ancien atelier REF2V a été enregistré en mode H3 et contient déjà des essais. "
                    "Reprenez-le dans un nouvel atelier REF2V pour conserver son historique."
                )
            is_ref2v = ref2v_classic or (
                session.profile_id in {"minimax.h3.ref2v.direct", "minimax.h3.ref2v.combat", "minimax.h3.ref2v.sensual"}
                and session.session_mode.value == "direct_multimodal"
            )
            if is_ref2v and self.ref2v_workflow is None:
                raise ValueError("the integrated Ref2V workflow is not configured")
            first = None if is_ref2v else next((value for value in session.references if value.role == "first_frame"), None)
            last = None if is_ref2v else next((value for value in session.references if value.role == "last_frame"), None)
            references = tuple(session.references) if is_ref2v else ()
            if ref2v_classic:
                # Match the Picture numbering used by both LLM calls, including
                # reordered bindings or a subset of the session's references.
                from .prompt_composition import composition_picture_mapping
                references = tuple(
                    session.reference(reference_id)
                    for reference_id, _ in composition_picture_mapping(composition)
                )
            if is_ref2v and self.ref2v_workflow is not None and not (
                self.ref2v_workflow.minimum_reference_images
                <= len(references)
                <= self.ref2v_workflow.maximum_reference_images
            ):
                raise ValueError(
                    "the integrated Ref2V workflow accepts between "
                    f"{self.ref2v_workflow.minimum_reference_images} and "
                    f"{self.ref2v_workflow.maximum_reference_images} images"
                )
            for reference in (*references, first, last):
                if reference is not None:
                    asset = self.assets.get(reference.asset_id)
                    if not asset.media_type.startswith("image/"):
                        raise ValueError("H3 frame anchors must be images")
            mode = (
                H3RenderInputMode.REF2VA
                if is_ref2v
                else derive_h3_render_input_mode(first is not None, last is not None)
            )
            if existing is not None:
                # Repair only the omitted REF2V Classic profile, on explicit
                # reopening, before any attempt. Keep the prompt and its edits.
                return self.projects.save(replace(
                    existing,
                    input_mode=H3RenderInputMode.REF2VA,
                    first_frame_asset_id=None, first_frame_label=None,
                    last_frame_asset_id=None, last_frame_label=None,
                    reference_asset_ids=tuple(value.asset_id for value in references),
                    reference_labels=tuple(value.label for value in references),
                ))
            plan = composition.document(CompositionStage.BEAT_SHEET).active_revision
            cuts = extract_plan_cut_times_ms(plan.content if plan is not None else "")
            if not cuts:
                cuts = extract_prompt_cut_times_ms(final.content)
            warnings: list[str] = []
            if "[Shot 2]" in final.content and not cuts:
                warnings.append("Les coupures du prompt ne sont pas horodatées ; les keyframes seront réparties régulièrement.")
            project = H3RenderProject(
                project_id=self._project_id_factory(),
                source_session_id=session_id,
                source_prompt_revision_id=final.revision_id,
                model_id=session.model_id,
                input_mode=mode,
                current_prompt=final.content,
                planned_cut_times_ms=cuts,
                first_frame_asset_id=first.asset_id if first else None,
                first_frame_label=first.label if first else None,
                last_frame_asset_id=last.asset_id if last else None,
                last_frame_label=last.label if last else None,
                reference_asset_ids=tuple(value.asset_id for value in references),
                reference_labels=tuple(value.label for value in references),
                warnings=tuple(warnings),
                revision_version=self.default_revision_version(mode, session.preparation),
                preparation=session.preparation,
                combat_settings=session.combat_settings,
                cinematic_settings=session.cinematic_settings,
                sensual_settings=session.sensual_settings,
                camera_clauses=extract_compiled_camera_clauses(final.content),
                dialogue_level=getattr(
                    composition.preparation_intent.creative_axes if composition.preparation_intent
                    else getattr(session.active_brief_revision, "creative_axes", None), "dialogue", 0),
            )
            return self.projects.create(project)

    def get(self, project_id: str) -> H3RenderProject:
        with self._lock:
            return self._refresh_detached(self.projects.get(project_id))

    def list(self, limit: int = 30) -> list[H3RenderProject]:
        with self._lock:
            return [self._refresh_detached(value) for value in self.projects.list(limit)]

    def workflow_for_mode(
        self,
        input_mode: H3RenderInputMode,
        recipe_id: str | None = None,
        recipe_version: str | None = None,
    ) -> H3RenderRecipe | Ref2VRenderRecipe:
        if recipe_id is not None:
            for recipe in self.recipes_for_mode(input_mode):
                if recipe.reference.recipe_id == recipe_id and recipe.reference.version == recipe_version:
                    return recipe
            raise ValueError("Recette de rendu ou version indisponible pour ce mode.")
        if recipe_version is not None:
            raise ValueError("Une version doit être accompagnée de son identifiant de recette.")
        if input_mode is H3RenderInputMode.REF2VA:
            if self.ref2v_workflow is None:
                raise ValueError("the integrated Ref2V workflow is not configured")
            return self.ref2v_workflow
        return self.workflow

    def recipes_for_mode(self, input_mode):
        historical = self.historical_ref2v_workflows if input_mode is H3RenderInputMode.REF2VA else self.historical_h3_workflows
        return (self.workflow_for_mode(input_mode), *self.additional_workflows, *historical)

    def recipe_for_attempt(self, project, attempt):
        if attempt.recipe is None:
            return self.workflow_for_mode(project.input_mode)
        recipe = self.workflow_for_mode(project.input_mode, attempt.recipe.recipe_id, attempt.recipe.version)
        if recipe.reference != attempt.recipe:
            raise ValueError("La recette enregistrée de cet essai ne correspond plus au workflow disponible.")
        return recipe

    def progress_for_attempt(self, project, attempt):
        recipe = self.recipe_for_attempt(project, attempt)
        return recipe.progress_for(attempt.bunny) if attempt.bunny else recipe.progress_profile

    def _recipe_for(
        self,
        project: H3RenderProject,
    ) -> H3RenderRecipe | Ref2VRenderRecipe:
        return self.workflow_for_mode(project.input_mode)

    def new_seed(self) -> int:
        return self._seed_factory()

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return self.gateway.list_models()

    def stream_chat(
        self,
        project_id: str,
        message: str,
        *,
        feedback_attempt_id: str | None = None,
        revision_version: str | H3RenderRevisionVersion | None = None,
        model_id: str | None = None,
        creative_audacity: int | None = None,
        dialogue_level: int | None = None,
        include_reasoning: bool = False,
        repair_rejected: bool = False,
    ) -> Iterator[H3RenderStreamEvent]:
        message = _bounded_text(message, "message", 12_000)
        if dialogue_level is not None:
            validate_vocal_level(dialogue_level)
        if creative_audacity is not None:
            creative_audacity = _revision_audacity(creative_audacity)
            if creative_audacity == 0:
                creative_audacity = None
        if model_id is not None:
            model_id = _bounded_text(model_id, "model_id", 300)
        repair_error: str | None = None
        repair_draft: str | None = None
        with self._lock:
            project = self.projects.get(project_id)
            if repair_rejected:
                if project.revision_error is None:
                    raise ValueError("there is no rejected H3 revision to repair")
                repair_error = project.revision_error
                repair_draft = project.revision_draft
            if project.adaptation is not None and project.adaptation.status != "ready":
                raise ValueError("Terminez l’adaptation REF2V avant de modifier ou générer son prompt.")
            if not project.camera_clauses:
                current_prompt, camera_clauses = _migrate_legacy_camera_contract(
                    project.current_prompt
                )
                project = replace(
                    project,
                    current_prompt=current_prompt,
                    camera_clauses=camera_clauses,
                )
            version = _revision_version(
                (
                    project.revision_draft_version
                    if repair_rejected and project.revision_draft_version is not None
                    else revision_version
                )
                or project.revision_version
                or self.default_revision_version(project.input_mode, project.preparation)
            )
            if version not in self.revision_versions_for_mode(project.input_mode, project.preparation):
                raise ValueError(
                    f"revision {version.value} is not available for {project.input_mode.value}"
                )
            project = project.select_revision_version(version)
            if dialogue_level is not None:
                if dialogue_level and version not in {H3RenderRevisionVersion.VOCAL, H3RenderRevisionVersion.COMBAT, H3RenderRevisionVersion.COMBAT_1_1, H3RenderRevisionVersion.COMBAT_1_1_1, H3RenderRevisionVersion.COMBAT_1_2, H3RenderRevisionVersion.COMBAT_1_3, H3RenderRevisionVersion.CLASSIC_CINEMATIC, H3RenderRevisionVersion.SENSUAL}:
                    raise ValueError("Choisissez la révision 0.3.0 pour la liberté de dialogue.")
                project = replace(project, dialogue_level=dialogue_level)
            project = project.select_revision_model(
                model_id or project.revision_model_id or project.model_id
            )
            if feedback_attempt_id is not None:
                project = project.use_feedback(feedback_attempt_id)
            user = H3RenderTurn(
                turn_id=self._turn_id_factory(),
                role=H3RenderTurnRole.USER,
                content=message,
            )
            project = self.projects.save(project.add_turn(user))
        request = self._completion_request(
            project,
            message,
            include_reasoning,
            creative_audacity,
            repair_error=repair_error,
            repair_draft=repair_draft,
        )
        parts: list[str] = []
        try:
            for event in self.gateway.stream(request):
                if event.kind is StreamEventKind.DELTA:
                    parts.append(event.text)
                if event.kind is StreamEventKind.TRUNCATED:
                    raw = event.result.content if event.result is not None else "".join(parts)
                    error = ValueError(truncated_response_message(request.max_tokens))
                    self._report(event.result.call_id if event.result else None, LlmCallApplicationOutcome.REJECTED, error)
                    yield H3RenderStreamEvent(
                        StreamEventKind.TRUNCATED,
                        StreamPhase.TRUNCATED,
                        raw,
                        project=self.projects.get(project_id),
                        error=str(error),
                    )
                    return
                if event.kind is StreamEventKind.COMPLETED:
                    if event.result is None:
                        raise ValueError("model stream completed without a result")
                    try:
                        terminal = self._accept_chat_response(
                            project_id,
                            event.result.content,
                            version,
                            event.result.model_id,
                        )
                    except Exception as error:
                        self._report(event.result.call_id, LlmCallApplicationOutcome.REJECTED, error)
                        terminal = self._remember_rejected_revision(
                            project_id,
                            event.result.content,
                            error,
                            version,
                        )
                        yield H3RenderStreamEvent(
                            StreamEventKind.COMPLETED,
                            StreamPhase.COMPLETED,
                            event.result.content,
                            1.0,
                            terminal,
                            _error(error),
                        )
                    else:
                        self._report(event.result.call_id, LlmCallApplicationOutcome.ACCEPTED)
                        yield H3RenderStreamEvent(
                            StreamEventKind.COMPLETED,
                            StreamPhase.COMPLETED,
                            event.result.content,
                            1.0,
                            terminal,
                        )
                    return
                yield H3RenderStreamEvent(event.kind, event.phase, event.text, event.progress)
        except GeneratorExit:
            raise
        except Exception as error:
            yield H3RenderStreamEvent(
                StreamEventKind.COMPLETED,
                StreamPhase.COMPLETED,
                "".join(parts),
                1.0,
                self.projects.get(project_id),
                _error(error),
            )

    def video_lora_inventory(self, *, refresh=False) -> tuple[tuple[str, ...], str | None]:
        """Shared short-lived inventory; never queried from render polling."""
        with self._lora_inventory_lock:
            if not refresh and self._lora_inventory is not None and self._monotonic() < self._lora_inventory_expires:
                return self._lora_inventory
            try:
                raw_models = self._list_video_loras()
                if not isinstance(raw_models, (tuple, list)):
                    raise ValueError("Invalid LoRA inventory")
                models = {}
                for raw in raw_models:
                    try:
                        name = canonical_h3_video_lora_name(raw)
                    except (TypeError, ValueError):
                        continue
                    models.setdefault(name.casefold(), name)
                self._lora_inventory = (tuple(sorted(models.values(), key=str.casefold)), None)
            except Exception as error:
                self._lora_inventory = ((), f"Inventaire LoRA vid\u00e9o indisponible : {_error(error)}")
            self._lora_inventory_expires = self._monotonic() + (5 if self._lora_inventory[1] else 60)
            return self._lora_inventory

    def validate_video_loras(self, recipe, video_lora=None, video_loras=None):
        per_pass = recipe.reference.recipe_id == BUNNY_RECIPE_ID
        validate_video_lora_stack(video_loras, video_lora, per_pass)
        if video_lora is not None and not isinstance(video_lora, H3VideoLoraSelection):
            raise TypeError("video_lora must be H3VideoLoraSelection")
        if video_loras is not None and not getattr(recipe, "supports_video_lora_stack", False):
            raise ValueError("Choisissez une recette actuelle pour utiliser plusieurs LoRA.")
        if video_loras is not None:
            maximum = recipe.video_lora_stack_spec()["maximum"]
            if len(video_loras.entries) > maximum:
                raise ValueError(f"Cette recette accepte au maximum {maximum} LoRA. Choisissez une recette plus récente.")
        names = ([entry.name for entry in video_loras.active_entries] if video_loras is not None
                 else [video_lora.name] if video_lora is not None else [])
        if not names:
            return
        if not recipe.supports_video_lora:
            raise ValueError("H3 video LoRA is not available for this workflow")
        models, warning = self.video_lora_inventory()
        if warning:
            raise ValueError(warning)
        if video_lora is not None:
            if video_lora.name.casefold() not in {name.casefold() for name in models}:
                raise ValueError("selected H3 video LoRA is not available in ComfyUI")
            return
        available = set(models)
        for name in names:
            if name not in available:
                raise ValueError(f"LoRA vid\u00e9o absent de ComfyUI : {name}. Actualisez la liste ou d\u00e9sactivez ce LoRA.")

    def resolve_model_loading(self, recipe, mode, checkpoint=None):
        if checkpoint is not None:
            if not getattr(recipe, "supports_checkpoint_selection", False):
                raise ValueError("Cette recette historique ne permet pas de changer le checkpoint. Choisissez la recette actuelle.")
            if self.checkpoints is None:
                raise ValueError("Le catalogue des checkpoints est indisponible.")
            self.checkpoints.validate(checkpoint, mode)
        return recipe.model_loading(mode, checkpoint) if getattr(recipe, "supports_checkpoint_selection", False) else None

    def prepare_attempt(
        self,
        project_id: str,
        *,
        prompt: str,
        settings: VideoLabSettings,
        music_enabled: bool = False,
        spectrum_enabled: bool = False,
        video_lora: H3VideoLoraSelection | None = None,
        initial_megapixels: float = 0.2,
        force_upscale: bool = False,
        recipe_id: str | None = None,
        recipe_version: str | None = None,
        bunny: H3BunnySettings | None = None,
        checkpoint: str | None = None,
        video_loras: H3VideoLoraStack | None = None,
    ) -> H3RenderProject:
        if checkpoint is not None or video_lora is not None or video_loras is not None:
            candidate_project = self.projects.get(project_id)
            selected_recipe = self.workflow_for_mode(candidate_project.input_mode, recipe_id, recipe_version)
            if checkpoint is not None:
                self.resolve_model_loading(selected_recipe, candidate_project.input_mode, checkpoint)
            self.validate_video_loras(selected_recipe, video_lora, video_loras)
        validate_h3_initial_megapixels(initial_megapixels)
        prompt = _bounded_text(prompt, "prompt", 60_000)
        if not isinstance(settings, VideoLabSettings):
            raise TypeError("settings must be VideoLabSettings")
        if not isinstance(music_enabled, bool):
            raise TypeError("music_enabled must be a boolean")
        if not isinstance(spectrum_enabled, bool):
            raise TypeError("spectrum_enabled must be a boolean")
        if type(force_upscale) is not bool:
            raise TypeError("force_upscale must be a boolean")
        if video_lora is not None and not isinstance(video_lora, H3VideoLoraSelection):
            raise TypeError("video_lora must be an H3VideoLoraSelection or None")
        with self._lock:
            project = self.projects.get(project_id)
            recipe = self.workflow_for_mode(project.input_mode, recipe_id, recipe_version)
            model_loading = recipe.model_loading(project.input_mode, checkpoint) if getattr(recipe, "supports_checkpoint_selection", False) else None
            if project.adaptation is not None and project.adaptation.status != "ready":
                raise ValueError("Terminez l’adaptation REF2V avant de lancer un rendu.")
            if recipe.reference.recipe_id == BUNNY_RECIPE_ID:
                bunny = bunny or H3BunnySettings()
                if not isinstance(bunny, H3BunnySettings):
                    raise TypeError("Réglages BUNNY invalides.")
                settings = replace(settings, steps=bunny.coarse_steps + bunny.refine_steps)
                bunny_geometry(settings, initial_megapixels)
                if force_upscale:
                    raise ValueError("BUNNY does not support forced upscale.")
                if spectrum_enabled or (video_lora and video_lora.clip_last_layer is not None):
                    raise ValueError("BUNNY ne prend pas en charge Spectrum ou CLIP Last Layer.")
            elif bunny is not None:
                raise ValueError("Les réglages BUNNY ne s’appliquent pas à la recette actuelle.")
            if initial_megapixels != 0.2 and not getattr(recipe, "supports_initial_megapixels", False):
                raise ValueError("Ce workflow fixe la génération initiale à 0,2 MP.")
            if force_upscale and not getattr(recipe, "supports_upscale_bypass", False):
                raise ValueError("This historical workflow does not support the upscale A/B test.")
            upscale_bypassed = False
            if recipe.reference.recipe_id != BUNNY_RECIPE_ID:
                upscale_bypassed = bool(
                    getattr(recipe, "supports_upscale_bypass", False)
                    and h3_upscale_plan(
                        settings,
                        initial_megapixels,
                        force_upscale=force_upscale,
                    )["bypassed"]
                )
            prompt = canonicalize_h3_revision(project.current_prompt, prompt, project.input_mode, combat_sequence=project.combat_settings is not None, combat_version=project.preparation.version,
                classic_cinematic=project.preparation.is_classic_cinematic, sensual_cinematic=project.preparation.is_sensual)
            duration_ms = round(settings.effective_duration_seconds * 1000)
            cuts = extract_prompt_cut_times_ms(prompt) or project.planned_cut_times_ms
            timestamps = plan_keyframe_timestamps_ms(
                duration_ms,
                cuts,
                margin_ms=recipe.keyframe_margin_ms,
                maximum=recipe.maximum_keyframes,
            )
            effective_prompt = prompt if music_enabled else disable_non_diegetic_music(prompt)
            duration_warning = h3_prompt_duration_warning(
                prompt,
                settings.duration_seconds,
            )
            attempt = H3RenderAttempt(
                attempt_id=self._attempt_id_factory(),
                index=max((a.index for a in project.attempts if a.dlss is None), default=0) + 1,
                prompt=prompt,
                effective_prompt=effective_prompt,
                settings=settings,
                music_enabled=music_enabled,
                keyframe_timestamps_ms=timestamps,
                spectrum_enabled=spectrum_enabled,
                video_lora=video_lora,
                video_loras=video_loras,
                initial_megapixels=initial_megapixels,
                recipe=recipe.reference,
                bunny=bunny,
                checkpoint=checkpoint,
                model_loading=model_loading,
                force_upscale=force_upscale,
                upscale_bypassed=upscale_bypassed,
                warnings=(duration_warning,) if duration_warning else (),
            )
            if self.llm_traces is not None:
                from .prompt_recipes import preparation_call_ids
                try:
                    composition = self.compositions.get(project.source_session_id)
                except KeyError:
                    composition = None
                calls = preparation_call_ids(composition, project.source_prompt_revision_id) if composition else []
                self.llm_traces.snapshot(project, attempt, preparation_calls=calls)
            project = replace(project, current_prompt=prompt)
            return self.projects.save(project.add_attempt(attempt))

    def queue_attempt(self, project_id: str, attempt_id: str) -> H3RenderProject:
        active = {
            H3RenderAttemptStatus.QUEUED,
            H3RenderAttemptStatus.RUNNING,
            H3RenderAttemptStatus.CANCEL_PENDING,
        }
        with self._lock:
            project = self.projects.get(project_id)
            for candidate in self.projects.list(2**31 - 1):
                candidate = self._refresh_detached(candidate)
                for value in candidate.attempts:
                    if value.status in active:
                        raise ValueError(
                            f"Un rendu H3/REF2V est déjà actif : essai {value.index} "
                            f"dans l’atelier {candidate.project_id} ({value.status.value})."
                        )
            # Refresh may have recovered an earlier attempt in this same project.
            # Do not overwrite that terminal state with the pre-refresh snapshot.
            project = self.projects.get(project_id)
            return self.projects.save(project.replace_attempt(project.attempt(attempt_id).queue()))

    def execute_attempt(
        self,
        project_id: str,
        attempt_id: str,
        *,
        post_cooldown_seconds: float = 0,
        on_cooldown_started: Callable[[float], None] | None = None,
        on_cooldown_finished: Callable[[], None] | None = None,
        operation_label: str | None = None,
    ) -> H3RenderProject:
        if (
            isinstance(post_cooldown_seconds, bool)
            or not isinstance(post_cooldown_seconds, (int, float))
            or post_cooldown_seconds < 0
        ):
            raise ValueError("post_cooldown_seconds must be non-negative")
        if self.work_coordinator is not None:
            try:
                with self.work_coordinator.lease(
                    f"h3:{project_id}:{attempt_id}",
                    ComputeResource.REMOTE_GPU,
                    ProductionWorkload.VIDEO_RENDER,
                    (operation_label or "H3 / REF2V")[:200],
                    cancelled=lambda: self.projects.get(project_id).attempt(attempt_id).status
                    is not H3RenderAttemptStatus.QUEUED,
                ):
                    project = self._execute_attempt_owned(project_id, attempt_id)
                    attempt = project.attempt(attempt_id)
                    if post_cooldown_seconds and attempt.execution_id is not None:
                        self.work_coordinator.cooldown_while_owned(
                            ComputeResource.REMOTE_GPU,
                            post_cooldown_seconds,
                            "Refroidissement entre vidéos",
                            on_started=on_cooldown_started,
                            on_finished=on_cooldown_finished,
                        )
                    return project
            except ResourceWaitCancelled:
                return self.projects.get(project_id)
        return self._execute_attempt_owned(project_id, attempt_id)

    def _execute_attempt_owned(self, project_id: str, attempt_id: str) -> H3RenderProject:
        key = (project_id, attempt_id)
        activity_id = f"h3:{project_id}:{attempt_id}"
        if self.work_coordinator is not None:
            self.work_coordinator.report_progress(activity_id, 0.02, "Préparation du workflow vidéo")
        with self._lock:
            project = self.projects.get(project_id)
            attempt = project.attempt(attempt_id)
            if attempt.status is not H3RenderAttemptStatus.QUEUED:
                return project
            if key in self._claimed:
                raise ValueError("attempt is already executing")
            self._claimed.add(key)
        execution_id: str | None = None
        workflow_digest: str | None = None
        family = "PanelForge_H3_Ref2V" if project.input_mode is H3RenderInputMode.REF2VA else "PanelForge_H3_Base"
        output_prefix = f"video/{family}/{project_id}/{attempt_id}"
        try:
            recipe = self.recipe_for_attempt(project, attempt)
            extra = {"bunny": attempt.bunny, "initial_megapixels": attempt.initial_megapixels} if attempt.bunny else {}
            if getattr(recipe, "supports_initial_megapixels", False):
                extra["initial_megapixels"] = attempt.initial_megapixels
            if getattr(recipe, "supports_upscale_bypass", False):
                extra["force_upscale"] = attempt.force_upscale
            if getattr(recipe, "supports_checkpoint_selection", False):
                loading = self.resolve_model_loading(recipe, project.input_mode, attempt.checkpoint)
                if attempt.model_loading is not None and loading != attempt.model_loading:
                    raise ValueError("Le chargement du checkpoint ne correspond plus aux réglages enregistrés.")
                extra["checkpoint"] = attempt.checkpoint
            elif attempt.checkpoint is not None:
                raise ValueError("Checkpoint non pris en charge par cette recette historique.")
            if attempt.video_loras is not None:
                self.validate_video_loras(recipe, attempt.video_lora, attempt.video_loras)
                extra["video_loras"] = attempt.video_loras
            keyframe_indices = tuple(
                min(attempt.settings.frame_count - 1, round(value * VIDEO_FPS / 1000))
                for value in attempt.keyframe_timestamps_ms
            )
            if project.input_mode is H3RenderInputMode.REF2VA:
                source_images = tuple(
                    self._upload_frame(asset_id, f"reference-{index + 1}")
                    for index, asset_id in enumerate(project.reference_asset_ids)
                )
                workflow = recipe.build_workflow(
                    source_images=source_images,
                    prompt=attempt.effective_prompt,
                    settings=attempt.settings,
                    output_filename_prefix=output_prefix,
                    keyframe_indices=keyframe_indices,
                    spectrum_enabled=attempt.spectrum_enabled,
                    video_lora=attempt.video_lora,
                    **extra,
                )
            else:
                first_value = self._upload_frame(project.first_frame_asset_id, "first")
                last_value = self._upload_frame(project.last_frame_asset_id, "last")
                workflow = recipe.build_workflow(
                    input_mode=project.input_mode,
                    first_frame=first_value,
                    last_frame=last_value,
                    prompt=attempt.effective_prompt,
                    settings=attempt.settings,
                    output_filename_prefix=output_prefix,
                    keyframe_indices=keyframe_indices,
                    spectrum_enabled=attempt.spectrum_enabled,
                    video_lora=attempt.video_lora,
                    **extra,
                )
            if attempt.bunny:
                recipe.validate_dependencies(self.comfy, workflow)
            workflow_digest = self.projects.save_compiled_workflow(project_id, attempt_id, workflow)
            if self.work_coordinator is not None:
                self.work_coordinator.report_progress(activity_id, 0.08, "Envoi à ComfyUI")
            with self._lock:
                current = self.projects.get(project_id)
                current_attempt = current.attempt(attempt_id)
                if current_attempt.status is not H3RenderAttemptStatus.QUEUED:
                    return current
                execution_id = self.comfy.submit_workflow(workflow)
                current = self.projects.save(
                    current.replace_attempt(
                        current_attempt.start(execution_id, workflow_digest)
                    )
                )
            history = self._wait_history(project_id, attempt_id, execution_id)
            if self.work_coordinator is not None:
                self.work_coordinator.report_progress(activity_id, 0.88, "Récupération de la vidéo")
            output_ref = extract_bound_video(
                history,
                node_id=recipe.output_node_id,
                history_field=recipe.output_history_field,
            )
            output_content = self.comfy.download_output(
                filename=output_ref["filename"],
                subfolder=output_ref["subfolder"],
                folder_type=output_ref["type"],
            )
            _validate_mp4(output_content, output_ref["filename"])
            video_asset = self.assets.create(output_content, media_type="video/mp4", source_run_id=project_id)
            if self.work_coordinator is not None:
                self.work_coordinator.report_progress(activity_id, 0.96, "Import de la vidéo")
            keyframes, warnings = self._import_keyframes(history, project_id, attempt)
            with self._lock:
                current = self.projects.get(project_id)
                current_attempt = current.attempt(attempt_id)
                if current_attempt.status in {
                    H3RenderAttemptStatus.RUNNING,
                    H3RenderAttemptStatus.CANCEL_PENDING,
                }:
                    succeeded = current_attempt.succeed(
                        video_asset.asset_id,
                        keyframes,
                        warnings,
                    )
                    current = self.projects.save(
                        current.replace_attempt(succeeded).use_feedback(attempt_id)
                    )
                if self.work_coordinator is not None:
                    self.work_coordinator.report_progress(activity_id, 1.0, "Vidéo terminée")
                return current
        except Exception as error:
            with self._lock:
                current = self.projects.get(project_id)
                current_attempt = current.attempt(attempt_id)
                if (
                    current_attempt.status is H3RenderAttemptStatus.QUEUED
                    and execution_id is not None
                    and workflow_digest is not None
                ):
                    current = self._stop_unpersisted_submission(
                        current,
                        current_attempt,
                        execution_id,
                        workflow_digest,
                        error,
                    )
                elif current_attempt.status is H3RenderAttemptStatus.RUNNING:
                    current = self._stop_remote_after_failure(
                        current,
                        current_attempt,
                        error,
                    )
                elif current_attempt.status in {
                    H3RenderAttemptStatus.CREATED,
                    H3RenderAttemptStatus.QUEUED,
                }:
                    current = self.projects.save(current.replace_attempt(current_attempt.fail(_error(error))))
                return current
        finally:
            with self._lock:
                self._claimed.discard(key)

    def cancel_attempt(self, project_id: str, attempt_id: str) -> H3RenderProject:
        with self._lock:
            project = self.projects.get(project_id)
            attempt = project.attempt(attempt_id)
            if attempt.status in {H3RenderAttemptStatus.CREATED, H3RenderAttemptStatus.QUEUED}:
                return self.projects.save(project.replace_attempt(attempt.cancel()))
            if attempt.status not in {H3RenderAttemptStatus.RUNNING, H3RenderAttemptStatus.CANCEL_PENDING}:
                return project
            assert attempt.execution_id is not None
            try:
                self.comfy.cancel_execution(attempt.execution_id)
            except Exception as error:
                if attempt.status is H3RenderAttemptStatus.RUNNING:
                    attempt = attempt.cancel_pending(_error(error))
                else:
                    attempt = replace(attempt, error=_error(error))
            else:
                attempt = attempt.cancel()
            return self.projects.save(project.replace_attempt(attempt))

    def select_feedback(self, project_id: str, attempt_id: str | None) -> H3RenderProject:
        with self._lock:
            return self.projects.save(self.projects.get(project_id).use_feedback(attempt_id))

    def resume_attempt(self, project_id: str, attempt_id: str) -> H3RenderProject:
        with self._lock:
            return self.projects.save(self.projects.get(project_id).resume_attempt(attempt_id))

    def _completion_request(
        self,
        project: H3RenderProject,
        message: str,
        include_reasoning: bool,
        creative_audacity: int | None,
        *,
        repair_error: str | None = None,
        repair_draft: str | None = None,
    ) -> CompletionRequest:
        from .prompt_recipes import EDITABLE_KEYS
        from .prompt_recipe_text import using_prompt_texts
        package = None
        if self.prompt_recipes is not None:
            # A source workshop may since have switched recipe/family. The render
            # keeps its own preparation identity, including for future adjustments.
            mode = "ref2v" if project.input_mode is H3RenderInputMode.REF2VA else "fl2va"
            family = "classic.cinematic" if project.preparation.is_classic_cinematic else project.preparation.family
            key = (f"minimax.h3.{mode}.{family}.planned", project.preparation.version)
            if key in EDITABLE_KEYS:
                package = self.prompt_recipes.get(*key)
        with using_prompt_texts(package["fields"] if package else None):
            request = self._completion_request_scoped(project, message, include_reasoning, creative_audacity,
                repair_error=repair_error, repair_draft=repair_draft)
        system = request.system_prompt
        if package and package["fields"].get("render.system"):
            system = package["fields"]["render.system"]
            if project.preparation.is_combat:
                with using_prompt_texts(package["fields"]):
                    system += _combat_action_policy(project)
        return replace(request, system_prompt=system, trace_context={
            "session_id": project.source_session_id, "project_id": project.project_id,
            "stage": "render_adjustment", "turn_id": project.turns[-1].turn_id,
            "recipe_revision": package["revision"] if package else None,
            "cookbook_id": package["cookbook_id"] if package else None,
            "cookbook_version": package["version"] if package else None,
            "source_prompt_revision_id": project.source_prompt_revision_id,
        })

    def _completion_request_scoped(
        self,
        project: H3RenderProject,
        message: str,
        include_reasoning: bool,
        creative_audacity: int | None,
        *,
        repair_error: str | None = None,
        repair_draft: str | None = None,
    ) -> CompletionRequest:
        feedback = project.attempt(project.feedback_attempt_id) if project.feedback_attempt_id else None
        recipe = self.recipe_for_attempt(project, feedback) if feedback else self._recipe_for(project)
        version = project.revision_version or self.default_revision_version(project.input_mode, project.preparation)
        combat_policy = self.combat_revision_policies.get(project.preparation) if project.preparation.is_combat else None
        if project.preparation.is_combat and combat_policy is None:
            raise ValueError("the pinned Combat revision prompts are unavailable")
        camera_locked = version in {H3RenderRevisionVersion.CAMERA_LOCKED, H3RenderRevisionVersion.VOCAL, H3RenderRevisionVersion.COMBAT, H3RenderRevisionVersion.COMBAT_1_1, H3RenderRevisionVersion.COMBAT_1_1_1, H3RenderRevisionVersion.COMBAT_1_2, H3RenderRevisionVersion.COMBAT_1_3, H3RenderRevisionVersion.CLASSIC_CINEMATIC, H3RenderRevisionVersion.SENSUAL}
        images: list[ImageInput] = []
        if feedback is not None:
            for frame in feedback.keyframes:
                asset = self.assets.get(frame.asset_id)
                images.append(ImageInput(
                    asset.media_type,
                    self.assets.read_bytes(asset.asset_id),
                    f"GENERATED KEYFRAME — {frame.label} — {frame.timestamp_ms / 1000:.3f}s",
                ))
        conversation = "\n".join(
            f"{turn.role.value.upper()}: {turn.content}"
            + (
                "\nPROMPT REVISION: "
                + (
                    protect_h3_revision_camera(
                        turn.prompt,
                        extract_compiled_camera_clauses(turn.prompt),
                    )
                    if camera_locked else turn.prompt
                )
                if turn.prompt else ""
            )
            for turn in project.turns[:-1]
        ) or "No earlier exchange."
        selected = _attempt_context(feedback) if feedback is not None else "No rendered attempt selected."
        current_prompt = (
            protect_h3_revision_camera(project.current_prompt, project.camera_clauses)
            if camera_locked
            else project.current_prompt
        )
        camera_contract = (
            _camera_contract_prompt(project.camera_clauses)
            if camera_locked
            else "Camera clauses remain part of the editable legacy prompt."
        )
        sections = [
            f"H3 INPUT MODE (immutable): {project.input_mode.value.upper()}",
            f"CURRENT COMPLETE H3 PROMPT:\n{current_prompt}",
            f"CAMERA CONTRACT:\n{camera_contract}",
            f"RECENT PROJECT CONVERSATION:\n{conversation}",
            f"SELECTED RENDER AND EXACT SETTINGS:\n{selected}",
            (
                "KEYFRAME SAMPLING NOTE:\nFrames around planned cuts are sampled "
                f"{recipe.keyframe_margin_ms} ms before and after each cut, never at the exact boundary."
            ),
        ]
        if creative_audacity is not None:
            sections.append(
                "REVISION CREATIVE AUDACITY (explicit user control):\n"
                f"{creative_audacity}/3 — "
                f"{combat_policy.audacity_prompt if combat_policy else video_revision_audacity_policy(creative_audacity)}"
            )
        if repair_error is not None:
            sections.append(
                "REJECTED REVISION REPAIR (explicitly requested by the user):\n"
                "Correct the structure so the answer satisfies the application contract. "
                "Preserve the latest user intention and all valid content; do not invent a new request.\n"
                f"EXACT VALIDATOR ERROR:\n{repair_error}\n\n"
                "REJECTED PROMPT DRAFT:\n"
                f"{repair_draft or 'No prompt field could be recovered; rebuild it from CURRENT COMPLETE H3 PROMPT.'}"
            )
        sections.append(f"NEW USER MESSAGE (authoritative):\n{message}")
        if version in {H3RenderRevisionVersion.VOCAL, H3RenderRevisionVersion.COMBAT, H3RenderRevisionVersion.COMBAT_1_1, H3RenderRevisionVersion.COMBAT_1_1_1, H3RenderRevisionVersion.COMBAT_1_2, H3RenderRevisionVersion.COMBAT_1_3, H3RenderRevisionVersion.CLASSIC_CINEMATIC, H3RenderRevisionVersion.SENSUAL}:
            sections.append(vocal_policy(project.dialogue_level))
        from .classic_cinematic import REVISION_SYSTEM as classic_revision_system
        from .sensual_cinematic import REVISION_SYSTEM as sensual_revision_system
        ref_system = _REF2V_REVISION_SYSTEM_CAMERA_LOCKED if camera_locked else _REF2V_REVISION_SYSTEM
        if "[Shot 2]" in project.current_prompt:
            ref_system = ref_system.replace("scene setup, Shot 1,", "scene setup, all numbered shot headings with their exact cut timestamps,")
            ref_system += "\nKeep every existing [Shot N] heading and cut time exactly; do not collapse the sequence into Shot 1."
        user_prompt = "\n\n".join(sections)
        return CompletionRequest(
            model_id=project.revision_model_id or project.model_id,
            system_prompt=(
                classic_revision_system if project.preparation.is_classic_cinematic else
                sensual_revision_system if project.preparation.is_sensual else
                (combat_policy.system_prompt + _combat_action_policy(project)) if combat_policy else (ref_system
                if project.input_mode is H3RenderInputMode.REF2VA
                else (
                    _H3_REVISION_SYSTEM_CAMERA_LOCKED
                    if camera_locked
                    else _H3_REVISION_SYSTEM_LEGACY
                ))
            ),
            user_prompt=user_prompt,
            images=tuple(images),
            temperature=0.25,
            max_tokens=131_072,
            operation_id=(
                f"h3.{project.input_mode.value}.classic.cinematic.render.revision@{version.value}" if project.preparation.is_classic_cinematic else
                f"h3.{project.input_mode.value}.sensual.render.revision@1.0.0" if project.preparation.is_sensual else
                f"h3.{project.input_mode.value}.combat.render.revision@{project.preparation.version}" if combat_policy else
                f"h3.ref2v.render.revision@{version.value}"
                if project.input_mode is H3RenderInputMode.REF2VA
                else f"h3.base.render.revision@{version.value}"
            ),
            include_reasoning=include_reasoning,
        )

    def _accept_chat_response(
        self,
        project_id: str,
        raw: str,
        version: H3RenderRevisionVersion,
        model_id: str,
    ) -> H3RenderProject:
        value = _decode_json(raw)
        expected = {"message", "questions", "prompt", "recommendations"}
        if version in {H3RenderRevisionVersion.CAMERA_LOCKED, H3RenderRevisionVersion.VOCAL, H3RenderRevisionVersion.COMBAT, H3RenderRevisionVersion.COMBAT_1_1, H3RenderRevisionVersion.COMBAT_1_1_1, H3RenderRevisionVersion.COMBAT_1_2, H3RenderRevisionVersion.COMBAT_1_3, H3RenderRevisionVersion.CLASSIC_CINEMATIC, H3RenderRevisionVersion.SENSUAL}:
            expected.add("camera_directives")
        if set(value) != expected:
            raise ValueError("H3 render revision response has invalid fields")
        message = _bounded_text(value.get("message"), "assistant message", 12_000)
        questions = _string_array(value.get("questions"), "questions", 3)
        recommendations = _string_array(value.get("recommendations"), "recommendations", 8)
        with self._lock:
            project = self.projects.get(project_id)
            candidate = _bounded_text(value.get("prompt"), "H3 prompt", 60_000)
            camera_clauses = project.camera_clauses
            if version in {H3RenderRevisionVersion.CAMERA_LOCKED, H3RenderRevisionVersion.VOCAL, H3RenderRevisionVersion.COMBAT, H3RenderRevisionVersion.COMBAT_1_1, H3RenderRevisionVersion.COMBAT_1_1_1, H3RenderRevisionVersion.COMBAT_1_2, H3RenderRevisionVersion.COMBAT_1_3, H3RenderRevisionVersion.CLASSIC_CINEMATIC, H3RenderRevisionVersion.SENSUAL}:
                camera_clauses = _revision_camera_clauses(
                    value.get("camera_directives"),
                    project.camera_clauses,
                    continuous_phases=project.preparation.uses_cinematic_phases,
                )
                candidate = compile_h3_revision_camera(
                    candidate,
                    project.camera_clauses,
                    camera_clauses,
                )
            prompt = canonicalize_h3_revision(
                project.current_prompt,
                candidate,
                project.input_mode,
                combat_sequence=project.combat_settings is not None, combat_version=project.preparation.version,
                classic_cinematic=project.preparation.is_classic_cinematic,
                sensual_cinematic=project.preparation.is_sensual,
                camera_clauses=camera_clauses if version in {H3RenderRevisionVersion.CAMERA_LOCKED, H3RenderRevisionVersion.VOCAL, H3RenderRevisionVersion.COMBAT, H3RenderRevisionVersion.COMBAT_1_1, H3RenderRevisionVersion.COMBAT_1_1_1, H3RenderRevisionVersion.COMBAT_1_2, H3RenderRevisionVersion.COMBAT_1_3, H3RenderRevisionVersion.CLASSIC_CINEMATIC, H3RenderRevisionVersion.SENSUAL} else (),
            )
            if version in {H3RenderRevisionVersion.VOCAL, H3RenderRevisionVersion.COMBAT, H3RenderRevisionVersion.COMBAT_1_1, H3RenderRevisionVersion.COMBAT_1_1_1, H3RenderRevisionVersion.COMBAT_1_2, H3RenderRevisionVersion.COMBAT_1_3, H3RenderRevisionVersion.CLASSIC_CINEMATIC, H3RenderRevisionVersion.SENSUAL}:
                from .direct_fl2va_prompt import requested_h3_base_duration_ms
                latest_message = next((turn.content for turn in reversed(project.turns)
                                       if turn.role is H3RenderTurnRole.USER), "")
                validate_revision_speech(project.current_prompt, prompt, latest_message,
                    level=project.dialogue_level,
                    duration_ms=requested_h3_base_duration_ms(project.current_prompt) or 8000)
            assistant = H3RenderTurn(
                turn_id=self._turn_id_factory(),
                role=H3RenderTurnRole.ASSISTANT,
                content=message,
                prompt=prompt,
                questions=questions,
                recommendations=recommendations,
                revision_version=version,
                model_id=_bounded_text(model_id, "model_id", 300),
            )
            return self.projects.save(replace(
                project.add_turn(assistant),
                camera_clauses=camera_clauses,
                revision_version=version,
            ))

    def _remember_rejected_revision(
        self,
        project_id: str,
        raw: str,
        error: Exception,
        version: H3RenderRevisionVersion,
    ) -> H3RenderProject:
        draft = _revision_candidate(raw)
        with self._lock:
            project = self.projects.get(project_id).select_revision_version(version)
            return self.projects.save(project.reject_revision(
                draft=draft,
                error=_revision_error(error, draft),
                version=version,
            ))

    def _upload_frame(self, asset_id: str | None, role: str) -> str | None:
        if asset_id is None:
            return None
        asset = self.assets.get(asset_id)
        extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(asset.media_type)
        if extension is None:
            raise ValueError(f"unsupported H3 {role} frame media type")
        uploaded = self.comfy.upload_image(
            self.assets.read_bytes(asset_id),
            filename=f"{asset.asset_id}{extension}",
            subfolder="panelforge/h3-base",
        )
        return uploaded.workflow_value

    def _wait_history(self, project_id: str, attempt_id: str, execution_id: str) -> dict[str, Any]:
        deadline = self._monotonic() + self.run_timeout
        while True:
            attempt = self.projects.get(project_id).attempt(attempt_id)
            if attempt.status is H3RenderAttemptStatus.CANCELLED:
                raise RuntimeError("H3 Base render cancelled")
            history = self.comfy.get_history(execution_id)
            record = history.get(execution_id)
            if isinstance(record, Mapping):
                status = record.get("status")
                if isinstance(status, Mapping):
                    completed = status.get("completed") is True
                    name = status.get("status_str")
                    if completed and name == "success":
                        return dict(record)
                    if completed or name == "error":
                        raise RuntimeError(f"ComfyUI execution failed: {status}")
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                raise TimeoutError("ComfyUI H3 Base render timed out")
            self._sleep(min(self.poll_interval, remaining))

    def _import_keyframes(
        self,
        history: Mapping[str, Any],
        project_id: str,
        attempt: H3RenderAttempt,
    ) -> tuple[tuple[H3RenderKeyframe, ...], tuple[str, ...]]:
        frames: list[H3RenderKeyframe] = []
        warnings: list[str] = []
        project = self.projects.get(project_id)
        recipe = self.recipe_for_attempt(project, attempt)
        cut_times = extract_prompt_cut_times_ms(attempt.prompt) or project.planned_cut_times_ms
        for timestamp, node_id in zip(
            attempt.keyframe_timestamps_ms,
            recipe.keyframe_output_nodes(len(attempt.keyframe_timestamps_ms)),
            strict=True,
        ):
            try:
                ref = _extract_bound_image(history, node_id, "images")
                content = self.comfy.download_output(
                    filename=ref["filename"],
                    subfolder=ref["subfolder"],
                    folder_type=ref["type"],
                )
                media_type = _image_media_type(content)
                asset = self.assets.create(content, media_type=media_type, source_run_id=project_id)
                frames.append(H3RenderKeyframe(
                    asset_id=asset.asset_id,
                    timestamp_ms=timestamp,
                    label=keyframe_label(
                        timestamp,
                        attempt.keyframe_timestamps_ms,
                        cut_times,
                    ),
                ))
            except Exception as error:
                warnings.append(f"Keyframe {timestamp / 1000:.3f}s indisponible : {_error(error)}")
        if not frames:
            warnings.append("Aucune keyframe n’a été importée ; le rendu vidéo reste utilisable.")
        return tuple(frames), tuple(warnings)

    def _refresh_detached(self, project: H3RenderProject) -> H3RenderProject:
        revision_version = project.revision_version or self.default_revision_version(
            project.input_mode, project.preparation
        )
        if revision_version not in self.revision_versions_for_mode(project.input_mode, project.preparation):
            revision_version = self.default_revision_version(project.input_mode, project.preparation)
        camera_clauses = project.camera_clauses
        if not camera_clauses:
            camera_clauses = extract_compiled_camera_clauses(project.current_prompt)
        current = replace(
            project,
            revision_version=revision_version,
            camera_clauses=camera_clauses,
        )
        if current != project:
            current = self.projects.save(current)
        for attempt in current.attempts:
            if (
                attempt.status in {H3RenderAttemptStatus.RUNNING, H3RenderAttemptStatus.CANCEL_PENDING}
                and (current.project_id, attempt.attempt_id) not in self._claimed
            ):
                current = self._refresh_detached_attempt(current, current.attempt(attempt.attempt_id))
        return current

    def _refresh_detached_attempt(self, project: H3RenderProject, attempt: H3RenderAttempt) -> H3RenderProject:
        assert attempt.execution_id is not None
        try:
            history = self.comfy.get_history(attempt.execution_id)
            if not isinstance(history, Mapping):
                return project
            if not history:
                if self.comfy.get_queue().find(attempt.execution_id) is not None:
                    return project
                # A render can finish between the first history read and the queue
                # snapshot. Re-read before declaring a persisted execution lost.
                history = self.comfy.get_history(attempt.execution_id)
                if not isinstance(history, Mapping):
                    return project
                if not history:
                    updated = attempt.fail(
                        "Exécution ComfyUI introuvable dans la file et l’historique "
                        f"({attempt.execution_id}). Le suivi de cet essai est terminé ; "
                        "son prompt et ses réglages sont conservés."
                    )
                    return self.projects.save(project.replace_attempt(updated))
            record = history.get(attempt.execution_id)
            status = record.get("status") if isinstance(record, Mapping) else None
            if not isinstance(status, Mapping):
                return project
            completed = status.get("completed") is True
            name = status.get("status_str")
            if not completed and name not in {"error", "interrupted"}:
                return project
            if completed and name == "success":
                recipe = self.recipe_for_attempt(project, attempt)
                output_ref = extract_bound_video(
                    record,
                    node_id=recipe.output_node_id,
                    history_field=recipe.output_history_field,
                )
                content = self.comfy.download_output(
                    filename=output_ref["filename"],
                    subfolder=output_ref["subfolder"],
                    folder_type=output_ref["type"],
                )
                _validate_mp4(content, output_ref["filename"])
                asset = self.assets.create(content, media_type="video/mp4", source_run_id=project.project_id)
                frames, warnings = self._import_keyframes(record, project.project_id, attempt)
                updated = attempt.succeed(asset.asset_id, frames, warnings)
            elif name == "interrupted":
                updated = attempt.cancel()
            else:
                updated = attempt.fail(f"ComfyUI execution failed after restart: {status}")
        except Exception:
            return project
        updated_project = project.replace_attempt(updated)
        if updated.status is H3RenderAttemptStatus.SUCCEEDED:
            updated_project = updated_project.use_feedback(attempt.attempt_id)
        return self.projects.save(updated_project)

    def _report(
        self,
        call_id: str | None,
        outcome: LlmCallApplicationOutcome,
        error: Exception | None = None,
    ) -> None:
        if self.application_outcomes is None or call_id is None:
            return
        self.application_outcomes.report_application_outcome(
            call_id,
            outcome,
            error_type=type(error).__name__ if error else None,
            error_message=str(error) if error else None,
        )

    def _stop_remote_after_failure(
        self,
        project: H3RenderProject,
        attempt: H3RenderAttempt,
        error: Exception,
    ) -> H3RenderProject:
        assert attempt.execution_id is not None
        execution_error = _error(error)
        try:
            self.comfy.cancel_execution(attempt.execution_id)
        except Exception as cancellation_error:
            attempt = attempt.cancel_pending(
                f"{execution_error}; remote cancellation failed: {_error(cancellation_error)}"
            )
        else:
            attempt = attempt.fail(execution_error)
        return self.projects.save(project.replace_attempt(attempt))

    def _stop_unpersisted_submission(
        self,
        project: H3RenderProject,
        attempt: H3RenderAttempt,
        execution_id: str,
        workflow_digest: str,
        error: Exception,
    ) -> H3RenderProject:
        submitted = attempt.start(execution_id, workflow_digest)
        execution_error = _error(error)
        try:
            self.comfy.cancel_execution(execution_id)
        except Exception as cancellation_error:
            submitted = submitted.cancel_pending(
                f"{execution_error}; remote cancellation failed: {_error(cancellation_error)}"
            )
        else:
            submitted = submitted.fail(execution_error)
        return self.projects.save(project.replace_attempt(submitted))


def extract_prompt_cut_times_ms(prompt: str) -> tuple[int, ...]:
    if not isinstance(prompt, str):
        return ()
    values = {
        (int(match.group("minutes")) * 60 + int(match.group("seconds"))) * 1000
        + int(match.group("milliseconds"))
        for match in _SHOT_CUT_RE.finditer(prompt)
    }
    return tuple(sorted(value for value in values if value > 0))


def extract_plan_cut_times_ms(content: str) -> tuple[int, ...]:
    if not isinstance(content, str) or not content.strip():
        return ()
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        return ()
    if not isinstance(value, Mapping):
        return ()
    candidates: object = value.get("hard_cut_times_ms")
    if not isinstance(candidates, list):
        candidates = value.get("shot_starts_ms")
    derived = value.get("derived_timing")
    if not isinstance(candidates, list) and isinstance(derived, Mapping):
        candidates = derived.get("cut_times_ms")
    if isinstance(candidates, list):
        values = {
            item for item in candidates
            if not isinstance(item, bool) and isinstance(item, int) and item > 0
        }
        if values:
            return tuple(sorted(values))
    shots = value.get("shots")
    if not isinstance(shots, list) or len(shots) < 2:
        return ()
    elapsed = 0
    values: list[int] = []
    for shot in shots[:-1]:
        if not isinstance(shot, Mapping):
            return ()
        duration = shot.get("duration_ms")
        if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0:
            return ()
        elapsed += duration
        values.append(elapsed)
    return tuple(values)


def plan_keyframe_timestamps_ms(
    duration_ms: int,
    cut_times_ms: tuple[int, ...],
    *,
    margin_ms: int = 500,
    maximum: int = 8,
) -> tuple[int, ...]:
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or duration_ms <= 0:
        raise ValueError("duration_ms must be positive")
    if isinstance(margin_ms, bool) or not isinstance(margin_ms, int) or margin_ms <= 0:
        raise ValueError("margin_ms must be positive")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 2:
        raise ValueError("maximum must be at least two")
    cuts = tuple(sorted({value for value in cut_times_ms if 0 < value < duration_ms}))
    final_ms = max(0, duration_ms - round(1000 / VIDEO_FPS))
    if not cuts:
        count = min(5, maximum)
        if count == 1:
            return (0,)
        return tuple(round(final_ms * index / (count - 1)) for index in range(count))
    pair_budget = max(0, (maximum - 2) // 2)
    if len(cuts) > pair_budget:
        if pair_budget == 1:
            cuts = (cuts[len(cuts) // 2],)
        else:
            cuts = tuple(cuts[round(index * (len(cuts) - 1) / (pair_budget - 1))] for index in range(pair_budget))
    values = [0]
    all_boundaries = (0, *cuts, duration_ms)
    for index, cut in enumerate(cuts, 1):
        previous = all_boundaries[index - 1]
        following = all_boundaries[index + 1]
        before = max(previous + 1, cut - margin_ms)
        after = min(following - 1, cut + margin_ms)
        if before == cut:
            before = max(previous + 1, cut - 1)
        if after == cut:
            after = min(following - 1, cut + 1)
        values.extend((before, after))
    values.append(final_ms)
    return tuple(sorted(set(max(0, min(final_ms, value)) for value in values)))


def disable_non_diegetic_music(prompt: str) -> str:
    matches = list(_FIELD_RE.finditer(prompt))
    music = next((match for match in matches if match.group(1).lower() == "non_diegetic_music"), None)
    if music is None:
        return prompt.rstrip() + "\nnon_diegetic_music:\nN/A"
    next_match = next((match for match in matches if match.start() > music.start()), None)
    end = next_match.start() if next_match else len(prompt)
    return prompt[:music.end()] + "N/A\n" + prompt[end:].lstrip("\r\n")


def h3_prompt_duration_warning(
    prompt: str,
    render_duration_seconds: float,
) -> str | None:
    """Describe a prompt/render duration mismatch without blocking the render."""

    if not isinstance(prompt, str):
        raise TypeError("prompt must be a string")
    if isinstance(render_duration_seconds, bool) or not isinstance(
        render_duration_seconds,
        (int, float),
    ):
        raise TypeError("render_duration_seconds must be a number")
    patterns = (
        r"\btarget video lasts\s+([0-9]+(?:\.[0-9]+)?)\s+seconds?\b",
        r"\baligns with the\s+([0-9]+(?:\.[0-9]+)?)-second mark of the target video\b",
        r"\bone continuous(?: approximately)?\s+([0-9]+(?:\.[0-9]+)?)-second shot\b",
        r"\btarget video is(?: approximately)?\s+([0-9]+(?:\.[0-9]+)?)[ -]second\b",
    )
    values = tuple(dict.fromkeys(
        float(match.group(1))
        for pattern in patterns
        for match in re.finditer(pattern, prompt, flags=re.IGNORECASE)
    ))
    requested = float(render_duration_seconds)
    if not values or all(abs(value - requested) < 0.001 for value in values):
        return None
    prompt_duration = " / ".join(_format_seconds(value) for value in values)
    return (
        f"Prompt compilé pour {prompt_duration} s · rendu configuré pour "
        f"{_format_seconds(requested)} s. Les timestamps et l’ancre finale ne sont "
        "pas réécrits automatiquement."
    )


def canonicalize_h3_revision(
    current_prompt: str,
    candidate: str,
    input_mode: H3RenderInputMode,
    *,
    camera_clauses: tuple[str, ...] = (),
    combat_sequence: bool = False,
    combat_version: str | None = None,
    classic_cinematic: bool = False,
    sensual_cinematic: bool = False,
) -> str:
    current = _bounded_text(current_prompt, "current prompt", 60_000).replace("\r\n", "\n")
    value = _bounded_text(candidate, "candidate prompt", 60_000).replace("\r\n", "\n")
    if classic_cinematic or sensual_cinematic or combat_version == "1.3.0":
        from .cinematic_core_v1 import preserve_camera_layout
        preserve_camera_layout(current, value)
        if camera_clauses and extract_compiled_camera_clauses(value) != camera_clauses:
            raise ValueError("Conservez l’ordre des phases caméra approuvées.")
    if input_mode is H3RenderInputMode.REF2VA:
        header, current_body = _split_ref2v_header(current)
        _, candidate_body = _split_ref2v_header(value, required=False)
        if not candidate_body.strip():
            candidate_body = current_body
        result = f"{header}\n\n{candidate_body.strip()}"
        _validate_revision_camera_clauses(result, camera_clauses)
        if classic_cinematic or sensual_cinematic:
            if sensual_cinematic:
                from .sensual_cinematic import prompt_errors
            else:
                from .classic_cinematic import prompt_errors
            _preserve_sequence_cuts(current, result)
            errors = prompt_errors(result, input_mode.value)
        elif combat_sequence:
            from .combat_sequence import prompt_errors
            _preserve_combat_cuts(current, result)
            errors = prompt_errors(result, input_mode.value, combat_version)
        elif "[Shot 2]" in current:
            from .direct_ref2v_multishot_prompt_v2 import lint_direct_ref2v_multishot_prompt_v2
            if re.findall(r"(?m)^\[Shot \d+\](?: At [^\n,]+,)?", current) != re.findall(r"(?m)^\[Shot \d+\](?: At [^\n,]+,)?", result):
                raise ValueError("La révision doit conserver les plans et leurs instants de coupe.")
            errors = lint_direct_ref2v_multishot_prompt_v2(result, preserve_h3_landmarks=True)
        else:
            errors = lint_direct_ref2v_prompt(result)
        if errors:
            raise ValueError(" ".join(dict.fromkeys(errors)))
        return result
    current_start = re.search(r"(?im)^integrated_multimodal_description:\s*", current)
    candidate_start = re.search(r"(?im)^integrated_multimodal_description:\s*", value)
    if current_start is None or candidate_start is None:
        raise ValueError("H3 prompt must contain integrated_multimodal_description")
    header = current[:current_start.start()].strip()
    body = value[candidate_start.start():].strip()
    result = f"{header}\n\n{body}" if header else body
    matches = list(_FIELD_RE.finditer(result))
    names = [match.group(1).lower() for match in matches]
    if names != ["integrated_multimodal_description", "overall_soundscape", "non_diegetic_music"]:
        raise ValueError("H3 prompt must contain the three canonical fields exactly once and in order")
    _validate_revision_camera_clauses(result, camera_clauses)
    if classic_cinematic or sensual_cinematic:
        if sensual_cinematic:
            from .sensual_cinematic import prompt_errors
        else:
            from .classic_cinematic import prompt_errors
        _preserve_sequence_cuts(current, result)
        errors = prompt_errors(result, input_mode.value)
        if errors:
            raise ValueError(" ".join(errors))
    elif combat_sequence:
        from .combat_sequence import prompt_errors
        _preserve_combat_cuts(current, result)
        errors = prompt_errors(result, input_mode.value, combat_version)
        if errors:
            raise ValueError(" ".join(errors))
    errors = tuple(
        issue.message
        for issue in lint_h3_prompt(H3ProtocolMode(input_mode.value), result)
        if issue.severity is H3IssueSeverity.ERROR
    )
    if errors:
        raise ValueError(" ".join(dict.fromkeys(errors)))
    return result


def _preserve_sequence_cuts(current: str, candidate: str) -> None:
    pattern = r"(?m)^(?:\[Shot \d+\]|Shot \d+:)(?: At [^\n,]+,)?"
    if re.findall(pattern, current) != re.findall(pattern, candidate):
        raise ValueError("Conservez le nombre de plans et les coupures de cet atelier.")
    duration = re.search(r"The target video lasts \d+(?:\.\d+)? seconds\.", current)
    if duration and duration.group() not in candidate:
        raise ValueError("Conservez la durée du prompt courant.")


_preserve_combat_cuts = _preserve_sequence_cuts


def _combat_action_policy(project) -> str:
    from .combat_sequence import action_policy
    return action_policy(project.combat_settings, project.preparation.version)


def _validate_revision_camera_clauses(prompt: str, camera_clauses: tuple[str, ...]) -> None:
    if not camera_clauses:
        return  # Legacy revisions do not supply a compiler-owned camera contract.
    # A timed static clause contains the untimed static sentence as a suffix.
    # Count whole parsed directives, not occurrences of that substring.
    actual = Counter(extract_compiled_camera_clauses(prompt))
    expected = Counter(camera_clauses)
    for clause, count in expected.items():
        if actual[clause] != count:
            raise ValueError(
                "compiled camera clause must remain present exactly "
                f"{count} time(s): {clause}"
            )
    if actual - expected:
        raise ValueError("unexpected compiled camera clause; keep only the camera tokens in the editable prompt")


def protect_h3_revision_camera(
    prompt: str,
    camera_clauses: tuple[str, ...],
) -> str:
    """Replace compiler-owned camera clauses with stable editor tokens."""

    value = prompt
    for index, clause in enumerate(camera_clauses, 1):
        token = f"[[camera:camera_{index}]]"
        if clause not in value:
            raise ValueError(f"compiled camera clause is missing: {clause}")
        value = value.replace(clause, token, 1)
    return value


def _migrate_legacy_camera_contract(prompt: str) -> tuple[str, tuple[str, ...]]:
    """Normalize the one free-form static label accepted by the former validator."""

    clauses = extract_compiled_camera_clauses(prompt)
    if clauses:
        return prompt, clauses
    migrated, _ = re.subn(
        r"(?i)\bCamera movement:\s*static\.",
        "The camera holds a static shot.",
        prompt,
    )
    return migrated, extract_compiled_camera_clauses(migrated)


def compile_h3_revision_camera(
    candidate: str,
    previous_clauses: tuple[str, ...],
    camera_clauses: tuple[str, ...],
) -> str:
    """Compile stable editor tokens and reject invented camera placeholders."""

    if len(previous_clauses) != len(camera_clauses):
        raise ValueError("camera revision must preserve the number of compiled directives")
    value = candidate
    for index, clause in enumerate(previous_clauses, 1):
        token = f"[[camera:camera_{index}]]"
        if token not in value and clause in value:
            value = value.replace(clause, token, 1)
    known = {f"[[camera:camera_{index}]]" for index in range(1, len(camera_clauses) + 1)}
    found = set(re.findall(r"\[\[camera:camera_[1-9][0-9]*\]\]", value))
    if found - known:
        raise ValueError("the revised prompt contains an unknown camera token")
    for index, clause in enumerate(camera_clauses, 1):
        token = f"[[camera:camera_{index}]]"
        if value.count(token) != 1:
            raise ValueError(f"{token} must appear exactly once in the revised prompt")
        # Some repair answers copy both the token and its literal expansion.
        # Remove only an exact adjacent copy belonging to this same token.
        copies = sorted({previous_clauses[index - 1], clause}, key=len, reverse=True)
        redundant = re.compile(
            re.escape(token) + r"\s*(?:" + "|".join(re.escape(copy) for copy in copies) + r")(?=\s|$)"
        )
        value = redundant.sub(lambda _match: token, value, count=1)
        value = value.replace(token, clause, 1)
    return value


def _split_ref2v_header(
    prompt: str,
    *,
    required: bool = True,
) -> tuple[str, str]:
    first, separator, rest = prompt.partition("\n\n")
    lines = tuple(line.strip() for line in first.splitlines() if line.strip())
    if separator and lines and all("<Picture " in line for line in lines):
        return first.strip(), rest.strip()
    if required:
        raise ValueError("Ref2V prompt is missing its canonical Picture header")
    return "", prompt.strip()


def keyframe_label(
    timestamp_ms: int,
    timestamps: tuple[int, ...],
    cut_times_ms: tuple[int, ...] = (),
) -> str:
    if timestamp_ms == timestamps[0]:
        return "début"
    if timestamp_ms == timestamps[-1]:
        return "fin"
    if cut_times_ms:
        closest = min(cut_times_ms, key=lambda value: abs(value - timestamp_ms))
        if timestamp_ms < closest:
            return "avant coupe"
        if timestamp_ms > closest:
            return "après coupe"
    return "échantillon de continuité"


def _attempt_context(attempt: H3RenderAttempt | None) -> str:
    if attempt is None:
        return "No rendered attempt selected."
    return json.dumps({
        "attempt_id": attempt.attempt_id,
        "render_recipe": (attempt.recipe.recipe_id + "@" + attempt.recipe.version) if attempt.recipe else "legacy",
        "bunny": ({"turbo_enabled": attempt.bunny.turbo_enabled, "base_steps": attempt.bunny.base_steps,
                   "coarse_steps": attempt.bunny.coarse_steps, "refine_steps": attempt.bunny.refine_steps,
                   **({"lora_second_strength": attempt.bunny.lora_second_strength}
                      if attempt.video_loras is None else {})} if attempt.bunny else None),
        "prompt_used": attempt.effective_prompt,
        "initial_megapixels": attempt.initial_megapixels,
        "force_upscale": attempt.force_upscale,
        "upscale_bypassed": attempt.upscale_bypassed,
        "aspect_ratio": attempt.settings.aspect_ratio.value,
        "megapixels": attempt.settings.megapixels,
        "duration_seconds": attempt.settings.duration_seconds,
        "effective_duration_seconds": attempt.settings.effective_duration_seconds,
        "steps": attempt.settings.steps,
        "seed": str(attempt.settings.seed),
        "music_enabled": attempt.music_enabled,
        "spectrum_enabled": attempt.spectrum_enabled,
        "video_lora": (
            {
                "name": attempt.video_lora.name,
                "strength": attempt.video_lora.strength,
                "clip_last_layer": attempt.video_lora.clip_last_layer,
                "overlay_version": attempt.video_lora.overlay_version,
            }
            if attempt.video_lora is not None
            else None
        ),
        "video_loras": asdict(attempt.video_loras) if attempt.video_loras is not None else None,
        "keyframe_timestamps_ms": list(attempt.keyframe_timestamps_ms),
    }, ensure_ascii=False, indent=2)


def _extract_bound_image(history: Mapping[str, Any], node_id: str, history_field: str) -> dict[str, str]:
    outputs = history.get("outputs")
    node = outputs.get(node_id) if isinstance(outputs, Mapping) else None
    values = node.get(history_field) if isinstance(node, Mapping) else None
    if not isinstance(values, list) or not values or not isinstance(values[0], Mapping):
        raise ValueError(f"ComfyUI keyframe node {node_id!r} has no output")
    value = values[0]
    filename = value.get("filename")
    subfolder = value.get("subfolder", "")
    folder_type = value.get("type", "output")
    if not isinstance(filename, str) or not filename:
        raise ValueError("ComfyUI keyframe output has no filename")
    if not isinstance(subfolder, str) or not isinstance(folder_type, str):
        raise ValueError("ComfyUI keyframe output has invalid location fields")
    return {"filename": filename, "subfolder": subfolder, "type": folder_type}


def _image_media_type(content: bytes) -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    raise ValueError("keyframe output is not a supported image")


def _format_seconds(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _validate_mp4(content: bytes, filename: str) -> None:
    if not filename.lower().endswith(".mp4"):
        raise ValueError("ComfyUI output is not an MP4 video")
    if len(content) < 12 or content[4:8] != b"ftyp":
        raise ValueError("ComfyUI output has no MP4 signature")


def _revision_version(
    value: str | H3RenderRevisionVersion,
) -> H3RenderRevisionVersion:
    try:
        return H3RenderRevisionVersion(value)
    except (TypeError, ValueError) as error:
        raise ValueError("unsupported H3 render revision version") from error


def _camera_contract_prompt(camera_clauses: tuple[str, ...]) -> str:
    motions = ", ".join(value.value for value in H3CameraMotion)
    clauses = "\n".join(
        f"- [[camera:camera_{index}]] = {clause}"
        for index, clause in enumerate(camera_clauses, 1)
    ) or "- No compiled camera directive is present."
    return (
        f"{clauses}\n"
        "When explicitly changing camera, camera_directives must be a JSON array with "
        "one object per token, even when there is only one token. Each object has exactly "
        "id, start_ms, motion, amplitude, speed, target_clause. "
        f"Allowed motion values: {motions}. Amplitude: small, large or null. "
        "Speed: slow, fast or null.\n"
        "Motion-specific requirements: for shake.slightly, shake.strongly and pov, "
        "amplitude, speed and target_clause must all be null. Their dynamics are already built in. "
        "For static_shot, amplitude and speed must be null; a target_clause is allowed. "
        "For the other motions, modifiers and target_clause are optional.\n"
        "Keep visibility constraints in the scene/action prose when a motion cannot accept a target: "
        "for example, 'Both people and the doorway remain visible together.' This is permitted scene "
        "composition, not a second camera instruction. If the compiled movement remains unchanged, "
        "camera_directives may be null.\n"
        "For motions that accept a target, target_clause must be null/empty or begin with exactly one "
        "of these spatial or visual continuations: to, toward, onto, into, from, behind, beside, "
        "above, below, away from, around, along, across, past, through, following, keeping, "
        "maintaining, revealing, showing, centered on, focused on, ending on, framing, holding, "
        "leaving, placing, as, while, until, with. target_clause must not contain camera-control "
        "terms or their inflections: camera, zoom, push, pull, pan, truck, tilt, pedestal, arc, "
        "track, shake, POV, point-of-view, roll, dolly, orbit, crane, handheld.\n"
        "Valid one-token JSON shape: "
        '[{"id":"camera_1","start_ms":0,"motion":"push.in","amplitude":"small",'
        '"speed":"slow","target_clause":"toward the rider as she passes"}]\n'
        "Valid slight-shake directive: "
        '[{"id":"camera_1","start_ms":0,"motion":"shake.slightly","amplitude":null,'
        '"speed":null,"target_clause":null}]'
    )


def _revision_camera_clauses(
    value: object,
    current: tuple[str, ...],
    *, continuous_phases: bool = False,
) -> tuple[str, ...]:
    if value is None:
        return current
    if isinstance(value, Mapping) and len(current) == 1:
        value = [value]
    if not isinstance(value, list) or len(value) != len(current):
        raise ValueError(
            "camera_directives must be null or contain one object per camera token"
        )
    clauses: list[str] = []
    previous_start = -1
    expected_fields = {
        "id",
        "start_ms",
        "motion",
        "amplitude",
        "speed",
        "target_clause",
    }
    for index, item in enumerate(value, 1):
        if not isinstance(item, Mapping) or set(item) != expected_fields:
            raise ValueError("camera directive fields do not match revision 0.2.0")
        expected_id = f"camera_{index}"
        if item.get("id") != expected_id:
            raise ValueError(f"camera directive {index} must use id {expected_id}")
        start_ms = item.get("start_ms")
        if isinstance(start_ms, bool) or not isinstance(start_ms, int) or start_ms < 0:
            raise ValueError("camera start_ms must be a non-negative integer")
        if continuous_phases:
            stamp = re.match(r"At (\d{2}):(\d{2})\.(\d{3}),", current[index - 1])
            expected_start = (int(stamp[1]) * 60000 + int(stamp[2]) * 1000 + int(stamp[3])) if stamp else 0
            if start_ms != expected_start:
                raise ValueError("Preserve the existing cut timestamp or untimed continuous phase (start_ms 0).")
        if not continuous_phases and start_ms < previous_start:
            raise ValueError("camera directives must remain chronological")
        previous_start = start_ms
        try:
            directive = H3CameraDirective(
                directive_id=expected_id,
                motion=H3CameraMotion(item.get("motion")),
                amplitude=(
                    H3CameraAmplitude(item["amplitude"])
                    if item.get("amplitude") is not None else None
                ),
                speed=(
                    H3CameraSpeed(item["speed"])
                    if item.get("speed") is not None else None
                ),
                target_clause=(item.get("target_clause") or ""),
            )
        except (TypeError, ValueError) as error:
            hint = ""
            if "does not accept a target clause" in str(error):
                hint = ". Set target_clause to null and preserve the visibility constraint in the scene/action prose."
            elif "does not accept amplitude or speed modifiers" in str(error):
                hint = ". Set amplitude and speed to null; this motion already defines its dynamics."
            raise ValueError(f"invalid camera directive {expected_id}: {error}{hint}") from error
        clause = compile_camera_motion(directive)
        if start_ms:
            minutes, remainder = divmod(start_ms, 60_000)
            seconds, milliseconds = divmod(remainder, 1000)
            clause = f"At {minutes:02d}:{seconds:02d}.{milliseconds:03d}, {clause}"
        clauses.append(clause)
    return tuple(clauses)


def _revision_candidate(raw: str) -> str | None:
    try:
        value = _decode_json(raw)
    except ValueError:
        candidate = raw.strip()
    else:
        prompt = value.get("prompt")
        candidate = prompt.strip() if isinstance(prompt, str) else raw.strip()
    return candidate[:60_000] if candidate else None


def _revision_error(error: Exception, draft: str | None) -> str:
    message = _error(error)
    if not draft or "camera movement must come" not in message:
        return message
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", draft):
        if "[[camera:" in sentence:
            continue
        if re.search(
            r"(?i)\b(?:camera|lens)\b|\b(?:zoom|pan|tilt|tracking|orbit|dolly|crane)(?:s|ed|ing)?\b",
            sentence,
        ):
            return f"{message} Clause refusée : {sentence.strip()[:500]}"
    return message


def _decode_json(raw: str) -> dict[str, Any]:
    value = raw.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.IGNORECASE)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("model response is not valid JSON") from error
    if not isinstance(parsed, dict):
        raise ValueError("model response must be a JSON object")
    return parsed


def _string_array(value: object, label: str, maximum: int) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{label} must be a list containing at most {maximum} values")
    return tuple(_bounded_text(item, label, 2000) for item in value)


def _revision_audacity(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 3:
        raise ValueError("creative_audacity must be between 0 and 3")
    return value


def video_revision_audacity_policy(value: int) -> str:
    value = _revision_audacity(value)
    common = (
        "Work inside the existing duration, reference roles, identities and shot structure. "
        "Rebalance or replace weak beats instead of mechanically stacking more actions. "
    )
    if value == 0:
        return common + (
            "Make only the correction explicitly requested; volunteer no new action, staging, "
            "environmental event or camera change."
        )
    if value == 1:
        return common + (
            "You may add one subtle, theme-compatible enrichment when it directly helps the "
            "requested correction, but keep the current direction dominant."
        )
    if value == 2:
        return common + (
            "Take an assertive initiative: strengthen action density or staging with one clear "
            "signature beat, while keeping every addition subordinate and physically achievable."
        )
    return common + (
        "Take a bold but coherent initiative: diagnose empty or slow passages, reshape the timing "
        "around one strong signature beat and at most one supporting effect. This selected level is "
        "explicit authorization to revise the canonical camera directives when a motivated camera "
        "change materially improves pacing; never write free camera prose."
    )


def _bounded_text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    result = value.strip()
    if len(result) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return result


def _error(error: Exception) -> str:
    detail = str(error).strip()
    return f"{type(error).__name__}: {detail}" if detail else type(error).__name__


__all__ = [
    "H3RenderService",
    "H3RenderStreamEvent",
    "canonicalize_h3_revision",
    "derive_h3_render_input_mode",
    "disable_non_diegetic_music",
    "extract_plan_cut_times_ms",
    "extract_prompt_cut_times_ms",
    "plan_keyframe_timestamps_ms",
    "video_revision_audacity_policy",
]
