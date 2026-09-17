"""Offline checks for conservative post-Writer voice-over normalization."""

from copy import deepcopy
import json
import unittest

from panelforge.application import classic_cinematic as classic
from panelforge.application.vocal_delivery import normalize_voiceovers, voiceover_cues
from tests.test_classic_cinematic import fixture


class VocalDeliveryTest(unittest.TestCase):
    def test_reads_structured_story_labels_without_treating_off_screen_as_voiceover(self):
        source = (
            "Léa — VOIX OFF : « Je revis ! »\n"
            "Tom — DERRIÈRE LA PORTE : « Léa ? »\n"
            "Léa — PENSÉE / VOIX INTÉRIEURE : « Reste calme. »"
        )
        cues = voiceover_cues(source)
        self.assertEqual([cue.delivery for cue in cues], ["voice_over", "spoken", "thought"])
        self.assertEqual([cue.speaker_id for cue in cues], ["S1", "S2", "S1"])

    def test_known_writer_wrapper_gets_canonical_phrase_and_closed_lips(self):
        source = "Léa — VOIX OFF : « Enfin… je revis ! »"
        content = "Léa's (<Picture 1>) off-screen voice narrates <d>[French] Enfin… je revis !</d> as she relaxes."
        result = normalize_voiceovers(content, source)
        self.assertEqual(result.applied, 1)
        self.assertEqual(result.warnings, ())
        self.assertIn("Léa (<Picture 1>) (S1) says in an off-screen voiceover:", result.content)
        self.assertIn("</d> while all visible characters keep their lips completely closed and still as she relaxes.", result.content)

    def test_ambiguous_wrapper_is_preserved_with_a_warning_and_other_prompts_are_identical(self):
        source = "Léa — VOIX OFF : « Enfin… je revis ! »"
        ambiguous = "A memory passes through her mind: <d>[French] Enfin… je revis !</d>."
        result = normalize_voiceovers(ambiguous, source)
        self.assertEqual(result.content, ambiguous)
        self.assertEqual(result.applied, 0)
        self.assertEqual(len(result.warnings), 1)
        ordinary = "Léa says <d>[French] Bonjour.</d>."
        self.assertEqual(normalize_voiceovers(ordinary, "Léa : « Bonjour. »").content, ordinary)

    def test_classic_h3_and_ref2v_apply_the_same_optional_post_compiler(self):
        line = "Enfin… je revis !"
        source = f"Léa — VOIX OFF : « {line} »"
        prose = f"Her inner voice-over reads <d>[French] {line}</d> as she looks away."
        for mode in ("i2va", "ref2va"):
            with self.subTest(mode=mode):
                plan, _, context = fixture(mode=mode, count=1, source=source)
                plan["spoken_lines"] = [line]
                plan["spoken_languages"] = ["French"]
                plan["shots"][0]["phases"][0]["actions"] = [prose]
                context.update(dialogues=[line], locked_speech=[line])
                context["plan"] = json.loads(classic.canonical_plan(json.dumps(plan, ensure_ascii=False), context))
                approved = classic.Plan.model_validate(context["plan"])
                writer = classic.Writer(
                    shots=tuple(classic.WrittenShot(phases=tuple(
                        " ".join(phase.actions) for phase in shot.phases)) for shot in approved.shots),
                    overall_soundscape=approved.overall_soundscape,
                    non_diegetic_music=approved.non_diegetic_music,
                )
                prompt, encoded = classic._compile(approved, writer, deepcopy(context))
                saved = classic.decode_context(encoded)
                self.assertIn("Léa (S1) says in an off-screen voiceover:", prompt)
                self.assertIn("while all visible characters keep their lips completely closed and still", prompt)
                self.assertEqual(saved["vocal_normalization"]["applied"], 1)


if __name__ == "__main__":
    unittest.main()
