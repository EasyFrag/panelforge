"""Conversational prompt iteration and Latent Speed rendering for H3 Base."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
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

from .minimax_h3_protocol import (
    H3IssueSeverity,
    H3ProtocolMode,
    compile_camera_motion,
    extract_compiled_camera_clauses,
    lint_h3_prompt,
)
from .direct_ref2v_prompt import lint_direct_ref2v_prompt
from .prompt_lab import (
    CompletionRequest,
    ImageInput,
    LlmCallApplicationOutcome,
    LlmCallApplicationOutcomeReporter,
    MultimodalGateway,
    StreamEventKind,
    StreamPhase,
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

Camera tokens such as [[camera:camera_1]] are application-owned. Copy every supplied token exactly once at the same chronological position and write no other camera, lens, framing, zoom, pan, tilt, tracking, orbit, dolly or crane prose. When the user does not explicitly request a camera change, camera_directives must be null. When the user explicitly requests a camera change, return one object per supplied token in the same order with exactly id, start_ms, motion, amplitude, speed and target_clause. Use only the motion enum shown in the CAMERA CONTRACT; use null for absent amplitude, speed or target_clause. Never add or remove a camera token.

GENERATED KEYFRAMES are visual evidence sampled away from expected cut boundaries. Compare them with the user's goal and the exact render settings. They reveal composition, continuity and visible motion states, but not voice quality, music, sound, fine lip sync or everything occurring between samples. Never claim to have heard the video. Treat the newest user message as authoritative for audiovisual problems that keyframes cannot prove.

Keep H3 prose chronological, physically achievable and concise. Each timed event appears once. Maintain object-state consistency, clean dialogue tags and continuous-motion constraints where requested. Do not introduce labels such as <Image N>, @image or <Subject N>. Do not output Markdown or text outside the JSON."""

