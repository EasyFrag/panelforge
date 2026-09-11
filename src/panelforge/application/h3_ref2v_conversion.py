"""One-call adaptation of an existing H3 prompt, preserving compiler-owned text."""

from collections import Counter
from dataclasses import replace
import hashlib
import json
import re
from threading import RLock
from time import monotonic

from panelforge.domain.h3_render import (
    H3Ref2VAdaptation, H3RenderInputMode, H3RenderProject, H3RenderRevisionVersion, H3RenderSetup,
)
from .direct_ref2v_prompt import direct_reference_header_for_roles, lint_direct_ref2v_prompt
from .direct_fl2va_prompt import requested_h3_base_duration_ms
from .direct_ref2v_multishot_prompt_v2 import lint_direct_ref2v_multishot_prompt_v2
from .minimax_h3_protocol import extract_compiled_camera_clauses, lint_h3_prompt, H3ProtocolMode, H3IssueSeverity
from .prompt_lab import CompletionRequest, ImageInput, StreamEventKind, StreamPhase, LlmCallApplicationOutcome

CONVERSION_VERSION = "1.0.0"
CONVERSION_SYSTEM_V1 = """Adapt an already authored MiniMax H3 image/text-to-video prompt into Ref2V.
Return exactly one JSON object: {"shots": ["complete adapted body for shot 1", "..."]}.
Keep the supplied number and order of shots. Translate the conditioning references, not the story:
preserve every action, causal change, final state, existing speaker, camera decision, cut and chronology.
Use the native images only within their supplied reference roles. The first and last references describe
the intended opening/final states; do not reinterpret them as identity-only references or add a hold.
Keep every [[keep:N]] token exactly once, in its original shot and original order. Those tokens contain
protected camera clauses, spoken lines, timestamps and transitions. Never emit new camera prose,
speech, timestamps, shot headings, audio fields or reference-alignment headers. The application owns them.
You may cite only the supplied <Picture N> labels. Ref2V reference semantics replace any old FL2VA
alignment instructions, while the visual intent and action stay the same. Do not improve the script,
invent dialogue, generate a Brief/Plan, ask questions, or describe alternative versions.
Write the result directly, in the language of the existing visual prompt; supplied dialogue stays verbatim.
"""
_FIELDS = re.compile(r"(?m)^(integrated_multimodal_description|overall_soundscape|non_diegetic_music):[ \t]*")
_HEADINGS = re.compile(r"(?m)^\[Shot ([1-9][0-9]*)\](?:[ \t]+At \d{2}:\d{2}\.\d{3},)?")
_TOKEN = re.compile(r"\[\[keep:(\d+)\]\]")


def conversion_document(prompt: str) -> dict:
    matches = list(_FIELDS.finditer(prompt))
    if [m.group(1) for m in matches] != ["integrated_multimodal_description", "overall_soundscape", "non_diegetic_music"]:
        raise ValueError("L’adaptation attend les trois champs du prompt H3 courant.")
    values = {m.group(1): prompt[m.end():matches[i+1].start() if i+1 < len(matches) else len(prompt)].strip()
              for i, m in enumerate(matches)}
    body = values["integrated_multimodal_description"]
    headings = list(_HEADINGS.finditer(body))
    if not headings or [int(m.group(1)) for m in headings] != list(range(1, len(headings)+1)):
        raise ValueError("Le prompt H3 doit contenir ses plans numérotés dans l’ordre.")
    cameras = extract_compiled_camera_clauses(prompt)
    alternatives = [re.escape(c) for c in sorted(set(cameras), key=len, reverse=True)]
    alternatives += [r"<d>.*?</d>", r"<scenetrans>", r"(?:At\s+)?\d{2}:\d{2}\.\d{3}",
                     r"The target video[^\n]*?\.(?=\s|$)"]
    protected = re.compile("|".join(alternatives), re.DOTALL)
    locks = []
    shots = []
    for i, heading in enumerate(headings):
        text = body[heading.end():headings[i+1].start() if i+1 < len(headings) else len(body)].strip()
        if i == 0 and body[:heading.start()].strip():
            text = body[:heading.start()].strip() + " " + text
        def keep(match):
            locks.append(match.group())
            return f"[[keep:{len(locks)}]]"
        shots.append(protected.sub(keep, text))
    return {"shots": shots, "headings": [h.group() for h in headings], "locks": locks,
            "duration_ms": requested_h3_base_duration_ms(prompt),
            "overall_soundscape": values["overall_soundscape"], "non_diegetic_music": values["non_diegetic_music"]}


