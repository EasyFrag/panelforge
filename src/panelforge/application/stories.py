"""Story ideation and revision, using the existing LLM gateway only on request."""
from copy import deepcopy
from datetime import UTC, datetime
import json
from threading import Event, RLock, Thread
from time import monotonic
from uuid import uuid4

from panelforge.domain.stories import (
    DEFAULT_DIALOGUE_LANGUAGE, DEFAULT_NARRATIVE_FORMAT, EXPLICIT_RECIPE_ID, RECIPE_ID, RECIPE_VERSION,
    SENSUAL_RECIPE_ID, SERIES_EPISODE_COUNT, SILENT_CATS_RECIPE_ID,
    decode_story_json, dialogue_language_label, dialogue_language_selection,
    extract_script_dialogue_cues, narrative_format_selection, parse_response, response_contract,
    scenario_text, scene_intention, story_diagnostics, story_recipe_selection,
    story_recipe_spec, story_recipe_specs, validate_fruit_story_contract, validate_scenario,
)
from .prompt_lab import CompletionRequest, StreamEventKind, LlmCallApplicationOutcome
from .revised_documents import strip_markdown_fence
from panelforge.domain import long_stories as long_narrative
from panelforge.domain.story_response_recovery import StoryJsonError, decode_response
from panelforge.domain import story_contracts
from panelforge.domain import story_draft_repairs
from panelforge.domain.story_diagnostics import normalize_scene_state, project_quality, quality_issues
from . import story_attempts
from .long_stories import request as long_story_request
from .story_workflow import StoryWorkflow, new_workflow
from .story_stream import story_truncation_message


_MAX_LIVE_DRAFT_CHARS = 240_000
_MAX_LIVE_REASONING_CHARS = 144_000
_LIVE_SAVE_INTERVAL_SECONDS = 1.5
_MAX_STANDARD_BRIEF_CHARS = 12_000
_MAX_CONTINUATION_BRIEF_CHARS = 60_000

_DIALOGUE_REGISTER_POLICIES = {
    1: (
        "REGISTRE DES DIALOGUES — ORAL DIRECT. Dans les dialogues nouvellement écrits, emploie la langue cible "
        "de façon orale, quotidienne et moins littéraire lorsque le personnage et la situation s’y prêtent. Garde les actions "
        "et la narration dans leur registre actuel. Ne force pas cette couleur dans chaque réplique."
    ),
    2: (
        "REGISTRE DES DIALOGUES — CRU. Dans les dialogues nouvellement écrits, préfère dans la langue cible des formulations "
        "franches, familières ou vulgaires lorsque le personnage et la situation s’y prêtent. Garde les actions et la narration dans leur registre actuel. "
        "La vulgarité reste naturelle, intelligible et propre à chaque personnage ; ce n’est pas un quota."
    ),
    3: (
        "REGISTRE DES DIALOGUES — TRÈS CRU / ARGOT. Dans les dialogues nouvellement écrits, autorise fortement le "
        "vocabulaire cru, l’argot et les tournures de rue ou internet naturels dans la langue cible et compatibles avec le personnage, "
        "sans traduire littéralement un argot français et sans transformer automatiquement tous les personnages en caricatures. "
        "Garde les actions et la narration dans leur registre actuel ; ce n’est pas un quota."
    ),
}


def _dialogue_language_policy(language, *, script=False, revising=False):
    canonical = dialogue_language_selection(language)
    label = dialogue_language_label(canonical)
    if script:
        return (
            f"LANGUE PARLÉE — {label} (identifiant H3 : {canonical}). Le sélecteur déclare la langue réellement "
            "écrite dans le script : ne traduis, ne translittère et ne reformule aucune réplique. Les descriptions, "
            "la narration éditoriale et reply restent en français."
        )
    policy = (
        f"LANGUE PARLÉE — {label} (identifiant H3 : {canonical}). Écris uniquement le champ text de toute nouvelle "
        f"réplique en {label}. Les descriptions, les actions, les autres champs narratifs et reply restent en français. "
        "Cette règle remplace, pour dialogue.text seulement, toute consigne éditoriale antérieure disant que le scénario "
        "ou les paroles sont en français. N’ajoute ni traduction parallèle ni translittération."
    )
    if revising:
        policy += (
            " Les répliques déjà validées restent inchangées sauf demande explicite de reformulation ; toute réplique "
            "nouvelle ou explicitement réécrite utilise cette langue."
        )
    return policy


def _dialogue_register_policy(level, language):
    policy = _DIALOGUE_REGISTER_POLICIES[level]
    if language == "French":
        if level == 2:
            policy += " En français, préfère par exemple « ça pue » à « cela sent mauvais » lorsque le personnage s’y prête."
        elif level == 3:
            policy += " En français, des formulations comme « ça schlingue » ou « wesh » sont permises si elles correspondent au personnage."
    return policy


def _fruit_audio_first_policy():
    return """MODE FRUIT — NOMS ET COMPRÉHENSION AUDIO OBLIGATOIRES
Tous les personnages Fruit portent un seul nom inventé construit à partir de leur espèce. Aucun prénom humain,
aucun prénom humain suivi du fruit en nom de famille : « Nour Myrtille », « Camille Cerise » ou « Théo Raisin »
sont interdits. Exemples de forme : Figos/Figette, Pomitto/Pomitta, Mangotino/Manguette,
Ananito/Ananette, Myrtillo/Myrtilla, Cerisino/Cerisetta. La fiche description nomme explicitement l’espèce.
Si un ancien concept contient encore un prénom humain, remplace-le de façon cohérente dans le prochain arc ou
scénario structuré.

L’histoire doit réussir le TEST D’ÉCOUTE : sans regarder l’image, on comprend la situation, ce que chaque
personnage veut, pourquoi il agit, l’obstacle, puis la conséquence. Les paroles exactes portent toute information
causale indispensable ; action, opening_state et ending_state ne doivent pas être les seuls endroits où elle existe.
Un texte écrit important est lu ou reformulé à voix haute. Les gestes et les images enrichissent le gag et
l’émotion, mais ne remplacent pas l’explication narrative.

Chaque micro-scène comporte entre UNE ET QUATRE entrées dialogue brèves. Utilise spoken pour la confrontation,
thought ou voice_over pour rendre une intention, une information ou un raccord explicite lorsqu’il serait artificiel
de le faire dire à voix haute. Quatre répliques par scène sont autorisées. Ne décris pas oralement chaque geste :
verbalise seulement les faits nécessaires pour suivre la causalité. Si l’intrigue ne tient pas, répartis-la sur les
scènes ou épisodes disponibles au lieu de supprimer une étape indispensable."""


def _dedupe_conversation(turns):
    """Remove only adjacent duplicate messages, typically left by a failed retry."""
    compact = []
    for turn in turns:
        normalized = (turn.get("role"), (turn.get("text") or "").strip())
        previous = compact[-1] if compact else None
        if previous and normalized == (previous.get("role"), (previous.get("text") or "").strip()):
            compact[-1] = turn
        else:
            compact.append(turn)
    return compact


def _ideas_system_prompt(base_prompt):
    """One proposal, including when archived/user recipes still ask for three."""
    fixed_count_markers = ("trois", "concept-2", "concept-3")
    retained = [
        line for line in base_prompt.splitlines()
        if not any(marker in line.casefold() for marker in fixed_count_markers)
    ]
    authority = (
        "ÉTAPE IDÉES — UNE HISTOIRE\n"
        "Produis exactement une proposition complète, identifiée concept-1. "
        "Le brief, les corrections explicites et le contrat JSON du contexte font foi. "
        "Renvoie uniquement reply et concepts, en JSON valide."
    )
    return authority + "\n\n" + "\n".join(retained).strip()


_LONG_OUTLINE_MODE_POLICIES = {
    RECIPE_ID: (
        "Univers Fruit : tous les personnages principaux sont des fruits anthropomorphes adultes, avec une espèce "
        "et un nom fruité stable (Pomitta, Figos, Mangotino, Ananette, ou forme comparable). La causalité essentielle "
        "doit pouvoir être racontée plus tard par des dialogues, pensées ou voix off, sans imposer ici un quota de répliques."
    ),
    SENSUAL_RECIPE_ID: (
        "Univers sensuel : personnages humains clairement adultes, désir réciproque et conflit non coercitif. "
        "La progression reste évocatrice et non graphique."
    ),
    EXPLICIT_RECIPE_ID: (
        "Univers Cru ++ : tous les participants sont adultes. Respecte exactement la progression et les limites "
        "demandées par le brief ; les changements de relation et d'état doivent rester causalement lisibles."
    ),
    SILENT_CATS_RECIPE_ID: (
        "Univers Chats muets : couple de chats anthropomorphes adultes photoréalistes, histoire entièrement "
        "compréhensible par les gestes et les objets, sans parole, voix off, texte lisible ni narration."
    ),
}


