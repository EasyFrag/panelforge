"""User-run patch regressions; fake services and memory storage only."""
from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from uuid import uuid4
import unittest

from panelforge.application.video_factory import FactoryConflict, VideoFactoryService
from panelforge.application.video_factory_workflows import FactoryWorkflows
from panelforge.domain.video_factory import configuration, new_item
from tests.test_video_factory import MemoryStore, FakeWorkflows, DeferredThread
from tests import test_video_factory as fixtures


class FactoryTimingRetryServiceTest(unittest.TestCase):
    setUp = fixtures.FactoryServiceTest.setUp
    receive = fixtures.FactoryServiceTest.receive
    select = fixtures.FactoryServiceTest.select
    item = fixtures.FactoryServiceTest.item

    def test_retry_preserves_successes_and_clears_only_failed_attempt_timing(self):
        identity = self.receive(final=True)
        item = self.service._get(identity)
        item['status'] = 'failed'
        for stage in ('plan', 'prompt', 'video', 'social'):
            item['steps'][stage].update(status='succeeded', started_at='2026-09-26T08:00:00+00:00',
                finished_at='2026-09-26T08:00:10+00:00', output={'asset_id': 'asset-kept', 'text': stage})
        kept = deepcopy(item['steps'])
        item['steps']['dlss'].update(status='failed', error='invalid request',
            started_at='2026-09-26T08:00:11+00:00', finished_at='2026-09-26T08:00:12+00:00')
        self.service.action('retry', *self.select(identity))
        result = self.item(identity)
        for stage in ('plan', 'prompt', 'video', 'social'):
            self.assertEqual(result['steps'][stage], kept[stage])
        self.assertEqual(result['steps']['dlss']['status'], 'pending')
        self.assertIsNone(result['steps']['dlss']['started_at'])
        self.assertIsNone(result['steps']['dlss']['finished_at'])
        self.assertEqual(result['status'], 'queued')
        self.assertEqual(self.adapter.calls, [])

    def test_same_retry_action_handles_export_without_replaying_successes(self):
        identity = self.receive(final=True)
        item = self.service._get(identity)
        item['status'] = 'succeeded'
        item['steps']['video'].update(status='succeeded', output={'asset_id': 'video-kept'})
        item['delivery'] = {'status': 'failed', 'key': 'files', 'error': 'disk'}
        before = deepcopy(item['steps'])
        self.service.action('retry', *self.select(identity))
        self.assertEqual(self.item(identity)['steps'], before)
        self.assertEqual(self.item(identity)['status'], 'succeeded')
        self.assertEqual(self.item(identity)['delivery']['status'], 'queued')
        self.assertEqual(self.adapter.calls, [])

    def test_retry_selection_is_atomic_when_a_row_is_already_in_production(self):
        a, b = self.receive('a'), self.receive('b')
        self.service._get(a)['status'] = 'failed'
        self.service._get(b)['status'] = 'queued'
        before = deepcopy(self.store.value)
        with self.assertRaises(FactoryConflict):
            self.service.action('retry', *self.select(a, b))
        self.assertEqual(self.store.value, before)
        self.assertEqual(self.item(a)['status'], 'failed')

    def test_remove_supports_every_idle_state_and_keeps_external_sources(self):
        ids = []
        for status in ('preparation', 'queued', 'succeeded', 'failed', 'cancelled'):
            identity = self.receive(status)
            self.service._get(identity)['status'] = status
            ids.append(identity)
        sources = [deepcopy(self.item(identity)['source']) for identity in ids]
        self.service.action('remove', *self.select(*ids))
        self.assertEqual(self.service.snapshot()['items'], [])
        self.assertEqual(len(sources), 5)
        self.assertEqual(self.adapter.calls, [])

    def test_cancel_remove_and_resend_frees_the_episode_deduplication_key(self):
        config = configuration('ref2v')
        config['intention'] = 'Scene intent'
        entry = dict(name='Scene 1', config=config,
            source=dict(kind='episode', id='english-copy', scene_id='scene-1', index=0))
        first = self.service.receive([entry])['ids'][0]
        self.service._get(first)['status'] = 'queued'
        self.service.action('cancel', *self.select(first))
        duplicate = self.service.receive([entry])
        self.assertEqual(duplicate['added'], 0)
        self.assertEqual(duplicate['existing'][0]['status'], 'cancelled')
        self.assertEqual(duplicate['existing'][0]['scene_index'], 0)
        self.service.action('remove', *self.select(first))
        resent = self.service.receive([entry])
        self.assertEqual(resent['added'], 1)
        self.assertNotEqual(resent['ids'][0], first)
        self.assertEqual(self.item(resent['ids'][0])['status'], 'preparation')
        self.assertEqual(self.adapter.calls, [])

    def test_active_remove_waits_for_worker_and_late_cancel_error_cannot_resurrect(self):
        identity = self.receive(final=True)
        self.service.launch(*self.select(identity))
        self.service.dispatch()
        self.service.action('remove', *self.select(identity))
        self.assertTrue(self.item(identity)['remove_requested'])
        self.assertTrue(self.item(identity)['cancel_requested'])
        self.service.dispatch()
        self.assertEqual(len(self.service._workers), 1)
        DeferredThread.finish()  # Finish the active step, then its late cancel callback.
        self.assertEqual(self.service.snapshot()['items'], [])
        self.adapter.cancel = Mock(side_effect=RuntimeError('late cancellation reply'))
        DeferredThread.finish()
        self.assertEqual(self.service.snapshot()['items'], [])

    def test_remove_waits_for_confirmed_child_stop_even_when_queue_is_paused(self):
        identity = self.receive(final=True)
        self.service.launch(*self.select(identity))
        item = self.service._get(identity)
        item['runtime'].update(attempt_id='attempt-running', render_project_id='project-running')
        self.adapter.pending_removal_stage = Mock(side_effect=['video', 'video', None])
        self.service.dispatch()
        self.service.action('remove', *self.select(identity))
        DeferredThread.finish()
        DeferredThread.finish()
        self.assertEqual(self.item(identity)['recover_stage'], 'video')
        self.service._state['paused'] = True
        self.service.dispatch()
        DeferredThread.finish()
        self.assertEqual(self.service.snapshot()['items'], [])

    def test_restart_recovers_pending_removal_without_blind_resubmission(self):
        identity = self.receive(final=True)
        item = self.service._get(identity)
        item.update(status='active', remove_requested=True, cancel_requested=True)
        item['runtime'].update(attempt_id='attempt-existing', render_project_id='project-existing')
        item['steps']['video']['status'] = 'running'
        self.service._save((item,))
        restarted = VideoFactoryService(store=self.store, adapter=self.adapter)
        self.assertEqual(restarted.snapshot()['items'][0]['recover_stage'], 'video')
        restarted.dispatch()
        DeferredThread.finish()
        self.assertEqual(restarted.snapshot()['items'], [])

    def test_publication_callback_does_not_restore_a_removed_result(self):
        identity = self.receive(final=True)
        self.service._get(identity)['status'] = 'succeeded'
        self.service.outputs = Mock()
        self.service.outputs.publish.return_value = {'status': 'succeeded', 'key': 'files'}
        self.service.action('remove', *self.select(identity))
        self.service._publish_delivery(identity, {'key': 'files'}, {})
        self.assertEqual(self.service.snapshot()['items'], [])


