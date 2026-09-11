"""User-run neutral regressions for analysis citations and H3 Plan syntax."""
from copy import deepcopy
import json
import unittest

from panelforge.application import classic_cinematic as classic, combat_sequence as combat
from panelforge.application.combat_cinematic import Plan as CombatPlan
from panelforge.application.media_intention import without_source_citations, source_reference_warning
from panelforge.application.minimax_h3_protocol import lint_h3_prompt
from panelforge.application.vocal_policy import speech_lines
from tests.test_classic_cinematic import fixture as classic_fixture
from tests.test_combat_cinematic import fixture as combat_fixture
from tests.test_media_analysis import MediaAnalysisTest


class IntentionBoundaryTest(unittest.TestCase):
    setUp = MediaAnalysisTest.setUp
    request = MediaAnalysisTest.request

    def test_parenthetical_citations_removed_but_words_and_timing_preserved(self):
        for citation in ("(image 1)", "(images 8-10)", "(images 8–10)", "(images 2 à 5)",
                         "[captures 2, 3 et 4]", "(voir frames 1 to 3)", "(image #8)"):
            with self.subTest(citation=citation):
                text=f"Au début {citation}, la personne ouvre le livre, puis tourne une page."
                expected="Au début, la personne ouvre le livre, puis tourne une page."
                self.assertEqual(without_source_citations(text), expected)
                self.assertIsNone(source_reference_warning(expected))
        text='Elle dit « Regardez (image 8). » puis répond "Look at image 2." À 3 s, elle ferme le livre.'
        self.assertEqual(without_source_citations(text), text)
        self.assertIsNone(source_reference_warning(text))
        for text in ("Elle reprend la pose de l’image 8.", "<Picture 2> marche.", "La frame 10 sert de référence."):
            self.assertEqual(without_source_citations(text), text)
            self.assertIsNotNone(source_reference_warning(text))

    def test_generated_and_old_intentions_are_cleaned_before_transfer(self):
        raw="La personne ouvre le livre (image 1), puis tourne une page (images 8-10)."
        self.gateway.response=json.dumps(dict(intention=raw,observations=["Images 8-10 : une page est tournée."],uncertainties=[]))
        record=self.service.create(self.request())
        saved=list(self.service.stream(record["analysis_id"]))[-1]["record"]
        self.assertNotIn("images 8-10",saved["intention"])
        self.assertIn("images 8-10",saved["generated_intention"])
        self.assertIn("Images 8-10",saved["observations"][0])
        # An old saved analysis is normalized only when the user saves/transfers.
        saved["intention"]=raw;self.store.save(saved)
        cleaned=self.service.save_intention(saved["analysis_id"],raw)
        self.assertEqual(cleaned["intention"],"La personne ouvre le livre, puis tourne une page.")
        self.assertEqual(len(self.gateway.requests),1)
        with self.assertRaisesRegex(ValueError,"renvoie encore"):
            self.service.save_intention(saved["analysis_id"],"Elle reproduit la pose de l’image 8.")
        self.assertEqual(self.store.get(saved["analysis_id"])["intention"],cleaned["intention"])

    def test_inline_references_keep_an_editable_candidate_without_retry(self):
        self.gateway.response=json.dumps(dict(intention="Elle reprend la position de l’image 8.",observations=[],uncertainties=[]))
        record=self.service.create(self.request())
        result=list(self.service.stream(record["analysis_id"]))[-1]["record"]
        self.assertEqual(result["status"],"succeeded")
        self.assertIn("image 8",result["intention"])
        self.assertTrue(result["intention_warning"])
        self.assertEqual(len(self.gateway.requests),1)


