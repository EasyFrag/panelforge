"""Resolve a saved journey version without changing historical prompt policies."""
import json
from panelforge.domain.image_journeys import journey_version, journey_direction, journey_preset, ordered_steps
from . import image_journey_realistic_prompting as realistic
from . import image_journey_prompting as v1
from . import image_journey_edit_prompting as manual_v1
from . import image_journey_v2_prompting as v2
from .image_journey_reverse_prompting import REVERSE_POLICIES


def progression(record):
    if journey_preset(record) == "realistic":
        return realistic
    if journey_direction(record) == "reverse":
        return REVERSE_POLICIES[journey_version(record)]
    return v2 if journey_version(record) == "2" else v1


def manual(record):
    if journey_preset(record) == "realistic":
        return realistic
    if journey_direction(record) == "reverse":
        return REVERSE_POLICIES[journey_version(record)]
    return v2 if journey_version(record) == "2" else manual_v1


HEAD_REQUEST = (
    'PREPEND is a manual extension beyond the first saved image in GENERATION order. '
    'CURRENT is the one adjacent source to edit; it stays unchanged in the saved sequence. '
    'Produce exactly the requested state, which may be more complete or earlier than CURRENT. '
    'Do not impose the automatic journey endpoint or remove elements unless requested. '
    'Keep the preset, camera and fixed surroundings. The supplied finished reference stays an identity '
    'reference, not a requirement to copy its completion level. No change to any existing image.'
)


def edit_request(step):
    request = progression(step).edit_request(step)
    if step.get('kind') == 'prepend':
        request += '\n' + HEAD_REQUEST
    if step.get('regeneration_feedback') and step.get('retry_kind') != 'cleanup':
        request += ('\nRegenerate the SAME requested transformation from the original edit source. '
                    'The previous rejected result is not a reference. Correct the diagnosed defect '
                    'without adding a different work stage. Previous visual review: '
                    + json.dumps(step['regeneration_feedback'], ensure_ascii=False))
    return request


def progression_context(project):
    context = json.loads(progression(project).user_prompt(project))
    current = next((s for s in ordered_steps(project)
                    if s.get('output_asset_id') == project['current_asset_id'] and s.get('user_acceptance')), None)
    if current and project['phase'] != 'reviewing':
        context['accepted_current_image'] = dict(step_id=current['id'],
            previous_review=current['review'], instruction=(
                'The user explicitly accepted these exact CURRENT pixels. Do not reject or regenerate this '
                'image again. Observe its actual state and plan the next requested work stage (assessment initial). '
                'This exception only covers this image. All preset constraints still apply to future outputs.'))
    if project['phase'] == 'reviewing' and project['steps'][-1].get('regeneration_feedback'):
        step = project['steps'][-1]
        context['previous_attempt_rejection'] = step['regeneration_feedback']
        context['correction'] = dict(kind=step.get('retry_kind', 'regenerate'),
            original_transformation=step['action'],
            instruction='Judge the original requested state AND preservation of the correction source; do not just count people.')
    return json.dumps(context, ensure_ascii=False)


def manual_context(operation):
    context = json.loads(manual(operation).context(operation))
    if operation['kind'] == 'prepend':
        context.update(edit_source='CURRENT (first saved state)', boundary_instruction=HEAD_REQUEST)
    if operation.get('regeneration_feedback'):
        context['previous_attempt_rejection'] = operation['regeneration_feedback']
        context['correction'] = dict(kind=operation.get('retry_kind', 'regenerate'),
            original_transformation=operation['action'],
            instruction='Judge the original requested state and preservation of CORRECTION_SOURCE.')
    return json.dumps(context, ensure_ascii=False)


def manual_system(operation, *, reviewing):
    prompting = manual(operation)
    system = prompting.REVIEW_SYSTEM if reviewing else prompting.PLAN_SYSTEM
    return system + ('\n' + HEAD_REQUEST if operation['kind'] == 'prepend' else '')
