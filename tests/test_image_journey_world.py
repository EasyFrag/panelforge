"""World memory and permissive reviews. User-run tests; all gateways are local fakes."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from panelforge.application import image_journey_realistic_prompting as prompting
from panelforge.application import image_journey_world as world
from panelforge.application.image_journey_resolutions import ImageJourneyResolutions
from panelforge.application.prompt_lab import CompletionResult, CompletionStreamEvent, StreamEventKind, StreamPhase
from panelforge.domain import image_journey_retries as retry
from panelforge.domain import image_journeys as journey
from panelforge.infrastructure.presets.minimax_edit import load_minimax_edit_workflow
from test_image_journeys import ImageJourneyFixture
import test_image_journey_retries as fixtures
from test_image_journey_progress_review import progress, comparison

WORLD = 'A mixed ice and wool world: chunky knitted walls and fibrous foreground, translucent ice floor.'
GOOD = fixtures.GOOD
SOFT = dict(GOOD, requested_change_complete=False, scene_preserved=False)


class WorldGateway(fixtures.RetryGateway):
    world_value = WORLD
    echo_world = False

    def stream(self, request):
        for event in super().stream(request):
            if (event.kind is StreamEventKind.COMPLETED and request.operation_id in
                    {prompting.OPERATION, prompting.PLAN_OPERATION, prompting.REVIEW_OPERATION}):
                value = json.loads(event.result.content)
                if 'world_description' in request.output_schema['properties'] or self.echo_world:
                    value['world_description'] = self.world_value
                yield CompletionStreamEvent(StreamEventKind.COMPLETED, StreamPhase.COMPLETED,
                    result=CompletionResult(request.model_id, json.dumps(value), call_id='world-call'))
            else:
                yield event


class WorldReviewContractTest(unittest.TestCase):
    def test_soft_scene_and_material_flags_do_not_veto_useful_progress(self):
        for defects in ([], ['untargeted_damage']):
            with self.subTest(defects=defects):
                result = retry.visual_review(dict(observation='Dépose visible malgré des matières différentes.',
                    quality=SOFT, progress=progress(defects=defects)))
                self.assertEqual(result['assessment'], 'usable')
                step = dict(journey_preset='realistic', automatic_retry_enabled=True,
                    source_asset_id='source', output_asset_id='result', review=result)
                self.assertIsNone(retry.mode(step))
                self.assertFalse(result['quality']['scene_preserved'])  # Keep the observation, not a veto.

    def test_clear_prohibitions_and_absence_of_progress_still_block(self):
        for defect in retry.HARD_DEFECTS:
            with self.subTest(defect=defect):
                result = retry.visual_review(dict(observation='Défaut manifeste identifié.',
                    quality=GOOD, progress=progress(defects=[defect])))
                self.assertEqual(result['assessment'], 'unusable')
        for level in ('none', 'regression'):
            result = retry.visual_review(dict(observation='Aucune avancée utile.',
                quality=GOOD, progress=progress(level)))
            self.assertEqual(result['assessment'], 'unusable')
        reached = retry.visual_review(dict(observation='État de départ déjà atteint.',
            quality=GOOD, progress=progress('none', reached=True)))
        self.assertEqual(reached['assessment'], 'usable')

    def test_people_cleanup_keeps_partial_work_despite_soft_material_drift(self):
        step = dict(id='step', journey_preset='realistic', automatic_retry_enabled=True,
            source_asset_id='before', output_asset_id='initial', world_description=WORLD,
            review=retry.visual_review(dict(observation='Ouvriers ajoutés, mobilier retiré.',
                quality=dict(SOFT, people_present=True),
                progress=progress(defects=['people', 'untargeted_damage']))))
        self.assertEqual(retry.mode(step), 'cleanup')
        retry.begin(step, 'cleanup')
        self.assertEqual(step['source_asset_id'], 'initial')
        self.assertEqual(step['world_description'], WORLD)
        self.assertEqual(step['attempt_history'][0]['world_description'], WORLD)
        self.assertIsNone(retry.mode(step))  # No third automatic attempt.
        step['review'] = dict(observation='Toujours des ouvriers.')
        replacement = ImageJourneyResolutions._replacement(step, False, 'manual-retry')
        self.assertEqual(replacement['world_description'], WORLD)
        self.assertEqual(replacement['automatic_retry_count'], 1)

    def test_comparison_can_retain_initial_with_soft_drift(self):
        step = dict(journey_preset='realistic', retry_kind='regenerate', automatic_retry_count=1,
            output_asset_id='correction', attempt_history=[dict(output_asset_id='initial')])
        value = dict(observation='Correction peu utile.', quality=GOOD, progress=progress('none'),
            comparison=comparison('initial', initial_quality=SOFT,
                initial_progress=progress(defects=['untargeted_damage'])))
        selected, result = retry.select_review(value, step)
        self.assertEqual(selected['assessment'], 'usable')
        self.assertEqual(result['selected'], 'initial')
        self.assertFalse(selected['quality']['scene_preserved'])

    def test_world_metadata_is_stable_advisory_and_does_not_mutate_schema(self):
        original = deepcopy(prompting.PLAN_SCHEMA)
        schema = prompting.plan_schema({})
        self.assertIn('world_description', schema['required'])
        self.assertEqual(prompting.PLAN_SCHEMA, original)
        self.assertNotIn('world_description', prompting.plan_schema(dict(world_description=WORLD))['properties'])
        reply = dict(title='Dépose', world_description='An ordinary concrete world.')
        self.assertEqual(world.take_description(reply, dict(world_description=WORLD)),
                         dict(world_description=WORLD))
        self.assertNotIn('world_description', reply)
        for missing in (None, '', {}, 'x' * (world.LIMIT + 1), 'World from <Picture 9>'):
            self.assertEqual(world.take_description(dict(world_description=missing), {}), {})

    def test_compiled_prompt_keeps_world_and_cleanup_does_not_restore_it(self):
        context = dict(mode='edit', guide=None, source_asset_id='source', world_description=WORLD,
            render_inputs=[dict(id='source', tag='<Picture 1>', asset_id='source')])
        raw = json.dumps(dict(message='Dépose.', prompt='Edit <Picture 1> to remove the furniture.'))
        rendered = prompting.decode_prompt(raw, context)[1]
        self.assertIn(WORLD, rendered)
        self.assertNotIn('<Picture 2>', rendered)
        cleaned = prompting.decode_prompt(raw, dict(context, retry_kind='cleanup'))[1]
        self.assertNotIn(WORLD, cleaned)
        self.assertIn('Do not use this cleanup to correct its style', cleaned)
        self.assertIn('world/theme variations alone must not reject', prompting.REVIEW_RULES)
        self.assertNotIn('untargeted_damage',
            retry.PROGRESS_SCHEMA['properties']['blocking_defects']['items']['enum'])


class ImageJourneyWorldTest(ImageJourneyFixture):
    real = fixtures.ImageJourneyRetriesTest.real
    render_frame = fixtures.ImageJourneyRetriesTest.render_frame
    render_current = fixtures.ImageJourneyRetriesTest.render_current
    render_operation = fixtures.ImageJourneyRetriesTest.render_operation
    start_operation = fixtures.ImageJourneyRetriesTest.start_operation
    operation = fixtures.ImageJourneyRetriesTest.operation
    operation_until = fixtures.ImageJourneyRetriesTest.operation_until

    def setUp(self):
        super().setUp()
        self.minimax.workflow = load_minimax_edit_workflow(
            Path(__file__).resolve().parents[1] / 'workflows/image.edit/minimax-h3-still/1.3.0')
        self.gateway = WorldGateway()
        self.journeys.gateway = self.minimax.gateway = self.gateway

    def test_world_is_saved_once_sent_to_each_render_and_survives_restart(self):
        initial = self.real(count=2, intention='Grotte vide dans un monde en laine.')
        self.journeys.advance(self.journey_id)
        self.assertEqual(self.current_journey()['world_description'], WORLD)
        self.gateway.world_value = 'An ordinary stone cave.'
        self.gateway.echo_world = True  # A later model echo must not redefine the original.
        final = self.until('completed')
        self.assertEqual(final['world_description'], WORLD)
        for step in final['steps']:
            self.assertEqual(step['world_description'], WORLD)
            self.assertEqual(step['finished_reference_asset_id'], initial['source_asset_id'])
            self.assertIn(WORLD, step['prompt'])
            child = self.minimax.get(step['minimax_project_id'])
            self.assertEqual(child['world_description'], WORLD)
            self.assertIn(WORLD, child['stages'][0]['messages'][0]['text'])
            self.assertEqual(child['stages'][0]['messages'][0]['journey_world_description'], WORLD)
        analyses = [r for r in self.gateway.requests if r.operation_id == prompting.OPERATION]
        self.assertEqual(len(analyses), 3)  # Initial plan plus two reviews; no world-analysis call.
        self.assertTrue(all(json.loads(r.user_prompt)['world_description'] == WORLD for r in analyses[1:]))
        self.assertTrue(all('world_description' not in r.output_schema['properties'] for r in analyses[1:]))
        self.journeys = self.new_service()
        self.assertEqual(self.current_journey()['world_description'], WORLD)

    def test_partial_theme_drift_continues_with_result_as_next_source(self):
        self.real(count=2)
        current = self.until('reviewing')
        output = current['steps'][0]['output_asset_id']
        self.gateway.verdicts = [SOFT]
        self.gateway.progress_verdicts = [progress(defects=['untargeted_damage'])]
        self.journeys.advance(self.journey_id)
        current = self.current_journey()
        self.assertEqual(current['phase'], 'ready')
        self.assertEqual(current['current_asset_id'], output)
        self.assertNotIn('attempt_history', current['steps'][0])
        self.until('rendering')
        self.assertEqual(self.current_journey()['steps'][1]['source_asset_id'], output)

    def test_all_manual_gaps_inherit_world_without_changing_neighbors(self):
        for kind in ('insert', 'append', 'prepend'):
            with self.subTest(kind=kind):
                self.real(count=1, command='world-' + kind, intention='Monde en laine et glace.')
                before = deepcopy(self.until('completed')['steps'])
                anchors = (dict(after_frame_id='source', before_frame_id=before[0]['id']) if kind == 'insert'
                    else dict(after_frame_id=None, before_frame_id='source') if kind == 'prepend' else {})
                op = self.start_operation(kind, **anchors)
                self.assertEqual(op['world_description'], WORLD)
                self.assertEqual(op['world_intention'], 'Monde en laine et glace.')
                self.operation_until('reviewing')
                self.gateway.verdicts = [SOFT]
                self.gateway.progress_verdicts = [progress()]
                self.journeys.edits.advance(self.journey_id)
                completed = self.operation()
                self.assertEqual(completed['status'], 'completed')
                self.assertIn(WORLD, completed['prompt'])
                self.assertNotIn('attempt_history', completed)
                self.assertEqual(self.current_journey()['steps'], before)
                call = [r for r in self.gateway.requests if r.operation_id == prompting.PLAN_OPERATION][-1]
                self.assertEqual(json.loads(call.user_prompt)['world_description'], WORLD)

    def test_legacy_manual_analysis_learns_world_without_rewriting_saved_steps(self):
        self.gateway.world_value = None
        self.real(count=1, intention='Monde en laine.')
        completed = self.until('completed')
        self.assertNotIn('world_description', completed)
        before = deepcopy(completed['steps'])
        self.gateway.world_value = WORLD
        self.start_operation('append')
        self.journeys.edits.advance(self.journey_id)
        self.assertEqual(self.current_journey()['world_description'], WORLD)
        self.assertEqual(self.operation()['world_description'], WORLD)
        self.assertEqual(self.current_journey()['steps'], before)
        call = [r for r in self.gateway.requests if r.operation_id == prompting.PLAN_OPERATION][-1]
        self.assertIn('world_description', call.output_schema['properties'])
        self.assertEqual(json.loads(call.user_prompt)['world_intention'], 'Monde en laine.')

    def test_cleanup_keeps_current_world_and_two_attempt_budget(self):
        self.real(count=1)
        initial = deepcopy(self.until('reviewing')['steps'][0])
        self.gateway.verdicts = [dict(SOFT, people_present=True)]
        self.gateway.progress_verdicts = [progress(defects=['people'])]
        self.journeys.advance(self.journey_id)
        step = self.current_journey()['steps'][0]
        self.assertEqual(step['retry_kind'], 'cleanup')
        self.assertEqual(step['source_asset_id'], initial['output_asset_id'])
        final = self.until('completed')['steps'][0]
        self.assertEqual(final['automatic_retry_count'], 1)
        self.assertEqual(len(self.comfy.submitted), 2)
        self.assertEqual(final['world_description'], WORLD)
        self.assertNotIn(WORLD, final['prompt'])  # Cleanup never reapplies the original style.
        self.assertIn('Do not use this cleanup to correct its style', final['prompt'])
        rendered = self.minimax.get(final['minimax_project_id'])['stages'][0]['attempts'][-1]
        self.assertEqual([i['asset_id'] for i in rendered['context']['render_inputs']],
                         [initial['output_asset_id']])