_REF2V_REVISION_SYSTEM = """You are a collaborative MiniMax H3 Ref2V prompt editor.
Return raw JSON only, with exactly these fields:
{"message":"concise helpful reply in French","questions":["up to three useful questions"],"prompt":"complete standalone English MiniMax H3 Ref2V prompt","recommendations":["optional concise advice"]}

The complete prompt is always required and immediately runnable. Rewrite the CURRENT H3 PROMPT directly; never return a Brief, action plan, patch or diff. Preserve the application-owned opening <Picture N> reference rules exactly, followed by the scene setup, Shot 1, overall_soundscape and non_diegetic_music. Preserve every explicit quoted dialogue unless the user explicitly asks to change it. Never invent, remove, renumber or reinterpret a reference.

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


class H3RenderComfy(Protocol):
    def list_lora_models(self) -> tuple[str, ...]: ...
    def upload_image(self, content: bytes, *, filename: str, subfolder: str = "") -> UploadedImage: ...
    def submit_workflow(self, workflow: Mapping[str, Any]) -> str: ...
    def get_history(self, prompt_id: str) -> dict[str, Any]: ...
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
        video_lora: H3VideoLoraSelection | None = None,
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
    def keyframe_output_nodes(self, count: int) -> tuple[str, ...]: ...
    def build_workflow(
        self,
        *,
        source_images: tuple[str, ...],
        prompt: str,
        settings: VideoLabSettings,
        output_filename_prefix: str,
        keyframe_indices: tuple[int, ...],
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
        comfy: H3RenderComfy,
        assets: H3RenderAssets,
        projects: H3RenderProjects,
        sessions: H3RenderSessions,
        compositions: H3RenderCompositions,
        application_outcomes: LlmCallApplicationOutcomeReporter | None = None,
        run_timeout: float = 3600.0,
        poll_interval: float = 1.0,
        project_id_factory: Callable[[], str] | None = None,
        turn_id_factory: Callable[[], str] | None = None,
        attempt_id_factory: Callable[[], str] | None = None,
        seed_factory: Callable[[], int] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if run_timeout <= 0 or poll_interval <= 0:
            raise ValueError("timeouts must be positive")
        self.gateway = gateway
        self.workflow = workflow
        self.ref2v_workflow = ref2v_workflow
        self.comfy = comfy
        self.assets = assets
        self.projects = projects
        self.sessions = sessions
        self.compositions = compositions
        self.application_outcomes = application_outcomes
        self.run_timeout = run_timeout
        self.poll_interval = poll_interval
        self._project_id_factory = project_id_factory or (lambda: f"h3-render-{uuid4().hex}")
        self._turn_id_factory = turn_id_factory or (lambda: f"turn-{uuid4().hex}")
        self._attempt_id_factory = attempt_id_factory or (lambda: f"attempt-{uuid4().hex}")
        self._seed_factory = seed_factory or (lambda: secrets.randbits(64))
        self._monotonic = monotonic
        self._sleep = sleep
        self._lock = RLock()
        self._claimed: set[tuple[str, str]] = set()

    @staticmethod
    def revision_versions_for_mode(
        input_mode: H3RenderInputMode,
    ) -> tuple[H3RenderRevisionVersion, ...]:
        if input_mode is H3RenderInputMode.REF2VA:
            return (H3RenderRevisionVersion.LEGACY,)
        return (
            H3RenderRevisionVersion.CAMERA_LOCKED,
            H3RenderRevisionVersion.LEGACY,
        )

    @classmethod
    def default_revision_version(
        cls,
        input_mode: H3RenderInputMode,
    ) -> H3RenderRevisionVersion:
        return cls.revision_versions_for_mode(input_mode)[0]

    def get_or_create_from_session(self, session_id: str) -> H3RenderProject:
        session = self.sessions.get(session_id)
        composition = self.compositions.get(session_id)
        final = composition.document(CompositionStage.FINAL_PROMPT).active_revision
        if final is None:
            raise ValueError("generate an H3 prompt before opening the render project")
        with self._lock:
            existing = self.projects.find_source_revision(session_id, final.revision_id)
            if existing is not None:
                return self._refresh_detached(existing)
            is_ref2v = (
                session.profile_id == "minimax.h3.ref2v.direct"
                and session.session_mode.value == "direct_multimodal"
            )
            if is_ref2v and self.ref2v_workflow is None:
                raise ValueError("the integrated Ref2V workflow is not configured")
            first = None if is_ref2v else next((value for value in session.references if value.role == "first_frame"), None)
            last = None if is_ref2v else next((value for value in session.references if value.role == "last_frame"), None)
            references = tuple(session.references) if is_ref2v else ()
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
                revision_version=self.default_revision_version(mode),
                camera_clauses=(
                    ()
                    if mode is H3RenderInputMode.REF2VA
                    else extract_compiled_camera_clauses(final.content)
                ),
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
    ) -> H3RenderRecipe | Ref2VRenderRecipe:
        if input_mode is H3RenderInputMode.REF2VA:
            if self.ref2v_workflow is None:
                raise ValueError("the integrated Ref2V workflow is not configured")
            return self.ref2v_workflow
        return self.workflow

    def _recipe_for(
        self,
        project: H3RenderProject,
    ) -> H3RenderRecipe | Ref2VRenderRecipe:
        return self.workflow_for_mode(project.input_mode)

    def new_seed(self) -> int:
        return self._seed_factory()

    def stream_chat(
        self,
        project_id: str,
        message: str,
        *,
        feedback_attempt_id: str | None = None,
        revision_version: str | H3RenderRevisionVersion | None = None,
        include_reasoning: bool = False,
    ) -> Iterator[H3RenderStreamEvent]:
        message = _bounded_text(message, "message", 12_000)
        with self._lock:
            project = self.projects.get(project_id)
            if (
                project.input_mode is not H3RenderInputMode.REF2VA
                and not project.camera_clauses
            ):
                current_prompt, camera_clauses = _migrate_legacy_camera_contract(
                    project.current_prompt
                )
                project = replace(
                    project,
                    current_prompt=current_prompt,
                    camera_clauses=camera_clauses,
                )
            version = _revision_version(
                revision_version or project.revision_version
                or self.default_revision_version(project.input_mode)
            )
            if version not in self.revision_versions_for_mode(project.input_mode):
                raise ValueError(
                    f"revision {version.value} is not available for {project.input_mode.value}"
                )
            project = project.select_revision_version(version)
            if feedback_attempt_id is not None:
                project = project.use_feedback(feedback_attempt_id)
            user = H3RenderTurn(
                turn_id=self._turn_id_factory(),
                role=H3RenderTurnRole.USER,
                content=message,
            )
            project = self.projects.save(project.add_turn(user))
        request = self._completion_request(project, message, include_reasoning)
        parts: list[str] = []
        try:
            for event in self.gateway.stream(request):
                if event.kind is StreamEventKind.DELTA:
                    parts.append(event.text)
                if event.kind is StreamEventKind.TRUNCATED:
                    raw = event.result.content if event.result is not None else "".join(parts)
                    error = ValueError("La réponse du modèle a été tronquée.")
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

    def video_lora_inventory(self) -> tuple[tuple[str, ...], str | None]:
        """Return safe MiniMax video LoRAs without making standard renders depend on discovery."""
        try:
            raw_models = self.comfy.list_lora_models()
        except Exception as error:
            return (), f"Inventaire LoRA vid\u00e9o indisponible : {_error(error)}"
        models: dict[str, str] = {}
        for raw in raw_models:
            try:
                name = canonical_h3_video_lora_name(raw)
            except (TypeError, ValueError):
                continue
            models.setdefault(name.casefold(), name)
        return tuple(sorted(models.values(), key=str.casefold)), None

    def prepare_attempt(
        self,
        project_id: str,
        *,
        prompt: str,
        settings: VideoLabSettings,
        music_enabled: bool = False,
        video_lora: H3VideoLoraSelection | None = None,
    ) -> H3RenderProject:
        prompt = _bounded_text(prompt, "prompt", 60_000)
        if not isinstance(settings, VideoLabSettings):
            raise TypeError("settings must be VideoLabSettings")
        if not isinstance(music_enabled, bool):
            raise TypeError("music_enabled must be a boolean")
        if video_lora is not None and not isinstance(video_lora, H3VideoLoraSelection):
            raise TypeError("video_lora must be an H3VideoLoraSelection or None")
        with self._lock:
            project = self.projects.get(project_id)
            if video_lora is not None:
                if project.input_mode is H3RenderInputMode.REF2VA:
                    raise ValueError("H3 video LoRA is not available for Ref2V yet")
                models, warning = self.video_lora_inventory()
                if warning is not None:
                    raise ValueError(warning)
                if video_lora.name.casefold() not in {
                    value.casefold() for value in models
                }:
                    raise ValueError("selected H3 video LoRA is not available in ComfyUI")
            recipe = self._recipe_for(project)
            prompt = canonicalize_h3_revision(project.current_prompt, prompt, project.input_mode)
            duration_ms = round(settings.effective_duration_seconds * 1000)
            cuts = extract_prompt_cut_times_ms(prompt) or project.planned_cut_times_ms
            timestamps = plan_keyframe_timestamps_ms(
                duration_ms,
                cuts,
                margin_ms=recipe.keyframe_margin_ms,
                maximum=recipe.maximum_keyframes,
            )
            effective_prompt = prompt if music_enabled else disable_non_diegetic_music(prompt)
            attempt = H3RenderAttempt(
                attempt_id=self._attempt_id_factory(),
                index=len(project.attempts) + 1,
                prompt=prompt,
                effective_prompt=effective_prompt,
                settings=settings,
                music_enabled=music_enabled,
                keyframe_timestamps_ms=timestamps,
                video_lora=video_lora,
            )
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
                if any(value.status in active for value in candidate.attempts):
                    raise ValueError("another H3 Base render is already active")
            return self.projects.save(project.replace_attempt(project.attempt(attempt_id).queue()))

    def execute_attempt(self, project_id: str, attempt_id: str) -> H3RenderProject:
        key = (project_id, attempt_id)
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
            recipe = self._recipe_for(project)
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
                    video_lora=attempt.video_lora,
                )
            workflow_digest = self.projects.save_compiled_workflow(project_id, attempt_id, workflow)
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
    ) -> CompletionRequest:
        recipe = self._recipe_for(project)
        feedback = project.attempt(project.feedback_attempt_id) if project.feedback_attempt_id else None
        version = project.revision_version or self.default_revision_version(project.input_mode)
        camera_locked = (
            project.input_mode is not H3RenderInputMode.REF2VA
            and version is H3RenderRevisionVersion.CAMERA_LOCKED
        )
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
        user_prompt = "\n\n".join((
            f"H3 INPUT MODE (immutable): {project.input_mode.value.upper()}",
            f"CURRENT COMPLETE H3 PROMPT:\n{current_prompt}",
            f"CAMERA CONTRACT:\n{camera_contract}",
            f"RECENT PROJECT CONVERSATION:\n{conversation}",
            f"SELECTED RENDER AND EXACT SETTINGS:\n{selected}",
            (
                "KEYFRAME SAMPLING NOTE:\nFrames around planned cuts are sampled "
                f"{recipe.keyframe_margin_ms} ms before and after each cut, never at the exact boundary."
            ),
            f"NEW USER MESSAGE (authoritative):\n{message}",
        ))
        return CompletionRequest(
            model_id=project.model_id,
            system_prompt=(
                _REF2V_REVISION_SYSTEM
                if project.input_mode is H3RenderInputMode.REF2VA
                else (
                    _H3_REVISION_SYSTEM_CAMERA_LOCKED
                    if camera_locked
                    else _H3_REVISION_SYSTEM_LEGACY
                )
            ),
            user_prompt=user_prompt,
            images=tuple(images),
            temperature=0.25,
            max_tokens=16_384,
            operation_id=(
                "h3.ref2v.render.revision@0.1.0"
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
    ) -> H3RenderProject:
        value = _decode_json(raw)
        expected = {"message", "questions", "prompt", "recommendations"}
        if version is H3RenderRevisionVersion.CAMERA_LOCKED:
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
            if version is H3RenderRevisionVersion.CAMERA_LOCKED:
                camera_clauses = _revision_camera_clauses(
                    value.get("camera_directives"),
                    project.camera_clauses,
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
                camera_clauses=camera_clauses if version is H3RenderRevisionVersion.CAMERA_LOCKED else (),
            )
            assistant = H3RenderTurn(
                turn_id=self._turn_id_factory(),
                role=H3RenderTurnRole.ASSISTANT,
                content=message,
                prompt=prompt,
                questions=questions,
                recommendations=recommendations,
                revision_version=version,
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
        recipe = self._recipe_for(project)
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
            project.input_mode
        )
        if revision_version not in self.revision_versions_for_mode(project.input_mode):
            revision_version = self.default_revision_version(project.input_mode)
        camera_clauses = project.camera_clauses
        if project.input_mode is not H3RenderInputMode.REF2VA and not camera_clauses:
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
        recipe = self._recipe_for(project)
        try:
            history = self.comfy.get_history(attempt.execution_id)
            record = history.get(attempt.execution_id)
            status = record.get("status") if isinstance(record, Mapping) else None
            if not isinstance(status, Mapping):
                return project
            completed = status.get("completed") is True
            name = status.get("status_str")
            if not completed and name != "error":
                return project
            if completed and name == "success":
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


def derive_h3_render_input_mode(first_frame: bool, last_frame: bool) -> H3RenderInputMode:
    if not first_frame and not last_frame:
        return H3RenderInputMode.T2VA
    if first_frame and not last_frame:
        return H3RenderInputMode.I2VA
    if not first_frame:
        return H3RenderInputMode.L2VA
    return H3RenderInputMode.FL2VA


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


def canonicalize_h3_revision(
    current_prompt: str,
    candidate: str,
    input_mode: H3RenderInputMode,
    *,
    camera_clauses: tuple[str, ...] = (),
) -> str:
    current = _bounded_text(current_prompt, "current prompt", 60_000).replace("\r\n", "\n")
    value = _bounded_text(candidate, "candidate prompt", 60_000).replace("\r\n", "\n")
    if input_mode is H3RenderInputMode.REF2VA:
        header, current_body = _split_ref2v_header(current)
        _, candidate_body = _split_ref2v_header(value, required=False)
        if not candidate_body.strip():
            candidate_body = current_body
        result = f"{header}\n\n{candidate_body.strip()}"
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
    expected_camera = Counter(camera_clauses)
    for clause, expected_count in expected_camera.items():
        if result.count(clause) != expected_count:
            raise ValueError(
                "compiled camera clause must remain present exactly "
                f"{expected_count} time(s): {clause}"
            )
    errors = tuple(
        issue.message
        for issue in lint_h3_prompt(H3ProtocolMode(input_mode.value), result)
        if issue.severity is H3IssueSeverity.ERROR
    )
    if errors:
        raise ValueError(" ".join(dict.fromkeys(errors)))
    return result


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
        "prompt_used": attempt.effective_prompt,
        "aspect_ratio": attempt.settings.aspect_ratio.value,
        "megapixels": attempt.settings.megapixels,
        "duration_seconds": attempt.settings.duration_seconds,
        "effective_duration_seconds": attempt.settings.effective_duration_seconds,
        "steps": attempt.settings.steps,
        "seed": str(attempt.settings.seed),
        "music_enabled": attempt.music_enabled,
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
        "When explicitly changing camera, return camera_directives objects with "
        "id, start_ms, motion, amplitude, speed, target_clause. "
        f"Allowed motion values: {motions}. Amplitude: small, large or null. "
        "Speed: slow, fast or null."
    )


def _revision_camera_clauses(
    value: object,
    current: tuple[str, ...],
) -> tuple[str, ...]:
    if value is None:
        return current
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
        if start_ms < previous_start:
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
            raise ValueError(f"invalid camera directive {expected_id}: {error}") from error
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
]
