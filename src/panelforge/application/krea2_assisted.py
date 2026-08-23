"""Conversational prompt design and single-image KREA2 T2I rendering."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
import json
import secrets
from threading import RLock
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
from panelforge.infrastructure.krea2_batch_recipes import Krea2VisualRecipe

from .prompt_lab import (
    CompletionRequest,
    ImageInput,
    LlmCallApplicationOutcome,
    LlmCallApplicationOutcomeReporter,
    ModelDescriptor,
    MultimodalGateway,
    StreamEventKind,
    StreamPhase,
)


_CREATION_SYSTEM = """You are a collaborative art director and KREA2 text-to-image prompt writer.
Return raw JSON only, with exactly these fields:
{"message":"concise helpful reply in French","questions":["up to three useful questions"],"prompt":"complete standalone KREA2 prompt in the TARGET PROMPT LANGUAGE","recommendations":["optional concise setting or iteration advice"]}

The prompt is always required, even when questions remain: it must be usable immediately. Treat any REFERENCE IMAGE only as visual evidence to describe or reverse-engineer. It will NOT be sent to the renderer, so never write edit instructions such as keep, change, replace, preserve from the image, or references to "this image". Produce a self-contained text-to-image description instead.

Use the conversation, the current prompt and the user's newest message as one evolving design brief. When GENERATED RESULT is supplied, compare it with the requested goal using the exact render prompt and settings, identify only relevant visible discrepancies, then rewrite the complete target prompt. Do not append contradictions. Cover concrete subject, framing/composition, pose/action, materials, environment, lighting, palette and finish when relevant. Ask only questions that materially change the result. Do not invent a second workflow or recommend KREA Edit.

Explicit sexual content may be described only when every depicted person is unambiguously an adult and the user requests it. Never infer adulthood from an ambiguous image, introduce youth-related traits, or add an unrequested sexual act or participant. Never output Markdown or commentary outside the JSON."""

_RECIPE_SYSTEM = """You help turn a proven KREA2 text-to-image result into an immutable reusable Batch recipe.
Return raw JSON only with exactly these fields:
{"message":"concise recipe-design reply in French","questions":["up to three material questions"],"recipe":null}
or:
{"message":"concise recipe-design reply in French","questions":["up to three material questions"],"recipe":{"recipe_id":"lowercase_slug","display_name":"human name","description":"short purpose","identity":"visual family identity","invariants":["fixed rules"],"variables":["safe variation axes"],"risks":["failure modes"],"canonical_prompt":"complete standalone KREA2 prompt in the TARGET PROMPT LANGUAGE"}}

