"""User-run regressions for retaining an earlier image attempt; all gateways are fakes."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application.image_journeys import JourneyConflict
from panelforge.application import image_journey_policies as policies
from panelforge.domain import image_journeys as journey
from panelforge.features.lab.image_journeys_web import image_journeys_router
from panelforge.infrastructure.presets.minimax_edit import load_minimax_edit_workflow
from test_image_journeys import ImageJourneyFixture
import test_image_journey_retries as retry_tests


class ImageJourneyRetainAttemptTest(ImageJourneyFixture):
    real = retry_tests.ImageJourneyRetriesTest.real
    render_frame = retry_tests.ImageJourneyRetriesTest.render_frame
    render_current = retry_tests.ImageJourneyRetriesTest.render_current
    start_operation = retry_tests.ImageJourneyRetriesTest.start_operation
    operation = retry_tests.ImageJourneyRetriesTest.operation
    render_operation = retry_tests.ImageJourneyRetriesTest.render_operation
    operation_until = retry_tests.ImageJourneyRetriesTest.operation_until

    def setUp(self):
        super().setUp()
        self.minimax.workflow = load_minimax_edit_workflow(
            Path(__file__).resolve().parents[1] / 'workflows/image.edit/minimax-h3-still/1.3.0')
        self.gateway = retry_tests.RetryGateway()
        self.journeys.gateway = self.minimax.gateway = self.gateway

    def blocked(self, count=2):
        self.gateway.verdicts = [retry_tests.PEOPLE, retry_tests.PEOPLE]
        self.real(count=count)
        self.until('reviewing')
        self.journeys.advance(self.journey_id)
        self.until('reviewing')
        self.journeys.advance(self.journey_id)
        result = self.current_journey()
        self.assertEqual(result['status'], 'paused')
        return result

    def body(self, project, step=None, **changes):
        step = step or project['steps'][-1]
        return {**dict(version=project['version'], command='choose-initial', step_id=step['id'],
            output_asset_id=step['attempt_history'][0]['output_asset_id'], action='accept'), **changes}

    def test_initial_becomes_actual_source_and_only_selected_output_is_exported(self):
        blocked = self.blocked()
        correction = deepcopy(blocked['steps'][0])
        first = deepcopy(correction['attempt_history'][0])
        calls, renders = len(self.gateway.requests), len(self.comfy.submitted)
        accepted = self.journeys.resolutions.resolve(self.journey_id, **self.body(blocked))
        step = accepted['steps'][0]
        self.assertEqual(step['id'], correction['id'])
        self.assertEqual(accepted['current_asset_id'], first['output_asset_id'])
        self.assertEqual(accepted['phase'], 'planning')
        self.assertEqual(accepted['summary'], first['review']['observation'])
        self.assertEqual(accepted['completed_milestones'], correction['progress_before']['completed_milestones'])
        for key in ('output_asset_id', 'source_asset_id', 'review', 'prompt', 'settings', 'minimax_project_id', 'attempt_id'):
            self.assertEqual(step[key], first[key], key)
        self.assertEqual(step['retained_attempt_index'], 0)
        self.assertEqual(step['automatic_retry_count'], 1)
        self.assertEqual([a['output_asset_id'] for a in step['attempt_history']],
                         [first['output_asset_id'], correction['output_asset_id']])
        self.assertEqual(step['user_acceptance']['output_asset_id'], first['output_asset_id'])
        self.assertEqual(step['review']['assessment'], 'unusable')
        self.assertEqual((len(self.gateway.requests), len(self.comfy.submitted)), (calls, renders))
        self.assertEqual(self.journeys.renderer.result(step)['output_asset_id'], first['output_asset_id'])
        context = json.loads(policies.progression_context(accepted))
        self.assertEqual(context['accepted_current_image']['previous_review'], first['review'])
        completed = self.until('completed')
        self.assertEqual(completed['steps'][1]['source_asset_id'], first['output_asset_id'])
        self.assertEqual(len(self.comfy.submitted), 3)
        target = self.journeys.prepare_transitions(self.journey_id)
        outputs = [f['asset_id'] for f in self.transitions.get(target['project_id'])['frames']]
        self.assertIn(first['output_asset_id'], outputs)
        self.assertNotIn(correction['output_asset_id'], outputs)

    def test_last_initial_finishes_without_model_call_and_survives_restart(self):
        blocked = self.blocked(count=1)
        calls = len(self.gateway.requests)
        body = self.body(blocked)
        selected = self.journeys.resolutions.resolve(self.journey_id, **body)
        self.assertEqual(selected['status'], 'completed')
        self.assertEqual(self.journeys.resolutions.resolve(self.journey_id, **body), selected)
        self.assertEqual(len(selected['image_resolutions']), 1)
        self.journeys = self.new_service()
        self.journeys.recover()
        self.journeys.advance(self.journey_id)
        opened = self.journeys.public(self.current_journey())
        self.assertEqual(opened['steps'][0]['retained_attempt_index'], 0)
        self.assertEqual(len(opened['steps'][0]['attempt_history']), 2)
        self.assertEqual(opened['transferable_frame_ids'], ['source', body['step_id']])
        self.assertEqual(opened['blocked_images'], [])
        self.assertEqual(len(self.gateway.requests), calls)
        self.assertEqual(len(self.comfy.submitted), 2)

    def test_http_accepts_exact_archive_but_rejects_stale_foreign_and_regenerate_requests(self):
        project = self.blocked()
        body = self.body(project)
        app = FastAPI()
        app.include_router(image_journeys_router(self.journeys))
        endpoint = '/api/image-lab/journeys/projects/' + self.journey_id + '/image-resolutions'
        with TestClient(app) as client:
            for change in (dict(version=body['version'] - 1), dict(output_asset_id='unrelated-asset'),
                           dict(action='regenerate'), dict(step_id='unrelated-step')):
                response = client.post(endpoint, json={**body, **change})
                self.assertEqual(response.status_code, 409, response.text)
            response = client.post(endpoint, json=body)
            self.assertEqual(response.status_code, 202, response.text)
            self.assertEqual(response.json()['project']['steps'][0]['output_asset_id'], body['output_asset_id'])
            self.assertEqual(client.post(endpoint, json=body).status_code, 202)
            self.assertEqual(client.post(endpoint, json={**body, 'command': 'new-stale'}).status_code, 409)
        self.assertEqual(len(self.comfy.submitted), 2)

    def test_archive_cannot_be_accepted_while_correction_is_running(self):
        self.gateway.verdicts = [retry_tests.PEOPLE]
        self.real(count=2)
        self.until('reviewing')
        self.journeys.advance(self.journey_id)
        pending = self.current_journey()
        with self.assertRaises(JourneyConflict):
            self.journeys.resolutions.resolve(self.journey_id, **self.body(pending))
        self.assertEqual(self.current_journey(), pending)

    def test_manual_gaps_retain_initial_without_changing_neighbors(self):
        for kind in ('insert', 'append', 'prepend'):
            with self.subTest(kind=kind):
                self.real(count=1, command='retain-' + kind)
                before = deepcopy(self.until('completed')['steps'])
                anchors = (dict(after_frame_id='source', before_frame_id=before[0]['id']) if kind == 'insert'
                    else dict(after_frame_id=None, before_frame_id='source') if kind == 'prepend' else {})
                self.start_operation(kind, **anchors)
                self.gateway.verdicts = [retry_tests.PEOPLE, retry_tests.PEOPLE]
                self.operation_until('reviewing')
                self.journeys.edits.advance(self.journey_id)
                self.operation_until('reviewing')
                self.journeys.edits.advance(self.journey_id)
                op = self.operation()
                self.assertEqual(op['status'], 'paused')
                body = self.body(self.current_journey(), step=op, command='choose-' + kind)
                calls, renders = len(self.gateway.requests), len(self.comfy.submitted)
                accepted = self.journeys.resolutions.resolve(self.journey_id, **body)
                self.assertEqual(accepted['steps'], before)
                self.assertEqual(len(accepted['manual_steps']), 1)
                step = accepted['manual_steps'][0]
                self.assertEqual(step['output_asset_id'], body['output_asset_id'])
                self.assertEqual(step['retained_attempt_index'], 0)
                self.assertEqual(len(step['attempt_history']), 2)
                self.assertEqual(journey.ordered_frame_ids(accepted).count(op['id']), 1)
                self.assertEqual((len(self.gateway.requests), len(self.comfy.submitted)), (calls, renders))
                self.assertIn(step['id'], journey.transferable_frame_ids(accepted))
                if kind == 'append':
                    self.assertEqual(accepted['current_asset_id'], body['output_asset_id'])

    def test_selection_after_manual_regeneration_keeps_original_render_provenance(self):
        blocked = self.blocked()
        old = deepcopy(blocked['steps'][0])
        regenerated = self.journeys.resolutions.resolve(self.journey_id, **self.body(blocked,
            command='regenerate-current', action='regenerate', output_asset_id=old['output_asset_id']))
        self.gateway.verdicts = [retry_tests.PEOPLE]
        self.until('reviewing')
        self.journeys.advance(self.journey_id)
        blocked = self.current_journey()
        self.assertNotEqual(regenerated['steps'][0]['id'], old['id'])
        accepted = self.journeys.resolutions.resolve(self.journey_id, **self.body(blocked))
        chosen = accepted['steps'][0]
        self.assertEqual(len(chosen['attempt_history']), 3)
        self.assertEqual(chosen['render_step_id'], old['id'])
        child = self.minimax.ensure_journey_step(chosen)
        self.assertEqual(child['id'], old['attempt_history'][0]['minimax_project_id'])
        self.assertEqual(self.journeys.renderer.result(chosen)['output_asset_id'], chosen['output_asset_id'])
        self.assertEqual(len(self.comfy.submitted), 3)

    def test_later_manual_image_prevents_replacing_its_source_with_an_archive(self):
        blocked = self.blocked()
        self.start_operation('append')
        self.operation_until('completed')
        current = self.current_journey()
        self.assertEqual(self.journeys.public(current)['blocked_images'][0]['accept_previous_asset_ids'], [])
        with self.assertRaises(JourneyConflict):
            self.journeys.resolutions.resolve(self.journey_id, **self.body(current))
        self.assertEqual(self.current_journey()['steps'], blocked['steps'])