def compile_conversion(raw: str, source_prompt: str, roles: tuple[str, ...], *, combat_sequence: bool = False, combat_version: str | None = None, classic_cinematic: bool = False) -> str:
    source = conversion_document(source_prompt)
    value = raw.strip()
    if value.startswith("```") and value.endswith("```"):
        value = value.split("\n", 1)[1][:-3].strip()
    data = json.loads(value)
    if not isinstance(data, dict) or set(data) != {"shots"} or not isinstance(data["shots"], list) or len(data["shots"]) != len(source["shots"]):
        raise ValueError("La conversion doit conserver le nombre de plans dans un objet JSON shots.")
    bodies = []
    for before, after in zip(source["shots"], data["shots"], strict=True):
        if not isinstance(after, str) or not after.strip():
            raise ValueError("Chaque plan adapté doit contenir du texte.")
        if _TOKEN.findall(before) != _TOKEN.findall(after):
            raise ValueError("La conversion doit conserver les éléments protégés dans leur plan et leur ordre.")
        residual = _TOKEN.sub("", after)
        if re.search(r"<d>|</d>|<scenetrans>|\[\[|\]\]|\[Shot |\b\d{2}:\d{2}\.\d{3}\b|overall_soundscape:|non_diegetic_music:", residual):
            raise ValueError("La conversion a ajouté des paroles, repères ou champs non autorisés.")
        numbers = {int(n) for n in re.findall(r"<Picture\s+(\d+)>", after)}
        if not numbers <= set(range(1, len(roles)+1)):
            raise ValueError("La conversion cite une image qui n’existe pas.")
        bodies.append(_TOKEN.sub(lambda m: source["locks"][int(m.group(1))-1], after).strip())
    header = direct_reference_header_for_roles(roles)
    headings = source["headings"] if len(bodies) > 1 else ["Shot 1:"]
    setup = "The reference images apply only within their declared roles."
    if source["duration_ms"] and not any("The target video" in body for body in bodies):
        setup += f" Total duration: {source['duration_ms'] / 1000:g} seconds."
    prompt = header + "\n\n" + setup + "\n\n"
    prompt += "\n\n".join(h + " " + b for h, b in zip(headings, bodies, strict=True))
    prompt += f"\n\noverall_soundscape:\n{source['overall_soundscape']}\n\nnon_diegetic_music:\n{source['non_diegetic_music']}"
    if classic_cinematic:
        from .classic_cinematic import prompt_errors
        from .cinematic_core_v1 import preserve_camera_layout
        errors = prompt_errors(prompt, "ref2va")
        preserve_camera_layout(source_prompt, prompt)
    elif combat_sequence:
        from .combat_sequence import prompt_errors
        errors = prompt_errors(prompt, "ref2va", combat_version)
        if combat_version == "1.3.0":
            from .combat_cinematic import preserve_camera_layout
            preserve_camera_layout(source_prompt, prompt)
    else:
        errors = (lint_direct_ref2v_multishot_prompt_v2(prompt, preserve_h3_landmarks=True)
                  if len(bodies) > 1 else lint_direct_ref2v_prompt(prompt))
    errors += tuple(issue.message for issue in lint_h3_prompt(H3ProtocolMode.REF2VA, prompt) if issue.severity is H3IssueSeverity.ERROR)
    if Counter(extract_compiled_camera_clauses(prompt)) != Counter(extract_compiled_camera_clauses(source_prompt)):
        errors += ("Les directives caméra doivent rester identiques pendant la conversion.",)
    if errors:
        raise ValueError(" ".join(errors))
    return prompt


