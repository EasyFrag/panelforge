import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panelforge.infrastructure.instance_info import capture_instance_info


class InstanceInfoTests(unittest.TestCase):
    def test_identity_records_source_workspace_and_local_edits_without_private_data(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "src/panelforge/example.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n", encoding="utf-8")
            (root / "pyproject.toml").write_text('[project]\nname = "example"\n', encoding="utf-8")
            private = root / ".env"
            private.write_text("SECRET=private-value", encoding="utf-8")
            workspace = root / "workspace"
            workspace.mkdir()
            runtime = workspace / "runtime.json"
            runtime.write_text("{}", encoding="utf-8")

            def git(*args, **kwargs):
                command = args[0]
                output = " M src/panelforge/example.py" if "status" in command else "test-version"
                return subprocess.CompletedProcess(command, 0, output, "")

            with patch("panelforge.infrastructure.instance_info.subprocess.run", side_effect=git):
                first = capture_instance_info(root, workspace)
                private.write_text("SECRET=changed", encoding="utf-8")
                runtime.write_text('{"changed": true}', encoding="utf-8")
                second = capture_instance_info(root, workspace)
                source.write_text("value = 2\n", encoding="utf-8")
                third = capture_instance_info(root, workspace)

            self.assertEqual(first["source_root"], str(root))
            self.assertEqual(first["workspace"], str(workspace))
            self.assertEqual(first["pid"], os.getpid())
            self.assertTrue(first["git_modified"])
            self.assertEqual(first["git_commit"], "test-version")
            self.assertEqual(len(first["source_sha256"]), 64)
            self.assertEqual(first["source_sha256"], second["source_sha256"])
            self.assertNotEqual(first["source_sha256"], third["source_sha256"])
            self.assertNotIn("SECRET", str(first))

    def test_git_missing_or_timed_out_does_not_prevent_startup(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired("git", 3)):
            with self.subTest(error=type(error).__name__), TemporaryDirectory() as directory:
                with patch("panelforge.infrastructure.instance_info.subprocess.run", side_effect=error):
                    info = capture_instance_info(directory, Path(directory) / "workspace")
                self.assertIsNone(info["git_commit"])
                self.assertIsNone(info["git_branch"])
                self.assertIsNone(info["git_modified"])
                self.assertIsNone(info["source_sha256"])
                self.assertIsNotNone(info["started_at"])
