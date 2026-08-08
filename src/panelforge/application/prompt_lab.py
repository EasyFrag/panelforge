"""Supervised prompt-reference analysis use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from panelforge.domain import (
    AnalysisRevision,
    PromptLabSession,
    PromptReference,
    RevisionOrigin,
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
    max_tokens: int = 1400


@dataclass(frozen=True, slots=True)
class CompletionResult:
    model_id: str
    content: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


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


@dataclass(frozen=True, slots=True)
class NewReference:
    asset_id: str
    role: str
    label: str


class MultimodalGateway(Protocol):
    def list_models(self) -> tuple[ModelDescriptor, ...]: ...

    def complete(self, request: CompletionRequest) -> CompletionResult: ...


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
                ),
                images=(self._image(reference),),
            )
        )
        return self._append_revision(
            session,
            reference,
            content=result.content,
            origin=RevisionOrigin.MODEL,
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
            )
        )
        return self._append_revision(
            session,
            reference,
            content=result.content,
            origin=RevisionOrigin.REWRITE,
            instruction=instruction,
        )

    def approve_reference(
        self,
        session_id: str,
        reference_id: str,
    ) -> PromptLabSession:
        session = self.sessions.get(session_id)
        updated = session.update_reference(session.reference(reference_id).approve())
        return self.sessions.save(updated)

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