The selected result's exact checkpoint, ratio, megapixels and ordered LoRA stack are controlled by PanelForge and must not be repeated as invented technical settings. Separate what defines the family from what may vary across a Batch. Keep the selected proven prompt architecture as the canonical prompt, generalizing only the variable subject details needed by the requested family. Ask questions when identity, invariants or allowed variation axes remain ambiguous. You may still provide a draft while questions remain. Never publish anything and never output Markdown."""


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
        workflow: Krea2AssistedWorkflow,
        comfy: Krea2AssistedComfy,
        assets: Krea2AssistedAssets,
        projects: Krea2AssistedStore,
        resources: Krea2AssistedResources,
        exporter: Krea2CreationExporter | None = None,
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
        self.recipes = recipes
        self.workflow = workflow
        self.comfy = comfy
        self.assets = assets
        self.projects = projects
        self.resources = resources
        self.exporter = exporter
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
        self._lock = RLock()
        self._claimed: set[tuple[str, str]] = set()

    @property
    def export_root(self) -> str | None:
        return str(self.exporter.root) if self.exporter is not None else None

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return self.gateway.list_models()

    def create_project(
        self,
        *,
        name: str,
        intention: str,
        model_id: str,
        reference_asset_id: str | None = None,
        reference_filename: str | None = None,
    ) -> Krea2AssistedProject:
        name = _bounded_text(name, "name", 120)
        intention = _bounded_text(intention, "intention", 12_000)
        model_id = _bounded_text(model_id, "model_id", 300)
        if reference_asset_id is not None:
            asset = self.assets.get(reference_asset_id)
            if not asset.media_type.startswith("image/"):
                raise ValueError("the assisted reference must be an image")
        return self.projects.create(Krea2AssistedProject(
            project_id=self._project_id_factory(),
            name=name,
            intention=intention,
            model_id=model_id,
            reference_asset_id=reference_asset_id,
            reference_filename=(
                _bounded_text(reference_filename, "reference_filename", 240)
                if reference_filename is not None
                else None
            ),
            warnings=self._inventory_warnings(),
        ))

    def get(self, project_id: str) -> Krea2AssistedProject:
        with self._lock:
            return self._refresh_detached(self.projects.get(project_id))

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
        include_reasoning: bool = False,
    ) -> Iterator[Krea2AssistedStreamEvent]:
        message = _bounded_text(message, "message", 12_000)
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
            if prompt_language is not None:
                project = project.with_prompt_language(prompt_language)
            if feedback_attempt_id is not None:
                project = project.use_feedback(feedback_attempt_id)
            user_turn = Krea2AssistedTurn(
                turn_id=self._turn_id_factory(),
                mode=mode,
                role=Krea2AssistedTurnRole.USER,
                content=message,
                guidance_asset_id=guidance_asset_id,
                guidance_filename=guidance_filename,
            )
            project = self.projects.save(replace(project, turns=(*project.turns, user_turn)))
        request = self._completion_request(project, message, mode, include_reasoning)
        parts: list[str] = []
        try:
            for event in self.gateway.stream(request):
                if event.kind is StreamEventKind.DELTA:
                    parts.append(event.text)
                if event.kind is StreamEventKind.TRUNCATED:
                    raw = event.result.content if event.result is not None else "".join(parts)
                    error = ValueError("La réponse du modèle a été tronquée.")
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
                        terminal = self._accept_chat_response(project_id, mode, event.result.content)
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

    def prepare_attempt(
        self,
        project_id: str,
        *,
        prompt: str,
        settings: Krea2BatchSettings,
        seed: int | None = None,
    ) -> Krea2AssistedProject:
        prompt = _bounded_text(prompt, "prompt", 40_000)
        if not isinstance(settings, Krea2BatchSettings):
            raise TypeError("settings must be Krea2BatchSettings")
        chosen_seed = self._seed_factory() if seed is None else seed
        with self._lock:
            project = self.projects.get(project_id)
            attempt = Krea2AssistedAttempt(
                attempt_id=self._attempt_id_factory(),
                index=len(project.attempts) + 1,
                prompt=prompt,
                settings=settings,
                seed=chosen_seed,
            )
            return self.projects.save(project.add_attempt(attempt))

    def queue_attempt(self, project_id: str, attempt_id: str) -> Krea2AssistedProject:
        active = {
            Krea2AssistedAttemptStatus.QUEUED,
            Krea2AssistedAttemptStatus.RUNNING,
            Krea2AssistedAttemptStatus.CANCEL_PENDING,
        }
        with self._lock:
            project = self.projects.get(project_id)
            if not self._model_available(project.attempt(attempt_id).settings.model_name):
                raise ValueError("Le checkpoint sélectionné n’est pas disponible dans le catalogue KREA2.")
            for candidate in self.projects.list(10_000):
                candidate = self._refresh_detached(candidate)
                if any(value.status in active for value in candidate.attempts):
                    raise ValueError("another assisted KREA2 render is already active")
            return self.projects.save(project.replace_attempt(project.attempt(attempt_id).queue()))

    def execute_attempt(self, project_id: str, attempt_id: str) -> Krea2AssistedProject:
        key = (project_id, attempt_id)
        with self._lock:
            project = self.projects.get(project_id)
            attempt = project.attempt(attempt_id)
            if attempt.status is not Krea2AssistedAttemptStatus.QUEUED:
                return project
            if key in self._claimed:
                raise ValueError("attempt is already executing")
            self._claimed.add(key)
        execution_id: str | None = None
        output_prefix = f"image/krea2-assisted/{project_id}/{attempt_id}"
        try:
            render_settings = self._available_settings(attempt.settings)
            workflow = self.workflow.build(
                prompt=attempt.prompt,
                settings=render_settings,
                seed=attempt.seed,
                output_prefix=output_prefix,
                sidecar_text=_sidecar(project, attempt, render_settings, output_prefix, self.workflow.reference),
            )
            digest = self.projects.save_compiled_workflow(project_id, attempt_id, workflow)
            with self._lock:
                current = self.projects.get(project_id)
                current_attempt = current.attempt(attempt_id)
                if current_attempt.status is not Krea2AssistedAttemptStatus.QUEUED:
                    return current
                execution_id = self.comfy.submit_workflow(workflow)
                current = self.projects.save(current.replace_attempt(current_attempt.start(execution_id, digest)))
            history = self._wait_history(project_id, attempt_id, execution_id)
            output = _extract_output_or_prefix(
                history,
                execution_id,
                self.workflow.output_node_id,
                self.workflow.output_history_field,
                output_prefix,
            )
            content = self.comfy.download_output(
                filename=output["filename"],
                subfolder=output["subfolder"],
                folder_type=output["type"],
            )
            _validate_png(content)
            asset = self.assets.create(
                content,
                media_type=self.workflow.output_media_type,
                source_run_id=project_id,
            )
            with self._lock:
                current = self.projects.get(project_id)
                current_attempt = current.attempt(attempt_id)
                if current_attempt.status in {
                    Krea2AssistedAttemptStatus.RUNNING,
                    Krea2AssistedAttemptStatus.CANCEL_PENDING,
                }:
                    current = self.projects.save(current.replace_attempt(current_attempt.succeed(asset.asset_id)))
                return current
        except Exception as error:
            with self._lock:
                current = self.projects.get(project_id)
                current_attempt = current.attempt(attempt_id)
                if current_attempt.status in {
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
            if attempt.status in {
                Krea2AssistedAttemptStatus.CREATED,
                Krea2AssistedAttemptStatus.QUEUED,
            }:
                return self.projects.save(project.replace_attempt(attempt.cancel()))
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
            recipe = self.recipes.publish_new(proposal, selected.settings)
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
        if project.reference_asset_id is not None:
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
        conversation = "\n".join(
            f"{turn.mode.value.upper()} {turn.role.value.upper()}: {turn.content}"
            + (
                f"\nTURN GUIDANCE IMAGE USED: {turn.guidance_filename or 'guidance-image'}"
                if turn.guidance_asset_id is not None
                else ""
            )
            + (f"\nPROMPT: {turn.prompt}" if turn.prompt else "")
            for turn in project.turns[-14:-1]
        ) or "No earlier exchange."
        selected = "No generated result selected."
        if feedback is not None:
            selected = _attempt_context(feedback)
        memory = _recipe_memory(self.recipes.current())
        resources = _resource_memory(
            self.resources.list_models(),
            self.resources.list_loras(),
        )
        user = "\n\n".join((
            f"PROJECT: {project.name}",
            f"TARGET PROMPT LANGUAGE (authoritative):\n{_prompt_language_instruction(project.prompt_language)}",
            f"ORIGINAL INTENTION:\n{project.intention}",
            f"REFERENCE STATUS:\n{'A descriptive reference image is attached.' if project.reference_asset_id else 'No reference image.'}",
            (
                "TURN GUIDANCE STATUS:\nA TURN GUIDANCE IMAGE is attached only for the NEW USER MESSAGE. "
                "Use it as visual evidence or inspiration requested by that message. It does not replace "
                "REFERENCE IMAGE or GENERATED RESULT, and it does not become persistent project identity "
                "unless the user explicitly requests that."
                if current_turn.guidance_asset_id is not None
                else "TURN GUIDANCE STATUS:\nNo turn-specific guidance image."
            ),
            f"CURRENT TARGET PROMPT:\n{project.current_prompt or 'None yet.'}",
            f"RECENT PROJECT CONVERSATION:\n{conversation}",
            f"SELECTED GENERATED RESULT AND EXACT SETTINGS:\n{selected}",
            f"PUBLISHED RECIPE MEMORY (validated global knowledge only):\n{memory}",
            f"AVAILABLE KREA2 RENDER RESOURCES (advice only; never invent missing files):\n{resources}",
            f"NEW USER MESSAGE (authoritative):\n{message}",
        ))
        return CompletionRequest(
            model_id=project.model_id,
            system_prompt=_CREATION_SYSTEM if mode is Krea2AssistedTurnMode.CREATION else _RECIPE_SYSTEM,
            user_prompt=user,
            images=tuple(images),
            temperature=0.35 if mode is Krea2AssistedTurnMode.CREATION else 0.2,
            max_tokens=16_384,
            operation_id=(
                "krea2.assisted.creation_chat@0.3.0"
                if mode is Krea2AssistedTurnMode.CREATION
                else "krea2.assisted.recipe_chat@0.3.0"
            ),
            include_reasoning=include_reasoning,
        )

    def _accept_chat_response(
        self,
        project_id: str,
        mode: Krea2AssistedTurnMode,
        raw: str,
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
                    mode=mode,
                    role=Krea2AssistedTurnRole.ASSISTANT,
                    content=message,
                    questions=questions,
                    prompt=prompt,
                    recommendations=recommendations,
                )
                return self.projects.save(replace(
                    project,
                    turns=(*project.turns, assistant),
                    current_prompt=prompt,
                ))
            if set(value) != {"message", "questions", "recipe"}:
                raise ValueError("recipe response has invalid fields")
            draft = _parse_draft(value.get("recipe"), project.prompt_language)
            assistant = Krea2AssistedTurn(
                turn_id=self._turn_id_factory(),
                mode=mode,
                role=Krea2AssistedTurnRole.ASSISTANT,
                content=message,
                questions=questions,
            )
            project = replace(project, turns=(*project.turns, assistant))
            if draft is not None:
                project = project.with_recipe_draft(draft)
            return self.projects.save(project)

    def _wait_history(self, project_id: str, attempt_id: str, execution_id: str) -> dict[str, Any]:
        deadline = self._monotonic() + self.run_timeout
        while True:
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
                    raise RuntimeError(f"ComfyUI execution failed: {status}")
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
                output = _extract_output_or_prefix(
                    history,
                    attempt.execution_id,
                    self.workflow.output_node_id,
                    self.workflow.output_history_field,
                    prefix,
                )
                content = self.comfy.download_output(
                    filename=output["filename"],
                    subfolder=output["subfolder"],
                    folder_type=output["type"],
                )
                _validate_png(content)
                asset = self.assets.create(
                    content,
                    media_type=self.workflow.output_media_type,
                    source_run_id=project.project_id,
                )
                updated = attempt.succeed(asset.asset_id)
            elif terminal == "interrupted":
                updated = attempt.cancel()
            else:
                updated = attempt.fail(f"ComfyUI execution failed: {status}")
        except Exception:
            return project
        return self.projects.save(project.replace_attempt(updated))

    def _available_settings(self, settings: Krea2BatchSettings) -> Krea2BatchSettings:
        available = {
            normalize_krea2_model_name(getattr(value, "comfy_name", ""))
            for value in self.resources.list_loras()
        }
        return replace(
            settings,
            loras=tuple(
                value
                for value in settings.loras
                if normalize_krea2_model_name(value.name) in available
            ),
        )

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
    for recipe in recipes[:20]:
        loras = ", ".join(f"{value.name}@{value.strength:g}" for value in recipe.settings.loras) or "none"
        lines.append(
            f"- {recipe.recipe_id}@{recipe.version}: {recipe.identity[:260]} | "
            f"checkpoint={recipe.settings.model_name}; ratio={recipe.settings.aspect_ratio.value}; LoRA={loras}"
        )
    return "\n".join(lines)


def _resource_memory(models: tuple[object, ...], loras: tuple[object, ...]) -> str:
    model_names = [
        getattr(value, "comfy_name", "")
        for value in models[:40]
        if getattr(value, "comfy_name", "")
    ]
    lora_names = [
        getattr(value, "comfy_name", "")
        for value in loras[:80]
        if getattr(value, "comfy_name", "")
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
            "llm_model_id": project.model_id,
            "reference_filename": project.reference_filename,
        },
        "render": {
            "model_name": effective_settings.model_name,
            "aspect_ratio": effective_settings.aspect_ratio.value,
            "megapixels": effective_settings.megapixels,
            "base_width": width,
            "base_height": height,
            "seed": attempt.seed,
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
