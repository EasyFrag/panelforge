"""Offline fixtures; never connect to a model or ComfyUI."""
import json
from pathlib import Path
import tempfile
import unittest

from panelforge.application.vocal_policy import (
    speech_lines, validate_brief_speech, validate_revision_speech, validate_speech,
)
from panelforge.application.video_preparation import compile_direct_prompt
from panelforge.domain.prompt_lab import BriefRevision, CreativeFreedomAxes, PromptLabSession, PromptSessionMode, RevisionOrigin
from panelforge.infrastructure.prompt_profiles import LocalPromptProfileCatalog
from panelforge.infrastructure.prompt_cookbooks import LocalPromptCookbookCatalog
from panelforge.infrastructure.storage import LocalPromptSessionStore

ROOT = Path(__file__).resolve().parents[1]


class VocalPolicyTest(unittest.TestCase):
    def test_ref2v_plan_and_writer_preserve_the_first_decision(self):
        from panelforge.domain import BriefReferenceSnapshot, CompositionStage
        from tests.test_video_preparation_recipes import preparation_service
        from tests.test_direct_ref2v_composition import action_plan_v4, final_document
        for route in ("planned", "guided"):
            with self.subTest(route=route), tempfile.TemporaryDirectory() as directory:
                plan = action_plan_v4(dialogue_text="Here you go.")
                plan["dialogue_cues"][0]["language"] = "English"
                service, gateway, session, _ = preparation_service(directory, "ref2v", route,
                    [json.dumps(plan), final_document(camera_owned=True, with_dialogue_placeholder=True)],
                    version="1.1.0", profile_version="0.6.0", creative_axes=CreativeFreedomAxes(1, 0, 1, 2),
                    source_text="A courier hands over a parcel in 12 seconds.")
                if route == "guided":
                    brief = BriefRevision("brief-fixture", "A courier hands over a parcel in 12 seconds.",
                        'The courier says <d>[English] Here you go.</d> while handing over the parcel.', 35,
                        RevisionOrigin.MODEL,
                        tuple(BriefReferenceSnapshot(ref.reference_id, None, ref.uses) for ref in session.references),
                        creative_axes=CreativeFreedomAxes(1, 0, 1, 2), vocal_dialogues=("Here you go.",))
                    service.sessions.save(session.add_brief_revision(brief).approve_brief())
                service.generate(session.session_id, CompositionStage.BEAT_SHEET)
                service.approve(session.session_id, CompositionStage.BEAT_SHEET)
                result = service.generate(session.session_id, CompositionStage.FINAL_PROMPT)
                prompt = result.document(CompositionStage.FINAL_PROMPT).active_revision.content
                self.assertEqual(speech_lines(prompt), (("English", "Here you go."),))
                self.assertIn("VOCAL POLICY", gateway.requests[0].system_prompt)
                self.assertIn("already decided", gateway.requests[1].system_prompt)
                self.assertEqual(len(gateway.requests), 2)

    def test_permissions_silence_language_and_duration(self):
        lines = (("English", "What is that?"),)
        for level in (0, 1):
            with self.subTest(level=level), self.assertRaises(ValueError):
                validate_speech(lines, (), level=level, source_text="", duration_ms=8000)
        self.assertEqual(validate_speech(lines, (), level=2, source_text=""), ("What is that?",))
        for changed in (
            dict(lines=lines * 2, level=2, source_text=""),
            dict(lines=lines, level=3, source_text="No dialogue"),
            dict(lines=(("French", "Regarde !"),), level=3, source_text=""),
            dict(lines=lines, level=2, source_text="", duration_ms=500),
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_speech(protected=(), **changed)

    def test_requested_french_is_preserved_and_downstream_is_locked(self):
        lines = (("French", "Ne touche pas !"), ("English", "Wow!"))
        validate_speech(lines, ("Ne touche pas !",), level=2, source_text="",
                        locked=("Ne touche pas !", "Wow!"))
        with self.assertRaises(ValueError):
            validate_speech(lines[:1], ("Ne touche pas !",), level=2, source_text="",
                            locked=("Ne touche pas !", "Wow!"))
        with self.assertRaises(ValueError):
            validate_speech((("French", "Ne touche pas."),), ("Ne touche pas !",), level=0, source_text="")

    def test_brief_records_only_spontaneous_lines(self):
        text = 'Requested: "Bonjour !". She raises her head and says <d>[English] Wow!</d>'
        self.assertEqual(validate_brief_speech(text, ("Bonjour !",), level=2,
                         source_text='"Bonjour !"', duration_ms=8000), ("Wow!",))

    def test_revision_does_not_erase_words_during_a_camera_change(self):
        before = 'She says <d>[English] Wow!</d>'
        with self.assertRaises(ValueError):
            validate_revision_speech(before, 'She looks around.', 'Change la caméra.', level=2, duration_ms=8000)
        validate_revision_speech(before, 'She looks around.', 'Retire le dialogue.', level=0, duration_ms=8000)
        validate_revision_speech(before, before, 'Change la caméra.', level=0, duration_ms=8000)

    def test_one_call_compiler_permits_then_protects_selected_line(self):
        context = {"mode": "t2va", "header": "", "duration_ms": 8000, "dialogues": [],
                   "vocal_policy_version": "1.0.0", "dialogue_level": 2, "source_text": "She finds a gemstone."}
        fields = {"camera_motion": "static_shot", "integrated_multimodal_description":
                  "She lifts the gemstone and says <d>[English] What is that?</d>",
                  "overall_soundscape": "N/A", "non_diegetic_music": "N/A"}
        self.assertIn("What is that?", compile_direct_prompt(json.dumps(fields), json.dumps(context)))
        context["chosen_dialogues"] = ["What is that?"]
        fields["integrated_multimodal_description"] = "She lifts the gemstone."
        with self.assertRaises(ValueError):
            compile_direct_prompt(json.dumps(fields), json.dumps(context))

    def test_versioned_catalogs_and_history(self):
        profiles = LocalPromptProfileCatalog(ROOT / "prompt_profiles")
        recipes = LocalPromptCookbookCatalog(ROOT / "prompt_cookbooks")
        for family, version, old in (("fl2va.direct", "1.2.0", "1.1.0"),
                                     ("fl2va.direct.multishot", "1.1.0", "1.0.0"),
                                     ("ref2v.direct", "1.1.0", "1.0.0")):
            for route in ("guided", "planned", "prompt"):
                key = f"minimax.h3.{family}.{route}"
                self.assertEqual(recipes.get(key, version).vocal_policy_version, "1.0.0")
                self.assertIsNone(recipes.get(key, old).vocal_policy_version)
        self.assertEqual(profiles.get("minimax.h3.fl2va.direct", "0.6.0").vocal_policy_version, "1.0.0")

    def test_brief_roundtrip_and_old_schema_default(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalPromptSessionStore(directory)
            session = PromptLabSession("vocal-session", "fixture", "minimax.h3.fl2va.direct", "0.6.0", (),
                                       session_mode=PromptSessionMode.H3_BASE)
            brief = BriefRevision("brief-1", "She finds a gemstone.", "She says Wow!", 35,
                                  RevisionOrigin.MODEL, (), creative_axes=CreativeFreedomAxes(1, 0, 1, 2),
                                  vocal_dialogues=("Wow!",))
            store.create(session.add_brief_revision(brief))
            reopened = store.get(session.session_id)
            self.assertEqual(reopened.active_brief_revision.vocal_dialogues, ("Wow!",))
            self.assertEqual(reopened.active_brief_revision.creative_axes.dialogue, 2)
            from panelforge.infrastructure.storage.prompt_sessions import _session_from_dict, _session_to_dict
            raw = _session_to_dict(reopened, created_at="2026-09-09T12:00:00+00:00", updated_at="2026-09-09T12:00:00+00:00")
            raw["schema_version"] = 8
            for item in raw["brief_revisions"]:
                item.pop("vocal_dialogues"); item["creative_axes"].pop("dialogue")
            old = _session_from_dict(raw, schema_version=8)
            self.assertEqual(old.active_brief_revision.vocal_dialogues, ())
            self.assertEqual(old.active_brief_revision.creative_axes.dialogue, 0)
