"""Explicit adoption of independent final-prompt model routing."""

# New cookbook versions must opt in deliberately; historical recipes stay pinned.
WRITER_MODEL_RECIPES = frozenset({
    ("minimax.h3.fl2va.classic.cinematic.planned", "1.0.0"),
    ("minimax.h3.ref2v.classic.cinematic.planned", "1.0.0"),
    ("minimax.h3.fl2va.combat.planned", "1.3.0"),
    ("minimax.h3.ref2v.combat.planned", "1.3.0"),
    ("minimax.h3.fl2va.sensual.planned", "1.0.0"),
    ("minimax.h3.ref2v.sensual.planned", "1.0.0"),
})


def supports_writer_model(cookbook_id: str, version: str) -> bool:
    return (cookbook_id, version) in WRITER_MODEL_RECIPES
