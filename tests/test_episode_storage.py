"""User-run storage regressions; temporary documents only."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from panelforge.infrastructure.storage.episodes import LocalEpisodeStore
from panelforge.infrastructure.storage.local import StorageCorruptionError


class EpisodeStorageTest(unittest.TestCase):
    def test_missing_copy_raises_file_not_found_without_creating_a_document(self):
        with TemporaryDirectory() as folder:
            store = LocalEpisodeStore(folder)
            identity = "episode-" + "a" * 32
            with self.assertRaises(FileNotFoundError):
                store.get(identity)
            self.assertFalse((Path(folder) / "episodes").exists())
            saved = store.save(dict(episode_id=identity, title="English copy"))
            self.assertEqual(store.get(identity), saved)

    def test_existing_invalid_json_remains_corruption_and_is_never_overwritten(self):
        with TemporaryDirectory() as folder:
            store = LocalEpisodeStore(folder)
            store.root.mkdir()
            path = store.root / ("episode-" + "a" * 32 + ".json")
            original = b'{"schema_version": 1, "unfinished":'
            path.write_bytes(original)
            with self.assertRaisesRegex(StorageCorruptionError, "invalid JSON"):
                store.get(path.stem)
            self.assertEqual(path.read_bytes(), original)
