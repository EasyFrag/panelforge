"""Versioned reference-video overlay for the two existing REF2V recipes."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path


def _reachable(graph, roots):
    required = set()
    def visit_value(value):
        if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and type(value[1]) is int:
            visit(value[0])
        elif isinstance(value, dict):
            for child in value.values():
                visit_value(child)
    def visit(node_id):
        if node_id in required:
            return
        required.add(node_id)
        for value in graph[node_id]['inputs'].values():
            visit_value(value)
    for root in roots:
        visit(root)
    return {key: value for key, value in graph.items() if key in required}


class DanceRecipe:
    supports_reference_video = True

    def __init__(self, recipe, manifest, entry):
        self.recipe, self.contract, self.entry = recipe, manifest, entry
        source = entry['source']
        if (recipe.reference.recipe_id, recipe.reference.version, recipe.reference.workflow_sha256) != (
                source['recipe_id'], source['version'], source['workflow_sha256']):
            raise ValueError('La recette Danse ne correspond plus à sa source versionnée.')
        digest = hashlib.sha256(json.dumps({'contract': manifest, 'entry': entry},
                                           sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.reference = replace(recipe.reference, version=recipe.reference.version + '.dance.' + manifest['version'],
                                 workflow_sha256=digest)
        self.source_reference = self.reference

    def __getattr__(self, name):
        return getattr(self.recipe, name)

    def build_workflow(self, *, reference_video=None, reference_audio=False,
                       dance_stage='full', source_latents=(), **kwargs):
        graph = self.recipe.build_workflow(**kwargs)
        if reference_video is None:
            if dance_stage != 'full' or source_latents:
                raise ValueError('Une vidéo de référence est nécessaire.')
            return graph
        if dance_stage not in {'full', 'draft', 'refine'} or (dance_stage == 'refine') != (len(source_latents) == 2):
            raise ValueError('Reprise du brouillon invalide.')
        nodes, bindings = self.contract['nodes'], self.entry
        if any(value in graph for value in nodes.values()):
            raise ValueError('Collision avec les nœuds réservés à la danse.')
        def add(key, class_type, **inputs):
            graph[nodes[key]] = {'class_type': class_type, 'inputs': inputs}
            return [nodes[key], 0]
        video = add('video', 'LoadVideo', file=reference_video)
        components = add('components', 'GetVideoComponents', video=video)
        for binding in bindings['conditionings']:
            node = graph[binding['id']]
            if node['class_type'] != binding['class']:
                raise ValueError('Le conditionnement REF2V a changé.')
            node['inputs']['ref_videos.ref_video_0'] = components
            if reference_audio:
                node['inputs']['ref_video_audios.ref_video_audio_0'] = [nodes['components'], 1]
        roots = [self.output_node_id, *self.keyframe_output_nodes(len(kwargs.get('keyframe_indices', ())))]
        if dance_stage == 'draft':
            coarse = bindings['coarse']
            split = add('split', 'LTXVSeparateAVLatent', av_latent=coarse)
            for i, key in enumerate(('save_video', 'save_audio')):
                add(key, 'SaveLatent', samples=[nodes['split'], i],
                    filename_prefix=kwargs['output_filename_prefix'] + ('_video' if i == 0 else '_audio'))
                roots.append(nodes[key])
            for binding in bindings['decode']:
                graph[binding['id']]['inputs'][binding['input']] = coarse
        elif dance_stage == 'refine':
            video_latent = add('load_video', 'LoadLatent', latent=source_latents[0])
            audio_latent = add('load_audio', 'LoadLatent', latent=source_latents[1])
            av = add('concat', 'LTXVConcatAVLatent', video_latent=video_latent, audio_latent=audio_latent)
            values = {'video': video_latent, 'audio': audio_latent, 'av': av}
            for binding in bindings['resume']:
                graph[binding['id']]['inputs'][binding['input']] = values[binding['stream']]
        return _reachable(graph, roots)

    def latent_outputs(self, history):
        outputs = history.get('outputs', {})
        result = []
        for key in ('save_video', 'save_audio'):
            files = outputs.get(self.contract['nodes'][key], {}).get('latents', [])
            if len(files) != 1:
                raise ValueError('Les latents du brouillon ne sont pas disponibles ; impossible de le finaliser.')
            result.append(files[0])
        return tuple(result)

    def validate_dependencies(self, comfy, workflow):
        validate = getattr(self.recipe, 'validate_dependencies', None)
        if validate and self.entry.get('delegate_dependency_validation', False):
            validate(comfy, workflow)
            return
        for class_type in sorted({node['class_type'] for node in workflow.values()}):
            if class_type not in comfy.describe_node(class_type):
                raise ValueError(f'Danse : nœud ComfyUI manquant : {class_type}.')

    def progress_for_dance(self, stage, bunny, *, upscale_bypassed=False):
        profile = self.recipe.progress_for(bunny) if bunny else self.recipe.progress_profile
        if not profile or (stage == 'full' and not upscale_bypassed):
            return profile
        bindings = self.entry['progress']['draft' if stage == 'full' else stage]
        phases = tuple(replace(phase, start_percent=bounds[0], end_percent=bounds[1])
                       for phase in profile.phases if (bounds := bindings.get(phase.phase_id)) is not None)
        label = 'Préparation de l’aperçu' if stage == 'draft' else 'Reprise de l’aperçu' if stage == 'refine' else profile.initial_label
        return replace(profile, initial_label=label, phases=phases)


def dance_recipes(recipes, manifest_path: Path):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['schema_version'] != 1:
        raise ValueError('Version de contrat Danse non prise en charge.')
    result = []
    for entry in manifest['recipes']:
        source = entry['source']
        recipe = next((r for r in recipes if r.reference.recipe_id == source['recipe_id']
                       and r.reference.version == source['version']), None)
        if recipe is None:
            raise ValueError('La recette REF2V prévue pour Danse est indisponible.')
        result.append(DanceRecipe(recipe, manifest, entry))
    return tuple(result)
