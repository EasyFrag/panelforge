"""Conversational prompt design and single-image KREA2 T2I rendering."""

from __future__ import annotations

from panelforge.domain.krea2_sampling import (
    Krea2AssistedSampling,
    Krea2AssistedSettings,
    as_batch_settings,
    sampling_for,
)

from collections.abc import Callable, Iterator, Mapping
from dataclasses import asdict, dataclass, replace
import json
import secrets
from threading import Event, Lock, RLock, Thread
import time
from typing import Any, Protocol
from uuid import uuid4

from panelforge.domain.assets import Asset
from panelforge.domain.krea2_assisted import (
    Krea2AssistedAttempt,
    Krea2AssistedAttemptStatus,
    Krea2AssistedProject,
    Krea2AssistedRecipeDraft,
    Krea2AssistedTurn,
    Krea2AssistedTurnMode,
    Krea2AssistedTurnRole,
)
from panelforge.domain.krea2_batch import (
    KREA2_BATCH_RGTHREE_MAX_SEED,
    Krea2BatchSettings,
    Krea2PromptLanguage,
)
from panelforge.domain.krea2_lab import normalize_krea2_model_name
from panelforge.domain.krea2_style_presets import Krea2StylePreset
from panelforge.domain.krea2_lab import Krea2AspectRatio
from panelforge.domain.krea2_assisted_workflows import DEFAULT_KREA2_ASSISTED_WORKFLOW
from panelforge.domain.recipes import RecipeRef
from panelforge.domain.production import ComputeResource, ProductionWorkload
from panelforge.infrastructure.krea2_batch_recipes import Krea2VisualRecipe

from . import krea2_assisted_v1, krea2_assisted_v2, krea2_assisted_v3
from .production_resources import ResourceWaitCancelled
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


_RENDER_PENDING = {
    Krea2AssistedAttemptStatus.QUEUED,
    Krea2AssistedAttemptStatus.SUBMITTING,
    Krea2AssistedAttemptStatus.RUNNING,
    Krea2AssistedAttemptStatus.CANCEL_PENDING,
}
_AMBIGUOUS_SUBMISSION = (
    "Envoi à ComfyUI interrompu avant confirmation. La file attend : vérifiez la file ComfyUI "
    "avant de retirer cet essai. Le retirer ici n’annule pas un éventuel rendu distant."
)


class _RenderTrackingStopped(Exception):
    pass


class _RenderFailed(Exception):
    pass


def assistance_recipe(version):
    for recipe in (krea2_assisted_v1, krea2_assisted_v2, krea2_assisted_v3):
        if version == recipe.VERSION:
            return recipe
    raise ValueError(f"unsupported KREA2 assistance recipe: {version}")


class Krea2AssistedAssets(Protocol):
    def create(self, content: bytes, *, media_type: str, source_run_id: str | None = None) -> Asset: ...
    def get(self, asset_id: str) -> Asset: ...
    def read_bytes(self, asset_id: str) -> bytes: ...


class Krea2AssistedStore(Protocol):
    def create(self, project: Krea2AssistedProject) -> Krea2AssistedProject: ...
    def save(self, project: Krea2AssistedProject) -> Krea2AssistedProject: ...
    def get(self, project_id: str) -> Krea2AssistedProject: ...
    def list(self, limit: int = 30) -> list[Krea2AssistedProject]: ...
    def save_compiled_workflow(self, project_id: str, attempt_id: str, workflow: dict[str, Any]) -> str: ...


