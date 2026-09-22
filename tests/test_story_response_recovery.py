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

    def test_duplicate_delivery_is_recovered_locally_without_changing_text(self):
        original = '{"text":"Il a du jus.","delivery":"delivery":"spoken"}'
        corrected = '{"text":"Il a du jus.","delivery":"spoken"}'
        data, notes = decode_response(original)
        self.assertEqual(data, {"text": "Il a du jus.", "delivery": "spoken"})
        self.assertTrue(notes)
        assert_format_only(original, corrected)

    def test_flat_scalar_equality_cannot_hide_reparenting(self):
        with self.assertRaisesRegex(ValueError, "modifie le contenu"):
            assert_format_only('{"a":{"b":1},"c":2}', '{"a":{"b":1,"c":2}}')

    def test_duplicate_keys_truncation_and_nonfinite_numbers_are_not_guessed(self):
        for raw in ('{"delivery":"spoken","delivery":"thought"}', '{"a":"texte"', '{"x":NaN}', '{"x":1e999}'):
            with self.subTest(raw=raw), self.assertRaises(StoryJsonError):
                decode_response(raw)

    def test_key_like_text_inside_dialogue_is_unchanged(self):
        # Build the literal using json to ensure this is dialogue data, not malformed JSON.
        import json
        value = {"text": 'Il dit : "delivery": "delivery": "spoken".', "delivery": "spoken"}
        result, notes = decode_response(json.dumps(value))
        self.assertEqual(result, value)
        self.assertFalse(notes)
