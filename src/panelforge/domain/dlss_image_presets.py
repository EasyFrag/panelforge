"""Image-only comparison recipes. Deltas are relative to the user's settings."""

from dataclasses import asdict, replace

from .dlss import DlssSettings


PRESET_VERSION = "1.0.0"
PRESETS = (
    ("current", "Réglages actuels", None, 0),
    ("soft", "Traitement doux", "intensity", -0.25),
    ("detail", "Détails renforcés", "detail", 0.15),
    ("structure", "Structure renforcée", "structure", 0.2),
    ("tone", "Tonalité adoucie", "tone", -0.2),
)


def image_presets(settings: DlssSettings):
    if settings.interpolate or settings.hdr:
        raise ValueError("La comparaison de préréglages est réservée aux images SDR.")
    result = []
    for identifier, label, field, delta in PRESETS:
        value = settings
        if field:
            adjusted = round(max(1 if field == "detail" else 0, min(2, getattr(settings, field) + delta)), 4)
            value = replace(settings, **{field: adjusted})
        result.append({"preset_id": identifier, "label": label, "settings": asdict(value),
                       "available": field is None or value != settings, "version": PRESET_VERSION})
    return result


def selected_image_presets(settings, preset_ids):
    if not 1 <= len(preset_ids) <= len(PRESETS) or len(set(preset_ids)) != len(preset_ids):
        raise ValueError("Choisis entre un et cinq préréglages distincts.")
    available = {p["preset_id"]: p for p in image_presets(settings)}
    if any(identifier not in available for identifier in preset_ids):
        raise ValueError("Préréglage DLSS image inconnu.")
    if any(not available[identifier]["available"] for identifier in preset_ids):
        raise ValueError("Un préréglage est identique aux réglages actuels à cette limite. Décoche-le.")
    # Stable order independent of the order in which checkboxes were clicked.
    return [p for p in available.values() if p["preset_id"] in preset_ids]
