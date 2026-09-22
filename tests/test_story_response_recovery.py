"""Data-only recovery regressions; no model or live workspace."""
import unittest

from panelforge.domain.story_response_recovery import StoryJsonError, assert_format_only, decode_response


class StoryResponseRecoveryTest(unittest.TestCase):
    def test_literal_replace_is_resolved_without_interpreting_code(self):
        raw = '{"reply": "Texte en French".replace("French", "français"), "keep": [8, true, null]}'
        result, repairs = decode_response(raw)
        self.assertEqual(result, {"reply": "Texte en français", "keep": [8, True, None]})
        self.assertEqual(len(repairs), 1)

    def test_code_and_unknown_methods_remain_invalid(self):
        for value in ('"text".replace("text", __import__("os"))', '"text".upper()', '"text".replace("", "x")'):
            with self.subTest(value=value), self.assertRaises(StoryJsonError):
                decode_response('{"reply": ' + value + '}')

    def test_method_text_inside_a_string_is_not_touched(self):
        raw = '{"reply":"Une méthode .replace() est citée.",}'
        result, repairs = decode_response(raw)
        self.assertEqual(result["reply"], "Une méthode .replace() est citée.")
        self.assertFalse(repairs)

    def test_format_fallback_cannot_rewrite_scalars(self):
        assert_format_only('{"a": "texte" "b": 8}', '{"a": "texte", "b": 8}')
        for corrected in ('{"a":"autre","b":8}', '{"a":"texte","b":10}'):
            with self.assertRaisesRegex(ValueError, "modifie le contenu"):
                assert_format_only('{"a":"texte" "b":8}', corrected)
