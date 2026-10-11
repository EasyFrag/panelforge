"""User-run regressions. No model calls, FFmpeg, or real ComfyUI execution."""
import base64
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from panelforge.application.dance import DanceService
from panelforge.application.dance_prompting import default_prompt, validate_prompt
from panelforge.application.h3_render import H3RenderService
from panelforge.domain.dance import DanceReference, excerpt_frames
from panelforge.domain.h3_bunny import H3BunnySettings
from panelforge.domain.h3_render import H3RenderAttemptStatus, H3RenderInputMode
from panelforge.domain.video_lab import VideoAspectRatio, VideoLabSettings
from panelforge.features.lab.dance_web import dance_router
from panelforge.features.lab.web import serialize_h3_render_project
from panelforge.infrastructure.presets import Ref2VH3RenderPresetRecipe, VideoLabPresetRecipe, load_video_lab_workflow
from panelforge.infrastructure.presets.h3_bunny import BunnyH3RenderRecipe
from panelforge.infrastructure.presets.h3_dance import dance_recipes
from panelforge.infrastructure.presets.h3_loras import MultiLoraH3RenderRecipe
from panelforge.infrastructure.presets.h3_video_vae import H3VideoVaeUpdates
from panelforge.infrastructure.storage import LocalAssetStore, LocalH3RenderProjectStore
from panelforge.infrastructure.storage.h3_render_projects import _deserialize, _serialize

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / 'workflows'
MANIFEST = WF / 'video.reference/dance/1.0.0/manifest.json'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
MP4 = b'\x00\x00\x00\x18ftypisomfake-video'


def sources():
    ordinary = WF / 'video.generate.ref2v/minimax-h3-ref2v/0.2.5'
    bunny = WF / 'video.generate.h3-base/minimax-h3-bunny/0.1.3'
    return (MultiLoraH3RenderRecipe(Ref2VH3RenderPresetRecipe(VideoLabPresetRecipe(load_video_lab_workflow(ordinary))), ordinary),
            MultiLoraH3RenderRecipe(BunnyH3RenderRecipe(bunny), bunny))


def recipes():
    update = H3VideoVaeUpdates(WF, WF / 'video.vae/minimax-h3-int8-convrot/1.0.0/manifest.json')
    return dance_recipes(tuple(update.upgrade(r) for r in sources()), MANIFEST)


def parameters(recipe):
    bunny = H3BunnySettings() if recipe.reference.recipe_id == 'minimax-h3-bunny' else None
    steps = bunny.coarse_steps + bunny.refine_steps if bunny else 12
    value = dict(source_images=('photo.png',), prompt=default_prompt(True),
                 settings=VideoLabSettings(VideoAspectRatio.PORTRAIT_WIDESCREEN, 1.0, 8, steps, 123, True),
                 initial_megapixels=.2, output_filename_prefix='video/dance/test', keyframe_indices=(0, 100))
    if bunny:
        value['bunny'] = bunny
    return value