def _long_outline_system_prompt(recipe_id, dialogue_language):
    mode_policy = _LONG_OUTLINE_MODE_POLICIES.get(recipe_id, "Respecte le ton et les limites du brief.")
    language_policy = ""
    if recipe_id != SILENT_CATS_RECIPE_ID:
        language_policy = (
            f" Les futures paroles seront en {dialogue_language_label(dialogue_language)} ; la bible et l'arc restent en français."
        )
    return f"""ARCHITECTE — ARC LONG UNIQUEMENT
Construis une bible de série compacte et exactement {SERIES_EPISODE_COUNT} épisodes ordonnés, episode-1 à
episode-{SERIES_EPISODE_COUNT}. Renvoie uniquement reply et series_outline selon le contrat JSON fourni. Ne produis
ni micro-scène, ni dialogue détaillé, ni variante alternative. Le brief et le concept sélectionné sont autoritaires.

Chaque épisode est une unité compréhensible avec une promesse locale, un obstacle, une chaîne causale, un payoff
local accompli et un état concret transmis au suivant. Son dernier beat doit MONTRER l'action ou la conséquence qui
réalise le payoff local ; ending_state l'enregistre, il ne le remplace pas. Ne livre pas quatre instantanés d'une
histoire plus grande.

N'ouvre jamais un épisode après un incident causal indispensable (vol, trahison, découverte, signature, agression,
décision) sauf si actual_previous_episodes montre déjà cet incident. Sinon, fais commencer l'épisode avant et inscris
l'incident dans ses beats. Une preuve, un objet décisif ou une aide doit être introduit avant son usage. Privilégie un
conflit central et une preuve centrale au lieu d'empiler des artifices.

Calibre chaque épisode pour target_scene_count × target_clip_seconds secondes. Les beats sont des jalons narratifs,
pas une instruction de distribuer mécaniquement un beat par clip. N'exige pas une action naturellement plus longue que
la durée disponible (par exemple cuisiner entièrement un plat) : montre une action courte, son résultat déjà préparé,
ou reporte cette progression sur un autre épisode.

La bible conserve exactement les mêmes identifiants, noms, liens et identités visuelles dans les quatre épisodes.
{mode_policy}{language_policy}
JSON valide uniquement, sans markdown ni commentaire extérieur."""


class StoryConflict(ValueError):
    pass


class StoryCancelled(Exception):
    pass


def _now():
    return datetime.now(UTC).isoformat()


