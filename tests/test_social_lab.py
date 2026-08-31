import json
from pathlib import Path
import tempfile
import unittest

from panelforge.application import (
    CompletionResult,
    CompletionStreamEvent,
    ModelDescriptor,
    SocialLabService,
    StreamEventKind,
    StreamPhase,
    parse_social_response,
)
from panelforge.domain import SocialLanguage
from panelforge.infrastructure.storage import LocalAssetStore, LocalSocialLabStore


PNG = b"\x89PNG\r\n\x1a\n" + b"social-frame"
MP4 = b"\x00\x00\x00\x18ftypisom" + b"social-video"


def response(prefix):
    return json.dumps({
        "message": f"{prefix} proposals are ready.",
        "variants": [
            {
                "angle": f"{prefix} angle {index}",
                "hook": f"{prefix} hook {index}",
                "caption": f"{prefix} caption {index}",
                "hashtags": [f"#tag{index}", "#video"],
                "emojis": ["✨", "🎬"],
            }
            for index in range(1, 4)
        ],
    })


class Gateway:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def list_models(self):
        return (ModelDescriptor("Qwen3.8-27B"),)

    def stream(self, request):
        self.requests.append(request)
        content = next(self.responses)
        if request.include_reasoning:
            yield CompletionStreamEvent(
                StreamEventKind.REASONING,
                StreamPhase.GENERATING,
                text="editorial trace",
            )
        yield CompletionStreamEvent(
            StreamEventKind.DELTA,
            StreamPhase.GENERATING,
            text=content,
        )
        yield CompletionStreamEvent(
            StreamEventKind.COMPLETED,
            StreamPhase.COMPLETED,
            result=CompletionResult(
                request.model_id,
                content,
                call_id=f"call-{len(self.requests)}",
            ),
        )


class SocialLabServiceTest(unittest.TestCase):
    def test_parser_closes_only_missing_final_json_containers(self):
        raw = response("Recovered")[:-1]

        message, variants = parse_social_response(raw, expected_count=3)

        self.assertEqual(message, "Recovered proposals are ready.")
        self.assertEqual(len(variants), 3)
        self.assertEqual(variants[-1].hook, "Recovered hook 3")

    def test_parser_does_not_repair_an_unterminated_json_string(self):
        with self.assertRaisesRegex(ValueError, "not valid JSON"):
            parse_social_response(
                '{"message":"unfinished',
                expected_count=3,
            )

    def test_four_keyframes_profiles_and_complete_conversation_are_persisted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = LocalAssetStore(root)
            video = assets.create(MP4, media_type="video/mp4")
            frames = tuple(
                assets.create(PNG + bytes([index]), media_type="image/png").asset_id
                for index in range(4)
            )
            gateway = Gateway((response("First"), response("Second")))
            store = LocalSocialLabStore(root)
            turn_ids = iter(("turn-user-1", "turn-assistant-1", "turn-user-2", "turn-assistant-2"))
            service = SocialLabService(
                gateway=gateway,
                assets=assets,
                projects=store,
                source_prompt_resolver=lambda _asset: "A duckling waits for a bus.",
                project_id_factory=lambda: "social-test",
                profile_id_factory=lambda: "channel-test",
                turn_id_factory=turn_ids.__next__,
            )
            profile = service.save_profile(
                profile_id=None,
                name="Cute stories",
                language=SocialLanguage.ENGLISH,
                mood="Warm comedy",
                vibe="Cinematic deadpan",
                example="Tiny animals, very serious problems.",
                instructions="Never use generic engagement bait.",
            )
            project = service.create_project(
                name="Duck at the bus stop",
                model_id="Qwen3.8-27B",
                language=SocialLanguage.ENGLISH,
                variant_count=3,
                video_asset_id=video.asset_id,
                video_filename="duck.mp4",
                keyframe_asset_ids=frames,
                mood=profile.mood,
                vibe=profile.vibe,
                example=profile.example,
                instructions=profile.instructions,
                channel_profile_id=profile.profile_id,
            )

            first = list(service.stream_chat(
                project.project_id,
                "Create the first publication options.",
                include_reasoning=True,
            ))
            project = first[-1].project
            self.assertIsNotNone(project)
            self.assertEqual(len(project.latest_variants), 3)
            self.assertEqual(gateway.requests[0].max_tokens, 64_000)
            self.assertEqual(len(gateway.requests[0].images), 4)
            self.assertEqual(
                [image.label for image in gateway.requests[0].images],
                [
                    "VIDEO KEYFRAME 1 · 10%",
                    "VIDEO KEYFRAME 2 · 35%",
                    "VIDEO KEYFRAME 3 · 65%",
                    "VIDEO KEYFRAME 4 · 90%",
                ],
            )
            self.assertIn("TARGET LANGUAGE: English", gateway.requests[0].user_prompt)
            self.assertIn("A duckling waits for a bus.", gateway.requests[0].user_prompt)

            second = list(service.stream_chat(
                project.project_id,
                "Make every hook shorter.",
            ))
            project = second[-1].project
            self.assertEqual(len(project.turns), 4)
            self.assertIn("First hook 1", gateway.requests[1].user_prompt)
            self.assertIn("Make every hook shorter.", gateway.requests[1].user_prompt)

            reopened = LocalSocialLabStore(root).get_project(project.project_id)
            self.assertEqual(reopened.latest_variants[0].hook, "Second hook 1")
            self.assertEqual(
                LocalSocialLabStore(root).get_profile(profile.profile_id).vibe,
                "Cinematic deadpan",
            )

    def test_variant_count_may_change_during_a_long_conversation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = LocalAssetStore(root)
            video = assets.create(MP4, media_type="video/mp4")
            frames = tuple(
                assets.create(PNG + bytes([index]), media_type="image/png").asset_id
                for index in range(4)
            )
            two_variants = json.loads(response("Next"))
            two_variants["variants"] = two_variants["variants"][:2]
            gateway = Gateway((response("First"), json.dumps(two_variants)))
            service = SocialLabService(
                gateway=gateway,
                assets=assets,
                projects=LocalSocialLabStore(root),
            )
            project = service.create_project(
                name="Changing count",
                model_id="Qwen3.8-27B",
                language=SocialLanguage.ENGLISH,
                variant_count=3,
                video_asset_id=video.asset_id,
                video_filename="video.mp4",
                keyframe_asset_ids=frames,
            )
            project = list(service.stream_chat(project.project_id, "Start"))[-1].project
            project = list(service.stream_chat(
                project.project_id,
                "Keep only two approaches.",
                variant_count=2,
            ))[-1].project
            self.assertEqual(project.variant_count, 2)
            self.assertEqual(len(project.latest_variants), 2)
            self.assertEqual(len(project.turns[-3].variants), 3)


if __name__ == "__main__":
    unittest.main()
