"""User-run bounded retry regressions. All model and render gateways are local fakes."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from panelforge.application import image_journey_realistic_prompting as realistic
from panelforge.application import image_journey_policies as policies
from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.domain import image_journeys as journey
from panelforge.domain import image_journey_retries as retries
from panelforge.infrastructure.presets.minimax_edit import load_minimax_edit_workflow
from test_image_journeys import ImageJourneyFixture
import test_image_journey_realistic as realistic_tests
import test_image_journey_edits as manual_tests
from test_qwen_edit import png

GOOD = dict(people_present=False, requested_change_complete=True, scene_preserved=True)
PEOPLE = dict(GOOD, people_present=True)


class RetryGateway(realistic_tests.RealisticGateway):
    def __init__(self):
        super().__init__()
        self.verdicts = []
        self.default_quality = GOOD
        self.review_hook = None
        self.progress_verdicts = []
        self.comparisons = []
        self.decision_overrides = []

    def stream(self, request):
        for event in super().stream(request):
            review = (request.operation_id == realistic.REVIEW_OPERATION or
                request.operation_id == realistic.OPERATION and json.loads(request.user_prompt).get('reviewing_result'))
            if not review or event.kind is not StreamEventKind.COMPLETED:
                yield event
                continue
            value = json.loads(event.result.content)
            quality = self.verdicts.pop(0) if self.verdicts else self.default_quality
            if quality is None:
                value.pop('quality', None)
            else:
                value['quality'] = deepcopy(quality)
            value['observation'] = 'Diagnostic de la transformation et de la population.'
            if self.progress_verdicts:
                value['progress'] = self.progress_verdicts.pop(0)
            elif isinstance(quality, dict) and quality.get('requested_change_complete') is False:
                value['progress'].update(level='none', visible_changes='Aucune dépose visible.',
                    remaining_work='Réaliser la transformation.', destination_reached=False)
            if self.comparisons:
                value['comparison'] = self.comparisons.pop(0)
            elif 'comparison' in value:
                bad = not isinstance(quality, dict) or quality.get('people_present')
                bad = bad or value['progress']['level'] in {'none', 'regression'}
                bad = bad or set(value['progress']['blocking_defects']).intersection(retries.HARD_DEFECTS)
                value['comparison']['selected'] = 'none' if bad else 'correction'
            if self.decision_overrides:
                value.update(self.decision_overrides.pop(0))
            if self.review_hook:
                hook, self.review_hook = self.review_hook, None
                hook()
            yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED,
                result=CompletionResult(request.model_id, json.dumps(value), call_id='retry-review'))


class ImageJourneyRetriesTest(ImageJourneyFixture):
    real = realistic_tests.ImageJourneyRealisticTest.real
    start_operation = manual_tests.ImageJourneyEditsTest.start_operation
    operation = manual_tests.ImageJourneyEditsTest.operation
    operation_until = manual_tests.ImageJourneyEditsTest.operation_until

    def setUp(self):
        super().setUp()
        self.minimax.workflow = load_minimax_edit_workflow(
            Path(__file__).resolve().parents[1] / 'workflows/image.edit/minimax-h3-still/1.3.0')
        self.gateway = RetryGateway()
        self.journeys.gateway = self.minimax.gateway = self.gateway

    def render_frame(self, frame):
        child = self.minimax.ensure_journey_step(frame)
        stage = child['stages'][0]
        attempt = next(a for a in stage['attempts'] if a['request_id'] == frame['render_request_id'])
        self.comfy.output = png(('red', 'green', 'blue')[len(self.comfy.submitted) % 3],
                               size=tuple(frame['render_profile']['dimensions']))
        self.minimax.execute_attempt(child['id'], stage['id'], attempt['id'])

    def render_current(self):
        self.render_frame(self.current_journey()['steps'][-1])

    def render_operation(self):
        self.render_frame(self.operation())

    def start_rejection(self, quality=PEOPLE, **values):
        self.gateway.verdicts = [quality]
        initial = self.real(count=values.pop('count', 1), **values)
        rejected = deepcopy(self.until('reviewing')['steps'][-1])
        self.journeys.advance(self.journey_id)
        return initial, rejected, self.current_journey()

    def test_people_only_cleanup_keeps_one_frame_and_exports_only_correction(self):
        initial, rejected, pending = self.start_rejection(count=2)
        step = pending['steps'][-1]
        self.assertEqual(pending['phase'], 'prompting')
        self.assertEqual(step['id'], rejected['id'])
        self.assertEqual(step['retry_kind'], 'cleanup')
        self.assertEqual(step['source_asset_id'], rejected['output_asset_id'])
        self.assertEqual(step['retry_initial_source_asset_id'], initial['source_asset_id'])
        self.assertEqual(step['attempt_history'][0]['output_asset_id'], rejected['output_asset_id'])
        self.assertEqual(step['action'], rejected['action'])
        self.assertEqual(pending['completed_milestones'], rejected['progress_before']['completed_milestones'])
        self.assertEqual(journey.transferable_frame_ids(pending), ['source'])
        result = self.until('completed')
        corrected = result['steps'][0]
        child = self.minimax.ensure_journey_step(corrected)
        inputs = child['stages'][0]['attempts'][-1]['context']['render_inputs']
        self.assertEqual([i['asset_id'] for i in inputs], [rejected['output_asset_id']])
        self.assertNotEqual(corrected['minimax_project_id'], rejected['minimax_project_id'])
        self.assertTrue(corrected['prompt'].startswith(realistic.IMAGE_PREFIX))
        self.assertNotIn('<Picture 2>', corrected['prompt'])
        self.assertNotIn('Regenerate the SAME', policies.edit_request(corrected))
        self.assertEqual(result['steps'][1]['source_asset_id'], corrected['output_asset_id'])
        self.assertEqual((result['count'], len(result['steps']), len(self.comfy.submitted)), (2, 2, 3))
        analysis = next(a for a in result['analyses'] if a['id'] == corrected['review']['analysis_id'])
        self.assertEqual(analysis['input_assets'][0][0], initial['source_asset_id'])
        self.assertTrue(any(a == rejected['output_asset_id'] and 'CORRECTION_SOURCE' in label
                            for a, label in analysis['input_assets']))
        exported = self.journeys.prepare_transitions(self.journey_id)
        assets = [f['asset_id'] for f in self.transitions.get(exported['project_id'])['frames']]
        self.assertIn(corrected['output_asset_id'], assets)
        self.assertNotIn(rejected['output_asset_id'], assets)

    def test_wrong_state_or_damaged_scene_regenerates_from_validated_source(self):
        for field in ('requested_change_complete', 'scene_preserved'):
            with self.subTest(field=field):
                if field == 'scene_preserved':
                    self.gateway.progress_verdicts = [dict(level='partial', visible_changes='Le lieu est remplacé.',
                        remaining_work='Retrouver le lieu.', blocking_defects=['host'], destination_reached=False)]
                initial, rejected, pending = self.start_rejection(dict(PEOPLE, **{field: False}),
                                                                 command='wrong-' + field)
                step = pending['steps'][-1]
                self.assertEqual(step['retry_kind'], 'regenerate')
                self.assertEqual(step['source_asset_id'], initial['source_asset_id'])
                self.assertIn('Regenerate the SAME', policies.edit_request(step))
                final = self.until('completed')['steps'][0]
                child = self.minimax.ensure_journey_step(final)
                self.assertEqual(child['stages'][0]['attempts'][0]['context']['render_inputs'][0]['asset_id'],
                                 initial['source_asset_id'])
                self.assertNotEqual(final['render_request_id'], rejected['render_request_id'])

    def test_second_rejection_stops_and_resume_does_not_allow_a_third_render(self):
        self.gateway.default_quality = PEOPLE
        _, rejected, _ = self.start_rejection()
        self.until('reviewing')
        self.journeys.advance(self.journey_id)
        stopped = self.current_journey()
        step = stopped['steps'][0]
        self.assertEqual(stopped['status'], 'paused')
        self.assertEqual(step['automatic_retry_count'], 1)
        self.assertEqual(len(self.comfy.submitted), 2)
        self.assertEqual(journey.transferable_frame_ids(stopped), ['source'])
        self.assertEqual(self.journeys.public(stopped)['blocked_images'][0]['output_asset_id'], step['output_asset_id'])
        self.journeys = self.new_service()
        self.journeys.recover()
        self.resume_journey()
        for _ in range(3):
            self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()['status'], 'paused')
        self.assertEqual(len(self.comfy.submitted), 2)
        self.assertEqual(step['attempt_history'][0]['output_asset_id'], rejected['output_asset_id'])

    def test_explicit_regenerate_after_failed_cleanup_uses_original_and_keeps_history(self):
        self.gateway.default_quality = PEOPLE
        initial, _, _ = self.start_rejection()
        self.until('reviewing')
        self.journeys.advance(self.journey_id)
        current = self.current_journey()
        step = current['steps'][0]
        retried = self.journeys.resolutions.resolve(self.journey_id, version=current['version'],
            command='manual-retry', step_id=step['id'], output_asset_id=step['output_asset_id'], action='regenerate')
        replacement = retried['steps'][0]
        self.assertEqual(replacement['source_asset_id'], initial['source_asset_id'])
        self.assertEqual(replacement['automatic_retry_count'], 1)
        self.assertEqual(len(replacement['attempt_history']), 2)
        self.until('reviewing')
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()['status'], 'paused')
        self.assertEqual(len(self.comfy.submitted), 3)  # Third render was explicitly requested.
        current = self.current_journey()
        step = current['steps'][0]
        accepted = self.journeys.resolutions.resolve(self.journey_id, version=current['version'],
            command='accept-correction', step_id=step['id'], output_asset_id=step['output_asset_id'], action='accept')
        self.assertEqual(accepted['status'], 'completed')
        self.assertEqual(journey.transferable_frame_ids(accepted), ['source', step['id']])
        self.assertEqual(accepted['steps'][0]['review']['assessment'], 'unusable')

    def test_restart_during_queued_correction_reuses_the_same_request(self):
        _, rejected, _ = self.start_rejection()
        queued = self.until('rendering')['steps'][0]
        self.journeys = self.new_service()
        self.journeys.recover()
        recovered = self.current_journey()
        self.assertEqual(recovered['status'], 'paused')
        self.assertEqual(recovered['steps'][0]['render_request_id'], queued['render_request_id'])
        self.resume_journey()
        done = self.until('completed')['steps'][0]
        child = self.minimax.ensure_journey_step(done)
        self.assertEqual(len(child['stages'][0]['attempts']), 1)
        self.assertEqual(done['render_identity'], queued['render_identity'])
        self.assertEqual(done['attempt_history'][0]['output_asset_id'], rejected['output_asset_id'])
        self.assertEqual(len(self.comfy.submitted), 2)

    def test_pause_during_review_saves_rejection_without_starting_correction(self):
        self.gateway.verdicts = [PEOPLE, PEOPLE]
        self.real(count=1)
        self.until('reviewing')
        self.gateway.review_hook = lambda: self.journeys.pause(self.journey_id)
        self.journeys.advance(self.journey_id)
        paused = self.current_journey()
        self.assertEqual(paused['status'], 'paused')
        self.assertNotIn('attempt_history', paused['steps'][0])
        self.assertEqual(len(self.comfy.submitted), 1)
        self.resume_journey()
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()['steps'][0]['automatic_retry_count'], 1)
        self.until('completed')
        self.assertEqual(len(self.comfy.submitted), 2)

    def test_missing_or_malformed_quality_suspends_without_render_retry(self):
        for index, value in enumerate((None, dict(PEOPLE, people_present='yes'), {})):
            with self.subTest(value=value):
                before = len(self.comfy.submitted)
                _, _, result = self.start_rejection(value, command='invalid-quality-' + str(index))
                self.assertEqual(result['status'], 'paused')
                self.assertIsNone(result['steps'][0]['review'])
                self.assertNotIn('attempt_history', result['steps'][0])
                self.assertEqual(len(self.comfy.submitted), before + 1)

    def test_existing_step_does_not_silently_gain_automatic_retry(self):
        self.real(count=1)
        old = self.until('reviewing')
        old['steps'][0].pop('automatic_retry_enabled')
        self.journey_store.save(old)
        self.gateway.verdicts = [PEOPLE]
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()['status'], 'paused')
        self.assertNotIn('attempt_history', self.current_journey()['steps'][0])
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_manual_gaps_keep_neighbors_and_commit_correction_once(self):
        for kind in ('insert', 'append', 'prepend'):
            with self.subTest(kind=kind):
                self.real(count=1, command='manual-' + kind)
                before = deepcopy(self.until('completed')['steps'])
                anchors = (dict(after_frame_id='source', before_frame_id=before[0]['id']) if kind == 'insert'
                    else dict(after_frame_id=None, before_frame_id='source') if kind == 'prepend' else {})
                op = self.start_operation(kind, **anchors)
                self.gateway.verdicts = [PEOPLE]
                initial = deepcopy(self.operation_until('reviewing'))
                self.journeys.edits.advance(self.journey_id)
                pending = self.operation()
                self.assertEqual(pending['id'], op['id'])
                self.assertEqual(pending['retry_kind'], 'cleanup')
                self.assertEqual(self.current_journey().get('manual_steps', []), [])
                completed = self.operation_until('completed')
                self.journeys.edits.advance(self.journey_id)
                result = self.current_journey()
                self.assertEqual(result['steps'], before)
                self.assertEqual(len(result['manual_steps']), 1)
                self.assertEqual(journey.ordered_frame_ids(result).count(op['id']), 1)
                self.assertEqual(completed['attempt_history'][0]['output_asset_id'], initial['output_asset_id'])
                child = self.minimax.ensure_journey_step(completed)
                self.assertEqual([i['asset_id'] for i in child['stages'][0]['attempts'][0]['context']['render_inputs']],
                                 [initial['output_asset_id']])

    def test_manual_second_rejection_suspends_without_committing_or_looping(self):
        self.real(count=1)
        before = deepcopy(self.until('completed')['steps'])
        self.gateway.default_quality = PEOPLE
        self.start_operation('insert', after_frame_id='source', before_frame_id=before[0]['id'])
        self.operation_until('reviewing')
        self.journeys.edits.advance(self.journey_id)
        self.operation_until('reviewing')
        self.journeys.edits.advance(self.journey_id)
        op = self.operation()
        self.assertEqual(op['status'], 'paused')
        self.assertEqual(len(op['attempt_history']), 1)
        self.assertEqual(self.current_journey().get('manual_steps', []), [])
        self.assertEqual(self.current_journey()['steps'], before)
        self.journeys.edits.control(self.journey_id, op['id'], action='resume')
        self.journeys.edits.advance(self.journey_id)
        self.assertEqual(self.operation()['status'], 'paused')
        self.assertEqual(len(self.comfy.submitted), 3)  # One base step plus the two manual attempts.

    def test_public_history_strips_private_mask_reply_without_mutating_journal(self):
        _, _, pending = self.start_rejection()
        pending['steps'][0]['attempt_history'][0]['protection'] = dict(raw='private', coverage=0.2)
        public = self.journeys.public(pending)
        for key in ('steps', 'ordered_steps'):
            self.assertNotIn('raw', public[key][0]['attempt_history'][0]['protection'])
        self.assertEqual(pending['steps'][0]['attempt_history'][0]['protection']['raw'], 'private')

    def test_later_manual_frame_prevents_replacing_its_automatic_source(self):
        self.real(count=2)
        self.until('reviewing')
        self.journeys.pause(self.journey_id)
        self.start_operation('append')
        tail = self.operation_until('completed')
        self.gateway.verdicts = [PEOPLE]
        self.resume_journey()
        self.journeys.advance(self.journey_id)
        result = self.current_journey()
        self.assertEqual(result['status'], 'paused')
        self.assertNotIn('attempt_history', result['steps'][0])
        self.assertEqual(result['manual_steps'][0]['output_asset_id'], tail['output_asset_id'])
        self.assertEqual(len(self.comfy.submitted), 2)


class RetryContractTest(unittest.TestCase):
    def test_cleanup_disables_only_its_own_mask_and_preserves_diagnostic(self):
        step = dict(id='frame', journey_preset='realistic', automatic_retry_enabled=True,
            source_asset_id='source', output_asset_id='bad', auto_mask=True,
            review=dict(assessment='unusable', observation='People.', quality=PEOPLE),
            action=dict(title='Bare cave', change='Bare rock', preserve='Host'),
            protection=dict(raw='internal', result='protected'), prompt='Original')
        retries.begin(step, 'cleanup')
        self.assertFalse(step['auto_mask'])
        self.assertTrue(step['retry_initial_auto_mask'])
        self.assertNotIn('protection', step)
        self.assertEqual(step['attempt_history'][0]['protection']['raw'], 'internal')
        self.assertIsNone(retries.mode(step))
        step.update(output_asset_id='still-bad', review=dict(assessment='unusable', observation='People.', quality=PEOPLE))
        self.assertIsNone(retries.mode(step))
        with self.assertRaises(ValueError):
            retries.begin(step, 'cleanup')
        replacement = {}
        retries.inherit_manual_retry(step, replacement)
        self.assertEqual(replacement['source_asset_id'], 'source')
        self.assertTrue(replacement['auto_mask'])

    def test_miniature_has_no_retry_and_old_prompt_decoding_stays_compatible(self):
        step = dict(journey_preset='miniature', automatic_retry_enabled=True,
            output_asset_id='bad', review=dict(assessment='unusable', observation='People.', quality=PEOPLE))
        self.assertIsNone(retries.mode(step))
        context = dict(mode='edit', guide=None, source_asset_id='source',
            render_inputs=[dict(id='source', tag='<Picture 1>', asset_id='source')])
        raw = json.dumps(dict(message='Edit', prompt='Edit <Picture 1> to expose the rock.'))
        legacy = realistic.decode_prompt(raw, context, legacy=True)[1]
        current = realistic.decode_prompt(raw, context)[1]
        self.assertIn(realistic.LEGACY_IMAGE_RULES, legacy)
        self.assertNotIn(realistic.IMAGE_PREFIX, legacy)
        self.assertTrue(current.startswith(realistic.IMAGE_PREFIX))
