"""User-run regressions for project-local sequel IDs; no model calls."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.application.long_stories import request
from panelforge.application.stories import StoryService
from panelforge.domain import long_stories as narrative, story_contracts as contracts
from panelforge.infrastructure.long_story_recipes import LongStoryRecipes
from panelforge.infrastructure.storage.stories import LocalStoryStore, LocalStoryRecipeStore
from tests.test_long_stories import arc_response, unit_response

ROOT = Path(__file__).resolve().parents[1]


class NoCallsGateway:
    def stream(self, request):
        raise AssertionError("Request construction must not call a model")


class StoryIdentifierScopeTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        recipes = LongStoryRecipes(ROOT / "prompt_sources/story.long/2.0.0")
        self.package = recipes.snapshot()
        self.service = StoryService(gateway=NoCallsGateway(), store=LocalStoryStore(temp.name), long_recipes=recipes,
            recipes=LocalStoryRecipeStore(temp.name, ROOT / "prompt_sources/story.brainrot/1.0.0"))
        self.project = self.service.create(brief="Continuer après le départ, sans rejouer le premier épisode.",
            narrative_format="long", creation_mode="adapt", scene_count=4, clip_seconds=10,
            long_options=dict(profile="suspense", delivery="continuous", narration="dialogue",
                              unit_count=1, ending_type="open"),
            prior_story=json.dumps(dict(unit_id="episode-1", events=[dict(id="event-1", change="Un départ ancien.")])))
        self.project["parent_story_id"] = "story-" + "a" * 32
        doc = self.project["document"]
        doc.update(series_outline=arc_response(self.project)["series_outline"], selected_episode_id="episode-1",
                   episode_formats={"episode-1": dict(scene_count=4, clip_seconds=10)})
        unit = unit_response(self.project)
        doc.update(scenario=unit["scenario"], episode_scenarios={"episode-1": unit["scenario"]},
                   episode_states={"episode-1": unit["episode_state"]}, prior_story_snapshot=deepcopy(unit["scenario"]))
        doc["reviews"]["outline"] = dict(source_hash=narrative.source_hash(self.project, "outline"),
            issues=[dict(severity="blocking", target_id="episode-1", problem="Collision avec episode-1 du passé.",
                         suggestion="Renommer episode-2 et event-7 ; ouvrir les paths des IDs.")])

    def build(self, project, operation):
        project["job"] = dict(operation=operation, response_contract_version=contracts.VERSION,
                              instruction="", feedback_target={"unit_id": "outline"} if operation == "discuss" else None)
        before = deepcopy(project)
        result = request(project, self.package, "Français.")
        self.assertEqual(before, project)
        return result, json.loads(result.user_prompt)

    def test_same_ids_across_projects_are_explicitly_scoped_throughout_writing(self):
        for operation in ("compose", "outline", "edit_outline", "review_outline", "repair_outline",
                          "revise_outline", "develop", "discuss"):
            with self.subTest(operation=operation):
                result, context = self.build(deepcopy(self.project), operation)
                scope = context["story_id_scope"]
                self.assertEqual(self.project["project_id"], scope["current_project_id"])
                self.assertEqual(self.project["parent_story_id"], scope["previous_project_id"])
                self.assertEqual(["episode-1"], scope["current_unit_ids"])
                self.assertEqual(["previous_story_read_only", "previous_episode_read_only"], scope["historical_fields"])
                self.assertEqual(self.project["prior_story"], context["previous_story_read_only"])
                self.assertEqual(self.project["document"]["prior_story_snapshot"], context["previous_episode_read_only"])
                self.assertIn("ne justifie aucun renommage", result.system_prompt)
                self.assertIn("conserve les relations, savoirs et états visuels hérités", result.system_prompt)
                if operation in {"compose", "outline", "repair_outline", "revise_outline"}:
                    response_schema = result.output_schema
                    if operation == "revise_outline":
                        response_schema = response_schema["anyOf"][0]
                    schema = response_schema["properties"]["series_outline"]
                    self.assertEqual(["episode-1"], schema["properties"]["episodes"]["items"]["properties"]["id"]["enum"])
                if operation in {"edit_outline", "repair_outline"}:
                    self.assertEqual(self.project["document"]["reviews"]["outline"]["issues"], context["review_to_address"]["issues"])
                if operation == "edit_outline":
                    self.assertFalse(any(path.endswith("/id") for path in context["allowed_edit_paths"]))

    def test_pasted_history_and_snapshot_only_also_have_a_separate_scope(self):
        for source in ("text", "snapshot"):
            with self.subTest(source=source):
                project = deepcopy(self.project)
                project.pop("parent_story_id")
                if source == "text":
                    project["document"].pop("prior_story_snapshot")
                else:
                    project.pop("prior_story")
                _, context = self.build(project, "review_outline")
                self.assertIsNone(context["story_id_scope"]["previous_project_id"])
                self.assertEqual(1, len(context["story_id_scope"]["historical_fields"]))

    def test_no_external_history_and_blind_reader_keep_their_existing_projection(self):
        project = deepcopy(self.project)
        project.pop("prior_story")
        project["document"].pop("prior_story_snapshot")
        result, context = self.build(project, "review_outline")
        self.assertNotIn("story_id_scope", context)
        self.assertNotIn("PORTÉE DES IDENTIFIANTS", result.system_prompt)
        for operation in ("review_episode", "review_block"):
            project = deepcopy(self.project)
            project["job"] = dict(operation=operation, response_contract_version=contracts.VERSION,
                                  instruction="", review_unit_ids=["episode-1"])
            result = request(project, self.package, "Français.")
            context = json.loads(result.user_prompt)
            for key in ("story_id_scope", "previous_story_read_only", "previous_episode_read_only", "secrets"):
                self.assertNotIn(key, context)
            self.assertEqual("previous-story", context["reader_history"][0]["unit_id"])
            self.assertNotIn("PORTÉE DES IDENTIFIANTS", result.system_prompt)

    def test_current_arc_still_requires_local_unit_ids_unique_events_and_valid_dependencies(self):
        project = deepcopy(self.project)
        outline = project["document"]["series_outline"]
        self.assertEqual("episode-1", narrative.validate_outline(project, outline)["episodes"][0]["id"])
        for defect in ("renamed_unit", "duplicate_event", "external_dependency"):
            with self.subTest(defect=defect):
                invalid = deepcopy(outline)
                unit = invalid["episodes"][0]
                if defect == "renamed_unit":
                    unit["id"] = "episode-2"
                elif defect == "duplicate_event":
                    unit["events"].append(deepcopy(unit["events"][0]))
                else:
                    unit["events"][0]["depends_on"] = ["old-project-event"]
                with self.assertRaises(ValueError):
                    narrative.validate_outline(project, invalid)