class StoryService:
    def __init__(self, *, gateway, store, recipes, traces=None, application_outcomes=None, long_recipes=None):
        self.gateway, self.store, self.recipes = gateway, store, recipes
        self.traces, self.application_outcomes = traces, application_outcomes
        self.long_recipes = long_recipes
        self._lock = RLock()
        self._active = {}
        self.workflow = StoryWorkflow(self)

    @staticmethod
    def _normalize(project):
        project.setdefault("recipe", {"id": RECIPE_ID, "version": RECIPE_VERSION})
        recipe = story_recipe_selection(project["recipe"])
        project["recipe"] = recipe
        legacy_model = project.get("model_id", "")
        project.setdefault("architect_model_id", legacy_model)
        project.setdefault("writer_model_id", legacy_model)
        project.setdefault("creation_mode", "ideas")
        project.setdefault("narrative_format", DEFAULT_NARRATIVE_FORMAT)
        project["narrative_format"] = narrative_format_selection(project["narrative_format"])
        project.setdefault("parent_story_id", None)
        if project["narrative_format"] == "long":
            document = project.setdefault("document", {})
            document.setdefault("series_outline", None)
            document.setdefault("selected_episode_id", None)
            document.setdefault("episode_scenarios", {})
            document.setdefault("episode_formats", {})
        project.setdefault("dialogue_register", 0)
        project.setdefault("dialogue_language", DEFAULT_DIALOGUE_LANGUAGE)
        project["dialogue_language"] = dialogue_language_selection(project["dialogue_language"])
        if story_recipe_spec(recipe["id"], recipe["version"]).get("dialogue_policy") == "forbidden":
            project["dialogue_register"] = 0
            project["dialogue_language"] = DEFAULT_DIALOGUE_LANGUAGE
        project.setdefault("diagnostics", story_diagnostics(project.get("document", {}).get("scenario"),
            clip_seconds=project.get("clip_seconds", 10), target_scene_count=project.get("scene_count", 6),
            recipe_id=recipe["id"]))
        if isinstance(project.get("job"), dict):
            project["job"].setdefault("draft", "")
            project["job"].setdefault("reasoning", "")
        if long_narrative.is_v2(project):
            project["long_status"] = long_narrative.status(project)
            project["diagnostics"] = [d for d in project["diagnostics"] if d["code"] not in {"clip_load", "language_residue", "estimated_clip_load"}]
            target = project["document"].get("selected_episode_id") or "outline"
            project["diagnostics"].extend(project_quality(project, target))
        return project

    def recipe_specs(self):
        available = {(item["id"], item["version"]) for item in self.recipes.list()}
        return [spec for spec in story_recipe_specs() if (spec["id"], spec["version"]) in available]

    def create(self, *, title="Nouvelle histoire", brief="", clip_seconds=10, scene_count=6,
               recipe_id=RECIPE_ID, recipe_version=RECIPE_VERSION,
               architect_model_id="", writer_model_id="", creation_mode="ideas",
               dialogue_register=0, dialogue_language=DEFAULT_DIALOGUE_LANGUAGE,
               narrative_format=DEFAULT_NARRATIVE_FORMAT, parent_story_id=None, long_options=None,
               workflow_mode=None, visual_universe="", target_seconds=None, prior_story=""):
        if not isinstance(title, str) or not title.strip() or len(title) > 160:
            raise ValueError("Donnez un nom à cette histoire (160 caractères maximum).")
        if not isinstance(brief, str):
            raise ValueError("Point de départ invalide.")
        if not isinstance(prior_story, str) or len(prior_story) > 60000:
            raise ValueError("L'épisode précédent doit tenir dans 60 000 caractères.")
        if type(clip_seconds) is not int or not 5 <= clip_seconds <= 15 or type(scene_count) is not int or not 1 <= scene_count <= 12:
            raise ValueError("Choisissez 1 à 12 micro-scènes de 5 à 15 secondes.")
        if creation_mode not in {"ideas", "script", "continuation", "adapt"}:
            raise ValueError("Mode de création inconnu.")
        narrative_format = narrative_format_selection(narrative_format)
        if long_options is not None:
            if narrative_format != "long" or self.long_recipes is None:
                raise ValueError("Le moteur long V2 n’est pas configuré pour ce parcours.")
            long_options = long_narrative.options(long_options)
            if creation_mode not in {"ideas", "adapt"}:
                raise ValueError("La V2 commence par des propositions ou par une histoire fournie.")
        if workflow_mode is not None and long_options is None:
            raise ValueError("Le parcours guidé nécessite le moteur long V2.")
        if long_options and "auto" in long_options.values() and workflow_mode is None:
            raise ValueError("Les choix automatiques nécessitent le parcours guidé.")
        if not isinstance(visual_universe, str) or len(visual_universe) > 1000:
            raise ValueError("Décris l’univers en 1 000 caractères maximum.")
        if target_seconds is not None and (type(target_seconds) is not int or not 10 <= target_seconds <= 2160):
            raise ValueError("La durée souhaitée doit être comprise entre 10 et 2 160 secondes.")
        if creation_mode == "adapt" and (long_options is None or not brief.strip()):
            raise ValueError("L’adaptation longue V2 nécessite une histoire fournie.")
        if narrative_format == "long" and long_options is None and creation_mode != "ideas":
            raise ValueError("Une histoire longue commence par un arc global ; utilise le mode Explorer des propositions.")
        if parent_story_id is not None and (
                not isinstance(parent_story_id, str)
                or not parent_story_id.startswith("story-") or len(parent_story_id) != 38):
            raise ValueError("Histoire parente invalide.")
        brief_limit = (_MAX_CONTINUATION_BRIEF_CHARS if creation_mode in {"continuation", "adapt"}
                       else _MAX_STANDARD_BRIEF_CHARS)
        if len(brief) > brief_limit:
            raise ValueError(f"Point de départ trop long ({brief_limit:,} caractères maximum).".replace(",", " "))
        if type(dialogue_register) is not int or not 0 <= dialogue_register <= 3:
            raise ValueError("Le registre des dialogues doit être compris entre 0 et 3.")
        dialogue_language = dialogue_language_selection(dialogue_language)
        if creation_mode in {"script", "continuation"} and not brief.strip():
            raise ValueError("Collez un script complet à suivre." if creation_mode == "script"
                             else "Collez au moins le dernier épisode ou un résumé de la saga à continuer.")
        if creation_mode == "script":
            dialogue_register = 0
        recipe = story_recipe_selection({"id": recipe_id, "version": recipe_version})
        if story_recipe_spec(recipe["id"], recipe["version"]).get("dialogue_policy") == "forbidden":
            dialogue_register = 0
            dialogue_language = DEFAULT_DIALOGUE_LANGUAGE
            if long_options is not None:
                long_options["narration"] = "visual"
        if not any((item["id"], item["version"]) == (recipe["id"], recipe["version"])
                   for item in self.recipes.list()):
            raise ValueError("Cette famille d’histoire n’est pas installée dans ce Lab.")
        for model_id in (architect_model_id, writer_model_id):
            if not isinstance(model_id, str) or len(model_id) > 300:
                raise ValueError("Identifiant de modèle LLM invalide.")
        document = dict(concepts=[], selected_id=None, scenario=None)
        if narrative_format == "long":
            document.update(series_outline=None, selected_episode_id=None,
                            episode_scenarios={}, episode_formats={})
        if creation_mode == "continuation":
            document.update(continuity=None, continuity_source=None)
        if parent_story_id:
            from panelforge.domain.story_continuity import carry_forward
            parent = self.store.get(parent_story_id)
            previous = parent.get("document", {}).get("scenario")
            if previous:
                document["prior_story_snapshot"] = deepcopy(previous)
                document["visual_state_inherited"] = carry_forward(previous)
        value = dict(project_id=f"story-{uuid4().hex}", title=title.strip(), brief=brief.strip(),
            clip_seconds=clip_seconds, scene_count=scene_count, document=document,
            revisions=[], turns=[], job=None, model_id=writer_model_id.strip(), recipe=recipe,
            architect_model_id=architect_model_id.strip(), writer_model_id=writer_model_id.strip(), diagnostics=[],
            creation_mode=creation_mode, dialogue_register=dialogue_register,
            dialogue_language=dialogue_language, narrative_format=narrative_format,
            parent_story_id=parent_story_id)
        if prior_story.strip():
            value["prior_story"] = prior_story.strip()
        if long_options is not None:
            value.update(narrative_engine=deepcopy(long_narrative.ENGINE), long_options=long_options)
            value.update(visual_universe=visual_universe.strip(), target_seconds=target_seconds,
                         narrative_preferences=deepcopy(long_options))
            document.update(episode_states={}, episode_provenance={}, reviews={})
            if workflow_mode is not None:
                value["workflow"] = new_workflow(workflow_mode)
            value["llm_usage"] = dict(calls=0, elapsed_ms=0, repair_calls=0, since=_now(), earlier_calls_unknown=False)
        return self._normalize(self.store.save(value))

    def get(self, project_id):
        with self._lock:
            project = self._normalize(self.store.get(project_id))
            job = project.get("job")
            if job and job["status"] in {"running", "cancelling"} and project_id not in self._active:
                job.update(status="interrupted", error="Le service a été interrompu. La dernière version et le brouillon sont conservés.")
                if project.get("workflow"):
                    project["workflow"].update(status="blocked", message="Le service s’est arrêté. Reprends l’étape ; les textes sont conservés.")
                project = self.store.save(project)
            if job and job.get("status") == "failed" and job.get("draft") and long_narrative.is_v2(project):
                job = project["job"] = dict(project["job"])
                try:
                    _reply, incoming = self._parse_draft(project, self._received_draft(job))
                    job.update(can_revalidate=True, revalidation_error=None)
                    preview = deepcopy(project)
                    if incoming:
                        long_narrative.apply_document(preview, incoming)
                    job["draft_diagnostics"] = project_quality(preview, long_narrative.scope(project))
                    job["draft_preview"] = (incoming or {}).get("scenario")
                except (ValueError, TypeError, KeyError) as error:
                    job.update(can_revalidate=False, revalidation_error=str(error))
                    job["draft_diagnostics"] = getattr(error, "issues", [story_contracts.issue("draft_invalid", "response", str(error))])
                    try:
                        decoded, _ = decode_response(strip_markdown_fence(self._received_draft(job).strip()))
                        if not isinstance(decoded, dict):
                            raise ValueError("Un brouillon narratif doit être un objet JSON.")
                        if story_contracts.structured(project):
                            decoded = story_contracts.canonical_response(project, decoded)
                        job["draft_preview"] = decoded.get("scenario")
                        job["draft_diagnostics"] += quality_issues(project, scenario=decoded.get("scenario"),
                            state=decoded.get("episode_state"), target=long_narrative.scope(project))
                    except (ValueError, KeyError, TypeError, IndexError):
                        job["draft_preview"] = None
            return project

    @staticmethod
    def _received_draft(job):
        repair = job.get("format_repair") or {}
        if repair.get("content_preserved") and repair.get("draft"):
            return repair["draft"]
        return job.get("draft") or ""

    def _editable(self, project_id, expected_version):
        project = self.get(project_id)
        if project_id in self._active:
            raise StoryConflict("Un échange est déjà en cours pour cette histoire.")
        if type(expected_version) is not int or expected_version != project["version"]:
            raise StoryConflict("Cette histoire a changé dans un autre onglet. Rechargez-la avant de continuer.")
        return project

    def _snapshot(self, project, label, *, model_id=None, recipe_revision=None, call_id=None):
        recipe = story_recipe_selection(project.get("recipe"))
        project["revisions"].append(dict(revision=len(project["revisions"]) + 1, created_at=_now(), label=label,
            document=deepcopy(project["document"]), model_id=model_id, recipe=deepcopy(recipe),
            recipe_revision=recipe_revision, call_id=call_id))
        scenario = project["document"]["scenario"]
        episode_format = self._active_episode_format(project)
        project["diagnostics"] = story_diagnostics(scenario, clip_seconds=episode_format["clip_seconds"],
            target_scene_count=episode_format["scene_count"], recipe_id=recipe["id"])
        if long_narrative.is_v2(project):
            project["revisions"][-1]["narrative_engine"] = deepcopy(long_narrative.ENGINE)
            project["revisions"][-1]["long_options"] = deepcopy(project["long_options"])
            if model_id:
                project["revisions"][-1]["editorial_fingerprint"] = project["job"]["editorial_fingerprint"]
            project["diagnostics"] = [item for item in project["diagnostics"] if item["code"] != "scene_count"]
            target = project["document"].get("selected_episode_id") or "outline"
            project["diagnostics"].extend(project_quality(project, target))
            project["long_status"] = long_narrative.status(project)
        chosen = next((c for c in project["document"]["concepts"] if c["id"] == project["document"]["selected_id"]), None)
        outline = project["document"].get("series_outline")
        if outline or scenario or chosen:
            project["title"] = (outline or scenario or chosen)["title"][:160]

    @staticmethod
    def _active_episode_format(project):
        document = project.get("document") or {}
        selected = document.get("selected_episode_id")
        value = (document.get("episode_formats") or {}).get(selected, {})
        return {
            "scene_count": value.get("scene_count", project["scene_count"]),
            "clip_seconds": value.get("clip_seconds", project["clip_seconds"]),
        }

    @staticmethod
    def _series_history(project):
        """Compact actual history; generated episodes override the planned arc without another LLM call."""
        document = project.get("document") or {}
        outline = document.get("series_outline") or {}
        selected = document.get("selected_episode_id")
        ordered = [item["id"] for item in outline.get("episodes", [])]
        before = ordered[:ordered.index(selected)] if selected in ordered else []
        actual = document.get("episode_scenarios") or {}
        result = []
        for episode_id in before:
            scenario = actual.get(episode_id)
            if not scenario:
                continue
            result.append({
                "episode_id": episode_id,
                "title": scenario["title"],
                "logline": scenario["logline"],
                "visible_outcomes": [scene["ending_state"][:800] for scene in scenario["scenes"]],
                "latest_ending": scenario["scenes"][-1]["ending_state"][:1500],
                "characters": [{key: character[key] for key in ("id", "name", "description")}
                               for character in scenario["characters"]],
            })
        return result

    @staticmethod
    def _validate_series_cast(outline, scenario):
        by_id = {item["id"]: item for item in outline["characters"]}
        by_name = {item["name"].strip().casefold(): item for item in outline["characters"]}
        for character in scenario["characters"]:
            canonical = by_id.get(character["id"])
            if canonical and character["name"].strip().casefold() != canonical["name"].strip().casefold():
                raise ValueError(
                    f"Le personnage {character['id']} doit conserver le nom {canonical['name']} dans tous les épisodes."
                )
            named = by_name.get(character["name"].strip().casefold())
            if named and character["id"] != named["id"]:
                raise ValueError(
                    f"Le personnage récurrent {character['name']} doit conserver l’identifiant {named['id']}."
                )

    def select(self, project_id, concept_id, expected_version):
        with self._lock:
            project = self._editable(project_id, expected_version)
            document = project["document"]
            if concept_id not in {c["id"] for c in document["concepts"]}:
                raise ValueError("Choisissez une des propositions disponibles.")
            if document["selected_id"] == concept_id:
                return project
            document.update(selected_id=concept_id, scenario=None)
            if project.get("narrative_format") == "long":
                document.update(series_outline=None, selected_episode_id=None,
                                episode_scenarios={}, episode_formats={})
                if long_narrative.is_v2(project):
                    document.update(episode_states={}, episode_provenance={}, reviews={})
            self._snapshot(project, "Choix de l’histoire")
            return self.store.save(project)

    def select_series_episode(self, project_id, episode_id, expected_version, *, scene_count, clip_seconds):
        with self._lock:
            project = self._editable(project_id, expected_version)
            if project.get("narrative_format") != "long":
                raise ValueError("Ce projet n’est pas une histoire longue.")
            document = project["document"]
            outline = document.get("series_outline")
            if not outline or episode_id not in {item["id"] for item in outline["episodes"]}:
                raise ValueError("Épisode de l’arc introuvable.")
            existing = (document.get("episode_scenarios") or {}).get(episode_id)
            if type(scene_count) is not int or not 1 <= scene_count <= 12:
                raise ValueError("Choisissez 1 à 12 micro-scènes pour cet épisode.")
            if type(clip_seconds) is not int or not 5 <= clip_seconds <= 15:
                raise ValueError("Choisissez des clips de 5 à 15 secondes.")
            previous_format = (document.get("episode_formats") or {}).get(episode_id)
            requested_format = {"scene_count": scene_count, "clip_seconds": clip_seconds}
            if long_narrative.is_v2(project) and previous_format != requested_format:
                raise ValueError("Le budget V2 est fixé à la création et relu avec l’arc ; conservez ce plafond et cette durée.")
            if existing and previous_format and previous_format != requested_format:
                raise ValueError("Le format d’un épisode déjà développé ne peut pas changer sans réécriture.")
            document.setdefault("episode_formats", {})[episode_id] = requested_format
            document["selected_episode_id"] = episode_id
            document["scenario"] = deepcopy(existing) if existing else None
            self._snapshot(project, f"Ouverture de {episode_id}")
            return self.store.save(project)

    def edit_continuity(self, project_id, expected_version, visual_continuity):
        from panelforge.domain.story_continuity import normalize
        with self._lock:
            project = self._editable(project_id, expected_version)
            doc = project["document"]
            scenario = deepcopy(doc.get("scenario"))
            if not scenario:
                raise ValueError("Développe d'abord le scénario pour organiser sa continuité.")
            target = doc.get("selected_episode_id")
            reviewed = bool(long_narrative.is_v2(project) and long_narrative.review_current(project, target))
            approvals = (project.get("workflow") or {}).get("approvals", {})
            approved = bool(reviewed and approvals.get(target) == long_narrative.source_hash(project, target))
            scenario["visual_continuity"] = normalize(visual_continuity, scenario)
            scenario["visual_continuity"].pop("warnings", None)
            doc["scenario"] = scenario
            if target:
                doc["episode_scenarios"][target] = deepcopy(scenario)
            if reviewed:
                # The author validates this visual ledger; the playable text is
                # untouched. Keep its review without spending another model call.
                doc["reviews"][target]["source_hash"] = long_narrative.source_hash(project, target)
                doc["reviews"][target]["visual_continuity_edited_by_author"] = True
                if approved:
                    approvals[target] = long_narrative.source_hash(project, target)
            self._snapshot(project, "Continuité visuelle ajustée par l'auteur")
            return self.store.save(project)

    def edit_scene(self, project_id, index, expected_version, changes):
        with self._lock:
            project = self._editable(project_id, expected_version)
            scenario = deepcopy(project["document"].get("scenario"))
            if scenario is None:
                raise ValueError("Développez d’abord le scénario.")
            if type(index) is not int or not 0 <= index < len(scenario["scenes"]):
                raise ValueError("Micro-scène introuvable.")
            allowed = {"title", "opening_state", "action", "dialogue", "ending_state",
                       "relationship_state", "appearance_state", "sexual_state", "visual_transition"}
            if not isinstance(changes, dict) or not changes or set(changes) - allowed:
                raise ValueError("Champs de micro-scène inconnus.")
            current_scene = scenario["scenes"][index]
            transition_became_stale = (
                "visual_transition" not in changes
                and "visual_transition" in current_scene
                and any(field in changes and changes[field] != current_scene[field]
                        for field in ("opening_state", "action", "ending_state"))
            )
            if transition_became_stale:
                current_scene.pop("visual_transition")
            current_scene.update(deepcopy(changes))
            recipe = story_recipe_selection(project["recipe"])
            project["document"]["scenario"] = validate_scenario(scenario, recipe["id"], recipe["version"])
            if long_narrative.is_v2(project):
                long_narrative.fabrication_scenario(project, require_review=False)
            if project.get("narrative_format") == "long" and project["document"].get("selected_episode_id"):
                project["document"].setdefault("episode_scenarios", {})[
                    project["document"]["selected_episode_id"]] = deepcopy(project["document"]["scenario"])
            if project.get("workflow"):
                project["workflow"].update(status="paused", wait_target=None)
                project["workflow"]["repairs"].pop(project["document"].get("selected_episode_id"), None)
            self._snapshot(project, f"Édition manuelle de la scène {index + 1}")
            project["turns"].append(dict(role="assistant",
                text=f"La scène {index + 1} a été modifiée manuellement sans appel LLM.", created_at=_now()))
            return self.store.save(project)

    def restore(self, project_id, revision, expected_version):
        with self._lock:
            project = self._editable(project_id, expected_version)
            if type(revision) is not int or not 1 <= revision <= len(project["revisions"]):
                raise ValueError("Version d’histoire introuvable.")
            project["document"] = deepcopy(project["revisions"][revision - 1]["document"])
            if long_narrative.is_v2(project):
                project["long_options"] = deepcopy(project["revisions"][revision - 1].get("long_options", project["long_options"]))
                if project.get("workflow"):
                    project["workflow"].update(status="paused", approvals={}, repairs={}, wait_target=None)
            self._snapshot(project, f"Reprise de la version {revision}")
            project["turns"].append(dict(role="assistant", text=f"Version {revision} réappliquée. Les échanges suivants partiront de ce document.", created_at=_now()))
            return self.store.save(project)

    def start(self, project_id, *, operation, instruction, model_id=None, expected_version, request_id,
              feedback_target=None, review_unit_ids=None, workflow_step=False):
        if operation not in {"ideas", "outline", "develop", "script", "revise"} | long_narrative.EXTRA_OPERATIONS:
            raise ValueError("Action d’écriture inconnue.")
        if not isinstance(instruction, str) or len(instruction) > 12000 or (operation in {"revise", "discuss"} and not instruction.strip()):
            raise ValueError("Écrivez une demande de 1 à 12 000 caractères.")
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 100:
            raise ValueError("Identifiant de demande invalide.")
        with self._lock:
            project = self.get(project_id)
            if project.get("job", {}) and project["job"]["request_id"] == request_id:
                return project
            project = self._editable(project_id, expected_version)
            v2 = long_narrative.is_v2(project)
            story_attempts.archive_job(project)
            if feedback_target:
                project["job"] = {**(project.get("job") or {}), "feedback_target": feedback_target}
            elif project.get("job"):
                project["job"].pop("feedback_target", None)
            if not v2 and operation in long_narrative.EXTRA_OPERATIONS:
                raise ValueError("Cette action appartient au moteur long V2.")
            if v2:
                long_narrative.check_start(project, operation)
            if operation == "ideas" and project["creation_mode"] not in {"ideas", "continuation"}:
                raise ValueError("Ce projet suit un script fourni et ne génère pas de pistes.")
            if operation == "script" and project["creation_mode"] != "script":
                raise ValueError("Ce projet n’est pas configuré pour suivre un script.")
            if operation == "outline":
                if project.get("narrative_format") != "long":
                    raise ValueError("La construction d’un arc est réservée aux histoires longues.")
                if not project["document"]["selected_id"] and not (v2 and project["creation_mode"] == "adapt"):
                    raise ValueError("Sélectionnez une histoire avant de construire son arc.")
            if operation == "develop":
                if not project["document"]["selected_id"] and not (v2 and (project["creation_mode"] == "adapt" or project.get("workflow"))):
                    raise ValueError("Sélectionnez une histoire avant de la développer.")
                if project.get("narrative_format") == "long" and (
                        not project["document"].get("series_outline")
                        or not project["document"].get("selected_episode_id")):
                    raise ValueError("Construisez l’arc puis choisissez un épisode à développer.")
            if operation == "revise" and not (
                    project["document"]["concepts"] or project["document"]["scenario"]
                    or project["document"].get("series_outline")):
                raise ValueError("Créez d’abord une proposition ou structurez le script fourni.")
            revises_outline = (operation == "revise" and project.get("narrative_format") == "long"
                               and project["document"].get("series_outline")
                               and not project["document"].get("scenario"))
            role = "architect_model_id" if operation in {"ideas", "outline"} or revises_outline else "writer_model_id"
            if v2 and ("outline" in operation or operation.startswith("review_")):
                role = "architect_model_id"
            if operation == "compose" or (feedback_target and feedback_target["unit_id"] == "outline"):
                role = "architect_model_id"
            chosen_model = model_id.strip() if isinstance(model_id, str) else project.get(role, "")
            if not chosen_model:
                chosen_model = project.get("model_id", "")
            if not chosen_model or len(chosen_model) > 300:
                raise ValueError("Choisissez un modèle LLM pour cette étape.")
            # Read active editorial instructions now; this call retains its snapshot.
            recipe = story_recipe_selection(project["recipe"])
            if v2 and self.long_recipes is None:
                raise ValueError("La recette longue V2 doit être configurée dans le lanceur.")
            package = self.long_recipes.snapshot() if v2 else self.recipes.get(recipe["id"], recipe["version"])
            label = {"ideas": "Propose une histoire à partir de mon intention.",
                     "outline": "Construis l’arc global en quatre épisodes autoportants et reliés.",
                     "develop": "Développe l’histoire sélectionnée en scénario complet.",
                     "script": "Structure fidèlement le script fourni sans omettre ni réécrire ses dialogues.",
                     "revise": instruction.strip(),
                     "revise_outline": "Révise le contrat et l’arc selon mon retour.",
                     "review_outline": "Relis le contrat et l’arc global.",
                     "review_episode": "Relis cette unité et son canon.",
                     "repair_outline": "Corrige les remarques de la relecture de l’arc en une passe.",
                     "repair_episode": "Corrige les remarques de la relecture de cette unité en une passe.",
                     "compose": "Imagine une histoire et sa progression à partir de mon idée.",
                     "edit_outline": "Vérifie l’histoire et apporte les petites corrections utiles.",
                     "review_block": "Vérifie ces séquences et leurs raccords.", "discuss": instruction.strip()}[operation]
            if v2 and operation == "outline":
                label = "Construis le contrat et l’architecture longue selon le format choisi."
            turn_text = instruction.strip() or label
            previous_job = project.get("job") or {}
            duplicate_failed_retry = (
                previous_job.get("status") in {"failed", "interrupted", "cancelled"}
                and previous_job.get("operation") == operation
                and project["turns"]
                and project["turns"][-1].get("role") == "user"
                and (project["turns"][-1].get("text") or "").strip() == turn_text
            )
            if not duplicate_failed_retry:
                turn = dict(role="user", text=turn_text, created_at=_now())
                if feedback_target:
                    turn.update(target=deepcopy(feedback_target), feedback_status="pending", request_id=request_id,
                                question=operation == "discuss")
                project["turns"].append(turn)
            elif feedback_target:
                project["turns"][-1].update(target=deepcopy(feedback_target), feedback_status="pending",
                                            request_id=request_id, question=operation == "discuss")
            project[role] = chosen_model
            project["model_id"] = chosen_model
            project["job"] = dict(request_id=request_id, status="running", operation=operation, started_at=_now(),
                phase="Préparation de l’écriture…", error=None, draft="", reasoning="", model_role=role,
                recipe=deepcopy(recipe), recipe_revision=package["revision"], call_id=None,
                instruction=instruction.strip())
            if feedback_target:
                project["job"]["feedback_target"] = deepcopy(feedback_target)
            if operation == "review_block":
                identities = review_unit_ids or [project["document"]["selected_episode_id"]]
                if not isinstance(identities, list) or not 1 <= len(identities) <= 2 or len(set(identities)) != len(identities):
                    raise ValueError("Une relecture groupée porte sur une ou deux séquences distinctes.")
                if any(identity not in project["document"]["episode_scenarios"] for identity in identities):
                    raise ValueError("Rédigez les séquences avant leur relecture.")
                project["job"]["review_unit_ids"] = identities
            if project.get("workflow") and not workflow_step:
                project["workflow"].update(status="paused", pause_requested=False)
            if v2:
                project["job"].update(narrative_engine=deepcopy(long_narrative.ENGINE),
                                      response_contract_version=story_contracts.VERSION,
                                      editorial_fingerprint=package["fingerprint"],
                                      narrative_input_hash=long_narrative.input_hash(project))
                if project.get("workflow"):
                    flow = project["workflow"]
                    flow["budget_calls"] = flow.get("budget_calls", flow.get("calls", 0)) + 1
                    flow["calls"] = flow.get("calls", 0) + 1
            cancel = Event()
            self._active[project_id] = cancel
            try:
                project = self.store.save(project)
                worker = Thread(target=self._run, args=(deepcopy(project), package, cancel), daemon=True,
                                name=f"story-{project_id[-8:]}")
                worker.start()
            except BaseException:
                self._active.pop(project_id, None)
                raise
            return project

    def retry(self, project_id, expected_version, model_id=None):
        """Retry exactly the failed scope; never reinterpret a local comment as a global rewrite."""
        with self._lock:
            project = self._editable(project_id, expected_version)
            job = deepcopy(project.get("job") or {})
            if job.get("status") not in {"failed", "interrupted", "cancelled"}:
                raise ValueError("Aucune étape en échec à reprendre.")
            if long_narrative.is_v2(project) and job.get("narrative_input_hash") not in {None, long_narrative.input_hash(project)}:
                raise ValueError("Le document a changé depuis cet appel. Adresse un nouveau retour à la version actuelle.")
            if project.get("workflow"):
                project["workflow"].update(status="paused" if job["operation"] == "discuss" else "running",
                                           pause_requested=False, wait_target=None, budget_calls=0)
                project = self.store.save(project)
            instruction = job.get("instruction")
            if instruction is None:
                instruction = next((turn["text"] for turn in reversed(project["turns"]) if turn["role"] == "user"), "")
            try:
                return self.start(project_id, operation=job["operation"], instruction=instruction,
                    expected_version=project["version"], request_id=str(uuid4()), model_id=model_id,
                    feedback_target=job.get("feedback_target"), review_unit_ids=job.get("review_unit_ids"),
                    workflow_step=bool(project.get("workflow")))
            except Exception as error:
                if project.get("workflow"):
                    self.workflow._stop(self.store.get(project_id), "blocked", str(error))
                raise

    def cancel(self, project_id):
        with self._lock:
            project = self.get(project_id)
            event = self._active.get(project_id)
            if project.get("workflow"):
                project["workflow"].update(status="paused", pause_requested=True)
            if event:
                event.set()
                project["job"].update(status="cancelling", phase="Annulation demandée ; attente du moteur LLM…")
            if event or project.get("workflow"):
                project = self.store.save(project)
            return project

    def _request(self, project, package):
        if long_narrative.is_v2(project):
            language = project.get("dialogue_language", DEFAULT_DIALOGUE_LANGUAGE)
            register = project.get("dialogue_register", 0)
            return long_story_request(project, package, _dialogue_language_policy(language),
                                      _dialogue_register_policy(register, language) if register else "")
        operation = project["job"]["operation"]
        recipe = story_recipe_selection(project["recipe"])
        has_scenario = bool(project["document"]["scenario"])
        has_series_outline = bool(project["document"].get("series_outline"))
        long_story = project.get("narrative_format") == "long"
        field = {"ideas": "plan.system", "outline": "plan.system", "develop": "writer.system", "script": "writer.system",
                 "revise": "revision.system"}[operation]
        seen = []
        document = deepcopy(project["document"])
        conversation = _dedupe_conversation(project["turns"][-16:])
        if operation == "ideas":
            # New pitches start from the author's brief and feedback. Previous
            # generated jokes/style are references to avoid, not a fresh brief.
            seen = [{"title": c["title"], "hook": c["hook"]} for c in document["concepts"]]
            source_continuity = (document.get("continuity_source") or document.get("continuity")
                                 if project["creation_mode"] == "continuation" else None)
            document = dict(concepts=[], selected_id=None, scenario=None)
            if source_continuity:
                document["continuity"] = source_continuity
            conversation = [turn for turn in conversation if turn["role"] == "user"]
            for other in self.store.list(8):
                if other["project_id"] == project["project_id"]:
                    continue
                try:
                    previous = self._normalize(self.store.get(other["project_id"]))
                    if previous["recipe"] != recipe:
                        continue
                    seen.extend({"title": c["title"], "hook": c["hook"]} for c in previous["document"]["concepts"])
                except (OSError, ValueError):
                    continue
        elif project["creation_mode"] == "continuation":
            # continuity_source is retained for alternative pitches and restore,
            # but the active cumulative memory is sufficient for the LLM.
            document.pop("continuity_source", None)
        episode_format = self._active_episode_format(project)
        target_scene_count = episode_format["scene_count"]
        clip_seconds = episode_format["clip_seconds"]
        source_dialogues = extract_script_dialogue_cues(project["brief"]) if operation == "script" else []
        continuation = project["creation_mode"] == "continuation"
        if operation == "outline" or (
                operation == "revise" and long_story and has_series_outline and not has_scenario):
            contract_notes = (
                f"MODE HISTOIRE LONGUE. JSON strict conforme au contrat : un seul arc global contenant exactement "
                f"{SERIES_EPISODE_COUNT} épisodes ordonnés, sans micro-scènes. Chaque épisode pose une question locale, "
                "enchaîne des étapes causales visibles, apporte un payoff local satisfaisant et transmet un état concret "
                "au suivant. Les quatre épisodes forment néanmoins une seule histoire globale. Les personnages de série "
                "gardent exactement leurs identifiants, noms et identités visuelles."
            )
        elif operation == "script":
            contract_notes = (
                "MODE SCRIPT FIDÈLE. Le champ brief est le script source complet et prévaut sur le ton éditorial par défaut. "
                "Conserver tous ses événements, sa fin et l’intégralité de ses dialogues mot pour mot, dans le même ordre et avec les mêmes locuteurs. "
                "Chaque entrée source_dialogues possède un dialogue_id autoritaire. Recopier son text sans y ajouter une indication comme (Voix off). "
                "Stocker séparément le canal dans delivery (spoken, voice_over, off_screen, thought ou mediated) et l’indication originale facultative dans delivery_note. "
                f"La sortie doit contenir exactement {target_scene_count} micro-scène{'s' if target_scene_count > 1 else ''} "
                f"de {clip_seconds} secondes. Les titres, numéros, scènes ou rubriques du brief sont des événements source, pas un découpage imposé. "
                "Regrouper plusieurs événements successifs dans une même micro-scène lorsque nécessaire. Condenser uniquement leur mise en scène et leur description : "
                "ne supprimer aucun événement, ne paraphraser aucun dialogue et ne changer ni leur ordre ni la fin. "
                "Ne jamais augmenter le nombre de micro-scènes pour suivre le nombre de rubriques du brief. JSON strict conforme au contrat. "
                "1–12 personnages, 1–8 décors ; tous les identifiants référencés doivent exister."
            )
        elif continuation:
            phase = "après le nouvel épisode" if operation == "develop" or has_scenario else "avant le nouvel épisode"
            contract_notes = (
                f"MODE SUITE D’UNE HISTOIRE. JSON strict conforme au contrat, y compris continuity qui décrit la saga {phase}. "
                "Le brief peut contenir plusieurs épisodes : les plus anciens donnent le contexte cumulatif et la fin du dernier "
                "épisode est le point de départ immédiat. Ne redécouvre pas un fait déjà acquis, ne contredis pas une connaissance "
                "ou une relation établie et n’invente pas hors champ une nouvelle preuve, un nouvel objet décisif ou une autorité de secours. "
                "Toute nouveauté indispensable est déclarée dans continuation_plan.introduced_elements puis préparée avant son usage. "
                "Chaque piste suit une chaîne causale lisible carry_over → obstacle → payoff. Évite d’empiler plusieurs solutions nouvelles. "
                f"Tout scenario renvoyé contient exactement {target_scene_count} micro-scène"
                f"{'s' if target_scene_count > 1 else ''} de {clip_seconds} secondes ; 1–12 personnages et 1–8 décors."
            )
        elif operation == "develop" or (operation == "revise" and has_scenario):
            contract_notes = (
                f"JSON strict conforme au contrat. Tout scenario renvoyé contient exactement {target_scene_count} micro-scène"
                f"{'s' if target_scene_count > 1 else ''} de {clip_seconds} secondes dans scenario.scenes ; "
                "1–12 personnages, 1–8 décors. Tous les identifiants référencés doivent exister. "
                "En révision, discussion_only:true ne modifie rien et ne renvoie pas scenario ; sinon renvoyer le document entier. "
                "Le document courant et selected_id font foi."
            )
        else:
            contract_notes = (
                "JSON strict conforme au contrat. Une seule proposition, identifiée concept-1 ; "
                "1–12 personnages, 1–8 décors. Tous les identifiants référencés doivent exister. "
                "En révision, discussion_only:true ne modifie rien ; sinon renvoyer le document entier. "
                "Le document courant et selected_id font foi."
            )
        context = dict(operation=operation, creation_mode=project["creation_mode"],
            narrative_format=project.get("narrative_format", DEFAULT_NARRATIVE_FORMAT),
            brief=project["brief"], clip_seconds=clip_seconds,
            target_scene_count=target_scene_count, target_clip_seconds=clip_seconds, current_document=document,
            conversation=conversation, recent_concepts_to_avoid=seen[:24],
            response_contract=response_contract(operation, has_scenario, recipe["id"], recipe["version"],
                                                creation_mode=project["creation_mode"],
                                                narrative_format=project.get("narrative_format", DEFAULT_NARRATIVE_FORMAT),
                                                has_series_outline=has_series_outline),
            contract_notes=contract_notes)
        if long_story and has_series_outline:
            context["selected_episode_id"] = document.get("selected_episode_id")
            context["actual_previous_episodes"] = self._series_history(project)
            # The compact actual history above is authoritative. Avoid resending every
            # prior detailed scenario and consuming the long-context budget repeatedly.
            context["current_document"].pop("episode_scenarios", None)
            if operation == "develop" or (operation == "revise" and has_scenario):
                selected_episode = document.get("selected_episode_id")
                outline = deepcopy(document.get("series_outline") or {})
                outline["episodes"] = [
                    item for item in outline.get("episodes", []) if item.get("id") == selected_episode
                ]
                context["current_document"].pop("concepts", None)
                context["current_document"]["series_outline"] = outline
        dialogue_allowed = story_recipe_spec(recipe["id"], recipe["version"]).get("dialogue_policy") != "forbidden"
        dialogue_language = dialogue_language_selection(project.get("dialogue_language", DEFAULT_DIALOGUE_LANGUAGE))
        if dialogue_allowed:
            context["dialogue_language"] = dialogue_language
            context["dialogue_language_label"] = dialogue_language_label(dialogue_language)
        if source_dialogues:
            context["source_dialogues"] = source_dialogues
        outline_stage = long_story and (operation == "outline" or (
            operation == "revise" and has_series_outline and not has_scenario
        ))
        if outline_stage:
            system_prompt = _long_outline_system_prompt(recipe["id"], dialogue_language)
        elif operation == "ideas":
            system_prompt = _ideas_system_prompt(package["fields"][field])
        else:
            system_prompt = package["fields"][field]
        if operation == "revise":
            # Archived recipe versions remain immutable; their former selection
            # wording must not reintroduce several proposals into a new call.
            for old, new in (("leurs trois concepts complets", "la proposition complète"),
                             ("trois concepts avant développement", "une proposition avant développement"),
                             ("concept-1, concept-2 et concept-3", "concept-1"),
                             ("concept-1, concept-2 ou concept-3", "concept-1")):
                system_prompt = system_prompt.replace(old, new)
        if operation == "script":
            system_prompt += (
                "\n\nMODE SCRIPT FIDÈLE POUR CET APPEL : le brief contient un script complet. Il est la source narrative autoritaire "
                "et remplace toute demande de développer une piste ou d’appliquer le ton par défaut. N’omets, ne reformule et n’invente aucun dialogue. "
                f"Produis exactement {target_scene_count} micro-scène{'s' if target_scene_count > 1 else ''} de {clip_seconds} secondes. "
                "Les sections du script sont des événements à regrouper, pas des micro-scènes obligatoires. Préserve mot pour mot tous les dialogues, "
                "dans leur ordre, ainsi que chaque événement et la fin ; compresse le découpage et les descriptions plutôt que le contenu. "
                "Pour chaque source_dialogues, conserve dialogue_id et text. delivery et delivery_note portent les indications de voix off, hors champ, pensée ou média ; "
                "ces indications ne doivent jamais être ajoutées au début de text."
            )
        elif operation == "revise" and not has_scenario and not has_series_outline:
            system_prompt += "\n\nRenvoie uniquement l’histoire ajustée dans concepts, une seule proposition identifiée concept-1."
        if operation == "develop" or (operation == "revise" and has_scenario):
            system_prompt += (
                f"\n\nFORMAT DE L’ÉPISODE : scenario.scenes contient exactement {target_scene_count} micro-scène"
                f"{'s' if target_scene_count > 1 else ''} de {clip_seconds} secondes. Ce nombre est obligatoire, même si le contenu "
                "doit être regroupé ou densifié. Une discussion_only peut ne renvoyer aucun scénario."
            )
        if long_story and (operation == "develop" or (operation == "revise" and has_scenario)):
            selected_episode = document.get("selected_episode_id")
            system_prompt += (
                f"\n\nHISTOIRE LONGUE — DÉVELOPPEMENT DE {selected_episode} UNIQUEMENT : le nombre demandé concerne "
                "cet épisode, jamais l’histoire globale. Montre toutes les actions indispensables à sa compréhension ; aucun "
                "événement causal majeur ne se produit hors champ entre deux micro-scènes. Chaque micro-scène part de l’état "
                "final réellement visible de la précédente et produit un changement principal lisible. Résous la promesse "
                "locale de l’épisode sans anticiper les payoffs des épisodes suivants. actual_previous_episodes décrit ce qui "
                "s’est réellement passé et prévaut sur l’arc planifié en cas d’écart. Réutilise les identifiants et noms stables "
                "des personnages récurrents de series_outline. Si l'ouverture planifiée suppose un incident causal absent de "
                "actual_previous_episodes, répare-la et montre cet incident dans l'épisode. Calibre les actions pour la durée "
                "totale disponible ; ne répartis pas mécaniquement les beats sur les clips et n'impose pas une action naturellement "
                "plus longue que le temps disponible. La dernière micro-scène accomplit visiblement le payoff local au lieu de "
                "seulement l'annoncer dans ending_state."
            )
        if continuation:
            system_prompt += (
                "\n\nMODE SUITE D’UNE HISTOIRE — MÉMOIRE CUMULATIVE : considère l’intégralité du brief comme le canon de la saga, "
                "même si le dernier épisode avait lui-même des antécédents. Les épisodes anciens restent un contexte résumé ; l’état final "
                "du dernier épisode est la frontière de reprise exacte et sa version détaillée prévaut sur un résumé antérieur en cas d’écart. "
                "continuity doit rester court, cumulatif et exploitable par le prochain "
                "épisode : faits acquis, états actuels des personnages, conflits ouverts et éléments encore disponibles. "
                "Pendant les propositions, continuity résume uniquement le passé fourni, jamais les événements spéculatifs des pistes. "
                "Pendant le développement ou la révision du scénario, mets continuity à jour après les conséquences du nouvel épisode. "
                "Ne refais pas une révélation déjà vécue. Une résolution doit découler d’un élément déjà établi ou être introduite visiblement "
                "avant son payoff. continuation_plan rend cette causalité explicite pour chaque proposition."
            )
        if operation in {"develop", "script"} or (operation == "revise" and has_scenario):
            system_prompt += (
                "\n\nTRANSITIONS VISUELLES : visual_transition est optionnel. Mets-le à null ou omets-le lorsqu’il n’y a "
                "aucune transformation visuelle importante et persistante dans la micro-scène. Sinon renvoie exactement "
                "{before, trigger, visible_change, after} : le même clip doit rendre visibles l’état initial, le déclencheur, "
                "le changement observable puis l’état final, sans commencer après la transformation."
            )
            if operation == "script":
                system_prompt += (
                    " En mode Script fidèle, ne renseigne visual_transition que si cette transformation est explicitement "
                    "racontée par le script ; n’invente ni déclencheur ni résultat."
                )
            if recipe["id"] == SILENT_CATS_RECIPE_ID:
                system_prompt += (
                    " Dans cette famille muette, visual_transition est obligatoire pour toute guérison ou autre changement "
                    "important d’état physique, d’objet, de tenue ou de salissure, et doit rester compréhensible sans paroles."
                )
        if recipe["id"] == RECIPE_ID and project["creation_mode"] != "script" and not outline_stage:
            system_prompt += "\n\n" + _fruit_audio_first_policy()
        if dialogue_allowed and not outline_stage:
            system_prompt += "\n\n" + _dialogue_language_policy(
                dialogue_language, script=operation == "script",
                revising=operation == "revise" and has_scenario,
            )
        dialogue_register = project.get("dialogue_register", 0)
        if story_recipe_spec(recipe["id"], recipe["version"]).get("dialogue_policy") == "forbidden":
            dialogue_register = 0
        if operation in {"develop", "revise"} and dialogue_register:
            context["dialogue_register"] = dialogue_register
            system_prompt += "\n\n" + _dialogue_register_policy(dialogue_register, dialogue_language)
            if operation == "revise":
                system_prompt += (
                    " Les dialogues déjà validés restent inchangés sauf si la demande de révision vise explicitement "
                    "leur formulation ; applique surtout ce registre aux nouvelles répliques."
                )
        return CompletionRequest(model_id=project["model_id"], system_prompt=system_prompt,
            user_prompt=json.dumps(context, ensure_ascii=False), temperature=.8 if operation == "ideas" else (.35 if operation == "script" else .65),
            max_tokens=24000, include_reasoning=True,
            operation_id=f"{recipe['id']}.{operation}@{recipe['version']}",
            trace_context=dict(project_id=project["project_id"], stage=f"story_{operation}", cookbook_id=recipe["id"],
                               cookbook_version=recipe["version"], recipe_revision=package["revision"], turn_id=project["job"]["request_id"]))

    def _parse_draft(self, project, raw):
        try:
            if long_narrative.is_v2(project):
                data, _normalizations = decode_response(strip_markdown_fence(raw.strip()))
            else:
                data = decode_story_json(strip_markdown_fence(raw.strip()))
        except StoryJsonError:
            raise
        except ValueError as error:
            raise ValueError(
                "Le modèle n’a pas renvoyé un JSON valide. La dernière version et le brouillon sont conservés."
            ) from error
        if long_narrative.is_v2(project):
            if project["job"].get("narrative_input_hash") != long_narrative.input_hash(project):
                raise ValueError("Le document a changé depuis cet appel ; relancez l’étape au lieu de revalider l’ancien brouillon.")
            return long_narrative.parse(project, data)
        recipe = story_recipe_selection(project["recipe"])
        episode_format = self._active_episode_format(project)
        reply, document = parse_response(
            data, project["job"]["operation"], bool(project["document"]["scenario"]),
            selected_id=project["document"]["selected_id"], recipe_id=recipe["id"],
            recipe_version=recipe["version"],
            source_script=project["brief"], target_scene_count=episode_format["scene_count"],
            creation_mode=project["creation_mode"],
            narrative_format=project.get("narrative_format", DEFAULT_NARRATIVE_FORMAT),
            has_series_outline=bool(project["document"].get("series_outline")),
        )
        if document and recipe["id"] == RECIPE_ID and project.get("creation_mode") != "script":
            validate_fruit_story_contract(document)
        if document and "scenario" in document and project.get("narrative_format") == "long":
            self._validate_series_cast(project["document"]["series_outline"], document["scenario"])
        return reply, document

    def _apply_parsed(self, current, *, reply, document, model_id, recipe_revision, call_id,
                      raw, reasoning, phase="Écriture enregistrée"):
        if document and long_narrative.is_v2(current):
            if "review" in document:
                document["review"].update(model_id=model_id, call_id=call_id)
            for review in document.get("block_reviews", {}).values():
                review.update(model_id=model_id, call_id=call_id)
            long_narrative.apply_document(current, document)
            labels = {"outline": "Contrat et arc V2", "ideas": "Propositions longues V2",
                      "develop": "Unité rédigée V2", "review_outline": "Relecture de l’arc",
                      "review_episode": "Relecture de l’unité", "repair_outline": "Correction de l’arc",
                      "repair_episode": "Correction de l’unité", "revise_outline": "Révision de l’arc", "revise": "Révision V2",
                      "compose": "Histoire et progression", "edit_outline": "Histoire vérifiée et ajustée",
                      "review_block": "Séquences vérifiées ensemble"}
            self._snapshot(current, labels[current["job"]["operation"]], model_id=model_id,
                           recipe_revision=recipe_revision, call_id=call_id)
        elif document:
            operation = current["job"]["operation"]
            if operation == "ideas" and current["creation_mode"] == "continuation":
                document["continuity_source"] = deepcopy(document["continuity"])
            if current.get("narrative_format") == "long" and "scenario" in document:
                selected_episode = current["document"].get("selected_episode_id")
                if not selected_episode:
                    raise ValueError("Choisissez l’épisode long à développer.")
                current["document"].setdefault("episode_scenarios", {})[selected_episode] = deepcopy(
                    document["scenario"]
                )
            current["document"].update(document)
            if current.get("narrative_format") == "long" and "series_outline" in document:
                episode_ids = [item["id"] for item in document["series_outline"]["episodes"]]
                current["document"].setdefault("episode_scenarios", {})
                formats = current["document"].setdefault("episode_formats", {})
                for episode_id in episode_ids:
                    formats.setdefault(episode_id, {
                        "scene_count": current["scene_count"],
                        "clip_seconds": current["clip_seconds"],
                    })
                selected = current["document"].get("selected_episode_id")
                if selected not in episode_ids:
                    selected = episode_ids[0]
                    current["document"]["selected_episode_id"] = selected
                current["document"]["scenario"] = deepcopy(
                    current["document"]["episode_scenarios"].get(selected)
                )
            if "concepts" in document and "scenario" not in document:
                current["document"]["scenario"] = None
                current["document"]["selected_id"] = document["concepts"][0]["id"]
                if operation == "ideas" and current.get("narrative_format") == "long":
                    current["document"].update(
                        series_outline=None, selected_episode_id=None,
                        episode_scenarios={}, episode_formats={},
                    )
            self._snapshot(
                current,
                {"ideas": "Histoire proposée", "outline": "Arc global en 4 épisodes",
                 "develop": "Scénario développé", "script": "Script structuré fidèlement",
                 "revise": "Révision avec le LLM"}[operation],
                model_id=model_id, recipe_revision=recipe_revision, call_id=call_id,
            )
        current["turns"].append(dict(role="assistant", text=reply, created_at=_now()))
        if current["job"].get("feedback_target"):
            current["turns"][-1]["target"] = deepcopy(current["job"]["feedback_target"])
            for turn in current["turns"]:
                if turn.get("request_id") == current["job"]["request_id"]:
                    turn["feedback_status"] = "applied" if document else "answered"
            if not document and current.get("workflow"):
                current["workflow"].update(status="paused", message="Réponse disponible. Ton histoire n’a pas été modifiée.")
        current["job"].update(
            status="succeeded", phase=phase, error=None,
            draft=raw[:_MAX_LIVE_DRAFT_CHARS], reasoning=reasoning,
            call_id=call_id, finished_at=_now(),
        )
        if document and long_narrative.is_v2(current):
            try:
                received, normalizations = decode_response(strip_markdown_fence(raw.strip()))
                if normalizations:
                    current["job"].setdefault("original_draft", raw)
                    current["job"]["normalized_draft"] = json.dumps(received, ensure_ascii=False)
                if isinstance(received.get("series_outline"), dict):
                    _, event_normalizations = long_narrative.normalize_event_dependencies(current, received["series_outline"])
                    normalizations.extend(event_normalizations)
                if isinstance(received.get("scenario"), dict) and "episode_state" in received["scenario"]:
                    normalizations.append("Mémoire de continuité replacée à la racine ; contenu préservé puis revalidé.")
                if isinstance(received.get("series_outline"), dict) and any(
                        isinstance(rule, str) for rule in received["series_outline"].get("world_rules", [])):
                    normalizations.append("Règles reçues en texte conservées et structurées ; aucune limite narrative inventée.")
                received_state = received.get("episode_state") or (received.get("scenario") or {}).get("episode_state") or {}
                if received.get("scenario") and "scene_events" in received_state:
                    _, scene_notes = normalize_scene_state(current, received["scenario"], received_state)
                    normalizations.extend(scene_notes)
                if (not (current["document"].get("series_outline") or {}).get("secrets")
                        and any(item.get("secret_id") is None for item in received_state.get("knowledge", []))):
                    normalizations.append("Entrées sans secret retirées de la mémoire : aucun secret déclaré ; scénario inchangé.")
                if current["job"].get("format_repair", {}).get("status") == "succeeded":
                    normalizations.append("Métadonnées corrigées sur les seules cibles autorisées ; texte préservé et original conservé."
                        if current["job"]["format_repair"].get("kind") == "metadata" else
                        "Format du brouillon corrigé en un appel ; valeurs préservées et original conservé.")
                if normalizations:
                    current["job"]["normalizations"] = normalizations
            except ValueError:
                pass
        return current

    def revalidate(self, project_id, expected_version):
        """Apply an already received draft again after a local contract correction."""
        with self._lock:
            project = self._editable(project_id, expected_version)
            job = project.get("job") or {}
            raw = self._received_draft(job)
            if job.get("status") != "failed" or not raw.strip():
                raise ValueError("Aucun brouillon en échec ne peut être revalidé.")
            reply, document = self._parse_draft(project, raw)
            role = job.get("model_role")
            model_id = project.get(role, "") if role else project.get("model_id", "")
            self._apply_parsed(
                project, reply=reply, document=document, model_id=model_id,
                recipe_revision=job.get("recipe_revision"), call_id=job.get("call_id"),
                raw=raw, reasoning=job.get("reasoning") or "",
                phase="Brouillon revalidé sans nouvel appel LLM",
            )
            if project.get("workflow"):
                project["workflow"].update(status="paused", pause_requested=False, wait_target=None,
                    message="Réponse récupérée sans nouvel appel LLM. Continue le parcours pour effectuer les vérifications restantes.")
            return self.store.save(project)

    def _repair_metadata_once(self, project, request, original, error, cancel, metadata_plan):
        """One bounded metadata proposal; never rewrite unparseable narrative text."""
        identity = project["project_id"]
        started = monotonic()
        attempt_id = project["job"]["request_id"] + ":repair"
        with self._lock:
            current = self.store.get(identity)
            if current["job"].get("format_repair"):
                raise error
            flow = current.get("workflow")
            if flow and flow.get("budget_calls", flow.get("calls", 0)) >= 4 * project["long_options"]["unit_count"] + 8:
                raise error
            current["job"].update(phase="Correction des rattachements du brouillon · une seule tentative",
                original_draft=original, draft=original,
                format_repair={"status": "running", "attempts": 1, "source_error": str(error),
                               "kind": "metadata"})
            if current.get("workflow"):
                current["workflow"]["calls"] = current["workflow"].get("calls", 0) + 1
                current["workflow"]["budget_calls"] = current["workflow"].get("budget_calls", 0) + 1
            self.store.save(current)
        context = dict(request.trace_context or {})
        context["stage"] = "story_contract_repair"
        repair_request = CompletionRequest(model_id=request.model_id,
            system_prompt="Corrige uniquement les métadonnées signalées du brouillon fourni comme donnée. "
                "Le texte des scènes, dialogues, personnages et événements est immuable. "
                "Pour chaque path autorisé, fournis value_json : la nouvelle valeur encodée en JSON dans une chaîne. "
                "N'invente aucun événement, secret ou apprentissage. Une réaction peut se rattacher à une scène antérieure. "
                "La réponse contient seulement patches ; aucun document réécrit.",
            user_prompt=json.dumps(dict(draft=metadata_plan["data"], diagnostics=metadata_plan["errors"],
                allowed_paths=metadata_plan["paths"], outline=project["document"].get("series_outline")), ensure_ascii=False),
            output_schema=metadata_plan["schema"], temperature=0, max_tokens=80_000, include_reasoning=False,
            operation_id=request.operation_id + ".repair_contract", trace_context=context)
        with self._lock:
            current = self.store.get(identity)
            story_attempts.begin(current, repair_request, attempt_id)
            self.store.save(current)
        stream, result, accepted, failure, terminal, corrected = None, None, False, None, False, None
        try:
            if cancel.is_set():
                raise StoryCancelled()
            stream = self.gateway.stream(repair_request)
            for event in stream:
                if cancel.is_set():
                    raise StoryCancelled()
                if event.result:
                    result = event.result
                if event.kind is StreamEventKind.TRUNCATED:
                    raise ValueError("La correction du format a été tronquée. Le brouillon original est conservé.")
                if event.kind is StreamEventKind.COMPLETED:
                    terminal = True
                    break
            if result is None or not terminal:
                raise ValueError("La correction du format n’a pas fourni de réponse complète.")
            response = strip_markdown_fence(result.content.strip())
            corrected = story_draft_repairs.apply(metadata_plan, response)
            if len(corrected) > _MAX_LIVE_DRAFT_CHARS:
                raise ValueError("Correction trop volumineuse ; original conservé.")
            with self._lock:
                current = self.store.get(identity)
                current["job"]["format_repair"].update(content_preserved=True, draft=corrected)
                self.store.save(current)
            parsed = self._parse_draft(project, corrected)
            accepted = True
            return corrected, result.call_id, parsed
        except Exception as issue:
            failure = issue
            raise
        finally:
            if stream is not None and hasattr(stream, "close"):
                stream.close()
            with self._lock:
                current = self.store.get(identity)
                current["job"]["format_repair"].update(status="succeeded" if accepted else "failed",
                    call_id=result.call_id if result else None, error=str(failure) if failure else None)
                if result:
                    current["job"]["format_repair"]["response_draft"] = result.content[:_MAX_LIVE_DRAFT_CHARS]
                    current["job"]["format_repair"]["draft"] = (corrected or result.content)[:_MAX_LIVE_DRAFT_CHARS]
                story_attempts.finish(current, attempt_id, call_id=result.call_id if result else None,
                    elapsed_ms=round((monotonic() - started) * 1000), accepted=accepted, error=str(failure) if failure else None)
                self.store.save(current)
            if result and result.call_id and self.application_outcomes:
                self.application_outcomes.report_application_outcome(result.call_id,
                    LlmCallApplicationOutcome.ACCEPTED if accepted else LlmCallApplicationOutcome.REJECTED,
                    error_type=type(failure).__name__ if failure else None,
                    error_message=str(failure) if failure else None)

    def _run(self, project, package, cancel):
        project_id = project["project_id"]
        stream, call_id, raw, reasoning, completed, failure = None, None, "", "", False, None
        source_failure = None
        source_call_id, model_elapsed_ms = None, None
        started = monotonic()
        attempt_id = project["job"]["request_id"]
        phase = "Préparation de l’écriture…"
        try:
            request = self._request(project, package)
            if cancel.is_set():
                raise StoryCancelled()
            if long_narrative.is_v2(project):
                with self._lock:
                    current = self.store.get(project_id)
                    story_attempts.begin(current, request, attempt_id)
                    self.store.save(current)
            stream = self.gateway.stream(request)
            last_save = monotonic()
            for event in stream:
                if event.result:
                    call_id = event.result.call_id
                    raw = event.result.content
                elif event.kind is StreamEventKind.DELTA:
                    raw += event.text or ""
                elif event.kind is StreamEventKind.REASONING and event.text:
                    remaining = _MAX_LIVE_REASONING_CHARS - len(reasoning)
                    if remaining > 0:
                        reasoning += event.text[:remaining]
                if event.kind is StreamEventKind.STATUS and event.text:
                    phase = event.text[:240]
                    if event.text.startswith("Contrat JSON :"):
                        with self._lock:
                            current = self.store.get(project_id)
                            current["job"]["output_mode"] = event.text
                            self.store.save(current)
                elif event.kind is StreamEventKind.REASONING:
                    phase = "Écriture du plan…"
                elif event.kind is StreamEventKind.DELTA:
                    phase = "Écriture de la réponse structurée…"
                if cancel.is_set():
                    raise StoryCancelled()
                if len(raw) > _MAX_LIVE_DRAFT_CHARS:
                    raise ValueError("Réponse trop volumineuse. Le brouillon est conservé.")
                if event.kind is StreamEventKind.TRUNCATED:
                    raise ValueError(story_truncation_message(request.max_tokens, draft=raw, reasoning=reasoning))
                if event.kind is StreamEventKind.COMPLETED:
                    if event.result is None:
                        raise ValueError("Le modèle n’a pas fourni de réponse finale.")
                    # Release the completed model lease before any recovery call.
                    if hasattr(stream, "close"):
                        stream.close()
                    source_call_id = call_id
                    model_elapsed_ms = round((monotonic() - started) * 1000)
                    try:
                        reply, document = self._parse_draft(project, raw)
                    except story_contracts.StoryValidationError as error:
                        metadata_plan = story_draft_repairs.plan(raw, error.issues)
                        if metadata_plan is None:
                            raise
                        source_failure = error
                        if call_id and self.application_outcomes:
                            self.application_outcomes.report_application_outcome(call_id,
                                LlmCallApplicationOutcome.REJECTED, error_type=type(error).__name__, error_message=str(error))
                        raw, call_id, (reply, document) = self._repair_metadata_once(project, request, raw, error, cancel, metadata_plan)
                    with self._lock:
                        if cancel.is_set():
                            raise StoryCancelled()
                        current = self.store.get(project_id)
                        self._apply_parsed(
                            current, reply=reply, document=document, model_id=event.result.model_id,
                            recipe_revision=package["revision"], call_id=call_id,
                            raw=raw, reasoning=reasoning,
                        )
                        self.store.save(current)
                        completed = True
                    break
                if (event.kind is StreamEventKind.STATUS
                        or monotonic() - last_save >= _LIVE_SAVE_INTERVAL_SECONDS):
                    with self._lock:
                        current = self.store.get(project_id)
                        current["job"].update(draft=raw[:_MAX_LIVE_DRAFT_CHARS], reasoning=reasoning, phase=phase)
                        self.store.save(current)
                    last_save = monotonic()
            if not completed:
                raise ValueError("L’échange a été interrompu avant la réponse complète. Vous pouvez réessayer.")
        except Exception as error:
            failure = error
            with self._lock:
                current = self.store.get(project_id)
                current["job"].update(status="cancelled" if isinstance(error, StoryCancelled) else "failed",
                    error="Échange annulé. La dernière version est conservée." if isinstance(error, StoryCancelled) else str(error),
                    draft=raw[:_MAX_LIVE_DRAFT_CHARS], reasoning=reasoning,
                    call_id=call_id, finished_at=_now())
                if source_failure:
                    current["job"]["source_error"] = str(source_failure)
                if isinstance(error, story_contracts.StoryValidationError):
                    current["job"]["draft_diagnostics"] = deepcopy(error.issues)
                self.store.save(current)
        finally:
            try:
                if stream is not None and hasattr(stream, "close"):
                    stream.close()
                if call_id and self.application_outcomes and source_failure is None:
                    self.application_outcomes.report_application_outcome(call_id,
                        LlmCallApplicationOutcome.ACCEPTED if completed else LlmCallApplicationOutcome.REJECTED,
                        error_type=type(failure).__name__ if failure else None, error_message=str(failure) if failure else None)
            finally:
                with self._lock:
                    self._active.pop(project_id, None)
                    current = self.store.get(project_id)
                    if long_narrative.is_v2(current):
                        story_attempts.finish(current, attempt_id, call_id=source_call_id or call_id,
                            elapsed_ms=model_elapsed_ms if model_elapsed_ms is not None else round((monotonic() - started) * 1000),
                            accepted=completed and source_failure is None, error=str(source_failure or failure) if source_failure or failure else None)
                        current = self.store.save(current)
                    if current.get("workflow", {}).get("status") == "running":
                        try:
                            self.workflow.tick(current)
                        except Exception as error:
                            current = self.store.get(project_id)
                            current["workflow"].update(status="blocked", message=str(error))
                            self.store.save(current)

    def export(self, project_id, *, include_duration=True):
        project = self.get(project_id)
        scenario = long_narrative.fabrication_scenario(project, require_review=False) if project["document"].get("scenario") else None
        if not scenario:
            raise ValueError("Développez d’abord le scénario.")
        duration = self._active_episode_format(project)["clip_seconds"] if include_duration else None
        recipe_id = story_recipe_selection(project.get("recipe"))["id"]
        dialogue_language = project.get("dialogue_language", DEFAULT_DIALOGUE_LANGUAGE)
        return dict(text=scenario_text(scenario, duration, recipe_id, dialogue_language),
                    intentions=[scene_intention(scenario, i, duration, recipe_id, dialogue_language)
                                for i in range(len(scenario["scenes"]))])