class FactoryDlssRequestTest(unittest.TestCase):
    def test_real_length_ids_are_bounded_stable_and_attempt_specific(self):
        dlss = Mock()
        dlss.queue.return_value = dict(job_id='job', status='succeeded', output_asset_id='upscaled')
        adapter = FactoryWorkflows(prompt_lab=None, composition=None, render=None, dlss=dlss,
            social=None, episodes=None, assets=None, coordinator=None)
        item = new_item('Video', configuration(), {}, 'key')
        item['steps']['video']['output'] = dict(owner='h3', project_id='h3-render-'+uuid4().hex,
            attempt_id='attempt-'+uuid4().hex, asset_id='video')
        requests = []
        for attempt in (item['steps']['video']['output']['attempt_id'],
                        item['steps']['video']['output']['attempt_id'], 'attempt-'+uuid4().hex):
            item['steps']['video']['output']['attempt_id'] = attempt
            adapter._dlss(item, Mock(), lambda: False, Mock())
            request_id = dlss.queue.call_args.kwargs['request_id']
            self.assertRegex(request_id, r'\A[A-Za-z0-9_-]{1,80}\Z')
            requests.append(request_id)
        self.assertEqual(requests[0], requests[1])
        self.assertNotEqual(requests[1], requests[2])

    def test_removal_never_retries_or_creates_a_dlss_job(self):
        dlss = Mock()
        dlss.jobs.get.return_value = dict(status='cancelled', job_id='job')
        adapter = FactoryWorkflows(prompt_lab=None, composition=None, render=None, dlss=dlss,
            social=None, episodes=None, assets=None, coordinator=None)
        item = new_item('Video', configuration(), {}, 'key')
        item['runtime'].update(dlss_job_id='job', explicit_retry=True)
        from panelforge.application.video_factory import FactoryCancelled
        with self.assertRaises(FactoryCancelled):
            adapter.run(item, 'dlss', Mock(), lambda: True, Mock())
        dlss.retry.assert_not_called()
        dlss.queue.assert_not_called()


if __name__ == '__main__':
    unittest.main()