"""User-run realistic fit-out regressions, using only fake model and render gateways."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application import image_journey_policies as policies
from panelforge.application import image_journey_realistic_prompting as realistic
from panelforge.application import image_journey_reference_prompting as references
from panelforge.application.image_journey_reverse_prompting import REVERSE_POLICIES
from panelforge.application.image_journeys import JourneyConflict
from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.domain import image_journeys as policy
from panelforge.domain.minimax_edit import journey_child_id
from panelforge.features.lab.image_journeys_web import image_journeys_router
from panelforge.infrastructure.presets.minimax_edit import load_minimax_edit_workflow
from test_image_journeys import ImageJourneyFixture
import test_image_journey_edits as manual_tests
from test_qwen_edit import png


class RealisticGateway(manual_tests.EditGateway):
    endpoint_early = False

    def stream(self, request):
        if request.operation_id not in {realistic.OPERATION, realistic.PLAN_OPERATION, realistic.REVIEW_OPERATION}:
            yield from super().stream(request)
            return
        self.requests.append(request)
        context = json.loads(request.user_prompt)
        if request.operation_id == realistic.PLAN_OPERATION:
            value = dict(title='Ossature seule', change='Remettre uniquement l’ossature en bois, sans personnages.',
                         preserve='La géométrie et la roche de la grotte, le cadrage.')
        elif request.operation_id == realistic.REVIEW_OPERATION:
            value = dict(assessment='usable', observation='L’ossature demandée est visible dans la même grotte.')
        else:
            total, remaining = context['total_new_images'], context['remaining_images']
            milestones = context['milestones'] or ['Dépose des équipements', 'Dépose des parois et couches', 'Lieu brut']
            done = (total - remaining) * len(milestones) // total
            if self.endpoint_early and context['reviewing_result']:
                done = len(milestones)
            value = dict(destination=context['destination'] or context['user_intention'] or 'Grotte vide, humide et austère.',
                milestones=milestones, completed_milestones=done, summary='Le lieu reste intact, les couches sont retirées.',
                observation='La grotte conserve sa géométrie.', assessment='usable' if context['reviewing_result'] else 'initial',
                next_action=None if not remaining or done == len(milestones) else dict(title='Dépose visible',
                    change='Retirer une couche de l’aménagement en conservant la grotte, sans personnages.',
                    preserve='Roche, proportions et cadrage de la grotte.',
                    through_milestone=(total - remaining + 1) * len(milestones) // total))
        yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED,
            result=CompletionResult(request.model_id, json.dumps(value), call_id='realistic-call'))


class ImageJourneyRealisticTest(ImageJourneyFixture):
    start_operation = manual_tests.ImageJourneyEditsTest.start_operation
    operation = manual_tests.ImageJourneyEditsTest.operation
    render_operation = manual_tests.ImageJourneyEditsTest.render_operation
    operation_until = manual_tests.ImageJourneyEditsTest.operation_until

    def setUp(self):
        super().setUp()
        root = Path(__file__).resolve().parents[1]
        self.minimax.workflow = load_minimax_edit_workflow(root / 'workflows/image.edit/minimax-h3-still/1.3.0')
        self.gateway = RealisticGateway()
        self.journeys.gateway = self.minimax.gateway = self.gateway

    def real(self, **changes):
        values = dict(command='realistic', content=png(), intention='', count=3, journey_preset='realistic',
                      journey_version='2', progression_model_id='progression-vision', prompt_model_id='minimax-prompter')
        result = self.journeys.create(**{**values, **changes})
        self.journey_id = result['id']
        return result

    def test_saved_preset_idempotency_and_legacy_fingerprint(self):
        old = self.create_journey(command='legacy', count=1)
        self.assertNotIn('journey_preset', old)
        path = self.journey_store._path(old['id'])
        before = path.read_bytes()
        self.assertEqual(self.journeys.public(old)['journey_preset'], 'miniature')
        retried = self.journeys.create(command='legacy', content=png(), intention='Aménager la cave', count=1,
            journey_version='1', journey_preset='miniature', progression_model_id='progression-vision', prompt_model_id='minimax-prompter')
        self.assertEqual(retried, old)
        self.assertEqual(path.read_bytes(), before)
        real = self.real()
        self.assertEqual(real['journey_direction'], 'reverse')
        self.assertEqual(self.real(journey_preset=None, journey_version=None), real)
        with self.assertRaises(JourneyConflict):
            self.real(journey_preset='miniature')
        self.assertEqual(self.gateway.requests, [])

    def test_invalid_preset_or_forward_realism_is_rejected_before_asset_preparation(self):
        with patch.object(self.minimax.images, 'normalize_source', wraps=self.minimax.images.normalize_source) as normalize:
            for preset in ('', 'unknown', 1, True, [], {}):
                with self.subTest(preset=preset), self.assertRaises(ValueError):
                    self.real(journey_preset=preset)
            with self.assertRaisesRegex(ValueError, 'À rebours'):
                self.real(journey_direction='forward')
            normalize.assert_not_called()
        self.assertEqual(self.journeys.list(), [])
        self.assertEqual(self.gateway.requests, [])

    def test_one_three_and_five_images_use_realistic_policy_without_extra_calls(self):
        for count in (1, 3, 5):
            with self.subTest(count=count):
                start_calls, start_renders = len(self.gateway.requests), len(self.comfy.submitted)
                initial = self.real(count=count, command='budget-' + str(count))
                result = self.until('completed')
                calls = self.gateway.requests[start_calls:]
                progression = [r for r in calls if r.operation_id == realistic.OPERATION]
                self.assertEqual(len(progression), count + 1)
                self.assertEqual(len(self.comfy.submitted) - start_renders, count)
                self.assertEqual(len(calls), 2 * count + 1)
                self.assertEqual(result['count'], count)
                self.assertEqual(result['destination'], 'Grotte vide, humide et austère.')
                self.assertIsNone(result['next_action'])
                self.assertEqual(json.loads(progression[0].user_prompt)['desired_initial_state'], '')
                self.assertEqual(json.loads(progression[-1].user_prompt)['remaining_images'], 0)
                self.assertTrue(all(r.system_prompt == realistic.SYSTEM for r in progression))
                for index, step in enumerate(result['steps']):
                    self.assertEqual(step['journey_preset'], 'realistic')
                    self.assertEqual(step['finished_reference_asset_id'], initial['source_asset_id'])
                    self.assertEqual(step['settings']['steps'], 18)
                    self.assertEqual(step['settings']['reference_mode'], 'native')
                    self.assertEqual(step['output_dimensions'], initial['source_dimensions'])
                    self.assertIn(realistic.IMAGE_RULES, step['prompt'])
                    self.assertEqual(step['review']['assessment'], 'usable')
                    child = self.minimax.get(journey_child_id(step['id']))
                    self.assertEqual(child['journey_preset'], 'realistic')
                    attempt = child['stages'][0]['attempts'][-1]
                    expected = [initial['source_asset_id']] if not index else [
                        result['steps'][index - 1]['output_asset_id'], initial['source_asset_id']]
                    self.assertEqual([i['asset_id'] for i in attempt['context']['render_inputs']], expected)
                    if index:
                        self.assertIn(realistic.REFERENCE_ROLES, step['prompt'])
                        self.assertNotIn(references.ROLES, step['prompt'])

    def test_resume_and_reopen_keep_preset_and_only_revision_changes_initial_state(self):
        self.real(intention='Arbre intact, feuilles au sol.')
        self.until('queueing')
        before = self.journeys.pause(self.journey_id)
        self.journeys = self.new_service()
        self.assertEqual(self.journeys.public(self.current_journey())['journey_preset'], 'realistic')
        resumed = self.resume_journey()
        self.assertEqual(resumed['intent_revision'], before['intent_revision'])
        self.assertEqual(resumed['steps'], before['steps'])
        self.journeys.pause(self.journey_id)
        revised = self.resume_journey(intention='Arbre intact, sol couvert de mousse.')
        self.assertEqual(revised['journey_preset'], 'realistic')
        self.assertEqual(revised['intent_revision'], before['intent_revision'] + 1)
        self.assertEqual(revised['phase'], 'planning')
        self.assertEqual(len(self.comfy.submitted), 0)

    def test_realistic_policies_override_life_version_without_changing_miniature(self):
        for version in ('1', '2'):
            record = dict(journey_preset='realistic', journey_direction='reverse', journey_version=version)
            self.assertIs(policies.progression(record), realistic)
            self.assertIs(policies.manual(record), realistic)
            record.pop('journey_preset')
            self.assertIs(policies.progression(record), REVERSE_POLICIES[version])
        self.assertIn('no workers, people, crowds, hands', realistic.SYSTEM)
        self.assertIn('With three outputs prefer major transformations', realistic.SYSTEM)
        self.assertIn('five or more', realistic.SYSTEM)
        self.assertIn('Do not default to flat ground', realistic.SYSTEM)
        self.assertNotIn('visible but discreet background', realistic.SYSTEM)
        self.assertIn('visible but discreet background', REVERSE_POLICIES['2'].SYSTEM)

    def test_insert_and_append_inherit_preset_without_rewriting_saved_images(self):
        initial = self.real(count=3)
        result = self.until('completed')
        before = deepcopy(result['steps'])
        for kind in ('insert', 'append'):
            anchors = dict(after_frame_id=before[0]['id'], before_frame_id=before[1]['id']) if kind == 'insert' else {}
            operation = self.start_operation(kind, intention='Ossature seule sans isolant.', **anchors)
            self.assertEqual(operation['journey_preset'], 'realistic')
            self.assertEqual(operation['finished_reference_asset_id'], initial['source_asset_id'])
            completed = self.operation_until('completed')
            self.assertIn(realistic.IMAGE_RULES, completed['prompt'])
            self.assertEqual(self.current_journey()['steps'], before)
        manual_calls = [r for r in self.gateway.requests if r.operation_id == realistic.PLAN_OPERATION]
        self.assertEqual(len(manual_calls), 2)
        self.assertEqual(json.loads(manual_calls[0].user_prompt)['order'], 'finished_to_initial')
        self.assertTrue(all(r.system_prompt == realistic.PLAN_SYSTEM for r in manual_calls))

    def test_export_preserves_selected_construction_order_and_realistic_metadata(self):
        initial = self.real()
        result = self.until('completed')
        selected = ['source', result['steps'][0]['id'], result['steps'][-1]['id']]
        export = self.journeys.prepare_transitions(self.journey_id, frame_ids=selected, frame_order='reverse_generation')
        frames = self.transitions.get(export['project_id'])['frames']
        self.assertEqual([f['asset_id'] for f in frames], [result['steps'][-1]['output_asset_id'],
                         result['steps'][0]['output_asset_id'], initial['source_asset_id']])
        self.assertEqual(frames[-1]['label'], 'Aménagement terminé')
        self.assertTrue(all(f['origin']['journey_preset'] == 'realistic' for f in frames))
        self.assertEqual(self.journeys.prepare_transitions(self.journey_id, frame_ids=selected,
                         frame_order='reverse_generation'), export)

    def test_early_initial_state_stops_without_rendering_the_finished_scene_again(self):
        self.gateway.endpoint_early = True
        self.real(count=5)
        result = self.until('completed')
        self.assertEqual(result['completion_reason'], 'reverse_endpoint')
        self.assertEqual(len(result['steps']), 1)
        self.assertEqual(len(self.comfy.submitted), 1)
        self.assertIn('État de départ atteint après 1 images sur 5', result['warning'])
        self.assertNotIn('Terrain dégagé', result['warning'])

    def test_reference_compiler_keeps_roles_no_people_and_rejects_invented_tags(self):
        single = dict(mode='edit', guide=None, source_asset_id='current', render_inputs=[
            dict(id='source', tag='<Picture 1>', asset_id='current')])
        pair = deepcopy(single)
        pair['render_inputs'].append(dict(id='journey-finished', tag='<Picture 2>', asset_id='finished'))
        raw = json.dumps(dict(message='Retirer le mobilier.', prompt='Edit <Picture 1> to remove the furniture.'))
        _, one = realistic.decode_prompt(raw, single)
        _, two = realistic.decode_prompt(raw, pair)
        self.assertIn(realistic.IMAGE_RULES, one)
        self.assertNotIn('<Picture 2>', one)
        self.assertIn(realistic.REFERENCE_ROLES, two)
        for prompt in ('Edit the cave.', 'Edit <Picture 1> with <Picture 3>.'):
            with self.subTest(prompt=prompt), self.assertRaises(ValueError):
                realistic.decode_prompt(json.dumps(dict(message='Essai', prompt=prompt)), pair)
        self.assertNotIn(realistic.IMAGE_RULES, references.decode(raw, pair)[1])

    def test_http_advertises_preset_and_locks_it_during_resume(self):
        app = FastAPI()
        app.include_router(image_journeys_router(self.journeys))
        prefix = '/api/image-lab/journeys'
        with TestClient(app) as client:
            self.assertIn('realistic', client.get(prefix + '/spec').json()['journey_presets'])
            data = dict(command='api-real', journey_preset='realistic', count=3,
                        progression_model_id='vision', prompt_model_id='writer')
            files = {'source_image': ('finished.png', png(), 'image/png')}
            for values in ({'journey_preset': 'invalid'}, {'journey_direction': 'forward'}):
                self.assertEqual(client.post(prefix + '/projects', data={**data, **values}, files=files).status_code, 422)
            response = client.post(prefix + '/projects', data=data, files=files)
            self.assertEqual(response.status_code, 201, response.text)
            project = response.json()['project']
            self.assertEqual((project['journey_preset'], project['journey_direction'], project['intention']),
                             ('realistic', 'reverse', ''))
            url = prefix + '/projects/' + project['id']
            paused = client.post(url + '/pause').json()['project']
            resume = dict(version=paused['version'], command='resume', intention='Grotte vide.',
                          progression_model_id='vision', prompt_model_id='writer')
            self.assertEqual(client.post(url + '/resume', json={**resume, 'journey_preset': 'miniature'}).status_code, 422)
            result = client.post(url + '/resume', json=resume)
            self.assertEqual(result.status_code, 202, result.text)
            self.assertEqual(result.json()['project']['journey_preset'], 'realistic')
        self.assertEqual(self.gateway.requests, [])
