"""User-run regressions: fake gateways only, including legacy rejected journals."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application import image_journey_policies as policies
from panelforge.application import image_journey_realistic_prompting as realistic
from panelforge.application.image_journeys import JourneyConflict
from panelforge.domain import image_journeys as journey
from panelforge.domain.minimax_edit import journey_child_id
from panelforge.features.lab.image_journeys_web import image_journeys_router
from panelforge.infrastructure.presets.minimax_edit import load_minimax_edit_workflow
from test_image_journeys import ImageJourneyFixture
import test_image_journey_edits as manual_tests
import test_image_journey_realistic as real_tests


class ImageJourneyResolutionTest(ImageJourneyFixture):
    start_operation = manual_tests.ImageJourneyEditsTest.start_operation
    operation = manual_tests.ImageJourneyEditsTest.operation
    render_operation = manual_tests.ImageJourneyEditsTest.render_operation
    operation_until = manual_tests.ImageJourneyEditsTest.operation_until

    def setUp(self):
        super().setUp()
        self.gateway = manual_tests.EditGateway()
        self.minimax.gateway = self.journeys.gateway = self.gateway

    def rejected(self, **values):
        self.create_journey(**values)
        self.until('reviewing')
        self.gateway.assessment = 'unusable'
        self.journeys.advance(self.journey_id)
        result = self.current_journey()
        self.assertEqual(result['status'], 'paused')
        self.assertEqual(result['steps'][-1]['review']['assessment'], 'unusable')
        return result

    def command(self, project, action, **changes):
        step = project['steps'][-1]
        return dict(version=project['version'], command=journey.identity('decision'), action=action,
                    step_id=step['id'], output_asset_id=step['output_asset_id'], **changes)

    def decide(self, project, action):
        return self.journeys.resolutions.resolve(self.journey_id, **self.command(project, action))

    def test_accept_uses_real_pixels_preserves_verdict_and_continues_without_regeneration(self):
        blocked = self.rejected(count=2)
        step = deepcopy(blocked['steps'][-1])
        renders, calls = len(self.comfy.submitted), len(self.gateway.requests)
        result = self.decide(blocked, 'accept')
        self.assertEqual(result['steps'][-1]['review'], step['review'])
        self.assertEqual(result['current_asset_id'], step['output_asset_id'])
        self.assertEqual(result['phase'], 'planning')
        self.assertIn(step['id'], journey.transferable_frame_ids(result))
        self.assertEqual((len(self.comfy.submitted), len(self.gateway.requests)), (renders, calls))
        context = json.loads(policies.progression_context(result))
        self.assertIn('accepted_current_image', context)
        self.gateway.assessment = 'usable'
        completed = self.until('completed')
        self.assertEqual(completed['steps'][1]['source_asset_id'], step['output_asset_id'])
        self.assertEqual(len(self.comfy.submitted), 2)
        self.assertEqual(completed['count'], 2)

    def test_accept_last_completes_and_exports_without_a_model_call(self):
        blocked = self.rejected(count=1)
        self.assertEqual(self.journeys.public(blocked)['blocked_images'][0]['accept_label'], 'Accepter et terminer')
        calls = len(self.gateway.requests)
        result = self.decide(blocked, 'accept')
        self.assertEqual((result['phase'], result['status']), ('completed', 'completed'))
        self.journeys.advance(self.journey_id)
        self.assertEqual(len(self.gateway.requests), calls)
        self.assertEqual(len(journey.sequence(result)['frames']), 2)
        target = self.journeys.prepare_transitions(self.journey_id)
        self.assertEqual(len(self.transitions.get(target['project_id'])['frames']), 2)

    def test_regenerate_replaces_same_slot_source_action_and_budget_with_fresh_requests(self):
        blocked = self.rejected(count=2, auto_mask=True)
        old = deepcopy(blocked['steps'][-1])
        rejected_pixels = self.assets.read_bytes(old['output_asset_id'])
        result = self.decide(blocked, 'regenerate')
        new = result['steps'][-1]
        self.assertEqual(len(result['steps']), 1)
        self.assertEqual(result['count'], 2)
        self.assertEqual(journey.generated(result), 0)
        for key in ('source_asset_id', 'action', 'index', 'render_profile', 'journey_version'):
            self.assertEqual(new[key], old[key])
        for key in ('id', 'prompt_request_id', 'render_request_id'):
            self.assertNotEqual(new[key], old[key])
        for key in ('protection', 'raw_output_asset_id', 'attempt_id', 'settings'):
            self.assertNotIn(key, new)
        self.assertEqual(new['regeneration_feedback'], old['review']['observation'])
        self.assertIn(old['review']['observation'], policies.edit_request(new))
        self.assertEqual(result['abandoned_steps'][-1]['output_asset_id'], old['output_asset_id'])
        self.assertEqual(self.assets.read_bytes(old['output_asset_id']), rejected_pixels)
        self.assertEqual(result['completed_milestones'], old['progress_before']['completed_milestones'])
        self.gateway.assessment = 'usable'
        completed = self.until('completed')
        self.assertEqual(journey.generated(completed), 2)
        self.assertEqual(len(self.comfy.submitted), 3)  # One rejected attempt, two retained outputs.
        self.assertNotEqual(journey_child_id(old['id']), completed['steps'][0]['minimax_project_id'])

    def test_retries_are_idempotent_and_stale_or_different_decisions_conflict(self):
        blocked = self.rejected()
        body = self.command(blocked, 'regenerate')
        result = self.journeys.resolutions.resolve(self.journey_id, **body)
        self.assertEqual(self.journeys.resolutions.resolve(self.journey_id, **body), result)
        self.assertEqual(len(result['abandoned_steps']), 1)
        for changes in ({'action': 'accept'}, {'command': 'stale-decision'},
                        {'command': 'old-image', 'version': result['version']}):
            with self.assertRaises(JourneyConflict):
                self.journeys.resolutions.resolve(self.journey_id, **{**body, **changes})
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_legacy_rejection_can_be_regenerated_after_restart_without_replaying_it(self):
        project = self.rejected()
        step = project['steps'][-1]
        before = step.pop('progress_before')
        self.journey_store.save(project)
        self.journeys = self.new_service()
        restored = self.decide(self.current_journey(), 'regenerate')
        self.assertEqual(restored['completed_milestones'], before['completed_milestones'])
        self.assertEqual(restored['summary'], before['summary'])
        self.assertEqual(restored['steps'][-1]['source_asset_id'], step['source_asset_id'])
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_technical_failure_has_no_visual_override(self):
        self.create_journey()
        self.until('reviewing')
        self.gateway.bad_progression = True
        self.journeys.advance(self.journey_id)
        project = self.current_journey()
        self.assertEqual(self.journeys.public(project)['blocked_images'], [])
        with self.assertRaises(JourneyConflict):
            self.decide(project, 'accept')

    def test_inflight_claim_and_pending_addition_block_resolution(self):
        project = self.rejected()
        self.journeys._claims.add(self.journey_id)
        try:
            self.assertFalse(self.journeys.public(project)['blocked_images'][0]['available'])
            with self.assertRaises(JourneyConflict):
                self.decide(project, 'regenerate')
        finally:
            self.journeys._claims.clear()
        self.start_operation()
        project = self.current_journey()
        with self.assertRaises(JourneyConflict):
            self.decide(project, 'accept')

    def test_manual_neighbors_and_existing_exports_survive_regeneration(self):
        self.rejected()
        self.start_operation()
        self.operation_until('completed')
        before = self.current_journey()
        manual = deepcopy(before['manual_steps'])
        exported = self.journeys.prepare_transitions(self.journey_id,
            frame_ids=['source', manual[0]['id']])
        old_export = deepcopy(self.transitions.get(exported['project_id']))
        after = self.decide(before, 'regenerate')
        self.assertEqual(after['manual_steps'], manual)
        self.assertEqual(self.transitions.get(exported['project_id']), old_export)
        self.assertEqual(after['sequence_order'], ['source', after['steps'][0]['id'], manual[0]['id']])

    def rejected_manual(self):
        self.create_journey(count=1)
        self.until('completed')
        self.start_operation('prepend', after_frame_id=None, before_frame_id='source')
        self.operation_until('reviewing')
        project = self.current_journey()
        op = project['image_operations'][-1]
        op.update(status='paused', error='Des ouvriers sont apparus.',
                  review=dict(assessment='unusable', observation='Des ouvriers sont apparus.'))
        self.journey_store.save(project)
        body = dict(version=project['version'], command='manual-decision', step_id=op['id'],
                    output_asset_id=op['output_asset_id'])
        return project, deepcopy(op), body

    def test_accept_manual_commits_once_at_original_gap_and_preserves_original(self):
        before, op, body = self.rejected_manual()
        after = self.journeys.resolutions.resolve(self.journey_id, **body, action='accept')
        self.assertEqual(after['source_asset_id'], before['source_asset_id'])
        self.assertEqual(after['steps'], before['steps'])
        self.assertEqual(journey.ordered_frame_ids(after), [op['id'], 'source', before['steps'][0]['id']])
        self.assertEqual(after['manual_steps'][0]['review'], op['review'])
        self.assertTrue(journey.image_accepted(after['manual_steps'][0]))
        self.assertEqual(self.journeys.resolutions.resolve(self.journey_id, **body, action='accept'), after)

    def test_regenerate_manual_uses_same_source_and_commits_only_replacement(self):
        before, op, body = self.rejected_manual()
        after = self.journeys.resolutions.resolve(self.journey_id, **body, action='regenerate')
        replacement = after['image_operations'][-1]
        self.assertEqual(after['image_operations'][0]['status'], 'cancelled')
        self.assertEqual(replacement['source_asset_id'], op['source_asset_id'])
        self.assertEqual(replacement['action'], op['action'])
        self.assertEqual(replacement['kind'], 'prepend')
        self.assertEqual(replacement['phase'], 'prompting')
        self.operation_until('completed')
        final = self.current_journey()
        self.assertEqual([s['id'] for s in final['manual_steps']], [replacement['id']])
        self.assertEqual(final['steps'], before['steps'])

    def test_http_decision_validates_exact_output_and_preserves_idempotency(self):
        project = self.rejected(count=1)
        app = FastAPI()
        app.include_router(image_journeys_router(self.journeys))
        client = TestClient(app)
        body = self.command(project, 'accept')
        path = f'/api/image-lab/journeys/projects/{self.journey_id}/image-resolutions'
        self.assertEqual(client.post(path, json={**body, 'output_asset_id': 'other'}).status_code, 409)
        self.assertEqual(client.post(path, json={**body, 'version': True}).status_code, 422)
        response = client.post(path, json=body)
        self.assertEqual(response.status_code, 202, response.text)
        self.assertNotIn('image_resolutions', response.json()['project'])
        self.assertEqual(client.post(path, json=body).json(), response.json())


class ImageJourneyHeadTest(ImageJourneyFixture):
    start_operation = manual_tests.ImageJourneyEditsTest.start_operation
    operation = manual_tests.ImageJourneyEditsTest.operation
    render_operation = manual_tests.ImageJourneyEditsTest.render_operation
    operation_until = manual_tests.ImageJourneyEditsTest.operation_until
    real = real_tests.ImageJourneyRealisticTest.real

    def setUp(self):
        super().setUp()
        self.minimax.workflow = load_minimax_edit_workflow(
            Path(__file__).resolve().parents[1] / 'workflows/image.edit/minimax-h3-still/1.3.0')
        self.gateway = real_tests.RealisticGateway()
        self.minimax.gateway = self.journeys.gateway = self.gateway

    def test_realistic_prepend_then_insert_keeps_anchors_source_and_reverse_export(self):
        initial = self.real(count=1)
        existing = deepcopy(self.until('completed')['steps'])
        op = self.start_operation('prepend', after_frame_id=None, before_frame_id='source',
                                  intention='Ajouter une verrière au-dessus de la terrasse.')
        self.assertEqual(op['source_asset_id'], initial['source_asset_id'])
        self.assertEqual(op['finished_reference_asset_id'], initial['source_asset_id'])
        self.operation_until('completed')
        project = self.current_journey()
        self.assertEqual(project['steps'], existing)
        self.assertEqual(project['current_asset_id'], existing[-1]['output_asset_id'])
        plan = next(r for r in self.gateway.requests if r.operation_id == realistic.PLAN_OPERATION)
        self.assertEqual(len(plan.images), 1)
        self.assertIn('PREPEND', plan.system_prompt)
        self.assertEqual(json.loads(plan.user_prompt)['edit_source'], 'CURRENT (first saved state)')
        self.assertIn('ajout manuel', policies.edit_request(op))
        selected = journey.transferable_frame_ids(project)
        export = journey.sequence(project, selected, frame_order='reverse_generation')
        self.assertEqual([f['asset_id'] for f in export['frames']],
                         [existing[-1]['output_asset_id'], initial['source_asset_id'], self.operation()['output_asset_id']])
        middle = self.start_operation('insert', after_frame_id=op['id'], before_frame_id='source')
        self.operation_until('completed')
        final = self.current_journey()
        self.assertEqual(journey.ordered_frame_ids(final), [op['id'], middle['id'], 'source', existing[0]['id']])
        self.assertEqual(journey.generated(final), 1)
        self.assertEqual(final['source_asset_id'], initial['source_asset_id'])

    def test_acceptance_in_realistic_reverse_keeps_constraints_for_future_images(self):
        self.real(count=3)
        project = self.until('reviewing')
        step = project['steps'][-1]
        step['review'] = dict(assessment='unusable', observation='Des ouvriers sont présents.')
        project.update(status='paused', pause_requested=True, error=step['review']['observation'])
        self.journey_store.save(project)
        accepted = self.journeys.resolutions.resolve(self.journey_id, version=project['version'], command='accept-real',
            step_id=step['id'], output_asset_id=step['output_asset_id'], action='accept')
        context = json.loads(policies.progression_context(accepted))
        self.assertEqual(context['population'], 'none')
        self.assertEqual(context['accepted_current_image']['step_id'], step['id'])
        final = self.until('completed')
        self.assertEqual(len(final['steps']), 3)
        self.assertEqual(final['steps'][1]['source_asset_id'], step['output_asset_id'])
        self.assertEqual(final['steps'][1]['journey_preset'], 'realistic')
        self.assertEqual(final['steps'][1]['finished_reference_asset_id'], final['source_asset_id'])

    def test_prepend_before_any_automatic_image_does_not_change_generation_source(self):
        project = self.create_journey()
        self.journeys.pause(self.journey_id)
        op = self.start_operation('prepend', after_frame_id=None, before_frame_id='source')
        self.operation_until('completed')
        self.resume_journey()
        final = self.until('completed')
        self.assertEqual(final['steps'][0]['source_asset_id'], project['source_asset_id'])
        self.assertEqual(journey.ordered_frame_ids(final), [op['id'], 'source', *[s['id'] for s in final['steps']]])

    def test_second_head_addition_and_stale_gap(self):
        self.create_journey(count=1)
        self.until('completed')
        first = self.start_operation('prepend', after_frame_id=None, before_frame_id='source')
        self.operation_until('completed')
        with self.assertRaises(ValueError):
            self.start_operation('prepend', after_frame_id=None, before_frame_id='source')
        second = self.start_operation('prepend', after_frame_id=None, before_frame_id=first['id'])
        self.operation_until('completed')
        self.assertEqual(journey.ordered_frame_ids(self.current_journey())[:3], [second['id'], first['id'], 'source'])

    def test_head_http_contract_and_accepted_pixels_cannot_follow_a_different_output(self):
        self.create_journey(count=1)
        project = self.until('completed')
        app = FastAPI()
        app.include_router(image_journeys_router(self.journeys))
        client = TestClient(app)
        response = client.post(f'/api/image-lab/journeys/projects/{self.journey_id}/image-operations', json=dict(
            version=project['version'], command='head-http', kind='prepend', before_frame_id='source', intention='Ajouter un toit.'))
        self.assertEqual(response.status_code, 202, response.text)
        self.assertTrue(client.get('/api/image-lab/journeys/spec').json()['prepend_images'])
        step = deepcopy(project['steps'][0])
        step.update(review=dict(assessment='unusable'), user_acceptance=dict(output_asset_id=step['output_asset_id']))
        self.assertTrue(journey.image_accepted(step))
        step['output_asset_id'] = 'different-pixels'
        self.assertFalse(journey.image_accepted(step))
