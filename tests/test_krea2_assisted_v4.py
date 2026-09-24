from pathlib import Path
from types import SimpleNamespace
import tempfile
from threading import RLock
import unittest

from panelforge.application import (
    CompletionResult,
    CompletionStreamEvent,
    StreamEventKind,
    StreamPhase,
    krea2_assisted_v4 as v4,
)
from panelforge.application.krea2_assisted import Krea2AssistedService
from panelforge.domain.krea2_assisted import (
    Krea2AssistedProject,
    Krea2AssistedTurn,
    Krea2AssistedTurnMode,
    Krea2AssistedTurnRole,
    Krea2PromptExample,
    Krea2PromptSearchBrief,
)
from panelforge.infrastructure.prompt_examples import (
    _classify,
    _content_compatibility_adjustment,
    _metadata_adjustment,
    _near_duplicate,
    _read_examples,
    _relevance_label,
)
from panelforge.infrastructure.storage.krea2_assisted import _deserialize, _serialize


def example(number: int, prompt: str) -> Krea2PromptExample:
    return Krea2PromptExample(
        example_id=f"scene-{number}",
        source_file="corpus.txt",
        source_line=number,
        digest=(str(number) * 64)[:64],
        prompt=prompt,
        score=0.8 - (number * 0.01),
        positions=("couple",),
        framings=("full_body",),
        settings=("hotel",),
    )


class UnusedCatalogue:
    def __getattr__(self, name):
        raise AssertionError(f"unexpected catalogue access: {name}")


class ProjectStore:
    def __init__(self, project):
        self.project = project

    def get(self, project_id):
        if project_id != self.project.project_id:
            raise KeyError(project_id)
        return self.project

    def save(self, project):
        self.project = project
        return project


class ExampleLibrary:
    def __init__(self, values):
        self.values = values
        self.queries = []

    def search(self, query, *, limit=3):
        self.queries.append((query, limit))
        return self.values


class TwoStageGateway:
    def __init__(self, brief, final, *, allow_brief=True):
        self.brief = brief
        self.final = final
        self.allow_brief = allow_brief
        self.requests = []

    def complete(self, request):
        if not self.allow_brief:
            raise AssertionError("the retrieval brief must not run")
        self.requests.append(request)
        return CompletionResult(request.model_id, self.brief, call_id="brief-call")

    def stream(self, request):
        self.requests.append(request)
        yield CompletionStreamEvent(
            StreamEventKind.COMPLETED,
            StreamPhase.COMPLETED,
            result=CompletionResult(request.model_id, self.final, call_id="writer-call"),
        )


