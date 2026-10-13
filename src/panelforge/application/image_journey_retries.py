"""Review selection and one visual correction inside the existing journal transaction."""
from panelforge.domain import image_journey_retries as retry
from panelforge.domain.image_journeys import ordered_steps
from .image_journey_resolutions import ImageJourneyResolutions


def comparison_inputs(items, step):
    """The extra reference is for the existing review call only, never the render prompt."""
    previous = retry.comparison_candidate(step)
    if not previous:
        return items
    asset_id = previous['output_asset_id']
    label = 'INITIAL_ATTEMPT — premier essai, à comparer réellement à RESULT'
    if any(identity == asset_id for identity, _ in items):
        return [(identity, existing + (' — ' + label if identity == asset_id else ''))
                for identity, existing in items]
    return [*items, (asset_id, label)]


def apply_review(project, step, decision, metadata, *, manual=False):
    """Save the comparison and promote chosen pixels in the same journal transaction."""
    from copy import deepcopy
    comparison = decision.get('attempt_comparison')
    chosen = {key: deepcopy(decision[key]) for key in ('assessment', 'observation', 'quality', 'progress')
              if key in decision}
    if comparison and comparison['selected'] == 'initial':
        if not manual and ordered_steps(project)[-1]['id'] != step['id']:
            raise ValueError('Une image suivante dépend de cet essai : son remplacement reste manuel.')
        if (comparison['correction_asset_id'] != step.get('output_asset_id')
                or (retry.comparison_candidate(step) or {}).get('output_asset_id') != comparison['initial_asset_id']):
            raise ValueError('Les essais ont changé depuis la comparaison.')
        # Snapshot the correction's own verdict, not the verdict of the chosen initial.
        step['review'] = dict(deepcopy(comparison['correction_review']), **metadata)
        retry.retain_previous(step, comparison['initial_asset_id'])
    step['review'] = dict(chosen, **metadata)
    if comparison:
        step['attempt_comparison'] = dict(deepcopy(comparison), **metadata)


def start(project, step, *, manual=False, stopping=False):
    if stopping:
        return False
    if manual:
        if step.get('status') != 'running':
            return False
    elif project['status'] != 'running' or project['pause_requested']:
        return False
    # A later manual state may depend on these pixels. Leave its earlier rejection for the user.
    if not manual and ordered_steps(project)[-1]['id'] != step['id']:
        return False
    kind = retry.mode(step)
    if kind is None:
        return False
    if not manual:
        ImageJourneyResolutions._restore_progress(project, step)
    retry.begin(step, kind)
    if manual:
        step.update(status='running', phase='prompting', error=None)
    else:
        project.update(status='running', phase='prompting', next_action=None, error=None, warning=None,
                       current_asset_id=step['retry_initial_source_asset_id'])
        project.pop('completion_reason', None)
    return True
