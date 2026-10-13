"""One bounded visual correction, with immutable attempt snapshots and explicit quality."""
from copy import deepcopy

from . import image_journeys as journey

QUALITY_FIELDS = ('people_present', 'requested_change_complete', 'scene_preserved')
QUALITY_SCHEMA = dict(type='object', additionalProperties=False,
    properties={key: dict(type='boolean') for key in QUALITY_FIELDS}, required=list(QUALITY_FIELDS))

# Completion of an exact requested edit is informative, not a veto on useful progress.
PROGRESS_FIELDS = ('level', 'visible_changes', 'remaining_work', 'blocking_defects', 'destination_reached')
DEFECTS = ('people', 'camera', 'host', 'untargeted_damage', 'contradiction', 'corruption')
# Keep the historical advisory value readable, but never retry for material/style drift alone.
HARD_DEFECTS = ('people', 'camera', 'host', 'contradiction', 'corruption')
PROGRESS_SCHEMA = dict(type='object', additionalProperties=False, properties=dict(
    level=dict(type='string', enum=['complete', 'partial', 'none', 'regression']),
    visible_changes=dict(type='string'), remaining_work=dict(type='string'),
    blocking_defects=dict(type='array', items=dict(type='string', enum=list(HARD_DEFECTS))),
    destination_reached=dict(type='boolean')), required=list(PROGRESS_FIELDS))
REVIEW_SCHEMA = dict(type='object', additionalProperties=False, properties=dict(
    observation=dict(type='string'), quality=QUALITY_SCHEMA, progress=PROGRESS_SCHEMA),
    required=['observation', 'quality', 'progress'])
COMPARISON_SCHEMA = dict(type='object', additionalProperties=False, properties=dict(
    initial_review=REVIEW_SCHEMA, selected=dict(type='string', enum=['initial', 'correction', 'none']),
    reason=dict(type='string')), required=['initial_review', 'selected', 'reason'])


def progress(value):
    if not isinstance(value, dict) or set(value) != set(PROGRESS_FIELDS):
        raise ValueError('La relecture doit décrire le progrès visible, le travail restant et les défauts bloquants.')
    result = deepcopy(value)
    if not isinstance(result['level'], str) or result['level'] not in {'complete', 'partial', 'none', 'regression'}:
        raise ValueError('Niveau de progrès invalide.')
    if type(result['destination_reached']) is not bool:
        raise ValueError('La relecture doit préciser si la destination est atteinte.')
    defects = result['blocking_defects']
    if not isinstance(defects, list) or any(not isinstance(d, str) or d not in DEFECTS for d in defects):
        raise ValueError('Défaut bloquant inconnu.')
    result['blocking_defects'] = list(dict.fromkeys(defects))
    for key in ('visible_changes', 'remaining_work'):
        result[key] = journey.text(result[key], key, 4000, key == 'visible_changes')
    if result['level'] == 'partial' and not result['destination_reached'] and not result['remaining_work']:
        raise ValueError('Une avancée partielle doit préciser le travail restant.')
    return result


def usable_review(result):
    q, p = result['quality'], result['progress']
    return (not q['people_present'] and not set(p['blocking_defects']).intersection(HARD_DEFECTS)
            and p['level'] != 'regression'
            and (p['level'] in {'complete', 'partial'} or p['destination_reached']))


def visual_review(value):
    if not isinstance(value, dict) or set(value) != {'observation', 'quality', 'progress'}:
        raise ValueError('Relecture comparative invalide.')
    q = quality(value['quality'])
    if q is None:
        raise ValueError('La relecture doit préciser la qualité de chaque essai.')
    result = dict(observation=journey.text(value['observation'], 'Observation', 4000, True),
                  quality=q, progress=progress(value['progress']))
    result['assessment'] = 'usable' if usable_review(result) else 'unusable'
    return result


def comparison_candidate(step):
    history = step.get('attempt_history') or []
    if (journey.journey_preset(step) == 'realistic' and step.get('retry_kind') in {'cleanup', 'regenerate'}
            and step.get('automatic_retry_count') == 1 and step.get('retained_attempt_index') is None
            and history and history[-1].get('output_asset_id')):
        return history[-1]
    return None


def select_review(value, step):
    """Validate observations before trusting the model's preferred attempt or planning state."""
    selected = visual_review({key: value.pop(key, None) for key in ('observation', 'quality', 'progress')})
    candidate = comparison_candidate(step)
    comparison = value.pop('comparison', None)
    if candidate:
        if not isinstance(comparison, dict) or set(comparison) != {'initial_review', 'selected', 'reason'}:
            raise ValueError('La correction doit être comparée au premier essai.')
        initial = visual_review(comparison['initial_review'])
        choice = comparison['selected']
        if not isinstance(choice, str) or choice not in {'initial', 'correction', 'none'}:
            raise ValueError('Choix d’essai invalide.')
        if (choice == 'none' and (usable_review(initial) or usable_review(selected))
                or choice == 'initial' and not usable_review(initial)
                or choice == 'correction' and not usable_review(selected)):
            raise ValueError('Le choix comparatif doit conserver un essai exploitable, sans défaut bloquant.')
        comparison = dict(selected=choice,
            reason=journey.text(comparison['reason'], 'Comparaison', 4000, True),
            initial_asset_id=candidate['output_asset_id'], correction_asset_id=step['output_asset_id'],
            initial_review=initial, correction_review=deepcopy(selected))
        if choice == 'initial':
            selected = initial
    elif comparison is not None:
        raise ValueError('Aucun essai précédent à comparer pour cette image.')
    value.update(assessment=selected['assessment'], observation=selected['observation'])
    if selected['assessment'] == 'unusable' and 'next_action' in value:
        value['next_action'] = None
    return selected, comparison


