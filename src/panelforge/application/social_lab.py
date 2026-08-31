"""Conversational Instagram copy generation from four video keyframes."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
import json
from threading import RLock
from typing import Protocol
from uuid import uuid4

from panelforge.domain.assets import Asset
from panelforge.domain.social_lab import (
    SocialChannelProfile,
    SocialLanguage,
    SocialProject,
    SocialTurn,
    SocialTurnRole,
    SocialVariant,
)

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
from .revised_documents import strip_markdown_fence


_SYSTEM_PROMPT = """You are an expert Instagram editor creating publication-ready copy from four chronological video keyframes and an editorial brief.

Return raw JSON only with exactly this shape:
{"message":"short helpful reply in French","variants":[{"angle":"short editorial angle","hook":"short title or Reel hook","caption":"complete Instagram caption","hashtags":["#tag"],"emojis":["emoji"]}]}

Hard rules:
- Return exactly VARIANT COUNT genuinely distinct variants.
- Write hook, caption, angle and hashtags in TARGET LANGUAGE. The short message may remain in French.
- Each variant must use a different editorial angle, not minor synonym changes.
- Use the supplied mood, vibe, channel example and instructions as guidance, not text to quote mechanically.
- The example defines channel voice; never copy a full sentence unless explicitly requested.
- Keep claims grounded in visible keyframes and SOURCE PROMPT CONTEXT. Never claim to hear dialogue, music, narration or sound unless the source context explicitly states it.
- Provide useful, specific hashtags without stuffing or duplicates. Every hashtag starts with # and contains no spaces.
- Provide one to four context-appropriate emojis. Avoid repeating the same emoji set across every variant.
- Do not include Markdown, code fences, explanations outside JSON, placeholder text or invented handles.
- During refinements, preserve the full conversation and follow the newest user message while returning a complete replacement set of variants."""


class SocialLabAssets(Protocol):
    def get(self, asset_id: str) -> Asset: ...
    def read_bytes(self, asset_id: str) -> bytes: ...


class SocialLabStore(Protocol):
    def create_project(self, project: SocialProject) -> SocialProject: ...
    def save_project(self, project: SocialProject) -> SocialProject: ...
    def get_project(self, project_id: str) -> SocialProject: ...
    def list_projects(self, limit: int = 30) -> list[SocialProject]: ...
    def save_profile(self, profile: SocialChannelProfile) -> SocialChannelProfile: ...
    def get_profile(self, profile_id: str) -> SocialChannelProfile: ...
    def list_profiles(self, limit: int = 100) -> list[SocialChannelProfile]: ...


@dataclass(frozen=True, slots=True)
class SocialLabStreamEvent:
    kind: StreamEventKind
    phase: StreamPhase
    text: str = ""
    progress: float | None = None
    project: SocialProject | None = None
    error: str | None = None


class SocialLabService:
    def __init__(
        self,
        *,
        gateway: MultimodalGateway,
        assets: SocialLabAssets,
        projects: SocialLabStore,
        application_outcomes: LlmCallApplicationOutcomeReporter | None = None,
        source_prompt_resolver: Callable[[Asset], str | None] | None = None,
        project_id_factory: Callable[[], str] | None = None,
        profile_id_factory: Callable[[], str] | None = None,
        turn_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.gateway = gateway
        self.assets = assets
        self.projects = projects
        self.application_outcomes = application_outcomes
        self.source_prompt_resolver = source_prompt_resolver
        self._project_id_factory = project_id_factory or (
            lambda: f"social-{uuid4().hex}"
        )
        self._profile_id_factory = profile_id_factory or (
            lambda: f"channel-{uuid4().hex}"
        )
        self._turn_id_factory = turn_id_factory or (
            lambda: f"turn-{uuid4().hex}"
        )
        self._lock = RLock()

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return self.gateway.list_models()

    def list_projects(self, limit: int = 30) -> list[SocialProject]:
        return self.projects.list_projects(limit)

    def get_project(self, project_id: str) -> SocialProject:
        return self.projects.get_project(project_id)

    def list_profiles(self, limit: int = 100) -> list[SocialChannelProfile]:
        return self.projects.list_profiles(limit)

    def get_profile(self, profile_id: str) -> SocialChannelProfile:
        return self.projects.get_profile(profile_id)

    def save_profile(
        self,
        *,
        profile_id: str | None,
        name: str,
        language: SocialLanguage,
        mood: str = "",
        vibe: str = "",
        example: str = "",
        instructions: str = "",
    ) -> SocialChannelProfile:
        return self.projects.save_profile(SocialChannelProfile(
            profile_id=(
                _bounded_text(profile_id, "profile_id", 128)
                if profile_id is not None
                else self._profile_id_factory()
            ),
            name=_bounded_text(name, "profile name", 120),
            language=language,
            mood=_optional_text(mood, "profile mood", 4_000),
            vibe=_optional_text(vibe, "profile vibe", 4_000),
            example=_optional_text(example, "profile example", 12_000),
            instructions=_optional_text(
                instructions,
                "profile instructions",
                8_000,
            ),
        ))

    def create_project(
        self,
        *,
        name: str,
        model_id: str,
        language: SocialLanguage,
        variant_count: int,
        video_asset_id: str,
        video_filename: str,
        keyframe_asset_ids: tuple[str, ...],
        mood: str = "",
        vibe: str = "",
        example: str = "",
        instructions: str = "",
        channel_profile_id: str | None = None,
    ) -> SocialProject:
        video = self.assets.get(video_asset_id)
        if video.media_type not in {"video/mp4", "video/webm"}:
            raise ValueError("Social Lab requires an MP4 or WebM video")
        if len(keyframe_asset_ids) != 4:
            raise ValueError("Social Lab requires exactly four keyframes")
        for asset_id in keyframe_asset_ids:
            asset = self.assets.get(asset_id)
            if not asset.media_type.startswith("image/"):
                raise ValueError("Social Lab keyframes must be images")
        source_prompt = None
        if self.source_prompt_resolver is not None:
            value = self.source_prompt_resolver(video)
            if isinstance(value, str) and value.strip():
                source_prompt = value.strip()[:50_000]
        return self.projects.create_project(SocialProject(
            project_id=self._project_id_factory(),
            name=_bounded_text(name, "project name", 120),
            model_id=_bounded_text(model_id, "model_id", 300),
            language=language,
            variant_count=variant_count,
            video_asset_id=video.asset_id,
            video_filename=_bounded_text(video_filename, "video filename", 240),
            keyframe_asset_ids=keyframe_asset_ids,
            mood=_optional_text(mood, "mood", 4_000),
            vibe=_optional_text(vibe, "vibe", 4_000),
            example=_optional_text(example, "example", 12_000),
            instructions=_optional_text(instructions, "instructions", 8_000),
            channel_profile_id=channel_profile_id,
            source_prompt=source_prompt,
        ))

    def stream_chat(
        self,
        project_id: str,
        message: str,
        *,
        model_id: str | None = None,
        language: SocialLanguage | None = None,
        variant_count: int | None = None,
        mood: str | None = None,
        vibe: str | None = None,
        example: str | None = None,
        instructions: str | None = None,
        channel_profile_id: str | None = None,
        update_profile: bool = False,
        include_reasoning: bool = False,
    ) -> Iterator[SocialLabStreamEvent]:
        message = _bounded_text(message, "message", 12_000)
        with self._lock:
            project = self.projects.get_project(project_id).with_editorial(
                model_id=(
                    _bounded_text(model_id, "model_id", 300)
                    if model_id is not None
                    else None
                ),
                language=language,
                variant_count=variant_count,
                mood=(
                    _optional_text(mood, "mood", 4_000)
                    if mood is not None
                    else None
                ),
                vibe=(
                    _optional_text(vibe, "vibe", 4_000)
                    if vibe is not None
                    else None
                ),
                example=(
                    _optional_text(example, "example", 12_000)
                    if example is not None
                    else None
                ),
                instructions=(
                    _optional_text(instructions, "instructions", 8_000)
                    if instructions is not None
                    else None
                ),
                channel_profile_id=channel_profile_id,
                update_profile=update_profile,
            )
            user_turn = SocialTurn(
                turn_id=self._turn_id_factory(),
                role=SocialTurnRole.USER,
                content=message,
            )
            project = self.projects.save_project(project.add_turn(user_turn))

        request = self._completion_request(project, include_reasoning)
        parts: list[str] = []
        try:
            for event in self.gateway.stream(request):
                if event.kind is StreamEventKind.DELTA:
                    parts.append(event.text)
                if event.kind is StreamEventKind.TRUNCATED:
                    error = ValueError(truncated_response_message(request.max_tokens))
                    self._report(
                        event.result.call_id if event.result else None,
                        LlmCallApplicationOutcome.REJECTED,
                        error,
                    )
                    yield SocialLabStreamEvent(
                        StreamEventKind.TRUNCATED,
                        StreamPhase.TRUNCATED,
                        event.result.content if event.result else "".join(parts),
                        project=self.projects.get_project(project_id),
                        error=str(error),
                    )
                    return
                if event.kind is StreamEventKind.COMPLETED:
                    if event.result is None:
                        raise ValueError("model stream completed without a result")
                    try:
                        terminal = self._accept_response(
                            project_id,
                            event.result.content,
                        )
                    except Exception as error:
                        self._report(
                            event.result.call_id,
                            LlmCallApplicationOutcome.REJECTED,
                            error,
                        )
                        yield SocialLabStreamEvent(
                            StreamEventKind.COMPLETED,
                            StreamPhase.COMPLETED,
                            event.result.content,
                            1.0,
                            self.projects.get_project(project_id),
                            _error(error),
                        )
                    else:
                        self._report(
                            event.result.call_id,
                            LlmCallApplicationOutcome.ACCEPTED,
                        )
                        yield SocialLabStreamEvent(
                            StreamEventKind.COMPLETED,
                            StreamPhase.COMPLETED,
                            event.result.content,
                            1.0,
                            terminal,
                        )
                    return
                yield SocialLabStreamEvent(
                    event.kind,
                    event.phase,
                    event.text,
                    event.progress,
                )
        except GeneratorExit:
            raise
        except Exception as error:
            yield SocialLabStreamEvent(
                StreamEventKind.COMPLETED,
                StreamPhase.COMPLETED,
                "".join(parts),
                1.0,
                self.projects.get_project(project_id),
                _error(error),
            )

    def _completion_request(
        self,
        project: SocialProject,
        include_reasoning: bool,
    ) -> CompletionRequest:
        images: list[ImageInput] = []
        positions = ("10%", "35%", "65%", "90%")
        for index, asset_id in enumerate(project.keyframe_asset_ids):
            asset = self.assets.get(asset_id)
            images.append(ImageInput(
                media_type=asset.media_type,
                content=self.assets.read_bytes(asset_id),
                label=f"VIDEO KEYFRAME {index + 1} · {positions[index]}",
            ))
        language = (
            "English"
            if project.language is SocialLanguage.ENGLISH
            else "French"
        )
        source_prompt = project.source_prompt or (
            "Unavailable. Infer only visible content from the four keyframes; "
            "do not infer audio."
        )
        conversation = "\n\n".join(
            _turn_context(turn, index)
            for index, turn in enumerate(project.turns, start=1)
        )
        user_prompt = f"""TARGET LANGUAGE: {language}
