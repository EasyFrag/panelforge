"""User-run protection regressions. Only synthetic images and fake model/render gateways."""
from copy import deepcopy
from io import BytesIO
import json
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from panelforge.domain import image_journeys as journey
from panelforge.domain.image_journey_masks import VERSION, dimensions_3mp, validate_plan
from panelforge.infrastructure.image_journey_masks import PillowJourneyMasks
from test_image_journeys import ImageJourneyFixture
import test_image_journey_edits as edits_fixture
from test_qwen_edit import png


def rectangle(left, top, right, bottom):
    return [dict(x=x, y=y) for x, y in ((left, top), (right, top), (right, bottom), (left, bottom))]


def mask_plan():
    return dict(observation='Travaux au centre, décor conservé.', regions=[
        dict(label='Travaux', outline=rectangle(200, 200, 800, 800), holes=[])])


def array(content):
    with Image.open(BytesIO(content)) as image:
        return np.array(image.convert('RGBA'))


class MaskCompositionTest(unittest.TestCase):
    def test_source_pixels_are_exact_outside_mask_and_generated_pixels_inside(self):
        # Different colors everywhere simulate unwanted global generative drift.
        before, raw = png('navy', size=(256, 256)), png('orange', size=(256, 256))
        result = PillowJourneyMasks().compose(before, raw, mask_plan())
        mask = np.array(Image.open(BytesIO(result.mask_png)))
        actual, original, generated = array(result.image_png), array(before), array(raw)
        np.testing.assert_array_equal(actual[mask == 0], original[mask == 0])
        np.testing.assert_array_equal(actual[mask == 255], generated[mask == 255])
        self.assertTrue(np.any((mask > 0) & (mask < 255)))
        self.assertGreater(result.coverage, 0)
        self.assertLess(result.coverage, 1)

    def test_unchanged_holes_and_disconnected_regions(self):
        plan = mask_plan()
        plan['regions'][0]['holes'] = [rectangle(400, 400, 600, 600)]
        plan['regions'].append(dict(label='Ombre séparée', outline=rectangle(20, 20, 120, 120), holes=[]))
        before, raw = png('navy', size=(256, 256)), png('orange', size=(256, 256))
        actual = array(PillowJourneyMasks().compose(before, raw, plan).image_png)
        np.testing.assert_array_equal(actual[128, 128], array(before)[128, 128])
        np.testing.assert_array_equal(actual[16, 16], array(raw)[16, 16])
        np.testing.assert_array_equal(actual[16, 128], array(before)[16, 128])

    def test_empty_edit_preserves_every_source_pixel(self):
        before = png('navy', size=(160, 96))
        result = PillowJourneyMasks().compose(before, png('orange'), dict(observation='Aucun ajout visible.', regions=[]))
        np.testing.assert_array_equal(array(result.image_png), array(before))
        self.assertEqual(result.coverage, 0)

    def test_previous_addition_survives_outside_the_next_edit(self):
        first_plan = mask_plan()
        first_plan['regions'][0]['outline'] = rectangle(100, 200, 400, 800)
        second_plan = mask_plan()
        second_plan['regions'][0]['outline'] = rectangle(600, 200, 900, 800)
        initial = png('navy', size=(256, 256))
        first = PillowJourneyMasks().compose(initial, png('green', size=(256, 256)), first_plan)
        second = PillowJourneyMasks().compose(first.image_png, png('orange', size=(256, 256)), second_plan)
        actual = array(second.image_png)
        np.testing.assert_array_equal(actual[128, 64], array(first.image_png)[128, 64])
        self.assertNotEqual(tuple(actual[128, 64]), tuple(array(initial)[128, 64]))
        np.testing.assert_array_equal(actual[128, 192], array(png('orange', size=(256, 256)))[128, 192])

    def test_resolution_mismatch_is_rejected_without_resizing(self):
        with self.assertRaisesRegex(ValueError, 'mêmes dimensions'):
            PillowJourneyMasks().compose(png(size=(160, 96)), png(size=(320, 192)), mask_plan())

    def test_invalid_or_unbounded_geometry_is_rejected(self):
        for invalid in (True, float('nan'), float('inf'), -1, 1001):
            with self.subTest(value=invalid):
                plan = mask_plan()
                plan['regions'][0]['outline'][0]['x'] = invalid
                with self.assertRaises(ValueError):
                    validate_plan(plan)
        for vertices in ([], rectangle(500, 500, 500, 500)):
            plan = mask_plan()
            plan['regions'][0]['outline'] = vertices
            with self.assertRaises(ValueError):
                validate_plan(plan)

    def test_3mp_profile_matches_audited_tree_dimensions_and_limits(self):
        self.assertEqual(dimensions_3mp((1120, 1984)), (1344, 2368))
        for size in ((128, 128), (6000, 1000), (1000, 6000)):
            dimensions = dimensions_3mp(size)
            self.assertTrue(all(64 <= v <= 4096 and v % 32 == 0 for v in dimensions))