class H3Ref2VConversionService:
    def __init__(self, renders):
        self.renders = renders
        self._lock = RLock()
        self._active: set[str] = set()

    def prepare(self, source_id: str, *, request_id: str, prompt: str, model_id: str,
                setup: H3RenderSetup, extra_reference: tuple[str, str] | None = None) -> H3RenderProject:
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id):
            raise ValueError("Identifiant de conversion invalide.")
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 60000:
            raise ValueError("Le prompt courant est vide ou trop long.")
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("Choisissez un modèle LLM pour l’adaptation.")
        source = self.renders.projects.get(source_id)
        if source.input_mode is H3RenderInputMode.REF2VA:
            raise ValueError("Cet atelier est déjà en REF2V.")
        conversion_document(prompt)
        references = [(asset, label, role) for asset, label, role in (
            (source.first_frame_asset_id, source.first_frame_label, "first_frame"),
            (source.last_frame_asset_id, source.last_frame_label, "last_frame")) if asset]
        if not references and extra_reference:
            references.append((*extra_reference, "subject_reference"))
        if not references:
            raise ValueError("Ajoutez une image de référence avant de convertir un prompt texte seul.")
        for asset, _, _ in references:
            if not self.renders.assets.get(asset).media_type.startswith("image/"):
                raise ValueError("Les références doivent être des images.")
        expected = self.renders.workflow_for_mode(H3RenderInputMode.REF2VA, setup.recipe.recipe_id, setup.recipe.version)
        if expected.reference != setup.recipe:
            raise ValueError("La recette de rendu de destination est indisponible.")
        if setup.checkpoint is not None or setup.model_loading is not None:
            loading = self.renders.resolve_model_loading(expected, H3RenderInputMode.REF2VA, setup.checkpoint)
            if loading != setup.model_loading:
                raise ValueError("Le modèle vidéo de destination ne correspond pas aux réglages sélectionnés.")
        if setup.video_loras is not None:
            self.renders.validate_video_loras(expected, setup.video_lora, setup.video_loras)
        target_id = "h3-adapt-" + hashlib.sha256(f"{source_id}:{request_id}".encode()).hexdigest()[:32]
        adaptation = H3Ref2VAdaptation(request_id, source_id, prompt.strip(), tuple(r[2] for r in references), setup)
        project = H3RenderProject(target_id, source.source_session_id, f"adaptation:{request_id}", model_id,
            H3RenderInputMode.REF2VA, prompt.strip(),
            reference_asset_ids=tuple(r[0] for r in references), reference_labels=tuple(r[1] for r in references),
            planned_cut_times_ms=source.planned_cut_times_ms, dialogue_level=source.dialogue_level,
            revision_version=self.renders.default_revision_version(H3RenderInputMode.REF2VA, source.preparation),
            preparation=source.preparation,
            combat_settings=source.combat_settings, cinematic_settings=source.cinematic_settings, adaptation=adaptation)
        with self._lock:
            try:
                existing = self.renders.projects.get(target_id)
            except (KeyError, FileNotFoundError):
                return self.renders.projects.create(project)
            previous = existing.adaptation
            if previous is None or (previous.source_prompt, previous.render_setup, existing.reference_asset_ids, existing.model_id) != (adaptation.source_prompt, setup, project.reference_asset_ids, model_id):
                raise ValueError("Cet identifiant correspond à une autre conversion ; démarrez une nouvelle adaptation.")
            return existing

    def stream(self, project_id: str, *, include_reasoning: bool = False):
        from .h3_render import H3RenderStreamEvent, extract_prompt_cut_times_ms
        with self._lock:
            project = self.renders.projects.get(project_id)
            adaptation = project.adaptation
            if adaptation is None:
                raise ValueError("Cet atelier ne provient pas d’une adaptation.")
            if project_id in self._active:
                raise ValueError("Cette adaptation est déjà en cours.")
            if adaptation.status != "pending":
                yield H3RenderStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED, project=project,
                    error=adaptation.error or ("Appel interrompu ; créez une nouvelle adaptation." if adaptation.status == "running" else None))
                return
            self._active.add(project_id)
            project = self.renders.projects.save(replace(project, adaptation=replace(adaptation, status="running")))
        raw = ""
        saved_at = monotonic()
        call_id = None
        completed = False
        try:
            document = conversion_document(adaptation.source_prompt)
            images = tuple(ImageInput(media_type=self.renders.assets.get(asset).media_type,
                content=self.renders.assets.read_bytes(asset), label=f"<Picture {i}> role={role}")
                for i, (asset, role) in enumerate(zip(project.reference_asset_ids, adaptation.reference_roles, strict=True), 1))
            request = CompletionRequest(model_id=project.model_id, system_prompt=CONVERSION_SYSTEM_V1,
                user_prompt=json.dumps({"reference_roles": adaptation.reference_roles, "shots": document["shots"]}, ensure_ascii=False),
                images=images, temperature=0.15, max_tokens=131072,
                operation_id=f"h3.convert.ref2v@{CONVERSION_VERSION}", include_reasoning=include_reasoning)
            for event in self.renders.gateway.stream(request):
                if event.kind is StreamEventKind.DELTA:
                    raw += event.text
                    if monotonic() - saved_at >= 2:
                        project = self.renders.projects.save(replace(project,
                            adaptation=replace(adaptation, status="running", raw_response=raw)))
                        saved_at = monotonic()
                if event.kind in {StreamEventKind.COMPLETED, StreamEventKind.TRUNCATED}:
                    if event.result is not None:
                        raw, call_id = event.result.content, event.result.call_id
                    if event.kind is StreamEventKind.TRUNCATED:
                        raise ValueError("La réponse de conversion a été tronquée ; le brouillon est conservé.")
                    prompt = compile_conversion(raw, adaptation.source_prompt, adaptation.reference_roles,
                                                combat_sequence=project.combat_settings is not None, combat_version=project.preparation.version,
                                                classic_cinematic=project.preparation.is_classic_cinematic)
                    project = self.renders.projects.save(replace(project, current_prompt=prompt,
                        camera_clauses=extract_compiled_camera_clauses(prompt), planned_cut_times_ms=extract_prompt_cut_times_ms(prompt),
                        adaptation=replace(adaptation, status="ready", raw_response=raw, call_id=call_id)))
                    self.renders._report(call_id, LlmCallApplicationOutcome.ACCEPTED)
                    completed = True
                    yield H3RenderStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED, project=project, progress=1.0)
                    return
                yield H3RenderStreamEvent(event.kind, event.phase, event.text, event.progress)
            raise ValueError("Le modèle a interrompu l’adaptation sans résultat complet.")
        except BaseException as error:
            if completed:
                raise
            message = "Adaptation interrompue ; brouillon conservé." if isinstance(error, GeneratorExit) else str(error)
            project = self.renders.projects.save(replace(project, adaptation=replace(adaptation, status="failed", raw_response=raw, error=message, call_id=call_id)))
            self.renders._report(call_id, LlmCallApplicationOutcome.REJECTED, error)
            if isinstance(error, GeneratorExit):
                raise
            if not isinstance(error, Exception):
                raise
            yield H3RenderStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED, project=project, error=message)
        finally:
            with self._lock:
                self._active.discard(project_id)
