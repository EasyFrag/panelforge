"""Backlog, prompt reconstruction and iterative rendering for KREA2 Edit."""

from __future__ import annotations

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
from panelforge.domain.krea2_batch import (
    Krea2BatchItemStatus,
    Krea2LoraSelection,
    Krea2PromptLanguage,
)
from panelforge.domain.krea2_edit import (
    Krea2EditAttempt,
    Krea2EditAttemptStatus,
    Krea2EditMetadata,
    Krea2EditPromptRevision,
    Krea2EditPromptStatus,
    Krea2EditSettings,
    Krea2EditSource,
    Krea2EditSourceState,
)
from panelforge.infrastructure.presets.krea2_edit import ValidatedKrea2EditWorkflow

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


_PROMPT_SYSTEM = """You write one production-ready KREA2 image-edit prompt in the explicitly requested target language.
Return only the final natural-language prompt: no Markdown, JSON, title, analysis, or commentary.

The image labelled STAGE SOURCE is the immutable image that the renderer will edit. A second image labelled GENERATED FEEDBACK may be supplied only as evidence of the current result: use it to understand relevant errors or inconsistencies, but never mistake it for the renderer's source. The user's new edit instruction has priority. Preserve every visible identity, material, environment, lighting, and style attribute that the instruction does not change. When a CURRENT TARGET PROMPT is supplied, rewrite it semantically: remove or replace clauses that contradict the requested edit instead of appending contradictory instructions. When no current prompt is supplied, reconstruct it from the stage source while applying the edit in the same pass.

Describe framing and camera, composition and crop, subject anatomy/pose/contact, gaze/expression, appearance/materials, environment, lighting, color, and rendering finish when they are relevant. Prefer concrete visible relationships over generic adjectives. Keep sparse images concise and complex images sufficiently detailed.

Explicit NSFW content involving clearly adult subjects is allowed for this image-edit task and should be described objectively and precisely when present or explicitly requested. Never infer that an ambiguous subject is adult, never introduce youth-related attributes, and never add an unrequested sexual act or participant.

Do not add a negative-prompt section. Preserve useful explicit constraints from the base prompt only when they remain relevant to the requested result."""

_META_LINE = re.compile(
    r"^(?:certainly|sure|of course)?[\s,!—-]*(?:here(?:'s| is)|final prompt|prompt:)\b",
    re.IGNORECASE,
)

_CHINESE_META_LINE = re.compile(
    r"^(?:(?:当然|好的)[，,：:]?\s*)?(?:(?:以下(?:是|为)|这是)\s*)?(?:最终\s*)?(?:KREA2\s*)?(?:图像编辑\s*)?提示词[：:]?\s*$"
)


def _prompt_language_instruction(language: Krea2PromptLanguage) -> str:
    if language is Krea2PromptLanguage.CHINESE_SIMPLIFIED:
        return (
            "TARGET PROMPT LANGUAGE: Simplified Chinese (中文). Write the entire final KREA2 "
            "prompt in natural Simplified Chinese. Preserve LoRA trigger tokens, proper names, "
            "filenames, quoted literal text, and other exact technical tokens verbatim when translating "
            "them would change their function. Do not provide an English duplicate or translation."
        )
    return (
        "TARGET PROMPT LANGUAGE: English. Write the entire final KREA2 prompt in natural English. "
        "Preserve LoRA trigger tokens, proper names, filenames, quoted literal text, and other exact "
        "technical tokens verbatim. Do not provide a Chinese duplicate or translation."
    )


class Krea2EditAssets(Protocol):
    def create(self, content: bytes, *, media_type: str, source_run_id: str | None = None) -> Asset: ...
    def get(self, asset_id: str) -> Asset: ...
    def read_bytes(self, asset_id: str) -> bytes: ...


class Krea2EditStore(Protocol):
    def create(self, source: Krea2EditSource) -> Krea2EditSource: ...
    def save(self, source: Krea2EditSource) -> Krea2EditSource: ...
    def get(self, source_id: str) -> Krea2EditSource: ...
    def list(self, limit: int = 100, *, include_hidden: bool = False) -> list[Krea2EditSource]: ...
    def find_batch_source(self, batch_id: str, item_id: str) -> Krea2EditSource | None: ...
    def save_compiled_workflow(self, source_id: str, attempt_id: str, workflow: dict[str, Any]) -> str: ...


