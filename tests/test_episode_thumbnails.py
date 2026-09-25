"""User-run checks: fake Qwen queue, isolated index/assets, no remote generation."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

from PIL import Image
from panelforge.application.episode_thumbnails import EpisodeThumbnailService
from panelforge.domain.episode_thumbnails import GRID_LAYOUT, ThumbnailConflict, badge_geometry, cover_format, assign_reference_roles, composition_prompt, default_references, editorial_context
from panelforge.domain.qwen_edit import QwenEditSettings, validate_prompt
from panelforge.infrastructure.episode_thumbnail_images import EpisodeThumbnailImages
from panelforge.infrastructure.storage.episode_thumbnails import LocalEpisodeThumbnailStore


class Assets:
    def __init__(self):
        self.content = {"cast-a": b"character", "place-a": b"place", "qwen-output": b"artwork"}

    def read_bytes(self, key):
        return self.content[key]

    def create(self, content, *, media_type):
        key = f"asset-{len(self.content)}"
        self.content[key] = content
        return NS(asset_id=key)


class Images:
    def __init__(self):
        self.calls = []

    def badge(self, **options):
        return b"transparent-badge"

    def normalize(self, content):
        return content

    def render(self, content, **options):
        self.calls.append((content, deepcopy(options)))
        return content + str(options["number"]).encode()


class Qwen:
    def __init__(self):
        self.projects, self.queued = {}, []

    def create(self, *, name, composition):
        key = f"qwen-{len(self.projects)}"
        self.projects[key] = dict(id=key, stages=[dict(id="stage", revision=1, references=[], attempts=[])])
        return deepcopy(self.projects[key])

    def get(self, key):
        return deepcopy(self.projects[key])

    def add_reference(self, key, stage_id, *, revision, **reference):
        stage = self.projects[key]["stages"][0]
        assert stage["revision"] == revision
        stage["references"].append(reference)
        stage["revision"] += 1
        return self.get(key)

    def update(self, key, stage_id, *, revision, changes):
        stage = self.projects[key]["stages"][0]
        assert stage["revision"] == revision
        validate_prompt(changes["prompt"], [{"tag": f"<image{i+1}>"} for i in range(len(stage["references"]))])
        stage.update(changes)
        stage["revision"] += 1
        return self.get(key)

    def queue_attempt(self, key, stage_id, *, revision, request_id):
        stage = self.projects[key]["stages"][0]
        assert stage["revision"] == revision
        self.queued.append(key)
        stage["attempts"].append(dict(id=f"attempt-{key}", request_id=request_id, status="queued", output_asset_id=None))
        return self.get(key)

    def finish(self, key, failed=False):
        self.projects[key]["stages"][0]["attempts"][-1].update(
            status="failed" if failed else "succeeded", error="Erreur simulée" if failed else None,
            output_asset_id=None if failed else "qwen-output")


class ThumbnailTest(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = LocalEpisodeThumbnailStore(temporary.name)
        self.metadata = dict(groups={}, projects={})
        self.story_a, self.story_b = "story-" + "a" * 32, "story-" + "b" * 32
        self.first, self.second = "episode-" + "a" * 32, "episode-" + "b" * 32
        self.projects = [dict(project_id=self.story_a, title="GLOW UP", narrative_format="long", long_options={"delivery": "continuous"}),
                         dict(project_id=self.story_b, parent_story_id=self.story_a, title="La suite")]
        refs = [dict(id="a", source_id="pechette", name="Pêchette", kind="character", image_asset_id="cast-a"),
                dict(id="place", name="Maison", kind="location", image_asset_id="place-a")]
        self.episodes = {self.first: dict(episode_id=self.first, story_id=self.story_a, references=refs, scenes=[{"prompt": "KEEP"}]),
                         self.second: dict(episode_id=self.second, story_id=self.story_b, references=deepcopy(refs), scenes=[{"prompt": "KEEP TOO"}])}
        self.qwen, self.images, self.assets = Qwen(), Images(), Assets()
        self.service = self.make_service()

    def make_service(self):
        return EpisodeThumbnailService(store=self.store, stories=NS(catalog=lambda: {"items": deepcopy(self.projects)},
            library_metadata=lambda: deepcopy(self.metadata)), episodes=NS(get=lambda key: deepcopy(self.episodes[key])),
            assets=self.assets, images=self.images, qwen=self.qwen)

    def create_ready(self):
        result = self.service.prepare(self.first, request_id="initial-thumbnail")
        self.qwen.finish(result["template"]["qwen_project_id"])
        return self.service.get(self.first)

    def test_same_series_changes_only_number_no_extra_generation_and_preserves_scenes(self):
        before = deepcopy(self.episodes)
        first = self.create_ready()
        second = self.service.prepare(self.second, request_id="following-thumbnail")
        self.assertEqual(second["status"], "ready")
        self.assertEqual((first["number"], second["number"]), (1, 2))
        self.assertEqual(first["template_id"], second["template_id"])
        self.assertEqual(len(self.qwen.queued), 1)
        self.assertEqual(self.images.calls[0][0], self.images.calls[1][0])
        self.assertEqual(self.images.calls[0][1] | {"number": 2}, self.images.calls[1][1])
        self.assertEqual(self.episodes, before)
        self.assertEqual(self.service.prepare(self.second, request_id="another-launch")["asset_id"], second["asset_id"])
        self.assertEqual(len(self.images.calls), 2)

    def test_two_concurrent_episodes_share_one_pending_template(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda key: self.service.prepare(key, request_id=key), [self.first, self.second]))
        self.assertEqual(len(self.qwen.queued), 1)
        self.assertEqual(results[0]["template_id"], results[1]["template_id"])
        self.qwen.finish(self.qwen.queued[0])
        self.assertEqual(self.service.get(self.first)["status"], "ready")
        self.assertEqual(self.service.get(self.second)["status"], "ready")

    def test_restart_recovers_attempt_by_request_id_without_requeue(self):
        pending = self.service.prepare(self.first, request_id="first-request")
        index = self.store.load()
        index["templates"][pending["template_id"]]["qwen_attempt_id"] = None
        self.store.save(index)
        self.qwen.finish(self.qwen.queued[0])
        result = self.make_service().get(self.first)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(len(self.qwen.queued), 1)
        self.assertEqual(len(self.images.calls), 1)

    def test_missing_attempt_is_actionable_not_an_endless_spinner(self):
        pending = self.service.prepare(self.first, request_id="first-request")
        self.qwen.projects[pending["template"]["qwen_project_id"]]["stages"][0]["attempts"] = []
        result = self.make_service().get(self.first)
        self.assertEqual(result["status"], "failed")
        self.assertIn("Relance", result["error"])

    def test_new_model_does_not_rewrite_existing_episode_or_lose_last_good_template_on_failure(self):
        first = self.create_ready()
        second = self.service.prepare(self.second, request_id="second-request")
        pending = self.service.prepare(self.second, request_id="new-artwork", expected_revision=second["revision"],
            source="generate", title="NOUVEAU TITRE", replace=True)
        self.qwen.finish(pending["template"]["qwen_project_id"], failed=True)
        failed = self.service.get(self.second)
        self.assertEqual(failed["asset_id"], second["asset_id"])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["series_template_id"], first["template_id"])
        self.assertEqual(self.service.get(self.first)["asset_id"], first["asset_id"])
        self.assertEqual(self.service.get(self.first)["template_id"], first["template_id"])

    def test_import_and_choose_existing_template_do_not_call_qwen(self):
        first = self.service.prepare(self.first, request_id="import-first", expected_revision=0,
            source="upload", content=b"imported-poster", title_mode="overlay", title="Mon affiche", replace=True)
        second = self.service.prepare(self.second, request_id="choose-existing", source="template", template_id=first["template_id"])
        self.assertEqual(first["status"], "ready")
        self.assertEqual(second["template_id"], first["template_id"])
        self.assertEqual(self.qwen.queued, [])
        self.assertEqual(self.images.calls[1][0], b"imported-poster")

    def test_duplicate_request_is_idempotent_and_stale_edit_is_rejected(self):
        first = self.create_ready()
        edited = self.service.prepare(self.first, request_id="number-edit", expected_revision=first["revision"], number=4, replace=True)
        self.assertEqual(edited["number"], 4)
        duplicate = self.service.prepare(self.first, request_id="number-edit", expected_revision=first["revision"], number=4, replace=True)
        self.assertEqual(duplicate["asset_id"], edited["asset_id"])
        with self.assertRaises(ThumbnailConflict):
            self.service.prepare(self.first, request_id="old-edit", expected_revision=first["revision"], replace=True)
        self.assertEqual(len(self.qwen.queued), 1)

    def test_numbering_uses_library_overrides_serial_units_and_same_number_for_language(self):
        self.projects[0].update(long_options={"delivery": "serial"}, document={"series_outline": {"episodes": [{"id": "unit-1"}, {"id": "unit-2"}]}})
        self.episodes[self.first]["series_episode_id"] = "unit-2"
        self.metadata["projects"][self.story_a] = {"group_id": self.story_a, "episode_number": 7}
        self.assertEqual(self.service.get(self.first)["number"], 8)
        self.episodes[self.first]["localization"] = {"language": "English"}
        self.assertEqual(self.service.get(self.first)["number"], 8)
        self.projects[0]["long_options"]["delivery"] = "continuous"
        self.assertEqual(self.service.get(self.first)["number"], 7)

    def test_default_reference_selection_avoids_duplicate_character_states(self):
        choices = [dict(id="green", source_id="pechette", kind="character"), dict(id="pink", source_id="pechette", kind="character"),
                   dict(id="citron", source_id="citron", kind="character"), dict(id="place", kind="location")]
        self.assertEqual(default_references(choices), ["green", "citron", "place"])

    def test_sixteen_images_preserve_explicit_layers_and_style_in_qwen_and_template(self):
        self.episodes[self.first]["references"] = [dict(id=f"ref-{i}", source_id=f"char-{i}", name=f"Personnage {i}",
            kind="character", image_asset_id="cast-a") for i in range(16)]
        ids = [r["id"] for r in self.episodes[self.first]["references"]]
        roles = {key: "foreground" if i < 2 else "background" for i, key in enumerate(ids)}
        result = self.service.prepare(self.first, request_id="large-cast", reference_ids=ids, reference_roles=roles, title_style="cinema")
        template = result["template"]
        stage = self.qwen.projects[template["qwen_project_id"]]["stages"][0]
        self.assertEqual(len(stage["references"]), 16)
        self.assertIn("<image16>", stage["prompt"])
        self.assertIn("SUPPORTING SUBJECT", stage["references"][-1]["role"])
        self.assertIn("MAIN SUBJECT", stage["references"][0]["role"])
        self.assertIn("heavy condensed", stage["prompt"])
        self.assertIn("10% to 29%", stage["prompt"])
        self.assertEqual(template["reference_roles"], roles)
        self.assertEqual(template["title_style"], "cinema")
        self.qwen.finish(template["qwen_project_id"])
        first = self.service.get(self.first)
        second = self.service.prepare(self.second, request_id="reuse-styled-cast")
        self.assertEqual(second["template_id"], first["template_id"])
        self.assertEqual(self.images.calls[-1][1]["title_style"], "cinema")
        self.assertEqual(len(self.qwen.queued), 1)

    def test_over_limit_and_unknown_role_do_not_enqueue(self):
        with self.assertRaisesRegex(ValueError, "16"):
            self.service.prepare(self.first, request_id="too-many-images", reference_ids=[f"r-{i}" for i in range(17)])
        with self.assertRaisesRegex(ValueError, "rôle"):
            self.service.prepare(self.first, request_id="unselected-role", reference_ids=["a"], reference_roles={"place": "background"})
        with self.assertRaisesRegex(ValueError, "rôle"):
            self.service.prepare(self.first, request_id="invalid-role", reference_ids=["a"], reference_roles={"a": "invented"})
        self.assertFalse(self.qwen.queued)

    def test_exact_title_reserves_empty_title_zone_and_does_not_request_qwen_lettering(self):
        refs = assign_reference_roles([{"id": "a", "name": "Kiwina", "kind": "character"}], {"a": "foreground"})
        prompt = composition_prompt("LE GLOW-UP", "overlay", refs, "Un décor de théâtre.", "pop")
        self.assertIn("Draw no text or letters", prompt)
        self.assertNotIn("Write exactly", prompt)
        self.assertIn("Un décor de théâtre", prompt)
        self.assertIn("MAIN SUBJECT", prompt)

    def test_new_cover_uses_native_three_by_four_and_reports_export_size(self):
        pending = self.service.prepare(self.first, request_id="grid-cover")
        template = pending["template"]
        self.assertEqual(template["layout"], GRID_LAYOUT)
        settings = self.qwen.projects[template["qwen_project_id"]]["stages"][0]["settings"]
        self.assertEqual(settings["aspect_ratio"], "3:4")
        self.assertEqual(QwenEditSettings(**settings).dimensions(), (1248, 1664))
        self.assertEqual(pending["output_format"], {"width": 1080, "height": 1440, "aspect_ratio": "3:4"})
        self.qwen.finish(template["qwen_project_id"])
        ready = self.service.get(self.first)
        self.assertEqual(ready["asset_format"], ready["output_format"])
        self.assertEqual(self.images.calls[-1][1]["layout"], GRID_LAYOUT)

    def test_existing_vertical_template_is_reused_with_its_original_layout(self):
        index = self.store.load()
        template = dict(id="legacy", group_id=self.story_a, title="GLOW UP", title_mode="artwork", title_style="pop",
                        layout="poster-cover-v2", status="ready", asset_id="qwen-output", created_at="2026-09-01")
        index["templates"]["legacy"] = template
        index["series"][self.story_a] = "legacy"
        self.store.save(index)
        result = self.service.prepare(self.second, request_id="keep-old-format")
        self.assertEqual(result["template"]["layout"], "poster-cover-v2")
        self.assertEqual(result["asset_format"], cover_format("poster-cover-v2"))
        self.assertEqual(result["output_format"]["aspect_ratio"], "9:16")
        self.assertEqual(self.images.calls[-1][1]["layout"], "poster-cover-v2")
        self.assertEqual(self.qwen.queued, [])

    def test_title_is_isolated_from_instructions_and_once_is_not_added(self):
        import json
        title = "Le Muscle de Citron"
        prompt = composition_prompt(title, "artwork", [], "Un décor de salle de sport.")
        self.assertNotIn("ONCE", prompt)
        self.assertEqual(prompt.splitlines()[-1], json.dumps(title, ensure_ascii=False))
        self.assertEqual(prompt.count(json.dumps(title, ensure_ascii=False)), 1)
        self.assertIn("portrait 3:4", prompt)
        self.assertIn("10% to 29%", prompt)
        self.assertIn("80% and 91%", prompt)
        # A legitimate title containing that word must not be rewritten by cleanup.
        self.assertTrue(composition_prompt("ONCE UPON A LIME", "artwork", [], "").endswith('"ONCE UPON A LIME"'))

    def test_missing_references_require_import_without_creating_qwen_projects(self):
        self.episodes[self.first]["references"] = []
        with self.assertRaisesRegex(ValueError, "importe"):
            self.service.prepare(self.first, request_id="missing-references")
        self.assertFalse(self.qwen.projects)


    def test_move_badge_reuses_original_preserves_history_and_is_idempotent(self):
        first = self.create_ready()
        before_episodes, before_queue = deepcopy(self.episodes), list(self.qwen.queued)
        moved = self.service.reposition_badge(self.first, request_id="move-badge", expected_revision=first["revision"],
            position={"x": 20, "y": 8}, remember_series=True)
        self.assertNotEqual(moved["asset_id"], first["asset_id"])
        self.assertEqual(moved["history"][-1]["asset_id"], first["asset_id"])
        self.assertEqual(self.images.calls[-1][0], b"artwork")
        self.assertEqual(self.images.calls[-1][1]["badge_position"], {"x": 20, "y": 8})
        duplicate = self.service.reposition_badge(self.first, request_id="move-badge", expected_revision=first["revision"],
            position={"x": 20, "y": 8}, remember_series=True)
        self.assertEqual(duplicate["asset_id"], moved["asset_id"])
        reopened = self.make_service().get(self.first)
        self.assertEqual(reopened["badge"]["position"], {"x": 20, "y": 8})
        self.assertEqual(self.episodes, before_episodes)
        self.assertEqual(self.qwen.queued, before_queue)

    def test_series_position_affects_future_covers_only_with_same_template(self):
        first = self.create_ready()
        second = self.service.prepare(self.second, request_id="before-position")
        moved = self.service.reposition_badge(self.first, request_id="remember-position", expected_revision=first["revision"],
            position={"x": 50, "y": 8}, remember_series=True)
        self.assertEqual(self.service.get(self.second)["asset_id"], second["asset_id"])
        third_id = "episode-" + "c" * 32
        self.episodes[third_id] = dict(self.episodes[self.first], episode_id=third_id)
        third = self.service.prepare(third_id, request_id="after-position")
        self.assertEqual(third["badge_position"], moved["badge_position"])
        replaced = self.service.prepare(third_id, request_id="different-model", expected_revision=third["revision"],
            source="upload", content=b"other-image", replace=True)
        self.assertIsNone(replaced["badge_position"])
        # Moving one cover without opting in does not replace the remembered series preference.
        self.service.reposition_badge(self.first, request_id="episode-only", expected_revision=moved["revision"],
            position={"x": 10, "y": 50})
        self.assertEqual(self.store.load()["badge_positions"][self.story_a]["position"], {"x": 50, "y": 8})

    def test_badge_preview_has_no_old_badge_and_does_not_write_assets_or_queue(self):
        first = self.create_ready()
        before_store, before_assets = self.store.load(), deepcopy(self.assets.content)
        self.service.badge_preview(self.first, part="background", expected_revision=first["revision"])
        self.assertEqual(self.images.calls[-1][0], b"artwork")
        self.assertFalse(self.images.calls[-1][1]["include_badge"])
        self.assertEqual(self.service.badge_preview(self.first, part="badge", expected_revision=first["revision"]), b"transparent-badge")
        self.assertEqual(self.store.load(), before_store)
        self.assertEqual(self.assets.content, before_assets)
        self.assertEqual(len(self.qwen.queued), 1)

    def test_badge_rejects_stale_unfinished_and_invalid_positions_before_rendering(self):
        pending = self.service.prepare(self.first, request_id="pending-cover")
        with self.assertRaises(ThumbnailConflict):
            self.service.reposition_badge(self.first, request_id="move-pending", expected_revision=pending["revision"], position={"x": 50, "y": 5})
        self.qwen.finish(pending["template"]["qwen_project_id"])
        first = self.service.get(self.first)
        count = len(self.images.calls)
        with self.assertRaises(ThumbnailConflict):
            self.service.reposition_badge(self.first, request_id="stale-position", expected_revision=first["revision"]-1, position={"x": 50, "y": 5})
        for position in ({"x": -1, "y": 0}, {"x": 0, "y": 101}, {"x": float("nan"), "y": 0},
                         {"x": True, "y": 0}, {"x": 0}, {"x": 0, "y": 0, "z": 3}):
            with self.subTest(position=position), self.assertRaises(ValueError):
                self.service.reposition_badge(self.first, request_id="invalid-position", expected_revision=first["revision"], position=position)
        self.assertEqual(len(self.images.calls), count)

    def test_trash_hides_unused_template_without_deleting_history_and_can_restore(self):
        first = self.create_ready()
        current = self.service.prepare(self.first, request_id="better-model", expected_revision=first["revision"],
            source="upload", content=b"better-image", replace=True)
        unused = next(t for t in current["templates"] if t["id"] == first["template_id"])
        self.assertTrue(unused["can_archive"])
        before_assets = deepcopy(self.assets.content)
        trashed = self.service.archive_template(self.first, unused["id"], archived=True, expected_revision=unused["revision"])
        template = next(t for t in trashed["templates"] if t["id"] == unused["id"])
        self.assertTrue(template["archived_at"])
        self.assertEqual(trashed["history"][-1]["asset_id"], first["asset_id"])
        self.assertEqual(self.assets.content, before_assets)
        with self.assertRaises(ThumbnailConflict):
            self.service.prepare(self.second, request_id="use-trashed", source="template", template_id=unused["id"])
        with self.assertRaises(ThumbnailConflict):
            self.service.archive_template(self.first, unused["id"], archived=False, expected_revision=unused["revision"])
        restored = self.service.archive_template(self.first, unused["id"], archived=False, expected_revision=template["revision"])
        self.assertFalse(next(t for t in restored["templates"] if t["id"] == unused["id"])["archived_at"])
        used = self.service.prepare(self.second, request_id="use-restored", source="template", template_id=unused["id"])
        self.assertEqual(used["template_id"], unused["id"])
        self.assertEqual(len(self.qwen.queued), 1)

    def test_trash_protects_models_used_by_other_episodes_even_when_not_series_default(self):
        first = self.create_ready()
        self.service.prepare(self.second, request_id="second-uses-first")
        current = self.service.prepare(self.first, request_id="new-default", expected_revision=first["revision"],
            source="upload", content=b"new-default", replace=True)
        old = next(t for t in current["templates"] if t["id"] == first["template_id"])
        self.assertEqual(old["episode_count"], 1)
        self.assertFalse(old["can_archive"])
        with self.assertRaises(ThumbnailConflict):
            self.service.archive_template(self.first, old["id"], archived=True, expected_revision=old["revision"])
        default = next(t for t in current["templates"] if t["id"] == current["template_id"])
        self.assertEqual(default["series_count"], 1)
        with self.assertRaises(ThumbnailConflict):
            self.service.archive_template(self.first, default["id"], archived=True, expected_revision=default["revision"])



class TypographyTest(unittest.TestCase):
    def test_numbers_change_only_badge_pixels_and_support_accents(self):
        source = BytesIO()
        Image.new("RGB", (1080, 1920), "#336677").save(source, format="PNG")
        render = EpisodeThumbnailImages()
        first = Image.open(BytesIO(render.render(source.getvalue(), title="PÊCHETTE", number=1, title_mode="overlay")))
        second = Image.open(BytesIO(render.render(source.getvalue(), title="PÊCHETTE", number=2, title_mode="overlay")))
        self.assertEqual(first.size, (1080, 1920))
        self.assertEqual(first.crop((0, 0, 1080, 1480)).tobytes(), second.crop((0, 0, 1080, 1480)).tobytes())
        self.assertNotEqual(first.crop((500, 1480, 965, 1705)).tobytes(), second.crop((500, 1480, 965, 1705)).tobytes())


    def test_v2_styles_render_separate_title_and_compact_episode_zones(self):
        source = BytesIO()
        Image.new("RGB", (1080, 1920), "#304544").save(source, format="PNG")
        render = EpisodeThumbnailImages()
        for style in ("pop", "cinema"):
            with self.subTest(style=style):
                first = Image.open(BytesIO(render.render(source.getvalue(), title="LE GLOW-UP DE KIWINA", number=1,
                    title_mode="overlay", title_style=style, layout="poster-cover-v2")))
                second = Image.open(BytesIO(render.render(source.getvalue(), title="LE GLOW-UP DE KIWINA", number=2,
                    title_mode="overlay", title_style=style, layout="poster-cover-v2")))
                self.assertEqual(first.size, (1080, 1920))
                self.assertEqual(first.crop((0, 0, 1080, 1590)).tobytes(), second.crop((0, 0, 1080, 1590)).tobytes())
                self.assertNotEqual(first.crop((290, 1590, 790, 1750)).tobytes(), second.crop((290, 1590, 790, 1750)).tobytes())
                self.assertEqual(first.getpixel((540, 900)), (48, 69, 68))
        pop = render.render(source.getvalue(), title="GLOW UP", number=1, title_mode="overlay", title_style="pop", layout="poster-cover-v2")
        cinema = render.render(source.getvalue(), title="GLOW UP", number=1, title_mode="overlay", title_style="cinema", layout="poster-cover-v2")
        self.assertNotEqual(pop, cinema)

    def test_v1_reuse_ignores_new_title_styles(self):
        source = BytesIO()
        Image.new("RGB", (1080, 1920), "#336677").save(source, format="PNG")
        render = EpisodeThumbnailImages()
        self.assertEqual(render.render(source.getvalue(), title="GLOW UP", number=3, title_mode="overlay", title_style="pop"),
                         render.render(source.getvalue(), title="GLOW UP", number=3, title_mode="overlay", title_style="cinema"))


    def test_grid_cover_keeps_title_and_number_inside_three_by_four_with_margins(self):
        source = BytesIO()
        Image.new("RGB", (1080, 1440), "#304544").save(source, format="PNG")
        renderer = EpisodeThumbnailImages()
        for style in ("pop", "cinema"):
            with self.subTest(style=style):
                one = Image.open(BytesIO(renderer.render(source.getvalue(), title="LE MUSCLE DE CITRON", number=1,
                    title_mode="overlay", title_style=style, layout=GRID_LAYOUT)))
                two = Image.open(BytesIO(renderer.render(source.getvalue(), title="LE MUSCLE DE CITRON", number=2,
                    title_mode="overlay", title_style=style, layout=GRID_LAYOUT)))
                self.assertEqual(one.size, (1080, 1440))
                self.assertEqual(one.crop((0, 0, 1080, 1150)).tobytes(), two.crop((0, 0, 1080, 1150)).tobytes())
                self.assertEqual(one.crop((0, 1310, 1080, 1440)).tobytes(), two.crop((0, 1310, 1080, 1440)).tobytes())
                self.assertNotEqual(one.crop((290, 1150, 790, 1310)).tobytes(), two.crop((290, 1150, 790, 1310)).tobytes())
                self.assertEqual(one.getpixel((540, 25)), (48, 69, 68))
                self.assertEqual(one.getpixel((540, 700)), (48, 69, 68))

    def test_moving_badge_uncovers_old_position_and_changes_only_two_regions(self):
        source = BytesIO()
        Image.new("RGB", (1080, 1440), "#304544").save(source, format="PNG")
        renderer = EpisodeThumbnailImages()
        options = dict(title="LE MUSCLE", number=3, title_mode="overlay", layout=GRID_LAYOUT)
        original = Image.open(BytesIO(renderer.render(source.getvalue(), **options)))
        moved = Image.open(BytesIO(renderer.render(source.getvalue(), **options, badge_position={"x": 50, "y": 50})))
        background = Image.open(BytesIO(renderer.render(source.getvalue(), **options, include_badge=False)))
        old_box = (290, 1150, 791, 1311)
        new_box = (290, 640, 791, 801)
        self.assertEqual(moved.crop(old_box).tobytes(), background.crop(old_box).tobytes())
        self.assertNotEqual(moved.crop(new_box).tobytes(), background.crop(new_box).tobytes())
        self.assertEqual(original.crop((0, 0, 1080, 600)).tobytes(), moved.crop((0, 0, 1080, 600)).tobytes())
        badge = Image.open(BytesIO(renderer.badge(number=3, layout=GRID_LAYOUT)))
        self.assertEqual(badge.mode, "RGBA")
        self.assertEqual(badge.getpixel((0, 0))[3], 0)

    def test_badge_extremes_stay_inside_each_supported_canvas(self):
        for layout in ("outfit-cover-v1", "poster-cover-v2", GRID_LAYOUT):
            for x, y in ((0, 0), (100, 100), (50, 8)):
                g = badge_geometry(layout, {"x": x, "y": y})
                self.assertGreaterEqual(g["x"], 0)
                self.assertGreaterEqual(g["y"], 0)
                self.assertLessEqual(g["x"] + g["width"], g["canvas"]["width"])
                self.assertLessEqual(g["y"] + g["height"], g["canvas"]["height"])