class ClassicDialogueBoundaryTest(unittest.TestCase):
    def fixture(self, mode="i2va", *, language="English", words="The book is ready."):
        plan,writer,context=classic_fixture(mode,count=1)
        plan["spoken_lines"]=[words];plan["spoken_languages"]=[language]
        plan["shots"][0]["phases"][0]["actions"]=[f"The visitor says <d>{words}</d>"]
        plan["shots"][0]["pacing"]="The rhythm comes from the page turn rather than any camera motion."
        for phase in plan["shots"][0]["phases"]:
            phase["camera"].update(motion="static_shot",amplitude=None,speed=None,target_clause="")
        context.update(dialogues=[words],locked_speech=[words])
        writer["shots"][0]["phases"][0]=f"The visitor says <d>{words}</d>"
        return plan,writer,context

    def test_plan_and_writer_complete_language_from_explicit_metadata_only(self):
        for mode in ("i2va","ref2va"):
            for language,words in (("English","The book is ready."),("French","Le livre est prêt.")):
                with self.subTest(mode=mode,language=language):
                    plan,writer,context=self.fixture(mode,language=language,words=words)
                    approved=json.loads(classic.canonical_plan(json.dumps(plan),context))
                    self.assertIn(f"<d>[{language}] {words}</d>",approved["shots"][0]["phases"][0]["actions"][0])
                    self.assertEqual(approved["spoken_lines"],[words])
                    context["plan"]=approved
                    output,encoded=classic.compile_result(json.dumps(writer),classic.encode_context(context),"final_prompt")
                    self.assertEqual(speech_lines(output),((language,words),))
                    self.assertEqual(classic.decode_context(encoded)["chosen_speech"],[words])
                    self.assertEqual(classic.prompt_errors(output,mode),())

    def test_old_tagged_plan_works_and_unknown_language_is_never_guessed(self):
        plan,writer,context=self.fixture(language="French",words="Le livre est prêt.")
        plan.pop("spoken_languages")
        with self.assertRaisesRegex(ValueError,"Langue manquante"):
            classic.canonical_plan(json.dumps(plan),context)
        plan["shots"][0]["phases"][0]["actions"]=["The visitor says <d>[fr] Le livre est prêt.</d>"]
        approved=json.loads(classic.canonical_plan(json.dumps(plan),context))
        context["plan"]=approved
        output,_=classic.compile_result(json.dumps(writer),classic.encode_context(context),"final_prompt")
        self.assertEqual(speech_lines(output),(("French","Le livre est prêt."),))
        self.assertIn("spoken_languages",json.loads(classic.schema("beat_sheet"))["required"])
        self.assertNotIn("spoken_languages",CombatPlan.model_json_schema()["properties"])

    def test_no_dialogue_added_or_language_assumed_for_unknown_words(self):
        plan,writer,context=self.fixture()
        context["plan"]=json.loads(classic.canonical_plan(json.dumps(plan),context))
        for words in ("Something else.","Le livre est fermé."):
            bad=deepcopy(writer);bad["shots"][0]["phases"][0]=f"The visitor says <d>{words}</d>"
            with self.assertRaises(ValueError): classic.compile_result(json.dumps(bad),classic.encode_context(context),"final_prompt")
        bad=deepcopy(writer);bad["shots"][0]["phases"][0]="The visitor says <d>[French] The book is ready.</d>"
        with self.assertRaisesRegex(ValueError,"langue déclarée"):
            classic.compile_result(json.dumps(bad),classic.encode_context(context),"final_prompt")
        contradictory=deepcopy(plan)
        contradictory["spoken_languages"]=["French"]
        contradictory["shots"][0]["phases"][0]["actions"]=["The visitor says <d>[English] The book is ready.</d>"]
        with self.assertRaisesRegex(ValueError,"contradictoires"):
            classic.canonical_plan(json.dumps(contradictory),context)

    def test_general_camera_fix_is_adopted_in_both_families(self):
        for family,fixture in ((classic,classic_fixture),(combat,combat_fixture)):
            plan,writer,context=fixture("ref2va",count=1)
            plan["shots"][0]["pacing"]="The rhythm comes from subject motion rather than any camera motion."
            for phase in plan["shots"][0]["phases"]:
                phase["camera"].update(motion="static_shot",amplitude=None,speed=None,target_clause="")
            context["plan"]=json.loads(family.canonical_plan(json.dumps(plan),context))
            prompt,_=family.compile_result(json.dumps(writer),family.encode_context(context),"final_prompt")
            self.assertNotIn("free_camera_motion",{issue.code for issue in lint_h3_prompt("ref2va",prompt)})
