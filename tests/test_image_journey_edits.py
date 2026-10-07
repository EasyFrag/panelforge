"""User-run regressions for manual steps and isolated HQ. All gateways are fakes."""
from copy import deepcopy
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application import image_journey_edit_prompting as prompting
from panelforge.application import image_journey_v2_prompting as prompting_v2
from panelforge.application.image_journeys import JourneyConflict
from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.domain import image_journeys as policy
from panelforge.domain.image_journey_edits import HQ_PROMPT
from panelforge.domain.minimax_edit import MinimaxEditSettings, journey_child_id
from panelforge.features.lab.image_journeys_web import image_journeys_router
from test_image_journeys import ImageJourneyFixture, JourneyGateway
from test_qwen_edit import png


class EditGateway(JourneyGateway):
    bad_manual_review = False
    premature_end = False

    def stream(self, request):
        reviewing = request.operation_id in {prompting.REVIEW_OPERATION, prompting_v2.REVIEW_OPERATION}
        if reviewing or request.operation_id in {prompting.PLAN_OPERATION, prompting_v2.PLAN_OPERATION}:
            self.requests.append(request)
            value = (dict(assessment='usable', observation='Le deck demandé est visible.')
                     if reviewing else
                     dict(title='Deck seul', change='Retirer la porte et son ouverture en conservant le deck.',
                          preserve='Le même deck, le cadrage et les couleurs.'))
            if not reviewing and request.operation_id == prompting_v2.PLAN_OPERATION:
                value['change'] += ' Déplacer la personne vers la droite du chantier.'
            raw = 'invalid' if self.bad_manual_review and reviewing else json.dumps(value)
            yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED,
                result=CompletionResult(request.model_id, raw, call_id='manual-call'))
            return
        for event in super().stream(request):
            if (self.premature_end and event.kind is StreamEventKind.COMPLETED
                    and event.result and 'remaining_images' in request.user_prompt):
                context = json.loads(request.user_prompt)
                if context['reviewing_result'] and context['remaining_images']:
                    value = json.loads(event.result.content)
                    value['next_action'] = None
                    yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED,
                        result=CompletionResult(request.model_id, json.dumps(value), call_id='premature-call'))
                    continue
            yield event


