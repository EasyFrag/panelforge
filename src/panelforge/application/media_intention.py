"""Keep analysis-frame provenance out of the intention handed to generation."""
import re

# A quoted line can legitimately mention an image number; its words are data.
_QUOTED = re.compile(r'"[^"\n]*"|«[^»]*»|“[^”]*”|(?<!\w)\x27[^\x27\n]*\x27(?!\w)')
_LABEL = r"(?:images?|captures?|frames?|pictures?)"
_INDEX = r"(?:(?:n[°o]|numéro|number|\#)\s*)?\d+"
_CITATION = re.compile(
    rf"[ \t]*[\(\[]\s*(?:(?:voir|see|cf\.?)\s+)?{_LABEL}\s+{_INDEX}"
    rf"(?:\s*(?:[-–—,]|à|a|to|et|and)\s*(?:{_LABEL}\s+)?{_INDEX})*\s*[\)\]]",
    re.IGNORECASE,
)
_INLINE = re.compile(rf"\b{_LABEL}\s+{_INDEX}\b", re.IGNORECASE)


def without_source_citations(text: str) -> str:
    """Remove only standalone citation parentheses/brackets, never scene prose."""
    pieces, start = [], 0
    for quote in _QUOTED.finditer(text):
        pieces.extend((_CITATION.sub("", text[start:quote.start()]), quote[0]))
        start = quote.end()
    pieces.append(_CITATION.sub("", text[start:]))
    return "".join(pieces).strip()


def source_reference_warning(text: str) -> str | None:
    if _INLINE.search(_QUOTED.sub("", text)):
        return "L’intention renvoie encore aux images d’analyse. Remplacez ces renvois par les actions ou les sujets concernés avant le transfert vers H3/REF2V. Les références de génération seront choisies séparément."
    return None
