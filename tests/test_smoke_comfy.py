import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.smoke_comfy import (
    find_first_image,
    save_output,
    validate_png,
    wait_for_history,
)


class FakeHistoryClient:
    def __init__(self, responses):
        self._responses = iter(responses)

    def get_history(self, prompt_id):
        return next(self._responses)


class SmokeComfyTest(unittest.TestCase):
    @patch("scripts.smoke_comfy.time.sleep")
    def test_wait_for_history_accepts_empty_history_then_success(self, sleep):
        prompt_id = "prompt-123"
        completed_run = {
            "status": {
                "status_str": "success",
                "completed": True,
            },
            "outputs": {},
        }
        client = FakeHistoryClient([{}, {prompt_id: completed_run}])

        result = wait_for_history(
            client,
            prompt_id,
            run_timeout=10,
            poll_interval=1,
        )

        self.assertIs(result, completed_run)
        sleep.assert_called_once()

    def test_wait_for_history_rejects_a_terminal_error(self):
        prompt_id = "prompt-123"
        failed_run = {
            "status": {
                "status_str": "error",
                "completed": True,
                "messages": ["model failed"],
            }
        }
        client = FakeHistoryClient([{prompt_id: failed_run}])

        with self.assertRaisesRegex(RuntimeError, "model failed"):
            wait_for_history(
                client,
                prompt_id,
                run_timeout=10,
                poll_interval=1,
            )

    def test_find_first_image_returns_the_comfy_reference(self):
        run = {
            "outputs": {
                "12": {"text": ["ignored"]},
                "15": {
                    "images": [
                        {
                            "filename": "candidate.png",
                            "subfolder": "characters",
                            "type": "output",
                        }
                    ]
                },
            }
        }

        node_id, image = find_first_image(run)

        self.assertEqual(node_id, "15")
        self.assertEqual(
            image,
            {
                "filename": "candidate.png",
                "subfolder": "characters",
                "type": "output",
            },
        )

    def test_find_first_image_rejects_a_run_without_images(self):
        with self.assertRaisesRegex(ValueError, "does not contain an image"):
            find_first_image({"outputs": {"12": {"text": ["no image"]}}})

    def test_validate_png_rejects_non_png_content(self):
        with self.assertRaisesRegex(ValueError, "not a PNG"):
            validate_png(b"not-an-image")

    def test_save_output_writes_once_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "candidate.png"

            save_output(output_path, b"image-content")

            self.assertEqual(output_path.read_bytes(), b"image-content")
            with self.assertRaises(FileExistsError):
                save_output(output_path, b"replacement")


if __name__ == "__main__":
    unittest.main()
