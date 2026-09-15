"""Offline regression cases, to run by the user: no real LLM or ComfyUI calls."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.domain import CompositionStage, CookbookBinding, VideoAspectRatio, VideoLabSettings
from panelforge.domain.h3_render import H3RenderAttempt, H3RenderInputMode
from panelforge.domain.video_preparation import ClassicCinematicSettings
from panelforge.infrastructure.presets import Ref2VH3RenderPresetRecipe, VideoLabPresetRecipe, load_video_lab_workflow
from panelforge.infrastructure.presets.h3_loras import MultiLoraH3RenderRecipe
from tests.test_classic_cinematic import fixture
from tests import test_combat_preparation as render_fixtures
from tests.test_video_preparation_recipes import preparation_service


ROLES = (
    "first_frame", "subject_reference", "environment_reference", "style_reference",
    "composition_reference", "motion_reference", "keyframe_reference", "last_frame",
    "subject_reference",
)
REF_WORKFLOW = (Path(__file__).resolve().parents[1] / "workflows" /
                "video.generate.ref2v/minimax-h3-ref2v/0.2.4")


def prepared(directory, roles, *, mode="ref2v", order=None, count=2):
    plan, writer, _ = fixture(count=count)
    service, gateway, session, composition = preparation_service(
        directory, mode, "planned", [json.dumps(plan), json.dumps(writer)],
        roles=roles, source_text="A quiet object reveal lasting 8 seconds. No music or speech.",
        version="1.0.0", cinematic_settings=ClassicCinematicSettings(count),
    )
    if order is not None:
        composition = replace(composition, bindings=(CookbookBinding(
            "references", tuple(session.references[i].reference_id for i in order)),))
    service.compositions.save(replace(composition, writer_model_id="fixture-writer"))
    for stage in (CompositionStage.BEAT_SHEET, CompositionStage.FINAL_PROMPT):
        service.generate(session.session_id, stage)
        service.approve(session.session_id, stage)
    renders = render_fixtures.CombatRenderTest().service(directory)
    renders.sessions, renders.compositions = service.sessions, service.compositions
    renders.ref2v_workflow = MultiLoraH3RenderRecipe(Ref2VH3RenderPresetRecipe(
        VideoLabPresetRecipe(load_video_lab_workflow(REF_WORKFLOW))), REF_WORKFLOW)
    return renders, gateway, session


def misclassified(renders, project, session):
    first = next((r for r in session.references if r.role == "first_frame"), None)
    last = next((r for r in session.references if r.role == "last_frame"), None)
    mode = (H3RenderInputMode.FL2VA if first and last else H3RenderInputMode.I2VA if first
            else H3RenderInputMode.L2VA if last else H3RenderInputMode.T2VA)
    return renders.projects.save(replace(
        project, input_mode=mode, reference_asset_ids=(), reference_labels=(),
        first_frame_asset_id=first.asset_id if first else None,
        first_frame_label=first.label if first else None,
        last_frame_asset_id=last.asset_id if last else None,
        last_frame_label=last.label if last else None,
    ))


class Ref2VClassicRenderBoundaryTest(unittest.TestCase):
    def test_two_calls_keep_roles_grammar_and_render_references(self):
        for roles in (("subject_reference",), ROLES[:2], ROLES):
            for count in (1, 2):
                with self.subTest(roles=roles, shots=count), tempfile.TemporaryDirectory() as directory:
                    renders, gateway, session = prepared(directory, roles, count=count)
                    project = renders.get_or_create_from_session(session.session_id)
                    self.assertEqual(len(gateway.requests), 2)
                    self.assertEqual(gateway.requests[0].model_id, "fixture-model")
                    self.assertEqual(gateway.requests[1].model_id, "fixture-writer")
                    self.assertEqual(len(gateway.requests[0].images), len(roles))
                    self.assertEqual(gateway.requests[1].images, ())
                    for request in gateway.requests:
                        for number, role in enumerate(roles, 1):
                            self.assertIn(f"<Picture {number}>", request.user_prompt)
                            self.assertIn(role, request.user_prompt)
                    self.assertIn("PLAN TO PRESERVE:", gateway.requests[1].user_prompt)
                    self.assertNotIn("integrated_multimodal_description:", project.current_prompt)
                    self.assertIn("Shot 1:" if count == 1 else "[Shot 2] At 00:04.000,", project.current_prompt)
                    self.assertIn("overall_soundscape:", project.current_prompt)
                    self.assertEqual(project.input_mode, H3RenderInputMode.REF2VA)
                    self.assertEqual(project.reference_asset_ids, tuple(r.asset_id for r in session.references))
                    self.assertEqual(project.reference_labels, tuple(r.label for r in session.references))
                    self.assertIsNone(project.first_frame_asset_id)
                    self.assertIsNone(project.last_frame_asset_id)
                    self.assertIs(renders.workflow_for_mode(project.input_mode), renders.ref2v_workflow)
                    self.assertEqual(renders.get_or_create_from_session(session.session_id), project)

    def test_current_render_recipe_accepts_all_nine_references_in_order(self):
        with tempfile.TemporaryDirectory() as directory:
            order = tuple(reversed(range(9)))
            renders, _, session = prepared(directory, ROLES, order=order)
            project = renders.get_or_create_from_session(session.session_id)
            settings = VideoLabSettings(VideoAspectRatio.PORTRAIT_WIDESCREEN, 0.2, 8, 25, 123)
            project = renders.prepare_attempt(project.project_id, prompt=project.current_prompt, settings=settings)
            attempt = project.attempts[-1]
            self.assertEqual(attempt.recipe, renders.ref2v_workflow.reference)
            self.assertEqual(attempt.recipe.version, "0.2.4")
            images = tuple(f"{asset_id}.png" for asset_id in project.reference_asset_ids)
            graph = renders.ref2v_workflow.build_workflow(source_images=images,
                prompt=attempt.effective_prompt, settings=settings,
                output_filename_prefix="video/fixture", keyframe_indices=(0, 191),
                spectrum_enabled=False, video_lora=None)
            target = next(node["inputs"] for node in graph.values()
                          if "ref_images.ref_image_0" in node.get("inputs", {}))
            connected = tuple(graph[str(target[f"ref_images.ref_image_{i}"][0])]["inputs"]["image"]
                              for i in range(9))
            self.assertEqual(connected, tuple(f"{session.references[i].asset_id}.png" for i in order))

    def test_bound_picture_order_and_subset_follow_the_llm_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            renders, gateway, session = prepared(directory, ROLES, order=(4, 1, 0))
            project = renders.get_or_create_from_session(session.session_id)
            selected = tuple(session.references[i] for i in (4, 1, 0))
            self.assertEqual(project.reference_asset_ids, tuple(r.asset_id for r in selected))
            self.assertEqual([image.content for image in gateway.requests[0].images],
                             [renders.assets.read_bytes(r.asset_id) for r in selected])
            for number, reference in enumerate(selected, 1):
                self.assertIn(f"<Picture {number}>", gateway.requests[1].user_prompt)
                self.assertIn(reference.role, gateway.requests[1].user_prompt)
            self.assertNotIn("<Picture 4>", project.current_prompt)

    def test_reopen_repairs_empty_misclassified_project_and_keeps_edits(self):
        for roles in (("subject_reference",), ROLES[:2], ("last_frame",), ROLES):
            with self.subTest(roles=roles), tempfile.TemporaryDirectory() as directory:
                renders, gateway, session = prepared(directory, roles)
                original = renders.get_or_create_from_session(session.session_id)
                original = renders.projects.save(replace(original,
                    revision_model_id="chosen-revision-model", dialogue_level=2,
                    revision_draft="An existing draft", revision_error="An existing error",
                    warnings=("Existing warning",),
                    current_prompt=original.current_prompt.replace(
                        "The target video lasts 8 seconds.",
                        "The target video lasts 8 seconds. Soft dust settles.")))
                misclassified(renders, original, session)
                repaired = renders.get_or_create_from_session(session.session_id)
                self.assertEqual(repaired, original)
                self.assertEqual(len(renders.projects.list()), 1)
                self.assertEqual(len(gateway.requests), 2)
                path = Path(directory) / "h3_render_projects" / repaired.project_id / "project.json"
                saved = path.read_bytes()
                self.assertEqual(renders.get_or_create_from_session(session.session_id), repaired)
                self.assertEqual(path.read_bytes(), saved)

    def test_misclassified_attempt_history_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            renders, _, session = prepared(directory, ROLES[:2])
            project = misclassified(renders, renders.get_or_create_from_session(session.session_id), session)
            attempt = H3RenderAttempt("historical-attempt", 1, project.current_prompt, project.current_prompt,
                VideoLabSettings(VideoAspectRatio.PORTRAIT_WIDESCREEN, 0.2, 8, 25, 123), False, ())
            original = renders.projects.save(replace(project, attempts=(attempt,)))
            with self.assertRaisesRegex(ValueError, "nouvel atelier REF2V"):
                renders.get_or_create_from_session(session.session_id)
            self.assertEqual(renders.projects.get(project.project_id), original)

    def test_h3_input_modes_and_reopening_remain_unchanged(self):
        for roles, mode in (((), H3RenderInputMode.T2VA), (("first_frame",), H3RenderInputMode.I2VA),
                            (("last_frame",), H3RenderInputMode.L2VA),
                            (("first_frame", "last_frame"), H3RenderInputMode.FL2VA)):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                renders, gateway, session = prepared(directory, roles, mode="fl2va")
                project = renders.get_or_create_from_session(session.session_id)
                self.assertEqual(project.input_mode, mode)
                self.assertEqual(project.reference_asset_ids, ())
                self.assertEqual(project.first_frame_asset_id,
                    next((r.asset_id for r in session.references if r.role == "first_frame"), None))
                self.assertEqual(project.last_frame_asset_id,
                    next((r.asset_id for r in session.references if r.role == "last_frame"), None))
                self.assertIn("integrated_multimodal_description:", project.current_prompt)
                self.assertIs(renders.workflow_for_mode(mode), renders.workflow)
                path = Path(directory) / "h3_render_projects" / project.project_id / "project.json"
                saved = path.read_bytes()
                self.assertEqual(renders.get_or_create_from_session(session.session_id), project)
                self.assertEqual(path.read_bytes(), saved)
                self.assertEqual(len(gateway.requests), 2)


if __name__ == "__main__":
    unittest.main()