class JourneyProtectionTest(ImageJourneyFixture):
    def mask_calls(self):
        return [request for request in self.gateway.requests if request.operation_id == VERSION]

    def test_protected_outputs_feed_analysis_next_render_and_transition_export(self):
        self.create_journey(count=2, auto_mask=True)
        result = self.until('completed')
        first, last = result['steps']
        self.assertTrue(result['auto_mask'])
        self.assertEqual(last['source_asset_id'], first['output_asset_id'])
        self.assertNotEqual(first['raw_output_asset_id'], first['output_asset_id'])
        self.assertEqual(result['current_asset_id'], last['output_asset_id'])
        self.assertEqual(len(self.comfy.submitted), 2)
        self.assertEqual(len(self.mask_calls()), 2)
        self.assertTrue(all(r.model_id == 'progression-vision' for r in self.mask_calls()))
        self.assertEqual(self.progression_calls()[1].images[1].content,
                         self.assets.read_bytes(first['output_asset_id']))
        frames = journey.sequence(result)['frames']
        self.assertEqual(frames[-1]['asset_id'], last['output_asset_id'])
        for step in result['steps']:
            before = array(self.assets.read_bytes(step['source_asset_id']))
            output = array(self.assets.read_bytes(step['output_asset_id']))
            mask = np.array(Image.open(BytesIO(self.assets.read_bytes(step['protection']['mask_asset_id']))))
            np.testing.assert_array_equal(output[mask == 0], before[mask == 0])

    def test_independent_mask_model_survives_restart_and_does_not_replace_other_roles(self):
        project = self.create_journey(count=1, auto_mask=True, mask_model_id=journey.DEFAULT_MASK_MODEL_ID)
        self.journeys = self.new_service()
        self.journeys.recover()
        # An older client omitting this field must retain the persisted selection.
        self.resume_journey()
        result = self.until('completed')
        self.assertEqual(result['mask_model_id'], journey.DEFAULT_MASK_MODEL_ID)
        self.assertTrue(all(r.model_id == 'progression-vision' for r in self.progression_calls()))
        other_calls = [r for r in self.gateway.requests if r not in self.progression_calls() + self.mask_calls()]
        self.assertTrue(other_calls)
        self.assertTrue(all(r.model_id == 'minimax-prompter' for r in other_calls))
        self.assertEqual([r.model_id for r in self.mask_calls()], [journey.DEFAULT_MASK_MODEL_ID])
        public = self.journeys.public(result)
        self.assertEqual(public['steps'][0]['protection']['model_id'], journey.DEFAULT_MASK_MODEL_ID)
        self.assertNotIn('raw', public['steps'][0]['protection'])
        self.assertEqual(result['id'], project['id'])

    def test_failed_analysis_can_switch_only_mask_model_and_keep_raw_render(self):
        self.create_journey(count=1, auto_mask=True, mask_model_id='first-mask-model')
        pending = self.until('protecting')['steps'][0]
        self.gateway.bad_mask = True
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()['status'], 'paused')
        self.gateway.bad_mask = False
        self.resume_journey(mask_model_id=journey.DEFAULT_MASK_MODEL_ID)
        result = self.until('completed')
        self.assertEqual(result['progression_model_id'], 'progression-vision')
        self.assertEqual(result['prompt_model_id'], 'minimax-prompter')
        self.assertEqual(result['steps'][0]['id'], pending['id'])
        self.assertEqual(result['steps'][0]['raw_output_asset_id'], pending['raw_output_asset_id'])
        self.assertEqual(len(self.comfy.submitted), 1)
        self.assertEqual([r.model_id for r in self.mask_calls()], ['first-mask-model', journey.DEFAULT_MASK_MODEL_ID])

    def test_raw_render_is_not_published_before_protection_and_review(self):
        self.create_journey(count=1, auto_mask=True)
        result = self.until('protecting')
        self.assertIsNone(result['steps'][0]['output_asset_id'])
        self.assertTrue(result['steps'][0]['raw_output_asset_id'])
        self.assertEqual(journey.generated(result), 0)
        self.assertEqual(len(journey.sequence(result)['frames']), 1)
        self.journeys.pause(self.journey_id)
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.mask_calls(), [])
        self.resume_journey()
        self.until('completed')
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_failed_mask_retries_without_rendering_even_if_intention_changed(self):
        self.create_journey(count=1, auto_mask=True)
        pending = self.until('protecting')['steps'][0]
        self.gateway.bad_mask = True
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()['status'], 'paused')
        self.gateway.bad_mask = False
        self.resume_journey(intention='Conserver cet ajout puis finir le décor.', progression_model_id='replacement-vision')
        result = self.until('completed')
        self.assertEqual(result['steps'][0]['id'], pending['id'])
        self.assertEqual(result['steps'][0]['raw_output_asset_id'], pending['raw_output_asset_id'])
        self.assertEqual(len(self.comfy.submitted), 1)
        self.assertEqual(len(self.mask_calls()), 2)
        self.assertEqual(self.mask_calls()[-1].model_id, 'replacement-vision')

    def test_restart_after_localization_reuses_plan_and_raw_render(self):
        self.create_journey(count=1, auto_mask=True, mask_model_id='original-mask-model')
        self.until('protecting')
        with patch.object(self.journeys.protection.compositor, 'compose', side_effect=OSError('disk unavailable')):
            self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()['status'], 'paused')
        self.assertTrue(self.current_journey()['steps'][0]['protection']['plan'])
        self.journeys = self.new_service()
        self.journeys.recover()
        self.resume_journey(mask_model_id=journey.DEFAULT_MASK_MODEL_ID)
        result = self.until('completed')
        self.assertEqual(result['mask_model_id'], journey.DEFAULT_MASK_MODEL_ID)
        self.assertEqual(result['steps'][0]['protection']['model_id'], 'original-mask-model')
        self.assertEqual(len(self.mask_calls()), 1)
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_pause_during_mask_saves_composite_and_waits_before_review(self):
        self.create_journey(count=1, auto_mask=True)
        self.until('protecting')
        self.gateway.mask_hook = lambda: self.journeys.pause(self.journey_id)
        self.journeys.advance(self.journey_id)
        result = self.current_journey()
        self.assertEqual((result['status'], result['phase']), ('paused', 'reviewing'))
        self.assertTrue(result['steps'][0]['output_asset_id'])
        self.assertIsNone(result['steps'][0]['review'])
        self.gateway.mask_hook = None
        self.resume_journey()
        self.until('completed')
        self.assertEqual(len(self.mask_calls()), 1)

    def test_mask_can_be_disabled_and_old_journals_keep_their_behavior(self):
        self.create_journey(count=1, auto_mask=False)
        result = self.until('completed')
        self.assertNotIn('protection', result['steps'][0])
        self.assertEqual(self.mask_calls(), [])


