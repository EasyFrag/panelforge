"""Offline contracts for protected speech and the optional H3 Chinese variant."""

from copy import deepcopy
import json
import tempfile
import unittest

from fastapi.testclient import TestClient

from panelforge.application import StreamEventKind
from panelforge.application.dialogue_placeholders import DialoguePlaceholders
from panelforge.application.vocal_policy import speech_lines
from panelforge.domain import CompositionStage
from panelforge.domain.video_preparation import ClassicCinematicSettings
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.storage import LocalPromptCompositionStore
from tests import test_combat_preparation as render_fixtures
from tests.test_classic_cinematic import fixture
from tests.test_video_preparation_recipes import preparation_service


class H3ChineseVariantTest(unittest.TestCase):
    def test_placeholder_roundtrip_restores_escaped_json_without_model_copying(self):
        lines = (
            'Elle dit : "reste ici".',
            "다시 만나자.",
        )
        placeholders = DialoguePlaceholders.from_lines(lines)
        source = json.dumps(
            {"spoken_lines": list(lines), "action": f"She says {lines[0]}"},
            ensure_ascii=False,
        )

        protected = placeholders.protect(source)
        restored = json.loads(placeholders.restore(protected))

        self.assertTrue(placeholders.active)
        self.assertNotIn(lines[0], protected)
        self.assertNotIn(lines[1], protected)
        self.assertEqual(restored["spoken_lines"], list(lines))
        self.assertEqual(restored["action"], f"She says {lines[0]}")

    def test_korean_dialogue_is_opaque_during_plan_and_writer_then_restored(self):
        line = "10만 원만 더 내면 끝내주게 해줄게요. 어때요?"
        plan, _, _ = fixture()
        plan = deepcopy(plan)
        plan["spoken_lines"] = [line]
        plan["spoken_languages"] = ["Korean"]
        plan["shots"][0]["phases"][0]["actions"].append(
            f"The masseuse speaks <d>[Korean] {line}</d> while holding her pose."
        )
        writer = {
            "shots": [
                {"phases": [" ".join(phase["actions"]) for phase in shot["phases"]]}
                for shot in plan["shots"]
            ],
            "overall_soundscape": plan["overall_soundscape"],
            "non_diegetic_music": plan["non_diegetic_music"],
        }
        placeholders = DialoguePlaceholders.from_lines((line,))
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, session, _ = preparation_service(
                directory,
                "ref2v",
                "planned",
                [
                    placeholders.protect(json.dumps(plan, ensure_ascii=False)),
                    placeholders.protect(json.dumps(writer, ensure_ascii=False)),
                ],
                version="1.0.0",
                preparation_family="classic",
                cinematic_settings=ClassicCinematicSettings(2),
                source_text=f'La masseuse dit exactement : "{line}" dans une scène de 8 secondes.',
            )

            planned = service.generate(session.session_id, CompositionStage.BEAT_SHEET)
            self.assertNotIn(line, gateway.requests[0].user_prompt)
            self.assertIn("__PF_SPEECH_", gateway.requests[0].user_prompt)
            self.assertIn("PROTECTED SPEECH TOKENS", gateway.requests[0].system_prompt)
            self.assertEqual(
                json.loads(planned.beat_sheet.active_revision.content)["spoken_lines"],
                [line],
            )
            service.approve(session.session_id, CompositionStage.BEAT_SHEET)
            completed = service.generate(session.session_id, CompositionStage.FINAL_PROMPT)

            self.assertNotIn(line, gateway.requests[1].user_prompt)
            self.assertIn("__PF_SPEECH_", gateway.requests[1].user_prompt)
            self.assertEqual(
                tuple(text for _, text in speech_lines(completed.final_prompt.active_revision.content)),
                (line,),
            )

    def test_chinese_variant_is_persisted_beside_english_and_opens_its_own_render(self):
        plan, writer, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, session, _ = preparation_service(
                directory,
                "fl2va",
                "planned",
                [json.dumps(plan), json.dumps(writer)],
                version="1.0.0",
                preparation_family="classic",
                cinematic_settings=ClassicCinematicSettings(2),
                source_text="A quiet object reveal in eight seconds. No speech.",
                roles=("first_frame", "last_frame"),
            )
            service.generate(session.session_id, CompositionStage.BEAT_SHEET)
            service.approve(session.session_id, CompositionStage.BEAT_SHEET)
            english_composition = service.generate(
                session.session_id, CompositionStage.FINAL_PROMPT
            )
            service.approve(session.session_id, CompositionStage.FINAL_PROMPT)
            english = english_composition.final_prompt.active_revision.content
            chinese = english.replace("The", "这个", 1)
            gateway.responses = iter((chinese,))

            events = list(service.stream_generate_chinese_variant(
                session.session_id,
                "local::unsloth/gemma-4-31B-it-qat-GGUF",
            ))

            self.assertEqual(events[-1].kind, StreamEventKind.COMPLETED)
            completed = events[-1].composition
            variant = completed.prompt_variant(
                completed.final_prompt.active_revision_id, "zh"
            )
            self.assertEqual(completed.final_prompt.active_revision.content, english)
            self.assertEqual(variant.content, chinese)
            self.assertEqual(gateway.requests[-1].images, ())
            self.assertIn("APPROVED PLAN", gateway.requests[-1].user_prompt)
            self.assertEqual(
                LocalPromptCompositionStore(directory).get(session.session_id)
                .prompt_variant(variant.source_revision_id, "zh"),
                variant,
            )

            renders = render_fixtures.CombatRenderTest().service(directory)
            renders.sessions = service.sessions
            renders.compositions = service.compositions
            english_project = renders.get_or_create_from_session(session.session_id)
            chinese_project = renders.get_or_create_from_session(
                session.session_id, prompt_language="zh"
            )
            self.assertNotEqual(english_project.project_id, chinese_project.project_id)
            self.assertEqual(english_project.current_prompt, english)
            self.assertEqual(chinese_project.current_prompt, chinese)
            self.assertTrue(chinese_project.source_prompt_revision_id.startswith("zh:"))

    def test_http_stream_exposes_variant_and_language_specific_render_project(self):
        plan, writer, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, session, _ = preparation_service(
                directory,
                "ref2v",
                "planned",
                [json.dumps(plan), json.dumps(writer)],
                version="1.0.0",
                preparation_family="classic",
                cinematic_settings=ClassicCinematicSettings(2),
                source_text="A quiet object reveal in eight seconds. No speech.",
            )
            service.generate(session.session_id, CompositionStage.BEAT_SHEET)
            service.approve(session.session_id, CompositionStage.BEAT_SHEET)
            composition = service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            service.approve(session.session_id, CompositionStage.FINAL_PROMPT)
            english = composition.final_prompt.active_revision.content
            gateway.responses = iter((english.replace("The", "这个", 1),))
            renders = render_fixtures.CombatRenderTest().service(directory)
            renders.sessions = service.sessions
            renders.compositions = service.compositions

            with TestClient(create_app(
                None,
                prompt_composition=service,
                h3_render=renders,
            )) as client:
                translated = client.post(
                    f"/api/prompt-lab/sessions/{session.session_id}"
                    "/composition/final-prompt/variants/zh/stream",
                    json={"model_id": "local::gemma"},
                )
                self.assertEqual(translated.status_code, 200, translated.text)
                self.assertIn('"kind": "completed"', translated.text)
                self.assertIn('"language": "zh"', translated.text)

                opened = client.post(
                    f"/api/h3-render/projects/from-session/{session.session_id}",
                    params={"prompt_language": "zh"},
                )
                self.assertEqual(opened.status_code, 201, opened.text)
                project = opened.json()["project"]
                self.assertEqual(project["prompt_language"], "zh")
                self.assertEqual(project["current_prompt"], english.replace("The", "这个", 1))


if __name__ == "__main__":
    unittest.main()
