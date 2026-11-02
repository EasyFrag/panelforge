"""Opt-in causal contracts and protected action transport for Petits hommes.

References prove structure and transmission, never the physical truth of a scene.
The model chooses all actions; this module supplies no scenario or tool examples.
"""
from copy import deepcopy
import json
import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from panelforge.domain.little_men_variety import MECHANISM_FAMILIES, OBJECTS, LEGACY_OBJECTS, validate_selection

from .vocal_policy import speech_lines


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ActionRef(_Model):
    phase: int = Field(ge=1, le=2, strict=True, description="One-based phase index in the single continuous shot.")
    action: int = Field(ge=1, le=6, strict=True, description="One-based action index inside that phase.")


class HelpContract(_Model):
    danger: str = Field(min_length=1, max_length=600, description="The principal active danger supported by the source image and intention, including its visible consequence. Ambient conditions must not replace it.")
    target: str = Field(min_length=1, max_length=400, description="The cause or threatening subject that the intervention changes, with the inhabitants or area needing help.")
    mechanism: str = Field(min_length=1, max_length=600, description="Why the chosen direct hand action or optional accessory changes this target. Describe one coherent solution without a gesture quota.")
    lasting_result: str = Field(min_length=1, max_length=600, description="The visible evidence that the danger is resolved and the benefit persists after the hand leaves. Concretize it in the referenced resolution action and end_state.")
    residents_benefit: str = Field(min_length=1, max_length=600, description="How the inhabitants visibly benefit before thanking, interacting with the result when relevant. This must be an observable activity or improved situation, not thanks itself.")
    active_threat: ActionRef = Field(description="Action showing the threat behaving actively and affecting the scene before the intervention.")
    intervention: tuple[ActionRef, ...] = Field(min_length=1, max_length=12, description="Ordered actions implementing the same solution. Each must state its useful gesture and visible target reaction. Reference only as many as the scene needs.")
    resolution: ActionRef = Field(description="Action proving the danger is resolved; may also be the last intervention action.")
    benefit: ActionRef = Field(description="Action showing the inhabitants benefiting after resolution and before thanks. May share the final action if the use visibly precedes its spoken thanks.")
    thanks: ActionRef = Field(description="The last action, containing the single short localized thank-you. No required collective pose or long pause.")


class ActiveThreat(_Model):
    description: str = Field(min_length=1, max_length=600, description="An actual danger supported by the image or its linked context, with its visible behavior or effect. Do not invent a danger to justify assistance.")
    evidence: ActionRef = Field(description="Action showing this established threat before the intervention, with behavior consistent with its role and physical state.")


class AdaptiveHelpContract(_Model):
    """Version 7 accepts a useful contribution without requiring a crisis."""
    initial_goal: str = Field(min_length=1, max_length=600, description="The initial objective supported by the image, its linked intention or the current user instruction. State the goal without prescribing an accessory.")
    help_need: str = Field(min_length=1, max_length=600, description="The concrete difficulty, effort or useful improvement that warrants assistance. An ordinary activity is sufficient; do not invent urgency or suffering.")
    beneficiary: str = Field(min_length=1, max_length=400, description="The being, group, place or resource directly benefiting from the intervention. Do not automatically treat an animal as a threat or require the residents to consume the result themselves.")
    target: str = Field(min_length=1, max_length=400, description="The physical element on which the hand acts to help the beneficiary.")
    mechanism: str = Field(min_length=1, max_length=600, description="The physical operation and why it changes the target usefully. Choose the contribution before the optional accessory; several useful gestures may implement one coherent solution.")
    lasting_result: str = Field(min_length=1, max_length=600, description="The observable useful change that persists beyond the decisive gesture. Show its evidence in the resolution action and end_state.")
    benefit_description: str = Field(min_length=1, max_length=600, description="The beneficiary's observable improvement after the result and before thanks. Residents use or appreciate the result when relevant; gratitude alone is not the benefit.")
    initial_state: ActionRef = Field(description="Action establishing the original activity, difficulty or effort before assistance. A static obstacle or state is valid; this action does not require a pause or deterioration.")
    threat: ActiveThreat | None = Field(description="Null when no danger is established. Otherwise describe that danger and reference its evidence before intervention. Preserve the actual role of each being.")
    intervention: tuple[ActionRef, ...] = Field(min_length=1, max_length=12, description="Distinct useful gestures in chronological order, stating contact or operation and the target's response. Support existing efforts and world rules. No gesture quota.")
    resolution: ActionRef = Field(description="Action proving the useful change; may be the final intervention action.")
    benefit: ActionRef = Field(description="Action showing the actual beneficiary's improvement after resolution and before gratitude. May share the final action if the visible benefit precedes the spoken thanks.")
    thanks: ActionRef = Field(description="The last action, with the residents' single brief localized thanks after the benefit. They may continue their activity; no required collective pose or long pause.")


