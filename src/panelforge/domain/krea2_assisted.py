"""Pure contracts for conversational KREA2 image creation projects."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
import re

from .krea2_batch import Krea2BatchSettings, Krea2PromptLanguage
from .krea2_style_presets import Krea2StylePreset, validate_preset_selection
from .assisted_composition import AssistedComposition
from .dlss import DlssResult, validate_dlss_attempt, validate_dlss_lineage


_SHA256 = re.compile(r"[0-9a-f]{64}")


class Krea2AssistedTurnMode(StrEnum):
    CREATION = "creation"
    RECIPE = "recipe"


class Krea2AssistedTurnRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class Krea2AssistedAttemptStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    SUBMITTING = "submitting"
    RUNNING = "running"
    CANCEL_PENDING = "cancel_pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Krea2AssistedTurn:
    turn_id: str
    mode: Krea2AssistedTurnMode
    role: Krea2AssistedTurnRole
    content: str
    guidance_asset_id: str | None = None
    guidance_filename: str | None = None
    questions: tuple[str, ...] = ()
    prompt: str | None = None
    recommendations: tuple[str, ...] = ()
    model_id: str | None = None
    assistance_recipe_version: str = "1.0.0"
    style_preset: Krea2StylePreset | None = None

    def __post_init__(self) -> None:
        validate_preset_selection(self.style_preset, False)
        _text(self.assistance_recipe_version, "assistance_recipe_version")
        _text(self.turn_id, "turn_id")
        if not isinstance(self.mode, Krea2AssistedTurnMode):
            raise TypeError("mode must be a Krea2AssistedTurnMode")
        if not isinstance(self.role, Krea2AssistedTurnRole):
            raise TypeError("role must be a Krea2AssistedTurnRole")
        _text(self.content, "turn content")
        if self.guidance_asset_id is not None:
            _text(self.guidance_asset_id, "guidance_asset_id")
        if self.guidance_filename is not None:
            _text(self.guidance_filename, "guidance_filename")
        if self.guidance_filename is not None and self.guidance_asset_id is None:
            raise ValueError("guidance_filename requires guidance_asset_id")
        if self.role is Krea2AssistedTurnRole.ASSISTANT and self.guidance_asset_id is not None:
            raise ValueError("only user turns can attach a guidance image")
        _strings(self.questions, "questions", maximum=3)
        _strings(self.recommendations, "recommendations", maximum=8)
        if self.prompt is not None:
            _text(self.prompt, "prompt")
        if self.model_id is not None:
            _text(self.model_id, "model_id")
        if self.role is Krea2AssistedTurnRole.USER and self.model_id is not None:
            raise ValueError("user turns cannot own a model ID")


@dataclass(frozen=True, slots=True)
class Krea2AssistedAttempt:
    attempt_id: str
    index: int
    prompt: str
    settings: Krea2BatchSettings
    seed: int
    status: Krea2AssistedAttemptStatus = Krea2AssistedAttemptStatus.CREATED
    execution_id: str | None = None
    compiled_workflow_sha256: str | None = None
    output_asset_id: str | None = None
    error: str | None = None
    accepted: bool = False
    # None means a legacy attempt with no recoverable conversation checkpoint.
    conversation_branch_id: str | None = None
    conversation_turn_id: str | None = None
    conversation_prompt_language: Krea2PromptLanguage = Krea2PromptLanguage.ENGLISH
    conversation_model_id: str | None = None
    style_preset: Krea2StylePreset | None = None
    preset_pending: bool = False
    queue_order: int | None = None
    kind: str = "generation"
    composition: AssistedComposition | None = None
    dlss: DlssResult | None = None

    def __post_init__(self) -> None:
        validate_preset_selection(self.style_preset, self.preset_pending)
        if self.queue_order is not None and (
            isinstance(self.queue_order, bool) or not isinstance(self.queue_order, int) or self.queue_order < 1
        ):
            raise ValueError("queue_order must be a positive integer")
        if self.conversation_branch_id is not None:
            _text(self.conversation_branch_id, "conversation_branch_id")
        if self.conversation_turn_id is not None:
            _text(self.conversation_turn_id, "conversation_turn_id")
            if self.conversation_branch_id is None:
                raise ValueError("conversation_turn_id requires a branch")
        if not isinstance(self.conversation_prompt_language, Krea2PromptLanguage):
            raise TypeError("conversation_prompt_language must be Krea2PromptLanguage")
        _text(self.attempt_id, "attempt_id")
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 1:
            raise ValueError("attempt index must be positive")
        _text(self.prompt, "prompt")
        if not isinstance(self.settings, Krea2BatchSettings):
            raise TypeError("settings must be Krea2BatchSettings")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or not 0 <= self.seed <= 2**50:
            raise ValueError("seed must be between 0 and 2^50")
        if not isinstance(self.status, Krea2AssistedAttemptStatus):
            raise TypeError("status must be Krea2AssistedAttemptStatus")
        if self.execution_id is not None:
            _text(self.execution_id, "execution_id")
        if self.compiled_workflow_sha256 is not None and _SHA256.fullmatch(self.compiled_workflow_sha256) is None:
            raise ValueError("compiled_workflow_sha256 must be a lowercase SHA-256")
        if self.output_asset_id is not None:
            _text(self.output_asset_id, "output_asset_id")
        if self.error is not None:
            _text(self.error, "error")
        if not isinstance(self.accepted, bool):
            raise TypeError("accepted must be a boolean")
        self._validate_state()

    def queue(self, order: int | None = None) -> Krea2AssistedAttempt:
        if self.status is not Krea2AssistedAttemptStatus.CREATED:
            raise ValueError("only a created attempt can be queued")
        return replace(self, status=Krea2AssistedAttemptStatus.QUEUED, queue_order=order)

    def submitting(self, digest: str) -> Krea2AssistedAttempt:
        if self.status is not Krea2AssistedAttemptStatus.QUEUED:
            raise ValueError("only a queued attempt can be submitted")
        return replace(self, status=Krea2AssistedAttemptStatus.SUBMITTING, compiled_workflow_sha256=_digest(digest))

    def start(self, execution_id: str, digest: str) -> Krea2AssistedAttempt:
        if self.status not in {Krea2AssistedAttemptStatus.QUEUED, Krea2AssistedAttemptStatus.SUBMITTING}:
            raise ValueError("only a queued attempt can start")
        return replace(
            self,
            status=Krea2AssistedAttemptStatus.RUNNING,
            execution_id=_text(execution_id, "execution_id"),
            compiled_workflow_sha256=_digest(digest),
        )

    def succeed(self, asset_id: str) -> Krea2AssistedAttempt:
        if self.status not in {
            Krea2AssistedAttemptStatus.RUNNING,
            Krea2AssistedAttemptStatus.CANCEL_PENDING,
        }:
            raise ValueError("only an active attempt can succeed")
        return replace(
            self,
            status=Krea2AssistedAttemptStatus.SUCCEEDED,
            output_asset_id=_text(asset_id, "asset_id"),
            error=None,
        )

    def fail(self, error: str) -> Krea2AssistedAttempt:
        if self.status not in {
            Krea2AssistedAttemptStatus.CREATED,
            Krea2AssistedAttemptStatus.QUEUED,
            Krea2AssistedAttemptStatus.SUBMITTING,
            Krea2AssistedAttemptStatus.RUNNING,
            Krea2AssistedAttemptStatus.CANCEL_PENDING,
        }:
            raise ValueError("only a non-terminal attempt can fail")
        return replace(
            self,
            status=Krea2AssistedAttemptStatus.FAILED,
            output_asset_id=None,
            error=_text(error, "error"),
        )

    def cancel_pending(self, error: str | None = None) -> Krea2AssistedAttempt:
        if self.status not in {
            Krea2AssistedAttemptStatus.QUEUED,
            Krea2AssistedAttemptStatus.RUNNING,
            Krea2AssistedAttemptStatus.CANCEL_PENDING,
        }:
            raise ValueError("only a queued or running attempt can await cancellation")
        return replace(
            self,
            status=Krea2AssistedAttemptStatus.CANCEL_PENDING,
            error=error.strip() if isinstance(error, str) and error.strip() else None,
        )

    def cancel(self) -> Krea2AssistedAttempt:
        if self.status not in {
            Krea2AssistedAttemptStatus.CREATED,
            Krea2AssistedAttemptStatus.QUEUED,
            Krea2AssistedAttemptStatus.SUBMITTING,
            Krea2AssistedAttemptStatus.RUNNING,
            Krea2AssistedAttemptStatus.CANCEL_PENDING,
        }:
            return self
        return replace(
            self,
            status=Krea2AssistedAttemptStatus.CANCELLED,
            output_asset_id=None,
            error=None,
        )

    def accept(self) -> Krea2AssistedAttempt:
        if self.status is not Krea2AssistedAttemptStatus.SUCCEEDED:
            raise ValueError("only a succeeded attempt can be accepted")
        return replace(self, accepted=True)

    def _validate_state(self) -> None:
        if self.dlss is not None:
            validate_dlss_attempt(self)
            if self.kind != "dlss" or self.composition is not None:
                raise ValueError("invalid DLSS image provenance")
            return
        if self.kind == "composition":
            if (not isinstance(self.composition, AssistedComposition)
                    or self.status is not Krea2AssistedAttemptStatus.SUCCEEDED
                    or self.output_asset_id is None
                    or any(v is not None for v in (self.execution_id, self.compiled_workflow_sha256, self.queue_order, self.error))):
                raise ValueError("a local composition must be succeeded without execution fields")
            return
        if self.kind != "generation" or self.composition is not None:
            raise ValueError("invalid assisted attempt kind")
        if self.status is Krea2AssistedAttemptStatus.CREATED:
            if any((self.execution_id, self.compiled_workflow_sha256, self.output_asset_id, self.error)):
                raise ValueError("created attempt contains execution fields")
        elif self.status is Krea2AssistedAttemptStatus.QUEUED:
            if any((self.execution_id, self.compiled_workflow_sha256, self.output_asset_id, self.error)):
                raise ValueError("queued attempt contains execution fields")
        elif self.status is Krea2AssistedAttemptStatus.SUBMITTING:
            if self.execution_id is not None or self.output_asset_id is not None or self.compiled_workflow_sha256 is None:
                raise ValueError("submitting attempt requires only a compiled workflow")
        elif self.status in {Krea2AssistedAttemptStatus.RUNNING, Krea2AssistedAttemptStatus.CANCEL_PENDING}:
            if self.execution_id is None or self.compiled_workflow_sha256 is None:
                raise ValueError("active attempt requires execution fields")
            if self.output_asset_id is not None:
                raise ValueError("active attempt cannot contain output")
        elif self.status is Krea2AssistedAttemptStatus.SUCCEEDED:
            if self.execution_id is None or self.compiled_workflow_sha256 is None or self.output_asset_id is None or self.error is not None:
                raise ValueError("succeeded attempt is incomplete")
        elif self.status is Krea2AssistedAttemptStatus.FAILED:
            if self.output_asset_id is not None or self.error is None:
                raise ValueError("failed attempt requires only an error")
        elif self.output_asset_id is not None or self.error is not None:
            raise ValueError("cancelled attempt cannot contain output or error")
        if self.accepted and self.status is not Krea2AssistedAttemptStatus.SUCCEEDED:
            raise ValueError("only a succeeded attempt can be accepted")


@dataclass(frozen=True, slots=True)
class Krea2AssistedRecipeDraft:
    recipe_id: str
    display_name: str
    description: str
    identity: str
    invariants: tuple[str, ...]
    variables: tuple[str, ...]
    risks: tuple[str, ...]
    canonical_prompt: str
    prompt_language: Krea2PromptLanguage = Krea2PromptLanguage.ENGLISH

    def __post_init__(self) -> None:
        for value, label in (
            (self.recipe_id, "recipe_id"),
            (self.display_name, "display_name"),
            (self.description, "description"),
            (self.identity, "identity"),
            (self.canonical_prompt, "canonical_prompt"),
        ):
            _text(value, label)
        if re.fullmatch(r"[a-z0-9][a-z0-9_]{1,63}", self.recipe_id) is None:
            raise ValueError("recipe_id must use lowercase letters, digits and underscores")
        _strings(self.invariants, "invariants", minimum=1, maximum=24)
        _strings(self.variables, "variables", minimum=1, maximum=24)
        _strings(self.risks, "risks", minimum=1, maximum=24)
        if not isinstance(self.prompt_language, Krea2PromptLanguage):
            raise TypeError("prompt_language must be a Krea2PromptLanguage")


@dataclass(frozen=True, slots=True)
class Krea2AssistedBranch:
    """A saved conversation path. Turns shared by two paths retain their IDs."""

    branch_id: str
    name: str
    parent_branch_id: str | None = None
    source_attempt_id: str | None = None
    turns: tuple[Krea2AssistedTurn, ...] = ()
    current_prompt: str | None = None
    prompt_language: Krea2PromptLanguage = Krea2PromptLanguage.ENGLISH
    revision_model_id: str | None = None
    feedback_attempt_id: str | None = None
    recipe_draft: Krea2AssistedRecipeDraft | None = None
    render_settings: Krea2BatchSettings | None = None
    render_seed: int | None = None
    style_preset: Krea2StylePreset | None = None
    preset_pending: bool = False

    def __post_init__(self) -> None:
        validate_preset_selection(self.style_preset, self.preset_pending)
        _text(self.branch_id, "branch_id")
        _text(self.name, "branch name")
        if not isinstance(self.turns, tuple) or any(not isinstance(t, Krea2AssistedTurn) for t in self.turns):
            raise TypeError("branch turns must contain Krea2AssistedTurn values")
        if len({t.turn_id for t in self.turns}) != len(self.turns):
            raise ValueError("branch turn IDs must be unique")
        if not isinstance(self.prompt_language, Krea2PromptLanguage):
            raise TypeError("branch prompt_language must be Krea2PromptLanguage")
        if self.render_settings is not None and not isinstance(self.render_settings, Krea2BatchSettings):
            raise TypeError("branch render_settings must be Krea2BatchSettings")
        if self.render_seed is not None and (
            isinstance(self.render_seed, bool) or not isinstance(self.render_seed, int)
            or not 0 <= self.render_seed <= 2**50
        ):
            raise ValueError("branch render_seed is invalid")


@dataclass(frozen=True, slots=True)
class Krea2AssistedProject:
    project_id: str
    name: str
    intention: str
    model_id: str
    prompt_language: Krea2PromptLanguage = Krea2PromptLanguage.ENGLISH
    revision_model_id: str | None = None
    reference_asset_id: str | None = None
    reference_filename: str | None = None
    turns: tuple[Krea2AssistedTurn, ...] = ()
    current_prompt: str | None = None
    attempts: tuple[Krea2AssistedAttempt, ...] = ()
    feedback_attempt_id: str | None = None
    accepted_attempt_id: str | None = None
    recipe_draft: Krea2AssistedRecipeDraft | None = None
    published_recipe_id: str | None = None
    published_recipe_version: str | None = None
    export_path: str | None = None
    export_error: str | None = None
    warnings: tuple[str, ...] = ()
    assistance_recipe_version: str = "1.0.0"
    active_branch_id: str = "main"
    branches: tuple[Krea2AssistedBranch, ...] = field(
        default_factory=lambda: (
            Krea2AssistedBranch(branch_id="main", name="Exploration initiale"),
        ),
    )
    render_settings: Krea2BatchSettings | None = None
    render_seed: int | None = None
    style_preset: Krea2StylePreset | None = None
    preset_pending: bool = False
    composition_base_asset_id: str | None = None

    def __post_init__(self) -> None:
        validate_preset_selection(self.style_preset, self.preset_pending)
        _text(self.assistance_recipe_version, "assistance_recipe_version")
        for value, label in (
            (self.project_id, "project_id"),
            (self.name, "name"),
            (self.intention, "intention"),
            (self.model_id, "model_id"),
        ):
            _text(value, label)
        if self.reference_asset_id is not None:
            _text(self.reference_asset_id, "reference_asset_id")
        if self.composition_base_asset_id is not None:
            _text(self.composition_base_asset_id, "composition_base_asset_id")
        if self.revision_model_id is not None:
            _text(self.revision_model_id, "revision_model_id")
        if not isinstance(self.prompt_language, Krea2PromptLanguage):
            raise TypeError("prompt_language must be a Krea2PromptLanguage")
        if self.reference_filename is not None:
            _text(self.reference_filename, "reference_filename")
        if not isinstance(self.turns, tuple) or any(not isinstance(value, Krea2AssistedTurn) for value in self.turns):
            raise TypeError("turns must contain Krea2AssistedTurn values")
        if not isinstance(self.attempts, tuple) or any(not isinstance(value, Krea2AssistedAttempt) for value in self.attempts):
            raise TypeError("attempts must contain Krea2AssistedAttempt values")
        if len({value.turn_id for value in self.turns}) != len(self.turns):
            raise ValueError("turn IDs must be unique")
        if len({value.attempt_id for value in self.attempts}) != len(self.attempts):
            raise ValueError("attempt IDs must be unique")
        previous: dict[str, Krea2AssistedAttempt] = {}
        validate_dlss_lineage(self.attempts)
        requests: set[str] = set()
        for attempt in self.attempts:
            c = attempt.composition
            if c:
                original, parent = previous.get(c.original_attempt_id), previous.get(c.parent_attempt_id)
                if (original is None or original.kind != "generation" or parent is None
                        or original.status is not Krea2AssistedAttemptStatus.SUCCEEDED
                        or parent.status is not Krea2AssistedAttemptStatus.SUCCEEDED
                        or c.generated_asset_id != original.output_asset_id
                        or attempt.settings != original.settings or attempt.seed != original.seed
                        or attempt.prompt != original.prompt or attempt.index != original.index
                        or (parent.composition.original_attempt_id if parent.composition else parent.attempt_id) != original.attempt_id):
                    raise ValueError("invalid composition image lineage")
                if c.request_id in requests:
                    raise ValueError("composition request IDs must be unique")
                requests.add(c.request_id)
            previous[attempt.attempt_id] = attempt
        if self.current_prompt is not None:
            _text(self.current_prompt, "current_prompt")
        attempt_ids = {value.attempt_id for value in self.attempts}
        if self.feedback_attempt_id is not None and self.feedback_attempt_id not in attempt_ids:
            raise ValueError("feedback_attempt_id does not exist")
        if self.accepted_attempt_id is not None and self.accepted_attempt_id not in attempt_ids:
            raise ValueError("accepted_attempt_id does not exist")
        if (self.published_recipe_id is None) != (self.published_recipe_version is None):
            raise ValueError("published recipe identity is incomplete")
        if self.export_error is not None:
            _text(self.export_error, "export_error")
        _strings(self.warnings, "warnings", maximum=64)
        if not isinstance(self.branches, tuple) or any(not isinstance(b, Krea2AssistedBranch) for b in self.branches):
            raise TypeError("branches must contain Krea2AssistedBranch values")
        known_branches: set[str] = set()
        known_turns: dict[str, Krea2AssistedTurn] = {}
        for branch in self.branches:
            if branch.branch_id in known_branches:
                raise ValueError("branch IDs must be unique")
            if branch.parent_branch_id is not None and branch.parent_branch_id not in known_branches:
                raise ValueError("a branch parent must precede its child")
            known_branches.add(branch.branch_id)
            if branch.source_attempt_id is not None and branch.source_attempt_id not in attempt_ids:
                raise ValueError("branch source attempt does not exist")
            if branch.feedback_attempt_id is not None and branch.feedback_attempt_id not in attempt_ids:
                raise ValueError("branch feedback attempt does not exist")
            for turn in branch.turns:
                if turn.turn_id in known_turns and known_turns[turn.turn_id] != turn:
                    raise ValueError("shared conversation turns must be immutable")
                known_turns[turn.turn_id] = turn
        if self.active_branch_id not in known_branches:
            raise ValueError("active branch does not exist")
        for turn in self.turns:
            if turn.turn_id in known_turns and known_turns[turn.turn_id] != turn:
                raise ValueError("shared conversation turns must be immutable")
        # Validate current render state with the same contract as saved branches.
        object.__setattr__(self, "branches", self.conversation_branches())

    @property
    def initial_reference_pending(self) -> bool:
        """Send the source until the project's first accepted assistant reply.

        Failed/cancelled calls leave only user turns and can retry with the
        source. Branch navigation must not silently attach it again, including
        a restart with an empty conversation from an old image.
        """
        return self.reference_asset_id is not None and not any(
            turn.role is Krea2AssistedTurnRole.ASSISTANT
            for branch in self.branches
            for turn in branch.turns
        )

    def conversation_branches(self) -> tuple[Krea2AssistedBranch, ...]:
        """Overlay the live state; inactive paths never receive later exchanges."""
        return tuple(
            replace(branch, turns=self.turns, current_prompt=self.current_prompt,
                    prompt_language=self.prompt_language, revision_model_id=self.revision_model_id,
                    feedback_attempt_id=self.feedback_attempt_id, recipe_draft=self.recipe_draft,
                    render_settings=self.render_settings, render_seed=self.render_seed,
                    style_preset=self.style_preset, preset_pending=self.preset_pending)
            if branch.branch_id == self.active_branch_id else branch
            for branch in self.branches
        )

    def switch_branch(self, branch_id: str) -> Krea2AssistedProject:
        branches = self.conversation_branches()
        branch = next((b for b in branches if b.branch_id == branch_id), None)
        if branch is None:
            raise KeyError(branch_id)
        return replace(
            self, branches=branches, active_branch_id=branch.branch_id, turns=branch.turns,
            current_prompt=branch.current_prompt, prompt_language=branch.prompt_language,
            revision_model_id=branch.revision_model_id, feedback_attempt_id=branch.feedback_attempt_id,
            recipe_draft=branch.recipe_draft, render_settings=branch.render_settings,
            render_seed=branch.render_seed,
            style_preset=branch.style_preset, preset_pending=branch.preset_pending,
        )

    def branch_from_attempt(
        self, attempt_id: str, branch_id: str, *, image_prompt_only: bool = False,
    ) -> Krea2AssistedProject:
        attempt = self.attempt(attempt_id)
        if attempt.status is not Krea2AssistedAttemptStatus.SUCCEEDED:
            raise ValueError("a conversation branch requires a succeeded image")
        if attempt.conversation_branch_id is None and not image_prompt_only:
            raise ValueError("Cet ancien essai ne possède pas de point de conversation. Utilisez la reprise image + prompt.")
        branches = self.conversation_branches()
        turns: tuple[Krea2AssistedTurn, ...] = ()
        parent_id = attempt.conversation_branch_id or "main"
        if not image_prompt_only:
            source = next((b for b in branches if b.branch_id == parent_id), None)
            if source is None:
                raise ValueError("conversation checkpoint branch does not exist")
            if attempt.conversation_turn_id is not None:
                index = next((i for i, t in enumerate(source.turns) if t.turn_id == attempt.conversation_turn_id), None)
                if index is None:
                    raise ValueError("conversation checkpoint turn does not exist")
                turns = source.turns[:index + 1]
        branch = Krea2AssistedBranch(
            branch_id=branch_id, name=f"Piste {len(branches)} · {self.attempt_label(attempt_id)}",
            parent_branch_id=parent_id, source_attempt_id=attempt_id, turns=turns,
            current_prompt=attempt.prompt, prompt_language=attempt.conversation_prompt_language,
            revision_model_id=attempt.conversation_model_id or self.model_id,
            feedback_attempt_id=attempt_id, render_settings=attempt.settings, render_seed=attempt.seed,
            style_preset=attempt.style_preset, preset_pending=attempt.preset_pending,
        )
        return replace(self, branches=(*branches, branch)).switch_branch(branch_id)

    def add_turns(
        self,
        user: Krea2AssistedTurn,
        assistant: Krea2AssistedTurn,
    ) -> Krea2AssistedProject:
        if user.role is not Krea2AssistedTurnRole.USER or assistant.role is not Krea2AssistedTurnRole.ASSISTANT:
            raise ValueError("a conversation exchange requires user then assistant")
        if user.mode is not assistant.mode:
            raise ValueError("conversation exchange modes differ")
        return replace(
            self,
            turns=(*self.turns, user, assistant),
            current_prompt=(assistant.prompt or self.current_prompt),
            revision_model_id=(assistant.model_id or self.revision_model_id),
        )

    def select_revision_model(self, model_id: str) -> Krea2AssistedProject:
        return replace(
            self,
            revision_model_id=_text(model_id, "revision_model_id"),
        )

    def add_attempt(self, attempt: Krea2AssistedAttempt) -> Krea2AssistedProject:
        if any(value.attempt_id == attempt.attempt_id for value in self.attempts):
            raise ValueError("attempt already exists")
        return replace(self, attempts=(*self.attempts, attempt))

    def replace_attempt(self, attempt: Krea2AssistedAttempt) -> Krea2AssistedProject:
        if sum(value.attempt_id == attempt.attempt_id for value in self.attempts) != 1:
            raise KeyError(attempt.attempt_id)
        return replace(
            self,
            attempts=tuple(attempt if value.attempt_id == attempt.attempt_id else value for value in self.attempts),
        )

    def use_feedback(self, attempt_id: str | None) -> Krea2AssistedProject:
        if attempt_id is None:
            return replace(self, feedback_attempt_id=None)
        attempt = self.attempt(attempt_id)
        if attempt.status is not Krea2AssistedAttemptStatus.SUCCEEDED:
            raise ValueError("feedback must reference a succeeded attempt")
        return replace(self, feedback_attempt_id=attempt_id)

    def accept_attempt(self, attempt_id: str) -> Krea2AssistedProject:
        attempt = self.attempt(attempt_id).accept()
        return replace(
            self.replace_attempt(attempt),
            accepted_attempt_id=attempt_id,
            current_prompt=attempt.prompt,
            feedback_attempt_id=attempt_id,
            attempts=tuple(
                replace(value, accepted=(value.attempt_id == attempt_id))
                for value in self.replace_attempt(attempt).attempts
            ),
        )

    def with_recipe_draft(self, draft: Krea2AssistedRecipeDraft) -> Krea2AssistedProject:
        return replace(self, recipe_draft=draft)

    def with_prompt_language(self, language: Krea2PromptLanguage) -> Krea2AssistedProject:
        if not isinstance(language, Krea2PromptLanguage):
            raise TypeError("language must be a Krea2PromptLanguage")
        return replace(self, prompt_language=language)

    def with_published_recipe(self, recipe_id: str, version: str) -> Krea2AssistedProject:
        return replace(
            self,
            published_recipe_id=_text(recipe_id, "recipe_id"),
            published_recipe_version=_text(version, "version"),
        )

    def with_export(self, path: str | None, error: str | None) -> Krea2AssistedProject:
        return replace(self, export_path=path, export_error=error)

    def attempt(self, attempt_id: str) -> Krea2AssistedAttempt:
        for value in self.attempts:
            if value.attempt_id == attempt_id:
                return value
        raise KeyError(attempt_id)

    def composition_number(self, attempt_id: str) -> int:
        attempt = self.attempt(attempt_id)
        if attempt.composition is None:
            return 0
        siblings = [a.attempt_id for a in self.attempts if a.composition
                    and a.composition.original_attempt_id == attempt.composition.original_attempt_id]
        return siblings.index(attempt_id) + 1

    def attempt_label(self, attempt_id: str) -> str:
        attempt = self.attempt(attempt_id)
        suffix = f" — Composition {self.composition_number(attempt_id)}" if attempt.composition else ""
        if attempt.dlss:
            siblings = [a.attempt_id for a in self.attempts if a.dlss and a.dlss.root_attempt_id == attempt.dlss.root_attempt_id]
            suffix = f" — DLSS {siblings.index(attempt_id) + 1}"
        return f"Essai {attempt.index}{suffix}"


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    return value.strip()


def _strings(
    values: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int,
) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{label} must be a tuple")
    if not minimum <= len(values) <= maximum:
        raise ValueError(f"{label} must contain between {minimum} and {maximum} values")
    for value in values:
        _text(value, label)
    return values


def _digest(value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError("digest must be a lowercase SHA-256")
    return value
