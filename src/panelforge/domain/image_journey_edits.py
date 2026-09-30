"""Explicit frame anchors and small contracts for manual journey operations."""
from . import image_journeys as journey

HQ_PROMPT = (
    'Create a higher-resolution version of <Picture 1>. Preserve the exact framing, '
    'geometry, objects, colors and lighting. Refine fine material textures and edge clarity. '
    'Do not add, remove or redesign anything. Avoid exaggerated contrast, sharpening halos '
    'and artificial texture.'
)
TERMINAL = {'completed', 'cancelled'}


def frames(project):
    return [dict(id='source', asset_id=project['source_asset_id'], title='Départ'), *[
        dict(id=step['id'], asset_id=step['output_asset_id'], title=step['action']['title'])
        for step in journey.ordered_steps(project) if step.get('output_asset_id')]]


def anchors(project, after_frame_id, before_frame_id):
    items = frames(project)
    for index, frame in enumerate(items):
        if frame['id'] == after_frame_id:
            following = items[index + 1] if index + 1 < len(items) else None
            if (following['id'] if following else None) != before_frame_id:
                raise ValueError('Ces images ne sont plus consécutives. Rouvre le bouton + souhaité.')
            return frame, following, index
    raise ValueError('Image de départ de cette opération introuvable.')


def pending(project, *, sequence_only=False):
    return any(op['status'] not in TERMINAL and (not sequence_only or op['kind'] != 'hq')
               for op in project.get('image_operations', []))


def can_edit(project):
    return (project['status'] in {'paused', 'completed'} and project['phase'] != 'rendering'
            and not any(not step.get('output_asset_id') for step in project['steps'])
            and not pending(project))


def validate_action(value):
    if not isinstance(value, dict) or set(value) != {'title', 'change', 'preserve'}:
        raise ValueError('La transformation demandée doit préciser son titre, le changement et les éléments à conserver.')
    return {key: journey.text(value[key], key, limit, True)
            for key, limit in (('title', 160), ('change', 4000), ('preserve', 2000))}


def validate_review(value):
    if not isinstance(value, dict) or set(value) != {'assessment', 'observation'}:
        raise ValueError('La relecture de cette image est incomplète.')
    if value['assessment'] not in {'usable', 'similar', 'unusable'}:
        raise ValueError('Constat visuel invalide.')
    return dict(assessment=value['assessment'], observation=journey.text(value['observation'], 'Observation', 4000, True))