class ChosenObject(_Model):
    catalog_id: str | None = Field(description="The stable catalogue ID when supplied, otherwise null. The application resolves an exact known catalogue name to its ID. Use the exact supplied name for a catalogue object.")
    name: str = Field(min_length=1, max_length=120, description="English object name. Use this exact name in a referenced intervention action where it is used. The giant hand is not an accessory.")

    @model_validator(mode="before")
    @classmethod
    def resolve_exact_known_name(cls, value):
        if (isinstance(value, dict) and "catalog_id" in value and value["catalog_id"] is None
                and isinstance(value.get("name"), str)):
            name = value["name"].strip().casefold()
            # Catalogue growth must not rewrite previously approved external objects.
            # New catalogue entries use the explicit ID supplied in their assortment.
            identity = next((identity for identity, item in LEGACY_OBJECTS.items() if item["name"].casefold() == name), None)
            if identity is not None:
                return {**value, "catalog_id": identity}
        return value

    @model_validator(mode="after")
    def valid_catalogue_object(self):
        if self.catalog_id is not None:
            if self.catalog_id not in OBJECTS:
                raise ValueError("Objet du catalogue Petits hommes inconnu.")
            if self.name.casefold() != OBJECTS[self.catalog_id]["name"].casefold():
                raise ValueError("Conservez le nom canonique correspondant à l’identifiant de l’objet.")
        return self


class VarietyChoice(_Model):
    objects: tuple[ChosenObject, ...] = Field(description="Distinct accessory kinds actually used by the intervention, each named in its action. Empty for direct hand action alone. Do not list unused alternatives.")
    mechanism_family: str = Field(min_length=1, json_schema_extra={"enum": list(MECHANISM_FAMILIES)}, description="The main physical operation that produces the lasting result, consistent with help_contract.mechanism and the referenced actions. Classify the decisive operation, not every preparatory gesture or the general goal.")
    departure_reason: str | None = Field(min_length=1, max_length=600, description="Concise English reason whenever direct hand action or any object outside the supplied assortment is necessary. Null when no explanation is needed. Relevance and a readable result take priority over diversity.")

    @field_validator("mechanism_family")
    @classmethod
    def known_mechanism(cls, value):
        if value not in MECHANISM_FAMILIES:
            raise ValueError("Famille de mécanisme Petits hommes inconnue.")
        return value

    @model_validator(mode="after")
    def distinct_objects_and_explanation(self):
        keys = [obj.catalog_id or obj.name.casefold() for obj in self.objects]
        if len(keys) != len(set(keys)):
            raise ValueError("Déclarez chaque type d’objet une seule fois.")
        if (not self.objects or any(obj.catalog_id is None for obj in self.objects)) and not self.departure_reason:
            raise ValueError("Expliquez le choix d’un objet hors catalogue ou de la main seule.")
        return self


def validate_variety_choice(plan, selection=None) -> None:
    """Validate declared choices, with frozen assortment membership when supplied.

    Literal mentions establish traceability, not semantic or visual correctness.
    The context-free linter checks structure; compilation requires the assortment.
    """
    value = _value(plan)
    choice = VarietyChoice.model_validate(value["variety_choice"])
    if selection is not None:
        validate_selection(selection)
        if any(obj.catalog_id not in selection["candidates"] for obj in choice.objects) and not choice.departure_reason:
            raise ValueError("Expliquez pourquoi l’intervention exige un objet hors de l’assortiment proposé.")
    contract = _contract(value)
    actions = " ".join(value["shots"][0]["phases"][ref.phase - 1]["actions"][ref.action - 1]
                       for ref in contract.intervention).casefold()
    for obj in choice.objects:
        name = obj.name.casefold()
        plural = "(?:es)?" if name.endswith(("s", "x", "z", "ch", "sh")) else "s?"
        if not re.search(r"(?<!\w)" + re.escape(name) + plural + r"(?!\w)", actions):
            raise ValueError("Chaque objet choisi doit être nommé dans une action d’intervention qui l’utilise.")
    validate_no_umbrella(json.dumps(choice.model_dump(mode="json"), ensure_ascii=False))


_UMBRELLA = re.compile(r"\b(?:umbrellas?|parapluies?|parasols?|ombrelles?)\b|雨伞|雨傘|阳伞|陽傘")
_UMBRELLA_GROUP = re.compile(
    r"(?:" + _UMBRELLA.pattern + r")(?:\s*(?:,|\b(?:and|or|nor|et|ni|ou)\b)\s*(?:"
    + _UMBRELLA.pattern + r"))*")
