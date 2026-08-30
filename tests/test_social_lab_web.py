import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from panelforge.application import ChangeViewRunner, SocialLabService
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.presets import ChangeViewPresetRecipe, load_change_view_preset
from panelforge.infrastructure.storage import LocalAssetStore, LocalRunStore, LocalSocialLabStore
from tests.test_social_lab import Gateway, MP4, PNG, response


ROOT = Path(__file__).resolve().parents[1]
CHANGE_VIEW = ROOT / "workflows" / "character.change_view" / "qwen-edit-2511-multiple-angles" / "0.2.0"


class UploadOnlyComfy:
    def upload_image(self, *_args, **_kwargs):
        return type("Uploaded", (), {"workflow_value": "unused.png"})()


def decode_sse(text):
    values = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(
            line[5:].lstrip()
            for line in block.splitlines()
            if line.startswith("data:")
        )
        if data:
            values.append(json.loads(data))
    return values


class SocialLabWebTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        assets = LocalAssetStore(root)
        runner = ChangeViewRunner(
            recipe=ChangeViewPresetRecipe(load_change_view_preset(CHANGE_VIEW)),
            comfy=UploadOnlyComfy(),
            assets=assets,
            runs=LocalRunStore(root),
        )
        self.gateway = Gateway((response("Web"),))
        social = SocialLabService(
            gateway=self.gateway,
            assets=assets,
            projects=LocalSocialLabStore(root),
            source_prompt_resolver=lambda _asset: "Known H3 source prompt.",
            project_id_factory=lambda: "social-web",
            profile_id_factory=lambda: "channel-web",
            turn_id_factory=iter(("turn-web-user", "turn-web-assistant")).__next__,
        )
        self.client = TestClient(create_app(runner, social_lab=social))

    def tearDown(self):
        self.client.close()
        self.temporary.cleanup()

    def test_profile_project_upload_and_conversational_stream(self):
        spec = self.client.get("/api/social-lab/spec")
        self.assertEqual(spec.status_code, 200)
        self.assertEqual(spec.json()["defaults"]["variant_count"], 3)
        self.assertEqual(spec.json()["defaults"]["language"], "en")
        self.assertEqual(spec.json()["defaults"]["keyframe_positions"], [10, 35, 65, 90])

        saved = self.client.post("/api/social-lab/profiles", json={
            "name": "Animal stories",
            "language": "en",
            "mood": "Cute",
            "vibe": "Deadpan",
            "example": "Small hero, big problem.",
            "instructions": "No clickbait.",
        })
        self.assertEqual(saved.status_code, 201, saved.text)
        profile_id = saved.json()["profile"]["profile_id"]

        files = [
            ("video", ("duck.mp4", MP4, "video/mp4")),
            *[
                ("keyframes", (f"frame-{index}.jpg", PNG + bytes([index]), "image/jpeg"))
                for index in range(4)
            ],
        ]
        created = self.client.post(
            "/api/social-lab/projects",
            data={
                "name": "Duck reel",
                "model_id": "Qwen3.8-27B",
                "language": "en",
                "variant_count": "3",
                "mood": "Cute",
                "vibe": "Deadpan",
                "example": "Small hero, big problem.",
                "instructions": "No clickbait.",
                "channel_profile_id": profile_id,
            },
            files=files,
        )
        self.assertEqual(created.status_code, 201, created.text)
        project = created.json()["project"]
        self.assertEqual(len(project["keyframes"]), 4)
        self.assertTrue(project["source_prompt_found"])

        streamed = self.client.post(
            f"/api/social-lab/projects/{project['project_id']}/chat/stream?include_reasoning=true",
            json={"message": "Create three options."},
        )
        self.assertEqual(streamed.status_code, 200, streamed.text)
        events = decode_sse(streamed.text)
        self.assertTrue(any(event["kind"] == "reasoning" for event in events))
        terminal = events[-1]["project"]
        self.assertEqual(len(terminal["latest_variants"]), 3)
        self.assertEqual(len(terminal["turns"]), 2)
        self.assertTrue(terminal["video_url"])

        reopened = self.client.get(f"/api/social-lab/projects/{project['project_id']}")
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(reopened.json()["project"]["latest_variants"][0]["hook"], "Web hook 1")


if __name__ == "__main__":
    unittest.main()