class DanceContractTest(unittest.TestCase):
    def test_excerpt_alignment_never_exceeds_requested_end(self):
        for duration in [5.2, 8, 10, 12, 15]:
            with self.subTest(duration=duration):
                frames = excerpt_frames(2, duration, 30)
                self.assertEqual(frames % 17, 5)
                self.assertLessEqual(frames / 24, duration)
                self.assertLess(duration - frames / 24, 17 / 24)
        self.assertEqual(excerpt_frames(0, 8, 8), 192)

    def test_invalid_or_out_of_bounds_excerpts_rejected(self):
        for args in [(0,5,20),(-1,8,20),(18,8,20),(0,16,20),(float('nan'),8,20),(False,8,20)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                excerpt_frames(*args)

    def test_audio_labels_follow_available_media(self):
        for has_audio in (False,True):
            self.assertEqual(validate_prompt(default_prompt(has_audio), has_audio), default_prompt(has_audio))
        for bad in [default_prompt(False).replace('<Video 1>', '<Video_1>'),
                    default_prompt(False).replace('<Picture 1>', '<Picture 2>'), default_prompt(True)]:
            with self.assertRaises(ValueError):
                validate_prompt(bad, False)


class DanceGraphTest(unittest.TestCase):
    def setUp(self):
        self.recipes = recipes()

    def test_image_only_graph_is_identical(self):
        for recipe in self.recipes:
            with self.subTest(recipe=recipe.reference.recipe_id):
                args = parameters(recipe)
                self.assertEqual(recipe.build_workflow(**args), recipe.recipe.build_workflow(**args))

    def test_full_render_changes_only_reference_inputs_and_loaders(self):
        for recipe in self.recipes:
            args = parameters(recipe)
            original = recipe.recipe.build_workflow(**args)
            actual = recipe.build_workflow(**args, reference_video='clip.mp4', reference_audio=True)
            for binding in recipe.entry['conditionings']:
                inputs = actual[binding['id']]['inputs']
                self.assertEqual(inputs.pop('ref_videos.ref_video_0'), [recipe.contract['nodes']['components'],0])
                self.assertEqual(inputs.pop('ref_video_audios.ref_video_audio_0'), [recipe.contract['nodes']['components'],1])
            for name in ('video','components'):
                actual.pop(recipe.contract['nodes'][name])
            # Original compilers may retain orphan utility nodes; all retained nodes must match.
            self.assertEqual(actual, {key:original[key] for key in actual})
            self.assertIn(recipe.output_node_id, actual)

    def test_equal_resolution_full_render_keeps_each_native_recipe_policy(self):
        for recipe in self.recipes:
            with self.subTest(recipe=recipe.reference.recipe_id):
                args = parameters(recipe)
                args.update(initial_megapixels=.9, settings=replace(args['settings'], megapixels=.9))
                original = recipe.recipe.build_workflow(**args)
                graph = recipe.build_workflow(**args, reference_video='clip.mp4', dance_stage='full')
                expected = 2 if args.get('bunny') else 1
                self.assertEqual(sum(n['class_type'] == 'SamplerCustomAdvanced' for n in graph.values()), expected)
                self.assertFalse(any(n['class_type'] in ('SaveLatent', 'LoadLatent') for n in graph.values()))
                for binding in recipe.entry['conditionings']:
                    self.assertEqual(graph[binding['id']]['inputs'].pop('ref_videos.ref_video_0'),
                                     [recipe.contract['nodes']['components'], 0])
                for name in ('video', 'components'):
                    graph.pop(recipe.contract['nodes'][name])
                self.assertEqual(graph, {key: original[key] for key in graph})

    def test_draft_saves_both_latents_and_prunes_second_sampler(self):
        for recipe in self.recipes:
            graph = recipe.build_workflow(**parameters(recipe), reference_video='clip.mp4', dance_stage='draft')
            nodes = recipe.contract['nodes']
            self.assertEqual(graph[nodes['save_video']]['class_type'], 'SaveLatent')
            self.assertEqual(graph[nodes['save_audio']]['class_type'], 'SaveLatent')
            self.assertIn(recipe.entry['coarse'][0], graph)
            self.assertEqual(sum(n['class_type']=='SamplerCustomAdvanced' for n in graph.values()), 1)
            for binding in recipe.entry['decode']:
                self.assertEqual(graph[binding['id']]['inputs'][binding['input']], recipe.entry['coarse'])

    def test_refinement_loads_saved_latents_without_coarse_sampling(self):
        for recipe in self.recipes:
            graph = recipe.build_workflow(**parameters(recipe), reference_video='clip.mp4', dance_stage='refine',
                                          source_latents=('saved-video.latent','saved-audio.latent'))
            self.assertNotIn(recipe.entry['coarse'][0], graph)
            self.assertEqual(sum(n['class_type']=='LoadLatent' for n in graph.values()), 2)
            self.assertEqual(sum(n['class_type']=='SamplerCustomAdvanced' for n in graph.values()), 1)

    def test_recipe_fingerprint_and_missing_latents_fail_explicitly(self):
        for recipe in self.recipes:
            with self.assertRaises(ValueError):
                recipe.build_workflow(**parameters(recipe), reference_video='clip.mp4', dance_stage='refine')
            with self.assertRaises(ValueError):
                recipe.latent_outputs({'outputs':{}})
        manifest = json.loads(MANIFEST.read_text())
        manifest['recipes'][0]['source']['workflow_sha256'] = '0'*64
        from panelforge.infrastructure.presets.h3_dance import DanceRecipe
        with self.assertRaises(ValueError):
            DanceRecipe(self.recipes[0].recipe, manifest, manifest['recipes'][0])


class FakeMedia:
    available = True
    def __init__(self): self.finishes=[]
    def inspect(self, content): return dict(duration_seconds=20,width=720,height=1280,has_audio=True)
    def image(self, content): return PNG
    def prepare(self, content, *, start, duration):
        return MP4, dict(frame_count=192,duration_seconds=8,has_audio=True)
    def finish(self, video, clip, **kwargs):
        self.finishes.append((video,clip,kwargs)); return video


class FakeComfy:
    def __init__(self, recipes):
        self.graphs={}; self.uploads=[]
        self.templates={}
        for recipe in recipes:
            for node in recipe.build_workflow(**parameters(recipe)).values():
                self.templates.setdefault(node['class_type'],{}).update({key:['STRING'] for key in node['inputs']})
    def upload_image(self, content, *, filename, subfolder=''):
        self.uploads.append((content,filename,subfolder))
        return SimpleNamespace(workflow_value=f'{subfolder}/{filename}')
    def describe_node(self, name): return {name:{'input':{'required':self.templates.get(name,{})}}}
    def list_lora_models(self): return ()
    def submit_workflow(self, graph):
        key=f'exec-{len(self.graphs)}'; self.graphs[key]=graph; return key
    def get_history(self, execution):
        outputs={}
        for key,node in self.graphs[execution].items():
            kind=node['class_type']
            if kind not in ('SaveVideo','SaveImage','SaveLatent'): continue
            ext={'SaveVideo':'mp4','SaveImage':'png','SaveLatent':'latent'}[kind]
            outputs[key]={'latents' if kind=='SaveLatent' else 'images':[
                {'filename':key+'.'+ext,'subfolder':'dance','type':'output'}]}
        return {execution:{'status':{'completed':True,'status_str':'success'},'outputs':outputs}}
    def download_output(self, *, filename, **kwargs):
        return MP4 if filename.endswith('.mp4') else PNG if filename.endswith('.png') else b'saved-latent'
    def cancel_execution(self, execution): raise AssertionError('Unexpected cancellation')
    def get_queue(self): return SimpleNamespace(find=lambda execution:None)


class DanceServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        base=sources(); self.extensions=recipes(); self.media=FakeMedia(); self.comfy=FakeComfy(self.extensions)
        updates=H3VideoVaeUpdates(WF,WF/'video.vae/minimax-h3-int8-convrot/1.0.0/manifest.json')
        self.render=H3RenderService(gateway=SimpleNamespace(list_models=lambda:()), workflow=base[0],
            ref2v_workflow=base[0], additional_workflows=(base[1],), recipe_upgrade=updates.upgrade,
            reference_video_upgrade=lambda candidates:dance_recipes(candidates,MANIFEST),dance_media=self.media,
            comfy=self.comfy, assets=LocalAssetStore(self.temp.name),projects=LocalH3RenderProjectStore(self.temp.name),
            sessions=None,compositions=None)
        self.service=DanceService(self.render)
        video=self.service.import_video(MP4)
        self.project=self.service.create(image=PNG,video_asset_id=video['asset_id'],start=1,duration=8,keep_audio=True,title='Danse test')

    def prepare(self, index=0, *, stage='draft', initial=.2, target=1.0):
        recipe=self.extensions[index]; args=parameters(recipe)
        return self.render.prepare_attempt(self.project.project_id,prompt=self.project.current_prompt,
            settings=replace(args['settings'], megapixels=target),initial_megapixels=initial,recipe_id=recipe.reference.recipe_id,
            recipe_version=recipe.reference.version,bunny=args.get('bunny'),dance_stage=stage)

    def execute(self, project):
        attempt=project.attempts[-1]; self.render.queue_attempt(project.project_id,attempt.attempt_id)
        return self.render.execute_attempt(project.project_id,attempt.attempt_id)

    def test_draft_and_refinement_reuse_inputs_seed_and_audio_for_both_recipes(self):
        for index in (0,1):
            with self.subTest(recipe=index):
                done=self.execute(self.prepare(index)); draft=done.attempts[-1]
                self.assertEqual(draft.status,H3RenderAttemptStatus.SUCCEEDED,draft.error)
                self.assertEqual(len(draft.latent_asset_ids),2)
                self.assertTrue(self.media.finishes[-1][2]['keep_audio'])
                final=self.service.finalize(done.project_id,draft.attempt_id,1.2)
                self.assertEqual(final.attempts[-1].source_attempt_id,draft.attempt_id)
                self.assertEqual(final.attempts[-1].settings.seed,draft.settings.seed)
                final=self.execute(final); refined=final.attempts[-1]
                self.assertEqual(refined.status,H3RenderAttemptStatus.SUCCEEDED,refined.error)
                graph=self.comfy.graphs[refined.execution_id]
                self.assertNotIn(self.extensions[index].entry['coarse'][0],graph)

    def test_direct_equal_resolution_render_exports_without_a_finalize_step(self):
        for index in (0, 1):
            with self.subTest(recipe=index):
                done = self.execute(self.prepare(index, stage='full', initial=.9, target=.9))
                attempt = done.attempts[-1]
                self.assertEqual(attempt.status, H3RenderAttemptStatus.SUCCEEDED, attempt.error)
                self.assertEqual(attempt.dance_stage, 'full')
                self.assertFalse(attempt.latent_asset_ids)
                self.assertEqual(attempt.upscale_bypassed, index == 0)
                self.assertTrue(self.media.finishes[-1][2]['keep_audio'])
                saved = serialize_h3_render_project(done)
                self.assertFalse(saved['attempts'][-1]['can_finalize'])
                phases = {p.phase_id for p in self.render.progress_for_attempt(done, attempt).phases}
                if index == 0:
                    self.assertFalse(phases & {'latent_upscale', 'refinement'})
                else:
                    self.assertTrue({'coarse', 'refine'} <= phases)

    def test_equal_resolution_preview_preserves_latents_and_native_finish_policy(self):
        for index in (0, 1):
            with self.subTest(recipe=index):
                done = self.execute(self.prepare(index, initial=.9, target=.9))
                draft = done.attempts[-1]
                self.assertEqual(draft.status, H3RenderAttemptStatus.SUCCEEDED, draft.error)
                self.assertEqual(len(draft.latent_asset_ids), 2)
                if index == 0:
                    count = len(done.attempts)
                    with self.assertRaisesRegex(ValueError, 'n’ajoute pas de finition'):
                        self.service.finalize(done.project_id, draft.attempt_id, .9)
                    self.assertEqual(len(self.render.projects.get(done.project_id).attempts), count)
                refined = self.execute(self.service.finalize(done.project_id, draft.attempt_id, 1.2 if index == 0 else .9))
                attempt = refined.attempts[-1]
                self.assertEqual(attempt.status, H3RenderAttemptStatus.SUCCEEDED, attempt.error)
                self.assertNotIn(self.extensions[index].entry['coarse'][0], self.comfy.graphs[attempt.execution_id])

    def test_recovery_after_restart_imports_latents_and_source_audio(self):
        prepared=self.prepare(); attempt=prepared.attempts[-1]; recipe=self.extensions[0]
        graph=recipe.build_workflow(**parameters(recipe),reference_video='clip.mp4',dance_stage='draft')
        execution=self.comfy.submit_workflow(graph)
        running=attempt.queue().start(execution,'a'*64)
        self.render.projects.save(prepared.replace_attempt(running))
        recovered=self.service.get(prepared.project_id).attempts[-1]
        self.assertEqual(recovered.status,H3RenderAttemptStatus.SUCCEEDED,recovered.error)
        self.assertEqual(len(recovered.latent_asset_ids),2)
        self.assertTrue(self.media.finishes[-1][2]['keep_audio'])

    def test_persistence_and_legacy_schema_roundtrip(self):
        value=_serialize(self.project)
        self.assertEqual(_deserialize(value),self.project)
        value['schema_version']=17; value.pop('dance_reference')
        self.assertIsNone(_deserialize(value).dance_reference)
        self.assertEqual(self.service.list()[0].dance_reference.clip_asset_id,self.project.dance_reference.clip_asset_id)

    def test_render_trace_does_not_look_up_an_invented_composition(self):
        def unexpected(*args): raise AssertionError('A dance has no composition session')
        saved=[]
        self.render.compositions=SimpleNamespace(get=unexpected)
        self.render.llm_traces=SimpleNamespace(snapshot=lambda *args,**kwargs:saved.append(kwargs))
        self.prepare()
        self.assertEqual(saved,[{'preparation_calls':[]}])

    def test_no_regular_recipe_or_modified_prompt_can_finalize_dance(self):
        with self.assertRaises(ValueError):
            self.render.prepare_attempt(self.project.project_id,prompt=self.project.current_prompt,
                settings=parameters(self.extensions[0])['settings'])
        done=self.execute(self.prepare()); draft=done.attempts[-1]
        with self.assertRaises(ValueError):
            self.render.prepare_attempt(done.project_id,prompt=draft.prompt+'\nChanged intent.',
                settings=draft.settings,initial_megapixels=.2,recipe_id=draft.recipe.recipe_id,
                recipe_version=draft.recipe.version,dance_stage='refine',source_attempt_id=draft.attempt_id)

    def test_api_reopens_sources_and_rejects_unknown_prompt_fields(self):
        app=FastAPI();app.include_router(dance_router(self.render,serialize_h3_render_project))
        with TestClient(app) as client:
            listed=client.get('/api/dance/projects').json()
            self.assertEqual(listed['projects'][0]['id'],self.project.project_id)
            result=client.put(f'/api/dance/projects/{self.project.project_id}/prompt',json={'prompt':self.project.current_prompt})
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['project']['dance_reference']['duration_seconds'],8)
            rejected=client.put(f'/api/dance/projects/{self.project.project_id}/prompt',json={'prompt':self.project.current_prompt,'unused':True})
            self.assertEqual(rejected.status_code,422)


if __name__=='__main__':
    unittest.main()
