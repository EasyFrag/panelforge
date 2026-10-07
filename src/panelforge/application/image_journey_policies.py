"""Resolve a saved journey version without changing historical prompt policies."""
from panelforge.domain.image_journeys import journey_version, journey_direction
from . import image_journey_prompting as v1
from . import image_journey_edit_prompting as manual_v1
from . import image_journey_v2_prompting as v2
from .image_journey_reverse_prompting import REVERSE_POLICIES


def progression(record):
    if journey_direction(record) == "reverse":
        return REVERSE_POLICIES[journey_version(record)]
    return v2 if journey_version(record) == "2" else v1


def manual(record):
    if journey_direction(record) == "reverse":
        return REVERSE_POLICIES[journey_version(record)]
    return v2 if journey_version(record) == "2" else manual_v1


def edit_request(step):
    return progression(step).edit_request(step)