VARIANT COUNT: {project.variant_count}
VIDEO FILE: {project.video_filename}

EDITORIAL BRIEF
Mood:
{project.mood or "Not specified."}

Vibe:
{project.vibe or "Not specified."}

Representative channel example:
{project.example or "Not supplied."}

Additional instructions:
{project.instructions or "None."}

SOURCE PROMPT CONTEXT
{source_prompt}

FULL CONVERSATION
{conversation}

Return exactly {project.variant_count} complete variants now."""
        operation = (
            "social.instagram.refine@0.1.0"
            if any(turn.role is SocialTurnRole.ASSISTANT for turn in project.turns)
            else "social.instagram.generate@0.1.0"
        )
        return CompletionRequest(
            model_id=project.model_id,
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            images=tuple(images),
            temperature=0.75,
            max_tokens=64_000,
            operation_id=operation,
            include_reasoning=include_reasoning,
        )

    def _accept_response(self, project_id: str, raw: str) -> SocialProject:
        with self._lock:
            project = self.projects.get_project(project_id)
            message, variants = parse_social_response(
                raw,
                expected_count=project.variant_count,
            )
            turn = SocialTurn(
                turn_id=self._turn_id_factory(),
                role=SocialTurnRole.ASSISTANT,
                content=message,
                variants=variants,
            )
            return self.projects.save_project(project.add_turn(turn))

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
            error_type=type(error).__name__ if error is not None else None,
            error_message=str(error) if error is not None else None,
        )


def parse_social_response(
    raw: str,
    *,
    expected_count: int,
) -> tuple[str, tuple[SocialVariant, ...]]:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Social Lab response is empty")
    text = strip_markdown_fence(raw.strip())
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        repaired = _close_unterminated_json_containers(text)
        if repaired == text:
            raise ValueError("Social Lab response is not valid JSON") from error
        try:
            value = json.loads(repaired)
        except json.JSONDecodeError:
            raise ValueError("Social Lab response is not valid JSON") from error
    if not isinstance(value, dict):
        raise ValueError("Social Lab response must be an object")
    variants_raw = value.get("variants")
    if not isinstance(variants_raw, list) or len(variants_raw) != expected_count:
        raise ValueError(
            f"Social Lab response must contain exactly {expected_count} variants"
        )
    variants: list[SocialVariant] = []
    for index, item in enumerate(variants_raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Social Lab variant {index} must be an object")
        hashtags = _string_values(item.get("hashtags", ()), hashtags=True)
        emojis = _string_values(item.get("emojis", ()))
        variants.append(SocialVariant(
            angle=_payload_text(item.get("angle"), f"variant {index} angle", 120),
            hook=_payload_text(
                item.get("hook", item.get("title")),
                f"variant {index} hook",
                300,
            ),
            caption=_payload_text(
                item.get("caption"),
                f"variant {index} caption",
                5_000,
            ),
            hashtags=hashtags,
            emojis=emojis,
        ))
    message = value.get("message")
    if not isinstance(message, str) or not message.strip():
        message = "Voici les propositions éditoriales."
    return message.strip()[:20_000], tuple(variants)


def _close_unterminated_json_containers(value: str) -> str:
    """Close only unambiguous arrays or objects left open at end of output."""

    expected_closers: list[str] = []
    in_string = False
    escaped = False
    for character in value:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            expected_closers.append("}")
        elif character == "[":
            expected_closers.append("]")
        elif character in "}]":
            if not expected_closers or expected_closers[-1] != character:
                return value
            expected_closers.pop()
    if in_string or not expected_closers:
        return value
    return value.rstrip() + "".join(reversed(expected_closers))


def _turn_context(turn: SocialTurn, index: int) -> str:
    header = f"TURN {index} · {turn.role.value.upper()}\n{turn.content}"
    if not turn.variants:
        return header
    variants = "\n".join(
        f"VARIANT {variant_index}:\n"
        f"ANGLE: {variant.angle}\n"
        f"HOOK: {variant.hook}\n"
        f"CAPTION: {variant.caption}\n"
        f"HASHTAGS: {' '.join(variant.hashtags)}\n"
        f"EMOJIS: {' '.join(variant.emojis)}"
        for variant_index, variant in enumerate(turn.variants, start=1)
    )
    return f"{header}\n{variants}"


def _string_values(value: object, *, hashtags: bool = False) -> tuple[str, ...]:
    if isinstance(value, str):
        values = value.split()
    elif isinstance(value, list):
        values = value
    else:
        raise ValueError("hashtags and emojis must be arrays or strings")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, str) or not item.strip():
            continue
        text = item.strip()
        if hashtags:
            text = "#" + text.lstrip("#")
            if any(character.isspace() for character in text):
                continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text[:300])
    return tuple(normalized)


def _payload_text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return value.strip()


def _bounded_text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    text = value.strip()
    if len(text) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return text


def _optional_text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return value.strip()


def _error(error: Exception) -> str:
    message = str(error).strip()
    return message or type(error).__name__


__all__ = [
    "SocialLabService",
    "SocialLabStreamEvent",
    "parse_social_response",
]
