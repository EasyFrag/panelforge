"""Versioned permissions and validation for optional English speech."""

from .prompt_recipe_text import prompt_text
from panelforge.domain.localized_speech import LOCALIZED_THANKS_V1, LOCALIZED_THANKS_V2, LOCALIZED_THANKS_V3, LOCALIZED_THANKS_V4, LOCALIZED_THANKS_POLICIES, STABLE_THANKS_LANGUAGES, FIXED_THANKS

from collections import Counter
import re
import unicodedata

VOCAL_POLICY_VERSION = "1.0.0"
_SPEECH = re.compile(r"<d>\s*\[([^\]]+)\]\s*(.*?)\s*</d>", re.DOTALL)
_SILENCE = re.compile(r"(?i)\b(?:sans (?:aucun(?:e)? )?(?:dialogue|paroles?|voix)|aucun(?:e)? (?:dialogue|parole|voix)|no (?:dialogue|speech|talking|voices?)|silent (?:video|clip|scene)|silence complet)\b")
_VOCAL_CHANGE = re.compile(r"(?i)\b(?:dialog\w*|r[eé]pliqu\w*|parol\w*|parle\w*|say\w*|speak\w*|speech|voice|voix|silenc\w*|cris?|rire|laugh\w*|scream\w*)\b")


def requests_vocal_change(message: str) -> bool:
    return bool(_VOCAL_CHANGE.search(message))


def validate_vocal_level(level: int) -> None:
    if type(level) is not int or not 0 <= level <= 3:
        raise ValueError("La liberté de dialogue doit être comprise entre 0 et 3.")


def vocal_level(axes) -> int:
    return getattr(axes, "dialogue", 0)


def speech_lines(content: str) -> tuple[tuple[str, str], ...]:
    return tuple((language.strip(), text.strip()) for language, text in _SPEECH.findall(content))


def vocal_policy(level: int, *, locked: bool = False, speech_policy=None, speech_language=None) -> str:
    validate_vocal_level(level)
    if speech_policy in (LOCALIZED_THANKS_V3, LOCALIZED_THANKS_V4):
        if locked and speech_language not in FIXED_THANKS:
            raise ValueError("Le Prompt attend la langue déjà approuvée dans le Plan.")
        formulas = ({speech_language: FIXED_THANKS[speech_language]}
                    if speech_language in FIXED_THANKS else FIXED_THANKS)
        choice = ("Language fixed. " if speech_language else
                  "Choose once using the source's scene pools and frozen order. ")
        version = 4 if speech_policy == LOCALIZED_THANKS_V4 else 3
        return (f"LOCALIZED THANK-YOU v{version}: the existing little people thank together once after the help. "
                + choice + "Only these words: "
                + "; ".join(f"{name}: {words}" for name, words in formulas.items()) + ". "
                "No added words or other speech. "
                + ("Preserve the approved words and language exactly." if locked else
                   "Copy the native words into spoken_lines and action speech; use the full English "
                   "language name in spoken_languages and the <d> tag."))
    if speech_policy in LOCALIZED_THANKS_POLICIES:
        language = (f"Use {speech_language}, the explicitly selected language." if speech_language else
                    "Choose the scene's language from explicit source location, then clear visual evidence; "
                    "use English for uncertain or multilingual locations without a specified local language.")
        if speech_policy == LOCALIZED_THANKS_V2 and not speech_language:
            language = ("Use the image's explicit location or architectural/landscape atmosphere and the "
                        "frozen language preference order in the source. Choose the first eligible language "
                        "in that order, within the matching regional group. With no evidence, choose the first "
                        "language in the global order. Never default to English or infer France from French prose. "
                        "Supported languages: " + ", ".join(STABLE_THANKS_LANGUAGES) + ".")
        wording = "At most 12 words; leave time for the actions and final reaction. "
        if speech_policy == LOCALIZED_THANKS_V2:
            formulas = ({speech_language: FIXED_THANKS[speech_language]}
                        if speech_language in FIXED_THANKS else FIXED_THANKS)
            wording = ("Use ONLY the fixed formula for the chosen language: "
                       + "; ".join(f"{name}: {words}" for name, words in formulas.items())
                       + ". Capitalization and surrounding punctuation may vary. "
                       "No extra words, address to the hand, qualifiers, repetition or other sentence. "
                       "Leave time for the actions and final reaction. ")
        version = 2 if speech_policy == LOCALIZED_THANKS_V2 else 1
        return (f"REQUESTED LOCALIZED THANK-YOU v{version}: exactly one brief thank-you by the existing little people "
                "after the helping actions. This is requested speech, independent of optional dialogue freedom. "
                + language + " Use native writing and the full English language name in spoken_languages "
                "and the <d> language tag. " + wording + "Do not add any other speech. "
                + ("Preserve the approved words AND language exactly." if locked else
                   ("Choose the language once in the Plan and copy its fixed formula; "
                    "record the location evidence in continuity_invariants."
                    if speech_policy == LOCALIZED_THANKS_V2 else
                    "Decide the exact words and language once in the Plan; record the location evidence in continuity_invariants.")))
    permission = (
        prompt_text('vocal_policy.vocal_policy.01', 'No spontaneous speech or vocal reactions; keep only what the user requests.'),
        prompt_text('vocal_policy.vocal_policy.02', 'May add a brief nonverbal reaction (gasp, laugh, justified cry); no invented words.'),
        prompt_text('vocal_policy.vocal_policy.03', 'May add one short English line and a brief appropriate nonverbal reaction.'),
        prompt_text('vocal_policy.vocal_policy.04', 'May add a short English exchange, up to three short lines, between existing characters.'),
    )[level]
    return (
        prompt_text('vocal_policy.vocal_policy.05', 'VOCAL POLICY {value1} — level {value2}/3. {value3} These are permissions, never quotas. Explicit silence overrides additions. Preserve user-supplied words verbatim, including their original language. Additions use [English], at most 12 words per line, and must leave time for the action; aim below 2.5 spoken words per second across the clip. Identify the existing speaker. Never invent a character, injury or event merely to motivate speech. Describe nonverbal sounds as synchronized action/sound prose, not as spoken dialogue tags. ', value1=VOCAL_POLICY_VERSION, value2=level, value3=permission)
        + (prompt_text('vocal_policy.vocal_policy.06', 'The supplied vocal ledger is already decided: retain it exactly, with its speakers and reactions; no further additions.')
           if locked else prompt_text('vocal_policy.vocal_policy.07', 'Choose any additions once at this decision stage; downstream stages will preserve them.'))
    )


