"""User-run reverse plan/endpoint regressions; synthetic images and fake gateways only."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from panelforge.application.image_journey_reverse_prompting import REVERSE_POLICIES
from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.domain import image_journeys as policy
from panelforge.infrastructure.presets.minimax_edit import load_minimax_edit_workflow
from test_image_journeys import ImageJourneyFixture
from test_image_journey_reverse import ReverseGateway

ROOT = Path(__file__).resolve().parents[1]
PLAN = ['Retirer le toit.', 'Retirer les piliers supérieurs.', 'Terrain dégagé.']
REVERSE = REVERSE_POLICIES['2']


def action(through=1):
    return dict(title='Retrait partiel', change='Retirer les piliers de gauche.',
                preserve='Conserver la base et les autres piliers.', through_milestone=through)


def snapshot(*, phase='reviewing', count=3, outputs=1, done=0):
    steps = [dict(id=f'step-{i}', source_asset_id=f'asset-{i}', output_asset_id=f'asset-{i+1}',
                  review=dict(assessment='usable'), action=action()) for i in range(outputs)]
    return dict(journey_direction='reverse', journey_version='2', phase=phase, count=count, steps=steps,
                manual_steps=[], current_asset_id=f'asset-{outputs}', source_asset_id='asset-0',
                milestones=list(PLAN), destination='Surface plate sans bâtiment.', completed_milestones=done,
                intent_revision=0, plan_revision=0)


def reply(*, done=1, assessment='usable', next_action=None):
    return dict(completed_milestones=done, assessment=assessment, summary='La base reste visible.',
                observation='Retrait partiel observé.', next_action=next_action)


class ReverseEndpointContractTest(unittest.TestCase):
    def test_locked_plan_is_owned_by_application_even_if_old_reply_echoes_rephrased_text(self):
        project = snapshot()
        before = deepcopy(project)
        for version in REVERSE_POLICIES.values():
            schema = version.schema(project)
            self.assertNotIn('milestones', schema['properties'])
            self.assertNotIn('destination', schema['required'])
            for extra in ({}, dict(destination='Autre formulation', milestones=[m.replace(' supérieurs', '') for m in PLAN])):
                value = {**reply(next_action=action()), **extra}
                original = deepcopy(value)
                decision = version.decode(json.dumps(value), project)
                self.assertEqual(decision['milestones'], PLAN)
                self.assertEqual(decision['destination'], before['destination'])
                self.assertEqual(value, original)
        self.assertEqual(project, before)
        forward = {**project, 'journey_direction': 'forward'}
        with self.assertRaisesRegex(ValueError, 'fixes'):
            policy.validate_decision({**reply(next_action=action()), 'destination': 'Different', 'milestones': PLAN}, forward)

    def test_initial_and_changed_intention_still_require_a_new_explicit_plan(self):
        for project in (snapshot(phase='planning', outputs=0), snapshot(phase='planning')):
            project['intent_revision'] = 1
            value = reply(assessment='initial', done=0, next_action=action())
            with self.assertRaises(ValueError):
                REVERSE.decode(json.dumps(value), project)
            value.update(destination='Un autre sol.', milestones=['Retrait du toit.', 'Retrait partiel.', 'Sol libre.'])
            result = REVERSE.decode(json.dumps(value), project)
            self.assertEqual(result['destination'], 'Un autre sol.')
            self.assertEqual(result['milestones'], value['milestones'])
            self.assertIn('milestones', REVERSE.schema(project)['required'])

    def test_partial_milestone_including_zero_is_valid_and_final_milestone_is_reserved(self):
        for done in (0, 1, 2):
            project = snapshot(phase='planning', outputs=0)
            value = reply(done=done, assessment='initial', next_action=action(done))
            self.assertEqual(REVERSE.decode(json.dumps(value), project)['next_action']['through_milestone'], done)
            value['next_action'] = action(3)
            with self.assertRaisesRegex(ValueError, 'dernière image'):
                REVERSE.decode(json.dumps(value), project)
        final = snapshot(phase='planning', outputs=2, done=2)
        self.assertEqual(REVERSE.decode(json.dumps(reply(done=2, assessment='initial', next_action=action(3))), final)['next_action'], action(3))

    def test_real_review_is_saved_when_only_the_next_action_is_invalid(self):
        project = snapshot()
        value = reply(done=2, next_action=action(3))
        decision = REVERSE.decode(json.dumps(value), project)
        self.assertEqual(decision['assessment'], 'usable')
        self.assertIsNone(decision['next_action'])
        self.assertIn('dernière image', decision['next_action_error'])
        for change in (dict(assessment='initial'), dict(completed_milestones=4), dict(observation=''), dict(unexpected=True)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                REVERSE.decode(json.dumps({**value, **change}), project)

    def test_endpoint_discards_a_noop_but_initial_unusable_or_manual_states_cannot_finish(self):
        project = snapshot(outputs=2)
        value = reply(done=3, next_action=action(3))
        value['next_action']['change'] = 'Aucun changement requis.'
        decision = REVERSE.decode(json.dumps(value), project)
        self.assertIsNone(decision['next_action'])
        self.assertTrue(policy.reverse_endpoint_reached(project, decision))
        self.assertFalse(policy.reverse_endpoint_reached(project, {**decision, 'assessment': 'unusable'}))
        self.assertFalse(policy.reverse_endpoint_reached(snapshot(phase='planning', outputs=0), {**decision, 'assessment': 'initial'}))
        project['manual_steps'] = [dict(id='manual', output_asset_id='another', manual=True)]
        self.assertFalse(policy.reverse_endpoint_reached(project, decision))

    def test_old_planning_checkpoint_requires_an_accepted_endpoint_for_the_current_source(self):
        project = snapshot(phase='planning', outputs=2, done=3)
        value = reply(done=3, assessment='initial', next_action=action(3))
        decision = REVERSE.decode(json.dumps(value), project)
        self.assertIsNone(decision['next_action'])
        self.assertTrue(policy.reverse_endpoint_reached(project, decision))
        for change in ('current_asset_id', 'plan_revision', 'review'):
            other = deepcopy(project)
            if change == 'review':
                other['steps'][-1]['review']['assessment'] = 'unusable'
            else:
                other[change] = 'different'
            self.assertFalse(policy.reverse_endpoint_reached(other, decision))


class EndpointGateway(ReverseGateway):
    early_at = None
    bad_next = False
    echo_plan = False
    verdict = 'usable'

    def stream(self, request):
        for event in super().stream(request):
            if 'reverse-progression' not in request.operation_id or not event.result:
                yield event
                continue
            context = json.loads(request.user_prompt)
            remaining = context['remaining_images']
            number = context['total_new_images'] - remaining
            reviewing = context['reviewing_result']
            done = min(number, 2) if reviewing else context['completed_milestones']
            if not remaining or reviewing and self.early_at is not None and number >= self.early_at:
                done = 3
            through = 3 if remaining == 1 else min(done + 1, 2)
            if self.bad_next and reviewing and number == 1:
                done, through = 2, 3
            if not reviewing and number and done == 2 and remaining > 1:
                through = 2
            value = reply(done=done, assessment=self.verdict if reviewing else 'initial',
                          next_action=action(through) if remaining else None)
            if done == 3 and remaining:
                value['next_action'] = {**action(3), 'title': 'Fin du processus', 'change': 'Aucun changement requis.'}
            if not context['existing_plan_locked']:
                value.update(destination='Surface plate sans bâtiment.', milestones=list(PLAN))
            elif self.echo_plan:
                value.update(destination=context['destination'], milestones=[m.replace(' supérieurs', '') for m in context['milestones']])
            yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED,
                result=CompletionResult(request.model_id, json.dumps(value), call_id='endpoint-fake'))


class ReverseEndpointServiceTest(ImageJourneyFixture):
    def setUp(self):
        super().setUp()
        self.minimax.workflow = load_minimax_edit_workflow(ROOT / 'workflows/image.edit/minimax-h3-still/1.3.0')
        self.gateway = EndpointGateway()
        self.minimax.gateway = self.journeys.gateway = self.gateway

    def reverse(self, **values):
        return self.create_journey(**{'journey_direction': 'reverse', 'journey_version': '2', 'count': 3, **values})

    def test_rephrased_jalon_resume_reviews_saved_image_and_continues_without_rerender(self):
        self.reverse()
        self.until('reviewing')
        self.journeys.advance(self.journey_id)
        self.until('reviewing')
        self.journeys.pause(self.journey_id)
        project = self.current_journey()
        project['error'] = 'Le cap et les jalons restent fixes jusqu’à une modification de l’intention.'
        self.journey_store.save(project)
        original = deepcopy(project['steps'][-1])
        self.gateway.echo_plan = True
        self.journeys = self.new_service()
        self.resume_journey()
        self.journeys.advance(self.journey_id)
        reviewed = self.current_journey()
        self.assertEqual(reviewed['phase'], 'ready')
        self.assertEqual(reviewed['steps'][-1]['output_asset_id'], original['output_asset_id'])
        self.assertEqual(reviewed['milestones'], PLAN)
        self.assertEqual(len(self.comfy.submitted), 2)
        self.assertEqual(len(self.prompt_calls()), 2)
        self.until('completed')
        self.assertEqual(len(self.comfy.submitted), 3)

    def test_bad_next_action_keeps_review_and_replans_with_a_partial_step(self):
        self.gateway.bad_next = True
        self.reverse()
        self.until('reviewing')
        self.journeys.advance(self.journey_id)
        project = self.current_journey()
        self.assertEqual(project['phase'], 'planning')
        self.assertEqual(project['status'], 'running')
        self.assertEqual(project['steps'][0]['review']['assessment'], 'usable')
        self.assertIn('dernière image', project['analyses'][-1]['next_action_error'])
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()['next_action']['through_milestone'], 2)
        self.assertIn('dernière image', json.loads(self.gateway.requests[-1].user_prompt)['previous_next_action_error'])
        result = self.until('completed')
        self.assertEqual(len(result['steps']), 3)
        self.assertEqual(len(self.comfy.submitted), 3)
        self.assertEqual(len(self.prompt_calls()), 3)

    def test_early_endpoint_stops_without_a_noop_call_and_survives_recovery_and_export(self):
        self.gateway.early_at = 2
        self.reverse()
        result = self.until('completed')
        self.assertEqual(result['count'], 3)
        self.assertEqual(policy.generated(result), 2)
        self.assertIsNone(result['next_action'])
        self.assertEqual(result['completion_reason'], 'reverse_endpoint')
        self.assertIn('2 images sur 3', result['warning'])
        self.assertEqual(len(self.comfy.submitted), 2)
        self.assertEqual(len(self.prompt_calls()), 2)
        self.assertEqual(len([r for r in self.gateway.requests if 'reverse-progression' in r.operation_id]), 3)
        calls = len(self.gateway.requests)
        self.journeys = self.new_service()
        self.journeys.recover()
        self.journeys.advance(self.journey_id)
        public = self.journeys.public(self.current_journey())
        self.assertEqual(public['generated'], 2)
        self.assertEqual(public['transferable_images'], 3)
        target = self.journeys.prepare_transitions(self.journey_id,
            frame_ids=public['transferable_frame_ids'], frame_order='reverse_generation')
        frames = self.transitions.get(target['project_id'])['frames']
        self.assertEqual([f['asset_id'] for f in frames],
                         [result['steps'][1]['output_asset_id'], result['steps'][0]['output_asset_id'], result['source_asset_id']])
        self.assertEqual(len(self.gateway.requests), calls)

    def test_more_images_than_milestones_keeps_the_requested_budget_until_endpoint(self):
        self.reverse(count=5)
        result = self.until('completed')
        self.assertEqual(policy.generated(result), 5)
        self.assertEqual(len(self.comfy.submitted), 5)
        self.assertEqual(len(self.prompt_calls()), 5)
        self.assertEqual([s['action']['through_milestone'] for s in result['steps']], [1, 2, 2, 2, 3])
        self.assertIsNone(result['warning'])

    def test_rejected_endpoint_is_not_mistaken_for_success(self):
        self.gateway.early_at = 1
        self.gateway.verdict = 'unusable'
        self.reverse()
        self.until('reviewing')
        self.journeys.advance(self.journey_id)
        result = self.current_journey()
        self.assertEqual(result['status'], 'paused')
        self.assertEqual(result['steps'][-1]['review']['assessment'], 'unusable')
        self.assertNotIn('completion_reason', result)
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_old_ready_checkpoint_drops_its_noop_without_any_extra_call(self):
        self.gateway.early_at = 2
        self.reverse()
        project = self.until('completed')
        project.update(status='paused', phase='ready', pause_requested=True, next_action=action(3))
        project.pop('completion_reason')
        self.journey_store.save(project)
        calls = len(self.gateway.requests)
        self.resume_journey()
        self.journeys.advance(self.journey_id)
        current = self.current_journey()
        self.assertEqual(current['status'], 'completed')
        self.assertIsNone(current['next_action'])
        self.assertEqual(len(current['steps']), 2)
        self.assertEqual(len(self.gateway.requests), calls)
        self.assertEqual(len(self.comfy.submitted), 2)

    def test_old_planning_checkpoint_with_empty_ground_finishes_without_a_new_render(self):
        self.gateway.early_at = 2
        self.reverse()
        project = self.until('completed')
        project.update(status='paused', phase='planning', pause_requested=True, next_action=None)
        project.pop('completion_reason')
        self.journey_store.save(project)
        self.resume_journey()
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()['status'], 'completed')
        self.assertEqual(len(self.comfy.submitted), 2)
        self.assertEqual(len(self.prompt_calls()), 2)
