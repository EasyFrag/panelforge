"""User-run selection regressions: synthetic contracts and fake LLM/render gateways."""
from copy import deepcopy
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from panelforge.domain import image_journeys as policy
from panelforge.features.lab.image_journeys_web import image_journeys_router
from test_image_journeys import ImageJourneyFixture


def sample_project():
    def step(identity):
        return dict(id=identity, source_asset_id='asset-source', output_asset_id='asset-' + identity,
                    action=dict(title=identity, change='Construire ' + identity),
                    review=dict(assessment='usable', observation='État obtenu.'))
    return dict(id='journey-sample', source_asset_id='asset-source', destination='Décor terminé',
                steps=[step('first'), step('last')], manual_steps=[step('middle')],
                sequence_order=['first', 'middle', 'last'])


class JourneySelectionContractTest(unittest.TestCase):
    def test_subset_excludes_source_and_obeys_journey_order_including_insertions(self):
        project = sample_project()
        before = deepcopy(project)
        selected = policy.sequence(project, ['last', 'middle'])
        self.assertEqual([f['asset_id'] for f in selected['frames']], ['asset-middle', 'asset-last'])
        self.assertEqual([f['origin']['index'] for f in selected['frames']], [2, 3])
        self.assertEqual(project, before)

    def test_explicit_selection_can_skip_an_unavailable_image_without_exporting_it(self):
        project = sample_project()
        for review in (None, dict(assessment='unusable', observation='Image inutilisable.')):
            with self.subTest(review=review):
                project['manual_steps'][0]['review'] = review
                self.assertEqual(policy.transferable_frame_ids(project), ['source', 'first', 'last'])
                self.assertEqual(len(policy.sequence(project)['frames']), 2)  # Legacy prefix.
                selected = policy.sequence(project, ['last', 'first'])
                self.assertEqual([f['origin']['step_id'] for f in selected['frames']], ['first', 'last'])
                with self.assertRaises(ValueError):
                    policy.sequence(project, ['source', 'middle'])

    def test_invalid_selection_never_silently_exports_all_images(self):
        project = sample_project()
        for value in ([], ['source'], ['first', 'first'], 'source', ['source', 'foreign'],
                      ['source', 3], ['source', {}], ['source', 'asset-first']):
            with self.subTest(value=value), self.assertRaises(ValueError):
                policy.sequence(project, value)
        project['manual_steps'][0]['output_asset_id'] = None
        with self.assertRaises(ValueError):
            policy.sequence(project, ['source', 'middle'])

    def test_selecting_all_has_the_same_payload_as_legacy_handoff(self):
        project = sample_project()
        self.assertEqual(policy.sequence(project, list(reversed(policy.transferable_frame_ids(project)))),
                         policy.sequence(project))


    def test_reverse_order_keeps_insertions_selection_and_generation_origins(self):
        project = sample_project()
        project['journey_direction'] = 'reverse'
        before = deepcopy(project)
        selected = policy.sequence(project, ['source', 'last', 'middle'], frame_order='reverse_generation')
        self.assertEqual([f['asset_id'] for f in selected['frames']], ['asset-last', 'asset-middle', 'asset-source'])
        self.assertEqual([f['origin']['index'] for f in selected['frames']], [3, 2, 0])
        self.assertEqual(selected['frames'][-1]['label'], 'Bâtiment terminé')
        self.assertEqual(project, before)
        self.assertEqual(policy.sequence(project, frame_order='generation'), policy.sequence(project))
        project['manual_steps'][0]['review'] = None
        selected = policy.sequence(project, ['source', 'last', 'first'], frame_order='reverse_generation')
        self.assertEqual([f['asset_id'] for f in selected['frames']], ['asset-last', 'asset-first', 'asset-source'])
        with self.assertRaises(ValueError):
            policy.sequence(project, ['source', 'middle'], frame_order='reverse_generation')

    def test_invalid_order_is_rejected_without_mutation(self):
        project = sample_project()
        before = deepcopy(project)
        for value in ('construction', '', None, True, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                policy.sequence(project, ['source', 'first'], frame_order=value)
        self.assertEqual(project, before)


class JourneySelectionHandoffTest(ImageJourneyFixture):
    def test_selection_has_its_own_idempotent_export_without_touching_existing_frise(self):
        self.create_journey(count=3)
        project = self.until('completed')
        original_steps = deepcopy(project['steps'])
        calls = len(self.gateway.requests)
        renders = len(self.comfy.submitted)
        full = self.journeys.prepare_transitions(self.journey_id)
        previous = deepcopy(self.transitions.get(full['project_id']))
        ids = [project['steps'][2]['id'], project['steps'][0]['id']]
        subset = self.journeys.prepare_transitions(self.journey_id, frame_ids=ids)
        self.assertNotEqual(subset, full)
        self.assertEqual(subset, self.journeys.prepare_transitions(self.journey_id, frame_ids=list(reversed(ids))))
        target = self.transitions.get(subset['project_id'])
        self.assertEqual([f['asset_id'] for f in target['frames']],
                         [project['steps'][0]['output_asset_id'], project['steps'][2]['output_asset_id']])
        self.assertEqual(len(target['transitions']), 1)
        self.assertFalse(target['transitions'][0]['reviewed'])
        self.assertEqual(target['deliveries'], [])
        self.assertEqual(self.transitions.get(full['project_id']), previous)
        self.assertEqual(self.current_journey()['steps'], original_steps)
        self.assertEqual(len(self.gateway.requests), calls)
        self.assertEqual(len(self.comfy.submitted), renders)
        self.assertEqual(full, self.journeys.prepare_transitions(self.journey_id,
                         frame_ids=policy.transferable_frame_ids(project)))

    def test_export_order_is_idempotent_and_never_changes_generation_or_prior_exports(self):
        self.create_journey(count=3)
        project = self.until('completed')
        calls, renders = len(self.gateway.requests), len(self.comfy.submitted)
        ids = ['source', project['steps'][0]['id'], project['steps'][2]['id']]
        forward = self.journeys.prepare_transitions(self.journey_id, frame_ids=ids)
        previous = deepcopy(self.transitions.get(forward['project_id']))
        backward = self.journeys.prepare_transitions(self.journey_id, frame_ids=ids, frame_order='reverse_generation')
        self.assertNotEqual(forward, backward)
        target = self.transitions.get(backward['project_id'])
        self.assertEqual([f['asset_id'] for f in target['frames']],
                         [project['steps'][2]['output_asset_id'], project['steps'][0]['output_asset_id'], project['source_asset_id']])
        by_id = {frame['id']: frame['asset_id'] for frame in target['frames']}
        self.assertEqual([(by_id[t['left']], by_id[t['right']]) for t in target['transitions']],
                         [(project['steps'][2]['output_asset_id'], project['steps'][0]['output_asset_id']),
                          (project['steps'][0]['output_asset_id'], project['source_asset_id'])])
        self.assertEqual(backward, self.journeys.prepare_transitions(self.journey_id,
                         frame_ids=list(reversed(ids)), frame_order='reverse_generation'))
        self.assertEqual(forward, self.journeys.prepare_transitions(self.journey_id, frame_ids=ids))
        self.assertEqual(self.transitions.get(forward['project_id']), previous)
        current = self.current_journey()
        for field in ('steps', 'manual_steps', 'sequence_order', 'source_asset_id', 'current_asset_id', 'count'):
            self.assertEqual(current.get(field), project.get(field), field)
        self.assertEqual(len(self.gateway.requests), calls)
        self.assertEqual(len(self.comfy.submitted), renders)

    def test_http_rejects_invalid_ids_and_supports_legacy_and_explicit_handoffs(self):
        self.create_journey(count=2)
        project = self.until('completed')
        self.assertEqual(self.journeys.public(project)['transferable_frame_ids'],
                         ['source', *[s['id'] for s in project['steps']]])
        app = FastAPI()
        app.include_router(image_journeys_router(self.journeys))
        url = '/api/image-lab/journeys/projects/' + self.journey_id + '/transitions'
        with TestClient(app) as client:
            for body in ({}, {'frame_ids': []}, {'frame_ids': ['source']}, {'frame_ids': None},
                         {'frame_ids': 'source'}, {'frame_ids': ['source', 'source']},
                         {'frame_ids': ['source', 'foreign']}, {'frame_ids': ['source', 1]},
                         {'frame_ids': ['source', project['steps'][0]['id']], 'frame_order': 'unknown'}):
                with self.subTest(body=body):
                    self.assertEqual(client.post(url, json=body).status_code, 422)
            self.assertEqual(self.transitions.list(), [])
            ids = [s['id'] for s in project['steps']]
            response = client.post(url, json={'frame_ids': list(reversed(ids))})
            self.assertEqual(response.status_code, 200, response.text)
            exported = self.transitions.get(response.json()['project_id'])
            self.assertEqual([f['origin']['step_id'] for f in exported['frames']], ids)
            reverse = client.post(url, json={'frame_ids': ids, 'frame_order': 'reverse_generation'})
            self.assertEqual(reverse.status_code, 200, reverse.text)
            reversed_export = self.transitions.get(reverse.json()['project_id'])
            self.assertEqual([f['origin']['step_id'] for f in reversed_export['frames']], list(reversed(ids)))
            self.assertNotEqual(response.json(), reverse.json())
            legacy = client.post(url)
            self.assertEqual(legacy.status_code, 200, legacy.text)
            self.assertEqual(len(self.transitions.get(legacy.json()['project_id'])['frames']), 3)