class ImageJourneyEditsTest(ImageJourneyFixture):
    def setUp(self):
        super().setUp()
        self.gateway = EditGateway()
        self.minimax.gateway = self.gateway
        self.journeys.gateway = self.gateway

    def start_operation(self, kind='append', **values):
        project = self.current_journey()
        steps = policy.ordered_steps(project)
        body = dict(version=project['version'], command=policy.identity('command'), kind=kind,
                    after_frame_id=steps[-1]['id'] if steps else 'source', intention='Ajouter un petit escalier en bois.')
        if kind == 'hq':
            body.update(intention='', prompt=HQ_PROMPT)
        result = self.journeys.edits.start(self.journey_id, **{**body, **values})
        return result['image_operations'][-1]

    def operation(self):
        return self.current_journey()['image_operations'][-1]

    def render_operation(self):
        op = self.operation()
        child = self.minimax.get(journey_child_id(op['id']))
        stage = child['stages'][0]
        attempt = next(a for a in stage['attempts'] if a['request_id'] == op['render_request_id'])
        self.comfy.output = png('green', size=tuple(op['dimensions']))
        self.minimax.execute_attempt(child['id'], stage['id'], attempt['id'])

    def operation_until(self, phase):
        for _ in range(25):
            op = self.operation()
            if op['phase'] == phase:
                return op
            self.assertNotEqual(op['status'], 'paused', op.get('error'))
            if op['phase'] == 'rendering':
                self.render_operation()
            self.journeys.edits.advance(self.journey_id)
        self.fail('Manual operation did not reach ' + phase)

    def test_insert_preserves_existing_steps_and_exports_the_new_order(self):
        self.create_journey()
        project = self.until('completed')
        existing = deepcopy(project['steps'])
        old_export = self.journeys.prepare_transitions(self.journey_id)
        op = self.start_operation('insert', after_frame_id=existing[0]['id'], before_frame_id=existing[1]['id'],
                                  intention='Le deck seul avant la porte.')
        self.assertEqual(op['source_asset_id'], existing[1]['output_asset_id'])
        self.operation_until('completed')
        current = self.current_journey()
        self.assertEqual(current['steps'], existing)
        self.assertEqual(current['count'], 2)
        self.assertEqual(policy.generated(current), 2)
        self.assertEqual([s['id'] for s in policy.ordered_steps(current)], [existing[0]['id'], op['id'], existing[1]['id']])
        plan = next(r for r in self.gateway.requests if r.operation_id == prompting.PLAN_OPERATION)
        self.assertEqual(plan.model_id, 'progression-vision')
        self.assertEqual(len(plan.images), 2)
        self.assertEqual(plan.images[1].content, self.assets.read_bytes(existing[1]['output_asset_id']))
        exported = self.journeys.prepare_transitions(self.journey_id)
        self.assertNotEqual(exported, old_export)
        self.assertEqual(len(self.transitions.get(old_export['project_id'])['frames']), 3)
        self.assertEqual(len(self.transitions.get(exported['project_id'])['frames']), 4)
        self.assertEqual(len(self.comfy.submitted), 3)

    def test_append_uses_last_real_output_even_when_current_asset_is_stale(self):
        self.create_journey()
        self.until('reviewing')
        project = self.journeys.pause(self.journey_id)
        automatic = deepcopy(project['steps'][0])
        self.assertNotEqual(automatic['output_asset_id'], project['current_asset_id'])
        op = self.start_operation()
        self.assertEqual(op['source_asset_id'], automatic['output_asset_id'])
        finished = self.operation_until('completed')
        self.assertEqual(self.current_journey()['current_asset_id'], finished['output_asset_id'])
        self.assertEqual(self.current_journey()['steps'][0], automatic)
        self.resume_journey()
        self.journeys.advance(self.journey_id)  # Persist old automatic review, then replan from the actual tail.
        self.assertEqual(self.current_journey()['phase'], 'planning')
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.progression_calls()[-1].images[0].content, self.assets.read_bytes(finished['output_asset_id']))
        result = self.until('completed')
        self.assertEqual(policy.generated(result), 2)
        self.assertEqual(len(policy.sequence(result)['frames']), 4)

    def test_append_to_completed_journey_does_not_restart_automatic_generation(self):
        self.create_journey(count=1)
        self.until('completed')
        self.start_operation()
        first = self.operation_until('completed')
        self.start_operation()
        second = self.operation_until('completed')
        self.assertEqual(second['source_asset_id'], first['output_asset_id'])
        project = self.current_journey()
        self.assertEqual(project['status'], 'completed')
        self.assertEqual(project['count'], 1)
        self.assertEqual(len(policy.sequence(project)['frames']), 4)

    def test_hq_doubles_output_without_resizing_reference_or_touching_sequence(self):
        project = self.create_journey(count=1, content=png(size=(128, 128)))
        before = deepcopy(policy.sequence(project))
        op = self.start_operation('hq', after_frame_id='source')
        finished = self.operation_until('completed')
        self.assertEqual(finished['output_dimensions'], [v * 2 for v in project['source_dimensions']])
        self.assertEqual(self.gateway.requests, [])
        self.assertEqual(policy.sequence(self.current_journey()), before)
        self.assertEqual(self.current_journey()['current_asset_id'], project['current_asset_id'])
        child = self.minimax.get(journey_child_id(op['id']))
        attempt = child['stages'][0]['attempts'][0]
        self.assertEqual(attempt['prompt'], HQ_PROMPT)
        self.assertEqual(attempt['context']['render_inputs'][0]['asset_id'], project['source_asset_id'])
        graph = self.comfy.submitted[-1]
        manifest = self.minimax.workflow.manifest
        slot = manifest['image_slots'][0]
        self.assertNotIn(slot['scale_node'], graph)
        self.assertEqual(graph[manifest['conditioning_node']]['inputs'][slot['input']], [slot['load_node'], 0])
        for name, value in zip(('width', 'height'), finished['output_dimensions']):
            for binding in manifest['inputs'][name]:
                self.assertEqual(graph[binding['node_id']]['inputs'][binding['input']], value)

    def test_manual_command_is_idempotent_and_stale_anchors_are_rejected(self):
        self.create_journey(count=1)
        project = self.until('completed')
        body = dict(version=project['version'], command='manual-one', kind='append',
                    after_frame_id=project['steps'][0]['id'], intention='Un escalier.')
        first = self.journeys.edits.start(self.journey_id, **body)
        self.assertEqual(self.journeys.edits.start(self.journey_id, **body)['version'], first['version'])
        with self.assertRaises(JourneyConflict):
            self.journeys.edits.start(self.journey_id, **{**body, 'intention':'Autre chose'})
        self.operation_until('completed')
        with self.assertRaises(ValueError):
            self.start_operation(after_frame_id=project['steps'][0]['id'])
        with self.assertRaises(JourneyConflict):
            self.journeys.edits.start(self.journey_id, **{**body, 'command':'stale-version'})

    def test_running_journey_cannot_be_edited_but_allows_isolated_hq(self):
        self.create_journey(content=png(size=(128, 128)))
        with self.assertRaises(JourneyConflict):
            self.start_operation(after_frame_id='source')
        self.start_operation('hq', after_frame_id='source')
        self.assertEqual(self.operation()['kind'], 'hq')

    def test_restart_collects_submitted_render_and_waits_before_review(self):
        self.create_journey(count=1)
        self.until('completed')
        self.start_operation()
        self.operation_until('rendering')
        requests = len(self.gateway.requests)
        op = self.operation()
        before = len(self.minimax._render_queue)
        self.journeys = self.new_service()
        self.journeys.recover()
        self.assertEqual(self.operation()['status'], 'paused')
        self.render_operation()
        self.journeys.edits.advance(self.journey_id)
        self.assertEqual(self.operation()['phase'], 'reviewing')
        self.journeys.edits.advance(self.journey_id)
        self.assertEqual(len(self.gateway.requests), requests)
        self.assertEqual(len(self.minimax._render_queue), before)
        self.journeys.edits.control(self.journey_id, op['id'], action='resume')
        self.operation_until('completed')
        self.assertEqual(len(self.comfy.submitted), 2)

    def test_lost_queue_acknowledgement_does_not_submit_a_second_hq(self):
        self.create_journey(count=1, content=png(size=(128, 128)))
        op = self.start_operation('hq', after_frame_id='source')
        attempt = self.journeys.renderer.queue_comparison(op)
        self.journeys.edits.advance(self.journey_id)
        self.assertEqual(self.operation()['attempt_id'], attempt['id'])
        self.assertEqual(len(self.minimax._render_queue), 1)
        self.operation_until('completed')
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_failed_review_keeps_output_and_resume_does_not_regenerate(self):
        self.create_journey(count=1)
        self.until('completed')
        op = self.start_operation()
        self.operation_until('reviewing')
        output = self.operation()['output_asset_id']
        self.gateway.bad_manual_review = True
        self.journeys.edits.advance(self.journey_id)
        self.assertEqual(self.operation()['status'], 'paused')
        self.assertEqual(self.operation()['output_asset_id'], output)
        self.gateway.bad_manual_review = False
        self.journeys.edits.control(self.journey_id, op['id'], action='resume')
        self.operation_until('completed')
        self.assertEqual(len(self.comfy.submitted), 2)

    def test_missing_next_action_preserves_review_then_finishes_requested_budget(self):
        self.gateway.premature_end = True
        self.create_journey()
        self.until('reviewing')
        self.journeys.advance(self.journey_id)
        project = self.current_journey()
        self.assertEqual(project['status'], 'running')
        self.assertEqual(project['phase'], 'planning')
        self.assertEqual(project['steps'][0]['review']['assessment'], 'usable')
        self.assertEqual(project['current_asset_id'], project['steps'][0]['output_asset_id'])
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.progression_calls()[-1].output_schema['properties']['next_action']['type'], 'object')
        result = self.until('completed')
        self.assertEqual(policy.generated(result), 2)
        self.assertEqual(len(self.comfy.submitted), 2)

    def test_hq_validation_and_http_creation_never_launch_models(self):
        project = self.create_journey(count=1, content=png(size=(128, 128)))
        app = FastAPI()
        app.include_router(image_journeys_router(self.journeys))
        prefix = '/api/image-lab/journeys'
        url = prefix + '/projects/' + project['id'] + '/image-operations'
        body = dict(version=project['version'], command='hq-http', kind='hq', after_frame_id='source', prompt=HQ_PROMPT)
        with TestClient(app) as client:
            self.assertEqual(client.get(prefix + '/spec').json()['hq_prompt'], HQ_PROMPT)
            self.assertEqual(client.post(url, json={**body, 'prompt':'Upscale without an image tag'}).status_code, 422)
            self.assertEqual(client.post(url, json={**body, 'version':True}).status_code, 422)
            response = client.post(url, json=body)
            self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(self.gateway.requests, [])
        self.assertEqual(self.comfy.submitted, [])
        with self.assertRaises(ValueError):
            MinimaxEditSettings(resolution='double', reference_mode='native').dimensions((2016, 3584))
        self.assertEqual(MinimaxEditSettings(resolution='double', reference_mode='native').dimensions((768, 1376)), (1536, 2752))

    def test_abandon_interrupted_planning_releases_the_gap_without_changing_images(self):
        self.create_journey(count=1)
        self.until('completed')
        before = deepcopy(policy.sequence(self.current_journey()))
        op = self.start_operation()
        self.journeys.recover()
        self.journeys.edits.control(self.journey_id, op['id'], action='cancel')
        self.assertEqual(policy.sequence(self.current_journey()), before)
        self.assertEqual(self.operation()['status'], 'cancelled')
        self.start_operation()
        self.assertEqual(len(self.current_journey()['image_operations']), 2)

    def test_failed_hq_render_retries_only_after_resume_and_keeps_the_prompt(self):
        self.create_journey(count=1, content=png(size=(128, 128)))
        op = self.start_operation('hq', after_frame_id='source')
        self.operation_until('rendering')
        child = self.minimax.get(journey_child_id(op['id']))
        stage = child['stages'][0]
        attempt = stage['attempts'][0]
        self.minimax._attempt_update(child['id'], stage['id'], attempt['id'], status='failed', error='Fake failure')
        self.journeys.edits.advance(self.journey_id)
        self.assertEqual(self.operation()['status'], 'paused')
        queued = len(self.minimax._render_queue)
        self.journeys.edits.advance(self.journey_id)
        self.assertEqual(len(self.minimax._render_queue), queued)
        self.journeys.edits.control(self.journey_id, op['id'], action='resume')
        finished = self.operation_until('completed')
        self.assertEqual(finished['prompt'], HQ_PROMPT)
        self.assertNotEqual(finished['render_request_id'], op['render_request_id'])
        self.assertEqual(self.gateway.requests, [])
        self.assertEqual(len(self.comfy.submitted), 1)
