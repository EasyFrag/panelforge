"""User-run V1/V2 regressions. All model and image gateways are fakes."""
from copy import deepcopy
import hashlib
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.application import image_journey_policies as policies
from panelforge.application import image_journey_prompting as v1
from panelforge.application import image_journey_edit_prompting as manual_v1
from panelforge.application import image_journey_v2_prompting as v2
from panelforge.application.image_journeys import JourneyConflict
from panelforge.domain import image_journeys as policy
from panelforge.domain.image_journey_masks import VERSION as MASK_OPERATION
from panelforge.features.lab.image_journeys_web import image_journeys_router
from test_image_journeys import ImageJourneyFixture
import test_image_journey_edits as manual_tests
from test_qwen_edit import png


class ImageJourneyVersionsTest(ImageJourneyFixture):
    def test_new_default_v2_and_explicit_v1_survive_idempotent_creation(self):
        default = self.create_journey(journey_version=None)
        self.assertEqual(default['journey_version'], '2')
        self.assertFalse(default['auto_mask'])
        self.assertEqual(self.create_journey(journey_version='2'), default)
        with self.assertRaises(JourneyConflict):
            self.create_journey(journey_version='1')
        old = self.create_journey(command='v1', journey_version='1')
        self.assertEqual(self.create_journey(command='v1', journey_version=None), old)
        self.assertEqual(self.gateway.requests, [])

    def test_invalid_version_is_rejected_before_assets_or_model_calls(self):
        for value in ('3', '', 2, True, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.create_journey(journey_version=value)
        self.assertEqual(self.journeys.list(), [])
        self.assertEqual(self.gateway.requests, [])

    def test_legacy_read_and_creation_retry_keep_original_fingerprint_and_v1(self):
        project = self.create_journey(count=1)
        project.pop('journey_version')
        project.pop('journey_direction')
        config = policy.configuration(project['intention'], 1, 'progression-vision', 'minimax-prompter')
        config['auto_mask'] = False
        project['creation_key'] = policy.fingerprint(dict(config=config, source=hashlib.sha256(png()).hexdigest()))
        self.journey_store.save(project)
        path = self.journey_store._path(self.journey_id)
        before = path.read_bytes()
        self.journeys = self.new_service()
        self.assertEqual(self.journeys.public(self.current_journey())['journey_version'], '1')
        self.assertEqual(self.create_journey(count=1, journey_version=None), project)
        self.assertEqual(self.create_journey(count=1, journey_version='1'), project)
        self.assertEqual(path.read_bytes(), before)
        with self.assertRaises(JourneyConflict):
            self.create_journey(count=1, journey_version='2')
        self.until('completed')
        self.assertTrue(all(r.operation_id == v1.OPERATION for r in self.progression_calls()))
        self.assertIn('Les ouvriers, outils en action', self.prompt_calls()[0].user_prompt)

    def test_v2_keeps_image_budget_routes_prompt_and_reviews_last_result(self):
        self.create_journey(journey_version='2')
        self.until('queueing')
        # A service reload preserves the V2 decision and already prepared prompt.
        self.journeys = self.new_service()
        result = self.until('completed')
        self.assertEqual(len(result['steps']), 2)
        self.assertEqual(len(self.comfy.submitted), 2)
        self.assertEqual(len(self.prompt_calls()), 2)
        self.assertEqual(len(self.progression_calls()), 3)
        self.assertTrue(all(r.operation_id == v2.OPERATION for r in self.progression_calls()))
        self.assertTrue(all(c['journey_version'] == '2' and c['policy_version'] == v2.VERSION for c in result['analyses']))
        self.assertTrue(all(s['journey_version'] == '2' and s['review'] for s in result['steps']))
        self.assertFalse(json.loads(self.progression_calls()[0].user_prompt)['reviewing_result'])
        final = json.loads(self.progression_calls()[-1].user_prompt)
        self.assertTrue(final['reviewing_result'])
        self.assertEqual(final['remaining_images'], 0)
        for call in self.prompt_calls():
            draft = json.loads(call.user_prompt)['NEW REQUEST']
            self.assertIn('Déplacer la personne vers la droite', draft)
            self.assertNotIn('seront préparés dans une vidéo ultérieure', draft)
        self.assertTrue(all(s['settings']['steps'] == 18 and s['settings']['reference_mode'] == 'native'
                            for s in result['steps']))
        self.assertFalse(any(r.operation_id == MASK_OPERATION for r in self.gateway.requests))

    def test_v2_intended_motion_reaches_optional_mask_with_the_construction_action(self):
        self.create_journey(count=1, journey_version='2', auto_mask=True, mask_model_id='qwen-mask')
        self.until('protecting')
        action = deepcopy(self.current_journey()['steps'][0]['action'])
        self.journeys.advance(self.journey_id)
        call = next(r for r in self.gateway.requests if r.operation_id == MASK_OPERATION)
        self.assertEqual(json.loads(call.user_prompt)['action'], action)
        self.assertIn('Déplacer la personne', action['change'])
        self.assertEqual(call.model_id, 'qwen-mask')
        self.assertEqual(self.current_journey()['phase'], 'reviewing')
        self.assertEqual(len(self.comfy.submitted), 1)

    def test_v2_similar_review_still_continues_and_exports_selected_states(self):
        self.gateway.assessment = 'similar'
        self.create_journey(journey_version='2')
        result = self.until('completed')
        ids = [s['id'] for s in result['steps']]
        calls = len(self.gateway.requests)
        exported = self.journeys.prepare_transitions(self.journey_id, frame_ids=ids)
        target = self.transitions.get(exported['project_id'])
        self.assertEqual([f['asset_id'] for f in target['frames']], [s['output_asset_id'] for s in result['steps']])
        self.assertEqual(len(target['transitions']), 1)
        self.assertEqual(len(self.gateway.requests), calls)

    def test_policies_keep_v1_and_remove_conflicting_bans_only_in_v2(self):
        self.assertIs(policies.progression({}), v1)
        self.assertIs(policies.manual({}), manual_v1)
        step = dict(destination='Deck', action=dict(change='Ajouter un deck.', preserve='Le cadrage.'))
        self.assertEqual(policies.edit_request(step), v1.edit_request(step))
        self.assertIn('rhythm belong to a later video workshop', v1.SYSTEM)
        self.assertIn('Do not add workers', manual_v1.PLAN_SYSTEM)
        self.assertNotIn('rhythm belong to a later video workshop', v2.SYSTEM)
        self.assertNotIn('Do not add workers', v2.PLAN_SYSTEM)
        self.assertIn('Background motion alone does not satisfy construction progress', v2.SYSTEM)
        self.assertIn('EARLIER -> RESULT -> LATER', v2.PLAN_SYSTEM)
        self.assertIn('never to restore original people/vehicle positions', v2.REVIEW_SYSTEM)

    def test_http_defaults_validation_and_resume_cannot_switch_version(self):
        app = FastAPI()
        app.include_router(image_journeys_router(self.journeys))
        prefix = '/api/image-lab/journeys'
        with TestClient(app) as client:
            self.assertEqual(client.get(prefix + '/spec').json()['default_journey_version'], '2')
            data = dict(command='api', count='1', progression_model_id='vision', prompt_model_id='prompter')
            files = {'source_image': ('start.png', png(), 'image/png')}
            invalid = client.post(prefix + '/projects', data={**data, 'journey_version': '3'}, files=files)
            self.assertEqual(invalid.status_code, 422)
            for value in (None, '1', '2'):
                body = {**data, 'command': 'api-' + str(value)}
                if value is not None:
                    body['journey_version'] = value
                response = client.post(prefix + '/projects', data=body, files=files)
                self.assertEqual(response.status_code, 201, response.text)
                project = response.json()['project']
                self.assertEqual(project['journey_version'], value or '2')
                url = prefix + '/projects/' + project['id']
                paused = client.post(url + '/pause').json()['project']
                resume = dict(version=paused['version'], command='resume', intention='Ajouter un deck.',
                              progression_model_id='vision', prompt_model_id='prompter')
                denied = client.post(url + '/resume', json={**resume, 'journey_version': '1'})
                self.assertEqual(denied.status_code, 422)
                resumed = client.post(url + '/resume', json=resume)
                self.assertEqual(resumed.status_code, 202, resumed.text)
                self.assertEqual(resumed.json()['project']['journey_version'], value or '2')
            self.assertEqual(self.gateway.requests, [])


class ImageJourneyV2ManualTest(ImageJourneyFixture):
    start_operation = manual_tests.ImageJourneyEditsTest.start_operation
    operation = manual_tests.ImageJourneyEditsTest.operation
    render_operation = manual_tests.ImageJourneyEditsTest.render_operation
    operation_until = manual_tests.ImageJourneyEditsTest.operation_until

    def setUp(self):
        super().setUp()
        self.gateway = manual_tests.EditGateway()
        self.journeys.gateway = self.minimax.gateway = self.gateway

    def test_v2_insert_uses_both_neighbors_and_keeps_all_existing_states(self):
        self.create_journey(journey_version='2')
        original = deepcopy(self.until('completed')['steps'])
        op = self.start_operation('insert', after_frame_id=original[0]['id'], before_frame_id=original[1]['id'],
                                  intention='Le deck seul, avant la porte.')
        self.assertEqual(op['journey_version'], '2')
        self.assertEqual(op['source_asset_id'], original[1]['output_asset_id'])
        self.operation_until('completed')
        result = self.current_journey()
        self.assertEqual(result['steps'], original)
        self.assertEqual(result['count'], 2)
        self.assertEqual(result['manual_steps'][0]['journey_version'], '2')
        plan = next(r for r in self.gateway.requests if r.operation_id == v2.PLAN_OPERATION)
        self.assertEqual(len(plan.images), 2)
        self.assertEqual([i.content for i in plan.images], [self.assets.read_bytes(s['output_asset_id']) for s in original])
        review = next(r for r in self.gateway.requests if r.operation_id == v2.REVIEW_OPERATION)
        self.assertEqual(len(review.images), 3)
        self.assertTrue(all(c['journey_version'] == '2' for c in self.operation()['analyses']))
        self.assertEqual(len(self.comfy.submitted), 3)
        draft = json.loads(self.prompt_calls()[-1].user_prompt)['NEW REQUEST']
        self.assertIn('Déplacer la personne', draft)

    def test_v2_append_review_retry_keeps_version_prompt_and_generated_image(self):
        self.create_journey(count=1, journey_version='2')
        self.until('completed')
        self.start_operation()
        self.operation_until('reviewing')
        prompts, renders = len(self.prompt_calls()), len(self.comfy.submitted)
        self.gateway.bad_manual_review = True
        self.journeys.edits.advance(self.journey_id)
        self.assertEqual(self.operation()['status'], 'paused')
        self.gateway.bad_manual_review = False
        self.journeys = self.new_service()
        self.journeys.edits.control(self.journey_id, self.operation()['id'], action='resume')
        self.operation_until('completed')
        self.assertEqual(self.operation()['journey_version'], '2')
        self.assertEqual(len(self.prompt_calls()), prompts)
        self.assertEqual(len(self.comfy.submitted), renders)
        self.assertEqual(self.current_journey()['status'], 'completed')
        self.assertTrue(all(c['policy_version'] == v2.VERSION for c in self.operation()['analyses']))
