"""One-call prompt variation followed by sequential KREA2 batch rendering."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
import hashlib
import json
import logging
import secrets
from threading import RLock
import time
from typing import Any, Protocol
import urllib.error
from uuid import uuid4

from panelforge.domain.assets import Asset
from panelforge.domain.krea2_batch import (
    KREA2_BATCH_RGTHREE_MAX_SEED,
    Krea2Batch,
    Krea2BatchItem,
    Krea2BatchItemStatus,
    Krea2BatchSettings,
    Krea2BatchStatus,
    Krea2LoraSelection,
    Krea2PromptLanguage,
    Krea2ReviewDecision,
)
from panelforge.domain.krea2_lab import Krea2AspectRatio, normalize_krea2_model_name
from panelforge.infrastructure.krea2_batch_recipes import Krea2VisualRecipe

from .prompt_lab import (
    CompletionRequest,
    CompletionResult,
    CompletionStreamEvent,
    LlmCallApplicationOutcome,
    LlmCallApplicationOutcomeReporter,
    ModelDescriptor,
    MultimodalGateway,
    StreamEventKind,
    StreamPhase,
)


_LOGGER = logging.getLogger(__name__)
_MISSING_HISTORY_OUTPUT = "ComfyUI history does not contain the expected PNG"


class Krea2BatchRecipeCatalog(Protocol):
    def current(self) -> tuple[Krea2VisualRecipe, ...]: ...
    def list(self) -> tuple[Krea2VisualRecipe, ...]: ...
    def get(self, recipe_id: str, version: str) -> Krea2VisualRecipe: ...
    def create_technical_revision(self, base: Krea2VisualRecipe, settings: Krea2BatchSettings) -> Krea2VisualRecipe: ...
    def parse_revision_draft(self, base: Krea2VisualRecipe, raw: str) -> Krea2VisualRecipe: ...
    def publish(self, proposal: Krea2VisualRecipe) -> Krea2VisualRecipe: ...


class Krea2BatchStore(Protocol):
    def create(self, batch: Krea2Batch) -> Krea2Batch: ...
    def save(self, batch: Krea2Batch) -> Krea2Batch: ...
    def get(self, batch_id: str) -> Krea2Batch: ...
    def list(self, limit: int = 20) -> list[Krea2Batch]: ...
    def recent_signatures(self, recipe_id: str, *, limit: int = 40) -> tuple[str, ...]: ...
    def save_compiled_workflow(self, batch_id: str, item_id: str, workflow: dict[str, Any]) -> str: ...


class Krea2BatchComfy(Protocol):
    def submit_workflow(self, workflow: Mapping[str, Any]) -> str: ...
    def get_history(self, prompt_id: str) -> dict[str, Any]: ...
    def download_output(self, *, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes: ...
    def cancel_execution(self, prompt_id: str) -> object | None: ...


class Krea2BatchAssets(Protocol):
    def create(self, content: bytes, *, media_type: str, source_run_id: str | None = None) -> Asset: ...


class Krea2BatchWorkflow(Protocol):
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


class Krea2BatchResources(Protocol):
    def list_models(self) -> tuple[object, ...]: ...
    def list_loras(self) -> tuple[object, ...]: ...


@dataclass(frozen=True, slots=True)
class Krea2BatchRequest:
    recipe_id: str
    recipe_version: str
    image_count: int
    model_id: str
    direction: str = ""
    settings: Krea2BatchSettings | None = None


@dataclass(frozen=True, slots=True)
class Krea2BatchStreamEvent:
    kind: StreamEventKind
    phase: StreamPhase
    text: str = ""
    progress: float | None = None
    batch: Krea2Batch | None = None


class Krea2BatchService:
    def __init__(
        self,
        *,
        gateway: MultimodalGateway,
        recipes: Krea2BatchRecipeCatalog,
        workflow: Krea2BatchWorkflow,
        comfy: Krea2BatchComfy,
        assets: Krea2BatchAssets,
        batches: Krea2BatchStore,
        resources: Krea2BatchResources,
        application_outcomes: LlmCallApplicationOutcomeReporter | None = None,
        run_timeout: float = 3600,
        poll_interval: float = 1,
        batch_id_factory: Callable[[], str] | None = None,
        seed_factory: Callable[[], int] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.gateway = gateway
        self.recipes = recipes
        self.workflow = workflow
        self.comfy = comfy
        self.assets = assets
        self.batches = batches
        self.resources = resources
        self.application_outcomes = application_outcomes
        self.run_timeout = run_timeout
        self.poll_interval = poll_interval
        self._batch_id_factory = batch_id_factory or (lambda: f"krea2-batch-{uuid4().hex}")
        self._seed_factory = seed_factory or (
            lambda: secrets.randbelow(KREA2_BATCH_RGTHREE_MAX_SEED + 1)
        )
        self._monotonic = monotonic
        self._sleep = sleep
        self._lock = RLock()
        self._claimed: set[str] = set()

    def list_models(self) -> tuple[ModelDescriptor, ...]:
        return self.gateway.list_models()

    def prepare(self, request: Krea2BatchRequest) -> Krea2Batch:
        if not isinstance(request, Krea2BatchRequest):
            raise TypeError("request must be a Krea2BatchRequest")
        if not 1 <= request.image_count <= 10:
            raise ValueError("image_count must be between 1 and 10")
        recipe = self.recipes.get(request.recipe_id, request.recipe_version)
        settings = request.settings or recipe.settings
        if settings != recipe.settings:
            recipe = self.recipes.create_technical_revision(recipe, settings)
        warnings = self._resource_warnings(settings)
        return self.batches.create(Krea2Batch.create(
            batch_id=self._batch_id_factory(),
            recipe_id=recipe.recipe_id,
            recipe_version=recipe.version,
            recipe_sha256=recipe.content_sha256,
            model_id=request.model_id,
            image_count=request.image_count,
            direction=request.direction,
            settings=settings,
            warnings=warnings,
        ))

    def stream_generate_prompts(
        self,
        batch_id: str,
        *,
        include_reasoning: bool = False,
    ) -> Iterator[Krea2BatchStreamEvent]:
        with self._lock:
            batch = self.batches.get(batch_id)
            recipe = self._recipe(batch)
            batch = self.batches.save(batch.start_prompt_generation())
        recent = self.batches.recent_signatures(recipe.recipe_id, limit=40)
        system, user = recipe.build_generation_prompts(
            image_count=batch.image_count,
            direction=batch.direction,
            recent_signatures=recent,
        )
        request = CompletionRequest(
            model_id=batch.model_id,
            system_prompt=system,
            user_prompt=user,
            temperature=0.55,
            max_tokens=32768,
            operation_id=f"krea2.batch.prompts.{recipe.recipe_id}@{recipe.version}",
            include_reasoning=include_reasoning,
        )
        parts: list[str] = []
        try:
            for event in self.gateway.stream(request):
                if event.kind is StreamEventKind.DELTA:
                    parts.append(event.text)
                if event.kind is StreamEventKind.COMPLETED:
                    if event.result is None:
                        raise ValueError("model stream completed without a result")
                    terminal = self._accept_prompts(batch, recipe, event.result)
                    yield Krea2BatchStreamEvent(
                        kind=StreamEventKind.COMPLETED,
                        phase=StreamPhase.COMPLETED,
                        text=terminal.raw_prompt_response or "",
                        progress=1,
                        batch=terminal,
                    )
                    return
                if event.kind is StreamEventKind.TRUNCATED:
                    raw = event.result.content if event.result is not None else "".join(parts)
                    error = RuntimeError("The model response was truncated.")
                    failed = self.batches.save(batch.fail(str(error), raw_response=raw))
                    self._report(event.result.call_id if event.result else None, LlmCallApplicationOutcome.REJECTED, error)
                    yield Krea2BatchStreamEvent(StreamEventKind.TRUNCATED, StreamPhase.TRUNCATED, text=raw, batch=failed)
                    return
                yield Krea2BatchStreamEvent(event.kind, event.phase, text=event.text, progress=event.progress)
        except Exception as error:
            failed = self.batches.save(batch.fail(_error(error), raw_response="".join(parts)))
            yield Krea2BatchStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED, text="".join(parts), progress=1, batch=failed)

    def start_rendering(self, batch_id: str) -> Krea2Batch:
        with self._lock:
            batch = self.batches.get(batch_id)
            if not self._model_available(batch.settings.model_name):
                raise ValueError("Le modèle de la recette n’est pas disponible dans le catalogue KREA2.")
            if any(
                candidate.status in {Krea2BatchStatus.RENDERING, Krea2BatchStatus.CANCEL_PENDING}
                for candidate in self.batches.list(10_000)
            ):
                raise ValueError("another KREA2 batch is already rendering")
            return self.batches.save(batch.start_rendering())

    def render(self, batch_id: str) -> Krea2Batch:
        with self._lock:
            batch = self.batches.get(batch_id)
            if batch.status is Krea2BatchStatus.CANCELLED:
                return batch
            if batch.status is not Krea2BatchStatus.RENDERING:
                raise ValueError("batch is not ready to render")
            if batch_id in self._claimed:
                raise ValueError("batch is already rendering")
            self._claimed.add(batch_id)
        try:
            available_loras = {
                normalize_krea2_model_name(getattr(resource, "comfy_name", ""))
                for resource in self.resources.list_loras()
            }
            render_settings = replace(
                batch.settings,
                loras=tuple(
                    lora
                    for lora in batch.settings.loras
                    if normalize_krea2_model_name(lora.name) in available_loras
                ),
            )
            for item in batch.items:
                current = self.batches.get(batch_id)
                if current.status in {Krea2BatchStatus.CANCELLED, Krea2BatchStatus.CANCEL_PENDING}:
                    return current
                current_item = next(candidate for candidate in current.items if candidate.item_id == item.item_id)
                if current_item.status is not Krea2BatchItemStatus.PENDING:
                    continue
                try:
                    current = self._render_item(current, current_item, render_settings)
                except Exception as error:
                    current = self.batches.get(batch_id)
                    current_item = next(candidate for candidate in current.items if candidate.item_id == item.item_id)
                    if current_item.status in {Krea2BatchItemStatus.PENDING, Krea2BatchItemStatus.RUNNING}:
                        current = current.replace_item(current_item.fail(_error(error)))
                        self.batches.save(current)
            current = self.batches.get(batch_id)
            if current.status is Krea2BatchStatus.RENDERING:
                current = self.batches.save(current.complete())
            return current
        finally:
            with self._lock:
                self._claimed.discard(batch_id)

    def cancel(self, batch_id: str) -> Krea2Batch:
        with self._lock:
            batch = self.batches.get(batch_id)
            running = next((item for item in batch.items if item.status is Krea2BatchItemStatus.RUNNING), None)
            if running is not None and running.execution_id is not None:
                try:
                    result = self.comfy.cancel_execution(running.execution_id)
                except Exception as error:
                    return self.batches.save(replace(batch, status=Krea2BatchStatus.CANCEL_PENDING, error=_error(error)))
                action = getattr(getattr(result, "action", None), "value", getattr(result, "action", None))
                if action == "already_finished":
                    try:
                        history = self.comfy.get_history(running.execution_id)
                        output = _extract_output(
                            history,
                            running.execution_id,
                            self.workflow.output_node_id,
                            self.workflow.output_history_field,
                        )
                        content = self.comfy.download_output(
                            filename=output["filename"],
                            subfolder=output.get("subfolder", ""),
                            folder_type=output.get("type", "output"),
                        )
                        _validate_png(content)
                        asset = self.assets.create(
                            content,
                            media_type=self.workflow.output_media_type,
                            source_run_id=batch.batch_id,
                        )
                        batch = batch.replace_item(running.succeed(asset.asset_id))
                    except Exception as error:
                        return self.batches.save(replace(
                            batch,
                            status=Krea2BatchStatus.CANCEL_PENDING,
                            error=f"Annulation déjà terminée, sortie à réconcilier : {_error(error)}",
                        ))
            return self.batches.save(batch.cancel())

    def review_item(
        self,
        batch_id: str,
        item_id: str,
        decision: Krea2ReviewDecision,
        comment: str = "",
    ) -> Krea2Batch:
        with self._lock:
            batch = self.batches.get(batch_id)
            item = next((value for value in batch.items if value.item_id == item_id), None)
            if item is None:
                raise KeyError(item_id)
            return self.batches.save(batch.replace_item(item.review_as(decision, comment)))

    def propose_recipe_revision(
        self,
        batch_id: str,
        instruction: str,
        *,
        draft: str | None = None,
        settings: Krea2BatchSettings | None = None,
        model_id: str | None = None,
        prompt_language: Krea2PromptLanguage | None = None,
    ) -> Krea2Batch:
        root = self._workshop_root(batch_id)
        if root.status is not Krea2BatchStatus.COMPLETED:
            raise ValueError("recipe workshop requires a completed source batch")
        instruction = _required_text(instruction, "revision instruction")
        base = self._recipe(root)
        workshop = self._load_workshop(root)
        _require_active_workshop(workshop)
        current = self._candidate_recipe(
            base,
            draft or root.recipe_revision_draft,
            settings,
            prompt_language,
        )
        reviews = self._workshop_reviews(root, workshop)
        conversation = tuple(
            {"role": str(turn.get("role", "user")), "message": str(turn.get("message", ""))}
            for turn in workshop["turns"]
            if isinstance(turn, dict) and turn.get("message")
        )
        system, user = current.build_revision_prompts(
            feedback=instruction,
            reviews=reviews,
            conversation=conversation,
        )
        selected_model = (model_id or workshop.get("model_id") or root.model_id).strip()
        result = self.gateway.complete(CompletionRequest(
            model_id=selected_model,
            system_prompt=system,
            user_prompt=user,
            temperature=0.2,
            max_tokens=16384,
            operation_id=f"krea2.batch.recipe_workshop.{base.recipe_id}@{base.version}",
        ))
        try:
            reply, raw_recipe = _decode_revision_response(result.content)
            proposal = self.recipes.parse_revision_draft(current, raw_recipe)
            proposal = replace(proposal, settings=current.settings)
            candidate = _recipe_draft_json(proposal, base_version=base.version)
            workshop["model_id"] = selected_model
            workshop["turns"].extend((
                {"role": "user", "message": instruction},
                {"role": "assistant", "message": reply},
            ))
            self._append_workshop_draft(workshop, candidate, source="model")
            updated = root.with_recipe_workshop(
                json.dumps(workshop, ensure_ascii=False, indent=2),
                candidate,
            )
        except Exception as error:
            self._report(result.call_id, LlmCallApplicationOutcome.REJECTED, error)
            raise
        self._report(result.call_id, LlmCallApplicationOutcome.ACCEPTED)
        return self.batches.save(updated)

    def save_recipe_revision_draft(
        self,
        batch_id: str,
        draft: str,
        *,
        settings: Krea2BatchSettings | None = None,
        prompt_language: Krea2PromptLanguage | None = None,
    ) -> Krea2Batch:
        root = self._workshop_root(batch_id)
        if root.status is not Krea2BatchStatus.COMPLETED:
            raise ValueError("recipe workshop requires a completed source batch")
        base = self._recipe(root)
        proposal = self._candidate_recipe(base, draft, settings, prompt_language)
        candidate = _recipe_draft_json(proposal, base_version=base.version)
        workshop = self._load_workshop(root)
        _require_active_workshop(workshop)
        self._append_workshop_draft(workshop, candidate, source="manual")
        return self.batches.save(root.with_recipe_workshop(
            json.dumps(workshop, ensure_ascii=False, indent=2),
            candidate,
        ))

    def prepare_recipe_revision_test(
        self,
        batch_id: str,
        *,
        image_count: int,
        direction: str,
        model_id: str,
        draft: str | None = None,
        settings: Krea2BatchSettings | None = None,
        prompt_language: Krea2PromptLanguage | None = None,
    ) -> tuple[Krea2Batch, Krea2Batch]:
        if not 1 <= image_count <= 10:
            raise ValueError("image_count must be between 1 and 10")
        root = self._workshop_root(batch_id)
        if root.status is not Krea2BatchStatus.COMPLETED:
            raise ValueError("recipe workshop requires a completed source batch")
        base = self._recipe(root)
        workshop = self._load_workshop(root)
        _require_active_workshop(workshop)
        proposal = self._candidate_recipe(
            base,
            draft or root.recipe_revision_draft,
            settings,
            prompt_language,
        )
        candidate = _recipe_draft_json(proposal, base_version=base.version)
        digest = _draft_digest(candidate)
        test = replace(
            Krea2Batch.create(
                batch_id=self._batch_id_factory(),
                recipe_id=proposal.recipe_id,
                recipe_version=proposal.version,
                recipe_sha256=digest,
                model_id=_required_text(model_id, "model_id"),
                image_count=image_count,
                direction=direction,
                settings=proposal.settings,
                warnings=self._resource_warnings(proposal.settings),
            ),
            workshop_source_batch_id=root.batch_id,
            recipe_snapshot=candidate,
        )
        test = self.batches.create(test)
        self._append_workshop_draft(workshop, candidate, source="test")
        if test.batch_id not in workshop["test_batch_ids"]:
            workshop["test_batch_ids"].append(test.batch_id)
        root = self.batches.save(root.with_recipe_workshop(
            json.dumps(workshop, ensure_ascii=False, indent=2),
            candidate,
        ))
        return test, root

    def accept_recipe_revision(
        self,
        batch_id: str,
        *,
        draft: str | None = None,
        settings: Krea2BatchSettings | None = None,
        prompt_language: Krea2PromptLanguage | None = None,
    ) -> Krea2VisualRecipe:
        root = self._workshop_root(batch_id)
        if draft is None and root.recipe_revision_draft is None:
            raise ValueError("batch has no recipe revision proposal")
        base = self._recipe(root)
        workshop = self._load_workshop(root)
        _require_active_workshop(workshop)
        proposal = self._candidate_recipe(
            base,
            draft or root.recipe_revision_draft,
            settings,
            prompt_language,
        )
        published = self.recipes.publish(proposal)
        candidate = _recipe_draft_json(proposal, base_version=base.version)
        workshop["status"] = "published"
        workshop["published_version"] = published.version
        self._append_workshop_draft(workshop, candidate, source="published")
        self.batches.save(root.with_recipe_workshop(
            json.dumps(workshop, ensure_ascii=False, indent=2),
            candidate,
        ))
        return published

    def get(self, batch_id: str) -> Krea2Batch:
        with self._lock:
            return self._recover_missing_outputs(self.batches.get(batch_id))

    def list(self, limit: int = 20) -> list[Krea2Batch]:
        with self._lock:
            return [self._recover_missing_outputs(batch) for batch in self.batches.list(limit)]

    def _accept_prompts(self, batch: Krea2Batch, recipe: Krea2VisualRecipe, result: CompletionResult) -> Krea2Batch:
        try:
            prompts = recipe.parse_prompts(result.content, batch.image_count)
            items = tuple(
                Krea2BatchItem(
                    item_id=f"image-{index:02d}",
                    index=index,
                    prompt=prompt,
                    variation_signature=signature,
                    seed=self._seed_factory(),
                )
                for index, (signature, prompt) in enumerate(prompts, start=1)
            )
            terminal = batch.prompts_ready(raw_response=result.content, items=items)
        except Exception as error:
            self._report(result.call_id, LlmCallApplicationOutcome.REJECTED, error)
            return self.batches.save(batch.fail(_error(error), raw_response=result.content))
        self._report(result.call_id, LlmCallApplicationOutcome.ACCEPTED)
        return self.batches.save(terminal)

    def _render_item(
        self,
        batch: Krea2Batch,
        item: Krea2BatchItem,
        settings: Krea2BatchSettings,
    ) -> Krea2Batch:
        output_prefix = f"image/krea2-batch/{batch.batch_id}/{item.item_id}"
        workflow = self.workflow.build(
            prompt=item.prompt,
            settings=settings,
            seed=item.seed,
            output_prefix=output_prefix,
            sidecar_text=_sidecar_text(
                batch,
                item,
                settings,
                output_prefix=output_prefix,
                workflow_reference=self.workflow.reference,
            ),
        )
        digest = self.batches.save_compiled_workflow(batch.batch_id, item.item_id, workflow)
        with self._lock:
            current = self.batches.get(batch.batch_id)
            if current.status is not Krea2BatchStatus.RENDERING:
                raise RuntimeError("batch cancelled before ComfyUI submission")
            current_item = next(value for value in current.items if value.item_id == item.item_id)
            if current_item.status is not Krea2BatchItemStatus.PENDING:
                raise RuntimeError("batch item changed before ComfyUI submission")
            execution_id = self.comfy.submit_workflow(workflow)
            item = current_item.start(execution_id, digest)
            batch = self.batches.save(current.replace_item(item))
        history = self._wait_history(batch.batch_id, execution_id)
        output = _extract_output(history, execution_id, self.workflow.output_node_id, self.workflow.output_history_field)
        content = self.comfy.download_output(filename=output["filename"], subfolder=output.get("subfolder", ""), folder_type=output.get("type", "output"))
        _validate_png(content)
        asset = self.assets.create(content, media_type=self.workflow.output_media_type, source_run_id=batch.batch_id)
        current = self.batches.get(batch.batch_id)
        current_item = next(value for value in current.items if value.item_id == item.item_id)
        return self.batches.save(current.replace_item(current_item.succeed(asset.asset_id)))

    def _wait_history(self, batch_id: str, execution_id: str) -> dict[str, Any]:
        deadline = self._monotonic() + self.run_timeout
        while True:
            batch = self.batches.get(batch_id)
            if batch.status in {Krea2BatchStatus.CANCELLED, Krea2BatchStatus.CANCEL_PENDING}:
                raise RuntimeError("batch cancelled")
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
                raise TimeoutError("ComfyUI batch item timed out")
            self._sleep(min(self.poll_interval, remaining))

    def _recipe(self, batch: Krea2Batch) -> Krea2VisualRecipe:
        if batch.recipe_snapshot is not None:
            value = json.loads(batch.recipe_snapshot)
            base = self.recipes.get(value["recipe_id"], value["base_version"])
            recipe = self._candidate_recipe(base, batch.recipe_snapshot, None)
            recipe = replace(recipe, content_sha256=_draft_digest(batch.recipe_snapshot))
            if recipe.content_sha256 != batch.recipe_sha256:
                raise ValueError("recipe candidate changed after test batch creation")
            return recipe
        recipe = self.recipes.get(batch.recipe_id, batch.recipe_version)
        if recipe.content_sha256 != batch.recipe_sha256:
            raise ValueError("recipe changed after batch creation")
        return recipe

    def _workshop_root(self, batch_id: str) -> Krea2Batch:
        batch = self.batches.get(batch_id)
        if batch.workshop_source_batch_id is not None:
            return self.batches.get(batch.workshop_source_batch_id)
        return batch

    def _load_workshop(self, root: Krea2Batch) -> dict[str, Any]:
        if root.recipe_workshop is not None:
            value = json.loads(root.recipe_workshop)
            if not isinstance(value, dict) or value.get("schema_version") != 1:
                raise ValueError("unsupported recipe workshop schema")
            return value
        return {
            "schema_version": 1,
            "status": "active",
            "source_batch_id": root.batch_id,
            "base_recipe_id": root.recipe_id,
            "base_recipe_version": root.recipe_version,
            "model_id": root.model_id,
            "turns": [],
            "drafts": [],
            "active_draft_id": None,
            "test_batch_ids": [],
            "published_version": None,
        }

    @staticmethod
    def _append_workshop_draft(workshop: dict[str, Any], draft: str, *, source: str) -> None:
        drafts = workshop.setdefault("drafts", [])
        if drafts and drafts[-1].get("candidate") == draft:
            workshop["active_draft_id"] = drafts[-1]["draft_id"]
            return
        draft_id = f"D{len(drafts) + 1}"
        drafts.append({"draft_id": draft_id, "source": source, "candidate": draft})
        workshop["active_draft_id"] = draft_id

    def _candidate_recipe(
        self,
        base: Krea2VisualRecipe,
        draft: str | None,
        settings: Krea2BatchSettings | None,
        prompt_language: Krea2PromptLanguage | None = None,
    ) -> Krea2VisualRecipe:
        if prompt_language is not None and not isinstance(
            prompt_language,
            Krea2PromptLanguage,
        ):
            raise TypeError("prompt_language must be Krea2PromptLanguage")
        if draft is None:
            proposal = self.recipes.parse_revision_draft(base, json.dumps({
                "identity": base.identity,
                "invariants": list(base.invariants),
                "variables": list(base.variables),
                "risks": list(base.risks),
                "canonical_prompt": base.canonical_prompt,
            }, ensure_ascii=False))
            return replace(
                proposal,
                settings=settings or base.settings,
                prompt_language=prompt_language or base.prompt_language,
            )
        value = json.loads(draft)
        recipe_value = value.get("recipe", value) if isinstance(value, dict) else value
        if not isinstance(recipe_value, dict):
            raise ValueError("recipe draft must be a JSON object")
        semantic = {
            key: recipe_value[key]
            for key in ("identity", "invariants", "variables", "risks", "canonical_prompt")
        }
        proposal = self.recipes.parse_revision_draft(base, json.dumps(semantic, ensure_ascii=False))
        candidate_settings = settings or _settings_from_draft(value, base.settings)
        draft_language = Krea2PromptLanguage(
            recipe_value.get("prompt_language", base.prompt_language.value)
        )
        return replace(
            proposal,
            settings=candidate_settings,
            prompt_language=prompt_language or draft_language,
        )

    def _workshop_reviews(
        self,
        root: Krea2Batch,
        workshop: dict[str, Any],
    ) -> tuple[dict[str, str], ...]:
        batches = [root]
        for test_batch_id in workshop.get("test_batch_ids", []):
            try:
                batches.append(self.batches.get(test_batch_id))
            except (KeyError, FileNotFoundError):
                continue
        return tuple(
            {
                "decision": item.review.value,
                "signature": item.variation_signature,
                "comment": item.comment,
                "prompt": item.prompt,
            }
            for batch in batches
            for item in batch.items
            if item.review is not Krea2ReviewDecision.NEUTRAL or item.comment
        )

    def _recover_missing_outputs(self, batch: Krea2Batch) -> Krea2Batch:
        """Recover files written by SaveImageKJ before PanelForge knew their names.

        SaveImageKJ writes the PNG and caption but, unlike the core SaveImage node,
        the installed version does not expose an ``images`` entry in ComfyUI's
        history.  Limit this reconciliation to the exact historical import error;
        genuine render failures remain untouched.
        """
        if batch.status not in {Krea2BatchStatus.COMPLETED, Krea2BatchStatus.FAILED}:
            return batch
        recovered: list[Krea2BatchItem] = []
        recovered_count = 0
        for item in batch.items:
            if (
                item.status is not Krea2BatchItemStatus.FAILED
                or item.execution_id is None
                or item.error is None
                or _MISSING_HISTORY_OUTPUT not in item.error
            ):
                recovered.append(item)
                continue
            try:
                history = self.comfy.get_history(item.execution_id)
                output = _extract_output(
                    history,
                    item.execution_id,
                    self.workflow.output_node_id,
                    self.workflow.output_history_field,
                )
                content = self.comfy.download_output(
                    filename=output["filename"],
                    subfolder=output.get("subfolder", ""),
                    folder_type=output.get("type", "output"),
                )
                _validate_png(content)
                asset = self.assets.create(
                    content,
                    media_type=self.workflow.output_media_type,
                    source_run_id=batch.batch_id,
                )
                recovered.append(item.recover_output(asset.asset_id))
                recovered_count += 1
            except Exception:
                _LOGGER.exception(
                    "failed to recover KREA2 batch output %s/%s",
                    batch.batch_id,
                    item.item_id,
                )
                recovered.append(item)
        if recovered_count == 0:
            return batch
        failed_count = sum(item.status is Krea2BatchItemStatus.FAILED for item in recovered)
        warnings = list(batch.warnings)
        warnings.append(
            f"{recovered_count} sortie(s) ComfyUI existante(s) ont Ã©tÃ© rÃ©importÃ©es."
        )
        if failed_count:
            warnings.append(
                f"Batch terminÃ© avec {failed_count} rendu(s) encore en Ã©chec sur {len(recovered)}."
            )
        return self.batches.save(replace(
            batch,
            status=Krea2BatchStatus.COMPLETED,
            items=tuple(recovered),
            warnings=tuple(warnings),
            error=None,
        ))

    def _resource_warnings(self, settings: Krea2BatchSettings) -> tuple[str, ...]:
        warnings: list[str] = []
        models = {
            normalize_krea2_model_name(getattr(item, "comfy_name", ""))
            for item in self.resources.list_models()
        }
        loras = {
            normalize_krea2_model_name(getattr(item, "comfy_name", ""))
            for item in self.resources.list_loras()
        }
        if normalize_krea2_model_name(settings.model_name) not in models:
            warnings.append(f"Modèle indisponible : {settings.model_name}")
        for lora in settings.loras:
            if normalize_krea2_model_name(lora.name) not in loras:
                warnings.append(f"LoRA indisponible, ignoré au rendu : {lora.name}")
        return tuple(warnings)

    def _model_available(self, name: str) -> bool:
        target = normalize_krea2_model_name(name)
        return any(normalize_krea2_model_name(getattr(item, "comfy_name", "")) == target for item in self.resources.list_models())

    def _report(self, call_id: str | None, outcome: LlmCallApplicationOutcome, error: Exception | None = None) -> None:
        if self.application_outcomes is None or call_id is None:
            return
        try:
            self.application_outcomes.report_application_outcome(
                call_id,
                outcome,
                error_type=type(error).__name__ if error else None,
                error_message=str(error) if error else None,
            )
        except Exception:
            _LOGGER.exception("failed to report KREA2 batch application outcome")


def _decode_revision_response(raw: str) -> tuple[str, str]:
    text = _required_text(raw, "model response")
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise ValueError("JSON fence is not closed")
        text = "\n".join(lines[1:-1])
        if text.lstrip().startswith("json\n"):
            text = text.lstrip()[5:]
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("recipe workshop response must be a JSON object")
    if "recipe" in value:
        if set(value) != {"reply", "recipe"} or not isinstance(value["recipe"], dict):
            raise ValueError("recipe workshop response must contain only reply and recipe")
        reply = _required_text(value["reply"], "workshop reply")
        recipe = value["recipe"]
    else:
        reply = "J’ai préparé une nouvelle candidate testable à partir de vos retours."
        recipe = value
    return reply, json.dumps(recipe, ensure_ascii=False)


def _recipe_draft_json(recipe: Krea2VisualRecipe, *, base_version: str) -> str:
    return json.dumps({
        "schema_version": 1,
        "recipe_id": recipe.recipe_id,
        "base_version": base_version,
        "version": recipe.version,
        "identity": recipe.identity,
        "invariants": list(recipe.invariants),
        "variables": list(recipe.variables),
        "risks": list(recipe.risks),
        "canonical_prompt": recipe.canonical_prompt,
        "prompt_language": recipe.prompt_language.value,
        "settings": {
            "model_name": recipe.settings.model_name,
            "aspect_ratio": recipe.settings.aspect_ratio.value,
            "megapixels": recipe.settings.megapixels,
            "loras": [
                {"name": lora.name, "strength": lora.strength}
                for lora in recipe.settings.loras
            ],
        },
    }, ensure_ascii=False, indent=2)


def _settings_from_draft(
    value: Mapping[str, Any],
    fallback: Krea2BatchSettings,
) -> Krea2BatchSettings:
    raw = value.get("settings")
    if raw is None:
        return fallback
    if not isinstance(raw, Mapping):
        raise ValueError("recipe draft settings must be an object")
    raw_loras = raw.get("loras", [])
    if not isinstance(raw_loras, list):
        raise ValueError("recipe draft LoRAs must be an array")
    return Krea2BatchSettings(
        model_name=_required_text(raw.get("model_name"), "recipe model_name"),
        aspect_ratio=Krea2AspectRatio(raw.get("aspect_ratio")),
        megapixels=raw.get("megapixels"),
        loras=tuple(
            Krea2LoraSelection(
                name=_required_text(item.get("name"), "recipe LoRA name"),
                strength=item.get("strength"),
            )
            for item in raw_loras
            if isinstance(item, Mapping)
        ),
    )


def _draft_digest(draft: str) -> str:
    value = json.loads(draft)
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty")
    return value.strip()


def _require_active_workshop(workshop: Mapping[str, Any]) -> None:
    if workshop.get("status") != "active":
        raise ValueError("this recipe workshop is already published")


def _extract_output(history: Mapping[str, Any], execution_id: str, node_id: str, field: str) -> dict[str, str]:
    record = history.get(execution_id)
    outputs = record.get("outputs") if isinstance(record, Mapping) else None
    node = outputs.get(node_id) if isinstance(outputs, Mapping) else None
    candidates = node.get(field) if isinstance(node, Mapping) else None
    if isinstance(candidates, list) and candidates and isinstance(candidates[0], Mapping):
        value = candidates[0]
        filename = value.get("filename")
        if not isinstance(filename, str) or not filename:
            raise ValueError("ComfyUI returned an invalid filename")
        return {"filename": filename, "subfolder": str(value.get("subfolder", "")), "type": str(value.get("type", "output"))}
    fallback = _save_image_kj_output(record, node_id)
    if fallback is not None:
        return fallback
    raise ValueError(_MISSING_HISTORY_OUTPUT)


def _save_image_kj_output(record: object, node_id: str) -> dict[str, str] | None:
    """Derive SaveImageKJ's first filename from its immutable prompt snapshot."""
    prompt = record.get("prompt") if isinstance(record, Mapping) else None
    workflow = prompt[2] if isinstance(prompt, list) and len(prompt) > 2 else None
    node = workflow.get(node_id) if isinstance(workflow, Mapping) else None
    if not isinstance(node, Mapping) or node.get("class_type") != "SaveImageKJ":
        return None
    inputs = node.get("inputs")
    prefix = inputs.get("filename_prefix") if isinstance(inputs, Mapping) else None
    output_folder = inputs.get("output_folder") if isinstance(inputs, Mapping) else None
    if not isinstance(prefix, str) or not prefix.strip() or output_folder != "output":
        return None
    normalized = prefix.strip().replace("\\", "/").strip("/")
    parts = normalized.split("/")
    if not parts or any(not part or part in {".", ".."} for part in parts):
        return None
    basename = parts[-1]
    if "%" in basename:
        return None
    return {
        "filename": f"{basename}_00001_.png",
        "subfolder": "/".join(parts[:-1]),
        "type": "output",
    }