_ABSTRACT = re.compile(r"\s+(?:organizations?|organisations?|companies|company|corporations?|terms?|categories|category|frameworks?)\b")
_DETERMINER = r"(?:(?:a|an|any|the|un|une|des|le|la|de|d')\s*)?"
_ADJECTIVES = r"(?:(?:open|opened|closed|transparent|clear|giant|large|small|black|red|ouvert|ouverte|ferme|fermee|geant|geante|grand|grande|petit|petite|noir|noire|rouge)\s+){0,3}"
_ABSENCE_BEFORE = re.compile(
    r"\b(?:no|without|sans|aucun|aucune|pas de|absence of|absence de|"
    r"(?:do not|does not|must not|never|don't|doesn't)\s+(?:use|add|introduce|include|choose|show|select|bring|deploy|depict)|"
    r"(?:ne pas|ne jamais)\s+(?:utiliser|ajouter|introduire|choisir|montrer))\s+"
    + _DETERMINER + _ADJECTIVES + r"$"
)
_ABSENCE_AFTER = re.compile(
    r"\s+(?:(?:is|are|remains?|est|sont)\s+)?(?:strictly\s+|entirely\s+|totalement\s+)?"
    r"(?:banned|forbidden|prohibited|absent|excluded|interdit\w*|exclu\w*|"
    r"not\s+(?:present|used|allowed)|n'est pas utilise)\b"
)
_EXCLUSION_SUBJECT = re.compile(r"\s*" + _DETERMINER + _ADJECTIVES + r"$")
_HELP_TOKEN = re.compile(r"\[\[help:(\d+):(\d+)\]\]")


def _normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold().replace("’", "'"))
                   if not unicodedata.combining(c))


def validate_no_umbrella(content: str) -> None:
    """Reject depicted/selected umbrellas, allowing a narrowly scoped exclusion.

    This lexical check covers English/French object names and common Chinese
    names. It is not a visual or general-purpose semantic classifier.
    """
    text = _normalized(content)
    for match in _UMBRELLA_GROUP.finditer(text):
        before = re.split(r'[.;!?\n":{}\[\]]|\b(?:but|mais|however|instead)\b', text[:match.start()])[-1]
        after = text[match.end():]
        if _ABSTRACT.match(after):
            continue
        exclusion = _ABSENCE_BEFORE.search(before)
        if exclusion and not re.search(r"\b(?:not|never|pas)\s*$", before[:exclusion.start()]):
            continue
        if _EXCLUSION_SUBJECT.fullmatch(before) and _ABSENCE_AFTER.match(after):
            continue
        raise ValueError("Petits hommes : le parapluie est interdit. Choisissez un autre moyen d’intervention dans le Plan et le Prompt.")


def _value(plan):
    return plan.model_dump(mode="json") if hasattr(plan, "model_dump") else plan


def _contract(value):
    """Dispatch an already policy-validated Plan, or a context-free lint input."""
    raw = value["help_contract"]
    model = AdaptiveHelpContract if "initial_state" in raw else HelpContract
    return model.model_validate(raw)


def _refs(contract):
    if isinstance(contract, AdaptiveHelpContract):
        threat = (contract.threat.evidence,) if contract.threat is not None else ()
        return (contract.initial_state, *threat, *contract.intervention,
                contract.resolution, contract.benefit, contract.thanks)
    return (contract.active_threat, *contract.intervention, contract.resolution,
            contract.benefit, contract.thanks)


def validate_contract(plan) -> None:
    value = _value(plan)
    contract = _contract(value)
    adaptive = isinstance(contract, AdaptiveHelpContract)
    if len(value["shots"]) != 1:
        raise ValueError("Petits hommes : conserver un seul plan continu.")
    actions = {(p, a): text for p, phase in enumerate(value["shots"][0]["phases"], 1)
               for a, text in enumerate(phase["actions"], 1)}
    keys = list(actions)

    def index(ref):
        key = (ref.phase, ref.action)
        if key not in actions:
            raise ValueError("Le contrat d’aide doit référencer des actions existantes du Plan.")
        return keys.index(key)

    initial, resolution, benefit, thanks = map(index, (
        contract.initial_state if adaptive else contract.active_threat,
        contract.resolution, contract.benefit, contract.thanks))
    gestures = [index(ref) for ref in contract.intervention]
    if gestures != sorted(set(gestures)):
        raise ValueError("Les gestes d’aide doivent être distincts et référencés dans leur ordre.")
    if not (initial < gestures[0] <= gestures[-1] <= resolution < benefit <= thanks == len(keys) - 1):
        raise ValueError("Respectez l’ordre état initial, intervention, résultat utile, bénéfice puis merci final." if adaptive else
                         "Respectez l’ordre danger actif, intervention, résolution, bénéfice des habitants puis merci final.")
    if adaptive and contract.threat is not None and index(contract.threat.evidence) >= gestures[0]:
        raise ValueError("La preuve du danger établi doit précéder l’intervention.")
    spoken = [(i, speech_lines(text)) for i, text in enumerate(actions.values()) if speech_lines(text)]
    if len(spoken) != 1 or spoken[0][0] != thanks or len(spoken[0][1]) != 1:
        raise ValueError("Le contrat d’aide doit pointer vers l’unique remerciement dans la dernière action.")
    descriptions = ((contract.initial_goal, contract.help_need, contract.beneficiary,
                     contract.target, contract.mechanism, contract.lasting_result,
                     contract.benefit_description,
                     *([contract.threat.description] if contract.threat is not None else [])) if adaptive else
                    (contract.danger, contract.target, contract.mechanism,
                     contract.lasting_result, contract.residents_benefit))
    for text in descriptions:
        if "<d>" in text or "[[help:" in text:
            raise ValueError("Décrivez le contrat d’aide sans paroles ni jetons de rédaction.")
    validate_no_umbrella(json.dumps(value, ensure_ascii=False))


