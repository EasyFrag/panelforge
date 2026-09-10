"""Offline Combat routing and isolation. All responses are fixed fixtures, never model calls."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from panelforge.application.prompt_lab import PromptLabService, creative_audacity_policy, creative_freedom_policy
from panelforge.application.h3_render import H3RenderService
from panelforge.domain import CompositionStage, CreativeFreedomAxes
from panelforge.domain.h3_render import H3RenderInputMode, H3RenderProject, H3RenderRevisionVersion
from panelforge.domain.video_preparation import VideoPreparationRef
from panelforge.infrastructure.combat_preparation import load_combat_revision_policy
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.storage import LocalAssetStore, LocalH3RenderProjectStore, LocalPromptSessionStore
from panelforge.infrastructure.presets import H3RenderPresetRecipe, Ref2VH3RenderPresetRecipe, VideoLabPresetRecipe, load_h3_render_workflow, load_video_lab_workflow
from tests.test_video_preparation_recipes import preparation_service
from tests.test_h3_multishot_preparation import state_plan
from tests.test_h3_render import WORKFLOW_DIRECTORY, REF2V_WORKFLOW_DIRECTORY
from tests import test_h3_ref2v_conversion as conversion_fixtures


ROOT = Path(__file__).resolve().parents[1]
COMBAT = VideoPreparationRef("combat", "1.0.0")
PROMPT = conversion_fixtures.PROMPT
INTENT = "In 8 seconds, a swordswoman attacks a shield bearer, who parries and counters; she retreats while remaining engaged. No music."
OPENING = "A swordswoman and a shield bearer face each other within striking distance in a stone courtyard."
ACTION = "The swordswoman steps in and slashes. The shield bearer intercepts the blade, redirects it outward and disengages. He counters as she steps clear and retreats. Their feet keep adjusting through the cut."
END = "The swordswoman retreats with her sword raised while the shield bearer keeps advancing."
BRIEF = "\n".join(f"- {heading}\n{text}" for heading, text in (
    ("INTENTION CENTRALE", "Un duel avec parade et riposte, sur 8 secondes."),
    ("RÉFÉRENCES CITÉES ET RÔLES", "Respecter les rôles fournis et leurs instants."),
    ("SUJETS ET IDENTITÉS À PRÉSERVER", "La combattante à l'épée et le porteur de bouclier."),
    ("DÉCOR ET ÉTAT INITIAL", "Une cour de pierre, adversaires à portée."),
    ("CHRONOLOGIE ET ACTIONS DEMANDÉES", "Elle attaque ; il pare, dégage son arme et riposte ; elle recule, le duel reste en mouvement."),
    ("CAMÉRA, LUMIÈRE ET MISE EN SCÈNE", "Cadrage fixe, lumière inchangée."),
    ("CONTRAINTES STRICTES", "Armes et identités stables. Pas de musique."),
    ("LIBERTÉS AUTORISÉES", "Mécanique nécessaire de l'échange."),
    ("QUESTIONS OU AMBIGUÏTÉS", "Aucune ambiguïté bloquante."),
))


def plan():
    return {
        "scene_setup": OPENING, "continuity_invariants": ["Same two fighters, weapons and courtyard."],
        "beats": [{"beat_id": "exchange", "start_ms": 0, "end_ms": 8000,
            "primary_action": "Attack, parry and counterattack.", "participants": ["swordswoman", "shield_bearer"],
            "observable_end_state": END,
            "steps": [
                {"step_id": "attack", "start_ms": 0, "end_ms": 4000,
                 "action": "The swordswoman slashes; the shield bearer parries and disengages.",
                 "continuity_after": "The blade is redirected outward and both fighters remain within reach."},
                {"step_id": "counter", "start_ms": 4000, "end_ms": 8000,
                 "action": "He counters as she retreats; their feet keep adjusting through the cut.",
                 "continuity_after": END}]}],
        "final_state": {"description": END, "final_hold_ms": 0},
        "motion_contract": {"primary_motion": END, "end_behavior": "continue_motion"},
        "dialogue_cues": [], "camera_directives": [], "risks": [], "technical_adjustments": [],
        "overall_soundscape": "N/A", "non_diegetic_music": "N/A",
    }


def response_pair(mode, multi):
    if multi:
        value = state_plan()
        value.update(scene_setup=OPENING, continuity_invariants=["Same fighters and weapons."], overall_soundscape="N/A")
        value["final_state"]["description"] = END
        for index, shot in enumerate(value["shots"]):
            shot.update(opening_composition=OPENING, purpose="Exchange initiative", new_information="A tactical response",
                        continuity_from_previous=None if index == 0 else "Same fighters, disengaged weapons and courtyard.",
                        actions=[ACTION], observable_end_state=END)
        return value, f"shot_1:\n{ACTION}\nshot_2:\n{ACTION}\noverall_soundscape:\nN/A\nnon_diegetic_music:\nN/A"
    body = (f"scene_setup:\nThe target video is one continuous 8-second shot. {OPENING}\nshot_1:\n{ACTION}"
            if mode == "ref2v" else f"integrated_multimodal_description:\n[Shot 1] The target video is one continuous 8-second shot. {OPENING} {ACTION}")
    return plan(), body + "\noverall_soundscape:\nN/A\nnon_diegetic_music:\nN/A"


def direct_body(multi=False):
    if multi:
        return json.dumps({"shots": [{"duration_ms": 4000, "opening_composition": OPENING,
                                      "camera_motion": "static_shot", "description": ACTION} for _ in range(2)],
                           "final_state": END, "dialogue_cues": [], "overall_soundscape": "N/A", "non_diegetic_music": "N/A"})
    return json.dumps({"camera_motion": "static_shot", "integrated_multimodal_description": OPENING + " " + ACTION,
                       "overall_soundscape": "N/A", "non_diegetic_music": "N/A"})


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class CombatPreparationTest(unittest.TestCase):
    def test_nine_recipes_pin_profiles_and_stage_ownership(self):
        catalog = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        profiles = LocalPromptProfileCatalog(ROOT / "prompt_profiles")
        recipes = [r for r in catalog.list() if r.preparation == COMBAT]
        self.assertEqual(len(recipes), 9)
        for recipe in recipes:
            with self.subTest(recipe=recipe.reference):
                profile = profiles.get(recipe.profile_id, recipe.profile_version)
                self.assertEqual(profile.preparation, COMBAT)
                self.assertEqual(recipe.preparation, COMBAT)
                self.assertIn("COMBAT PREPARATION 1.0.0", recipe.final_prompt_system_prompt)
                self.assertIn("COMBAT PREPARATION 1.0.0", profile.brief_system_prompt)
                if recipe.preparation_steps == 1:
                    self.assertEqual(recipe.stages, ("final_prompt",))
                    self.assertIsNone(recipe.beat_sheet_system_prompt)
                else:
                    self.assertIn("COMBAT PLAN OWNERSHIP", recipe.beat_sheet_system_prompt)
                    self.assertIn("COMBAT WRITER OWNERSHIP", recipe.final_prompt_system_prompt)
                    self.assertIn("approved Brief" if recipe.preparation_steps == 3 else "raw intention", recipe.beat_sheet_system_prompt)

    def test_all_routes_compile_without_extra_calls_and_preserve_family_on_reopen(self):
        for mode, multi in (("fl2va", False), ("fl2va", True), ("ref2v", False)):
            for route, calls in (("guided", 3), ("planned", 2), ("prompt", 1)):
                with self.subTest(mode=mode, multi=multi, route=route), tempfile.TemporaryDirectory() as directory:
                    value, writer = response_pair(mode, multi)
                    responses = ([BRIEF] if route == "guided" else []) + ([direct_body(multi)] if route == "prompt" else [json.dumps(value), writer])
                    service, gateway, session, composition = preparation_service(directory, mode, route, responses,
                        multishot=multi, preparation_family="combat", source_text=INTENT,
                        roles=("first_frame", "last_frame") if mode == "fl2va" else ("subject_reference",))
                    if route == "guided":
                        lab = PromptLabService(gateway=gateway, profiles=LocalPromptProfileCatalog(ROOT / "prompt_profiles"),
                                               assets=service.assets, sessions=service.sessions)
                        lab.structure_brief(session.session_id, INTENT, 0, CreativeFreedomAxes(0, 0, 0), creative_audacity=2)
                        lab.approve_brief(session.session_id)
                    if route != "prompt":
                        service.generate(session.session_id, CompositionStage.BEAT_SHEET)
                        service.approve(session.session_id, CompositionStage.BEAT_SHEET)
                    result = service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
                    self.assertIsNotNone(result.final_prompt.active_revision)
                    self.assertEqual(len(gateway.requests), calls)
                    self.assertTrue(all("COMBAT PREPARATION 1.0.0" in r.system_prompt for r in gateway.requests))
                    if calls > 1:
                        self.assertEqual(gateway.requests[-1].images, ())
                    self.assertEqual(LocalPromptSessionStore(directory).get(session.session_id).preparation, COMBAT)
                    self.assertEqual(service.get(session.session_id).cookbook, composition.cookbook)
                    renders = CombatRenderTest().service(directory)
                    renders.sessions, renders.compositions = service.sessions, service.compositions
                    project = renders.get_or_create_from_session(session.session_id)
                    self.assertEqual(project.preparation, COMBAT)
                    self.assertEqual(project.revision_version, H3RenderRevisionVersion.COMBAT)
                    self.assertEqual(project.input_mode, H3RenderInputMode.FL2VA if mode == "fl2va" else H3RenderInputMode.REF2VA)
                    self.assertEqual(project.attempts, ())

    def test_profile_and_cookbook_families_cannot_mix(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, session, composition = preparation_service(directory, "fl2va", "prompt", [], preparation_family="combat")
            with self.assertRaisesRegex(ValueError, "family/version"):
                service.configure(session.session_id, "minimax.h3.fl2va.direct.prompt", "1.2.0", composition.bindings, composition.preparation_intent)
            service.sessions.save(replace(session, preparation=VideoPreparationRef()))
            with self.assertRaisesRegex(ValueError, "family/version"):
                service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
            self.assertEqual(gateway.requests, [])

    def test_native_input_modes_keep_their_frame_roles(self):
        for roles, mode in (((), H3RenderInputMode.T2VA), (("first_frame",), H3RenderInputMode.I2VA),
                            (("last_frame",), H3RenderInputMode.L2VA), (("first_frame", "last_frame"), H3RenderInputMode.FL2VA)):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                service, gateway, session, _ = preparation_service(directory, "fl2va", "prompt", [direct_body()],
                    roles=roles, preparation_family="combat", source_text=INTENT)
                service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
                renders = CombatRenderTest().service(directory)
                renders.sessions, renders.compositions = service.sessions, service.compositions
                project = renders.get_or_create_from_session(session.session_id)
                self.assertEqual(project.input_mode, mode)
                self.assertEqual(project.preparation, COMBAT)
                self.assertEqual(len(gateway.requests), 1)
                self.assertEqual(len(gateway.requests[0].images), len(roles))

    def test_classic_resolved_templates_match_prepatch_snapshot(self):
        snapshot = json.loads((ROOT / "tests/fixtures/h3_classic_prompt_baseline.json").read_text(encoding="utf-8"))
        catalog = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        profiles = LocalPromptProfileCatalog(ROOT / "prompt_profiles")
        for key, expected in snapshot["cookbooks"].items():
            name, version = key.split("@")
            manifest = json.loads((ROOT / "prompt_cookbooks" / name / version / "manifest.json").read_text(encoding="utf-8"))
            recipe = catalog.get(name, version)
            self.assertEqual(fingerprint({k: getattr(recipe, k + "_prompt") for k in manifest["templates"]}), expected, key)
        for key, expected in snapshot["profiles"].items():
            name, version = key.split("@")
            profile = profiles.get(name, version)
            keys = ("analysis_system", "analysis_user", "revision_system", "revision_user", "brief_system", "brief_user", "brief_revision_system", "brief_revision_user")
            self.assertEqual(fingerprint({k: getattr(profile, k + "_prompt") for k in keys}), expected, key)

    def test_editing_combat_block_does_not_change_classic_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "prompt_cookbooks"
            shutil.copytree(ROOT / "prompt_cookbooks", destination)
            before = LocalPromptCookbookCatalog(destination)
            classic = before.get("minimax.h3.fl2va.direct.prompt", "1.2.0").final_prompt_system_prompt
            path = destination / "_blocks/h3-combat/1.0.0/choreography.system.txt"
            path.write_text(path.read_text(encoding="utf-8") + "\nISOLATION_FIXTURE", encoding="utf-8")
            after = LocalPromptCookbookCatalog(destination)
            self.assertEqual(after.get("minimax.h3.fl2va.direct.prompt", "1.2.0").final_prompt_system_prompt, classic)
            self.assertIn("ISOLATION_FIXTURE", after.get("minimax.h3.fl2va.combat.prompt", "1.0.0").final_prompt_system_prompt)
            combat_writer = after.get("minimax.h3.fl2va.combat.guided", "1.0.0").final_prompt_system_prompt
            classic_file = destination / "minimax.h3.fl2va.direct/0.4.0/final_prompt.system.txt"
            classic_file.write_text(classic_file.read_text(encoding="utf-8") + "\nCLASSIC_FIXTURE", encoding="utf-8")
            after_classic_edit = LocalPromptCookbookCatalog(destination)
            self.assertIn("CLASSIC_FIXTURE", after_classic_edit.get("minimax.h3.fl2va.direct.guided", "1.2.0").final_prompt_system_prompt)
            self.assertEqual(after_classic_edit.get("minimax.h3.fl2va.combat.guided", "1.0.0").final_prompt_system_prompt, combat_writer)

    def test_changing_family_forks_cleanly_without_inheriting_a_classic_brief_variant(self):
        with tempfile.TemporaryDirectory() as directory:
            service, gateway, session, _ = preparation_service(directory, "fl2va", "guided", [])
            profiles = LocalPromptProfileCatalog(ROOT / "prompt_profiles")
            classic = profiles.get("minimax.h3.fl2va.direct", "0.6.0")
            source = replace(session, profile_version=classic.version,
                             brief_variant_id=classic.brief_variants[0].variant_id,
                             brief_variant_version=classic.brief_variants[0].version)
            service.sessions.save(source)
            lab = PromptLabService(gateway=gateway, profiles=profiles, assets=service.assets, sessions=service.sessions)
            forked = lab.fork_session(source.session_id, profile_id="minimax.h3.fl2va.combat", profile_version="1.0.0")
            self.assertEqual(forked.preparation, COMBAT)
            self.assertIsNone(forked.brief_variant_id)
            self.assertEqual(forked.brief_revisions, ())
            self.assertEqual([r.asset_id for r in forked.references], [r.asset_id for r in source.references])
            self.assertEqual(service.sessions.get(source.session_id), source)
            self.assertEqual(gateway.requests, [])

    def test_zero_extra_motion_still_allows_the_requested_fight_and_no_effect_quota(self):
        policy = creative_freedom_policy(0, CreativeFreedomAxes(0, 0, 0), preparation=COMBAT)
        self.assertIn("necessary attack, defense, contact, recoil and recovery", policy)
        self.assertNotIn("COMBAT", creative_freedom_policy(0, CreativeFreedomAxes(0, 0, 0)))
        self.assertIn("not quotas", creative_audacity_policy(3, preparation=COMBAT))
        self.assertNotEqual(creative_audacity_policy(3), creative_audacity_policy(3, preparation=COMBAT))

    def test_legacy_session_schema_nine_reads_as_classic(self):
        with tempfile.TemporaryDirectory() as directory:
            service, _, session, _ = preparation_service(directory, "fl2va", "prompt", [])
            path = Path(directory) / "prompt_sessions" / session.session_id / "session.json"
            data = json.loads(path.read_text(encoding="utf-8")); data["schema_version"] = 9; data.pop("preparation"); data.pop("combat_settings")
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(LocalPromptSessionStore(directory).get(session.session_id).preparation, VideoPreparationRef())


class CombatRenderTest(unittest.TestCase):
    def service(self, directory):
        class NoRender:
            def submit_workflow(self, *args):
                raise AssertionError("No generation belongs in preparation tests")
        return H3RenderService(gateway=object(), comfy=NoRender(), assets=LocalAssetStore(directory),
            projects=LocalH3RenderProjectStore(directory), sessions=object(), compositions=object(),
            workflow=H3RenderPresetRecipe(load_h3_render_workflow(WORKFLOW_DIRECTORY)),
            ref2v_workflow=Ref2VH3RenderPresetRecipe(VideoLabPresetRecipe(load_video_lab_workflow(REF2V_WORKFLOW_DIRECTORY))),
            combat_revision_policies=(load_combat_revision_policy(ROOT / "prompt_cookbooks/_blocks"),))

    def test_post_render_keeps_its_own_policy_and_rejects_cross_family_revisions(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.service(directory)
            for mode in (H3RenderInputMode.T2VA, H3RenderInputMode.REF2VA):
                refs = {"reference_asset_ids": ("ref-1",), "reference_labels": ("Fighter",)} if mode is H3RenderInputMode.REF2VA else {}
                project = H3RenderProject("combat-" + mode.value, "session", "revision", "fixture", mode, PROMPT,
                    preparation=COMBAT, revision_version=H3RenderRevisionVersion.COMBAT, **refs)
                service.projects.create(project)
                request = service._completion_request(project, "La parade doit repousser la lame.", include_reasoning=False, creative_audacity=3)
                self.assertIn("COMBAT POST-RENDER REVISION 1.0.0", request.system_prompt)
                self.assertIn("COMBAT REVISION AUDACITY 1.0.0", request.user_prompt)
                self.assertIn("combat.render.revision@1.0.0", request.operation_id)
                self.assertEqual(service.get(project.project_id).preparation, COMBAT)
                self.assertEqual(service.revision_versions_for_mode(mode, COMBAT), (H3RenderRevisionVersion.COMBAT,))
                with self.assertRaisesRegex(ValueError, "different preparation family"):
                    project.select_revision_version(H3RenderRevisionVersion.VOCAL)
                classic = replace(project, preparation=VideoPreparationRef(), revision_version=H3RenderRevisionVersion.VOCAL)
                self.assertNotIn("COMBAT", service._completion_request(classic, "Corrige la parade", include_reasoning=False, creative_audacity=None).system_prompt)
            with self.assertRaisesRegex(ValueError, "unavailable"):
                service.default_revision_version(H3RenderInputMode.I2VA, VideoPreparationRef("combat", "9.0.0"))

    def test_conversion_preserves_combat_family_frames_settings_and_single_call(self):
        with tempfile.TemporaryDirectory() as directory:
            service, source, setup, _ = conversion_fixtures.H3Ref2VConversionTest().service(directory)
            source = replace(source, preparation=COMBAT, revision_version=H3RenderRevisionVersion.COMBAT)
            service.renders.projects.save(source)
            target = service.prepare(source.project_id, request_id="combat-conversion", prompt=PROMPT, model_id="fixture", setup=setup)
            target = list(service.stream(target.project_id))[-1].project
            self.assertEqual(target.preparation, COMBAT)
            self.assertEqual(target.revision_version, H3RenderRevisionVersion.COMBAT)
            self.assertEqual(target.adaptation.render_setup, setup)
            self.assertEqual(target.reference_asset_ids, (source.first_frame_asset_id, source.last_frame_asset_id))
            self.assertEqual(len(service.renders.gateway.requests), 1)
            self.assertEqual(target.attempts, ())
            self.assertEqual(LocalH3RenderProjectStore(directory).get(target.project_id).preparation, COMBAT)

    def test_legacy_render_schema_six_stays_classic(self):
        from panelforge.infrastructure.storage.h3_render_projects import _serialize, _deserialize
        classic = H3RenderProject("classic", "session", "revision", "fixture", H3RenderInputMode.T2VA, PROMPT,
                                  revision_version=H3RenderRevisionVersion.VOCAL)
        raw = _serialize(classic)
        self.assertEqual(raw["schema_version"], 12)
        raw["schema_version"] = 6
        raw.pop("preparation")
        self.assertEqual(_deserialize(raw), classic)