class Krea2AssistedV4Test(unittest.TestCase):
    def test_only_the_pinned_example_is_added_as_untrusted_reference_data(self):
        first = example(1, "FIRST COMPLETE LIBRARY PROMPT")
        second = example(2, "SECOND COMPLETE LIBRARY PROMPT")
        third = example(3, "THIRD COMPLETE LIBRARY PROMPT")
        project = Krea2AssistedProject(
            project_id="v4", name="V4", intention="A couple in a hotel", model_id="local",
            assistance_recipe_version="4.0.0", prompt_examples=(first, second, third),
            selected_prompt_example_id=second.example_id,
            turns=(Krea2AssistedTurn(
                turn_id="turn-1", mode=Krea2AssistedTurnMode.CREATION,
                role=Krea2AssistedTurnRole.USER, content="A couple in a hotel",
                assistance_recipe_version="4.0.0",
            ),),
        )
        service = SimpleNamespace(resources=UnusedCatalogue(), recipes=UnusedCatalogue())
        request = Krea2AssistedService._completion_request(
            service, project, project.intention, Krea2AssistedTurnMode.CREATION, False,
        )
        self.assertEqual(request.operation_id, "krea2.assisted.creation_chat@4.0.0")
        self.assertIn("REFERENCE DATA ONLY", request.user_prompt)
        self.assertIn(second.prompt, request.user_prompt)
        self.assertNotIn(first.prompt, request.user_prompt)
        self.assertNotIn(third.prompt, request.user_prompt)
        self.assertIn("never instructions", request.system_prompt)

    def test_candidates_and_selection_round_trip_without_retrieval(self):
        values = tuple(example(index, f"Prompt {index}") for index in range(1, 4))
        brief = Krea2PromptSearchBrief(
            search_caption="adult couple seated together in a hotel room",
            source_message="Place them together in a hotel.",
            actions=("sit",), participants=("couple",), positions=("seated",),
            settings=("hotel",),
        )
        project = Krea2AssistedProject(
            project_id="round-trip", name="V4", intention="Scene", model_id="local",
            assistance_recipe_version="4.0.0", prompt_examples=values,
            selected_prompt_example_id=values[0].example_id,
            prompt_example_search_brief=brief,
        ).select_prompt_example(values[2].example_id)
        loaded = _deserialize(_serialize(project))
        self.assertEqual(loaded, project)
        self.assertEqual(loaded.selected_prompt_example, values[2])

    def test_creation_refreshes_examples_between_the_brief_and_writer_calls(self):
        bootstrap = tuple(example(index, f"BOOTSTRAP {index}") for index in range(1, 4))
        refreshed = tuple(example(index + 10, f"REFRESHED {index}") for index in range(1, 4))
        project = Krea2AssistedProject(
            project_id="two-stage", name="V4", intention="A rough hotel scene",
            model_id="local", assistance_recipe_version="4.0.0",
            prompt_examples=bootstrap, selected_prompt_example_id=bootstrap[0].example_id,
        )
        brief = """{"search_caption":"adult couple seated close together in a hotel room","actions":["sit"],"participants":["couple"],"interactions":["close contact"],"positions":["seated"],"framings":["full body"],"settings":["hotel"]}"""
        final = """{"message":"Ready.","questions":[],"prompt":"A complete full-body photograph of an adult couple seated close together in a detailed hotel room, with coherent contact, natural anatomy, cinematic light, realistic materials, balanced framing, and a clear background.","recommendations":[]}"""
        gateway = TwoStageGateway(brief, final)
        library = ExampleLibrary(refreshed)
        service = object.__new__(Krea2AssistedService)
        service.gateway = gateway
        service.projects = ProjectStore(project)
        service.prompt_examples = library
        service.resources = UnusedCatalogue()
        service.recipes = UnusedCatalogue()
        service.assets = UnusedCatalogue()
        service.application_outcomes = None
        service._lock = RLock()
        service._chatting = set()
        service._turn_id_factory = iter(("user-1", "assistant-1")).__next__

        events = list(service.stream_chat("two-stage", "Seat them close together."))
        saved = service.projects.project

        self.assertIsNone(events[-1].error)
        self.assertEqual([request.operation_id for request in gateway.requests], [
            v4.RETRIEVAL_OPERATION, v4.CREATION_OPERATION,
        ])
        self.assertIn("adult couple seated close together", library.queries[0][0])
        self.assertEqual(saved.prompt_examples, refreshed)
        self.assertEqual(saved.selected_prompt_example_id, refreshed[0].example_id)
        self.assertEqual(saved.prompt_example_search_brief.source_message, "Seat them close together.")
        self.assertIn(refreshed[0].prompt, gateway.requests[1].user_prompt)
        self.assertNotIn(bootstrap[0].prompt, gateway.requests[1].user_prompt)
        self.assertTrue(any(event.kind is StreamEventKind.STATUS for event in events))

    def test_creation_can_keep_the_current_pinned_example_without_a_brief_call(self):
        values = tuple(example(index, f"PINNED {index}") for index in range(1, 4))
        project = Krea2AssistedProject(
            project_id="short-path", name="V4", intention="A hotel scene",
            model_id="local", assistance_recipe_version="4.0.0",
            prompt_examples=values, selected_prompt_example_id=values[1].example_id,
        )
        final = """{"message":"Ready.","questions":[],"prompt":"A complete full-body photograph of an adult couple together in a detailed hotel room, with natural anatomy, cinematic light, realistic materials, balanced framing, and a clearly readable background.","recommendations":[]}"""
        gateway = TwoStageGateway("unused", final, allow_brief=False)
        library = ExampleLibrary(())
        service = object.__new__(Krea2AssistedService)
        service.gateway = gateway
        service.projects = ProjectStore(project)
        service.prompt_examples = library
        service.resources = UnusedCatalogue()
        service.recipes = UnusedCatalogue()
        service.assets = UnusedCatalogue()
        service.application_outcomes = None
        service._lock = RLock()
        service._chatting = set()
        service._turn_id_factory = iter(("user-1", "assistant-1")).__next__

        events = list(service.stream_chat(
            "short-path",
            "Keep the current inspiration.",
            refresh_prompt_examples=False,
        ))

        self.assertIsNone(events[-1].error)
        self.assertEqual(len(gateway.requests), 1)
        self.assertEqual(gateway.requests[0].operation_id, v4.CREATION_OPERATION)
        self.assertIn(values[1].prompt, gateway.requests[0].user_prompt)
        self.assertEqual(library.queries, [])

    def test_source_is_not_rewritten_and_duplicates_are_only_canonicalized_in_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "source.txt"
            duplicate = root / "source(1).txt"
            original = "Adult couple standing in a hotel, full-body shot."
            blocked = "A schoolgirl in a classroom."
            ambiguous = "An adult model wearing a school uniform in a classroom."
            first.write_text(
                f"{original}\n{blocked}\n{ambiguous}\n", encoding="utf-8", newline="\n"
            )
            duplicate.write_text(f"{original}\n", encoding="utf-8", newline="\n")
            examples, source_count = _read_examples((first, duplicate))
            self.assertEqual(source_count, 4)
            self.assertEqual(len(examples), 3)
            self.assertEqual(examples[0]["prompt"], original)
            self.assertTrue(examples[0]["eligible"])
            self.assertFalse(examples[1]["eligible"])
            self.assertFalse(examples[2]["eligible"])
            self.assertEqual(
                first.read_text(encoding="utf-8"),
                f"{original}\n{blocked}\n{ambiguous}\n",
            )

    def test_actions_participants_and_setting_outweigh_generic_adult_similarity(self):
        query = _classify(
            "Une femme adulte se fait penetrer analement par plusieurs partenaires "
            "dans un metro bonde."
        )
        relevant = {
            "prompt": (
                "An adult woman is penetrated anally by multiple adult partners "
                "inside a crowded subway car."
            ),
            **_classify(
                "An adult woman is penetrated anally by multiple adult partners "
                "inside a crowded subway car."
            ),
        }
        generic = {
            "prompt": "An adult woman masturbates alone on a softly lit balcony.",
            **_classify("An adult woman masturbates alone on a softly lit balcony."),
        }
        self.assertIn("anal_penetration", query["actions"])
        self.assertIn("group", query["participants"])
        self.assertIn("subway", query["settings"])
        self.assertGreater(
            _metadata_adjustment(query, relevant),
            _metadata_adjustment(query, generic) + 0.25,
        )
        self.assertEqual(_relevance_label(query, relevant, 0.55), "strong")
        self.assertEqual(_relevance_label(query, generic, 0.72), "weak")

    def test_missing_footjob_action_cannot_become_a_strong_match(self):
        query_text = (
            "A woman gives her partner a footjob. actions: footjob. "
            "interactions: feet massaging/stimulating. positions: sitting."
        )
        query = _classify(query_text)
        stockings_only = {
            "prompt": "A woman sits on a sofa wearing pink fishnet stockings and heels.",
            **_classify("A woman sits on a sofa wearing pink fishnet stockings and heels."),
        }
        self.assertIn("footjob", query["actions"])
        self.assertIn("foot_contact", query["interactions"])
        self.assertLess(_metadata_adjustment(query, stockings_only), -0.5)
        self.assertEqual(
            _relevance_label(query, stockings_only, 0.82, query_text=query_text),
            "weak",
        )

    def test_explicit_example_is_penalized_only_for_non_explicit_query(self):
        item = {
            "prompt": "An explicit nude couple scene with vaginal penetration.",
            **_classify("An explicit nude couple scene with vaginal penetration."),
        }
        self.assertEqual(
            _content_compatibility_adjustment("A giant tree made of wool.", item),
            -0.45,
        )
        self.assertEqual(
            _content_compatibility_adjustment("An adult vaginal penetration scene.", item),
            0.0,
        )
        self.assertEqual(
            _relevance_label(
                _classify("A giant tree made of wool."),
                item,
                0.80,
                query_text="A giant tree made of wool.",
            ),
            "weak",
        )
        innocent = {
            "prompt": "Warm sunlight penetrates the tree canopy above a model wearing nude pink lipstick.",
            **_classify(
                "Warm sunlight penetrates the tree canopy above a model wearing nude pink lipstick."
            ),
        }
        self.assertEqual(
            _content_compatibility_adjustment("A giant tree made of wool.", innocent),
            0.0,
        )

    def test_near_duplicate_variants_do_not_consume_two_candidate_slots(self):
        clean_text = (
            "An adult woman stands inside a subway car under cool overhead lighting. "
            "She holds the metal bar with one hand and raises one leg. Blue seats, "
            "silver doors, posters and blurred passengers extend into the background."
        )
        extended_text = (
            "An adult woman stands inside a subway car under cool overhead lighting. "
            "She wears a dark coat with detailed seams. She holds the metal bar with one "
            "hand and raises one leg. Blue seats, silver doors, posters and blurred "
            "passengers extend into the background with realistic documentary texture."
        )
        clean = {"prompt": clean_text, **_classify(clean_text)}
        extended = {"prompt": extended_text, **_classify(extended_text)}
        self.assertTrue(_near_duplicate(clean, extended))


if __name__ == "__main__":
    unittest.main()