ATTEMPT_FIELDS = (
    'id', 'render_identity', 'render_step_id', 'action', 'source_asset_id', 'finished_reference_asset_id',
    'world_description', 'world_intention',
    'output_asset_id', 'raw_output_asset_id', 'output_dimensions', 'review', 'prompt',
    'prompt_model_id', 'prompt_policy_version', 'progression_model_id', 'protection',
    'settings', 'recipe', 'attempt_id', 'minimax_project_id', 'minimax_stage_id',
    'message_id', 'call_id', 'prompt_request_id', 'render_request_id', 'created_at',
    'generated_at', 'retry_kind', 'regeneration_feedback', 'user_acceptance', 'auto_mask', 'attempt_comparison',
)
RENDER_FIELDS = (
    'raw_output_asset_id', 'output_dimensions', 'protection', 'settings', 'recipe',
    'attempt_id', 'minimax_project_id', 'minimax_stage_id', 'message_id', 'call_id',
    'prompt_policy_version', 'generated_at', 'rejected_asset_id', 'user_acceptance', 'attempt_comparison',
)


def quality(value):
    if value is None:
        return None
    if (not isinstance(value, dict) or set(value) != set(QUALITY_FIELDS)
            or any(type(value[key]) is not bool for key in QUALITY_FIELDS)):
        raise ValueError('La relecture doit préciser les personnes, la transformation et la fidélité du décor.')
    return deepcopy(value)


def mode(step):
    """Never derive a correction from the model's free-form observation."""
    review = step.get('review') or {}
    if (journey.journey_preset(step) != 'realistic' or not step.get('automatic_retry_enabled')
            or step.get('automatic_retry_count', 0) >= 1 or not step.get('output_asset_id')
            or review.get('assessment') != 'unusable'):
        return None
    result = quality(review.get('quality'))
    if result is None:
        return None
    observed = review.get('progress')
    if observed is not None:
        observed = progress(observed)
        # Preserve useful work even when the requested transformation is only partial.
        useful = observed['level'] in {'complete', 'partial'} or observed['destination_reached']
        people_only = set(observed['blocking_defects']).intersection(HARD_DEFECTS) <= {'people'}
        return ('cleanup' if result['people_present'] and useful
                and observed['level'] != 'regression' and people_only else 'regenerate')
    # Historical reviews remain readable; new calls use the explicit progress contract.
    return ('cleanup' if result['people_present'] and result['requested_change_complete']
            and result['scene_preserved'] else 'regenerate')


def snapshot(step):
    return {key: deepcopy(step[key]) for key in ATTEMPT_FIELDS if key in step}


def begin(step, kind):
    """Keep the logical frame ID; new render identities prevent reusing rejected pixels."""
    if kind not in {'cleanup', 'regenerate'} or mode(step) != kind:
        raise ValueError('La correction automatique de cette étape est déjà utilisée ou indisponible.')
    previous = snapshot(step)
    source = step.get('retry_initial_source_asset_id', step['source_asset_id'])
    original_mask = step.get('retry_initial_auto_mask', step.get('auto_mask', False))
    step.setdefault('attempt_history', []).append(previous)
    for key in RENDER_FIELDS:
        step.pop(key, None)
    step.update(automatic_retry_count=1, retry_kind=kind,
        retry_initial_source_asset_id=source, retry_initial_auto_mask=original_mask,
        source_asset_id=previous['output_asset_id'] if kind == 'cleanup' else source,
        # A cleanup must be able to erase every unwanted person, without stale mask regions.
        auto_mask=False if kind == 'cleanup' else original_mask,
        render_identity=journey.identity('journey-render'),
        prompt_request_id=journey.identity('prompt'), render_request_id=journey.identity('render'),
        prompt='', output_asset_id=None, review=None,
        regeneration_feedback=previous['review']['observation'])


def retain_previous(step, output_asset_id):
    """Promote exact archived pixels; keep the complete attempt order for comparison."""
    history = step.get('attempt_history', [])
    index = next((i for i, attempt in enumerate(history)
                  if attempt.get('output_asset_id') == output_asset_id), None)
    if index is None or step.get('retained_attempt_index') is not None:
        raise ValueError('Cet essai précédent ne peut plus être accepté.')
    selected = deepcopy(history[index])
    attempts = [*deepcopy(history), snapshot(step)]
    # The logical frame and operation keep their identity, anchors, status and retry budget.
    for key in ATTEMPT_FIELDS:
        if key not in {'id', 'created_at'}:
            step.pop(key, None)
    step.update({key: value for key, value in selected.items()
                 if key in ATTEMPT_FIELDS and key not in {'id', 'created_at'}})
    step.update(attempt_history=attempts, retained_attempt_index=index,
        render_identity=selected.get('render_identity', selected['id']),
        render_step_id=selected.get('render_step_id', selected['id']),
        auto_mask=selected.get('auto_mask', bool(selected.get('protection'))))
    step.pop('rejected_asset_id', None)


def inherit_manual_retry(previous, replacement):
    """An explicit manual retry does not reset the automatic allowance or reuse cleanup pixels."""
    if previous.get('automatic_retry_enabled') or previous.get('attempt_history'):
        replacement['attempt_history'] = [*deepcopy(previous.get('attempt_history', [])), snapshot(previous)]
        replacement['automatic_retry_enabled'] = previous.get('automatic_retry_enabled', False)
        # A second attempt explicitly requested by the user also exhausts the allowance.
        replacement['automatic_retry_count'] = 1
        replacement['retry_kind'] = 'manual'
    replacement['source_asset_id'] = previous.get('retry_initial_source_asset_id', previous['source_asset_id'])
    replacement['auto_mask'] = previous.get('retry_initial_auto_mask', previous.get('auto_mask', False))