class ManualProtectionTest(ImageJourneyFixture):
    start_operation = edits_fixture.ImageJourneyEditsTest.start_operation
    operation = edits_fixture.ImageJourneyEditsTest.operation
    render_operation = edits_fixture.ImageJourneyEditsTest.render_operation
    operation_until = edits_fixture.ImageJourneyEditsTest.operation_until

    def setUp(self):
        super().setUp()
        self.gateway = edits_fixture.EditGateway()
        self.minimax.gateway = self.gateway
        self.journeys.gateway = self.gateway

    def test_append_uses_protected_final_image_and_insert_preserves_existing_steps(self):
        self.create_journey(count=1, auto_mask=True)
        baseline = self.until('completed')
        first = deepcopy(baseline['steps'][0])
        op = self.start_operation()
        self.assertEqual(op['source_asset_id'], first['output_asset_id'])
        appended = deepcopy(self.operation_until('completed'))
        self.assertNotEqual(appended['output_asset_id'], appended['raw_output_asset_id'])
        inserted = self.start_operation(kind='insert', after_frame_id=first['id'], before_frame_id=appended['id'])
        self.assertEqual(inserted['source_asset_id'], appended['output_asset_id'])
        self.operation_until('completed')
        result = self.current_journey()
        self.assertEqual(result['steps'][0], first)
        self.assertEqual(result['manual_steps'][0]['output_asset_id'], appended['output_asset_id'])
        self.assertEqual([s['id'] for s in journey.ordered_steps(result)], [first['id'], inserted['id'], appended['id']])
        self.assertEqual(len(self.comfy.submitted), 3)

    def test_append_and_insert_use_the_independent_mask_model(self):
        self.create_journey(count=1, auto_mask=True, mask_model_id=journey.DEFAULT_MASK_MODEL_ID)
        first = self.until('completed')['steps'][0]
        self.start_operation()
        appended = deepcopy(self.operation_until('completed'))
        self.assertEqual(appended['mask_model_id'], journey.DEFAULT_MASK_MODEL_ID)
        self.assertEqual(appended['protection']['model_id'], journey.DEFAULT_MASK_MODEL_ID)
        self.assertEqual(appended['progression_model_id'], 'progression-vision')
        self.assertEqual(appended['prompt_model_id'], 'minimax-prompter')
        self.start_operation(kind='insert', after_frame_id=first['id'], before_frame_id=appended['id'])
        inserted = self.operation_until('completed')
        self.assertEqual(inserted['protection']['model_id'], journey.DEFAULT_MASK_MODEL_ID)
        self.assertEqual(self.current_journey()['steps'][0], first)
        self.assertEqual(len(self.comfy.submitted), 3)

    def test_manual_mask_failure_resumes_only_protection(self):
        self.create_journey(count=1, auto_mask=True)
        self.until('completed')
        op = self.start_operation()
        self.operation_until('protecting')
        self.gateway.bad_mask = True
        self.journeys.edits.advance(self.journey_id)
        self.assertEqual(self.operation()['status'], 'paused')
        self.gateway.bad_mask = False
        self.journeys.edits.control(self.journey_id, op['id'], action='resume')
        self.operation_until('completed')
        self.assertEqual(len(self.comfy.submitted), 2)
