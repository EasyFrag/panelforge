from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.domain import (
    CompositionRevision,
    CompositionStage,
    CookbookBinding,
    CookbookRef,
    PromptComposition,
    RevisionOrigin,
    StageDocument,
)
from panelforge.infrastructure.storage import (
    LocalPromptCompositionStore,
    StorageCorruptionError,
)


class SequenceClock:
    def __init__(self) -> None:
        self._values = iter(
            (
                datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 8, 8, 10, 1, tzinfo=timezone.utc),
            )
        )

    def __call__(self) -> datetime:
        return next(self._values)


def sample_composition() -> PromptComposition:
    reference_plan = StageDocument(
        stage=CompositionStage.REFERENCE_PLAN,
        revisions=(
            CompositionRevision(
                revision_id="reference-plan-1",
                content="<Subject 1> vient de <Image 1>.",
                origin=RevisionOrigin.MODEL,
                source_ids=("brief-1", "cookbook-1"),
            ),
        ),
        active_revision_id="reference-plan-1",
        approved_revision_id="reference-plan-1",
    )
    beat_sheet = StageDocument(
        stage=CompositionStage.BEAT_SHEET,
        revisions=(
            CompositionRevision(
                revision_id="beat-sheet-1",
                content="0-3 s : les combattants se font face.",
                origin=RevisionOrigin.MODEL,
                source_ids=("reference-plan-1",),
            ),
        ),
        active_revision_id="beat-sheet-1",
        approved_revision_id="beat-sheet-1",
    )
    final_prompt = StageDocument(
        stage=CompositionStage.FINAL_PROMPT,
        revisions=(
            CompositionRevision(
                revision_id="final-prompt-1",
                content="subject_definitions: ...",
                origin=RevisionOrigin.MODEL,
                source_ids=("beat-sheet-1",),
            ),
        ),
        active_revision_id="final-prompt-1",
        approved_revision_id="final-prompt-1",
    )
    return PromptComposition(
        source_session_id="prompt-session-1",
        cookbook=CookbookRef(
            cookbook_id="fighter.arcade-versus",
            version="0.1.0",
            engine_contract_id="minimax.h3.ref2va",
            engine_contract_version="1.0.0",
        ),
        bindings=(
            CookbookBinding("fighter_a", ("reference-1",)),
            CookbookBinding("fighter_b", ("reference-2",)),
            CookbookBinding("arena", ("reference-3",)),
        ),
        reference_plan=reference_plan,
        beat_sheet=beat_sheet,
        final_prompt=final_prompt,
    )


class LocalPromptCompositionStoreTest(unittest.TestCase):
    def test_compare_and_save_rejects_a_stale_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalPromptCompositionStore(directory)
            initial = sample_composition()
            store.create(initial)
            first = initial.with_bindings(
                (
                    CookbookBinding("fighter_a", ("reference-3",)),
                    CookbookBinding("fighter_b", ("reference-2",)),
                    CookbookBinding("arena", ("reference-1",)),
                )
            )
            store.save_if_current(initial, first)

            with self.assertRaisesRegex(ValueError, "changed concurrently"):
                store.save_if_current(initial, initial)

            self.assertEqual(store.get(initial.source_session_id), first)

    def test_round_trip_create_and_save_preserves_creation_time(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalPromptCompositionStore(directory, clock=SequenceClock())
            composition = sample_composition()

            store.create(composition)
            changed = composition.update_document(
                composition.final_prompt.add_revision(
                    CompositionRevision(
                        revision_id="final-prompt-2",
                        content="subject_definitions: revised",
                        origin=RevisionOrigin.MANUAL,
                        source_ids=("beat-sheet-1",),
                        parent_revision_id="final-prompt-1",
                    )
                )
            )
            store.save(changed)

            self.assertEqual(store.get(composition.source_session_id), changed)
            path = (
                Path(directory)
                / "prompt_compositions"
                / composition.source_session_id
                / "composition.json"
            )
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["schema_version"], 1)
            self.assertEqual(raw["created_at"], "2026-08-08T10:00:00Z")
            self.assertEqual(raw["updated_at"], "2026-08-08T10:01:00Z")
            self.assertEqual(raw["bindings"][0]["slot_id"], "fighter_a")
            self.assertEqual(
                raw["final_prompt"]["revisions"][1]["origin"],
                "manual",
            )

    def test_rejects_unknown_or_invalid_nested_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalPromptCompositionStore(directory)
            composition = sample_composition()
            store.create(composition)
            path = (
                Path(directory)
                / "prompt_compositions"
                / composition.source_session_id
                / "composition.json"
            )
            original = json.loads(path.read_text(encoding="utf-8"))

            with self.subTest("unknown top-level field"):
                raw = dict(original)
                raw["unexpected"] = True
                path.write_text(json.dumps(raw), encoding="utf-8")
                with self.assertRaisesRegex(StorageCorruptionError, "fields"):
                    store.get(composition.source_session_id)

            with self.subTest("wrong document stage"):
                raw = json.loads(json.dumps(original))
                raw["reference_plan"]["stage"] = "beat_sheet"
                path.write_text(json.dumps(raw), encoding="utf-8")
                with self.assertRaisesRegex(StorageCorruptionError, "metadata"):
                    store.get(composition.source_session_id)

    def test_rejects_traversal_and_corrupt_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalPromptCompositionStore(directory)
            with self.assertRaisesRegex(ValueError, "unsafe"):
                store.get("../escape")

            composition = sample_composition()
            store.create(composition)
            path = (
                Path(directory)
                / "prompt_compositions"
                / composition.source_session_id
                / "composition.json"
            )
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["source_session_id"] = "another-session"
            path.write_text(json.dumps(raw), encoding="utf-8")

            with self.assertRaisesRegex(StorageCorruptionError, "identity"):
                store.get(composition.source_session_id)


if __name__ == "__main__":
    unittest.main()
