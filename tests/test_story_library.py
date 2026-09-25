"""User-run library regressions. No real model, rendering, or service worker."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from panelforge.application.stories import StoryService
from panelforge.application.story_library import StoryLibraryService, writing_progress
from panelforge.domain.episodes import initial_episode, scene_inputs, fingerprint, effective_video_setup
from panelforge.domain.stories import validate_scenario
from panelforge.domain.story_library import LibraryConflict, empty_metadata, memberships, metadata_change
from panelforge.features.lab.story_library_web import story_library_router
from panelforge.infrastructure.storage.stories import LocalStoryStore
from panelforge.infrastructure.storage.episodes import LocalEpisodeStore
from tests.test_episodes import SCENARIO


def sid(char):
    return 'story-' + char * 32


def forbidden(*args, **kwargs):
    raise AssertionError('The library must not call a live service or start/reconcile work')


class StoryLibraryTest(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.store = LocalStoryStore(tmp.name)
        self.episode_store = LocalEpisodeStore(tmp.name)
        self.renders = {}
        def render_get(key):
            if key not in self.renders:
                raise FileNotFoundError(key)
            return self.renders[key]
        self.stories = NS(store=self.store, _normalize=StoryService._normalize, _active={},
                          followups=NS(_active={}), get=forbidden, start=forbidden)
        self.episodes = NS(store=self.episode_store, render=NS(projects=NS(get=render_get)),
                           krea=NS(projects=NS(get=forbidden)), dlss=None, qwen_edit=None,
                           get=forbidden, create=forbidden)
        self.library = StoryLibraryService(self.stories, self.episodes)

    def story(self, char='a', parent=None, title='Glow up'):
        return self.store.save(dict(project_id=sid(char), title=title, brief='Une transformation.',
            parent_story_id=parent, narrative_format='short', clip_seconds=10, scene_count=1,
            dialogue_language='French', document=dict(scenario=validate_scenario(deepcopy(SCENARIO)), concepts=[]),
            revisions=[dict(revision=1)], job=None, turns=[]))

    def fabrication(self, story, char='a', render_id='render-current'):
        value = initial_episode(story, 'episode-' + char * 32)
        for ref in value['references']:
            ref['image_asset_id'] = 'asset-' + ref['id']
        scene = value['scenes'][0]
        scene['preparations'] = [dict(status='ready', input_hash=fingerprint(scene_inputs(value, scene)), render_project_id=render_id)]
        setup = effective_video_setup(value, scene)
        self.renders[render_id] = NS(current_prompt='Prompt', attempts=[
            NS(attempt_id='old', status='succeeded', output_asset_id='old-video', dlss=None, prompt='Prompt', settings=NS(**setup['settings'])),
            NS(attempt_id='last', status='succeeded', output_asset_id='last-video', dlss=None, prompt='Prompt', settings=NS(**setup['settings']))])
        return self.episode_store.save(value)

    def row(self, key=sid('a')):
        return next(i for g in self.library.view()['groups'] for i in g['items'] if i['project_id'] == key)

    def test_explicit_parent_groups_branches_without_using_similar_titles(self):
        a = self.story(); b = self.story('b', a['project_id'], 'Le jus acide')
        c = self.story('c', a['project_id'], 'Autre suite'); d = self.story('d', title='Glow up')
        links = memberships([a, b, c, d], empty_metadata())
        self.assertEqual(links[b['project_id']], (a['project_id'], 2))
        self.assertEqual(links[c['project_id']], (a['project_id'], 2))
        self.assertEqual(links[d['project_id']], (d['project_id'], 1))

    def test_favorite_rename_and_trash_do_not_modify_narrative_or_media(self):
        a = self.story(); self.story('b', a['project_id']); self.fabrication(a)
        before = {p: p.read_bytes() for p in self.root.rglob('*.json')}
        self.library.update('group', a['project_id'], expected_revision=0, title='GLOW UP', favorite=True)
        self.library.update('project', a['project_id'], expected_revision=1, trashed=True)
        self.assertEqual(self.store.list()[0]['project_id'], sid('b'))
        self.assertEqual(self.row(sid('b'))['episode_number'], 2)
        self.assertTrue(self.row()['trashed'])
        for path, content in before.items(): self.assertEqual(path.read_bytes(), content)
        self.library.update('project', a['project_id'], expected_revision=2, trashed=False)
        self.assertFalse(self.row()['trashed'])
        self.assertEqual(self.library.view()['groups'][0]['title'], 'GLOW UP')
        self.assertTrue(self.library.view()['groups'][0]['favorite'])

    def test_reorganization_moves_only_the_selected_entry(self):
        a = self.story(); b = self.story('b', a['project_id']); self.story('c', b['project_id']); d = self.story('d')
        self.library.update('project', b['project_id'], expected_revision=0, group_id=d['project_id'], episode_number=7)
        view = self.library.view()
        group = next(g for g in view['groups'] if g['id'] == d['project_id'])
        self.assertIn(sid('b'), [i['project_id'] for i in group['items']])
        self.assertEqual(self.row(sid('b'))['episode_number'], 7)
        original = next(g for g in view['groups'] if g['id'] == a['project_id'])
        self.assertIn(sid('c'), [i['project_id'] for i in original['items']])
        self.assertEqual(self.row(sid('c'))['episode_number'], 3)

    def test_current_fabrication_and_last_attempt_are_counted_once(self):
        a = self.story(); value = self.fabrication(a)
        old = deepcopy(value); old.update(episode_id='episode-'+'b'*32, source_hash='obsolete', created_at='9999')
        old['scenes'][0]['preparations'] = []
        self.episode_store.save(old)
        view = self.row(); counts = view['variants'][0]['counts']
        self.assertEqual((counts['scenes'], counts['videos'], counts['dlss']), (1, 1, 0))
        self.assertEqual(view['variants'][0]['fabrication_ids'], [value['episode_id']])
        self.renders['render-current'].attempts.append(NS(status='succeeded', output_asset_id='old-dlss', dlss=NS(root_attempt_id='old')))
        self.assertEqual(self.row()['variants'][0]['counts']['dlss'], 0)
        self.renders['render-current'].attempts.append(NS(status='succeeded', output_asset_id='new-dlss', dlss=NS(root_attempt_id='last')))
        self.assertEqual(self.row()['variants'][0]['counts']['dlss'], 1)

    def test_stale_reference_or_duration_does_not_count_as_current_video(self):
        a = self.story(); value = self.fabrication(a)
        value['scenes'][0]['duration'] = 8
        self.episode_store.save(value)
        c = self.row()['variants'][0]['counts']
        self.assertEqual((c['videos'], c['stale']), (0, 1))
        value['scenes'][0]['duration'] = 10
        value['references'][0]['image_asset_id'] = 'replacement'
        self.episode_store.save(value)
        self.assertEqual(self.row()['variants'][0]['counts']['videos'], 0)

    def test_queued_video_is_planned_and_not_counted_as_running_or_done(self):
        a = self.story(); self.fabrication(a)
        self.renders['render-current'].attempts[-1].status = 'queued'
        item = self.row()
        self.assertEqual(item['stages']['videos'], 'planned')
        self.assertTrue(item['active'])  # Locked in the library while a task is queued.
        self.assertEqual(item['variants'][0]['counts']['videos'], 0)
        self.assertFalse(item['variants'][0]['counts']['active'])

    def test_translation_is_another_language_not_another_episode(self):
        a = self.story(); value = self.fabrication(a)
        english = deepcopy(value); english.update(episode_id='episode-'+'c'*32, dialogue_language='English')
        english['localization'] = dict(source_episode_id=value['episode_id'], language='English', group_id='language-test')
        english['scenes'][0]['localization'] = dict(status='ready')
        self.episode_store.save(english)
        rows = self.library.view()['groups'][0]['items']
        self.assertEqual(len(rows), 1)
        self.assertEqual([v['language'] for v in rows[0]['variants']], ['French', 'English'])
        self.assertEqual([v['counts']['videos'] for v in rows[0]['variants']], [1, 1])

    def test_active_historical_render_prevents_trash_and_keeps_files(self):
        a = self.story(); self.fabrication(a, render_id='current')
        old = self.fabrication(a, char='b', render_id='historical')
        self.renders['historical'].attempts[-1].status = 'queued'
        with self.assertRaises(LibraryConflict):
            self.library.update('project', a['project_id'], expected_revision=0, trashed=True)
        self.assertEqual(self.store.library_metadata()['revision'], 0)
        self.assertEqual(self.episode_store.get(old['episode_id'])['story_id'], a['project_id'])

    def test_reading_library_is_read_only_and_missing_old_media_can_be_trashed(self):
        a = self.story(); self.fabrication(a)
        self.renders.clear()
        before = {p: p.read_bytes() for p in self.root.rglob('*.json')}
        row = self.row(); self.assertIsNotNone(row['progress_error'])
        self.assertFalse(row['active'])
        self.assertFalse((self.store.root / 'library.json').exists())
        for p, content in before.items(): self.assertEqual(p.read_bytes(), content)
        self.library.update('project', a['project_id'], expected_revision=0, trashed=True)
        self.assertTrue(self.row()['trashed'])

    def test_stale_revision_and_invalid_organization_are_rejected(self):
        self.story()
        self.library.update('group', sid('a'), expected_revision=0, favorite=True)
        with self.assertRaises(LibraryConflict):
            self.library.update('project', sid('a'), expected_revision=0, trashed=True)
        with self.assertRaises(ValueError):
            metadata_change(self.store.library_metadata(), self.store.catalog()['items'], kind='project', target=sid('a'), values={'group_id':sid('a')})

    def test_manual_review_is_not_an_approval_and_internal_sequences_are_not_episodes(self):
        a = self.story(); a.update(narrative_format='long', long_options={'delivery':'continuous','unit_count':3})
        a['document']['series_outline'] = {'episodes':[{'id':'episode-1'},{'id':'episode-2'},{'id':'episode-3'}]}
        b = self.story('b', a['project_id'])
        self.assertEqual(memberships([a,b], empty_metadata())[b['project_id']][1], 2)
        a['document']['reviews'] = {'outline':{'source_hash':'arc'},'episode-1':{'source_hash':'unit'}}
        a['workflow'] = {'mode':'manual','status':'awaiting_author','wait_target':'outline','approvals':{}}
        with patch('panelforge.application.story_library.narrative.is_v2', return_value=True), patch(
                'panelforge.application.story_library.narrative.status', return_value={'outline_reviewed':True,'units':{'episode-1':{'ready':True,'written':True}}}):
            self.assertEqual(writing_progress(a)['story'], 'approval')
            a['workflow'].update(wait_target='episode-1', approvals={'outline':'arc'})
            self.assertEqual(writing_progress(a)['scenario'], 'approval')
            a['workflow'].update(status='ready')
            self.assertEqual(writing_progress(a)['scenario'], 'done')

    def test_api_contract_and_conflict_status(self):
        self.story(); app = FastAPI(); app.include_router(story_library_router(self.stories, self.episodes))
        client = TestClient(app)
        self.assertEqual(client.get('/api/stories/library').status_code, 200)
        url = '/api/stories/library/groups/' + sid('a')
        self.assertEqual(client.patch(url, json={'expected_revision':0,'favorite':True}).status_code, 200)
        self.assertEqual(client.patch(url, json={'expected_revision':0,'favorite':False}).status_code, 409)
        self.assertEqual(client.patch(url, json={'expected_revision':1,'favorite':'yes'}).status_code, 422)
        self.assertEqual(client.patch(url, json={'expected_revision':1,'unknown':True}).status_code, 422)