def protected_actions(plan) -> dict[str, str]:
    value = _value(plan)
    contract = _contract(value)
    refs = sorted({(ref.phase, ref.action) for ref in _refs(contract)})
    return {f"[[help:{phase}:{action}]]": value["shots"][0]["phases"][phase - 1]["actions"][action - 1]
            for phase, action in refs}


def canonical_writer(plan) -> dict:
    """Validation-only Writer assembled from the model's own approved actions."""
    value = _value(plan)
    protected = protected_actions(value)
    phases = [" ".join(f"[[help:{p}:{a}]]" if f"[[help:{p}:{a}]]" in protected else action
                       for a, action in enumerate(phase["actions"], 1))
              for p, phase in enumerate(value["shots"][0]["phases"], 1)]
    return dict(shots=[dict(phases=phases)], overall_soundscape=value["overall_soundscape"],
                non_diegetic_music=value["non_diegetic_music"])


def writer_instructions(plan: dict) -> str:
    validate_contract(plan)
    protected = protected_actions(plan)
    return (
        ("\nCAUSAL ACTION TRANSPORT — Petits hommes v7\n" if isinstance(_contract(plan), AdaptiveHelpContract) else
         "\nCAUSAL ACTION TRANSPORT — Petits hommes v6\n" if "variety_choice" in plan else
         "\nCAUSAL ACTION TRANSPORT — Petits hommes v5\n")
        + "Each listed token stands for one approved action, including its speech when present. "
        "Place every token exactly once, in its original phase and in this order. "
        "Write only the unprotected actions and concise connective prose around them. "
        "Do not repeat, paraphrase or replace a protected action or its dialogue beside its token. "
        "Do not add a competing gesture, threat or outcome. The compiler inserts the approved "
        "action verbatim at that token; tokens never reach the video model. Keep the same target, "
        "reaction, lasting resolution and benefit. No umbrella or parasol.\n"
        + json.dumps([dict(token=token, action=action) for token, action in protected.items()], ensure_ascii=False)
    )


def expand_writer(plan, writer: dict) -> dict:
    """Replace only explicit protected-action tokens; never silently repair prose."""
    value = _value(plan)
    result = deepcopy(writer)
    protected = protected_actions(value)
    if len(result["shots"]) != 1 or len(result["shots"][0]["phases"]) != len(value["shots"][0]["phases"]):
        raise ValueError("Conservez le plan continu et ses phases d’aide.")
    for p, prose in enumerate(result["shots"][0]["phases"], 1):
        expected = [token for token in protected if token.startswith(f"[[help:{p}:")]
        found = [match[0] for match in _HELP_TOKEN.finditer(prose)]
        if found != expected:
            raise ValueError("Le Prompt doit conserver chaque jeton d’action d’aide une fois, dans sa phase et son ordre.")
        for token in expected:
            if protected[token] in prose:
                raise ValueError("Le Prompt répète une action protégée : conserver uniquement son jeton.")
        prose = _HELP_TOKEN.sub(lambda match: protected[match[0]], prose)
        if "[[help:" in prose:
            raise ValueError("Jeton d’action d’aide invalide.")
        result["shots"][0]["phases"][p - 1] = prose
    validate_no_umbrella(json.dumps(result, ensure_ascii=False))
    return result


def validate_final(content: str, protected: list[str]) -> None:
    validate_no_umbrella(content)
    cursor = 0
    for action in protected:
        position = content.find(action, cursor)
        if position < 0 or content.count(action) != 1:
            raise ValueError("Conservez les actions causales approuvées et leur ordre dans le Prompt Petits hommes.")
        cursor = position + len(action)
    if "[[help:" in content:
        raise ValueError("Le Prompt contient encore un jeton d’action d’aide non compilé.")
