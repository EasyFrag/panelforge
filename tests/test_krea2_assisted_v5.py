from pathlib import Path
import tempfile
import unittest

from panelforge.application import krea2_assisted_v5 as v5
from panelforge.application.krea2_assisted import Krea2AssistedService
from panelforge.domain.krea2_assisted import Krea2PromptExample
from panelforge.infrastructure.krea2_wildcards import LocalKrea2WildcardLibrary
from panelforge.infrastructure.storage.krea2_assisted import _deserialize, _serialize
from panelforge.domain.krea2_assisted import Krea2AssistedProject


class _Examples:
    def __init__(self, values):
        self.values = values

    def search(self, query, *, limit=3):
        return self.values[:limit]


class _Wildcards(_Examples):
    pass


def _scene(number):
    return Krea2PromptExample(
        example_id=f"scene-{number}",
        source_file="corpus.txt",
        source_line=number,
        digest=(str(number) * 64)[:64],
        prompt=f"Complete photographic scene {number}.",
        score=0.5,
    )


class Krea2AssistedV5Test(unittest.TestCase):
    def _structural_library(self, root):
        (root / "shared-common-data.yaml").write_text(
            """
uw-shared:
  common:
    medium:
    - A cinematic photograph of
""".strip(),
            encoding="utf-8",
        )
        (root / "krea2-nsfw-action-templates.yaml").write_text(
            """
uw-krea2-nsfw:
  router:
    portrait-intimate-action-partner-pics:
    - __uw-krea2-nsfw/template/action-partner-doggystyle-pov__
    - __uw-krea2-nsfw/template/action-partner-giving-oral-pov__
  template:
    action-partner-doggystyle-pov:
    - A cinematic photograph of two consenting adults in doggystyle from his POV. [3:4]
    action-partner-giving-oral-pov:
    - A cinematic photograph of two consenting adults having oral sex from his POV. [3:4]
""".strip(),
            encoding="utf-8",
        )
        (root / "krea2-nsfw-group-templates.yaml").write_text(
            """
uw-krea2-nsfw:
  router:
    portrait-intimate-action-group-penetration-pics:
    - __uw-krea2-nsfw/template/action-group-oral-threesome__
  template:
    action-group-oral-threesome:
    - A cinematic photograph of group sex with penetration and oral sex. [3:4]
""".strip(),
            encoding="utf-8",
        )
        return LocalKrea2WildcardLibrary(root, seed_factory=lambda: 42)

    def test_compiles_a_resolved_weighted_template_with_a_stable_audit_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "shared-common-data.yaml").write_text(
                """
uw-shared:
  common:
    medium:
    - 2::A candid photograph of
    - A cinematic photograph of
""".strip(),
                encoding="utf-8",
            )
            (root / "krea2-nsfw-action-templates.yaml").write_text(
                """
uw-krea2-nsfw:
  router:
    portrait-intimate-action-partner-pics:
    - __uw-krea2-nsfw/template/action-partner-giving-oral-pov__
  template:
    action-partner-giving-oral-pov:
    - >-
        __uw-shared/common/medium__ two consenting adult partners,
        explicit oral sex from a {close POV|medium POV},
        coherent contact in a hotel room, natural light. [3:4]
""".strip(),
                encoding="utf-8",
            )
            library = LocalKrea2WildcardLibrary(root, seed_factory=lambda: 42)

            self.assertEqual(library.status()["state"], "ready")
            result = library.search(
                "A consenting adult couple, fellatio from a close POV in a hotel.",
                limit=1,
            )[0]
            self.assertEqual(result.source_kind, "wildcard")
            self.assertEqual(result.variant_seed, 42)
            self.assertEqual(result.recommended_aspect_ratio, "3:4")
            self.assertEqual(result.relevance, "strong")
            self.assertNotIn("__", result.prompt)
            self.assertNotIn("[3:4]", result.prompt)

    def test_hybrid_search_pins_one_strong_template_and_two_scene_examples(self):
        scenes = tuple(_scene(number) for number in range(1, 4))
        template = Krea2PromptExample(
            example_id="wildcard-one",
            source_file="templates.yaml",
            source_line=8,
            digest="a" * 64,
            prompt="Compiled KREA2 action template.",
            score=0.8,
            relevance="strong",
            source_kind="wildcard",
            template_id="uw-krea2-nsfw/template/action-partner-oral",
            variant_seed=12,
            recommended_aspect_ratio="3:4",
        )
        service = object.__new__(Krea2AssistedService)
        service.prompt_examples = _Examples(scenes)
        service.prompt_wildcards = _Wildcards((template,))

        values = service._search_prompt_inspirations("5.0.0", "oral sex")

        self.assertEqual(values, (template, scenes[0], scenes[1]))

    def test_doggystyle_pair_rejects_group_oral_template(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = self._structural_library(Path(temporary))

            results = library.search(
                "POV of an orc penetrating an elf woman from behind in doggystyle. "
                "actions: penetrating. participants: orc, elf woman. "
                "positions: doggystyle, POV. framings: point of view.",
                limit=3,
            )

            self.assertTrue(results[0].template_id.endswith("action-partner-doggystyle-pov"))
            rejected = next(
                item for item in results
                if item.template_id.endswith("action-group-oral-threesome")
            )
            self.assertEqual(rejected.relevance, "weak")
            self.assertIn("oral_sex", rejected.actions)
            self.assertEqual(rejected.participants, ("group",))

    def test_oral_pov_keeps_exact_partner_template_first(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = self._structural_library(Path(temporary))

            results = library.search(
                "POV of an orc receiving oral sex from an elf woman. "
                "actions: oral sex. participants: orc, elf woman. framings: POV.",
                limit=3,
            )

            self.assertTrue(
                results[0].template_id.endswith("action-partner-giving-oral-pov")
            )
            self.assertEqual(results[0].relevance, "strong")

    def test_requested_group_multi_action_can_use_threesome_template(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = self._structural_library(Path(temporary))

            results = library.search(
                "A threesome with group sex, penetration and oral sex. "
                "actions: penetration, oral sex. participants: group.",
                limit=3,
            )

            self.assertTrue(results[0].template_id.endswith("action-group-oral-threesome"))
            self.assertEqual(results[0].relevance, "strong")

    def test_v5_metadata_round_trips_and_reaches_the_writer_as_reference_data(self):
        template = Krea2PromptExample(
            example_id="wildcard-persisted",
            source_file="templates.yaml",
            source_line=4,
            digest="b" * 64,
            prompt="Compiled complete prompt.",
            score=0.7,
            relevance="strong",
            source_kind="wildcard",
            template_id="uw-krea2-sfw/template/selfie-mirror-front",
            variant_seed=99,
            recommended_aspect_ratio="9:16",
        )
        project = Krea2AssistedProject(
            project_id="v5", name="V5", intention="Mirror selfie", model_id="local",
            assistance_recipe_version="5.0.0",
            prompt_examples=(template, _scene(1), _scene(2)),
            selected_prompt_example_id=template.example_id,
        )

        self.assertEqual(_deserialize(_serialize(project)), project)
        context = v5.example_context(template)
        self.assertIn("REFERENCE DATA ONLY", context)
        self.assertIn('"variant_seed":99', context)
        self.assertIn("Compiled complete prompt.", context)
        self.assertIn("random casting", context)

    def test_v3_is_the_stable_default_recipe(self):
        recipes = Krea2AssistedService.list_assistance_recipes()
        self.assertEqual(recipes[2], {"version": "3.0.0", "label": "V3 · STABLE"})
        self.assertEqual(recipes[-1]["version"], "5.0.0")
