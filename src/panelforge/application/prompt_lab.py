"""Supervised prompt-reference analysis use cases."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import math
import re
from typing import Protocol
from uuid import uuid4

from panelforge.domain import (
    AnalysisRevision,
    BriefReferenceSnapshot,
    BriefRevision,
    CreativeFreedomAxes,
    InterpretationRevision,
    PromptLabSession,
    PromptReference,
    PromptSessionMode,
    ReferenceEvidencePolicy,
    ReferenceUse,
    RevisionOrigin,
    direct_reference_required_use,
)

from .revised_documents import RevisedDocumentContract, strip_markdown_fence
from .direct_ref2v_plan import explicit_dialogue_ledger, extract_explicit_dialogues


_H3_BASE_PROFILE_IDS = {
    "minimax.h3.fl2va.direct",
    "minimax.h3.base.animal-interview",
}
_ANIMAL_INTERVIEW_PROFILE_ID = "minimax.h3.base.animal-interview"


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
        "- INTENTION CENTRALE",
        "- RÉFÉRENCES CITÉES ET RÔLES",
        "- SUJETS ET IDENTITÉS À PRÉSERVER",
        "- DÉCOR ET ÉTAT INITIAL",
        "- CHRONOLOGIE ET ACTIONS DEMANDÉES",
        "- CAMÉRA, LUMIÈRE ET MISE EN SCÈNE",
        "- CONTRAINTES STRICTES",
        "- LIBERTÉS AUTORISÉES",
        "- QUESTIONS OU AMBIGUÏTÉS",
    ),
)
_BRIEF_HEADINGS = frozenset(
    marker.removeprefix("- ") for marker in _BRIEF_CONTRACT.markers
)


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    model_id: str
    source: str = "server"
    display_name: str | None = None


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
    max_tokens: int | None = 262_144
    operation_id: str = "unspecified"
    include_reasoning: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.include_reasoning, bool):
            raise TypeError("include_reasoning must be a boolean")
        if self.max_tokens is not None:
            _require_non_negative_int(self.max_tokens, "max_tokens", positive=True)


def truncated_response_message(max_tokens: int | None) -> str:
    if max_tokens is None:
        return (
            "La réponse du modèle a été tronquée par la limite de contexte du "
            "fournisseur. Le brouillon partiel reste disponible."
        )
    formatted_budget = f"{max_tokens:,}".replace(",", " ")
    return (
        "La réponse du modèle a été tronquée : le budget de sortie de "
        f"{formatted_budget} tokens a été épuisé. Le raisonnement interne compte "
        "dans ce budget ; le brouillon partiel reste disponible."
    )


@dataclass(frozen=True, slots=True)
class CompletionResult:
    model_id: str
    content: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None
    call_id: str | None = None


class StreamEventKind(StrEnum):
    STATUS = "status"
    DELTA = "delta"
    REASONING = "reasoning"
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


class LlmCallApplicationOutcome(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


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
    max_tokens: int | None
    response_text: str
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    error_type: str | None
    error_message: str | None
    application_outcome: LlmCallApplicationOutcome | None = None
    application_error_type: str | None = None
    application_error_message: str | None = None

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
        if self.max_tokens is not None:
            _require_non_negative_int(self.max_tokens, "max_tokens", positive=True)
        _require_optional_text(self.finish_reason, "finish_reason")
        _require_optional_non_negative_int(self.prompt_tokens, "prompt_tokens")
        _require_optional_non_negative_int(
            self.completion_tokens,
            "completion_tokens",
        )
        _require_optional_text(self.error_type, "error_type")
        _require_optional_text(self.error_message, "error_message")
        if (
            self.application_outcome is not None
            and not isinstance(
                self.application_outcome,
                LlmCallApplicationOutcome,
            )
        ):
            raise TypeError(
                "application_outcome must be an LlmCallApplicationOutcome"
            )
        _require_optional_text(
            self.application_error_type,
            "application_error_type",
        )
        _require_optional_text(
            self.application_error_message,
            "application_error_message",
        )
        if self.application_outcome is not LlmCallApplicationOutcome.REJECTED and (
            self.application_error_type is not None
            or self.application_error_message is not None
        ):
            raise ValueError(
                "application errors require a rejected application outcome"
            )


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
class BriefPromptVariant:
    variant_id: str
    version: str
    display_name: str
    brief_system_prompt: str
    brief_user_prompt: str
    brief_revision_system_prompt: str
    brief_revision_user_prompt: str


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
    brief_variants: tuple[BriefPromptVariant, ...] = ()
    session_mode: PromptSessionMode = PromptSessionMode.ANALYZED

    def __post_init__(self) -> None:
        if not isinstance(self.session_mode, PromptSessionMode):
            raise TypeError("session_mode must be a PromptSessionMode")
        if not isinstance(self.brief_variants, tuple) or any(
            not isinstance(value, BriefPromptVariant)
            for value in self.brief_variants
        ):
            raise TypeError("brief_variants must contain BriefPromptVariant values")
        keys = [(value.variant_id, value.version) for value in self.brief_variants]
        if len(keys) != len(set(keys)):
            raise ValueError("brief variants must have unique IDs and versions")

    def brief_variant(self, variant_id: str, version: str) -> BriefPromptVariant:
        for variant in self.brief_variants:
            if variant.variant_id == variant_id and variant.version == version:
                return variant
        raise KeyError(
            f"unknown brief variant {variant_id}@{version} for "
            f"{self.profile_id}@{self.version}"
        )


@dataclass(frozen=True, slots=True)
class NewReference:
    asset_id: str
    role: str
    label: str
    uses: tuple[ReferenceUse, ...] = (ReferenceUse.SUBJECT,)
    evidence_policy: ReferenceEvidencePolicy = ReferenceEvidencePolicy.FULL


class MultimodalGateway(Protocol):
    def list_models(self) -> tuple[ModelDescriptor, ...]: ...

    def complete(self, request: CompletionRequest) -> CompletionResult: ...

    def stream(self, request: CompletionRequest) -> Iterator[CompletionStreamEvent]: ...


class LlmCallLogStore(Protocol):
    def append(self, record: LlmCallRecord) -> None: ...

    def list(self, limit: int = 20) -> tuple[LlmCallRecord, ...]: ...


class LlmCallApplicationOutcomeReporter(Protocol):
    def report_application_outcome(
        self,
        call_id: str,
        outcome: LlmCallApplicationOutcome,
        *,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None: ...


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
        brief_variant_id: str | None = None,
        brief_variant_version: str | None = None,
    ) -> PromptLabSession:
        profile = self.profiles.get(profile_id, profile_version)
        _validate_brief_variant(
            profile,
            brief_variant_id,
            brief_variant_version,
        )
        if profile.profile_id == "minimax.h3.i2v.direct":
            if len(references) != 1:
                raise ValueError("I2V Direct requires exactly one first-frame image")
            reference = references[0]
            if (
                reference.role != "first_frame"
                or ReferenceUse.FIRST_FRAME not in reference.uses
            ):
                raise ValueError(
                    "I2V Direct requires the image role and use first_frame"
                )
        if profile.profile_id in _H3_BASE_PROFILE_IDS:
            if len(references) > 2:
                raise ValueError("H3 Base accepts at most a first and a last frame")
            roles = [reference.role for reference in references]
            if any(role not in {"first_frame", "last_frame"} for role in roles):
                raise ValueError(
                    "H3 Base images must use first_frame or last_frame roles"
                )
            if len(roles) != len(set(roles)):
                raise ValueError("H3 Base accepts at most one frame for each role")
            for reference in references:
                required = direct_reference_required_use(reference.role)
                if required not in reference.uses:
                    raise ValueError(
                        f"H3 Base role {reference.role} requires use {required.value}"
                    )
        session = PromptLabSession(
            session_id=f"prompt-{uuid4().hex}",
            model_id=model_id,
            profile_id=profile_id,
            profile_version=profile_version,
            brief_variant_id=brief_variant_id,
            brief_variant_version=brief_variant_version,
            session_mode=profile.session_mode,
            references=tuple(
                PromptReference(
                    reference_id=f"ref-{uuid4().hex}",
                    asset_id=item.asset_id,
                    role=item.role,
                    label=item.label,
                    uses=item.uses,
                    evidence_policy=item.evidence_policy,
                )
                for item in references
            ),
        )
        return self.sessions.create(session)

    def fork_session(
        self,
        session_id: str,
        *,
        model_id: str | None = None,
        profile_id: str | None = None,
        profile_version: str | None = None,
        brief_variant_id: str | None = None,
        brief_variant_version: str | None = None,
        inherit_brief_variant: bool = True,
    ) -> PromptLabSession:
        """Create a clean session that reuses another session's image assets."""
        if (profile_id is None) != (profile_version is None):
            raise ValueError("fork profile id and version must be provided together")
        source = self.sessions.get(session_id)
        for reference in source.references:
            self.assets.get(reference.asset_id)
        return self.create_session(
            model_id=source.model_id if model_id is None else model_id,
            profile_id=source.profile_id if profile_id is None else profile_id,
            profile_version=(
                source.profile_version if profile_version is None else profile_version
            ),
            brief_variant_id=(
                source.brief_variant_id
                if inherit_brief_variant
                and brief_variant_id is None
                and brief_variant_version is None
                else brief_variant_id
            ),
            brief_variant_version=(
                source.brief_variant_version
                if inherit_brief_variant
                and brief_variant_id is None
                and brief_variant_version is None
                else brief_variant_version
            ),
            references=tuple(
                NewReference(
                    asset_id=reference.asset_id,
                    role=reference.role,
                    label=reference.label,
                    uses=reference.uses,
                    evidence_policy=reference.evidence_policy,
                )
                for reference in source.references
            ),
        )

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
        *,
        include_reasoning: bool = False,
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
            include_reasoning=include_reasoning,
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

    def configure_brief_variant(
        self,
        session_id: str,
        *,
        brief_variant_id: str | None,
        brief_variant_version: str | None,
    ) -> PromptLabSession:
        session = self.sessions.get(session_id)
        if session.brief_revisions:
            raise ValueError("brief variant is locked after the first Brief generation")
        profile = self._profile(session)
        _validate_brief_variant(
            profile,
            brief_variant_id,
            brief_variant_version,
        )
        return self.sessions.save(
            session.with_brief_variant(
                brief_variant_id,
                brief_variant_version,
            )
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
        *,
        include_reasoning: bool = False,
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
            include_reasoning=include_reasoning,
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
        *,
        include_reasoning: bool = False,
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
            include_reasoning=include_reasoning,
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
        *,
        include_reasoning: bool = False,
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
            include_reasoning=include_reasoning,
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
        creative_axes: CreativeFreedomAxes | None = None,
        *,
        creative_audacity: int = 0,
    ) -> PromptLabSession:
        session = self.sessions.get(session_id)
        profile = self._profile(session)
        system_prompt, user_prompt = _brief_prompts(profile, session)
        context, snapshots = _brief_inputs(session)
        freedom, axes = _creative_settings(creative_freedom, creative_axes)
        audacity = _creative_audacity(creative_audacity)
        result = self.gateway.complete(
            CompletionRequest(
                model_id=session.model_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt.format(
                    creative_freedom=freedom,
                    creative_policy=_creative_policy(freedom, axes),
                    creative_audacity=audacity,
                    creative_audacity_policy=creative_audacity_policy(audacity),
                    reference_context=context,
                    source_text=_required_text(source_text, "source_text"),
                    dialogue_ledger=explicit_dialogue_ledger(source_text),
                ),
                images=self._brief_images(session),
                operation_id=_brief_operation_id("brief.structure", session),
            )
        )
        return self._append_brief(
            session,
            source_text=source_text,
            content=_normalize_brief_document(_completed_content(result)),
            creative_freedom=freedom,
            creative_axes=axes,
            creative_audacity=audacity,
            references=snapshots,
            origin=RevisionOrigin.MODEL,
        )

    def stream_structure_brief(
        self,
        session_id: str,
        source_text: str,
        creative_freedom: int,
        *,
        creative_axes: CreativeFreedomAxes | None = None,
        creative_audacity: int = 0,
        include_reasoning: bool = False,
    ) -> Iterator[PromptLabStreamEvent]:
        session = self.sessions.get(session_id)
        profile = self._profile(session)
        system_prompt, user_prompt = _brief_prompts(profile, session)
        context, snapshots = _brief_inputs(session)
        freedom, axes = _creative_settings(creative_freedom, creative_axes)
        audacity = _creative_audacity(creative_audacity)
        request = CompletionRequest(
            model_id=session.model_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt.format(
                creative_freedom=freedom,
                creative_policy=_creative_policy(freedom, axes),
                creative_audacity=audacity,
                creative_audacity_policy=creative_audacity_policy(audacity),
                reference_context=context,
                source_text=_required_text(source_text, "source_text"),
                dialogue_ledger=explicit_dialogue_ledger(source_text),
            ),
            images=self._brief_images(session),
            operation_id=_brief_operation_id("brief.structure", session),
            include_reasoning=include_reasoning,
        )
        yield from self._stream_completion(
            request,
            lambda content: self._append_brief(
                session,
                source_text=source_text,
                content=_normalize_brief_document(content),
                creative_freedom=freedom,
                creative_axes=axes,
                creative_audacity=audacity,
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
            content=_normalize_brief_document(_required_text(content, "content")),
            creative_freedom=current.creative_freedom,
            creative_axes=current.creative_axes,
            creative_audacity=current.creative_audacity,
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
        system_prompt, user_prompt = _brief_revision_prompts(profile, session)
        context, snapshots = _brief_inputs(session)
        result = self.gateway.complete(
            CompletionRequest(
                model_id=session.model_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt.format(
                    creative_freedom=current.creative_freedom,
                    creative_policy=_creative_policy(
                        current.creative_freedom,
                        current.creative_axes,
                    ),
                    creative_audacity=current.creative_audacity,
                    creative_audacity_policy=creative_audacity_policy(
                        current.creative_audacity
                    ),
                    reference_context=context,
                    source_text=current.source_text,
                    dialogue_ledger=explicit_dialogue_ledger(current.source_text),
                    current_brief=current.content,
                    instruction=_required_text(instruction, "instruction"),
                ),
                images=self._brief_images(session),
                operation_id=_brief_operation_id("brief.revise", session),
            )
        )
        return self._append_brief(
            session,
            source_text=current.source_text,
            content=_normalize_brief_document(_completed_content(result)),
            creative_freedom=current.creative_freedom,
            creative_axes=current.creative_axes,
            creative_audacity=current.creative_audacity,
            references=snapshots,
            origin=RevisionOrigin.REWRITE,
            instruction=instruction,
        )

    def stream_revise_brief(
        self,
        session_id: str,
        instruction: str,
        *,
        include_reasoning: bool = False,
    ) -> Iterator[PromptLabStreamEvent]:
        session = self.sessions.get(session_id)
        current = _current_brief(session)
        profile = self._profile(session)
        system_prompt, user_prompt = _brief_revision_prompts(profile, session)
        context, snapshots = _brief_inputs(session)
        request = CompletionRequest(
            model_id=session.model_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt.format(
                creative_freedom=current.creative_freedom,
                creative_policy=_creative_policy(
                    current.creative_freedom,
                    current.creative_axes,
                ),
                creative_audacity=current.creative_audacity,
                creative_audacity_policy=creative_audacity_policy(
                    current.creative_audacity
                ),
                reference_context=context,
                source_text=current.source_text,
                dialogue_ledger=explicit_dialogue_ledger(current.source_text),
                current_brief=current.content,
                instruction=_required_text(instruction, "instruction"),
            ),
            images=self._brief_images(session),
            operation_id=_brief_operation_id("brief.revise", session),
            include_reasoning=include_reasoning,
        )
        yield from self._stream_completion(
            request,
            lambda content: self._append_brief(
                session,
                source_text=current.source_text,
                content=_normalize_brief_document(content),
                creative_freedom=current.creative_freedom,
                creative_axes=current.creative_axes,
                creative_audacity=current.creative_audacity,
                references=snapshots,
                origin=RevisionOrigin.REWRITE,
                instruction=instruction,
            ),
        )

    def approve_brief(self, session_id: str) -> PromptLabSession:
        session = self.sessions.get(session_id)
        return self.sessions.save(session.approve_brief())

    def create_super_fast_brief(
        self,
        session_id: str,
        source_text: str,
        creative_freedom: int,
        *,
        creative_axes: CreativeFreedomAxes | None = None,
        legacy_plan: bool = False,
    ) -> PromptLabSession:
        """Persist and approve a deterministic Brief capsule without an LLM call."""

        session = self.sessions.get(session_id)
        exact_source_text = _required_text(source_text, "source_text")
        intention = _inline_text(exact_source_text)
        freedom, axes = _creative_settings(creative_freedom, creative_axes)
        _, snapshots = _brief_inputs(session)
        reference_lines = []
        for picture_index, reference in enumerate(session.references, 1):
            reference_lines.append(
                f"<Picture {picture_index}>: name={_inline_text(reference.label)}; "
                f"role={reference.role}; uses="
                + ", ".join(use.value for use in reference.uses)
                + f"; evidence_policy={reference.evidence_policy.value}."
            )
        policy = creative_freedom_policy(freedom, axes)
        camera_instruction = (
            "Choose the minimum sufficient two-to-six-shot hard-cut sequence; "
            "keep typed camera motion optional and continuity-safe."
            if legacy_plan
            else "Choose the minimum sufficient two-to-six-shot hard-cut sequence "
            "directly in the final H3 prompt; keep camera motion optional and "
            "continuity-safe."
        )
        ambiguity_instruction = (
            "every material ambiguity explicitly in the Plan according to the "
            "creative-freedom policy."
            if legacy_plan
            else "every material ambiguity directly in the final prompt according "
            "to the creative-freedom policy."
        )
        content = "\n\n".join((
            "- INTENTION CENTRALE\n" + intention,
            "- RÉFÉRENCES CITÉES ET RÔLES\n" + "\n".join(reference_lines),
            (
                "- SUJETS ET IDENTITÉS À PRÉSERVER\n"
                "Preserve identities and stable appearance only through each "
                "reference's declared role, uses, and evidence policy."
            ),
            (
                "- DÉCOR ET ÉTAT INITIAL\n"
                "Derive visible initial state, environment, composition, and style "
                "only from the attached native images within their declared roles."
            ),
            "- CHRONOLOGIE ET ACTIONS DEMANDÉES\n" + intention,
            (
                "- CAMÉRA, LUMIÈRE ET MISE EN SCÈNE\n"
                + camera_instruction
            ),
            (
                "- CONTRAINTES STRICTES\n"
                "Respect every reference boundary, preserve physical and spatial "
                "continuity across cuts, and introduce no unsupported visual fact."
            ),
            f"- LIBERTÉS AUTORISÉES\nCreative freedom {freedom}/100. {policy}",
            (
                "- QUESTIONS OU AMBIGUÏTÉS\n"
                "No interactive recommendation step in Super rapide mode. Resolve "
                + ambiguity_instruction
            ),
        ))
        updated = self._append_brief(
            session,
            source_text=exact_source_text,
            content=_normalize_brief_document(content),
            creative_freedom=freedom,
            creative_axes=axes,
            references=snapshots,
            origin=RevisionOrigin.MANUAL,
        )
        return self.sessions.save(updated.approve_brief())

    def _profile(self, session: PromptLabSession) -> PromptProfile:
        return self.profiles.get(session.profile_id, session.profile_version)

    def _image(self, reference: PromptReference) -> ImageInput:
        asset = self.assets.get(reference.asset_id)
        return ImageInput(
            media_type=asset.media_type,
            content=self.assets.read_bytes(reference.asset_id),
            label=reference.label,
        )

    def _brief_images(self, session: PromptLabSession) -> tuple[ImageInput, ...]:
        if session.session_mode not in {
            PromptSessionMode.DIRECT_MULTIMODAL,
            PromptSessionMode.H3_BASE,
        }:
            return ()
        images: list[ImageInput] = []
        for index, reference in enumerate(session.references, 1):
            image = self._image(reference)
            images.append(
                ImageInput(
                    media_type=image.media_type,
                    content=image.content,
                    label=(
                        f"<Image {index}> · role={reference.role}"
                        if session.session_mode is PromptSessionMode.H3_BASE
                        else f"<Image {index}> · {reference.label}"
                    ),
                )
            )
        return tuple(images)

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
        creative_axes: CreativeFreedomAxes | None = None,
        creative_audacity: int = 0,
        references: tuple[BriefReferenceSnapshot, ...],
        origin: RevisionOrigin,
        instruction: str | None = None,
    ) -> PromptLabSession:
        if session.profile_id == _ANIMAL_INTERVIEW_PROFILE_ID:
            _validate_animal_interview_brief(source_text, content)
        revision = BriefRevision(
            revision_id=f"brief-{uuid4().hex}",
            source_text=source_text,
            content=content,
            creative_freedom=creative_freedom,
            creative_axes=creative_axes,
            creative_audacity=creative_audacity,
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


def _brief_prompts(
    profile: PromptProfile,
    session: PromptLabSession,
) -> tuple[str, str]:
    variant = _session_brief_variant(profile, session)
    if variant is not None:
        return variant.brief_system_prompt, variant.brief_user_prompt
    if profile.brief_system_prompt is None or profile.brief_user_prompt is None:
        raise ValueError("this prompt profile does not support structured briefs")
    return profile.brief_system_prompt, profile.brief_user_prompt


def _normalize_brief_document(content: str) -> str:
    """Canonicalize cosmetic heading bullets, then enforce the full Brief contract."""
    value = strip_markdown_fence(content).replace("\r\n", "\n")
    lines: list[str] = []
    for line in value.split("\n"):
        candidate = line.strip()
        if candidate.startswith("-"):
            candidate = candidate[1:].strip()
        lines.append(f"- {candidate}" if candidate in _BRIEF_HEADINGS else line)
    return _BRIEF_CONTRACT.extract("\n".join(lines))


def _validate_animal_interview_brief(source_text: str, content: str) -> None:
    """Keep supplied quotes verbatim and require a usable completed exchange."""

    source_dialogues = extract_explicit_dialogues(source_text)
    completed_dialogues = extract_explicit_dialogues(content)
    if len(completed_dialogues) < 2 or len(completed_dialogues) % 2:
        raise ValueError(
            "animal interview brief must contain complete question/answer pairs "
            "as quoted dialogue"
        )
    cursor = 0
    for exact_text in source_dialogues:
        try:
            cursor = completed_dialogues.index(exact_text, cursor) + 1
        except ValueError as error:
            raise ValueError(
                "animal interview brief must preserve every quoted source line "
                "verbatim and in order"
            ) from error


def _brief_revision_prompts(
    profile: PromptProfile,
    session: PromptLabSession,
) -> tuple[str, str]:
    variant = _session_brief_variant(profile, session)
    if variant is not None:
        return (
            variant.brief_revision_system_prompt,
            variant.brief_revision_user_prompt,
        )
    if (
        profile.brief_revision_system_prompt is None
        or profile.brief_revision_user_prompt is None
    ):
        raise ValueError("this prompt profile does not support brief revision")
    return profile.brief_revision_system_prompt, profile.brief_revision_user_prompt


def _validate_brief_variant(
    profile: PromptProfile,
    variant_id: str | None,
    version: str | None,
) -> None:
    if (variant_id is None) != (version is None):
        raise ValueError("brief variant id and version must be provided together")
    if variant_id is not None and version is not None:
        profile.brief_variant(variant_id, version)


def _session_brief_variant(
    profile: PromptProfile,
    session: PromptLabSession,
) -> BriefPromptVariant | None:
    if session.brief_variant_id is None:
        return None
    assert session.brief_variant_version is not None
    return profile.brief_variant(
        session.brief_variant_id,
        session.brief_variant_version,
    )


def _brief_operation_id(prefix: str, session: PromptLabSession) -> str:
    if session.brief_variant_id is None:
        return prefix
    return (
        f"{prefix}.{session.brief_variant_id}."
        f"{session.brief_variant_version}"
    )


def _brief_inputs(
    session: PromptLabSession,
) -> tuple[str, tuple[BriefReferenceSnapshot, ...]]:
    if (
        session.session_mode is PromptSessionMode.ANALYZED
        and not session.analysis_complete
    ):
        raise ValueError("approve every visual analysis before structuring the brief")
    context: list[str] = []
    snapshots: list[BriefReferenceSnapshot] = []
    for index, reference in enumerate(session.references, 1):
        analysis = reference.active_revision
        if (
            session.session_mode is PromptSessionMode.ANALYZED
            and (
                analysis is None
                or reference.approved_revision_id != analysis.revision_id
            )
        ):
            raise ValueError("approve every visual analysis before structuring the brief")
        snapshots.append(
            BriefReferenceSnapshot(
                reference_id=reference.reference_id,
                analysis_revision_id=(
                    analysis.revision_id
                    if session.session_mode is PromptSessionMode.ANALYZED
                    and analysis is not None
                    else None
                ),
                uses=reference.uses,
                evidence_policy=reference.evidence_policy,
            )
        )
        if session.session_mode in {
            PromptSessionMode.DIRECT_MULTIMODAL,
            PromptSessionMode.H3_BASE,
        }:
            identity_lines = [f"<Image {index}>"]
            if session.session_mode is not PromptSessionMode.H3_BASE:
                identity_lines.append(f"Name: {reference.label}")
            context.append(
                "\n".join(
                    (
                        *identity_lines,
                        f"User role: {reference.role}",
                        "Uses: " + ", ".join(
                            use.value for use in reference.uses
                        ),
                        f"Evidence policy: {reference.evidence_policy.value}",
                        "NATIVE IMAGE ATTACHED TO THIS REQUEST",
                    )
                )
            )
            continue
        if analysis is None:  # Guarded above; explicit for type narrowing.
            raise ValueError(
                "approve every visual analysis before structuring the brief"
            )
        context.append(
            "\n".join(
                (
                    f"<Image {index}>",
                    f"Nom : {reference.label}",
                    f"Rôle utilisateur : {reference.role}",
                    "Usages : " + ", ".join(use.value for use in reference.uses),
                    f"Politique de preuve : {reference.evidence_policy.value}",
                    "OBSERVATION APPROUVÉE",
                    project_reference_evidence(
                        analysis.content,
                        reference.evidence_policy,
                    ),
                )
            )
        )
    return "\n\n".join(context), tuple(snapshots)


_APPEARANCE_ONLY_V1_MARKERS = _OBSERVATION_CONTRACT.markers[2:4]


def project_reference_evidence(
    content: str,
    policy: ReferenceEvidencePolicy,
) -> str:
    """Apply a typed, deterministic evidence boundary to an observation."""

    if not isinstance(policy, ReferenceEvidencePolicy):
        raise TypeError("policy must be a ReferenceEvidencePolicy")
    if policy is ReferenceEvidencePolicy.FULL:
        return content

    value = strip_markdown_fence(content).replace("\r\n", "\n")
    headings: list[tuple[str, re.Match[str]]] = []
    for marker in _OBSERVATION_CONTRACT.markers:
        matches = list(re.finditer(rf"(?m)^{re.escape(marker)}\s*$", value))
        if len(matches) > 1:
            raise ValueError(
                f"appearance_only_v1 observation contains multiple sections: {marker}"
            )
        if matches:
            headings.append((marker, matches[0]))
    headings.sort(key=lambda item: item[1].start())
    by_marker = {marker: match for marker, match in headings}
    missing = [
        marker for marker in _APPEARANCE_ONLY_V1_MARKERS if marker not in by_marker
    ]
    if missing:
        raise ValueError(
            "appearance_only_v1 observation is missing required section: "
            + ", ".join(missing)
        )
    if [by_marker[marker].start() for marker in _APPEARANCE_ONLY_V1_MARKERS] != sorted(
        by_marker[marker].start() for marker in _APPEARANCE_ONLY_V1_MARKERS
    ):
        raise ValueError("appearance_only_v1 observation sections are out of order")
    selected: list[str] = []
    for marker in _APPEARANCE_ONLY_V1_MARKERS:
        match = by_marker[marker]
        end = next(
            (
                following.start()
                for _, following in headings
                if following.start() > match.start()
            ),
            len(value),
        )
        selected.append(value[match.start() : end].strip())
    return "\n\n".join(selected)


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


def _creative_audacity(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 3:
        raise ValueError("creative_audacity must be between 0 and 3")
    return value


def creative_audacity_policy(value: int) -> str:
    value = _creative_audacity(value)
    return (
        "Aucune initiative créative : complète seulement les transitions nécessaires et "
        "n'ajoute aucune idée-signature non demandée."
        if value == 0
        else "Initiative discrète : tu peux retenir un enrichissement thématique subtil, "
        "sans en faire un événement autonome."
        if value == 1
        else "Initiative affirmée : retiens exactement une idée-signature visuelle, "
        "mémorable, thématique et non nécessaire à la simple interpolation des frames."
        if value == 2
        else "Initiative audacieuse : retiens une idée-signature visuelle forte et tu peux "
        "l'accompagner d'au plus un effet de soutien cohérent ; ne multiplie pas les actions."
    )


def _creative_policy(
    value: int,
    axes: CreativeFreedomAxes | None = None,
) -> str:
    return creative_freedom_policy(value, axes)


def creative_axes_from_legacy(value: int) -> CreativeFreedomAxes:
    value = _creative_freedom(value)
    level = 0 if value <= 20 else 1 if value <= 45 else 2 if value <= 70 else 3
    return CreativeFreedomAxes(level, level, level)


def creative_freedom_from_axes(axes: CreativeFreedomAxes) -> int:
    if not isinstance(axes, CreativeFreedomAxes):
        raise TypeError("axes must be CreativeFreedomAxes")
    anchors = (0, 35, 65, 90)
    return round(
        sum(
            anchors[level]
            for level in (axes.scene_life, axes.camera, axes.extra_motion)
        )
        / 3
    )


def _creative_settings(
    value: int,
    axes: CreativeFreedomAxes | None,
) -> tuple[int, CreativeFreedomAxes]:
    if axes is None:
        freedom = _creative_freedom(value)
        return freedom, creative_axes_from_legacy(freedom)
    if not isinstance(axes, CreativeFreedomAxes):
        raise TypeError("creative_axes must be CreativeFreedomAxes or None")
    return creative_freedom_from_axes(axes), axes


def creative_freedom_policy(
    value: int,
    axes: CreativeFreedomAxes | None = None,
) -> str:
    value = _creative_freedom(value)
    resolved = axes or creative_axes_from_legacy(value)
    legacy_band = (
        "Factuel strict"
        if value <= 20
        else "Conservateur"
        if value <= 40
        else "Équilibré"
        if value <= 60
        else "Cinématographique"
        if value <= 80
        else "Exploratoire"
    )
    scene = (
        "n'ajoute aucune animation d'arrière-plan",
        "peut ajouter un micro-mouvement naturel d'arrière-plan si la scène paraît vide",
        "peut animer un ou deux éléments compatibles du décor",
        "peut enrichir plusieurs éléments compatibles du décor et de l'ambiance",
    )[resolved.scene_life]
    camera = (
        "n'ajoute aucun mouvement de caméra non demandé",
        "peut ajouter un mouvement de caméra subtil si le plan en bénéficie",
        "peut choisir un mouvement de caméra clairement perceptible et compatible",
        "peut composer plusieurs mouvements de caméra compatibles si le rythme le justifie",
    )[resolved.camera]
    motion = (
        "n'ajoute aucun mouvement de sujet ou d'objet non demandé",
        "peut ajouter un micro-mouvement secondaire naturel si l'action paraît figée",
        "peut ajouter un mouvement secondaire compatible au sujet ou à un objet",
        "peut ajouter plusieurs mouvements secondaires compatibles sans créer un nouvel événement narratif",
    )[resolved.extra_motion]
    return (
        f"{legacy_band}. Ces niveaux sont des autorisations, jamais des quotas : "
        "n'enrichis que les "
        "moments trop vides ou trop lents, sans contredire les frames, l'intention, "
        "les dialogues ni la continuité physique. "
        f"Vie de la scène {resolved.scene_life}/3 : {scene}. "
        f"Caméra {resolved.camera}/3 : {camera}. "
        f"Mouvements additionnels {resolved.extra_motion}/3 : {motion}."
    )


def _inline_text(value: str) -> str:
    return " ".join(value.split())


def _required_text(value: str, name: str) -> str:
    _require_non_empty_text(value, name)
    return value.strip()


def _completed_content(result: CompletionResult) -> str:
    if result.finish_reason == "length":
        raise ValueError(truncated_response_message(None))
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
