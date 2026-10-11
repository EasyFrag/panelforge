"""User-run progress/comparison regressions; model and image gateways are local fakes."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from panelforge.application import image_journey_realistic_prompting as prompting
from panelforge.application import image_journey_retries as application_retries
from panelforge.domain import image_journey_retries as retry
from panelforge.domain import image_journeys as journey
from panelforge.infrastructure.presets.minimax_edit import load_minimax_edit_workflow
from test_image_journeys import ImageJourneyFixture
import test_image_journey_retries as fixtures

GOOD = fixtures.GOOD
PARTIAL_QUALITY = dict(GOOD, requested_change_complete=False)


def progress(level='partial', *, defects=(), reached=False):
    return dict(level=level, visible_changes='Textile retiré au fond et à gauche.' if level != 'none' else 'Textile inchangé.',
                remaining_work='Retirer le textile restant au premier plan.' if not reached else '',
                blocking_defects=list(defects), destination_reached=reached)


def comparison(selected='initial', *, initial_quality=PARTIAL_QUALITY, initial_progress=None):
    return dict(selected=selected, reason='Le premier essai conserve davantage de dépose utile.',
                initial_review=dict(observation='Dépose partielle visible au fond.',
                    quality=deepcopy(initial_quality), progress=initial_progress or progress()))


class ProgressReviewContractTest(unittest.TestCase):
    def test_partial_is_usable_but_no_progress_or_hard_defect_is_not(self):
        for level, quality, defects, expected in (
                ('partial', PARTIAL_QUALITY, (), 'usable'),
                ('complete', GOOD, (), 'usable'),
                ('none', GOOD, (), 'unusable'),
                ('regression', GOOD, (), 'unusable'),
                ('partial', dict(GOOD, people_present=True), (), 'unusable'),
                ('partial', dict(GOOD, scene_preserved=False), (), 'usable'),
                ('partial', GOOD, ('contradiction',), 'unusable')):
            with self.subTest(level=level, quality=quality, defects=defects):
                result = retry.visual_review(dict(observation='Observation visible.', quality=quality,
                                                   progress=progress(level, defects=defects)))
                self.assertEqual(result['assessment'], expected)

    def test_partial_with_people_uses_cleanup_and_other_defects_regenerate(self):
        step = dict(id='step', journey_preset='realistic', automatic_retry_enabled=True,
                    output_asset_id='result', source_asset_id='before')
        for defects, expected in ((('people',), 'cleanup'), (('host',), 'regenerate')):
            step['review'] = retry.visual_review(dict(observation='Avancée avec défaut.',
                quality=dict(PARTIAL_QUALITY, people_present=True), progress=progress(defects=defects)))
            self.assertEqual(retry.mode(step), expected)
        step['automatic_retry_count'] = 1
        self.assertIsNone(retry.mode(step))

    def test_missing_comparison_and_unsafe_choice_are_rejected(self):
        step = dict(journey_preset='realistic', retry_kind='regenerate', automatic_retry_count=1,
                    output_asset_id='correction', attempt_history=[dict(output_asset_id='initial')])
        base = dict(assessment='usable', observation='Correction nette.', quality=GOOD, progress=progress())
        for choice in (None, comparison(initial_quality=dict(GOOD, people_present=True)),
                       comparison('none')):
            with self.subTest(choice=choice), self.assertRaises(ValueError):
                value = deepcopy(base)
                if choice is not None:
                    value['comparison'] = choice
                retry.select_review(value, step)

    def test_cleanup_reference_is_deduplicated_and_keeps_both_roles(self):
        step = dict(journey_preset='realistic', retry_kind='cleanup', automatic_retry_count=1,
                    attempt_history=[dict(output_asset_id='initial')])
        items = [('before', 'BEFORE'), ('correction', 'RESULT'), ('initial', 'CORRECTION_SOURCE')]
        result = application_retries.comparison_inputs(items, step)
        self.assertEqual(len(result), 3)
        self.assertIn('CORRECTION_SOURCE', result[-1][1])
        self.assertIn('INITIAL_ATTEMPT', result[-1][1])
        self.assertEqual(items[-1][1], 'CORRECTION_SOURCE')

    def test_later_manual_dependency_prevents_automatic_pixel_replacement(self):
        step = dict(id='step', journey_preset='realistic', retry_kind='regenerate',
                    automatic_retry_count=1, output_asset_id='correction',
                    attempt_history=[dict(id='step', output_asset_id='initial')])
        project = dict(steps=[step], manual_steps=[dict(id='later', manual=True, output_asset_id='later-image')])
        decision = dict(assessment='usable', observation='Progrès.', quality=PARTIAL_QUALITY, progress=progress(),
            attempt_comparison=dict(selected='initial', initial_asset_id='initial', correction_asset_id='correction'))
        before = deepcopy(project)
        with self.assertRaisesRegex(ValueError, 'dépend'):
            application_retries.apply_review(project, step, decision, {})
        self.assertEqual(project, before)

    def test_missing_or_malformed_progress_is_not_an_image_retry(self):
        for invalid in (None, {}, dict(progress(), destination_reached='yes'),
                        dict(progress(), blocking_defects=['slightly_incomplete']),
                        dict(progress(), remaining_work='')):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                retry.visual_review(dict(observation='Image.', quality=GOOD, progress=invalid))


class ImageJourneyProgressReviewTest(ImageJourneyFixture):
    real = fixtures.ImageJourneyRetriesTest.real
    render_frame = fixtures.ImageJourneyRetriesTest.render_frame
    render_current = fixtures.ImageJourneyRetriesTest.render_current
    render_operation = fixtures.ImageJourneyRetriesTest.render_operation
    start_rejection = fixtures.ImageJourneyRetriesTest.start_rejection
    start_operation = fixtures.ImageJourneyRetriesTest.start_operation
    operation = fixtures.ImageJourneyRetriesTest.operation
    operation_until = fixtures.ImageJourneyRetriesTest.operation_until

    def setUp(self):
        super().setUp()
        self.minimax.workflow = load_minimax_edit_workflow(
            Path(__file__).resolve().parents[1] / 'workflows/image.edit/minimax-h3-still/1.3.0')
        self.gateway = fixtures.RetryGateway()
        self.journeys.gateway = self.minimax.gateway = self.gateway

    def test_saved_realistic_prompt_versions_still_decode(self):
        context = dict(mode='edit', guide=None, source_asset_id='source',
                       render_inputs=[dict(id='source', tag='<Picture 1>', asset_id='source')])
        raw = json.dumps(dict(message='Dépose.', prompt='Edit <Picture 1> to expose bare rock.'))
        for version in ('1.0.0', '1.1.0', '1.2.0', prompting.VERSION):
            reply, rendered, _ = self.minimax._decode_message(
                dict(journey_realistic_policy=version, context=context), raw)
            self.assertTrue(reply)
            self.assertIn(prompting.LEGACY_IMAGE_RULES if version == '1.0.0' else prompting.IMAGE_RULES, rendered)
        self.assertEqual(self.gateway.requests, [])

    def test_useful_partial_continues_without_retry_and_becomes_next_source(self):
        self.real(count=3)
        self.until('reviewing')
        self.gateway.verdicts = [PARTIAL_QUALITY]
        self.gateway.progress_verdicts = [progress()]
        self.journeys.advance(self.journey_id)
        current = self.current_journey()
        first = current['steps'][0]
        self.assertEqual(first['review']['assessment'], 'usable')
        self.assertFalse(first['review']['quality']['requested_change_complete'])
        self.assertNotIn('attempt_history', first)
        self.assertEqual(current['phase'], 'ready')
        self.until('rendering')
        self.assertEqual(self.current_journey()['steps'][1]['source_asset_id'], first['output_asset_id'])
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_final_partial_does_not_falsely_claim_destination_reached(self):
        self.real(count=1)
        self.until('reviewing')
        self.gateway.verdicts = [PARTIAL_QUALITY]
        self.gateway.progress_verdicts = [progress()]
        self.journeys.advance(self.journey_id)
        final = self.current_journey()
        self.assertEqual(final['status'], 'completed')
        self.assertNotIn('completion_reason', final)
        self.assertLess(final['completed_milestones'], len(final['milestones']))
        self.assertIn('inachevés', final['warning'])
        self.assertEqual(len(self.comfy.submitted), 1)
        self.assertEqual(len(journey.transferable_frame_ids(final)), 2)

    def test_choose_initial_preserves_pixels_history_next_source_and_export(self):
        for corrected_level in ('none', 'partial'):
            with self.subTest(corrected_level=corrected_level):
                _, initial, _ = self.start_rejection(PARTIAL_QUALITY, count=2, command='choose-' + corrected_level)
                correction = deepcopy(self.until('reviewing')['steps'][0])
                rendered = self.minimax.get(correction['minimax_project_id'])['stages'][0]['attempts'][-1]
                self.assertNotIn(initial['output_asset_id'], [i['asset_id'] for i in rendered['context']['render_inputs']])
                self.gateway.verdicts = [PARTIAL_QUALITY]
                self.gateway.progress_verdicts = [progress(corrected_level)]
                self.gateway.comparisons = [comparison()]
                self.gateway.decision_overrides = [dict(summary='Le textile a disparu au fond et à gauche.',
                    completed_milestones=0)]
                self.journeys.advance(self.journey_id)
                chosen = self.current_journey()['steps'][0]
                self.assertEqual(chosen['id'], initial['id'])
                self.assertEqual(chosen['output_asset_id'], initial['output_asset_id'])
                self.assertEqual(chosen['retained_attempt_index'], 0)
                self.assertEqual([a['output_asset_id'] for a in chosen['attempt_history']],
                                 [initial['output_asset_id'], correction['output_asset_id']])
                self.assertEqual(chosen['attempt_history'][0]['review']['assessment'], 'unusable')
                self.assertEqual(chosen['review']['assessment'], 'usable')
                self.assertNotIn('user_acceptance', chosen)
                self.assertEqual(self.current_journey()['completed_milestones'], 0)
                call = next(c for c in self.current_journey()['analyses'] if c['id'] == chosen['review']['analysis_id'])
                self.assertTrue(any(asset == initial['output_asset_id'] and 'INITIAL_ATTEMPT' in label
                                    for asset, label in call['input_assets']))
                # Reopening must preserve the automatic choice and its rendering provenance.
                self.journeys = self.new_service()
                self.assertEqual(self.current_journey()['steps'][0]['output_asset_id'], initial['output_asset_id'])
                final = self.until('completed')
                self.assertEqual(final['steps'][1]['source_asset_id'], initial['output_asset_id'])
                self.assertEqual(len(final['steps']), 2)
                export = self.journeys.prepare_transitions(self.journey_id)
                assets = [f['asset_id'] for f in self.transitions.get(export['project_id'])['frames']]
                self.assertIn(initial['output_asset_id'], assets)
                self.assertNotIn(correction['output_asset_id'], assets)
                reviews = [c for c in final['analyses'] if c['phase'] == 'reviewing']
                self.assertEqual(len(reviews), 3)  # Initial, correction comparison, next step; no extra critic.
                child = self.minimax.ensure_journey_step(final['steps'][0])
                self.assertEqual(child['id'], initial['minimax_project_id'])

    def test_useful_correction_is_retained_even_when_its_exact_edit_is_partial(self):
        _, initial, _ = self.start_rejection(PARTIAL_QUALITY)
        correction = deepcopy(self.until('reviewing')['steps'][0])
        self.gateway.verdicts = [PARTIAL_QUALITY]
        self.gateway.progress_verdicts = [progress()]
        self.gateway.comparisons = [comparison('correction', initial_progress=progress('none'))]
        self.journeys.advance(self.journey_id)
        chosen = self.current_journey()['steps'][0]
        self.assertEqual(chosen['output_asset_id'], correction['output_asset_id'])
        self.assertEqual(chosen['attempt_history'][0]['output_asset_id'], initial['output_asset_id'])
        self.assertEqual(chosen['review']['assessment'], 'usable')
        self.assertEqual(chosen['attempt_comparison']['selected'], 'correction')

    def test_two_useless_attempts_pause_and_resume_cannot_generate_a_third(self):
        self.start_rejection(PARTIAL_QUALITY)
        self.until('reviewing')
        self.gateway.default_quality = PARTIAL_QUALITY
        self.gateway.comparisons = [comparison('none', initial_progress=progress('none'))]
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()['status'], 'paused')
        self.resume_journey()
        self.gateway.comparisons = [comparison('none', initial_progress=progress('none'))]
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()['status'], 'paused')
        self.assertEqual(len(self.comfy.submitted), 2)

    def test_manual_insert_append_prepend_can_keep_initial_without_changing_neighbors(self):
        for kind in ('insert', 'append', 'prepend'):
            with self.subTest(kind=kind):
                self.real(count=1, command='manual-progress-' + kind)
                before = deepcopy(self.until('completed')['steps'])
                anchors = (dict(after_frame_id='source', before_frame_id=before[0]['id']) if kind == 'insert'
                           else dict(after_frame_id=None, before_frame_id='source') if kind == 'prepend' else {})
                op = self.start_operation(kind, **anchors)
                initial = deepcopy(self.operation_until('reviewing'))
                self.gateway.verdicts = [PARTIAL_QUALITY]
                self.journeys.edits.advance(self.journey_id)
                corrected = deepcopy(self.operation_until('reviewing'))
                self.gateway.verdicts = [PARTIAL_QUALITY]
                self.gateway.progress_verdicts = [progress('none')]
                self.gateway.comparisons = [comparison()]
                self.journeys.edits.advance(self.journey_id)
                final = self.current_journey()
                self.assertEqual(final['steps'], before)
                self.assertEqual(self.operation()['status'], 'completed')
                selected = final['manual_steps'][0]
                self.assertEqual(selected['output_asset_id'], initial['output_asset_id'])
                self.assertEqual(selected['attempt_history'][1]['output_asset_id'], corrected['output_asset_id'])
                self.assertEqual(journey.ordered_frame_ids(final).count(op['id']), 1)
                self.assertEqual(final['count'], 1)