def _thanks_words(text: str, language: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    if language == "Arabic":
        # Optional vowel marks do not add spoken words to the same formula.
        text = re.sub("[\u064b-\u0652]", "", text)
    return " ".join(text.split()).strip(" .!?¡¿。").casefold()


def validate_speech(lines, protected, *, level: int, source_text: str,
                    duration_ms: int = 8000, locked=None, speech_policy=None, speech_language=None) -> tuple[str, ...]:
    """Protect requested words/order; bound additions without guessing language from prose."""
    validate_vocal_level(level)
    actual = tuple(text for _, text in lines)
    cursor = 0
    for text in protected:
        try:
            cursor = actual.index(text, cursor) + 1
        except ValueError as error:
            raise ValueError("Les paroles demandées doivent rester exactes et dans leur ordre.") from error
    if locked is not None and Counter(actual) != Counter(locked):
        raise ValueError("Conservez les dialogues déjà décidés ; aucun ajout ou retrait à cette étape.")
    if speech_policy in LOCALIZED_THANKS_POLICIES:
        if len(lines) != 1:
            raise ValueError("Prévoir un unique remerciement localisé.")
        language, text = lines[0]
        if speech_policy in (LOCALIZED_THANKS_V2, LOCALIZED_THANKS_V3, LOCALIZED_THANKS_V4) and language not in STABLE_THANKS_LANGUAGES:
            raise ValueError("Le remerciement doit utiliser une des 11 langues stables.")
        if speech_policy in (LOCALIZED_THANKS_V2, LOCALIZED_THANKS_V3, LOCALIZED_THANKS_V4):
            expected = FIXED_THANKS[language]
            if _thanks_words(text, language) != _thanks_words(expected, language):
                raise ValueError(f"Le remerciement en {language} doit être uniquement « {expected} », sans aucun ajout.")
        elif not text.strip() or len(text.split()) > 12:
            raise ValueError("Le remerciement doit être bref : 12 mots maximum.")
        if speech_language is not None and language != speech_language:
            raise ValueError("Conservez la langue de remerciement choisie.")
        # This explicit requested-speech policy overrides source-scene notes;
        # their old silence/dialogue instructions are geographical context only.
        return () if text in protected else (text,)
    remaining = Counter(protected)
    added = []
    for language, text in lines:
        if remaining[text]:
            remaining[text] -= 1
        else:
            if language != "English":
                raise ValueError("Les répliques ajoutées doivent utiliser la langue English.")
            added.append(text)
    allowed = (0, 0, 1, 3)[level]
    if _SILENCE.search(source_text):
        allowed = 0
    if len(added) > allowed:
        raise ValueError("Trop de répliques ajoutées pour la liberté de dialogue choisie (ou silence demandé).")
    if any(len(text.split()) > 12 for text in added):
        raise ValueError("Une réplique spontanée doit rester courte : 12 mots maximum.")
    if added and sum(len(text.split()) for text in actual) > max(0, duration_ms / 1000 * 2.5):
        raise ValueError("Les ajouts de dialogue occupent trop de temps pour ce clip.")
    return tuple(added)


def validate_brief_speech(content: str, protected, *, level: int, source_text: str,
                          duration_ms: int) -> tuple[str, ...]:
    # Requested quotes stay in the existing Brief ledger. Only new lines use <d>.
    pending = Counter(protected)
    added = []
    for language, text in speech_lines(content):
        if pending[text]:
            pending[text] -= 1
        else:
            added.append((language, text))
    validate_speech(tuple(("requested", t) for t in protected) + tuple(added), protected,
                    level=level, source_text=source_text, duration_ms=duration_ms)
    return tuple(text for _, text in added)


def validate_revision_speech(current: str, candidate: str, message: str, *, level: int, duration_ms: int) -> None:
    from .direct_ref2v_plan import extract_explicit_dialogues
    before = tuple(text for _, text in speech_lines(current))
    lines = speech_lines(candidate)
    after = tuple(text for _, text in lines)
    requested_change = requests_vocal_change(message)
    protected = tuple(text for text in before if text in after) if requested_change else before
    explicit = set(extract_explicit_dialogues(message))
    if requested_change and not explicit.issubset(after):
        raise ValueError("La révision doit conserver les nouvelles paroles explicitement demandées.")
    # New words explicitly supplied by the user are not spontaneous additions.
    annotated = tuple((language, text) for language, text in lines if text not in explicit or text in before)
    validate_speech(annotated, protected, level=level, source_text=message, duration_ms=duration_ms)
