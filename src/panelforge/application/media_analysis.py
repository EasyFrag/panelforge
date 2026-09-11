"""One visual analysis call, producing an editable French intention."""
from dataclasses import asdict
import json
from pathlib import Path
from threading import Lock
from uuid import uuid4

from panelforge.domain.media_analysis import ANALYSIS_VERSION, SPEECH_ANALYSIS_VERSION, MediaAnalysisInput
from .prompt_lab import CompletionRequest, ImageInput, StreamEventKind, LlmCallApplicationOutcome, truncated_response_message
from .revised_documents import strip_markdown_fence
from .media_intention import without_source_citations, source_reference_warning


class MediaAnalysisConflict(ValueError):
    pass


class MediaAnalysisService:
    def __init__(self, *, gateway, assets, store, images, prompt_directory: Path, application_outcomes=None,
                 transcription=None, speech_prompt_directory: Path | None = None):
        self.gateway, self.assets, self.store, self.images = gateway, assets, store, images
        self.system_prompt = (prompt_directory / "system.txt").read_text(encoding="utf-8")
        self.speech_system_prompt = (speech_prompt_directory / "system.txt").read_text(encoding="utf-8") if speech_prompt_directory else None
        self.transcription = transcription
        self.application_outcomes = application_outcomes
        self._lock = Lock()
        self._active = set()

    def create(self, request: MediaAnalysisInput):
        if request.transcript is not None and self.speech_system_prompt is None:
            raise ValueError("L’analyse avec paroles n’est pas configurée.")
        for frame in request.frames:
            asset = self.assets.get(frame.asset_id)
            if asset.media_type not in {"image/png", "image/jpeg", "image/webp"}:
                raise ValueError("Les captures doivent être des images.")
        return self.store.save(dict(analysis_id=f"analysis-{uuid4().hex}", analysis_version=SPEECH_ANALYSIS_VERSION if request.transcript is not None else ANALYSIS_VERSION,
            request=asdict(request), status="draft", intention="", generated_intention="", observations=[], uncertainties=[], error=None, call_id=None))

    def save_intention(self, analysis_id, intention):
        if not isinstance(intention, str) or not intention.strip() or len(intention) > 16_000:
            raise ValueError("L’intention doit contenir entre 1 et 16 000 caractères.")
        intention = without_source_citations(intention)
        if not intention:
            raise ValueError("Décrivez la scène ou ses actions dans l’intention.")
        warning = source_reference_warning(intention)
        if warning:
            raise ValueError(warning)
        with self._lock:
            if analysis_id in self._active:
                raise MediaAnalysisConflict("Cette analyse est en cours.")
            record = self.store.get(analysis_id)
            if record["status"] != "succeeded":
                raise ValueError("Terminez l’analyse avant d’enregistrer l’intention.")
            record["intention"] = intention.strip()
            record["intention_warning"] = None
            return self.store.save(record)

    def stream(self, analysis_id, *, include_reasoning=False):
        # Reject known conflicts before SSE; claim on iteration so an unopened
        # response cannot leave a permanent active entry.
        with self._lock:
            if analysis_id in self._active:
                raise MediaAnalysisConflict("Cette analyse est déjà en cours.")
            record = self.store.get(analysis_id)
            if record["status"] == "succeeded":
                return iter([dict(kind="completed", phase="completed", progress=1, record=record)])
            MediaAnalysisInput.from_dict(record["request"])
        return self._stream(record, include_reasoning)

    def _stream(self, record, include_reasoning):
        analysis_id = record["analysis_id"]
        with self._lock:
            record = self.store.get(analysis_id)
            conflict = analysis_id in self._active
            cached = record["status"] == "succeeded"
            if not conflict and not cached:
                self._active.add(analysis_id)
        if conflict:
            yield dict(kind="error", phase="failed", message="Cette analyse est déjà en cours.")
            return
        if cached:
            yield dict(kind="completed", phase="completed", progress=1, record=record)
            return
        completed, call_id, stream = False, None, None
        try:
            request = MediaAnalysisInput.from_dict(record["request"])
            version = SPEECH_ANALYSIS_VERSION if request.transcript is not None else ANALYSIS_VERSION
            record.update(status="running", error=None, analysis_version=version)
            self.store.save(record)
            yield dict(kind="status", phase="preparing", text="Préparation des images…")
            inputs = []
            for i, frame in enumerate(request.frames, 1):
                _, content = self.images.prepare(self.assets.read_bytes(frame.asset_id))
                time = "temps inconnu" if frame.time_seconds is None else f"{frame.time_seconds:g} s"
                inputs.append(ImageInput("image/jpeg", content, f"Image {i} — {time}"))
            context = asdict(request)
            # Media names are untrusted data; the model sees numbered evidence only.
            context.pop("source_name")
            context.pop("model_id")
            context["frames"] = [{"image": i, "time_seconds": f.time_seconds} for i, f in enumerate(request.frames, 1)]
            context.pop("transcript", None)
            if request.transcript is not None:
                if self.speech_system_prompt is None:
                    raise ValueError("L’analyse avec paroles n’est pas configurée.")
                context["transcript"] = dict(text=request.transcript.text, language=request.transcript.language,
                    detected_language=request.transcript.detected_language, keep_dialogue=request.transcript.keep_dialogue,
                    time_origin="selected_clip_start", edited=request.transcript.text != request.transcript.original_text)
            completion = CompletionRequest(model_id=request.model_id, system_prompt=self.speech_system_prompt if request.transcript is not None else self.system_prompt,
                user_prompt=json.dumps(context, ensure_ascii=False), images=tuple(inputs), temperature=.3,
                max_tokens=16_000, operation_id=f"media.visual-intention@{version}", include_reasoning=include_reasoning)
            stream = self.gateway.stream(completion)
            for event in stream:
                if event.result:
                    call_id = event.result.call_id
                if event.kind is StreamEventKind.TRUNCATED:
                    raise ValueError(truncated_response_message(completion.max_tokens))
                if event.kind is StreamEventKind.COMPLETED:
                    if event.result is None:
                        raise ValueError("L’analyse n’a pas renvoyé de résultat.")
                    value = parse_result(event.result.content)
                    generated = f"Durée cible : {request.duration_seconds:g} secondes.\n\n{value['intention']}"
                    intention = without_source_citations(generated)
                    record.update(status="succeeded", generated_intention=generated, intention=intention,
                        intention_warning=source_reference_warning(intention), analysis_version=version,
                        observations=value["observations"], uncertainties=value["uncertainties"], call_id=call_id, error=None)
                    record = self.store.save(record)
                    completed = True
                    self._report(call_id, LlmCallApplicationOutcome.ACCEPTED)
                    yield dict(kind="completed", phase="completed", progress=1, record=record)
                    return
                yield dict(kind=event.kind.value, phase=event.phase.value, text=event.text, progress=event.progress)
            raise ValueError("Le flux d’analyse s’est interrompu avant le résultat. Vous pouvez réessayer.")
        except GeneratorExit:
            raise
        except Exception as error:
            record.update(status="failed", error=str(error), call_id=call_id)
            self.store.save(record)
            self._report(call_id, LlmCallApplicationOutcome.REJECTED, error)
            yield dict(kind="error", phase="failed", message=str(error), error=str(error), record=record)
        finally:
            try:
                if stream is not None and hasattr(stream, "close"):
                    stream.close()
                if not completed and record["status"] == "running":
                    record.update(status="failed", error="Analyse interrompue ; les images et la consigne sont conservées.")
                    self.store.save(record)
            finally:
                with self._lock:
                    self._active.discard(analysis_id)

    def _report(self, call_id, outcome, error=None):
        if call_id and self.application_outcomes:
            self.application_outcomes.report_application_outcome(call_id, outcome,
                error_type=type(error).__name__ if error else None, error_message=str(error) if error else None)


def parse_result(raw):
    try:
        value = json.loads(strip_markdown_fence(raw.strip()))
    except (ValueError, AttributeError) as error:
        raise ValueError("L’analyse n’a pas fourni le JSON attendu. Les médias sont conservés pour réessayer.") from error
    if not isinstance(value, dict) or set(value) != {"intention", "observations", "uncertainties"}:
        raise ValueError("Résultat d’analyse incomplet.")
    if not isinstance(value["intention"], str) or not value["intention"].strip() or len(value["intention"]) > 15_000:
        raise ValueError("Intention vide ou trop longue.")
    for key in ("observations", "uncertainties"):
        if not isinstance(value[key], list) or len(value[key]) > 24 or any(not isinstance(s, str) or not s.strip() or len(s) > 2_000 for s in value[key]):
            raise ValueError("Observations d’analyse invalides.")
    return value