class Krea2AssistedComfy(Protocol):
    def submit_workflow(self, workflow: Mapping[str, Any]) -> str: ...
    def get_history(self, prompt_id: str) -> dict[str, Any]: ...
    def download_output(self, *, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes: ...
    def cancel_execution(self, prompt_id: str) -> object | None: ...


class Krea2AssistedWorkflow(Protocol):
    reference: object
    output_node_id: str
    output_history_field: str
    output_media_type: str
    outputs: tuple[object, ...]

    def build(
        self,
        *,
        prompt: str,
        settings: Krea2BatchSettings,
        seed: int,
        output_prefix: str,
        sidecar_text: str | None = None,
    ) -> dict[str, Any]: ...


class Krea2AssistedResources(Protocol):
    def list_models(self) -> tuple[object, ...]: ...
    def list_loras(self) -> tuple[object, ...]: ...
    def inventory_warnings(self) -> tuple[str, ...]: ...


class Krea2AssistedRecipes(Protocol):
    def current(self) -> tuple[Krea2VisualRecipe, ...]: ...
    def publish_new(self, draft: Krea2AssistedRecipeDraft, settings: Krea2BatchSettings) -> Krea2VisualRecipe: ...


class Krea2StylePresetStore(Protocol):
    def list(self) -> tuple[Krea2StylePreset, ...]: ...
    def get(self, preset_id: str) -> Krea2StylePreset: ...
    def save(self, preset: Krea2StylePreset) -> Krea2StylePreset: ...


class Krea2CreationExporter(Protocol):
    root: object

    def export(
        self,
        project: Krea2AssistedProject,
        attempt: Krea2AssistedAttempt,
        assets: Krea2AssistedAssets,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class Krea2AssistedStreamEvent:
    kind: StreamEventKind
    phase: StreamPhase
    text: str = ""
    progress: float | None = None
    project: Krea2AssistedProject | None = None
    error: str | None = None


class Krea2AssistedService:
    def __init__(
        self,
        *,
        gateway: MultimodalGateway,
        recipes: Krea2AssistedRecipes,
        workflow: Krea2AssistedWorkflow | None,
        comfy: Krea2AssistedComfy,
        assets: Krea2AssistedAssets,
        projects: Krea2AssistedStore,
        resources: Krea2AssistedResources,
        workflows: tuple[Krea2AssistedWorkflow, ...] | None = None,
        exporter: Krea2CreationExporter | None = None,
        presets: Krea2StylePresetStore | None = None,
        application_outcomes: LlmCallApplicationOutcomeReporter | None = None,
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
        self.gateway = gateway
        self.recipes = recipes
        configured_workflows = workflows or ((workflow,) if workflow is not None else ())
        workflow_map: dict[str, Krea2AssistedWorkflow] = {}
        for configured in configured_workflows:
            reference = configured.reference
            key = f"{getattr(reference, 'recipe_id')}@{getattr(reference, 'version')}"
            if key in workflow_map:
                raise ValueError(f"duplicate KREA2 Assisted workflow: {key}")
            workflow_map[key] = configured
        default_key = DEFAULT_KREA2_ASSISTED_WORKFLOW.key
        if workflow_map and default_key not in workflow_map:
            # Keep isolated fakes and legacy callers usable: their sole workflow
            # is the default for that service instance.
            if len(workflow_map) != 1:
                raise ValueError(f"missing default KREA2 Assisted workflow: {default_key}")
            default_key = next(iter(workflow_map))
        self._workflows = workflow_map
        self._default_workflow_key = default_key
        self.workflow = workflow_map.get(default_key)
        self.comfy = comfy
        self.assets = assets
        self.projects = projects
        self.resources = resources
        self.exporter = exporter
        self.presets = presets
        self.application_outcomes = application_outcomes
        self.run_timeout = run_timeout
        self.poll_interval = poll_interval
        self._project_id_factory = project_id_factory or (lambda: f"krea2-create-{uuid4().hex}")
        self._turn_id_factory = turn_id_factory or (lambda: f"turn-{uuid4().hex}")
        self._attempt_id_factory = attempt_id_factory or (lambda: f"attempt-{uuid4().hex}")
        self._seed_factory = seed_factory or (
            lambda: secrets.randbelow(KREA2_BATCH_RGTHREE_MAX_SEED + 1)
        )
        self._monotonic = monotonic
        self._sleep = sleep
        self.work_coordinator = work_coordinator
        self._lock = RLock()
        self._claimed: set[tuple[str, str]] = set()
        self._chatting: set[str] = set()
        self._render_lock = Lock()
        self._render_wake = Event()
        self._render_stop = Event()
        self._render_worker: Thread | None = None
        self._render_queue_error: str | None = None

    @property
    def export_root(self) -> str | None:
        return str(self.exporter.root) if self.exporter is not None else None

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return self.gateway.list_models()

    def workflow_specs(self) -> tuple[dict[str, object], ...]:
        return tuple({
            "id": key,
            "recipe_id": getattr(value.reference, "recipe_id"),
            "version": getattr(value.reference, "version"),
            "label": getattr(value, "display_name", key),
            "description": getattr(value, "description", ""),
            "default_sampling_preset_id": getattr(value, "default_sampling_preset_id", "current"),
            "outputs": [getattr(output, "role", "final") for output in _workflow_outputs(value)],
        } for key, value in self._workflows.items())

    def create_project(
        self,
        *,
        name: str,
        intention: str,
        model_id: str,
        reference_asset_id: str | None = None,
        reference_filename: str | None = None,
        assistance_recipe_version: str = "1.0.0",
        style_preset_id: str | None = None,
    ) -> Krea2AssistedProject:
        assistance_recipe(assistance_recipe_version)
        preset = self._preset(style_preset_id) if style_preset_id else None
        name = _bounded_text(name, "name", 120)
        if isinstance(intention, str) and not intention.strip() and reference_asset_id is not None:
            intention = (
                "À partir de l’image de référence, propose un prompt KREA2 autonome "
                "qui reproduit fidèlement le sujet, la composition, les matières "
                "et l’ambiance visibles."
            )
        intention = _bounded_text(intention, "intention", 12_000)
        model_id = _bounded_text(model_id, "model_id", 300)
        if reference_asset_id is not None:
            asset = self.assets.get(reference_asset_id)
            if not asset.media_type.startswith("image/"):
                raise ValueError("the assisted reference must be an image")
        return self.projects.create(Krea2AssistedProject(
            project_id=self._project_id_factory(),
            name=name,
            assistance_recipe_version=assistance_recipe_version,
            intention=intention,
            model_id=model_id,
            reference_asset_id=reference_asset_id,
            reference_filename=(
                _bounded_text(reference_filename, "reference_filename", 240)
                if reference_filename is not None
                else None
            ),
            warnings=self._inventory_warnings(),
            style_preset=preset, preset_pending=preset is not None,
            render_settings=(Krea2BatchSettings(
                model_name=preset.settings.model_name, loras=preset.settings.loras,
                aspect_ratio=Krea2AspectRatio.PORTRAIT_WIDESCREEN, megapixels=2.1,
            ) if preset else None),
        ))

    def _preset(self, preset_id: str) -> Krea2StylePreset:
        if self.presets is None:
            raise ValueError("Le catalogue de presets n’est pas configuré.")
        return self.presets.get(preset_id)

    def list_style_presets(self) -> tuple[Krea2StylePreset, ...]:
        return self.presets.list() if self.presets else ()

    def save_style_preset(self, project_id: str, attempt_id: str, name: str,
                          *, preset_id: str | None = None, expected_revision: int | None = None) -> Krea2StylePreset:
        with self._lock:
            if self.presets is None:
                raise ValueError("Le catalogue de presets n’est pas configuré.")
            project = self.projects.get(project_id)
            attempt = project.attempt(attempt_id)
            if attempt.status is not Krea2AssistedAttemptStatus.SUCCEEDED or attempt.output_asset_id is None:
                raise ValueError("Un preset doit provenir d’un essai réussi.")
            previous = self._preset(preset_id) if preset_id else None
            if previous is not None and previous.revision != expected_revision:
                raise ValueError("Le preset a changé. Recharge la liste avant de le mettre à jour.")
            return self.presets.save(Krea2StylePreset(
                preset_id=previous.preset_id if previous else f"style-{uuid4().hex}",
                revision=previous.revision + 1 if previous else 1,
                name=_bounded_text(name, "preset name", 120), prompt=attempt.prompt,
                image_asset_id=attempt.output_asset_id, settings=as_batch_settings(attempt.settings),
                source_project_id=project_id, source_attempt_id=attempt_id, source_seed=attempt.seed,
                prompt_language=attempt.conversation_prompt_language,
            ))

    def apply_style_preset(self, project_id: str, preset_id: str | None, *, expected_branch_id: str,
                           current_prompt: str | None, settings: Krea2BatchSettings,
                           seed: int | None) -> Krea2AssistedProject:
        with self._lock:
            project = self.projects.get(project_id)
            self._check_conversation_change(project, expected_branch_id)
            preset = self._preset(preset_id) if preset_id else None
            if preset:
                settings = replace(settings, model_name=preset.settings.model_name, loras=preset.settings.loras)
            prompt = project.current_prompt
            if current_prompt is not None:
                prompt = _bounded_text(current_prompt, "prompt", 40_000) if current_prompt.strip() else None
            return self.projects.save(replace(
                project, style_preset=preset, preset_pending=preset is not None,
                current_prompt=prompt,
                render_settings=settings, render_seed=seed,
            ))

    def get(self, project_id: str) -> Krea2AssistedProject:
        with self._lock:
            return self._refresh_detached(self.projects.get(project_id))

    @staticmethod
    def list_assistance_recipes() -> list[dict[str, str]]:
        return [{"version": recipe.VERSION, "label": recipe.LABEL}
                for recipe in (krea2_assisted_v1, krea2_assisted_v2, krea2_assisted_v3)]

    def list(self, limit: int = 30) -> list[Krea2AssistedProject]:
        with self._lock:
            return [self._refresh_detached(value) for value in self.projects.list(limit)]

    def stream_chat(
        self,
        project_id: str,
        message: str,
        *,
        mode: Krea2AssistedTurnMode = Krea2AssistedTurnMode.CREATION,
        feedback_attempt_id: str | None = None,
        prompt_language: Krea2PromptLanguage | None = None,
        guidance_asset_id: str | None = None,
        guidance_filename: str | None = None,
        model_id: str | None = None,
        include_reasoning: bool = False,
        expected_branch_id: str | None = None,
        current_prompt: str | None = None,
    ) -> Iterator[Krea2AssistedStreamEvent]:
        message = _bounded_text(message, "message", 12_000)
        if model_id is not None:
            model_id = _bounded_text(model_id, "model_id", 300)
        if not isinstance(mode, Krea2AssistedTurnMode):
            raise TypeError("mode must be Krea2AssistedTurnMode")
        if prompt_language is not None and not isinstance(prompt_language, Krea2PromptLanguage):
            raise TypeError("prompt_language must be a Krea2PromptLanguage")
        if guidance_asset_id is not None:
            guidance_asset = self.assets.get(guidance_asset_id)
            if not guidance_asset.media_type.startswith("image/"):
                raise ValueError("the turn guidance must be an image")
            guidance_filename = _bounded_text(
                guidance_filename or "guidance-image",
                "guidance_filename",
                240,
            )
        elif guidance_filename is not None:
            raise ValueError("guidance_filename requires guidance_asset_id")
        with self._lock:
            project = self.projects.get(project_id)
            self._check_conversation_change(project, expected_branch_id)
            if current_prompt is not None:
                prompt = _bounded_text(current_prompt, "prompt", 40_000) if current_prompt.strip() else None
                project = replace(project, current_prompt=prompt)
            assistance_recipe(project.assistance_recipe_version)
            project = project.select_revision_model(
                model_id or project.revision_model_id or project.model_id
            )
            if prompt_language is not None:
                project = project.with_prompt_language(prompt_language)
            if feedback_attempt_id is not None:
                project = project.use_feedback(feedback_attempt_id)
            user_turn = Krea2AssistedTurn(
                turn_id=self._turn_id_factory(),
                assistance_recipe_version=project.assistance_recipe_version,
                mode=mode,
                role=Krea2AssistedTurnRole.USER,
                content=message,
                guidance_asset_id=guidance_asset_id,
                guidance_filename=guidance_filename,
                style_preset=project.style_preset if project.preset_pending else None,
            )
            project = self.projects.save(replace(project, turns=(*project.turns, user_turn)))
            self._chatting.add(project_id)
        parts: list[str] = []
        try:
            request = self._completion_request(project, message, mode, include_reasoning)
            for event in self.gateway.stream(request):
                if event.kind is StreamEventKind.DELTA:
                    parts.append(event.text)
                if event.kind is StreamEventKind.TRUNCATED:
                    raw = event.result.content if event.result is not None else "".join(parts)
                    error = ValueError(truncated_response_message(request.max_tokens))
                    self._report(event.result.call_id if event.result else None, LlmCallApplicationOutcome.REJECTED, error)
                    yield Krea2AssistedStreamEvent(
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
                            mode,
                            event.result.content,
                            event.result.model_id,
                        )
                    except Exception as error:
                        self._report(event.result.call_id, LlmCallApplicationOutcome.REJECTED, error)
                        yield Krea2AssistedStreamEvent(
                            StreamEventKind.COMPLETED,
                            StreamPhase.COMPLETED,
                            event.result.content,
                            1.0,
                            self.projects.get(project_id),
                            _error(error),
                        )
                    else:
                        self._report(event.result.call_id, LlmCallApplicationOutcome.ACCEPTED)
                        yield Krea2AssistedStreamEvent(
                            StreamEventKind.COMPLETED,
                            StreamPhase.COMPLETED,
                            event.result.content,
                            1.0,
                            terminal,
                        )
                    return
                yield Krea2AssistedStreamEvent(event.kind, event.phase, event.text, event.progress)
        except GeneratorExit:
            raise
        except Exception as error:
            yield Krea2AssistedStreamEvent(
                StreamEventKind.COMPLETED,
                StreamPhase.COMPLETED,
                "".join(parts),
                1.0,
                self.projects.get(project_id),
                _error(error),
            )
        finally:
            with self._lock:
                self._chatting.discard(project_id)

    def prepare_attempt(
        self,
        project_id: str,
        *,
        prompt: str,
        settings: Krea2BatchSettings,
        seed: int | None = None,
        expected_branch_id: str | None = None,
        enqueue: bool = False,
    ) -> Krea2AssistedProject:
        prompt = _bounded_text(prompt, "prompt", 40_000)
        if not isinstance(settings, Krea2BatchSettings):
            raise TypeError("settings must be Krea2BatchSettings")
        selected_workflow = self._workflow_for_settings(settings) if self._workflows else None
        if enqueue:
            self._validate_render_settings(settings, allow_cached=True)
        chosen_seed = self._seed_factory() if seed is None else seed
        with self._lock:
            project = self.projects.get(project_id)
            if expected_branch_id is not None and project.active_branch_id != expected_branch_id:
                raise ValueError("La branche active a changé. Rechargez le projet.")
            attempt = Krea2AssistedAttempt(
                attempt_id=self._attempt_id_factory(),
                index=max((a.index for a in project.attempts if a.kind == "generation"), default=0) + 1,
                prompt=prompt,
                settings=settings,
                seed=chosen_seed,
                conversation_branch_id=project.active_branch_id,
                conversation_turn_id=project.turns[-1].turn_id if project.turns else None,
                conversation_prompt_language=project.prompt_language,
                conversation_model_id=project.revision_model_id or project.model_id,
                style_preset=project.style_preset, preset_pending=project.preset_pending,
                workflow=(
                    _recipe_ref(selected_workflow.reference)
                    if selected_workflow is not None else None
                ),
            )
            if enqueue:
                attempt = attempt.queue(self._next_queue_order())
            saved = self.projects.save(replace(
                project.add_attempt(attempt), current_prompt=prompt,
                render_settings=settings, render_seed=chosen_seed,
            ))
            if enqueue:
                self._render_wake.set()
            return saved

    def _check_conversation_change(self, project: Krea2AssistedProject, expected_branch_id: str | None) -> None:
        if project.project_id in self._chatting:
            raise ValueError("Attendez la fin de l’échange avant de changer de conversation.")
        if expected_branch_id is not None and project.active_branch_id != expected_branch_id:
            raise ValueError("La branche active a changé. Rechargez le projet.")

    def change_branch(
        self, project_id: str, *, expected_branch_id: str,
        branch_id: str | None = None, attempt_id: str | None = None,
        image_prompt_only: bool = False, current_prompt: str | None = None,
        settings: Krea2BatchSettings | None = None, seed: int | None = None,
        prompt_language: Krea2PromptLanguage | None = None, model_id: str | None = None,
    ) -> Krea2AssistedProject:
        if (branch_id is None) == (attempt_id is None):
            raise ValueError("Choose either a branch or an attempt")
        with self._lock:
            project = self.projects.get(project_id)
            self._check_conversation_change(project, expected_branch_id)
            # Preserve unsent prompt/settings edits on the departing path.
            if settings is not None:
                project = replace(
                    project, current_prompt=_bounded_text(current_prompt, "prompt", 40_000),
                    render_settings=settings, render_seed=seed,
                )
            if prompt_language is not None:
                project = project.with_prompt_language(prompt_language)
            if model_id is not None:
                project = project.select_revision_model(model_id)
            if attempt_id is not None:
                project = project.branch_from_attempt(
                    attempt_id, f"branch-{uuid4().hex}", image_prompt_only=image_prompt_only,
                )
            else:
                project = project.switch_branch(branch_id)
            return self.projects.save(project)

    def queue_attempt(self, project_id: str, attempt_id: str) -> Krea2AssistedProject:
        with self._lock:
            project = self.projects.get(project_id)
            attempt = project.attempt(attempt_id)
            if attempt.kind == "composition":
                raise ValueError("Une composition locale ne peut pas être envoyée à ComfyUI.")
            if attempt.status in _RENDER_PENDING:
                return project  # A repeated /start never duplicates a submission.
            self._validate_render_settings(attempt.settings, allow_cached=True)
            saved = self.projects.save(project.replace_attempt(attempt.queue(self._next_queue_order())))
            self._render_wake.set()
            return saved

    def _next_queue_order(self) -> int:
        # A durable global order, independent of project edits and branch navigation.
        latest = max((attempt.queue_order or 0 for project in self.projects.list(2**31 - 1)
                      for attempt in project.attempts), default=0)
        return max(time.time_ns(), latest + 1)

    def _pending_renders(self) -> list[tuple[Krea2AssistedProject, Krea2AssistedAttempt]]:
        entries = [(project, attempt) for project in self.projects.list(2**31 - 1)
                   for attempt in project.attempts if attempt.status in _RENDER_PENDING]
        entries.sort(key=lambda pair: (
            pair[1].status is Krea2AssistedAttemptStatus.QUEUED,
            pair[1].queue_order or 0, pair[0].project_id, pair[1].index,
        ))
        return entries

    def render_queue(self) -> dict[str, object]:
        with self._lock:
            entries = self._pending_renders()
            return {
                "worker_running": bool(self._render_worker and self._render_worker.is_alive()),
                "error": self._render_queue_error,
                "items": [{
                    "project_id": project.project_id, "project_name": project.name,
                    "attempt_id": attempt.attempt_id, "index": attempt.index,
                    "status": attempt.status.value, "position": index + 1,
                    "error": attempt.error or (
                        _AMBIGUOUS_SUBMISSION if attempt.status is Krea2AssistedAttemptStatus.SUBMITTING
                        and (project.project_id, attempt.attempt_id) not in self._claimed else None
                    ),
                } for index, (project, attempt) in enumerate(entries)],
            }

    def start_render_worker(self) -> None:
        with self._lock:
            if self._render_worker is None or not self._render_worker.is_alive():
                self._render_stop.clear()
                self._render_worker = Thread(target=self._render_loop, name="krea2-assisted-render-queue", daemon=True)
                self._render_worker.start()
            self._render_wake.set()

    def stop_render_worker(self) -> None:
        # Leave submitted jobs and queued records intact for the next server process.
        self._render_stop.set()
        self._render_wake.set()
        worker = self._render_worker
        if worker is not None:
            worker.join(timeout=2)

    def _render_loop(self) -> None:
        while not self._render_stop.is_set():
            self._render_wake.clear()
            try:
                progressed = self.process_next_render()
                self._render_queue_error = None
            except Exception as error:
                self._render_queue_error = f"File en attente : {_error(error)}"
                progressed = False
            if not progressed:
                self._render_wake.wait(timeout=5)

    def process_next_render(self, *, until: tuple[str, str] | None = None) -> bool:
        """Advance one FIFO entry; the lock also serializes synchronous callers."""
        if not self._render_lock.acquire(blocking=False):
            return False
        try:
            if self._render_stop.is_set():
                return False
            with self._lock:
                if until is not None and self.projects.get(until[0]).attempt(until[1]).status not in _RENDER_PENDING:
                    return False
                entries = self._pending_renders()
                if not entries:
                    return False
                project, attempt = entries[0]
                if attempt.status is Krea2AssistedAttemptStatus.SUBMITTING:
                    # A process died between POST /prompt and recording its ID.
                    # Do not guess whether it was accepted, or submit a duplicate.
                    if attempt.error != _AMBIGUOUS_SUBMISSION:
                        self.projects.save(project.replace_attempt(replace(attempt, error=_AMBIGUOUS_SUBMISSION)))
                    return False
            result = self._execute_render(project.project_id, attempt.attempt_id)
            return result.attempt(attempt.attempt_id).status not in _RENDER_PENDING
        finally:
            self._render_lock.release()

    def execute_attempt(self, project_id: str, attempt_id: str) -> Krea2AssistedProject:
        """Compatibility entry point for Production: respect FIFO, then return its result."""
        while self.projects.get(project_id).attempt(attempt_id).status in _RENDER_PENDING:
            if self._render_stop.is_set():
                break
            if not self.process_next_render(until=(project_id, attempt_id)):
                self._sleep(max(self.poll_interval, 0.1))
        return self.projects.get(project_id)

    def _execute_render(self, project_id: str, attempt_id: str) -> Krea2AssistedProject:
        if self.work_coordinator is not None:
            try:
                project_name = self.projects.get(project_id).name
                with self.work_coordinator.lease(
                    f"krea2:{project_id}:{attempt_id}",
                    ComputeResource.REMOTE_GPU,
                    ProductionWorkload.IMAGE_RENDER,
                    f"KREA2 · {project_name}"[:200],
                    cancelled=lambda: self.projects.get(project_id).attempt(attempt_id).status
                    not in _RENDER_PENDING,
                ):
                    return self._execute_render_owned(project_id, attempt_id)
            except ResourceWaitCancelled:
                return self.projects.get(project_id)
        return self._execute_render_owned(project_id, attempt_id)

    def _execute_render_owned(self, project_id: str, attempt_id: str) -> Krea2AssistedProject:
        key = (project_id, attempt_id)
        activity_id = f"krea2:{project_id}:{attempt_id}"
        if self.work_coordinator is not None:
            self.work_coordinator.report_progress(activity_id, 0.02, "Préparation du workflow KREA2")
        with self._lock:
            project = self.projects.get(project_id)
            attempt = project.attempt(attempt_id)
            if attempt.status not in {
                Krea2AssistedAttemptStatus.QUEUED, Krea2AssistedAttemptStatus.RUNNING,
                Krea2AssistedAttemptStatus.CANCEL_PENDING,
            }:
                return project
            if key in self._claimed:
                raise ValueError("attempt is already executing")
            self._claimed.add(key)
        execution_id = attempt.execution_id
        history_received = False
        output_prefix = f"image/krea2-assisted/{project_id}/{attempt_id}"
        try:
            workflow_definition = self._workflow_for_attempt(attempt)
            if execution_id is None:
                self._validate_render_settings(attempt.settings)
                workflow = workflow_definition.build(
                    prompt=attempt.prompt, settings=attempt.settings, seed=attempt.seed,
                    output_prefix=output_prefix,
                    sidecar_text=_sidecar(
                        project, attempt, attempt.settings, output_prefix,
                        workflow_definition.reference,
                        getattr(workflow_definition, "seed_metadata", lambda value: {"root": value})(attempt.seed),
                    ),
                )
                digest = self.projects.save_compiled_workflow(project_id, attempt_id, workflow)
                if self.work_coordinator is not None:
                    self.work_coordinator.report_progress(activity_id, 0.08, "Envoi à ComfyUI")
                with self._lock:
                    current = self.projects.get(project_id)
                    current_attempt = current.attempt(attempt_id)
                    if current_attempt.status is not Krea2AssistedAttemptStatus.QUEUED or self._render_stop.is_set():
                        return current
                    self.projects.save(current.replace_attempt(current_attempt.submitting(digest)))
                execution_id = self.comfy.submit_workflow(workflow)
                with self._lock:
                    current = self.projects.get(project_id)
                    self.projects.save(current.replace_attempt(current.attempt(attempt_id).start(execution_id, digest)))
            history = self._wait_history(project_id, attempt_id, execution_id)
            if self.work_coordinator is not None:
                self.work_coordinator.report_progress(activity_id, 0.88, "Récupération de l’image")
            history_received = True
            output_assets, output_warnings = self._import_outputs(
                workflow_definition, history, execution_id, output_prefix, project_id,
            )
            if self.work_coordinator is not None:
                self.work_coordinator.report_progress(activity_id, 0.96, "Import de l’image")
            with self._lock:
                current = self.projects.get(project_id)
                current_attempt = current.attempt(attempt_id)
                if current_attempt.status in {
                    Krea2AssistedAttemptStatus.RUNNING,
                    Krea2AssistedAttemptStatus.CANCEL_PENDING,
                }:
                    current = self.projects.save(current.replace_attempt(current_attempt.succeed(
                        output_assets["final"],
                        pre_flux_asset_id=output_assets.get("pre_flux"),
                        warnings=output_warnings,
                    )))
                if self.work_coordinator is not None:
                    self.work_coordinator.report_progress(activity_id, 1.0, "Image terminée")
                return current
        except _RenderTrackingStopped:
            return self.projects.get(project_id)
        except Exception as error:
            with self._lock:
                current = self.projects.get(project_id)
                current_attempt = current.attempt(attempt_id)
                if current_attempt.status is Krea2AssistedAttemptStatus.SUBMITTING:
                    current = self.projects.save(current.replace_attempt(replace(current_attempt, error=_AMBIGUOUS_SUBMISSION)))
                elif current_attempt.status in {Krea2AssistedAttemptStatus.RUNNING, Krea2AssistedAttemptStatus.CANCEL_PENDING} and not history_received and not isinstance(error, _RenderFailed):
                    # A lost connection/timeout is not proof the GPU job stopped.
                    # Keep its ID, block later submissions and retry tracking it.
                    current = self.projects.save(current.replace_attempt(replace(
                        current_attempt, error=f"Suivi ComfyUI en attente : {_error(error)}",
                    )))
                elif current_attempt.status in {
                    Krea2AssistedAttemptStatus.CREATED,
                    Krea2AssistedAttemptStatus.QUEUED,
                    Krea2AssistedAttemptStatus.RUNNING,
                    Krea2AssistedAttemptStatus.CANCEL_PENDING,
                }:
                    current = self.projects.save(current.replace_attempt(current_attempt.fail(_error(error))))
                return current
        finally:
            with self._lock:
                self._claimed.discard(key)

    def cancel_attempt(self, project_id: str, attempt_id: str) -> Krea2AssistedProject:
        with self._lock:
            project = self.projects.get(project_id)
            attempt = project.attempt(attempt_id)
            if attempt.status is Krea2AssistedAttemptStatus.SUBMITTING:
                if (project_id, attempt_id) in self._claimed:
                    raise ValueError("Envoi à ComfyUI en cours. Attendez sa confirmation avant d’annuler.")
                # Explicitly release an ambiguous dispatch; no unknown remote ID is interrupted.
                saved = self.projects.save(project.replace_attempt(attempt.cancel()))
                self._render_wake.set()
                return saved
            if attempt.status in {
                Krea2AssistedAttemptStatus.CREATED,
                Krea2AssistedAttemptStatus.QUEUED,
            }:
                saved = self.projects.save(project.replace_attempt(attempt.cancel()))
                self._render_wake.set()
                return saved
            if attempt.status not in {
                Krea2AssistedAttemptStatus.RUNNING,
                Krea2AssistedAttemptStatus.CANCEL_PENDING,
            }:
                return project
            assert attempt.execution_id is not None
            try:
                result = self.comfy.cancel_execution(attempt.execution_id)
                action = getattr(getattr(result, "action", None), "value", getattr(result, "action", None))
                if action == "already_finished":
                    refreshed = self._refresh_detached_attempt(project, attempt)
                    if refreshed != project:
                        return refreshed
                    return self.projects.save(project.replace_attempt(attempt.cancel_pending("Sortie terminée à réconcilier.")))
                return self.projects.save(project.replace_attempt(attempt.cancel()))
            except Exception as error:
                return self.projects.save(project.replace_attempt(attempt.cancel_pending(_error(error))))

    def select_feedback(self, project_id: str, attempt_id: str | None) -> Krea2AssistedProject:
        with self._lock:
            project = self.projects.get(project_id)
            return self.projects.save(project.use_feedback(attempt_id))

    def save_image(self, project_id: str, attempt_id: str) -> Krea2AssistedProject:
        with self._lock:
            project = self.projects.get(project_id).accept_attempt(attempt_id)
            if self.exporter is None:
                return self.projects.save(project)
            attempt = project.attempt(attempt_id)
            previous = project.export_path
            try:
                path = self.exporter.export(project, attempt, self.assets)
                project = project.with_export(path, None)
            except Exception as error:
                project = project.with_export(previous, _error(error))
            return self.projects.save(project)

    def set_recipe_draft(
        self,
        project_id: str,
        draft: Krea2AssistedRecipeDraft,
    ) -> Krea2AssistedProject:
        with self._lock:
            project = self.projects.get(project_id)
            draft = replace(draft, prompt_language=project.prompt_language)
            return self.projects.save(project.with_recipe_draft(draft))

    def publish_recipe(
        self,
        project_id: str,
        draft: Krea2AssistedRecipeDraft | None = None,
    ) -> tuple[Krea2AssistedProject, Krea2VisualRecipe]:
        with self._lock:
            project = self.projects.get(project_id)
            proposal = draft or project.recipe_draft
            if proposal is None:
                raise ValueError("the project has no recipe draft")
            proposal = replace(proposal, prompt_language=project.prompt_language)
            selected_id = project.feedback_attempt_id or project.accepted_attempt_id
            if selected_id is None:
                raise ValueError("select or save a successful render before publishing a recipe")
            selected = project.attempt(selected_id)
            if selected.status is not Krea2AssistedAttemptStatus.SUCCEEDED:
                raise ValueError("the recipe settings must come from a successful render")
            recipe = self.recipes.publish_new(proposal, as_batch_settings(selected.settings))
            project = project.with_recipe_draft(proposal).with_published_recipe(
                recipe.recipe_id,
                recipe.version,
            )
            if project.accepted_attempt_id is not None and self.exporter is not None:
                try:
                    path = self.exporter.export(project, project.attempt(project.accepted_attempt_id), self.assets)
                    project = project.with_export(path, None)
                except Exception as error:
                    project = project.with_export(project.export_path, _error(error))
            return self.projects.save(project), recipe

    def _completion_request(
        self,
        project: Krea2AssistedProject,
        message: str,
        mode: Krea2AssistedTurnMode,
        include_reasoning: bool,
    ) -> CompletionRequest:
        images: list[ImageInput] = []
        if project.initial_reference_pending:
            assert project.reference_asset_id is not None
            asset = self.assets.get(project.reference_asset_id)
            images.append(ImageInput(asset.media_type, self.assets.read_bytes(asset.asset_id), "REFERENCE IMAGE"))
        feedback = None
        if project.feedback_attempt_id is not None:
            feedback = project.attempt(project.feedback_attempt_id)
            if feedback.output_asset_id is not None:
                asset = self.assets.get(feedback.output_asset_id)
                images.append(ImageInput(asset.media_type, self.assets.read_bytes(asset.asset_id), "GENERATED RESULT"))
        current_turn = project.turns[-1]
        if current_turn.guidance_asset_id is not None:
            asset = self.assets.get(current_turn.guidance_asset_id)
            images.append(ImageInput(
                asset.media_type,
                self.assets.read_bytes(asset.asset_id),
                "TURN GUIDANCE IMAGE",
            ))
        recipe = assistance_recipe(project.assistance_recipe_version)
        if recipe in (krea2_assisted_v2, krea2_assisted_v3):
            # Do not inject unrelated recipes or fetch a resource catalogue for
            # a purely visual correction. Publication still receives its memory.
            memory = (_recipe_memory(self.recipes.current())
                      if mode is Krea2AssistedTurnMode.RECIPE or recipe.needs_recipes(message)
                      else "Not included for image creation; use the current design and feedback.")
            resources = (recipe.resource_memory(
                self.resources.list_models(), self.resources.list_loras(), message,
            ) if recipe.needs_resources(message)
                else "Not requested. Do not invent technical recommendations.")
        else:
            memory = _recipe_memory(self.recipes.current())
            resources = _resource_memory(self.resources.list_models(), self.resources.list_loras())
        user = recipe.user_prompt(
            project, message,
            selected=_attempt_context(feedback) if feedback else "No generated result selected.",
            memory=memory,
            resources=resources,
            language_instruction=_prompt_language_instruction(project.prompt_language),
        )
        if project.preset_pending and project.style_preset is not None:
            preset = project.style_preset
            asset = self.assets.get(preset.image_asset_id)
            images.append(ImageInput(asset.media_type, self.assets.read_bytes(asset.asset_id), "STYLE PRESET EXAMPLE"))
            user += (
                "\n\nNEW STYLE PRESET EXAMPLE (apply to this exchange):\n"
                + json.dumps({"name": preset.name, "revision": preset.revision, "example_prompt": preset.prompt,
                              "checkpoint": preset.settings.model_name,
                              "loras": [{"name": l.name, "strength": l.strength} for l in preset.settings.loras]}, ensure_ascii=False)
                + "\nUse this prompt and STYLE PRESET EXAMPLE image as a style example only. "
                "Apply its relevant materials, light and photographic treatment to the user's subject. "
                "Do not copy its subject, background or composition unless requested. "
                "The newest user message has priority; the current exploration remains the baseline. "
                "These settings are already selected; do not invent other settings."
            )
        return CompletionRequest(
            model_id=project.revision_model_id or project.model_id,
            system_prompt=recipe.system_prompt(mode.value),
            user_prompt=user,
            images=tuple(images),
            temperature=0.35 if mode is Krea2AssistedTurnMode.CREATION else 0.2,
            max_tokens=recipe.MAX_TOKENS,
            operation_id=(
                recipe.CREATION_OPERATION
                if mode is Krea2AssistedTurnMode.CREATION
                else recipe.RECIPE_OPERATION
            ),
            include_reasoning=include_reasoning,
        )

    def _accept_chat_response(
        self,
        project_id: str,
        mode: Krea2AssistedTurnMode,
        raw: str,
        model_id: str,
    ) -> Krea2AssistedProject:
        value = _decode_json(raw)
        message = _bounded_text(value.get("message"), "assistant message", 12_000)
        questions = _string_array(value.get("questions"), "questions", maximum=3)
        with self._lock:
            project = self.projects.get(project_id)
            if mode is Krea2AssistedTurnMode.CREATION:
                if set(value) != {"message", "questions", "prompt", "recommendations"}:
                    raise ValueError("creation response has invalid fields")
                prompt = _bounded_text(value.get("prompt"), "KREA2 prompt", 40_000)
                minimum_length = (
                    40
                    if project.prompt_language is Krea2PromptLanguage.CHINESE_SIMPLIFIED
                    else 80
                )
                if len(prompt) < minimum_length:
                    raise ValueError("the generated KREA2 prompt is too short")
                recommendations = _string_array(
                    value.get("recommendations"),
                    "recommendations",
                    maximum=8,
                )
                assistant = Krea2AssistedTurn(
                    turn_id=self._turn_id_factory(),
                    assistance_recipe_version=project.assistance_recipe_version,
                    mode=mode,
                    role=Krea2AssistedTurnRole.ASSISTANT,
                    content=message,
                    questions=questions,
                    prompt=prompt,
                    recommendations=recommendations,
                    model_id=_bounded_text(model_id, "model_id", 300),
                )
                return self.projects.save(replace(
                    project,
                    turns=(*project.turns, assistant),
                    current_prompt=prompt,
                    preset_pending=False,
                ))
            if set(value) != {"message", "questions", "recipe"}:
                raise ValueError("recipe response has invalid fields")
            draft = _parse_draft(value.get("recipe"), project.prompt_language)
            assistant = Krea2AssistedTurn(
                turn_id=self._turn_id_factory(),
                assistance_recipe_version=project.assistance_recipe_version,
                mode=mode,
                role=Krea2AssistedTurnRole.ASSISTANT,
                content=message,
                questions=questions,
                model_id=_bounded_text(model_id, "model_id", 300),
            )
            project = replace(project, turns=(*project.turns, assistant), preset_pending=False)
            if draft is not None:
                project = project.with_recipe_draft(draft)
            return self.projects.save(project)

    def _wait_history(self, project_id: str, attempt_id: str, execution_id: str) -> dict[str, Any]:
        deadline = self._monotonic() + self.run_timeout
        while True:
            if self._render_stop.is_set():
                raise _RenderTrackingStopped()
            attempt = self.projects.get(project_id).attempt(attempt_id)
            if attempt.status is Krea2AssistedAttemptStatus.CANCELLED:
                raise RuntimeError("KREA2 assisted attempt cancelled")
            history = self.comfy.get_history(execution_id)
            record = history.get(execution_id)
            status = record.get("status") if isinstance(record, Mapping) else None
            if isinstance(status, Mapping):
                terminal = _history_terminal_kind(status)
                if terminal == "success":
                    return history
                if terminal is not None:
                    raise _RenderFailed(f"ComfyUI execution failed: {status}")
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                raise TimeoutError("ComfyUI assisted render timed out")
            self._sleep(min(self.poll_interval, remaining))

    def _refresh_detached(self, project: Krea2AssistedProject) -> Krea2AssistedProject:
        current = project
        for attempt in project.attempts:
            if (
                attempt.status in {
                    Krea2AssistedAttemptStatus.RUNNING,
                    Krea2AssistedAttemptStatus.CANCEL_PENDING,
                }
                and (project.project_id, attempt.attempt_id) not in self._claimed
            ):
                current = self._refresh_detached_attempt(current, current.attempt(attempt.attempt_id))
        return current

    def _refresh_detached_attempt(
        self,
        project: Krea2AssistedProject,
        attempt: Krea2AssistedAttempt,
    ) -> Krea2AssistedProject:
        if attempt.status not in {
            Krea2AssistedAttemptStatus.RUNNING,
            Krea2AssistedAttemptStatus.CANCEL_PENDING,
        }:
            return project
        assert attempt.execution_id is not None
        try:
            history = self.comfy.get_history(attempt.execution_id)
            record = history.get(attempt.execution_id)
            status = record.get("status") if isinstance(record, Mapping) else None
            if not isinstance(status, Mapping):
                return project
            terminal = _history_terminal_kind(status)
            if terminal is None:
                return project
            if terminal == "success":
                prefix = f"image/krea2-assisted/{project.project_id}/{attempt.attempt_id}"
                workflow_definition = self._workflow_for_attempt(attempt)
                output_assets, output_warnings = self._import_outputs(
                    workflow_definition, history, attempt.execution_id, prefix, project.project_id,
                )
                updated = attempt.succeed(
                    output_assets["final"],
                    pre_flux_asset_id=output_assets.get("pre_flux"),
                    warnings=output_warnings,
                )
            elif terminal == "interrupted":
                updated = attempt.cancel()
            else:
                updated = attempt.fail(f"ComfyUI execution failed: {status}")
        except Exception:
            return project
        return self.projects.save(project.replace_attempt(updated))

    def _validate_render_settings(self, settings: Krea2BatchSettings, *, allow_cached: bool = False) -> None:
        workflow = self._workflow_for_settings(settings)
        sampling = sampling_for(settings)
        default_sampling = Krea2AssistedSampling()
        if (sampling.first_pass, sampling.second_pass) != (default_sampling.first_pass, default_sampling.second_pass):
            if not getattr(workflow, "supports_sampling", False):
                raise ValueError("Le workflow Assisted chargé ne prend pas en charge ces réglages de sampling.")
        known = getattr(self.resources, "selection_in_last_inventory", None)
        if allow_cached and callable(known) and known(settings.model_name, tuple(value.name for value in settings.loras)):
            return
        validate = getattr(self.resources, "validate_selection", None)
        if callable(validate):
            validate(settings.model_name, tuple(value.name for value in settings.loras))
            return
        if not self._model_available(settings.model_name):
            raise ValueError("Le checkpoint sélectionné n’est pas disponible dans le catalogue KREA2.")
        available = {
            normalize_krea2_model_name(getattr(value, "comfy_name", ""))
            for value in self.resources.list_loras()
        }
        missing = [value.name for value in settings.loras if normalize_krea2_model_name(value.name) not in available]
        if missing:
            raise ValueError("LoRA indisponible pour cet essai : " + ", ".join(missing))

    def _workflow_for_settings(self, settings: Krea2BatchSettings) -> Krea2AssistedWorkflow:
        if not self._workflows:
            raise ValueError("Aucun workflow KREA2 Assisted n'est configuré.")
        key = settings.workflow.key if isinstance(settings, Krea2AssistedSettings) else self._default_workflow_key
        if key == DEFAULT_KREA2_ASSISTED_WORKFLOW.key and key not in self._workflows:
            assert self.workflow is not None
            return self.workflow
        try:
            return self._workflows[key]
        except KeyError as error:
            raise ValueError(f"Famille de workflow KREA2 Assisted indisponible : {key}") from error

    def _workflow_for_attempt(self, attempt: Krea2AssistedAttempt) -> Krea2AssistedWorkflow:
        workflow = self._workflow_for_settings(attempt.settings)
        if attempt.workflow is None:
            return workflow
        key = f"{attempt.workflow.recipe_id}@{attempt.workflow.version}"
        try:
            workflow = self._workflows[key]
        except KeyError as error:
            raise ValueError(f"Workflow historique KREA2 Assisted indisponible : {key}") from error
        if getattr(workflow.reference, "workflow_sha256") != attempt.workflow.workflow_sha256:
            raise ValueError(f"Empreinte du workflow historique KREA2 Assisted incompatible : {key}")
        return workflow

    def _import_outputs(
        self,
        workflow: Krea2AssistedWorkflow,
        history: Mapping[str, Any],
        execution_id: str,
        output_prefix: str,
        project_id: str,
    ) -> tuple[dict[str, str], tuple[str, ...]]:
        assets: dict[str, str] = {}
        warnings: list[str] = []
        for output_spec in _workflow_outputs(workflow):
            role = getattr(output_spec, "role", "final")
            try:
                output = _extract_output_or_prefix(
                    history,
                    execution_id,
                    getattr(output_spec, "node_id"),
                    getattr(output_spec, "history_field"),
                    f"{output_prefix}{getattr(output_spec, 'prefix_suffix', '')}",
                )
                content = self.comfy.download_output(
                    filename=output["filename"],
                    subfolder=output["subfolder"],
                    folder_type=output["type"],
                )
                _validate_png(content)
                asset = self.assets.create(
                    content,
                    media_type=getattr(output_spec, "media_type"),
                    source_run_id=project_id,
                )
                assets[role] = asset.asset_id
            except Exception as error:
                if getattr(output_spec, "required", True):
                    raise
                warnings.append(f"Sortie auxiliaire {role} indisponible : {_error(error)}")
        if "final" not in assets:
            raise ValueError("Le workflow Assisted n'a produit aucune sortie finale.")
        return assets, tuple(warnings)

    def _model_available(self, name: str) -> bool:
        target = normalize_krea2_model_name(name)
        return any(
            normalize_krea2_model_name(getattr(value, "comfy_name", "")) == target
            for value in self.resources.list_models()
        )

    def _inventory_warnings(self) -> tuple[str, ...]:
        method = getattr(self.resources, "inventory_warnings", None)
        return tuple(method()) if callable(method) else ()

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


def _attempt_context(attempt: Krea2AssistedAttempt) -> str:
    return json.dumps({
        "attempt_id": attempt.attempt_id,
        **({"image_kind": "composition", "render_settings_are_inherited": True,
            "local_composition": "Selected image combines a fixed base with masked areas of the original generation; the prompt below describes that generation only."}
           if attempt.composition else {}),
        "prompt": attempt.prompt,
        "model_name": attempt.settings.model_name,
        "aspect_ratio": attempt.settings.aspect_ratio.value,
        "megapixels": attempt.settings.megapixels,
        "seed": attempt.seed,
        "loras": [
            {"name": value.name, "strength": value.strength}
            for value in attempt.settings.loras
        ],
    }, ensure_ascii=False, indent=2)


def _recipe_memory(recipes: tuple[Krea2VisualRecipe, ...]) -> str:
    if not recipes:
        return "No published recipe yet."
    lines = []
    for recipe in recipes[:krea2_assisted_v1.RECIPE_LIMIT]:
        loras = ", ".join(f"{value.name}@{value.strength:g}" for value in recipe.settings.loras) or "none"
        lines.append(
            f"- {recipe.recipe_id}@{recipe.version}: {recipe.identity[:260]} | "
            f"checkpoint={recipe.settings.model_name}; ratio={recipe.settings.aspect_ratio.value}; LoRA={loras}"
        )
    return "\n".join(lines)


def _resource_memory(models: tuple[object, ...], loras: tuple[object, ...]) -> str:
    model_names = [
        getattr(value, "comfy_name", "")
        for value in models[:krea2_assisted_v1.MODEL_LIMIT]
        if getattr(value, "comfy_name", "")
    ]
    lora_names = [
        getattr(value, "comfy_name", "")
        for value in loras[:krea2_assisted_v1.LORA_LIMIT]
        if getattr(value, "comfy_name", "")
        and getattr(value, "selectable", True)
    ]
    return (
        "CHECKPOINTS:\n- "
        + ("\n- ".join(model_names) if model_names else "none exposed")
        + "\nLORAS:\n- "
        + ("\n- ".join(lora_names) if lora_names else "none exposed")
    )


def _parse_draft(
    value: object,
    prompt_language: Krea2PromptLanguage = Krea2PromptLanguage.ENGLISH,
) -> Krea2AssistedRecipeDraft | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("recipe must be an object or null")
    required = {
        "recipe_id",
        "display_name",
        "description",
        "identity",
        "invariants",
        "variables",
        "risks",
        "canonical_prompt",
    }
    if set(value) != required:
        raise ValueError("recipe draft has invalid fields")
    return Krea2AssistedRecipeDraft(
        recipe_id=_bounded_text(value["recipe_id"], "recipe_id", 64),
        display_name=_bounded_text(value["display_name"], "display_name", 120),
        description=_bounded_text(value["description"], "description", 500),
        identity=_bounded_text(value["identity"], "identity", 4_000),
        invariants=_string_array(value["invariants"], "invariants", minimum=1, maximum=24),
        variables=_string_array(value["variables"], "variables", minimum=1, maximum=24),
        risks=_string_array(value["risks"], "risks", minimum=1, maximum=24),
        canonical_prompt=_bounded_text(value["canonical_prompt"], "canonical_prompt", 40_000),
        prompt_language=prompt_language,
    )


def parse_krea2_assisted_recipe_draft(value: object) -> Krea2AssistedRecipeDraft:
    draft = _parse_draft(value)
    if draft is None:
        raise ValueError("recipe draft must not be null")
    return draft


def _prompt_language_instruction(language: Krea2PromptLanguage) -> str:
    preservation = (
        "Preserve LoRA trigger phrases, proper names, filenames and quoted literal text verbatim. "
        "Never duplicate the prompt bilingually."
    )
    if language is Krea2PromptLanguage.CHINESE_SIMPLIFIED:
        return f"Simplified Chinese (简体中文). Write the complete prompt in Chinese. {preservation}"
    return f"English. Write the complete prompt in English. {preservation}"


def _decode_json(raw: str) -> Mapping[str, Any]:
    text = _bounded_text(raw, "model response", 100_000)
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise ValueError("JSON fence is not closed")
        text = "\n".join(lines[1:-1]).strip()
        if text.casefold().startswith("json\n"):
            text = text[5:].strip()
    value = json.loads(text)
    if not isinstance(value, Mapping):
        raise ValueError("model response must be a JSON object")
    return value


def _string_array(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int,
) -> tuple[str, ...]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{label} must contain between {minimum} and {maximum} strings")
    return tuple(_bounded_text(item, label, 2_000) for item in value)


def _bounded_text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    result = value.strip()
    if len(result) > maximum:
        raise ValueError(f"{label} must contain at most {maximum} characters")
    return result


def _sidecar(
    project: Krea2AssistedProject,
    attempt: Krea2AssistedAttempt,
    effective_settings: Krea2BatchSettings,
    output_prefix: str,
    reference: object,
    seeds: Mapping[str, int],
) -> str:
    width, height = effective_settings.resolution
    return json.dumps({
        "schema_version": 1,
        "prompt": attempt.prompt,
        "assisted_creation": {
            "project_id": project.project_id,
            "project_name": project.name,
            "intention": project.intention,
            "attempt_id": attempt.attempt_id,
            "llm_model_id": attempt.conversation_model_id or project.model_id,
            "conversation_branch_id": attempt.conversation_branch_id,
            "conversation_turn_id": attempt.conversation_turn_id,
            "reference_filename": project.reference_filename,
        },
        "render": {
            "sampling": asdict(sampling_for(effective_settings)),
            "model_name": effective_settings.model_name,
            "aspect_ratio": effective_settings.aspect_ratio.value,
            "megapixels": effective_settings.megapixels,
            "base_width": width,
            "base_height": height,
            "seed": attempt.seed,
            "seeds": dict(seeds),
            "loras": [
                {"name": value.name, "strength": value.strength}
                for value in effective_settings.loras
            ],
            "output_prefix": output_prefix,
        },
        "workflow": {
            "operation_id": getattr(reference, "operation_id"),
            "recipe_id": getattr(reference, "recipe_id"),
            "version": getattr(reference, "version"),
            "sha256": getattr(reference, "workflow_sha256"),
        },
    }, ensure_ascii=False, indent=2) + "\n"


def _workflow_outputs(workflow: Krea2AssistedWorkflow) -> tuple[object, ...]:
    outputs = getattr(workflow, "outputs", None)
    if isinstance(outputs, tuple) and outputs:
        return outputs
    # Compatibility for existing fakes and adapters predating multi-output.
    return (_LegacyWorkflowOutput(
        role="final",
        node_id=workflow.output_node_id,
        history_field=workflow.output_history_field,
        media_type=workflow.output_media_type,
    ),)


@dataclass(frozen=True, slots=True)
class _LegacyWorkflowOutput:
    role: str
    node_id: str
    history_field: str
    media_type: str
    prefix_suffix: str = ""
    required: bool = True


def _recipe_ref(value: object) -> RecipeRef:
    if isinstance(value, RecipeRef):
        return value
    return RecipeRef(
        operation_id=getattr(value, "operation_id"),
        recipe_id=getattr(value, "recipe_id"),
        version=getattr(value, "version"),
        workflow_sha256=getattr(value, "workflow_sha256"),
    )


def _extract_output_or_prefix(
    history: Mapping[str, Any],
    execution_id: str,
    node_id: str,
    field: str,
    prefix: str,
) -> dict[str, str]:
    record = history.get(execution_id)
    outputs = record.get("outputs") if isinstance(record, Mapping) else None
    node = outputs.get(node_id) if isinstance(outputs, Mapping) else None
    images = node.get(field) if isinstance(node, Mapping) else None
    if isinstance(images, list) and images and isinstance(images[0], Mapping):
        filename = images[0].get("filename")
        if isinstance(filename, str) and filename:
            return {
                "filename": filename,
                "subfolder": str(images[0].get("subfolder", "")),
                "type": str(images[0].get("type", "output")),
            }
    normalized = prefix.strip().replace("\\", "/").strip("/")
    parts = normalized.split("/")
    if not parts or any(not value or value in {".", ".."} or "%" in value for value in parts):
        raise ValueError("ComfyUI history has no expected assisted KREA2 PNG")
    return {
        "filename": f"{parts[-1]}_00001_.png",
        "subfolder": "/".join(parts[:-1]),
        "type": "output",
    }


def _history_terminal_kind(status: Mapping[str, Any]) -> str | None:
    status_str = status.get("status_str")
    completed = status.get("completed")
    if completed is True and status_str == "success":
        return "success"
    if status_str in {"interrupted", "cancelled"}:
        return "interrupted"
    if completed is True or status_str == "error":
        return "error"
    return None


def _validate_png(content: bytes) -> None:
    if not isinstance(content, bytes) or not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("KREA2 assisted output is not a PNG")


def _error(error: Exception) -> str:
    detail = str(error).strip()
    return f"{type(error).__name__}: {detail}" if detail else type(error).__name__
