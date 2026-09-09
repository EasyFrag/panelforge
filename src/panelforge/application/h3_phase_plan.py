"""Phase-aware ending validation for H3 preparation 1.1.0; V4 data unchanged."""

from __future__ import annotations

import re

from .direct_ref2v_plan import (
    DirectMotionEndBehavior,
    canonical_direct_ref2v_action_plan_v4,
    direct_ref2v_action_plan_warnings_v4,
    parse_direct_ref2v_action_plan_v4,
)


_ANCHOR = re.compile(r"(?i)\b(?:final|last|locked)[ -](?:frame|pose)\b")
_CONVERGENCE = re.compile(
    r"(?i)\b(?:match(?:es|ed|ing)?|identical|settles?|locks?|reaches?|ends?)\b"
)
_THROUGH_CUT = re.compile(
    r"(?i)\b(?:until|through|at)\s+(?:the\s+)?(?:cut|end)\b|\bfor the rest\b"
)
_QUALIFIED_STOP = re.compile(
    r"(?i)\b(?:except|apart from|briefly|momentarily|resumes?|again)\b"
)
# Deliberately narrow assertions, not general natural-language understanding.
# Completing a named object or stopping an earlier actor is never itself a freeze.
_GLOBAL_STOP = re.compile(
    r"(?i)\b(?:(?:the\s+)?(?:entire|whole)\s+(?:scene|frame|video|image)\s+"
    r"(?:(?:is|remains?)\s+(?:frozen|still|motionless)|freezes?|stops?)|"
    r"all\s+(?:visible\s+)?motion\s+(?:stops?|ceases?))\b"
)
_ACTOR_STOP = re.compile(
    r"(?i)(?:^|[;,]\s*|\b(?:while|and)\s+)"
    r"(?P<actor>(?:the\s+)?[a-z][a-z -]{0,65}?)\s+"
    r"(?:holds?\s+(?:the\s+)?final[ -](?:pose|frame)|"
    r"freezes?\s+in\s+(?:the\s+)?final[ -]pose|"
    r"stops?\s+(?:moving|drifting|rotating|dancing|walking|running)|"
    r"(?:is|remains?|stays?)\s+(?:still|motionless))\b"
)


def _subject(text: str) -> str:
    return re.sub(r"^(?:the|a|an)\s+", "", text.strip().lower())


def _ending_issues(content: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    plan = parse_direct_ref2v_action_plan_v4(content)
    if plan.motion_contract.end_behavior is not DirectMotionEndBehavior.CONTINUE:
        return (), ()
    cut = max(beat.end_ms for beat in plan.beats)
    primary_motion = _subject(plan.motion_contract.primary_motion)
    fragments = []
    for beat in plan.beats:
        fragments.extend((
            (beat.primary_action, beat.end_ms, beat.beat_id + ".primary_action"),
            (beat.observable_end_state, beat.end_ms, beat.beat_id + ".observable_end_state"),
        ))
        for step in beat.steps:
            fragments.extend((
                (step.action, step.end_ms, step.step_id + ".action"),
                (step.continuity_after, step.end_ms, step.step_id + ".continuity_after"),
            ))
    fragments.extend((d.visible_change, d.end_ms, d.directive_id + ".visible_change")
                     for d in plan.camera_directives)
    fragments.append((plan.final_state.description, cut, "final_state.description"))
    errors, warnings = [], []
    if plan.final_state.final_hold_ms:
        errors.append("continue_motion requires final_hold_ms=0")
    for fragment, end, location in fragments:
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", fragment):
            # An earlier finite phase may stop; only explicit continuation of
            # that stop to the cut, or a terminal stop, contradicts the contract.
            at_cut = end == cut or _THROUGH_CUT.search(sentence)
            global_stop = _GLOBAL_STOP.search(sentence)
            actor_stop = any(
                primary_motion.startswith(_subject(m.group("actor")) + " ")
                for m in _ACTOR_STOP.finditer(sentence)
            )
            if at_cut and (global_stop or actor_stop) and _QUALIFIED_STOP.search(sentence):
                warnings.append(
                    f"Fin à vérifier ({location}) : arrêt qualifié ou temporaire ; "
                    "vérifier quel mouvement reste actif à la coupure."
                )
            elif at_cut and (global_stop or actor_stop):
                errors.append(
                    f"{location}: continue_motion contradicts an explicit stop "
                    "of the remaining motion at the cut"
                )
            elif _ANCHOR.search(sentence) and _CONVERGENCE.search(sentence) and end < cut:
                warnings.append(
                    f"Fin à vérifier ({location}, {end} ms) : un élément rejoint son "
                    "aspect final ; vérifier que le mouvement prévu continue jusqu'à la coupure."
                )
    return tuple(dict.fromkeys(errors)), tuple(dict.fromkeys(warnings))


def canonical_h3_phase_plan(content: str, **recovery_options: object) -> str:
    canonical = canonical_direct_ref2v_action_plan_v4(content, **recovery_options)
    errors, _ = _ending_issues(canonical)
    if errors:
        raise ValueError("invalid H3 Base phase plan: " + " ".join(errors))
    return canonical


def lint_h3_phase_plan(content: str) -> tuple[str, ...]:
    try:
        return _ending_issues(content)[0]
    except (TypeError, ValueError) as error:
        return (str(error),)


def h3_phase_plan_warnings(content: str) -> tuple[str, ...]:
    try:
        _, ending = _ending_issues(content)
    except (TypeError, ValueError):
        return ()
    # Keep structural/camera/dialogue warnings, replace the legacy lexical guard.
    base = (w for w in direct_ref2v_action_plan_warnings_v4(content)
            if not w.startswith("Fin a verifier"))
    return tuple(dict.fromkeys((*base, *ending)))
