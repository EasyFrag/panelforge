"""Strict loader for immutable prompt cookbooks."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from panelforge.domain import CookbookRef


@dataclass(frozen=True, slots=True)
class CookbookSlot:
    slot_id: str
    label: str
    description: str
    subject_label: str | None
    accepted_uses: tuple[str, ...]
    required_uses: tuple[str, ...]
    required_shots: tuple[int, ...]
    minimum_references: int
    maximum_references: int


@dataclass(frozen=True, slots=True)
class PromptCookbook:
    reference: CookbookRef
    display_name: str
    description: str
    target_mode: str
    output_contract: str
    preset: str
    stages: tuple[str, ...]
    require_distinct_references: bool
    sources: tuple[str, ...]
    slots: tuple[CookbookSlot, ...]
    reference_plan_system_prompt: str | None
    reference_plan_user_prompt: str | None
    beat_sheet_system_prompt: str | None
    beat_sheet_user_prompt: str | None
    beat_sheet_reconcile_system_prompt: str | None
    beat_sheet_reconcile_user_prompt: str | None
    final_prompt_system_prompt: str
    final_prompt_user_prompt: str
    revision_system_prompt: str
    revision_user_prompt: str


class LocalPromptCookbookCatalog:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def list(self) -> tuple[PromptCookbook, ...]:
        if not self._root.is_dir():
            return ()
        cookbooks = [
            self._load(directory)
            for directory in self._root.glob("*/*")
            if directory.is_dir() and (directory / "manifest.json").is_file()
        ]
        return tuple(
            sorted(
                cookbooks,
                key=lambda item: (item.reference.cookbook_id, item.reference.version),
            )
        )

    def get(self, cookbook_id: str, version: str) -> PromptCookbook:
        for cookbook in self.list():
            if (
                cookbook.reference.cookbook_id == cookbook_id
                and cookbook.reference.version == version
            ):
                return cookbook
        raise KeyError((cookbook_id, version))

    def _load(self, directory: Path) -> PromptCookbook:
        manifest_path = directory / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid cookbook manifest: {manifest_path}") from error
        expected = {
            "schema_version",
            "cookbook_id",
            "version",
            "display_name",
            "description",
            "target_mode",
            "output_contract",
            "preset",
            "stages",
            "require_distinct_references",
            "sources",
            "engine_contract",
            "slots",
            "templates",
        }
        if not isinstance(manifest, dict) or set(manifest) != expected:
            raise ValueError(f"invalid cookbook fields: {manifest_path}")
        if manifest["schema_version"] != 2:
            raise ValueError(f"unsupported cookbook schema: {manifest_path}")
        engine = manifest["engine_contract"]
        if not isinstance(engine, dict) or set(engine) != {"id", "version"}:
            raise ValueError(f"invalid engine contract: {manifest_path}")
        raw_slots = manifest["slots"]
        if not isinstance(raw_slots, list) or not raw_slots:
            raise ValueError(f"cookbook slots must not be empty: {manifest_path}")
        slots: list[CookbookSlot] = []
        for raw_slot in raw_slots:
            if not isinstance(raw_slot, dict) or set(raw_slot) != {
                "id",
                "label",
                "description",
                "subject_label",
                "accepted_uses",
                "required_uses",
                "required_shots",
                "minimum_references",
                "maximum_references",
            }:
                raise ValueError(f"invalid cookbook slot: {manifest_path}")
            slot = CookbookSlot(
                slot_id=_text(raw_slot["id"], "slot id"),
                label=_text(raw_slot["label"], "slot label"),
                description=_text(raw_slot["description"], "slot description"),
                subject_label=_optional_text(
                    raw_slot["subject_label"],
                    "subject_label",
                ),
                accepted_uses=_text_list(
                    raw_slot["accepted_uses"],
                    "accepted_uses",
                ),
                required_uses=_text_list(
                    raw_slot["required_uses"],
                    "required_uses",
                ),
                required_shots=_positive_int_list(
                    raw_slot["required_shots"],
                    "required_shots",
                ),
                minimum_references=_positive_int(
                    raw_slot["minimum_references"], "minimum_references"
                ),
                maximum_references=_positive_int(
                    raw_slot["maximum_references"], "maximum_references"
                ),
            )
            if slot.maximum_references < slot.minimum_references:
                raise ValueError("maximum_references must be >= minimum_references")
            if not set(slot.required_uses).issubset(slot.accepted_uses):
                raise ValueError("required_uses must be included in accepted_uses")
            slots.append(slot)
        if len({slot.slot_id for slot in slots}) != len(slots):
            raise ValueError(f"cookbook slots must have unique IDs: {manifest_path}")
        templates = manifest["templates"]
        stages = _text_list(manifest["stages"], "stages")
        supported_stages = {"reference_plan", "beat_sheet", "final_prompt"}
        if not set(stages).issubset(supported_stages) or "final_prompt" not in stages:
            raise ValueError(f"invalid cookbook stages: {manifest_path}")
        if stages not in {
            ("final_prompt",),
            ("beat_sheet", "final_prompt"),
            ("reference_plan", "beat_sheet", "final_prompt"),
        }:
            raise ValueError(f"unsupported cookbook stage pipeline: {manifest_path}")
        template_keys = {
            "final_prompt_system",
            "final_prompt_user",
            "revision_system",
            "revision_user",
        }
        if "reference_plan" in stages:
            template_keys |= {"reference_plan_system", "reference_plan_user"}
        if "beat_sheet" in stages:
            template_keys |= {"beat_sheet_system", "beat_sheet_user"}
        reconciliation_keys = {
            "beat_sheet_reconcile_system",
            "beat_sheet_reconcile_user",
        }
        if not isinstance(templates, dict) or frozenset(templates) not in {
            frozenset(template_keys),
            frozenset(template_keys | reconciliation_keys),
        }:
            raise ValueError(f"invalid cookbook templates: {manifest_path}")
        raw_sources = manifest["sources"]
        if not isinstance(raw_sources, list) or not raw_sources:
            raise ValueError(f"cookbook sources must not be empty: {manifest_path}")
        sources = tuple(_text(value, "cookbook source") for value in raw_sources)

        def load_template(key: str) -> str:
            filename = _text(templates[key], f"template {key}")
            path = (directory / filename).resolve()
            if directory.resolve() not in path.parents or not path.is_file():
                raise ValueError(f"invalid cookbook template path: {filename}")
            content = path.read_text(encoding="utf-8").strip()
            return _text(content, f"template {key}")

        def optional_template(key: str) -> str | None:
            return load_template(key) if key in templates else None

        reference = CookbookRef(
            cookbook_id=_text(manifest["cookbook_id"], "cookbook_id"),
            version=_text(manifest["version"], "version"),
            engine_contract_id=_text(engine["id"], "engine contract id"),
            engine_contract_version=_text(engine["version"], "engine contract version"),
        )
        if directory.parent.name != reference.cookbook_id or directory.name != reference.version:
            raise ValueError(f"cookbook identity does not match its path: {manifest_path}")
        return PromptCookbook(
            reference=reference,
            display_name=_text(manifest["display_name"], "display_name"),
            description=_text(manifest["description"], "description"),
            target_mode=_text(manifest["target_mode"], "target_mode"),
            output_contract=_text(manifest["output_contract"], "output_contract"),
            preset=_text(manifest["preset"], "preset"),
            stages=stages,
            require_distinct_references=_boolean(
                manifest["require_distinct_references"],
                "require_distinct_references",
            ),
            sources=sources,
            slots=tuple(slots),
            reference_plan_system_prompt=optional_template("reference_plan_system"),
            reference_plan_user_prompt=optional_template("reference_plan_user"),
            beat_sheet_system_prompt=optional_template("beat_sheet_system"),
            beat_sheet_user_prompt=optional_template("beat_sheet_user"),
            beat_sheet_reconcile_system_prompt=optional_template(
                "beat_sheet_reconcile_system"
            ),
            beat_sheet_reconcile_user_prompt=optional_template(
                "beat_sheet_reconcile_user"
            ),
            final_prompt_system_prompt=load_template("final_prompt_system"),
            final_prompt_user_prompt=load_template("final_prompt_user"),
            revision_system_prompt=load_template("revision_system"),
            revision_user_prompt=load_template("revision_user"),
        )


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _text(value, name)


def _text_list(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty list")
    items = tuple(_text(item, name) for item in value)
    if len(items) != len(set(items)):
        raise ValueError(f"{name} must not contain duplicates")
    return items


def _positive_int_list(value: object, name: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty list")
    items = tuple(_positive_int(item, name) for item in value)
    if len(items) != len(set(items)):
        raise ValueError(f"{name} must not contain duplicates")
    if items != tuple(sorted(items)):
        raise ValueError(f"{name} must be sorted")
    return items


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value