class Krea2EditComfy(Protocol):
    def upload_image(self, content: bytes, *, filename: str, subfolder: str = "", overwrite: bool = False) -> object: ...
    def submit_workflow(self, workflow: Mapping[str, Any]) -> str: ...
    def get_history(self, prompt_id: str) -> dict[str, Any]: ...
    def download_output(self, *, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes: ...
    def cancel_execution(self, prompt_id: str) -> object | None: ...


class Krea2BatchReader(Protocol):
    def list(self, limit: int = 20) -> list[object]: ...


class Krea2ProjectExporter(Protocol):
    root: object

    def export(
        self,
        stages: tuple[Krea2EditSource, ...],
        assets: Krea2EditAssets,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class Krea2EditStreamEvent:
    kind: StreamEventKind
    phase: StreamPhase
    text: str = ""
    progress: float | None = None
    source: Krea2EditSource | None = None


@dataclass(frozen=True, slots=True)
class Krea2EditAttemptRequest:
    prompt: str
    settings: Krea2EditSettings

    def __post_init__(self) -> None:
        _text(self.prompt, "prompt")
        if not isinstance(self.settings, Krea2EditSettings):
            raise TypeError("settings must be Krea2EditSettings")


class Krea2EditService:
    def __init__(
        self,
        *,
        gateway: MultimodalGateway,
        workflow: ValidatedKrea2EditWorkflow,
        comfy: Krea2EditComfy,
        assets: Krea2EditAssets,
        sources: Krea2EditStore,
        batches: Krea2BatchReader | None = None,
        project_exporter: Krea2ProjectExporter | None = None,
        application_outcomes: LlmCallApplicationOutcomeReporter | None = None,
        run_timeout: float = 3600.0,
        poll_interval: float = 1.0,
        source_id_factory: Callable[[], str] | None = None,
        attempt_id_factory: Callable[[], str] | None = None,
        prompt_revision_id_factory: Callable[[], str] | None = None,
        seed_factory: Callable[[], int] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if run_timeout <= 0 or poll_interval <= 0:
            raise ValueError("timeouts must be positive")
        self.gateway = gateway
        self.workflow = workflow
        self.comfy = comfy
        self.assets = assets
        self.sources = sources
        self.batches = batches
        self.project_exporter = project_exporter
        self.application_outcomes = application_outcomes
        self.run_timeout = run_timeout
        self.poll_interval = poll_interval
        self._source_id_factory = source_id_factory or (lambda: f"krea2-edit-{uuid4().hex}")
        self._attempt_id_factory = attempt_id_factory or (lambda: f"attempt-{uuid4().hex}")
        self._prompt_revision_id_factory = prompt_revision_id_factory or (
            lambda: f"revision-{uuid4().hex}"
        )
        self._seed_factory = seed_factory or (lambda: secrets.randbits(64))
        self._monotonic = monotonic
        self._sleep = sleep
        self._lock = RLock()
        self._claimed: set[tuple[str, str]] = set()

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return self.gateway.list_models()

    @property
    def project_export_root(self) -> str | None:
        if self.project_exporter is None:
            return None
        return str(self.project_exporter.root)

    def add_source(
        self,
        *,
        asset_id: str,
        filename: str,
        metadata: Krea2EditMetadata,
        source_batch_id: str | None = None,
        source_batch_item_id: str | None = None,
    ) -> Krea2EditSource:
        asset = self.assets.get(asset_id)
        if not asset.media_type.startswith("image/"):
            raise ValueError("KREA2 edit source must be an image")
        source = Krea2EditSource(
            source_id=self._source_id_factory(),
            recipe=self.workflow.reference,
            source_asset_id=asset.asset_id,
            filename=_text(filename, "filename").strip(),
            metadata=metadata,
            source_batch_id=source_batch_id,
            source_batch_item_id=source_batch_item_id,
        )
        return self.sources.create(source)

    def sync_batch_sources(self, limit: int = 100) -> int:
        if self.batches is None:
            return 0
        created = 0
        for batch in self.batches.list(limit):
            for item in getattr(batch, "items", ()):
                if (
                    getattr(item, "status", None) is not Krea2BatchItemStatus.SUCCEEDED
                    or not getattr(item, "output_asset_id", None)
                    or self.sources.find_batch_source(batch.batch_id, item.item_id) is not None
                ):
                    continue
                metadata = Krea2EditMetadata(
                    prompt=item.prompt,
                    model_name=batch.settings.model_name,
                    aspect_ratio=batch.settings.aspect_ratio,
                    megapixels=batch.settings.megapixels,
                    seed=item.seed,
                    loras=batch.settings.loras,
                    origin="batch",
                )
                self.add_source(
                    asset_id=item.output_asset_id,
                    filename=f"{batch.batch_id}_{item.item_id}.png",
                    metadata=metadata,
                    source_batch_id=batch.batch_id,
                    source_batch_item_id=item.item_id,
                )
                created += 1
        return created

    def get(self, source_id: str) -> Krea2EditSource:
        with self._lock:
            return self._refresh_detached_attempts(self.sources.get(source_id))

    def list(self, limit: int = 100, *, include_hidden: bool = False) -> list[Krea2EditSource]:
        self.sync_batch_sources(limit=max(limit, 100))
        with self._lock:
            return [
                self._refresh_detached_attempts(source)
                for source in self.sources.list(limit, include_hidden=include_hidden)
            ]

    def set_state(self, source_id: str, state: Krea2EditSourceState) -> Krea2EditSource:
        if state not in {
            Krea2EditSourceState.PROCESSED,
            Krea2EditSourceState.HIDDEN,
        }:
            raise ValueError("a KREA2 edit project can only be processed or hidden")
        with self._lock:
            source = self.sources.get(source_id)
            project = [
                candidate
                for candidate in self.sources.list(2**31 - 1, include_hidden=True)
                if candidate.project_id == source.project_id
            ]
            if any(
                attempt.status
                in {
                    Krea2EditAttemptStatus.QUEUED,
                    Krea2EditAttemptStatus.RUNNING,
                    Krea2EditAttemptStatus.CANCEL_PENDING,
                }
                for candidate in project
                for attempt in candidate.attempts
            ):
                raise ValueError("an active KREA2 edit project cannot be archived")
            updated: Krea2EditSource | None = None
            for candidate in project:
                saved = self.sources.save(candidate.with_state(state))
                if saved.source_id == source_id:
                    updated = saved
            assert updated is not None
            return updated

    def stream_prepare_prompt(
        self,
        source_id: str,
        instruction: str,
        model_id: str,
        *,
        base_prompt: str | None = None,
        feedback_attempt_id: str | None = None,
        prompt_language: Krea2PromptLanguage | None = None,
        include_reasoning: bool = False,
    ) -> Iterator[Krea2EditStreamEvent]:
        if not isinstance(include_reasoning, bool):
            raise TypeError("include_reasoning must be a boolean")
        normalized_base = (
            base_prompt.strip()
            if isinstance(base_prompt, str) and base_prompt.strip()
            else None
        )
        with self._lock:
            source = self.sources.get(source_id)
            if source.state is not Krea2EditSourceState.PENDING:
                raise ValueError("only the active KREA2 edit stage can prepare a prompt")
            feedback = None
            if feedback_attempt_id is not None:
                feedback = _attempt(source, feedback_attempt_id)
                if (
                    feedback.status is not Krea2EditAttemptStatus.SUCCEEDED
                    or feedback.output_asset_id is None
                ):
                    raise ValueError("prompt feedback must reference a succeeded attempt")
            source = self.sources.save(
                source.begin_prompt(instruction, model_id, prompt_language)
            )
        image_asset = self.assets.get(source.source_asset_id)
        image = self.assets.read_bytes(source.source_asset_id)
        base = normalized_base or source.generated_prompt or source.metadata.prompt
        images = [ImageInput(image_asset.media_type, image, "STAGE SOURCE")]
        feedback_note = ""
        if feedback is not None:
            assert feedback.output_asset_id is not None
            feedback_asset = self.assets.get(feedback.output_asset_id)
            feedback_image = self.assets.read_bytes(feedback.output_asset_id)
            images.append(
                ImageInput(
                    feedback_asset.media_type,
                    feedback_image,
                    "GENERATED FEEDBACK",
                )
            )
            feedback_note = (
                "\n\nVISUAL FEEDBACK:\n"
                "Compare the GENERATED FEEDBACK with the current target and use "
                "visible discrepancies only when they help satisfy the new instruction. "
                "The next render still starts from STAGE SOURCE."
            )
        user = (
            _prompt_language_instruction(source.prompt_language)
            + "\n\nNEW EDIT INSTRUCTION (authoritative):\n"
            f"{source.instruction}\n\n"
            + (
                "CURRENT TARGET PROMPT TO REWRITE:\n" + base
                if base
                else "CURRENT TARGET PROMPT: unavailable. Reconstruct it from STAGE SOURCE."
            )
            + feedback_note
        )
        request = CompletionRequest(
            model_id=model_id,
            system_prompt=_PROMPT_SYSTEM,
            user_prompt=user,
            images=tuple(images),
            temperature=0.2,
            max_tokens=131_072,
            operation_id="krea2.edit.prompt.rewrite_or_reconstruct@0.3.0",
            include_reasoning=include_reasoning,
        )
        parts: list[str] = []
        try:
            for event in self.gateway.stream(request):
                if event.kind is StreamEventKind.DELTA:
                    parts.append(event.text)
                if event.kind is StreamEventKind.TRUNCATED:
                    raw = event.result.content if event.result is not None else "".join(parts)
                    terminal = self._finish_prompt_failure(
                        source,
                        raw,
                        truncated_response_message(request.max_tokens),
                        truncated=True,
                    )
                    self._report(event.result.call_id if event.result else None, LlmCallApplicationOutcome.REJECTED, ValueError("truncated edit prompt"))
                    yield Krea2EditStreamEvent(StreamEventKind.TRUNCATED, StreamPhase.TRUNCATED, raw, source=terminal)
                    return
                if event.kind is StreamEventKind.COMPLETED:
                    if event.result is None:
                        raise ValueError("model stream completed without a result")
                    raw = event.result.content
                    try:
                        prompt = normalize_krea2_edit_prompt(
                            raw,
                            source.prompt_language,
                        )
                        terminal = self._finish_prompt_success(
                            source,
                            raw,
                            prompt,
                            base_prompt=base,
                            feedback_attempt_id=(
                                feedback.attempt_id if feedback is not None else None
                            ),
                        )
                    except Exception as error:
                        terminal = self._finish_prompt_failure(
                            source,
                            raw,
                            _error(error),
                        )
                        self._report(event.result.call_id, LlmCallApplicationOutcome.REJECTED, error)
                    else:
                        self._report(event.result.call_id, LlmCallApplicationOutcome.ACCEPTED)
                    yield Krea2EditStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED, terminal.generated_prompt or raw, 1.0, terminal)
                    return
                yield Krea2EditStreamEvent(event.kind, event.phase, event.text, event.progress)
        except GeneratorExit:
            self._save_prompt_failure(source, "".join(parts), "Le flux de prompt a été interrompu.")
            raise
        except Exception as error:
            terminal = self._save_prompt_failure(source, "".join(parts), _error(error))
            yield Krea2EditStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED, "".join(parts), 1.0, terminal)
            return

    def prepare_attempt(self, source_id: str, request: Krea2EditAttemptRequest) -> Krea2EditSource:
        with self._lock:
            source = self.sources.get(source_id)
            if source.recipe != self.workflow.reference:
                raise ValueError("the source workflow version is not loaded")
            if source.state is not Krea2EditSourceState.PENDING:
                raise ValueError("only the active KREA2 edit stage can render")
            attempt = Krea2EditAttempt(
                attempt_id=self._attempt_id_factory(),
                prompt=request.prompt.strip(),
                settings=request.settings,
            )
            return self.sources.save(source.add_attempt(attempt))

    def promote_attempt(
        self,
        source_id: str,
        attempt_id: str,
        *,
        project_name: str | None = None,
        step_name: str | None = None,
    ) -> Krea2EditSource:
        """Promote one successful result to the immutable source of the next stage."""
        with self._lock:
            source = self.sources.get(source_id)
            all_sources = self.sources.list(2**31 - 1, include_hidden=True)
            for candidate in all_sources:
                if (
                    candidate.parent_source_id == source_id
                    and candidate.parent_attempt_id == attempt_id
                ):
                    return candidate
            if any(
                value.status
                in {
                    Krea2EditAttemptStatus.QUEUED,
                    Krea2EditAttemptStatus.RUNNING,
                    Krea2EditAttemptStatus.CANCEL_PENDING,
                }
                for value in source.attempts
            ):
                raise ValueError("an active attempt cannot be promoted")
            attempt = _attempt(source, attempt_id)
            if (
                attempt.status is not Krea2EditAttemptStatus.SUCCEEDED
                or attempt.output_asset_id is None
            ):
                raise ValueError("only a succeeded attempt can be promoted")
            self.assets.get(attempt.output_asset_id)
            project_stages = [
                value for value in all_sources if value.project_id == source.project_id
            ]
            existing_name = next(
                (value.project_name for value in project_stages if value.project_name),
                None,
            )
            requested_name = _human_label(
                project_name or existing_name or _filename_stem(source.filename),
                "project_name",
            )
            if existing_name is not None and requested_name != existing_name:
                raise ValueError("project_name cannot change after the first validation")
            accepted_label = _human_label(
                step_name or source.instruction or f"Modification {source.stage_index}",
                "step_name",
            )
            child = Krea2EditSource(
                source_id=self._source_id_factory(),
                recipe=source.recipe,
                source_asset_id=attempt.output_asset_id,
                filename=source.filename,
                metadata=Krea2EditMetadata(
                    prompt=attempt.prompt,
                    model_name=attempt.settings.model_name,
                    aspect_ratio=attempt.settings.aspect_ratio,
                    megapixels=attempt.settings.megapixels,
                    seed=attempt.settings.seed,
                    loras=attempt.settings.loras,
                    origin="edit",
                ),
                prompt_language=source.prompt_language,
                project_id=source.project_id,
                stage_index=source.stage_index + 1,
                parent_source_id=source.source_id,
                parent_attempt_id=attempt.attempt_id,
                project_name=requested_name,
                prompt_status=Krea2EditPromptStatus.READY,
                generated_prompt=attempt.prompt,
            )
            advanced = source.advance(
                attempt_id,
                project_name=requested_name,
                accepted_label=accepted_label,
            )
            self.sources.save(advanced)
            try:
                created = self.sources.create(child)
            except BaseException:
                self.sources.save(source)
                raise
            return self._export_project(created.project_id, created.source_id)

    def retry_project_export(self, source_id: str) -> Krea2EditSource:
        with self._lock:
            source = self.sources.get(source_id)
            stages = self._project_stages(source.project_id)
            if not any(value.accepted_attempt_id is not None for value in stages):
                raise ValueError("the KREA2 edit project has no validated result")
            return self._export_project(source.project_id, source.source_id)

    def _project_stages(self, project_id: str) -> tuple[Krea2EditSource, ...]:
        return tuple(
            sorted(
                (
                    value
                    for value in self.sources.list(2**31 - 1, include_hidden=True)
                    if value.project_id == project_id
                ),
                key=lambda value: value.stage_index,
            )
        )

    def _export_project(
        self,
        project_id: str,
        return_source_id: str,
    ) -> Krea2EditSource:
        if self.project_exporter is None:
            return self.sources.get(return_source_id)
        stages = self._project_stages(project_id)
        project_name = next(
            (value.project_name for value in stages if value.project_name),
            _filename_stem(stages[0].filename),
        )
        previous_path = next(
            (value.export_path for value in stages if value.export_path),
            None,
        )
        try:
            path = self.project_exporter.export(stages, self.assets)
            error = None
        except Exception as export_error:
            path = previous_path
            error = _error(export_error)
        for stage in stages:
            self.sources.save(
                stage.with_export(
                    project_name=project_name,
                    path=path,
                    error=error,
                )
            )
        return self.sources.get(return_source_id)

    def queue_attempt(self, source_id: str, attempt_id: str) -> Krea2EditSource:
        with self._lock:
            source = self.sources.get(source_id)
            active = {
                Krea2EditAttemptStatus.QUEUED,
                Krea2EditAttemptStatus.RUNNING,
                Krea2EditAttemptStatus.CANCEL_PENDING,
            }
            for candidate in self.sources.list(2**31 - 1, include_hidden=True):
                candidate = self._refresh_detached_attempts(candidate)
                if any(value.status in active for value in candidate.attempts):
                    raise ValueError("another KREA2 edit render is already active")
            attempt = _attempt(source, attempt_id).queue()
            return self.sources.save(source.replace_attempt(attempt))

    def execute_attempt(self, source_id: str, attempt_id: str) -> Krea2EditSource:
        key = (source_id, attempt_id)
        with self._lock:
            source = self.sources.get(source_id)
            attempt = _attempt(source, attempt_id)
            if attempt.status is not Krea2EditAttemptStatus.QUEUED:
                return source
            if key in self._claimed:
                raise ValueError("attempt is already executing")
            self._claimed.add(key)
        execution_id: str | None = None
        try:
            asset = self.assets.get(source.source_asset_id)
            content = self.assets.read_bytes(source.source_asset_id)
            uploaded = self.comfy.upload_image(
                content,
                filename=f"{source.source_id}{_image_extension(asset.media_type)}",
                subfolder="panelforge/krea2-edit",
            )
            source_image = getattr(uploaded, "workflow_value", None)
            if not isinstance(source_image, str) or not source_image:
                raise ValueError("ComfyUI upload did not return an image path")
            output_prefix = f"image/krea2-edit/{source.source_id}/{attempt.attempt_id}"
            workflow = self.workflow.build(
                source_image=source_image,
                prompt=attempt.prompt,
                settings=attempt.settings,
                output_prefix=output_prefix,
                sidecar_text=_sidecar(source, attempt, output_prefix),
            )
            digest = self.sources.save_compiled_workflow(source_id, attempt_id, workflow)
            with self._lock:
                current = self.sources.get(source_id)
                current_attempt = _attempt(current, attempt_id)
                if current_attempt.status is not Krea2EditAttemptStatus.QUEUED:
                    return current
                execution_id = self.comfy.submit_workflow(workflow)
                current_attempt = current_attempt.start(execution_id, digest)
                current = self.sources.save(current.replace_attempt(current_attempt))
            history = self._wait_history(source_id, attempt_id, execution_id)
            output = _extract_output_or_prefix(
                history,
                execution_id,
                self.workflow.output_node_id,
                self.workflow.output_history_field,
                output_prefix,
            )
            output_content = self.comfy.download_output(
                filename=output["filename"],
                subfolder=output["subfolder"],
                folder_type=output["type"],
            )
            if not output_content.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("KREA2 edit output is not a PNG")
            output_asset = self.assets.create(
                output_content,
                media_type=self.workflow.output_media_type,
                source_run_id=source_id,
            )
            with self._lock:
                current = self.sources.get(source_id)
                current_attempt = _attempt(current, attempt_id)
                if current_attempt.status in {Krea2EditAttemptStatus.RUNNING, Krea2EditAttemptStatus.CANCEL_PENDING}:
                    current = self.sources.save(current.replace_attempt(current_attempt.succeed(output_asset.asset_id)))
                return current
        except Exception as error:
            with self._lock:
                current = self.sources.get(source_id)
                current_attempt = _attempt(current, attempt_id)
                if current_attempt.status in {
                    Krea2EditAttemptStatus.CREATED,
                    Krea2EditAttemptStatus.QUEUED,
                    Krea2EditAttemptStatus.RUNNING,
                    Krea2EditAttemptStatus.CANCEL_PENDING,
                }:
                    if current_attempt.status is Krea2EditAttemptStatus.CANCEL_PENDING:
                        refreshed = self._refresh_detached_attempt(current, current_attempt)
                        if refreshed != current:
                            return refreshed
                        return current
                    if execution_id is not None and current_attempt.status is Krea2EditAttemptStatus.RUNNING:
                        try:
                            self.comfy.cancel_execution(execution_id)
                        except Exception as cancel_error:
                            current_attempt = current_attempt.cancel_pending(f"{_error(error)}; annulation distante : {_error(cancel_error)}")
                        else:
                            current_attempt = current_attempt.fail(_error(error))
                    else:
                        current_attempt = current_attempt.fail(_error(error))
                    current = self.sources.save(current.replace_attempt(current_attempt))
                return current
        finally:
            with self._lock:
                self._claimed.discard(key)

    def cancel_attempt(self, source_id: str, attempt_id: str) -> Krea2EditSource:
        with self._lock:
            source = self.sources.get(source_id)
            attempt = _attempt(source, attempt_id)
            if (
                attempt.status
                in {
                    Krea2EditAttemptStatus.RUNNING,
                    Krea2EditAttemptStatus.CANCEL_PENDING,
                }
                and (source_id, attempt_id) not in self._claimed
            ):
                source = self._refresh_detached_attempt(source, attempt)
                attempt = _attempt(source, attempt_id)
            if attempt.status in {Krea2EditAttemptStatus.RUNNING, Krea2EditAttemptStatus.CANCEL_PENDING}:
                assert attempt.execution_id is not None
                try:
                    cancellation = self.comfy.cancel_execution(attempt.execution_id)
                except Exception as error:
                    if attempt.status is Krea2EditAttemptStatus.RUNNING:
                        attempt = attempt.cancel_pending(_error(error))
                    else:
                        attempt = replace(attempt, error=_error(error))
                    return self.sources.save(source.replace_attempt(attempt))
                if _cancellation_action(cancellation) == "already_finished":
                    source = self._refresh_detached_attempt(source, attempt)
                    attempt = _attempt(source, attempt_id)
                    if attempt.status not in {
                        Krea2EditAttemptStatus.RUNNING,
                        Krea2EditAttemptStatus.CANCEL_PENDING,
                    }:
                        return source
                    message = (
                        "ComfyUI signale que le rendu est terminé, mais son "
                        "historique n’est pas encore disponible."
                    )
                    attempt = (
                        attempt.cancel_pending(message)
                        if attempt.status is Krea2EditAttemptStatus.RUNNING
                        else replace(attempt, error=message)
                    )
                    return self.sources.save(source.replace_attempt(attempt))
            return self.sources.save(source.replace_attempt(attempt.cancel()))

    def _wait_history(self, source_id: str, attempt_id: str, execution_id: str) -> dict[str, Any]:
        deadline = self._monotonic() + self.run_timeout
        while True:
            current = _attempt(self.sources.get(source_id), attempt_id)
            if current.status is Krea2EditAttemptStatus.CANCELLED:
                raise RuntimeError("KREA2 edit attempt cancelled")
            history = self.comfy.get_history(execution_id)
            candidate = history.get(execution_id)
            if isinstance(candidate, dict):
                status = candidate.get("status")
                if isinstance(status, dict):
                    if status.get("completed") is True and status.get("status_str") == "success":
                        return history
                    if status.get("completed") is True or status.get("status_str") == "error":
                        raise RuntimeError(f"ComfyUI execution failed: {status}")
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                raise TimeoutError(f"ComfyUI did not complete {execution_id!r} within {self.run_timeout:g} seconds")
            self._sleep(min(self.poll_interval, remaining))

    def _save_prompt_failure(self, source: Krea2EditSource, raw: str, error: str) -> Krea2EditSource:
        return self._finish_prompt_failure(source, raw, error)

    def _finish_prompt_success(
        self,
        expected: Krea2EditSource,
        raw: str,
        prompt: str,
        *,
        base_prompt: str | None,
        feedback_attempt_id: str | None,
    ) -> Krea2EditSource:
        with self._lock:
            current = self.sources.get(expected.source_id)
            if (
                current.prompt_status is not Krea2EditPromptStatus.GENERATING
                or current.instruction != expected.instruction
                or current.prompt_model_id != expected.prompt_model_id
            ):
                raise ValueError("the KREA2 edit prompt context changed during generation")
            revision = Krea2EditPromptRevision(
                revision_id=self._prompt_revision_id_factory(),
                instruction=current.instruction,
                base_prompt=base_prompt,
                prompt=prompt,
                model_id=current.prompt_model_id or expected.prompt_model_id or "unknown",
                prompt_language=current.prompt_language,
                feedback_attempt_id=feedback_attempt_id,
            )
            return self.sources.save(current.finish_prompt(raw, prompt, revision))

    def _finish_prompt_failure(
        self,
        expected: Krea2EditSource,
        raw: str | None,
        error: str,
        *,
        truncated: bool = False,
    ) -> Krea2EditSource:
        with self._lock:
            current = self.sources.get(expected.source_id)
            if (
                current.prompt_status is Krea2EditPromptStatus.GENERATING
                and current.instruction == expected.instruction
                and current.prompt_model_id == expected.prompt_model_id
            ):
                return self.sources.save(
                    current.fail_prompt(raw, error, truncated=truncated)
                )
            return current

    def _refresh_detached_attempts(self, source: Krea2EditSource) -> Krea2EditSource:
        current = source
        for attempt in source.attempts:
            if (
                attempt.status
                in {
                    Krea2EditAttemptStatus.RUNNING,
                    Krea2EditAttemptStatus.CANCEL_PENDING,
                }
                and (source.source_id, attempt.attempt_id) not in self._claimed
            ):
                current = self._refresh_detached_attempt(
                    current,
                    _attempt(current, attempt.attempt_id),
                )
        return current

    def _refresh_detached_attempt(
        self,
        source: Krea2EditSource,
        attempt: Krea2EditAttempt,
    ) -> Krea2EditSource:
        if attempt.status not in {
            Krea2EditAttemptStatus.RUNNING,
            Krea2EditAttemptStatus.CANCEL_PENDING,
        }:
            return source
        assert attempt.execution_id is not None
        try:
            history = self.comfy.get_history(attempt.execution_id)
            candidate = history.get(attempt.execution_id)
            if not isinstance(candidate, Mapping):
                return source
            status = candidate.get("status")
            if not isinstance(status, Mapping):
                return source
            terminal = _history_terminal_kind(status)
            if terminal is None:
                return source
            if terminal == "success":
                prefix = (
                    f"image/krea2-edit/{source.source_id}/{attempt.attempt_id}"
                )
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
                if not content.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("KREA2 edit output is not a PNG")
                asset = self.assets.create(
                    content,
                    media_type=self.workflow.output_media_type,
                    source_run_id=source.source_id,
                )
                updated = attempt.succeed(asset.asset_id)
            elif terminal == "interrupted":
                updated = attempt.cancel()
            else:
                updated = attempt.fail(f"ComfyUI execution failed: {status}")
        except Exception:
            return source
        return self.sources.save(source.replace_attempt(updated))

    def _report(self, call_id: str | None, outcome: LlmCallApplicationOutcome, error: Exception | None = None) -> None:
        if self.application_outcomes is None or call_id is None:
            return
        self.application_outcomes.report_application_outcome(
            call_id,
            outcome,
            error_type=type(error).__name__ if error is not None else None,
            error_message=str(error) if error is not None else None,
        )


def normalize_krea2_edit_prompt(
    raw: str,
    prompt_language: Krea2PromptLanguage = Krea2PromptLanguage.ENGLISH,
) -> str:
    if not isinstance(prompt_language, Krea2PromptLanguage):
        raise TypeError("prompt_language must be Krea2PromptLanguage")
    prompt = _text(raw, "model response").strip()
    fence = re.fullmatch(r"```(?:text|txt|prompt)?\s*\n([\s\S]*?)\n```", prompt, re.IGNORECASE)
    if fence:
        prompt = fence.group(1).strip()
    lines = prompt.splitlines()
    if lines and (
        _META_LINE.search(lines[0].strip())
        or _CHINESE_META_LINE.fullmatch(lines[0].strip())
    ):
        lines = lines[1:]
        prompt = "\n".join(lines).strip()
    if "```" in prompt:
        raise ValueError("Le modèle a renvoyé un bloc Markdown ambigu.")
    if prompt.startswith("{") or prompt.startswith("["):
        raise ValueError("Le modèle a renvoyé des données structurées au lieu d’un prompt.")
    minimum_length = (
        40
        if prompt_language is Krea2PromptLanguage.CHINESE_SIMPLIFIED
        else 80
    )
    if len(prompt) < minimum_length:
        raise ValueError("Le prompt reconstruit est trop court pour être exploitable.")
    return prompt


def _sidecar(source: Krea2EditSource, attempt: Krea2EditAttempt, output_prefix: str) -> str:
    width, height = attempt.settings.resolution
    return json.dumps({
        "schema_version": 1,
        "prompt": attempt.prompt,
        "edit": {
            "source_id": source.source_id,
            "project_id": source.project_id,
            "stage_index": source.stage_index,
            "parent_source_id": source.parent_source_id,
            "parent_attempt_id": source.parent_attempt_id,
            "source_asset_id": source.source_asset_id,
            "instruction": source.instruction,
            "prompt_language": source.prompt_language.value,
        },
        "render": {
            "model_name": attempt.settings.model_name,
            "aspect_ratio": attempt.settings.aspect_ratio.value,
            "megapixels": attempt.settings.megapixels,
            "base_width": width,
            "base_height": height,
            "seed": attempt.settings.seed,
            "ref_boost": attempt.settings.ref_boost,
            "steps": attempt.settings.steps,
            "loras": [{"name": value.name, "strength": value.strength} for value in attempt.settings.loras],
            "output_prefix": output_prefix,
        },
        "workflow": {
            "operation_id": source.recipe.operation_id,
            "recipe_id": source.recipe.recipe_id,
            "version": source.recipe.version,
            "sha256": source.recipe.workflow_sha256,
        },
    }, ensure_ascii=False, indent=2) + "\n"


def _attempt(source: Krea2EditSource, attempt_id: str) -> Krea2EditAttempt:
    found = next((value for value in source.attempts if value.attempt_id == attempt_id), None)
    if found is None:
        raise KeyError(attempt_id)
    return found


def _human_label(value: object, label: str) -> str:
    text = _text(value, label).strip()
    text = " ".join(text.split())
    if not text:
        raise ValueError(f"{label} must not be empty")
    if any(ord(character) < 32 for character in text):
        raise ValueError(f"{label} cannot contain control characters")
    if len(text) > 120:
        text = f"{text[:119].rstrip()}…"
    return text


def _filename_stem(filename: str) -> str:
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    stem = basename.rsplit(".", 1)[0] if "." in basename else basename
    return stem.strip() or "Projet KREA2"


def _extract_output_or_prefix(
    history: Mapping[str, Any],
    execution_id: str,
    node_id: str,
    field: str,
    prefix: str,
) -> dict[str, str]:
    candidate = history.get(execution_id)
    if isinstance(candidate, Mapping):
        outputs = candidate.get("outputs")
        if isinstance(outputs, Mapping):
            node = outputs.get(node_id)
            if isinstance(node, Mapping):
                images = node.get(field)
                if isinstance(images, list) and images and isinstance(images[0], Mapping):
                    value = images[0]
                    filename = value.get("filename")
                    if isinstance(filename, str) and filename:
                        return {
                            "filename": filename,
                            "subfolder": str(value.get("subfolder", "")),
                            "type": str(value.get("type", "output")),
                        }
    normalized = prefix.strip().replace("\\", "/").strip("/")
    parts = normalized.split("/")
    if not parts or any(not part or part in {".", ".."} or "%" in part for part in parts):
        raise ValueError("ComfyUI history has no expected KREA2 edit PNG")
    return {
        "filename": f"{parts[-1]}_00001_.png",
        "subfolder": "/".join(parts[:-1]),
        "type": "output",
    }


def _history_terminal_kind(status: Mapping[str, Any]) -> str | None:
    raw_name = status.get("status_str")
    name = raw_name.casefold() if isinstance(raw_name, str) else ""
    event_names: set[str] = set()
    messages = status.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, Mapping):
                raw_event = message.get("type")
            elif isinstance(message, (list, tuple)) and message:
                raw_event = message[0]
            else:
                raw_event = None
            if isinstance(raw_event, str):
                event_names.add(raw_event.casefold())
    if name in {"interrupted", "cancelled", "canceled"} or (
        "execution_interrupted" in event_names
    ):
        return "interrupted"
    if name in {"error", "failed", "failure"} or (
        "execution_error" in event_names
    ):
        return "failed"
    if name in {"success", "completed"} and (
        status.get("completed") is True or name == "completed"
    ):
        return "success"
    return None


def _cancellation_action(result: object | None) -> str | None:
    action = getattr(result, "action", None)
    value = getattr(action, "value", action)
    return value if isinstance(value, str) else None


def _image_extension(media_type: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }.get(media_type.casefold(), ".img")


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    return value


def _error(error: Exception) -> str:
    message = str(error).strip()
    return f"{type(error).__name__}: {message}" if message else type(error).__name__