def _validate_png(content: bytes) -> None:
    if not isinstance(content, bytes) or not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("KREA2 batch output is not a PNG")


def _sidecar_text(
    batch: Krea2Batch,
    item: Krea2BatchItem,
    settings: Krea2BatchSettings,
    *,
    output_prefix: str,
    workflow_reference: object,
) -> str:
    width, height = settings.resolution
    payload = {
        "schema_version": 1,
        "prompt": item.prompt,
        "variation_signature": item.variation_signature,
        "batch": {
            "batch_id": batch.batch_id,
            "item_id": item.item_id,
            "visual_recipe": f"{batch.recipe_id}@{batch.recipe_version}",
            "visual_recipe_sha256": batch.recipe_sha256,
        },
        "prompt_generation": {
            "model_id": batch.model_id,
            "direction": batch.direction,
        },
        "render": {
            "model_name": settings.model_name,
            "aspect_ratio": settings.aspect_ratio.value,
            "megapixels": settings.megapixels,
            "base_width": width,
            "base_height": height,
            "seed": item.seed,
            "loras": [
                {"name": lora.name, "strength": lora.strength}
                for lora in settings.loras
            ],
            "output_prefix": output_prefix,
            "sampling": {
                "first_pass": {
                    "steps": 8,
                    "cfg": 1.1,
                    "sampler": "er_sde",
                    "scheduler": "simple",
                    "denoise": 1.0,
                },
                "latent_upscale": {"method": "bislerp", "scale_by": 1.5},
                "second_pass": {
                    "steps": 2,
                    "cfg": 1.0,
                    "sampler": "er_sde",
                    "scheduler": "simple",
                    "denoise": 0.3,
                },
            },
        },
        "workflow": {
            "operation_id": getattr(workflow_reference, "operation_id"),
            "recipe_id": getattr(workflow_reference, "recipe_id"),
            "version": getattr(workflow_reference, "version"),
            "sha256": getattr(workflow_reference, "workflow_sha256"),
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _error(error: Exception) -> str:
    if isinstance(error, urllib.error.HTTPError):
        return _http_error(error)
    detail = str(error).strip()
    return f"{type(error).__name__}: {detail}" if detail else type(error).__name__


def _http_error(error: urllib.error.HTTPError) -> str:
    prefix = f"HTTP {error.code} {error.reason}".strip()
    try:
        raw = error.read(16_384)
    except Exception:
        raw = b""
    body = raw.decode("utf-8", errors="replace").strip()
    if not body:
        return prefix
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return f"{prefix}: {body[:2_000]}"
    if not isinstance(payload, Mapping):
        return f"{prefix}: {body[:2_000]}"

    details: list[str] = []
    summary = payload.get("error")
    if isinstance(summary, Mapping):
        message = summary.get("message") or summary.get("type")
        if isinstance(message, str) and message.strip():
            details.append(message.strip())
    node_errors = payload.get("node_errors")
    if isinstance(node_errors, Mapping):
        for node_id, node_error in node_errors.items():
            errors = node_error.get("errors") if isinstance(node_error, Mapping) else None
            if not isinstance(errors, list):
                continue
            for item in errors:
                if not isinstance(item, Mapping):
                    continue
                message = item.get("message") or item.get("details") or item.get("type")
                if isinstance(message, str) and message.strip():
                    details.append(f"nœud {node_id}: {message.strip()}")
    if not details:
        details.append(body[:2_000])
    return f"{prefix}: {'; '.join(details)}"
