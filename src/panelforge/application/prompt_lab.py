"""Supervised prompt-reference analysis use cases."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import math
from typing import Protocol
from uuid import uuid4

from panelforge.domain import (
    AnalysisRevision,
    BriefReferenceSnapshot,
    BriefRevision,
    InterpretationRevision,
    PromptLabSession,
    PromptReference,
    ReferenceUse,
    RevisionOrigin,
)

from .revised_documents import RevisedDocumentContract


_OBSERVATION_LEGACY_CONTRACT = RevisedDocumentContract(
    "visual observation",
    (
        "- DESCRIPTION VISIBLE",
        "- IDENTITÉ ET TRAITS DISTINCTIFS",
        "- VÊTEMENTS ET ACCESSOIRES",
        "- POSE, EXPRESSION ET CADRAGE",
        "- DÉCOR, LUMIÈRE ET STYLE",
        "- ÉLÉMENTS À PRÉSERVER",
        "- INCERTITUDES",
    ),
)
_OBSERVATION_CONTRACT = RevisedDocumentContract(
    "visual observation",
    (
        "- TYPE D'IMAGE ET DESCRIPTION GLOBALE",
        "- SUJETS VISIBLES",
        "- ÂGE APPARENT ET INCERTITUDE",
        "- APPARENCE ET TRAITS DISTINCTIFS",
        "- VÊTEMENTS, ACCESSOIRES ET OBJETS",
        "- ACTIONS ET INTERACTIONS VISIBLES",
        "- POSITIONS, ORIENTATIONS ET CONTACTS",
        "- POSE, EXPRESSION ET DIRECTION DU REGARD",
        "- COMPOSITION, CADRAGE ET CAMÉRA",
        "- DÉCOR, LUMIÈRE ET STYLE",
        "- CONTENU SENSIBLE OU ADULTE VISIBLE",
        "- ÉLÉMENTS À PRÉSERVER",
        "- INCERTITUDES",
    ),
)
_INTERPRETATION_CONTRACT = RevisedDocumentContract(
    "reference interpretation",
    (
        "- reference_role",
        "- subject_candidates",
        "- picture_anchor",
        "- initial_frame_state",
        "- preservation_requirements",
        "- prompt_implications",
        "- uncertainties",
    ),
)
_BRIEF_CONTRACT = RevisedDocumentContract(
    "structured brief",
    (
        "INTENTION CENTRALE",
        "RÉFÉRENCES CITÉES ET RÔLES",
        "SUJETS ET IDENTITÉS À PRÉSERVER",
        "DÉCOR ET ÉTAT INITIAL",
        "CHRONOLOGIE ET ACTIONS DEMANDÉES",
        "CAMÉRA, LUMIÈRE ET MISE EN SCÈNE",
        "CONTRAINTES STRICTES",
        "LIBERTÉS AUTORISÉES",
        "QUESTIONS OU AMBIGUÏTÉS",
    ),
)


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    model_id: str


@dataclass(frozen=True, slots=True)
class ImageInput:
    media_type: str
    content: bytes
    label: str


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    model_id: str
    system_prompt: str
    user_prompt: str
    images: tuple[ImageInput, ...] = ()
    temperature: float = 0.2
    max_tokens: int = 32768
    operation_id: str = "unspecified"


@dataclass(frozen=True, slots=True)
class CompletionResult:
    model_id: str
    content: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None


class StreamEventKind(StrEnum):
    STATUS = "status"
    DELTA = "delta"
    COMPLETED = "completed"
    TRUNCATED = "truncated"


class StreamPhase(StrEnum):
    PREPARING = "preparing"
    LOADING = "loading"
    GENERATING = "generating"
    COMPLETED = "completed"
    TRUNCATED = "truncated"


class LlmCallStatus(StrEnum):
    SUCCEEDED = "succeeded"
    TRUNCATED = "truncated"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class LlmCallImage:
    label: str
    media_type: str
    byte_size: int
    sha256: str

    def __post_init__(self) -> None:
        for value, name in ((self.label, "label"), (self.media_type, "media_type")):
            _require_non_empty_text(value, name)
        if (
            isinstance(self.byte_size, bool)
            or not isinstance(self.byte_size, int)
            or self.byte_size < 0
        ):
            raise ValueError("byte_size must be a non-negative integer")
        if (
            not isinstance(self.sha256, str)
            or len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")


@dataclass(frozen=True, slots=True)
class LlmCallRecord:
    call_id: str
    operation_id: str
    requested_model_id: str
    actual_model_id: str | None
    started_at: datetime
    duration_ms: int
    status: LlmCallStatus
    system_prompt: str
    user_prompt: str
    images: tuple[LlmCallImage, ...]
    temperature: float
    max_tokens: int
    response_text: str
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    error_type: str | None
    error_message: str | None

    def __post_init__(self) -> None:
        for value, name in (
            (self.call_id, "call_id"),
            (self.operation_id, "operation_id"),
            (self.requested_model_id, "requested_model_id"),
        ):
            _require_non_empty_text(value, name)
        _require_optional_text(self.actual_model_id, "actual_model_id")
        if not isinstance(self.started_at, datetime) or self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
        if (
            isinstance(self.duration_ms, bool)
            or not isinstance(self.duration_ms, int)
            or self.duration_ms < 0
        ):
            raise ValueError("duration_ms must be a non-negative integer")
        if not isinstance(self.status, LlmCallStatus):
            raise TypeError("status must be an LlmCallStatus")
        for value, name in (
            (self.system_prompt, "system_prompt"),
            (self.user_prompt, "user_prompt"),
            (self.response_text, "response_text"),
        ):
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string")
        if not isinstance(self.images, tuple) or not all(
            isinstance(image, LlmCallImage) for image in self.images
        ):
            raise TypeError("images must be a tuple of LlmCallImage")
        if (
            isinstance(self.temperature, bool)
            or not isinstance(self.temperature, (int, float))
            or not math.isfinite(self.temperature)
        ):
            raise ValueError("temperature must be finite")
        _require_non_negative_int(self.max_tokens, "max_tokens", positive=True)
        _require_optional_text(self.finish_reason, "finish_reason")
        _require_optional_non_negative_int(self.prompt_tokens, "prompt_tokens")
        _require_optional_non_negative_int(
            self.completion_tokens,
            "completion_tokens",
        )
        _require_optional_text(self.error_type, "error_type")
        _require_optional_text(self.error_message, "error_message")


@dataclass(frozen=True, slots=True)
class CompletionStreamEvent:
    kind: StreamEventKind
    phase: StreamPhase
    text: str = ""
    progress: float | None = None
    result: CompletionResult | None = None


@dataclass(frozen=True, slots=True)
class PromptLabStreamEvent:
    kind: StreamEventKind
    phase: StreamPhase
    text: str = ""
    progress: float | None = None
    session: PromptLabSession | None = None
    finish_reason: str | None = None
    max_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class PromptProfile:
    profile_id: str
    version: str
    display_name: str
    target_model_family: str
    analysis_system_prompt: str
    analysis_user_prompt: str
    revision_system_prompt: str
    revision_user_prompt: str
    interpretation_system_prompt: str | None = None
    interpretation_user_prompt: str | None = None
    interpretation_revision_system_prompt: str | None = None
    interpretation_revision_user_prompt: str | None = None
    brief_system_prompt: str | None = None
    brief_user_prompt: str | None = None
    brief_revision_system_prompt: str | None = None
    brief_revision_user_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class NewReference:
    asset_id: str
    role: str
    label: str
    uses: tuple[ReferenceUse, ...] = (ReferenceUse.SUBJECT,)


class MultimodalGateway(Protocol):
    def list_models(self) -> tuple[ModelDescriptor, ...]: ...

    def complete(self, request: CompletionRequest) -> CompletionResult: ...

    def stream(self, request: CompletionRequest) -> Iterator[CompletionStreamEvent]: ...


class LlmCallLogStore(Protocol):
    def append(self, record: LlmCallRecord) -> None: ...

    def list(self, limit: int = 20) -> tuple[LlmCallRecord, ...]: ...


class PromptProfileCatalog(Protocol):
    def list(self) -> tuple[PromptProfile, ...]: ...

    def get(self, profile_id: str, version: str) -> PromptProfile: ...


class PromptSessionStore(Protocol):
    def create(self, session: PromptLabSession) -> PromptLabSession: ...

    def save(self, session: PromptLabSession) -> PromptLabSession: ...

    def get(self, session_id: str) -> PromptLabSession: ...

    def list(self, limit: int) -> list[PromptLabSession]: ...


class AssetStore(Protocol):
    def create(self, content: bytes, media_type: str, source_run_id: str | None = None): ...

    def get(self, asset_id: str): ...

    def read_bytes(self, asset_id: str) -> bytes: ...


class PromptLabService:
    def __init__(
        self,
        *,
        gateway: MultimodalGateway,
        profiles: PromptProfileCatalog,
        assets: AssetStore,
        sessions: PromptSessionStore,
    ) -> None:
        self.gateway = gateway
        self.profiles = profiles
        self.assets = assets
        self.sessions = sessions

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return self.gateway.list_models()

    def list_profiles(self) -> tuple[PromptProfile, ...]:
        return self.profiles.list()

    def get_profile(self, profile_id: str, version: str) -> PromptProfile:
        return self.profiles.get(profile_id, version)

    def list_sessions(self, limit: int) -> list[PromptLabSession]:
        return self.sessions.list(limit)

    def get_session(self, session_id: str) -> PromptLabSession:
        return self.sessions.get(session_id)

    def create_asset(self, content: bytes, media_type: str):
        return self.assets.create(content, media_type)

    def create_session(
        self,
        *,
        model_id: str,
        profile_id: str,
        profile_version: str,
        references: tuple[NewReference, ...],
    ) -> PromptLabSession:
        self.profiles.get(profile_id, profile_version)
        session = PromptLabSession(
            session_id=f"prompt-{uuid4().hex}",
            model_id=model_id,
            profile_id=profile_id,
            profile_version=profile_version,
            references=tuple(
                PromptReference(
                    reference_id=f"ref-{uuid4().hex}",
                    asset_id=item.asset_id,
                    role=item.role,
                    label=item.label,
                    uses=item.uses,
                )
                for item in references
            ),
        )
        return self.sessions.create(session)

    def analyze_reference(
        self,
        session_id: str,
        reference_id: str,
    ) -> PromptLabSession:
        session = self.sessions.get(session_id)
        reference = session.reference(reference_id)
        profile = self._profile(session)
        result = self.gateway.complete(
            CompletionRequest(
                model_id=session.model_id,
                system_prompt=profile.analysis_system_prompt,
                user_prompt=profile.analysis_user_prompt.format(
                    role=reference.role,
                    label=reference.label,
                    uses=", ".join(use.value for use in reference.uses),
                ),
                images=(self._image(reference),),
                operation_id="reference.observe",
            )
        )
        return self._append_revision(
            session,
            reference,
            content=_completed_content(result),
            origin=RevisionOrigin.MODEL,
        )

    def stream_analyze_reference(
        self,
        session_id: str,
        reference_id: str,
    ) -> Iterator[PromptLabStreamEvent]:
        session = self.sessions.get(session_id)
        reference = session.reference(reference_id)
        profile = self._profile(session)
        request = CompletionRequest(
            model_id=session.model_id,
            system_prompt=profile.analysis_system_prompt,
            user_prompt=profile.analysis_user_prompt.format(
                role=reference.role,
                label=reference.label,
                uses=", ".join(use.value for use in reference.uses),
            ),
            images=(self._image(reference),),
            operation_id="reference.observe",
        )
        yield from self._stream_completion(
            request,
            lambda content: self._append_revision(
                session,
                reference,
                content=content,
                origin=RevisionOrigin.MODEL,
            ),
        )

    def edit_reference(
        self,
        session_id: str,
        reference_id: str,
        content: str,
    ) -> PromptLabSession:
        session = self.sessions.get(session_id)
        reference = session.reference(reference_id)
        return self._append_revision(
            session,
            reference,
            content=content,
            origin=RevisionOrigin.MANUAL,
        )

    def revise_reference(
        self,
        session_id: str,
        reference_id: str,
        instruction: str,
    ) -> PromptLabSession:
        session = self.sessions.get(session_id)
        reference = session.reference(reference_id)
        current = reference.active_revision
        if current is None:
            raise ValueError("analyze the reference before requesting a revision")
        profile = self._profile(session)
        result = self.gateway.complete(
            CompletionRequest(
                model_id=session.model_id,
                system_prompt=profile.revision_system_prompt,
                user_prompt=profile.revision_user_prompt.format(
                    role=reference.role,
                    current_analysis=current.content,
                    instruction=instruction,
                ),
                images=(self._image(reference),),
                operation_id="reference.observe.revise",
            )
        )
        return self._append_revision(
            session,
            reference,
            content=_extract_analysis_revision(
                profile,
                _completed_content(result),
            ),
            origin=RevisionOrigin.REWRITE,
            instruction=instruction,
        )

    def stream_revise_reference(
        self,
        session_id: str,
        reference_id: str,
        instruction: str,
    ) -> Iterator[PromptLabStreamEvent]:
        session = self.sessions.get(session_id)
        reference = session.reference(reference_id)
        current = reference.active_revision
        if current is None:
            raise ValueError("analyze the reference before requesting a revision")
        profile = self._profile(session)
        request = CompletionRequest(
            model_id=session.model_id,
            system_prompt=profile.revision_system_prompt,
            user_prompt=profile.revision_user_prompt.format(
                role=reference.role,
                current_analysis=current.content,
                instruction=instruction,
            ),
            images=(self._image(reference),),
            operation_id="reference.observe.revise",
        )
        yield from self._stream_completion(
            request,
            lambda content: self._append_revision(
                session,
                reference,
                content=_extract_analysis_revision(profile, content),
                origin=RevisionOrigin.REWRITE,
                instruction=instruction,
            ),
        )

    def approve_reference(
        self,
        session_id: str,
        reference_id: str,
    ) -> PromptLabSession:
        session = self.sessions.get(session_id)
        updated = session.update_reference(session.reference(reference_id).approve())
        return self.sessions.save(updated)

    def set_reference_uses(
        self,
        session_id: str,
        reference_id: str,
        uses: tuple[ReferenceUse, ...],
    ) -> PromptLabSession:
        session = self.sessions.get(session_id)
        updated = session.update_reference(
            session.reference(reference_id).set_uses(uses)
        )
        return self.sessions.save(updated)

    def interpret_reference(
        self,
        session_id: str,
        reference_id: str,
    ) -> PromptLabSession:
        session = self.sessions.get(session_id)
        reference = session.reference(reference_id)
        analysis = reference.active_revision
        if analysis is None or reference.approved_revision_id != analysis.revision_id:
            raise ValueError("approve the visual analysis before interpreting it")
        profile = self._profile(session)
        system_prompt, user_prompt = _interpretation_prompts(profile)
        result = self.gateway.complete(
            CompletionRequest(
                model_id=session.model_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt.format(
                    role=reference.role,
                    label=reference.label,
                    uses=", ".join(use.value for use in reference.uses),
                    current_analysis=analysis.content,
                ),
                images=(),
                operation_id="reference.interpret",
            )
        )
        return self._append_interpretation(
            session,
            reference,
            content=_completed_content(result),
            origin=RevisionOrigin.MODEL,
        )

    def stream_interpret_reference(
        self,
        session_id: str,
        reference_id: str,
    ) -> Iterator[PromptLabStreamEvent]:
        session = self.sessions.get(session_id)
        reference = session.reference(reference_id)
        analysis = reference.active_revision
        if analysis is None or reference.approved_revision_id != analysis.revision_id:
            raise ValueError("approve the visual analysis before interpreting it")
        profile = self._profile(session)
        system_prompt, user_prompt = _interpretation_prompts(profile)
        request = CompletionRequest(
            model_id=session.model_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt.format(
                role=reference.role,
                label=reference.label,
                uses=", ".join(use.value for use in reference.uses),
                current_analysis=analysis.content,
            ),
            operation_id="reference.interpret",
        )
        yield from self._stream_completion(
            request,
            lambda content: self._append_interpretation(
                session,
                reference,
                content=content,
                origin=RevisionOrigin.MODEL,
            ),
        )

    def edit_interpretation(
        self,
        session_id: str,
        reference_id: str,
        content: str,
    ) -> PromptLabSession:
        session = self.sessions.get(session_id)
        reference = session.reference(reference_id)
        return self._append_interpretation(
            session,
            reference,
            content=content,
            origin=RevisionOrigin.MANUAL,
        )

    def revise_interpretation(
        self,
        session_id: str,
        reference_id: str,
        instruction: str,
    ) -> PromptLabSession:
        session = self.sessions.get(session_id)
        reference = session.reference(reference_id)
        analysis = reference.active_revision
        current = reference.active_interpretation
        if analysis is None or current is None or reference.interpretation_is_stale:
            raise ValueError("generate a current interpretation before revising it")
        profile = self._profile(session)
        system_prompt, user_prompt = _interpretation_revision_prompts(profile)
        result = self.gateway.complete(
            CompletionRequest(
                model_id=session.model_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt.format(
                    role=reference.role,
                    uses=", ".join(use.value for use in reference.uses),
                    current_analysis=analysis.content,
                    current_interpretation=current.content,
                    instruction=instruction,
                ),
                images=(),
                operation_id="reference.interpret.revise",
            )
        )
        return self._append_interpretation(
            session,
            reference,
            content=_INTERPRETATION_CONTRACT.extract(
                _completed_content(result),
                strict=False,
            ),
            origin=RevisionOrigin.REWRITE,
            instruction=instruction,
        )

    def stream_revise_interpretation(
        self,
        session_id: str,
        reference_id: str,
        instruction: str,
    ) -> Iterator[PromptLabStreamEvent]:
        session = self.sessions.get(session_id)
        reference = session.reference(reference_id)
        analysis = reference.active_revision
        current = reference.active_interpretation
        if analysis is None or current is None or reference.interpretation_is_stale:
            raise ValueError("generate a current interpretation before revising it")
        profile = self._profile(session)
        system_prompt, user_prompt = _interpretation_revision_prompts(profile)
        request = CompletionRequest(
            model_id=session.model_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt.format(
                role=reference.role,
                uses=", ".join(use.value for use in reference.uses),
                current_analysis=analysis.content,
                current_interpretation=current.content,
                instruction=instruction,
            ),
            operation_id="reference.interpret.revise",
        )
        yield from self._stream_completion(
            request,
            lambda content: self._append_interpretation(
                session,
                reference,
                content=_INTERPRETATION_CONTRACT.extract(
                    content,
                    strict=False,
                ),
                origin=RevisionOrigin.REWRITE,
                instruction=instruction,
            ),
        )

    def approve_interpretation(
        self,
        session_id: str,
        reference_id: str,
    ) -> PromptLabSession:
        session = self.sessions.get(session_id)
        updated = session.update_reference(
            session.reference(reference_id).approve_interpretation()
        )
        return self.sessions.save(updated)

    def structure_brief(
        self,
        session_id: str,
        source_text: str,
        creative_freedom: int,
    ) -> PromptLabSession:
        session = self.sessions.get(session_id)
        profile = self._profile(session)
        system_prompt, user_prompt = _brief_prompts(profile)
        context, snapshots = _brief_inputs(session)
        result = self.gateway.complete(
            CompletionRequest(
                model_id=session.model_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt.format(
                    creative_freedom=_creative_freedom(creative_freedom),
                    creative_policy=_creative_policy(creative_freedom),
                    reference_context=context,
                    source_text=_required_text(source_text, "source_text"),
                ),
                operation_id="brief.structure",
            )
        )
        return self._append_brief(
            session,
            source_text=source_text,
            content=_completed_content(result),
            creative_freedom=creative_freedom,
            references=snapshots,
            origin=RevisionOrigin.MODEL,
        )

    def stream_structure_brief(
        self,
        session_id: str,
        source_text: str,
        creative_freedom: int,
    ) -> Iterator[PromptLabStreamEvent]:
        session = self.sessions.get(session_id)
        profile = self._profile(session)
        system_prompt, user_prompt = _brief_prompts(profile)
        context, snapshots = _brief_inputs(session)
        request = CompletionRequest(
            model_id=session.model_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt.format(
                creative_freedom=_creative_freedom(creative_freedom),
                creative_policy=_creative_policy(creative_freedom),
                reference_context=context,
                source_text=_required_text(source_text, "source_text"),
            ),
            operation_id="brief.structure",
        )
        yield from self._stream_completion(
            request,
            lambda content: self._append_brief(
                session,
                source_text=source_text,
                content=content,
                creative_freedom=creative_freedom,
                references=snapshots,
                origin=RevisionOrigin.MODEL,
            ),
        )

    def edit_brief(self, session_id: str, content: str) -> PromptLabSession:
        session = self.sessions.get(session_id)
        current = session.active_brief_revision
        if current is None:
            raise ValueError("structure the brief before editing it")
        _, snapshots = _brief_inputs(session)
        return self._append_brief(
            session,
            source_text=current.source_text,
            content=_required_text(content, "content"),
            creative_freedom=current.creative_freedom,
            references=snapshots,
            origin=RevisionOrigin.MANUAL,
        )

    def revise_brief(
        self,
        session_id: str,
        instruction: str,
    ) -> PromptLabSession:
        session = self.sessions.get(session_id)
        current = _current_brief(session)
        profile = self._profile(session)
        system_prompt, user_prompt = _brief_revision_prompts(profile)
        context, snapshots = _brief_inputs(session)
        result = self.gateway.complete(
            CompletionRequest(
                model_id=session.model_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt.format(
                    creative_freedom=current.creative_freedom,
                    creative_policy=_creative_policy(current.creative_freedom),
                    reference_context=context,
                    source_text=current.source_text,
                    current_brief=current.content,
                    instruction=_required_text(instruction, "instruction"),
                ),
                operation_id="brief.revise",
            )
        )
        return self._append_brief(
            session,
            source_text=current.source_text,
            content=_BRIEF_CONTRACT.extract(
                _completed_content(result),
                strict=False,
            ),
            creative_freedom=current.creative_freedom,
            references=snapshots,
            origin=RevisionOrigin.REWRITE,
            instruction=instruction,
        )

    def stream_revise_brief(
        self,
        session_id: str,
        instruction: str,
    ) -> Iterator[PromptLabStreamEvent]:
        session = self.sessions.get(session_id)
        current = _current_brief(session)
        profile = self._profile(session)
        system_prompt, user_prompt = _brief_revision_prompts(profile)
        context, snapshots = _brief_inputs(session)
        request = CompletionRequest(
            model_id=session.model_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt.format(
                creative_freedom=current.creative_freedom,
                creative_policy=_creative_policy(current.creative_freedom),
                reference_context=context,
                source_text=current.source_text,
                current_brief=current.content,
                instruction=_required_text(instruction, "instruction"),
            ),
            operation_id="brief.revise",
        )
        yield from self._stream_completion(
            request,
            lambda content: self._append_brief(
                session,
                source_text=current.source_text,
                content=_BRIEF_CONTRACT.extract(content, strict=False),
                creative_freedom=current.creative_freedom,
                references=snapshots,
                origin=RevisionOrigin.REWRITE,
                instruction=instruction,
            ),
        )

    def approve_brief(self, session_id: str) -> PromptLabSession:
        session = self.sessions.get(session_id)
        return self.sessions.save(session.approve_brief())

    def _profile(self, session: PromptLabSession) -> PromptProfile:
        return self.profiles.get(session.profile_id, session.profile_version)

    def _image(self, reference: PromptReference) -> ImageInput:
        asset = self.assets.get(reference.asset_id)
        return ImageInput(
            media_type=asset.media_type,
            content=self.assets.read_bytes(reference.asset_id),
            label=reference.label,
        )

    def _append_revision(
        self,
        session: PromptLabSession,
        reference: PromptReference,
        *,
        content: str,
        origin: RevisionOrigin,
        instruction: str | None = None,
    ) -> PromptLabSession:
        revision = AnalysisRevision(
            revision_id=f"revision-{uuid4().hex}",
            content=content,
            origin=origin,
            parent_revision_id=reference.active_revision_id,
            instruction=instruction,
        )
        updated = session.update_reference(reference.add_revision(revision))
        return self.sessions.save(updated)

    def _append_interpretation(
        self,
        session: PromptLabSession,
        reference: PromptReference,
        *,
        content: str,
        origin: RevisionOrigin,
        instruction: str | None = None,
    ) -> PromptLabSession:
        if reference.active_revision_id is None:
            raise ValueError("analyze the reference before interpreting it")
        interpretation = InterpretationRevision(
            revision_id=f"interpretation-{uuid4().hex}",
            content=content,
            origin=origin,
            source_analysis_revision_id=reference.active_revision_id,
            uses=reference.uses,
            parent_revision_id=reference.active_interpretation_id,
            instruction=instruction,
        )
        updated = session.update_reference(
            reference.add_interpretation(interpretation)
        )
        return self.sessions.save(updated)

    def _append_brief(
        self,
        session: PromptLabSession,
        *,
        source_text: str,
        content: str,
        creative_freedom: int,
        references: tuple[BriefReferenceSnapshot, ...],
        origin: RevisionOrigin,
        instruction: str | None = None,
    ) -> PromptLabSession:
        revision = BriefRevision(
            revision_id=f"brief-{uuid4().hex}",
            source_text=source_text,
            content=content,
            creative_freedom=creative_freedom,
            origin=origin,
            references=references,
            parent_revision_id=session.active_brief_revision_id,
            instruction=instruction,
        )
        return self.sessions.save(session.add_brief_revision(revision))

    def _stream_completion(
        self,
        request: CompletionRequest,
        persist: Callable[[str], PromptLabSession],
    ) -> Iterator[PromptLabStreamEvent]:
        terminal = False
        for event in self.gateway.stream(request):
            if event.kind is StreamEventKind.COMPLETED:
                if event.result is None:
                    raise ValueError("stream completed without a result")
                session = persist(event.result.content)
                terminal = True
                yield PromptLabStreamEvent(
                    kind=StreamEventKind.COMPLETED,
                    phase=StreamPhase.COMPLETED,
                    text=event.result.content,
                    progress=1.0,
                    session=session,
                    finish_reason=event.result.finish_reason,
                    max_tokens=request.max_tokens,
                )
            elif event.kind is StreamEventKind.TRUNCATED:
                if event.result is None:
                    raise ValueError("truncated stream ended without a result")
                terminal = True
                yield PromptLabStreamEvent(
                    kind=StreamEventKind.TRUNCATED,
                    phase=StreamPhase.TRUNCATED,
                    text=event.result.content,
                    finish_reason=event.result.finish_reason,
                    max_tokens=request.max_tokens,
                )
            else:
                yield PromptLabStreamEvent(
                    kind=event.kind,
                    phase=event.phase,
                    text=event.text,
                    progress=event.progress,
                )
        if not terminal:
            raise ValueError("model stream ended before completion")


def _interpretation_prompts(profile: PromptProfile) -> tuple[str, str]:
    if (
        profile.interpretation_system_prompt is None
        or profile.interpretation_user_prompt is None
    ):
        raise ValueError("this prompt profile does not support reference interpretation")
    return profile.interpretation_system_prompt, profile.interpretation_user_prompt


def _brief_prompts(profile: PromptProfile) -> tuple[str, str]:
    if profile.brief_system_prompt is None or profile.brief_user_prompt is None:
        raise ValueError("this prompt profile does not support structured briefs")
    return profile.brief_system_prompt, profile.brief_user_prompt


def _brief_revision_prompts(profile: PromptProfile) -> tuple[str, str]:
    if (
        profile.brief_revision_system_prompt is None
        or profile.brief_revision_user_prompt is None
    ):
        raise ValueError("this prompt profile does not support brief revision")
    return profile.brief_revision_system_prompt, profile.brief_revision_user_prompt


def _brief_inputs(
    session: PromptLabSession,
) -> tuple[str, tuple[BriefReferenceSnapshot, ...]]:
    if not session.analysis_complete:
        raise ValueError("approve every visual analysis before structuring the brief")
    context: list[str] = []
    snapshots: list[BriefReferenceSnapshot] = []
    for index, reference in enumerate(session.references, 1):
        analysis = reference.active_revision
        if analysis is None or reference.approved_revision_id != analysis.revision_id:
            raise ValueError("approve every visual analysis before structuring the brief")
        snapshots.append(
            BriefReferenceSnapshot(
                reference_id=reference.reference_id,
                analysis_revision_id=analysis.revision_id,
                uses=reference.uses,
            )
        )
        context.append(
            "\n".join(
                (
                    f"<Image {index}>",
                    f"Nom : {reference.label}",
                    f"Rôle utilisateur : {reference.role}",
                    "Usages : " + ", ".join(use.value for use in reference.uses),
                    "OBSERVATION APPROUVÉE",
                    analysis.content,
                )
            )
        )
    return "\n\n".join(context), tuple(snapshots)


def _current_brief(session: PromptLabSession) -> BriefRevision:
    current = session.active_brief_revision
    if current is None:
        raise ValueError("structure the brief before requesting a revision")
    if session.brief_is_stale:
        raise ValueError("the structured brief is stale; regenerate it first")
    return current


def _creative_freedom(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        raise ValueError("creative_freedom must be between 0 and 100")
    return value


def _creative_policy(value: int) -> str:
    value = _creative_freedom(value)
    if value <= 20:
        return "Factuel strict : n'ajoute aucun détail absent des entrées."
    if value <= 40:
        return "Conservateur : seulement des liaisons minimales et évidentes."
    if value <= 60:
        return "Équilibré : quelques propositions cinématographiques compatibles."
    if value <= 80:
        return "Cinématographique : enrichis caméra, rythme et ambiance sans contredire les contraintes."
    return "Exploratoire : propose librement des détails compatibles et marque-les comme libertés."


def _required_text(value: str, name: str) -> str:
    _require_non_empty_text(value, name)
    return value.strip()


def _completed_content(result: CompletionResult) -> str:
    if result.finish_reason == "length":
        raise ValueError("model response was truncated because its token budget was exhausted")
    return result.content


def _extract_analysis_revision(profile: PromptProfile, content: str) -> str:
    contract = (
        _OBSERVATION_CONTRACT
        if "- TYPE D'IMAGE ET DESCRIPTION GLOBALE" in profile.analysis_system_prompt
        else _OBSERVATION_LEGACY_CONTRACT
    )
    return contract.extract(content, strict=False)


def _interpretation_revision_prompts(profile: PromptProfile) -> tuple[str, str]:
    if (
        profile.interpretation_revision_system_prompt is None
        or profile.interpretation_revision_user_prompt is None
    ):
        raise ValueError("this prompt profile does not support interpretation revision")
    return (
        profile.interpretation_revision_system_prompt,
        profile.interpretation_revision_user_prompt,
    )


def _require_non_empty_text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")


def _require_optional_text(value: object, name: str) -> None:
    if value is not None:
        _require_non_empty_text(value, name)


def _require_non_negative_int(
    value: object,
    name: str,
    *,
    positive: bool = False,
) -> None:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        qualifier = "positive" if positive else "non-negative"
        raise ValueError(f"{name} must be a {qualifier} integer")


def _require_optional_non_negative_int(value: object, name: str) -> None:
    if value is not None:
        _require_non_negative_int(value, name)
