"""Small variety ledger for Petits hommes using the ordinary H3 Plan/Writer.

No causal action references or protected Writer tokens belong to this contract.
Literal object mentions establish traceability, not visual effectiveness.
"""
import json
import re

from pydantic import Field

from panelforge.domain.little_men_variety import MECHANISM_FAMILIES, validate_selection
from .little_men_causal import ChosenObject as _ChosenObject, VarietyChoice as _VarietyChoice, validate_no_umbrella


class ChosenObject(_ChosenObject):
    name: str = Field(min_length=1, max_length=120,
                      description="English object name. Use this exact name in the action where it is used. "
                                  "The giant hand is not an accessory.")


class VarietyChoice(_VarietyChoice):
    objects: tuple[ChosenObject, ...] = Field(
        description="Distinct accessories actually used and named in the actions. "
                    "Empty for direct hand action alone. Do not list unused alternatives.")
    mechanism_family: str = Field(
        min_length=1, json_schema_extra={"enum": list(MECHANISM_FAMILIES)},
        description="The main physical operation shown by the Plan's actual actions. "
                    "Classify the decisive useful change, not preparatory gestures or the general goal.",
    )


def validate_variety_choice(plan, selection=None) -> None:
    """Check a declared choice against ordinary actions and its frozen assortment."""
    value = plan.model_dump(mode="json") if hasattr(plan, "model_dump") else plan
    choice = VarietyChoice.model_validate(value["variety_choice"])
    if selection is not None:
        validate_selection(selection)
        if any(obj.catalog_id not in selection["candidates"] for obj in choice.objects) and not choice.departure_reason:
            raise ValueError("Expliquez pourquoi l’intervention exige un objet hors de l’assortiment proposé.")
    actions = " ".join(action for shot in value["shots"] for phase in shot["phases"]
                       for action in phase["actions"]).casefold()
    validate_chosen_objects(choice, actions)
    validate_no_umbrella(json.dumps(choice.model_dump(mode="json"), ensure_ascii=False))


def validate_chosen_objects(choice, content: str) -> None:
    """Retain the selected object names without freezing the Writer's prose."""
    if not isinstance(choice, VarietyChoice):
        choice = VarietyChoice.model_validate(choice)
    for obj in choice.objects:
        name = obj.name.casefold()
        plural = "(?:es)?" if name.endswith(("s", "x", "z", "ch", "sh")) else "s?"
        if not re.search(r"(?<!\w)" + re.escape(name) + plural + r"(?!\w)", content.casefold()):
            raise ValueError("Conservez le nom de chaque objet choisi dans les actions du Plan et du Prompt.")


def validate_plan(plan, context) -> None:
    value = plan.model_dump(mode="json") if hasattr(plan, "model_dump") else plan
    validate_no_umbrella(json.dumps(value, ensure_ascii=False))
    if "variety_choice" in value:
        selection = context.get("variety_selection")
        if selection is None:
            raise ValueError("L’assortiment Petits hommes experimental est absent du contexte approuvé.")
        validate_variety_choice(value, selection)
