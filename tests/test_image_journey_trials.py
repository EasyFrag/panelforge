"""Fixed-size journey regressions, for user execution with fake gateways only."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.image_journeys import JourneyConflict
from panelforge.domain.minimax_edit import MinimaxEditSettings, journey_child_id
from panelforge.features.lab.image_journeys_web import image_journeys_router
from panelforge.infrastructure.presets.minimax_edit import load_minimax_edit_workflow
from test_image_journeys import ImageJourneyFixture
from test_qwen_edit import png

ROOT = Path(__file__).resolve().parents[1]


class ImageJourneyTrialTest(ImageJourneyFixture):
    def baseline(self, count=2):
        self.create_journey(count=count, legacy=True)
        original = self.until('completed')
        self.minimax.workflow = load_minimax_edit_workflow(ROOT / 'workflows/image.edit/minimax-h3-still/1.2.0')
        return original

    def start_trial(self, **changes):
        values = dict(version=self.current_journey()['version'], command='fixed-one', count=2)
        return self.journeys.trials.start(self.journey_id, **{**values, **changes})

    def trial(self):
        return self.current_journey()['fixed_trials'][-1]

    def render_trial(self, *, wrong_size=False):
        trial = self.trial()
        step = next(s for s in trial['steps'] if s['status'] != 'succeeded')
        child = self.minimax.get(journey_child_id(step['id']))
        stage = child['stages'][0]
        attempt = next(a for a in stage['attempts'] if a['request_id'] == step['render_request_id'])
        self.comfy.output = png('orange', size=(160, 96) if wrong_size else tuple(trial['dimensions']))
        self.minimax.execute_attempt(child['id'], stage['id'], attempt['id'])
        self.journeys.trials.advance(self.journey_id)
        return attempt

    def test_native_graph_bypasses_resize_and_preserves_the_default_graph(self):
        self.baseline()
        workflow = self.minimax.workflow
        old = load_minimax_edit_workflow(ROOT / 'workflows/image.edit/minimax-h3-still/1.1.0')
        values = dict(images=['source.png'], prompt='Edit <Picture 1>.', dimensions=(768, 1376),
                      composition=False, output_prefix='trial')
        default = workflow.build(**values, settings=MinimaxEditSettings())
        self.assertEqual(default, old.build(**values, settings=MinimaxEditSettings()))
        native = workflow.build(**values, settings=MinimaxEditSettings(resolution='source', reference_mode='native'))
        slot = workflow.manifest['image_slots'][0]
        self.assertNotIn(slot['scale_node'], native)
        self.assertEqual(native[workflow.manifest['conditioning_node']]['inputs'][slot['input']], [slot['load_node'], 0])
        for binding in workflow.manifest['components'].values():
            self.assertEqual(native[binding['node_id']], default[binding['node_id']])
        with self.assertRaises(ValueError):
            old.build(**values, settings=MinimaxEditSettings(resolution='source', reference_mode='native'))
        with self.assertRaises(ValueError):
            MinimaxEditSettings(reference_mode='native')

    def test_chain_uses_new_outputs_fixed_dimensions_frozen_prompts_and_no_llm(self):
        original = self.baseline()
        calls = len(self.gateway.requests)
        sequence = self.journeys.sequence(self.journey_id)
        with patch.object(self.minimax.images, 'prepare_fixed_source', wraps=self.minimax.images.prepare_fixed_source) as resize:
            self.start_trial()
            source = self.trial()['source_asset_id']
            for index in range(2):
                self.journeys.trials.advance(self.journey_id)
                attempt = self.render_trial()
                trial = self.trial()
                step = trial['steps'][index]
                self.assertEqual(attempt['context']['render_inputs'][0]['asset_id'], source)
                self.assertEqual(attempt['dimensions'], trial['dimensions'])
                self.assertEqual(attempt['prompt'], original['steps'][index]['prompt'])
                self.assertEqual(attempt['settings']['seed'], step['settings']['seed'])
                self.assertEqual(self.minimax.images.dimensions(self.comfy.uploads[-1][0]), tuple(trial['dimensions']))
                self.assertEqual(self.minimax.images.dimensions(self.assets.read_bytes(step['output_asset_id'])), tuple(trial['dimensions']))
                source = step['output_asset_id']
            self.assertEqual(resize.call_count, 1)
        self.assertEqual(self.trial()['status'], 'completed')
        self.assertEqual(len(self.gateway.requests), calls)
        self.assertEqual(self.current_journey()['steps'], original['steps'])
        self.assertEqual(self.journeys.sequence(self.journey_id), sequence)

    def test_start_is_idempotent_and_get_does_not_queue(self):
        original = self.baseline()
        first = self.start_trial(version=original['version'])
        count = len(self.minimax._render_queue)
        duplicate = self.start_trial(version=original['version'])
        self.assertEqual(first['fixed_trials'], duplicate['fixed_trials'])
        self.current_journey()
        self.assertEqual(len(self.minimax._render_queue), count)
        with self.assertRaises(JourneyConflict):
            self.start_trial(command='second')
        with self.assertRaises(JourneyConflict):
            self.start_trial(count=1)

    def test_pause_finishes_submitted_image_then_resume_chains_its_result(self):
        self.baseline()
        self.start_trial()
        self.journeys.trials.advance(self.journey_id)
        trial_id = self.trial()['id']
        self.journeys.trials.control(self.journey_id, trial_id, action='pause')
        self.render_trial()
        self.assertEqual(self.trial()['status'], 'paused')
        self.assertEqual(self.trial()['steps'][1]['status'], 'pending')
        queued = len(self.minimax._render_queue)
        self.journeys.trials.advance(self.journey_id)
        self.assertEqual(len(self.minimax._render_queue), queued)
        self.journeys.trials.control(self.journey_id, trial_id, action='resume')
        self.journeys.trials.advance(self.journey_id)
        self.render_trial()
        self.assertEqual(self.trial()['status'], 'completed')

    def test_restart_collects_inflight_image_but_requires_resume_for_next(self):
        self.baseline()
        self.start_trial()
        self.journeys.trials.advance(self.journey_id)
        self.journeys = self.new_service()
        self.journeys.recover()
        self.assertEqual(self.trial()['status'], 'paused')
        self.assertTrue(self.journeys.trials.needs_work(self.current_journey()))
        self.render_trial()
        self.assertEqual(self.trial()['status'], 'paused')
        self.assertEqual(self.trial()['steps'][1]['status'], 'pending')
        self.assertFalse(self.journeys.trials.needs_work(self.current_journey()))

    def test_lost_ack_reuses_the_render_and_wrong_dimensions_do_not_feed_the_next_step(self):
        self.baseline()
        self.start_trial()
        queue = self.journeys.renderer.queue_comparison
        def lose_ack(step):
            queue(step)
            raise RuntimeError('lost acknowledgement')
        with patch.object(self.journeys.renderer, 'queue_comparison', side_effect=lose_ack):
            self.journeys.trials.advance(self.journey_id)
        self.assertEqual(self.trial()['steps'][0]['status'], 'queued')
        queued = len(self.minimax._render_queue)
        self.journeys.trials.advance(self.journey_id)
        self.assertEqual(len(self.minimax._render_queue), queued)
        self.render_trial(wrong_size=True)
        trial = self.trial()
        self.assertEqual(trial['status'], 'paused')
        self.assertIn('dimensions', trial['error'])
        self.assertIsNone(trial['steps'][1]['source_asset_id'])
        old_request = trial['steps'][0]['render_request_id']
        self.journeys.trials.control(self.journey_id, trial['id'], action='resume')
        self.assertNotEqual(self.trial()['steps'][0]['render_request_id'], old_request)
        self.journeys.trials.advance(self.journey_id)
        self.render_trial()
        self.assertEqual(self.trial()['steps'][1]['source_asset_id'], self.trial()['steps'][0]['output_asset_id'])

    def test_api_rejects_unavailable_steps_and_hidden_changes(self):
        original = self.baseline()
        app = FastAPI()
        app.include_router(image_journeys_router(self.journeys))
        url = f'/api/image-lab/journeys/projects/{self.journey_id}/fixed-trials'
        body = dict(version=original['version'], command='http', count=2)
        with TestClient(app) as client:
            for changes in ({'count': True}, {'count': 3}, {'prompt': 'change'}, {'seed': '42'}, {'version': 0}):
                self.assertIn(client.post(url, json={**body, **changes}).status_code, {409, 422})
            response = client.post(url, json=body)
            self.assertEqual(response.status_code, 202, response.text)
            trial = response.json()['project']['fixed_trials'][0]
            self.assertEqual(trial['steps'][0]['settings']['reference_mode'], 'native')
            duplicate = client.post(url, json=body)
            self.assertEqual(duplicate.json()['project']['fixed_trials'][0]['id'], trial['id'])
