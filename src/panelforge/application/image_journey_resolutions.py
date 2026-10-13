"""Explicit user decisions on rejected pixels; never rerender a successful request ID."""
from copy import deepcopy
import json

from panelforge.domain import image_journeys as journey
from panelforge.domain import image_journey_edits as edits
from panelforge.domain import image_journey_retries as retries


class ImageJourneyResolutions:
    def __init__(self, service):
        self.service = service

    def blocked_images(self, project):
        """Only visual rejections offer pixel acceptance; technical errors still use Resume."""
        candidates = []
        if project['status'] == 'paused' and project['phase'] == 'reviewing' and project['steps']:
            candidates.append((project['steps'][-1], False))
        candidates.extend((op, True) for op in project.get('image_operations', [])
                          if op['kind'] != 'hq' and op['status'] == 'paused' and op['phase'] == 'reviewing')
        result = []
        for step, manual in candidates:
            if (not step.get('output_asset_id') or journey.image_accepted(step)
                    or (step.get('review') or {}).get('assessment') != 'unusable'):
                continue
            available = (project['id'] not in self.service._claims and step['id'] not in self.service._claims
                         and (manual or not edits.pending(project, sequence_only=True)))
            # Replacing an earlier frame must not silently invalidate a later saved manual state.
            previous = [attempt['output_asset_id'] for attempt in step.get('attempt_history', [])
                        if attempt.get('output_asset_id') and attempt.get('review')]
            if not manual and journey.ordered_steps(project)[-1]['id'] != step['id']:
                previous = []
            result.append(dict(step_id=step['id'], output_asset_id=step['output_asset_id'], manual=manual,
                accept_previous_asset_ids=previous,
                available=available, reason=step['review']['observation'],
                accept_label='Accepter l’image' if manual else 'Accepter et terminer'
                    if journey.generated(project) >= project['count'] else 'Accepter et continuer'))
        return result

    def resolve(self, identity, *, version, command, step_id, output_asset_id, action):
        from .image_journeys import JourneyConflict
        journey.request_id(command)
        if action not in {'accept', 'regenerate'}:
            raise ValueError('Décision sur image inconnue.')
        key = journey.fingerprint(dict(step_id=step_id, output_asset_id=output_asset_id, action=action))
        service = self.service
        with service._lock:
            project = service._load(identity)
            previous = next((r for r in project.get('image_resolutions', []) if r['command'] == command), None)
            if previous:
                if previous['request_key'] != key:
                    raise JourneyConflict('Cette commande correspond déjà à une autre décision.')
                return project
            service._load(identity, version)
            target = next((r for r in self.blocked_images(project)
                           if r['step_id'] == step_id and (r['output_asset_id'] == output_asset_id
                               or action == 'accept' and output_asset_id in r['accept_previous_asset_ids'])), None)
            if not target:
                raise JourneyConflict('Cette image n’attend plus de décision. Actualise le parcours.')
            if not target['available']:
                raise JourneyConflict('Attends la suspension et termine ou abandonne l’ajout en cours.')
            manual = target['manual']
            step = service.edits._operation(project, step_id) if manual else project['steps'][-1]
            decision = dict(command=command, request_key=key, step_id=step_id, output_asset_id=output_asset_id,
                            action=action, created_at=journey.timestamp())
            if manual:
                edits.anchors(project, step['after_frame_id'], step['before_frame_id'])
            if action == 'accept':
                if step['output_asset_id'] != output_asset_id:
                    decision['previous_output_asset_id'] = step['output_asset_id']
                    if not manual:
                        self._restore_progress(project, step)
                    retries.retain_previous(step, output_asset_id)
                    decision['retained_attempt_index'] = step['retained_attempt_index']
                    if not manual:
                        # The correction's summary/endpoint no longer describes the accepted pixels.
                        project['summary'] = step['review']['observation']
                        project.pop('completion_reason', None)
                step['user_acceptance'] = dict(output_asset_id=output_asset_id, command=command,
                                               accepted_at=decision['created_at'])
                if manual:
                    service.edits._commit(project, step)
                else:
                    project.update(current_asset_id=edits.frames(project)[-1]['asset_id'], phase='planning',
                                   status='running', pause_requested=False, next_action=None, error=None, warning=None)
                    if journey.generated(project) >= project['count']:
                        project.update(status='completed', phase='completed')
                        if project['completed_milestones'] < len(project['milestones']):
                            project['warning'] = 'Le parcours est terminé ; certains jalons restent inachevés.'
                    elif journey.reverse_endpoint_reached(project, dict(assessment='initial',
                            milestones=project['milestones'], completed_milestones=project['completed_milestones'])):
                        service._complete_reverse(project)
            else:
                replacement = self._replacement(step, manual, command)
                decision['replacement_id'] = replacement['id']
                step.update(replacement_id=replacement['id'], discarded_at=decision['created_at'])
                if manual:
                    step.update(status='cancelled', phase='cancelled')
                    project['image_operations'].append(replacement)
                else:
                    project.setdefault('abandoned_steps', []).append(step)
                    project['steps'][-1] = replacement
                    if 'sequence_order' in project:
                        project['sequence_order'] = [replacement['id'] if k == step_id else k
                                                     for k in project['sequence_order']]
                    self._restore_progress(project, step)
                    project.update(current_asset_id=replacement['source_asset_id'], phase='prompting', status='running',
                                   pause_requested=False, next_action=None, error=None, warning=None)
                    project.pop('completion_reason', None)
            project.setdefault('image_resolutions', []).append(decision)
            service._save(project)
        service._wake.set()
        return project

    @staticmethod
    def _replacement(step, manual, command):
        # Copy inputs only. Old render/seed, mask polygons, outputs and reviews must never be reused.
        fields = ('journey_id', 'index', 'source_asset_id', 'source_dimensions', 'dimensions', 'destination',
                  'render_profile', 'auto_mask', 'mask_model_id', 'journey_version', 'journey_direction',
                  'journey_preset', 'finished_reference_asset_id', 'world_description', 'world_intention',
                  'action', 'prompt_model_id',
                  'progression_model_id', 'decision_analysis_id', 'intent_revision', 'progress_before',
                  'kind', 'after_frame_id', 'before_frame_id', 'after_asset_id', 'before_asset_id', 'intention')
        replacement = {k: deepcopy(step[k]) for k in fields if k in step}
        replacement.update(id=journey.identity('journey-edit' if manual else 'journey-step'),
            prompt_request_id=journey.identity('prompt'), render_request_id=journey.identity('render'),
            prompt='', output_asset_id=None, review=None, created_at=journey.timestamp(),
            regenerated_from_step_id=step['id'], regeneration_feedback=step['review']['observation'])
        from panelforge.domain.image_journey_retries import inherit_manual_retry
        inherit_manual_retry(step, replacement)
        if manual:
            replacement.update(command=command, request_key=journey.fingerprint(dict(regeneration_of=step['id'])),
                               status='running', phase='prompting', error=None, analyses=[])
        return replacement

    @staticmethod
    def _restore_progress(project, step):
        if step.get('intent_revision') != project['intent_revision']:
            return
        before = step.get('progress_before')
        if before is None:
            # Older journals already saved the exact pre-review context in their analysis record.
            call = next((c for c in project['analyses'] if c['id'] == step['review'].get('analysis_id')), None)
            try:
                context = json.loads(call['context']) if call else {}
                before = dict(summary=context.get('acquired_state'),
                              completed_milestones=context.get('completed_milestones'))
            except (ValueError, TypeError, KeyError):
                return
        if (isinstance(before.get('summary'), str) and type(before.get('completed_milestones')) is int
                and 0 <= before['completed_milestones'] <= len(project['milestones'])):
            project.update(summary=before['summary'], completed_milestones=before['completed_milestones'])
