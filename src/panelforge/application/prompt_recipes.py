"""Exact scope and contracts for editable video preparation instructions."""
from typing import Protocol


EDITABLE_RECIPES = (
    ("minimax.h3.fl2va.classic.cinematic.planned", "1.0.0", "Classique · H3 Base"),
    ("minimax.h3.ref2v.classic.cinematic.planned", "1.0.0", "Classique · REF2V"),
    ("minimax.h3.fl2va.combat.planned", "1.3.0", "Combat · H3 Base"),
    ("minimax.h3.ref2v.combat.planned", "1.3.0", "Combat · REF2V"),
    ("minimax.h3.fl2va.sensual.planned", "1.0.0", "Sensuel · H3 Base"),
    ("minimax.h3.ref2v.sensual.planned", "1.0.0", "Sensuel · REF2V"),
)
EDITABLE_KEYS = frozenset((key, version) for key, version, _ in EDITABLE_RECIPES)


class PromptRecipeStore(Protocol):
    def get(self, cookbook_id: str, version: str, revision: int | None = None) -> dict: ...


def preparation_call_ids(composition, revision_id):
    """Walk explicit dependencies; regenerated candidates do not depend on parents."""
    from panelforge.domain import CompositionStage, RevisionOrigin
    revisions = {r.revision_id: r for stage in CompositionStage for r in composition.document(stage).revisions}
    used, visited = set(), set()

    def visit(identity):
        parts = identity.split(":")
        identity = parts[1] if len(parts) >= 2 and parts[0] == "zh" else parts[-1]
        if identity in visited or identity not in revisions:
            return
        visited.add(identity)
        revision = revisions[identity]
        if revision.llm_call_id:
            used.add(revision.llm_call_id)
        for source in revision.source_ids:
            visit(source)
        if revision.parent_revision_id and revision.origin in {RevisionOrigin.MANUAL, RevisionOrigin.REWRITE}:
            visit(revision.parent_revision_id)

    visit(revision_id)
    return sorted(used)
