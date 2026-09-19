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
from .prompt_lab import CompletionRequest, StreamEventKind, LlmCallApplicationOutcome, truncated_response_message
from .revised_documents import strip_markdown_fence


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


def _ideas_system_prompt(base_prompt, count):
    """Make the requested pitch count authoritative without contradictory legacy wording."""
    if count == 3:
        return base_prompt
    fixed_count_markers = ("trois", "concept-2", "concept-3")
    retained = [
        line for line in base_prompt.splitlines()
        if not any(marker in line.casefold() for marker in fixed_count_markers)
    ]
    ids = "concept-1" if count == 1 else f"concept-1 à concept-{count}"
    authority = (
        "ÉTAPE IDÉES — QUANTITÉ AUTORITAIRE\n"
        f"Produis exactement {count} proposition{'s' if count > 1 else ''} complète"
        f"{'s' if count > 1 else ''}, identifiée{'s' if count > 1 else ''} {ids}. "
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
    def __init__(self, *, gateway, store, recipes, traces=None, application_outcomes=None):
        self.gateway, self.store, self.recipes = gateway, store, recipes
        self.traces, self.application_outcomes = traces, application_outcomes
        self._lock = RLock()
        self._active = {}

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
        project.setdefault("proposal_count", 3)
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
        return project

    def recipe_specs(self):
        available = {(item["id"], item["version"]) for item in self.recipes.list()}
        return [spec for spec in story_recipe_specs() if (spec["id"], spec["version"]) in available]

    def create(self, *, title="Nouvelle histoire", brief="", clip_seconds=10, scene_count=6,
               recipe_id=RECIPE_ID, recipe_version=RECIPE_VERSION,
               architect_model_id="", writer_model_id="", creation_mode="ideas", proposal_count=3,
               dialogue_register=0, dialogue_language=DEFAULT_DIALOGUE_LANGUAGE,
               narrative_format=DEFAULT_NARRATIVE_FORMAT, parent_story_id=None):
        if not isinstance(title, str) or not title.strip() or len(title) > 160:
            raise ValueError("Donnez un nom à cette histoire (160 caractères maximum).")
        if not isinstance(brief, str):
            raise ValueError("Point de départ invalide.")
        if type(clip_seconds) is not int or not 5 <= clip_seconds <= 15 or type(scene_count) is not int or not 1 <= scene_count <= 12:
            raise ValueError("Choisissez 1 à 12 micro-scènes de 5 à 15 secondes.")
        if creation_mode not in {"ideas", "script", "continuation"}:
            raise ValueError("Mode de création inconnu.")
        narrative_format = narrative_format_selection(narrative_format)
        if narrative_format == "long" and creation_mode != "ideas":
            raise ValueError("Une histoire longue commence par un arc global ; utilise le mode Explorer des propositions.")
        if parent_story_id is not None and (
                not isinstance(parent_story_id, str)
                or not parent_story_id.startswith("story-") or len(parent_story_id) != 38):
            raise ValueError("Histoire parente invalide.")
        brief_limit = (_MAX_CONTINUATION_BRIEF_CHARS if creation_mode == "continuation"
                       else _MAX_STANDARD_BRIEF_CHARS)
        if len(brief) > brief_limit:
            raise ValueError(f"Point de départ trop long ({brief_limit:,} caractères maximum).".replace(",", " "))
        if type(proposal_count) is not int or not 1 <= proposal_count <= 3:
            raise ValueError("Choisissez entre 1 et 3 propositions.")
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
        return self.store.save(dict(project_id=f"story-{uuid4().hex}", title=title.strip(), brief=brief.strip(),
            clip_seconds=clip_seconds, scene_count=scene_count, document=document,
            revisions=[], turns=[], job=None, model_id=writer_model_id.strip(), recipe=recipe,
            architect_model_id=architect_model_id.strip(), writer_model_id=writer_model_id.strip(), diagnostics=[],
            creation_mode=creation_mode, proposal_count=proposal_count, dialogue_register=dialogue_register,
            dialogue_language=dialogue_language, narrative_format=narrative_format,
            parent_story_id=parent_story_id))

    def get(self, project_id):
        with self._lock:
            project = self._normalize(self.store.get(project_id))
            job = project.get("job")
            if job and job["status"] in {"running", "cancelling"} and project_id not in self._active:
                job.update(status="interrupted", error="Le service a été interrompu. La dernière version et le brouillon sont conservés.")
                project = self.store.save(project)
            return project

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
            if existing and previous_format and previous_format != requested_format:
                raise ValueError("Le format d’un épisode déjà développé ne peut pas changer sans réécriture.")
            document.setdefault("episode_formats", {})[episode_id] = requested_format
            document["selected_episode_id"] = episode_id
            document["scenario"] = deepcopy(existing) if existing else None
            self._snapshot(project, f"Ouverture de {episode_id}")
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
            if project.get("narrative_format") == "long" and project["document"].get("selected_episode_id"):
                project["document"].setdefault("episode_scenarios", {})[
                    project["document"]["selected_episode_id"]] = deepcopy(project["document"]["scenario"])
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
            self._snapshot(project, f"Reprise de la version {revision}")
            project["turns"].append(dict(role="assistant", text=f"Version {revision} réappliquée. Les échanges suivants partiront de ce document.", created_at=_now()))
            return self.store.save(project)

    def start(self, project_id, *, operation, instruction, model_id=None, expected_version, request_id):
        if operation not in {"ideas", "outline", "develop", "script", "revise"}:
            raise ValueError("Action d’écriture inconnue.")
        if not isinstance(instruction, str) or len(instruction) > 12000 or (operation == "revise" and not instruction.strip()):
            raise ValueError("Écrivez une demande de 1 à 12 000 caractères.")
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 100:
            raise ValueError("Identifiant de demande invalide.")
        with self._lock:
            project = self.get(project_id)
            if project.get("job", {}) and project["job"]["request_id"] == request_id:
                return project
            project = self._editable(project_id, expected_version)
            if operation == "ideas" and project["creation_mode"] not in {"ideas", "continuation"}:
                raise ValueError("Ce projet suit un script fourni et ne génère pas de pistes.")
            if operation == "script" and project["creation_mode"] != "script":
                raise ValueError("Ce projet n’est pas configuré pour suivre un script.")
            if operation == "outline":
                if project.get("narrative_format") != "long":
                    raise ValueError("La construction d’un arc est réservée aux histoires longues.")
                if not project["document"]["selected_id"]:
                    raise ValueError("Sélectionnez une histoire avant de construire son arc.")
            if operation == "develop":
                if not project["document"]["selected_id"]:
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
            chosen_model = model_id.strip() if isinstance(model_id, str) else project.get(role, "")
            if not chosen_model:
                chosen_model = project.get("model_id", "")
            if not chosen_model or len(chosen_model) > 300:
                raise ValueError("Choisissez un modèle LLM pour cette étape.")
            # Read active editorial instructions now; this call retains its snapshot.
            recipe = story_recipe_selection(project["recipe"])
            package = self.recipes.get(recipe["id"], recipe["version"])
            count = project["proposal_count"]
            label = {"ideas": f"Propose {count} histoire{'s' if count > 1 else ''} différente{'s' if count > 1 else ''}.",
                     "outline": "Construis l’arc global en quatre épisodes autoportants et reliés.",
                     "develop": "Développe l’histoire sélectionnée en scénario complet.",
                     "script": "Structure fidèlement le script fourni sans omettre ni réécrire ses dialogues.",
                     "revise": instruction.strip()}[operation]
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
                project["turns"].append(dict(role="user", text=turn_text, created_at=_now()))
            project[role] = chosen_model
            project["model_id"] = chosen_model
            project["job"] = dict(request_id=request_id, status="running", operation=operation, started_at=_now(),
                phase="Préparation de l’écriture…", error=None, draft="", reasoning="", model_role=role,
                recipe=deepcopy(recipe), recipe_revision=package["revision"], call_id=None)
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

    def cancel(self, project_id):
        with self._lock:
            project = self.get(project_id)
            event = self._active.get(project_id)
            if event:
                event.set()
                project["job"].update(status="cancelling", phase="Annulation demandée ; attente du moteur LLM…")
                project = self.store.save(project)
            return project

    def _request(self, project, package):
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
        count = project["proposal_count"]
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
                f"JSON strict conforme au contrat. Exactement {count} concept{'s' if count > 1 else ''} ; "
                "1–12 personnages, 1–8 décors. Tous les identifiants référencés doivent exister. "
                "En révision, discussion_only:true ne modifie rien ; sinon renvoyer le document entier. "
                "Le document courant et selected_id font foi."
            )
        context = dict(operation=operation, creation_mode=project["creation_mode"],
            narrative_format=project.get("narrative_format", DEFAULT_NARRATIVE_FORMAT), proposal_count=count,
            brief=project["brief"], clip_seconds=clip_seconds,
            target_scene_count=target_scene_count, target_clip_seconds=clip_seconds, current_document=document,
            conversation=conversation, recent_concepts_to_avoid=seen[:24],
            response_contract=response_contract(operation, has_scenario, recipe["id"], recipe["version"], count,
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
            system_prompt = _ideas_system_prompt(package["fields"][field], count)
        else:
            system_prompt = package["fields"][field]
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
        elif operation == "revise" and not has_scenario and not has_series_outline and count != 3:
            system_prompt += (f"\n\nCONTRAT DE CE PROJET : le document contient exactement {count} proposition"
                              f"{'s' if count > 1 else ''}, identifiée{'s' if count > 1 else ''} de concept-1"
                              f"{' à concept-' + str(count) if count > 1 else ''}. Conserve cette quantité.")
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
            data = decode_story_json(strip_markdown_fence(raw.strip()))
        except ValueError as error:
            raise ValueError(
                "Le modèle n’a pas renvoyé un JSON valide. La dernière version et le brouillon sont conservés."
            ) from error
        recipe = story_recipe_selection(project["recipe"])
        episode_format = self._active_episode_format(project)
        reply, document = parse_response(
            data, project["job"]["operation"], bool(project["document"]["scenario"]),
            selected_id=project["document"]["selected_id"], recipe_id=recipe["id"],
            recipe_version=recipe["version"], proposal_count=project["proposal_count"],
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
        if document:
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
                if operation == "ideas":
                    current["document"]["selected_id"] = (
                        document["concepts"][0]["id"] if current["proposal_count"] == 1 else None
                    )
                    if current.get("narrative_format") == "long":
                        current["document"].update(
                            series_outline=None, selected_episode_id=None,
                            episode_scenarios={}, episode_formats={},
                        )
            proposal_label = (
                f"{current['proposal_count']} proposition"
                f"{'s' if current['proposal_count'] > 1 else ''}"
            )
            self._snapshot(
                current,
                {"ideas": proposal_label, "outline": "Arc global en 4 épisodes",
                 "develop": "Scénario développé", "script": "Script structuré fidèlement",
                 "revise": "Révision avec le LLM"}[operation],
                model_id=model_id, recipe_revision=recipe_revision, call_id=call_id,
            )
        current["turns"].append(dict(role="assistant", text=reply, created_at=_now()))
        current["job"].update(
            status="succeeded", phase=phase, error=None,
            draft=raw[:_MAX_LIVE_DRAFT_CHARS], reasoning=reasoning,
            call_id=call_id, finished_at=_now(),
        )
        return current

    def revalidate(self, project_id, expected_version):
        """Apply an already received draft again after a local contract correction."""
        with self._lock:
            project = self._editable(project_id, expected_version)
            job = project.get("job") or {}
            raw = job.get("draft") or ""
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
            return self.store.save(project)

    def _run(self, project, package, cancel):
        project_id = project["project_id"]
        stream, call_id, raw, reasoning, completed, failure = None, None, "", "", False, None
        phase = "Préparation de l’écriture…"
        try:
            request = self._request(project, package)
            if cancel.is_set():
                raise StoryCancelled()
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
                elif event.kind is StreamEventKind.REASONING:
                    phase = "Écriture du plan…"
                elif event.kind is StreamEventKind.DELTA:
                    phase = "Écriture de la réponse structurée…"
                if cancel.is_set():
                    raise StoryCancelled()
                if len(raw) > _MAX_LIVE_DRAFT_CHARS:
                    raise ValueError("Réponse trop volumineuse. Le brouillon est conservé.")
                if event.kind is StreamEventKind.TRUNCATED:
                    raise ValueError(truncated_response_message(request.max_tokens))
                if event.kind is StreamEventKind.COMPLETED:
                    if event.result is None:
                        raise ValueError("Le modèle n’a pas fourni de réponse finale.")
                    reply, document = self._parse_draft(project, raw)
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
                self.store.save(current)
        finally:
            try:
                if stream is not None and hasattr(stream, "close"):
                    stream.close()
                if call_id and self.application_outcomes:
                    self.application_outcomes.report_application_outcome(call_id,
                        LlmCallApplicationOutcome.ACCEPTED if completed else LlmCallApplicationOutcome.REJECTED,
                        error_type=type(failure).__name__ if failure else None, error_message=str(failure) if failure else None)
            finally:
                with self._lock:
                    self._active.pop(project_id, None)

    def export(self, project_id, *, include_duration=True):
        project = self.get(project_id)
        scenario = project["document"]["scenario"]
        if not scenario:
            raise ValueError("Développez d’abord le scénario.")
        duration = self._active_episode_format(project)["clip_seconds"] if include_duration else None
        recipe_id = story_recipe_selection(project.get("recipe"))["id"]
        dialogue_language = project.get("dialogue_language", DEFAULT_DIALOGUE_LANGUAGE)
        return dict(text=scenario_text(scenario, duration, recipe_id, dialogue_language),
                    intentions=[scene_intention(scenario, i, duration, recipe_id, dialogue_language)
                                for i in range(len(scenario["scenes"]))])
