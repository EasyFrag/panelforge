"""Controlled reference comparisons. User-run only, with fake LLM/Comfy gateways."""
from copy import deepcopy
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.image_journeys import JourneyConflict
from panelforge.domain.minimax_edit import MinimaxEditSettings, journey_child_id
from panelforge.features.lab.image_journeys_web import image_journeys_router
from panelforge.infrastructure.presets.minimax_edit import load_minimax_edit_workflow
from test_image_journeys import ImageJourneyFixture

ROOT = Path(__file__).resolve().parents[1]


class ImageJourneyComparisonTest(ImageJourneyFixture):
    def setUp(self):
        super().setUp()
        self.baseline_workflow = load_minimax_edit_workflow(ROOT / 'workflows/image.edit/minimax-h3-still/1.0.0')
        self.comparison_workflow = load_minimax_edit_workflow(ROOT / 'workflows/image.edit/minimax-h3-still/1.1.0')

    def completed(self):
        # Exercise the actual old journal format against the new renderer.
        self.create_journey(count=1, legacy=True)
        self.minimax.workflow = self.baseline_workflow
        result = self.until('completed')
        step = result['steps'][0]
        legacy = self.minimax.get(step['minimax_project_id'])
        legacy['stages'][0]['settings'].pop('reference_megapixels', None)
        legacy['stages'][0]['attempts'][0]['settings'].pop('reference_megapixels', None)
        self.store.save(legacy)
        self.minimax.workflow = self.comparison_workflow
        return result

    def compare(self, command='compare', **changes):
        project = self.current_journey()
        values = dict(version=project['version'], command=command, step_id=project['steps'][0]['id'],
                      reference_megapixels=2)
        return self.journeys.compare(self.journey_id, **{**values, **changes})

    def test_new_graph_changes_only_reference_resolution_and_keeps_old_default(self):
        values = dict(images=['source.png'], prompt='Edit <Picture 1>.', dimensions=(2016, 3584),
                      composition=False, output_prefix='comparison')
        one = self.comparison_workflow.build(**values, settings=MinimaxEditSettings(reference_megapixels=1))
        two = self.comparison_workflow.build(**values, settings=MinimaxEditSettings(reference_megapixels=2))
        old = self.baseline_workflow.build(**values, settings=MinimaxEditSettings())
        self.assertEqual(one, old)
        scale = self.comparison_workflow.manifest['image_slots'][0]['scale_node']
        self.assertEqual(two[scale]['inputs']['megapixels'], 2)
        two[scale]['inputs']['megapixels'] = 1
        self.assertEqual(one, two)
        self.assertEqual(self.comparison_workflow.template, self.baseline_workflow.template)
        with self.assertRaisesRegex(ValueError, 'workflow'):
            self.baseline_workflow.build(**values, settings=MinimaxEditSettings(reference_megapixels=2))
        for invalid in (True, 0, 1.5, 3, '2'):
            with self.assertRaises(ValueError):
                MinimaxEditSettings(reference_megapixels=invalid)

    def test_old_completed_step_replays_its_frozen_source_prompt_seed_and_dimensions(self):
        original = self.completed()
        step = original['steps'][0]
        base_project = self.minimax.get(step['minimax_project_id'])
        base_attempt = base_project['stages'][0]['attempts'][0]
        # A later manual edit must not affect the replay snapshot.
        self.minimax.update(base_project['id'], base_project['stages'][0]['id'],
            revision=base_project['stages'][0]['revision'], changes={'prompt': 'Different edit of <Picture 1>.'})
        original_child = deepcopy(self.minimax.get(base_project['id']))
        calls = len(self.gateway.requests)
        sequence = self.journeys.sequence(self.journey_id)
        result = self.compare()
        comparison = result['comparisons'][0]
        child = self.minimax.get(journey_child_id(comparison['id']))
        stage = child['stages'][0]
        attempt = stage['attempts'][0]
        self.assertEqual(attempt['prompt'], base_attempt['prompt'])
        self.assertEqual(attempt['dimensions'], base_attempt['dimensions'])
        self.assertEqual(attempt['context']['render_inputs'], base_attempt['context']['render_inputs'])
        expected = {**MinimaxEditSettings(**base_attempt['settings']).record(), 'reference_megapixels': 2, 'reuse_seed': True}
        self.assertEqual(attempt['settings'], expected)
        self.assertEqual(stage['messages'], [])
        self.assertEqual(len(self.gateway.requests), calls)
        self.assertEqual(self.minimax.get(base_project['id']), original_child)
        self.minimax.execute_attempt(child['id'], stage['id'], attempt['id'])
        result = self.current_journey()
        self.assertEqual(result['comparisons'][0]['status'], 'succeeded')
        self.assertTrue(result['comparisons'][0]['output_asset_id'])
        self.assertEqual(result['steps'], original['steps'])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(self.journeys.sequence(self.journey_id), sequence)
        self.assertFalse(any(p['id'] == child['id'] for p in self.minimax.list()))

    def test_retry_of_same_command_is_idempotent_even_with_stale_version(self):
        original = self.completed()
        first = self.compare(version=original['version'])
        queued = len(self.minimax._render_queue)
        second = self.compare(version=original['version'])
        self.assertEqual(second['comparisons'][0]['attempt_id'], first['comparisons'][0]['attempt_id'])
        self.assertEqual(len(second['comparisons']), 1)
        self.assertEqual(len(self.minimax._render_queue), queued)
        with self.assertRaises(JourneyConflict):
            self.compare(reference_megapixels=1)
        with self.assertRaises(JourneyConflict):
            self.compare(command='another-comparison')

    def test_failed_queue_is_recorded_and_get_never_queues_or_calls_models(self):
        self.completed()
        queue = self.journeys.renderer.queue_comparison
        self.journeys.renderer.queue_comparison = lambda comparison: (_ for _ in ()).throw(RuntimeError('queue unavailable'))
        calls, renders = len(self.gateway.requests), len(self.minimax._render_queue)
        result = self.compare()
        self.assertEqual(result['comparisons'][0]['status'], 'failed')
        self.assertIn('queue unavailable', result['comparisons'][0]['error'])
        recovered = self.new_service()
        recovered.recover()
        recovered.get(self.journey_id)
        self.assertEqual(len(self.gateway.requests), calls)
        self.assertEqual(len(self.minimax._render_queue), renders)
        self.journeys.renderer.queue_comparison = queue
        self.compare(command='explicit-new-attempt')
        self.assertEqual(len(self.current_journey()['comparisons']), 2)

    def test_lost_queue_acknowledgement_reuses_the_durable_attempt(self):
        self.completed()
        queue = self.journeys.renderer.queue_comparison
        def lose_ack(comparison):
            queue(comparison)
            raise RuntimeError('ack lost')
        self.journeys.renderer.queue_comparison = lose_ack
        result = self.compare()
        self.assertEqual(result['comparisons'][0]['status'], 'queued')
        queued = len(self.minimax._render_queue)
        self.compare()
        self.assertEqual(len(self.minimax._render_queue), queued)
        recovered = self.new_service()
        recovered.recover()
        self.assertEqual(recovered.get(self.journey_id)['comparisons'][0]['status'], 'queued')
        self.assertEqual(len(self.minimax._render_queue), queued)

    def test_completed_image_can_be_compared_without_pausing_and_stale_versions_do_not_queue(self):
        self.create_journey(count=2, legacy=True)
        original = self.until('reviewing')
        self.minimax.workflow = self.comparison_workflow
        with self.assertRaises(JourneyConflict):
            self.compare(version=0)
        self.assertNotIn('comparisons', self.journey_store.get(self.journey_id))
        result = self.compare()
        self.assertEqual(result['status'], 'running')
        self.assertEqual(result['phase'], 'reviewing')
        self.assertEqual(result['steps'], original['steps'])
        self.assertFalse(result['pause_requested'])

    def test_http_comparison_rejects_hidden_parameter_changes_and_boolean_resolution(self):
        original = self.completed()
        app = FastAPI()
        app.include_router(image_journeys_router(self.journeys))
        url = f'/api/image-lab/journeys/projects/{self.journey_id}/comparisons'
        body = dict(version=original['version'], command='http-compare',
                    step_id=original['steps'][0]['id'], reference_megapixels=2)
        with TestClient(app) as client:
            for invalid in ({'reference_megapixels': True}, {'reference_megapixels': 3}, {'seed': '42'}, {'prompt': 'change'}):
                self.assertEqual(client.post(url, json={**body, **invalid}).status_code, 422)
            response = client.post(url, json=body)
            self.assertEqual(response.status_code, 202, response.text)
            self.assertEqual(response.json()['project']['comparisons'][0]['settings']['reference_megapixels'], 2)
            repeat = client.post(url, json=body)
            self.assertEqual(repeat.json()['project']['comparisons'][0]['attempt_id'], response.json()['project']['comparisons'][0]['attempt_id'])

    def test_analysis_failure_preserves_the_real_error_and_completed_call_id(self):
        self.gateway.bad_progression = True
        self.create_journey(count=1)
        self.journeys.advance(self.journey_id)
        result = self.current_journey()
        self.assertEqual(result['status'], 'paused')
        call = result['analyses'][-1]
        self.assertEqual(call['status'], 'failed')
        self.assertEqual(call['call_id'], 'journey-call')
        self.assertEqual(call['raw'], 'invalid {')
        self.assertNotIn('multiple values', result['error'])
