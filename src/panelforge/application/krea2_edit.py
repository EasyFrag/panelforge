"""Backlog, prompt reconstruction and iterative rendering for KREA2 Edit."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import re
import secrets
from threading import RLock
import time
from typing import Any, Protocol
from uuid import uuid4

from panelforge.domain.assets import Asset
from panelforge.domain.krea2_edit_versions import Krea2EditRevision, edit_project_versions
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
    Krea2EditRetouch,
    Krea2EditSettings,
    Krea2EditSource,
    Krea2EditSourceState,
)
from panelforge.domain.firered_edit import FireRedEditSettings
from panelforge.domain.edit_settings import EditSettings, edit_engine, edit_settings_record, edit_output_dimensions
from .image_edit import EditWorkflow, EditImages

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
from . import krea2_edit_assistance, krea2_edit_assistance_v3
from . import firered_edit_assistance
from . import krea2_restage
from .krea2_retouch import RetouchCompositor
from . import krea2_edit_upscale as enhancement
from panelforge.domain.krea2_edit import validate_retouch_harmonization


class RetouchConflictError(ValueError):
    """The stage or an idempotent save request no longer matches the editor."""


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
    def create_revision(self, stages: tuple[Krea2EditSource, ...]) -> Krea2EditSource: ...
    def save(self, source: Krea2EditSource) -> Krea2EditSource: ...
    def save_restart(self, previous: Krea2EditSource, restarted: Krea2EditSource) -> Krea2EditSource: ...
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


@dataclass(frozen=True)
class Krea2EditBacklog:
    sources: tuple[Krea2EditSource, ...]
    versions: list[dict[str, object]]
    project_ids: tuple[str, ...]
    project_count: int


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
    settings: EditSettings
    workflow_version: str | None = None
    workflow_id: str | None = None

    def __post_init__(self) -> None:
        _text(self.prompt, "prompt")
        if not isinstance(self.settings, (Krea2EditSettings, FireRedEditSettings)):
            raise TypeError("settings must belong to a supported image-edit engine")


class Krea2EditService:
    def __init__(
        self,
        *,
        gateway: MultimodalGateway,
        workflow: EditWorkflow,
        historical_workflows: tuple[EditWorkflow, ...] = (),
        comfy: Krea2EditComfy,
        assets: Krea2EditAssets,
        sources: Krea2EditStore,
        batches: Krea2BatchReader | None = None,
        project_exporter: Krea2ProjectExporter | None = None,
        retouch_compositor: RetouchCompositor | None = None,
        upscale_workflow: enhancement.UpscaleWorkflow | None = None,
        upscale_images: enhancement.UpscaleImages | None = None,
        edit_images: EditImages | None = None,
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
        self.workflows = (workflow, *historical_workflows)
        if len({(item.reference.recipe_id, item.reference.version) for item in self.workflows}) != len(self.workflows):
            raise ValueError("duplicate image-edit recipe and version")
        self.comfy = comfy
        self.assets = assets
        self.sources = sources
        self.batches = batches
        self.project_exporter = project_exporter
        self.retouch_compositor = retouch_compositor
        self.upscale_workflow = upscale_workflow
        self.upscale_images = upscale_images
        self.edit_images = edit_images
        if any(item.engine == "firered" for item in self.workflows) and edit_images is None:
            raise ValueError("FireRed requires image decoding for orientation and output dimensions")
        if any(getattr(item, "requires_subject_reference", False) for item in self.workflows) and edit_images is None:
            raise ValueError("Two-reference editing requires image decoding for both inputs")
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

    def workflow_for_attempt(self, source: Krea2EditSource, attempt: Krea2EditAttempt) -> EditWorkflow | enhancement.UpscaleWorkflow:
        if attempt.upscale:
            if self.upscale_workflow is None or self.upscale_workflow.reference != attempt.upscale.workflow:
                raise ValueError("Le workflow d’amélioration de cet essai est indisponible.")
            return self.upscale_workflow
        reference = attempt.recipe or source.recipe
        for workflow in self.workflows:
            if workflow.reference == reference:
                return workflow
        raise ValueError(f"KREA2 edit workflow {reference.version} is not loaded")

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

    def restage_assisted(self, project, attempt_id: str, *, scene_asset_id: str, instruction: str, request_id: str):
        return krea2_restage.create(self, project, attempt_id, scene_asset_id=scene_asset_id,
                                   instruction=instruction, request_id=request_id)

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
            source = self.sources.get(source_id)
            return source if self._is_historical(source) else self._refresh_detached_attempts(source)

    def project_versions(self) -> list[dict[str, object]]:
        with self._lock:
            return edit_project_versions(self.sources.list(2**31 - 1, include_hidden=True))

    def project_stages(self, project_id: str) -> tuple[Krea2EditSource, ...]:
        with self._lock:
            stages = self._project_stages(project_id)
            if not stages:
                raise KeyError(project_id)
            return stages

    def _is_historical(self, source: Krea2EditSource) -> bool:
        return any(version["project_id"] == source.project_id and version["status"] == "historical"
                   for version in self.project_versions())

    def _require_editable(self, source: Krea2EditSource) -> None:
        if source.state is not Krea2EditSourceState.PENDING or self._is_historical(source):
            raise RetouchConflictError("Cette étape est en lecture seule. Utilise « Reprendre depuis cette étape » sur une image validée.")

    @staticmethod
    def _stage_busy(source: Krea2EditSource) -> bool:
        return source.prompt_status is Krea2EditPromptStatus.GENERATING or any(
            a.status in {Krea2EditAttemptStatus.QUEUED, Krea2EditAttemptStatus.RUNNING,
                         Krea2EditAttemptStatus.CANCEL_PENDING} for a in source.attempts)

    def resume_stage(self, source_id: str, *, request_id: str) -> Krea2EditSource:
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", request_id):
            raise ValueError("Identifiant de reprise invalide.")
        with self._lock:
            source = self.sources.get(source_id)
            project_id = "krea2-edit-revision-" + hashlib.sha256(
                f"{source_id}:{request_id}".encode()).hexdigest()[:32]
            try:
                root = self.sources.get(project_id)
            except (KeyError, FileNotFoundError):
                root = None
            if root is not None:
                if not root.revision or root.revision.request_id != request_id or root.revision.source_id != source_id:
                    raise RetouchConflictError("Cette reprise correspond déjà à une autre étape.")
                return next(stage for stage in self._project_stages(project_id)
                            if stage.stage_index == root.revision.stage_index)
            if source.accepted_attempt_id is None:
                raise ValueError("Choisis une étape déjà validée pour reprendre son travail.")
            stages = tuple(stage for stage in self._project_stages(source.project_id)
                           if stage.stage_index <= source.stage_index)
            if any(self._stage_busy(stage) for stage in stages):
                raise RetouchConflictError("Attends la fin de l’échange ou du rendu avant de reprendre cette étape.")
            if [s.stage_index for s in stages] != list(range(1, source.stage_index + 1)):
                raise ValueError("La chaîne d’origine est incomplète.")
            for parent, child in zip(stages, stages[1:]):
                if (child.parent_source_id != parent.source_id
                        or child.parent_attempt_id != parent.accepted_attempt_id
                        or _attempt(parent, parent.accepted_attempt_id).output_asset_id != child.source_asset_id):
                    raise ValueError("La chaîne d’origine est incohérente.")
            accepted = _attempt(source, source.accepted_attempt_id)
            family_id = source.revision.family_id if source.revision else source.project_id
            versions = [v for v in self.project_versions() if v["family_id"] == family_id]
            revision = Krea2EditRevision(
                family_id=family_id, number=max(v["number"] for v in versions) + 1,
                source_project_id=source.project_id, source_id=source_id,
                stage_index=source.stage_index, attempt_id=accepted.attempt_id,
                attempt_count=len(source.attempts), request_id=request_id,
            )
            ids = {s.source_id: project_id if s.stage_index == 1 else f"{project_id}-s{s.stage_index}"
                   for s in stages}
            copies = []
            for stage in stages:
                self.assets.get(stage.source_asset_id)
                for attempt in stage.attempts:
                    if attempt.output_asset_id:
                        self.assets.get(attempt.output_asset_id)
                    if attempt.retouch:
                        self.assets.get(attempt.retouch.mask_asset_id)
                    if attempt.upscale:
                        for asset_id in (attempt.upscale.input_asset_id, attempt.upscale.enhanced_asset_id, attempt.upscale.mask_asset_id):
                            if asset_id:
                                self.assets.get(asset_id)
                resumed = stage.source_id == source_id
                copies.append(replace(
                    stage, source_id=ids[stage.source_id], project_id=project_id,
                    parent_source_id=ids.get(stage.parent_source_id),
                    revision=revision, copied_from_source_id=stage.source_id, revision_activation=0,
                    source_batch_id=None, source_batch_item_id=None,
                    state=Krea2EditSourceState.PENDING if resumed else Krea2EditSourceState.ADVANCED,
                    accepted_attempt_id=None if resumed else stage.accepted_attempt_id,
                    generated_prompt=accepted.prompt if resumed else stage.generated_prompt,
                    prompt_status=Krea2EditPromptStatus.READY if resumed else stage.prompt_status,
                    prompt_error=None, raw_prompt_response=None, export_path=None, export_error=None,
                    restart_count=0,
                ))
            return self.sources.create_revision(tuple(copies))

    def backlog(self, project_limit: int = 3, *, project_id: str | None = None) -> Krea2EditBacklog:
        """Recent workshop families, keeping every stage of the open project.

        The store returns sources by modification time. Read it once for both
        family selection and versions; only selected projects are serialized.
        """
        if type(project_limit) is not int or project_limit < 0:
            raise ValueError("project_limit must be a non-negative integer")
        self.sync_batch_sources()
        with self._lock:
            sources = self.sources.list(2**31 - 1, include_hidden=True)
            versions = edit_project_versions(sources)
            by_id = {v["project_id"]: v for v in versions}
            groups: dict[str, list[Krea2EditSource]] = {}
            for source in sources:
                if (source.state in {Krea2EditSourceState.PENDING, Krea2EditSourceState.ADVANCED}
                        and by_id[source.project_id]["status"] != "historical"):
                    groups.setdefault(source.project_id, []).append(source)
            families: dict[str, str] = {}
            for candidate, stages in groups.items():
                if not any(s.state is Krea2EditSourceState.PENDING for s in stages):
                    continue
                version = by_id[candidate]
                previous = families.get(version["family_id"])
                if previous is None or version["number"] > by_id[previous]["number"]:
                    families[version["family_id"]] = candidate
            candidates = set(families.values())
            recent = [candidate for candidate in groups if candidate in candidates]
            visible = tuple(recent[:project_limit])
            selected = set(visible)
            if project_id is not None:
                selected.add(project_id)
            # Keep complete chains, including the pinned historical version.
            # Detached jobs outside the visible/open projects are not polled.
            stages = tuple(
                source if by_id[source.project_id]["status"] == "historical"
                else self._refresh_detached_attempts(source)
                for source in sources if source.project_id in selected
            )
            return Krea2EditBacklog(stages, versions, visible, len(recent))

    def list(self, limit: int = 100, *, include_hidden: bool = False) -> list[Krea2EditSource]:
        self.sync_batch_sources(limit=max(limit, 100))
        with self._lock:
            selected = self.sources.list(limit, include_hidden=include_hidden)
            project_ids = {source.project_id for source in selected}
            versions = self.project_versions()
            families = {v["family_id"] for v in versions if v["project_id"] in project_ids}
            project_ids.update(v["project_id"] for v in versions
                               if v["family_id"] in families and v["status"] != "historical")
            historical = {v["project_id"] for v in versions if v["status"] == "historical"}
            return [
                source if source.project_id in historical else self._refresh_detached_attempts(source)
                for source in self.sources.list(2**31 - 1, include_hidden=include_hidden)
                if source.project_id in project_ids
            ]

    def set_state(self, source_id: str, state: Krea2EditSourceState) -> Krea2EditSource:
        if state not in {
            Krea2EditSourceState.PROCESSED,
            Krea2EditSourceState.HIDDEN,
        }:
            raise ValueError("a KREA2 edit project can only be processed or hidden")
        with self._lock:
            source = self.sources.get(source_id)
            if self._is_historical(source):
                raise RetouchConflictError("Cette version historique reste consultable en lecture seule.")
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

    def restart_stage(self, source_id: str, *, expected_restart_count: int) -> Krea2EditSource:
        if type(expected_restart_count) is not int or expected_restart_count < 0:
            raise ValueError("Compteur de reprise invalide.")
        with self._lock:
            source = self.sources.get(source_id)
            # A retry must never erase work begun after the acknowledged restart.
            if source.restart_count > expected_restart_count:
                return source
            if source.restart_count != expected_restart_count:
                raise RetouchConflictError("L’état de l’étape a changé. Recharge l’atelier.")
            self._require_editable(source)
            try:
                restarted = source.restart()
            except ValueError as error:
                raise RetouchConflictError(str(error)) from error
            return self.sources.save_restart(source, restarted)

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
        assistance_version: str = "1.0.0",
        render_engine: str = "krea2",
    ) -> Iterator[Krea2EditStreamEvent]:
        writers = {writer.VERSION: writer for writer in (krea2_edit_assistance, krea2_edit_assistance_v3)}
        if assistance_version not in {"1.0.0", *writers}:
            raise ValueError("unsupported edit assistance version")
        writer = writers.get(assistance_version)
        if render_engine not in {"krea2", "firered"}:
            raise ValueError("unsupported edit prompt engine")
        if render_engine == "firered":
            if assistance_version != "3.0.0" or not any(w.engine == "firered" for w in self.workflows):
                raise ValueError("FireRed prompting requires the configured engine and targeted instructions V3")
            writer = firered_edit_assistance
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
            if source.subject_reference and render_engine != "krea2":
                raise ValueError("Cet atelier décor + sujet utilise Identity Edit.")
            self._require_editable(source)
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
        if source.subject_reference:
            subject_asset = self.assets.get(source.subject_reference.asset_id)
            images = [ImageInput("image/png", self.edit_images.normalize_source(image), "STAGE SOURCE"),
                      ImageInput("image/png", self.edit_images.normalize_source(self.assets.read_bytes(subject_asset.asset_id)), "SUBJECT REFERENCE")]
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
        if writer in (krea2_edit_assistance_v3, firered_edit_assistance):
            user = writer.user_prompt(
                source, language_instruction=_prompt_language_instruction(source.prompt_language),
                base_prompt=normalized_base, feedback_note=feedback_note,
            )
        elif writer:
            user += krea2_edit_assistance.context(source)
        if source.subject_reference:
            user += krea2_restage.PROMPT_CONTEXT
        request = CompletionRequest(
            model_id=model_id,
            system_prompt=(writer.SYSTEM if writer else _PROMPT_SYSTEM) + (krea2_restage.PROMPT_CONTEXT if source.subject_reference else ""),
            user_prompt=user,
            images=tuple(images),
            temperature=0.2,
            max_tokens=131_072,
            operation_id=(writer.OPERATION if writer
                          else "krea2.edit.prompt.rewrite_or_reconstruct@0.3.0"),
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
                        assistant_message, candidate = (
                            writer.decode(raw) if writer else (None, raw)
                        )
                        prompt = normalize_krea2_edit_prompt(
                            candidate,
                            source.prompt_language,
                            allow_short_edit=writer in (krea2_edit_assistance_v3, firered_edit_assistance),
                        )
                        terminal = self._finish_prompt_success(
                            source,
                            raw,
                            prompt,
                            base_prompt=base,
                            feedback_attempt_id=(
                                feedback.attempt_id if feedback is not None else None
                            ),
                            assistant_message=assistant_message,
                            assistance_version=assistance_version,
                            render_engine=render_engine,
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
            choices = [item for item in self.workflows if item.engine == edit_engine(request.settings)]
            choices = [item for item in choices if bool(getattr(item, "requires_subject_reference", False)) == bool(source.subject_reference)]
            workflow = next((item for item in choices
                             if (request.workflow_id is None or item.reference.recipe_id == request.workflow_id)
                             and (request.workflow_version is None or item.reference.version == request.workflow_version)), None)
            if workflow is None:
                raise ValueError("the requested image-edit recipe/version is not loaded for this engine")
            self._require_editable(source)
            if isinstance(request.settings, FireRedEditSettings):
                if request.settings.model_name != workflow.defaults["model_id"]:
                    raise ValueError("Le modèle ne correspond pas à cette recette FireRed.")
                self.edit_images.dimensions(self.assets.read_bytes(source.source_asset_id))
            attempt = Krea2EditAttempt(
                attempt_id=self._attempt_id_factory(),
                prompt=request.prompt.strip(),
                settings=request.settings,
                recipe=workflow.reference,
            )
            return self.sources.save(source.add_attempt(attempt))

    def prepare_upscale(self, source_id: str, attempt_id: str, *, model_name: str, request_id: str):
        return enhancement.prepare_upscale(self, source_id, attempt_id, model_name=model_name, request_id=request_id)

    def queue_upscale(self, source_id: str, attempt_id: str, *, model_name: str, request_id: str):
        source, candidate = self.prepare_upscale(source_id, attempt_id, model_name=model_name, request_id=request_id)
        with self._lock:
            source = self.sources.get(source_id)
            candidate = _attempt(source, candidate.attempt_id)
            should_start = candidate.status is Krea2EditAttemptStatus.CREATED
            if should_start:
                source = self.queue_attempt(source_id, candidate.attempt_id)
            return source, _attempt(source, candidate.attempt_id), should_start

    def _retouch_inputs(self, source: Krea2EditSource, attempt_id: str) -> tuple[Krea2EditAttempt, Krea2EditAttempt]:
        selected = _attempt(source, attempt_id)
        if selected.status is not Krea2EditAttemptStatus.SUCCEEDED:
            raise ValueError("Choisis un essai réussi pour le retoucher.")
        original = _attempt(source, selected.retouch.original_attempt_id) if selected.retouch else selected
        if original.output_asset_id is None:
            raise ValueError("Le rendu d’origine est indisponible.")
        return selected, original

    def prepare_retouch(self, source_id: str, attempt_id: str) -> dict[str, object]:
        if self.retouch_compositor is None:
            raise ValueError("La retouche n’est pas configurée.")
        with self._lock:
            source = self.sources.get(source_id)
            selected, original = self._retouch_inputs(source, attempt_id)
        prepared = self.retouch_compositor.prepare(
            self.assets.read_bytes(source.source_asset_id),
            self.assets.read_bytes(enhancement.generation_asset(original)),
        )
        mask = enhancement.mask_settings(selected)
        return {
            "source_id": source_id, "attempt_id": attempt_id,
            "original_attempt_id": original.attempt_id,
            "label": source.attempt_label(attempt_id),
            "editable": source.state is Krea2EditSourceState.PENDING and not self._is_historical(source),
            "width": prepared.width, "height": prepared.height,
            "source_png": prepared.source_png, "generated_png": prepared.generated_png,
            "harmonized_png": prepared.harmonized_png,
            "harmonize": mask.harmonize if mask else False,
            "harmonize_strength": mask.harmonize_strength if mask else 100,
            "color_method": "reinhard_lab_rgb@1.0.0",
            "mask_png": self.assets.read_bytes(mask.mask_asset_id) if mask and mask.mask_asset_id else None,
        }

    def save_retouch(self, source_id: str, attempt_id: str, mask: bytes,
                     *, request_id: str, harmonize: bool = False,
                     harmonize_strength: int = 100) -> tuple[Krea2EditSource, Krea2EditAttempt]:
        validate_retouch_harmonization(harmonize, harmonize_strength)
        if self.retouch_compositor is None:
            raise ValueError("La retouche n’est pas configurée.")
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", request_id):
            raise ValueError("Identifiant d’enregistrement invalide.")
        if not isinstance(mask, bytes) or not mask or len(mask) > 25 * 1024 * 1024:
            raise ValueError("Masque vide ou supérieur à 25 Mio.")
        digest = hashlib.sha256(mask).hexdigest()

        def existing(current: Krea2EditSource) -> Krea2EditAttempt | None:
            for candidate in current.attempts:
                if candidate.retouch and candidate.retouch.request_id == request_id:
                    if (candidate.retouch.parent_attempt_id != attempt_id
                            or candidate.retouch.submitted_mask_sha256 != digest
                            or candidate.retouch.harmonize != harmonize
                            or candidate.retouch.harmonize_strength != harmonize_strength):
                        raise RetouchConflictError("Cet enregistrement correspond déjà à une autre retouche.")
                    return candidate
            return None

        with self._lock:
            source = self.sources.get(source_id)
            found = existing(source)
            if found is not None:
                return source, found
            if source.state is not Krea2EditSourceState.PENDING:
                raise RetouchConflictError("Cette étape est déjà validée ou archivée. Le brouillon reste disponible.")
            self._require_editable(source)
            _, original = self._retouch_inputs(source, attempt_id)
        composed = self.retouch_compositor.compose(
            self.assets.read_bytes(source.source_asset_id),
            self.assets.read_bytes(enhancement.generation_asset(original)), mask,
            harmonize=harmonize, harmonize_strength=harmonize_strength,
        )
        with self._lock:
            current = self.sources.get(source_id)
            found = existing(current)
            if found is not None:
                return current, found
            if current.restart_count != source.restart_count:
                raise RetouchConflictError("Cette étape a été recommencée pendant la retouche. Recharge l’atelier.")
            if current.state is not Krea2EditSourceState.PENDING:
                raise RetouchConflictError("Cette étape a été validée pendant la retouche. Le brouillon reste disponible.")
            self._require_editable(current)
            mask_asset = self.assets.create(composed.mask_png, media_type="image/png", source_run_id=source_id)
            output = self.assets.create(composed.output_png, media_type="image/png", source_run_id=source_id)
            candidate = Krea2EditAttempt(
                attempt_id=self._attempt_id_factory(), prompt=original.prompt, settings=original.settings,
                recipe=original.recipe or current.recipe,
                status=Krea2EditAttemptStatus.SUCCEEDED, kind="retouch", output_asset_id=output.asset_id,
                retouch=Krea2EditRetouch(
                    original_attempt_id=original.attempt_id, parent_attempt_id=attempt_id,
                    source_asset_id=current.source_asset_id, generated_asset_id=enhancement.generation_asset(original),
                    mask_asset_id=mask_asset.asset_id, width=composed.width, height=composed.height,
                    request_id=request_id, submitted_mask_sha256=digest,
                    harmonize=harmonize, harmonize_strength=harmonize_strength,
                ),
            )
            # A local composition does not change an in-flight conversation or prompt.
            saved = self.sources.save(replace(current, attempts=(*current.attempts, candidate)))
            return saved, candidate

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
            self._require_editable(source)
            if self._stage_busy(source):
                raise RetouchConflictError("Attends la fin de l’échange ou du rendu avant de valider.")
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
                recipe=self.workflow.reference if source.subject_reference else attempt.recipe or source.recipe,
                source_asset_id=attempt.output_asset_id,
                filename=source.filename,
                metadata=Krea2EditMetadata(
                    prompt=None if source.subject_reference else attempt.prompt,
                    model_name=attempt.settings.model_name,
                    aspect_ratio=attempt.settings.aspect_ratio if isinstance(attempt.settings, Krea2EditSettings) else None,
                    megapixels=attempt.settings.megapixels,
                    seed=attempt.settings.seed,
                    loras=attempt.settings.loras if isinstance(attempt.settings, Krea2EditSettings) else (),
                    origin="upscale" if attempt.upscale else "retouch" if attempt.retouch else "edit",
                    ref_boost=attempt.settings.ref_boost if isinstance(attempt.settings, Krea2EditSettings) else None,
                    steps=attempt.settings.steps,
                    firered_settings=attempt.settings if isinstance(attempt.settings, FireRedEditSettings) else None,
                ),
                prompt_language=source.prompt_language,
                project_id=source.project_id,
                stage_index=source.stage_index + 1,
                parent_source_id=source.source_id,
                parent_attempt_id=attempt.attempt_id,
                project_name=requested_name,
                revision=source.revision,
                prompt_status=Krea2EditPromptStatus.IDLE if source.subject_reference else Krea2EditPromptStatus.READY,
                generated_prompt=None if source.subject_reference else attempt.prompt,
                prompt_model_id=source.prompt_model_id,
            )
            advanced = source.advance(
                attempt_id,
                project_name=requested_name,
                accepted_label=accepted_label,
            )
            if source.revision and source.stage_index == source.revision.stage_index:
                versions = [v for v in self.project_versions() if v["family_id"] == source.revision.family_id]
                active_ids = {v["project_id"] for v in versions if v["status"] == "active"}
                if any(s.project_id in active_ids and self._stage_busy(s) for s in all_sources):
                    raise RetouchConflictError("Un échange ou un rendu est encore actif dans l’ancienne version. Attends sa fin avant de valider la nouvelle.")
                advanced = replace(advanced, revision_activation=max(v["activation"] for v in versions) + 1)
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
            self._require_editable(source)
            if _attempt(source, attempt_id).kind == "retouch":
                raise ValueError("Une retouche locale ne peut pas être envoyée à ComfyUI.")
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
            self._require_editable(source)
            if key in self._claimed:
                raise ValueError("attempt is already executing")
            self._claimed.add(key)
        execution_id: str | None = None
        try:
            render_workflow = self.workflow_for_attempt(source, attempt)
            input_id = attempt.upscale.input_asset_id if attempt.upscale else source.source_asset_id
            asset = self.assets.get(input_id)
            content = self.assets.read_bytes(input_id)
            fire_source = isinstance(attempt.settings, FireRedEditSettings) and not attempt.upscale
            two_inputs = source.subject_reference is not None and not attempt.upscale
            if two_inputs and not getattr(render_workflow, "requires_subject_reference", False):
                raise ValueError("Le workflow de cet essai ne prend pas les deux références.")
            if fire_source or two_inputs:
                content = self.edit_images.normalize_source(content)
            if attempt.upscale:
                if attempt.upscale.model_name not in self.comfy.list_upscale_models():
                    raise ValueError("L’upscaler sélectionné est indisponible.")
                prepared = self.upscale_images.prepare(self.assets.read_bytes(source.source_asset_id), content)
                if (prepared.width, prepared.height) != (attempt.upscale.width, attempt.upscale.height):
                    raise ValueError("Les dimensions de la source ont changé.")
                content = prepared.image_png
            uploaded = self.comfy.upload_image(
                content,
                filename=f"{attempt.attempt_id if attempt.upscale else source.source_id}{'.png' if attempt.upscale or fire_source or two_inputs else _image_extension(asset.media_type)}",
                subfolder="panelforge/krea2-edit",
            )
            source_image = getattr(uploaded, "workflow_value", None)
            if not isinstance(source_image, str) or not source_image:
                raise ValueError("ComfyUI upload did not return an image path")
            reference_inputs = {}
            if two_inputs:
                subject_content = self.edit_images.normalize_source(self.assets.read_bytes(source.subject_reference.asset_id))
                uploaded_subject = self.comfy.upload_image(subject_content,
                    filename=f"{source.source_id}-subject.png", subfolder="panelforge/krea2-edit")
                subject_image = getattr(uploaded_subject, "workflow_value", None)
                if not isinstance(subject_image, str) or not subject_image:
                    raise ValueError("ComfyUI upload did not return the subject image path")
                reference_inputs["subject_image"] = subject_image
            output_prefix = f"image/krea2-edit/{source.source_id}/{attempt.attempt_id}"
            workflow = render_workflow.build(
                source_image=source_image, model_name=attempt.upscale.model_name,
                width=attempt.upscale.width, height=attempt.upscale.height, output_prefix=output_prefix,
            ) if attempt.upscale else render_workflow.build(
                source_image=source_image,
                prompt=attempt.prompt,
                settings=attempt.settings,
                output_prefix=output_prefix,
                sidecar_text=_sidecar(source, attempt, output_prefix),
                **reference_inputs,
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
                render_workflow.output_node_id,
                render_workflow.output_history_field,
                output_prefix,
            )
            output_content = self.comfy.download_output(
                filename=output["filename"],
                subfolder=output["subfolder"],
                folder_type=output["type"],
            )
            if not output_content.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("KREA2 edit output is not a PNG")
            with self._lock:
                current = self.sources.get(source_id)
                current_attempt = _attempt(current, attempt_id)
                if current_attempt.status in {Krea2EditAttemptStatus.RUNNING, Krea2EditAttemptStatus.CANCEL_PENDING}:
                    completed = self._finish_render_output(current, current_attempt, output_content)
                    current = self.sources.save(current.replace_attempt(completed))
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
            if self._is_historical(source):
                raise RetouchConflictError("Cette version historique reste consultable en lecture seule.")
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
        assistant_message: str | None = None,
        assistance_version: str = "1.0.0",
        render_engine: str = "krea2",
    ) -> Krea2EditSource:
        with self._lock:
            current = self.sources.get(expected.source_id)
            if (
                current.prompt_status is not Krea2EditPromptStatus.GENERATING
                or current.restart_count != expected.restart_count
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
                assistant_message=assistant_message,
                assistance_version=assistance_version,
                render_engine=render_engine,
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
                and current.restart_count == expected.restart_count
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
                render_workflow = self.workflow_for_attempt(source, attempt)
                prefix = (
                    f"image/krea2-edit/{source.source_id}/{attempt.attempt_id}"
                )
                output = _extract_output_or_prefix(
                    history,
                    attempt.execution_id,
                    render_workflow.output_node_id,
                    render_workflow.output_history_field,
                    prefix,
                )
                content = self.comfy.download_output(
                    filename=output["filename"],
                    subfolder=output["subfolder"],
                    folder_type=output["type"],
                )
                if not content.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("KREA2 edit output is not a PNG")
                updated = self._finish_render_output(source, attempt, content)
            elif terminal == "interrupted":
                updated = attempt.cancel()
            else:
                updated = attempt.fail(f"ComfyUI execution failed: {status}")
        except Exception:
            return source
        return self.sources.save(source.replace_attempt(updated))

    def _finish_render_output(self, source, attempt, content):
        if attempt.upscale:
            return enhancement.finish_upscale(self, source, attempt, content)
        dimensions = (self.edit_images.dimensions(content)
                      if isinstance(attempt.settings, FireRedEditSettings) or source.subject_reference else None)
        asset = self.assets.create(content, media_type="image/png", source_run_id=source.source_id)
        return attempt.succeed(asset.asset_id, dimensions=dimensions)

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
    *,
    allow_short_edit: bool = False,
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
    if not prompt or (not allow_short_edit and len(prompt) < minimum_length):
        raise ValueError("Le prompt reconstruit est trop court pour être exploitable.")
    return prompt


def _sidecar(source: Krea2EditSource, attempt: Krea2EditAttempt, output_prefix: str) -> str:
    width, height = edit_output_dimensions(attempt) or (None, None)
    recipe = attempt.recipe or source.recipe
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
            **({"subject_reference": asdict(source.subject_reference)} if source.subject_reference else {}),
            "instruction": source.instruction,
            "prompt_language": source.prompt_language.value,
        },
        "render": {
            **edit_settings_record(attempt.settings, string_seed=False),
            "base_width": width,
            "base_height": height,
            "output_prefix": output_prefix,
        },
        "workflow": {
            "operation_id": recipe.operation_id,
            "recipe_id": recipe.recipe_id,
            "version": recipe.version,
            "sha256": recipe.workflow_sha256,
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
