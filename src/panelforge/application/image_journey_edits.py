"""Durable additions, insertions and isolated HQ renders; no implicit video handoff."""
from copy import deepcopy
import json
from uuid import NAMESPACE_URL, uuid5

from panelforge.domain import image_journeys as journey
from panelforge.domain import image_journey_edits as policy
from panelforge.domain.minimax_edit import MinimaxEditSettings, validate_prompt
from . import image_journey_edit_prompting as prompting
from .prompt_lab import CompletionRequest, ImageInput, StreamEventKind
from .revised_documents import strip_markdown_fence


class ImageJourneyEdits:
    def __init__(self, service):
        self.service = service

    @staticmethod
    def needs_work(project):
        return any(op['status'] == 'running' or op['status'] == 'paused' and op['phase'] == 'rendering'
                   for op in project.get('image_operations', []))

    @staticmethod
    def recover(project):
        changed = False
        for op in project.get('image_operations', []):
            if op['status'] == 'running':
                op.update(status='paused', error='Opération suspendue au redémarrage. Tu peux reprendre.')
                for call in op.get('analyses', []):
                    if call['status'] == 'running':
                        call.update(status='failed', error='Analyse interrompue au redémarrage.')
                changed = True
        return changed

    @staticmethod
    def _operation(project, operation_id):
        return next(op for op in project.get('image_operations', []) if op['id'] == operation_id)

    def start(self, identity, *, version, command, kind, after_frame_id, before_frame_id=None,
              intention='', prompt=''):
        from .image_journeys import JourneyConflict
        service = self.service
        journey.request_id(command)
        if kind not in {'append', 'insert', 'hq'}:
            raise ValueError('Opération sur image inconnue.')
        intention = journey.text(intention, 'Demande', 6000, kind != 'hq')
        prompt = journey.text(prompt, 'Prompt HQ', 24000, kind == 'hq')
        if kind == 'hq':
            validate_prompt(prompt, [{}])
        key = journey.fingerprint(dict(kind=kind, after=after_frame_id, before=before_frame_id,
                                       intention=intention, prompt=prompt))
        with service._lock:
            project = service._load(identity)
            previous = next((op for op in project.get('image_operations', []) if op['command'] == command), None)
            if previous:
                if previous['request_key'] != key:
                    raise JourneyConflict('Cette commande correspond déjà à une autre opération.')
                return project
            service._load(identity, version)
            if policy.pending(project):
                raise JourneyConflict('Termine ou abandonne l’opération sur image en cours.')
            if kind == 'hq':
                if before_frame_id is not None:
                    raise ValueError('Un essai HQ utilise une seule image.')
                after = next(f for f in policy.frames(project) if f['id'] == after_frame_id)
                before, index = None, 0
            else:
                if not policy.can_edit(project) or identity in service._claims:
                    raise JourneyConflict('Suspends le parcours et attends la fin de l’étape avant de modifier la suite.')
                after, before, index = policy.anchors(project, after_frame_id, before_frame_id)
                if (kind == 'insert') != bool(before):
                    raise ValueError('Choisis + entre deux images pour insérer, ou à la fin pour ajouter.')
            source = (before or after)['asset_id']
            dimensions = list(service.images.dimensions(service.assets.read_bytes(source)))
            profile = deepcopy(project.get('render_profile'))
            settings = None
            if kind == 'hq':
                if not service.renderer.minimax.workflow.manifest['capabilities'].get('native_reference'):
                    raise ValueError('L’essai HQ nécessite le workflow MiniMax 1.2.0.')
                settings = MinimaxEditSettings(resolution='double', reference_mode='native', reuse_seed=False).record()
                output_dimensions = list(MinimaxEditSettings(**settings).dimensions(dimensions))
                profile = None
            else:
                output_dimensions = profile['dimensions'] if profile else list(MinimaxEditSettings().dimensions(dimensions))
            op_id = 'journey-edit-' + uuid5(NAMESPACE_URL, identity + '/' + command).hex
            op = dict(id=op_id, journey_id=identity, command=command, request_key=key, kind=kind,
                after_frame_id=after_frame_id, before_frame_id=before_frame_id, after_asset_id=after['asset_id'],
                before_asset_id=before['asset_id'] if before else None, intention=intention, source_asset_id=source,
                source_dimensions=dimensions, dimensions=output_dimensions, render_profile=profile,
                auto_mask=kind != 'hq' and project.get('auto_mask', False),
                destination=project['destination'], index=index + 1,
                action=dict(title='Essai HQ ×2' if kind == 'hq' else 'Étape intermédiaire' if kind == 'insert' else 'Nouvelle étape',
                            change=intention, preserve='Le cadrage, la perspective et les couleurs.'),
                status='running', phase='queueing' if kind == 'hq' else 'planning', error=None,
                prompt=prompt, prompt_model_id=project['prompt_model_id'], progression_model_id=project['progression_model_id'],
                prompt_request_id=journey.identity('prompt'), render_request_id=journey.identity('render'),
                output_asset_id=None, review=None, analyses=[], created_at=journey.timestamp())
            if settings:
                op['settings'] = settings
            project.setdefault('image_operations', []).append(op)
            service._save(project)
        service._wake.set()
        return project

    def control(self, identity, operation_id, *, action):
        from .image_journeys import JourneyConflict
        service = self.service
        if action not in {'resume', 'cancel'}:
            raise ValueError('Commande d’opération inconnue.')
        with service._lock:
            project = service._load(identity)
            op = self._operation(project, operation_id)
            if op['status'] in policy.TERMINAL:
                return project
            if op['status'] != 'paused' or operation_id in service._claims:
                raise JourneyConflict('Attends la suspension de cette opération.')
            if action == 'cancel':
                attempt = service.renderer.comparison_result(op)
                if attempt and attempt['status'] not in {'succeeded', 'failed', 'cancelled'}:
                    raise JourneyConflict('Le rendu soumis doit se terminer avant d’abandonner.')
                op.update(status='cancelled', phase='cancelled', error=None)
            else:
                if op['phase'] in {'prompting', 'queueing', 'rendering'}:
                    op.update(service.renderer.retry_failed(op))
                op.update(status='running', error=None)
            service._save(project)
        service._wake.set()
        return project

    def advance(self, identity):
        service = self.service
        with service._lock:
            if service._stop.is_set():
                return
            project = service._load(identity)
            op = next((op for op in project.get('image_operations', [])
                       if op['status'] == 'running' or op['status'] == 'paused' and op['phase'] == 'rendering'), None)
            if op is None or op['id'] in service._claims:
                return
            service._claims.add(op['id'])
            snapshot = deepcopy(op)
        try:
            phase = snapshot['phase']
            if phase in {'planning', 'reviewing'}:
                self._analyze(identity, snapshot)
            elif phase == 'prompting':
                values = service.renderer.prepare(snapshot)
                self._update(identity, op['id'], **values, phase='queueing')
            elif phase == 'queueing':
                # A restart or lost acknowledgement can collect this same request without submitting twice.
                self._update(identity, op['id'], phase='rendering')
                attempt = (service.renderer.queue_comparison(snapshot) if snapshot['kind'] == 'hq'
                           else service.renderer.queue(snapshot))
                self._update(identity, op['id'], attempt_id=attempt['id'])
            elif phase == 'rendering':
                self._collect(identity, snapshot)
            elif phase == 'protecting':
                service.protection.advance(identity, op['id'], manual=True)
            else:
                raise ValueError('État de l’opération inconnu.')
        except Exception as error:
            self._update(identity, op['id'], status='paused', error=str(error))
        finally:
            with service._lock:
                service._claims.discard(op['id'])

    def _update(self, identity, operation_id, **values):
        service = self.service
        with service._lock:
            project = service._load(identity)
            self._operation(project, operation_id).update(values)
            service._save(project)

    def _collect(self, identity, op):
        service = self.service
        attempt = service.renderer.comparison_result(op)
        if attempt is None:
            self._update(identity, op['id'], phase='queueing')
        elif attempt['status'] in {'failed', 'cancelled'}:
            self._update(identity, op['id'], status='paused', phase='queueing',
                         error=attempt.get('error') or 'Le rendu a été annulé. Tu peux reprendre.')
        elif attempt['status'] == 'succeeded':
            output = attempt.get('output_asset_id')
            if not output:
                raise ValueError('Le rendu terminé ne contient pas d’image.')
            dimensions = list(service.images.dimensions(service.assets.read_bytes(output)))
            if dimensions != op['dimensions']:
                self._update(identity, op['id'], rejected_asset_id=output, phase='queueing',
                             render_request_id=journey.identity('render'))
                raise ValueError('Le moteur a renvoyé des dimensions différentes de celles demandées.')
            values = dict(output_asset_id=output, output_dimensions=dimensions, attempt_id=attempt['id'],
                settings=deepcopy(attempt['settings']), recipe=deepcopy(attempt.get('recipe')),
                generated_at=journey.timestamp(), phase='reviewing')
            if op.get('auto_mask', False):
                values.update(raw_output_asset_id=output, output_asset_id=None, phase='protecting')
            if op['kind'] == 'hq':
                values.update(status='completed', phase='completed', error=None, finished_at=journey.timestamp())
            self._update(identity, op['id'], **values)

    def _analyze(self, identity, op):
        service = self.service
        reviewing = op['phase'] == 'reviewing'
        items = [(op['after_asset_id'], 'EARLIER — état précédent conservé' if op['kind'] == 'insert'
                  else 'CURRENT — dernière image, source à éditer')]
        if op['before_asset_id']:
            items.append((op['before_asset_id'], 'LATER — état suivant conservé, source à éditer'))
        if reviewing:
            items.append((op['output_asset_id'], 'RESULT — image réellement obtenue'))
        context = prompting.context(op)
        call = dict(id=journey.identity('analysis'), status='running', phase=op['phase'], context=context,
            input_assets=items, model_id=op['progression_model_id'], created_at=journey.timestamp(),
            policy_version=prompting.VERSION, raw='', call_id=None)
        with service._lock:
            project = service._load(identity)
            self._operation(project, op['id'])['analyses'].append(call)
            service._save(project)
        raw, call_id = '', None
        try:
            request = CompletionRequest(model_id=op['progression_model_id'],
                system_prompt=prompting.REVIEW_SYSTEM if reviewing else prompting.PLAN_SYSTEM,
                user_prompt=context, images=tuple(ImageInput('image/png', service.assets.read_bytes(asset_id), label)
                    for asset_id, label in items), max_tokens=12000, include_reasoning=False,
                operation_id=prompting.REVIEW_OPERATION if reviewing else prompting.PLAN_OPERATION,
                output_schema=prompting.REVIEW_SCHEMA if reviewing else prompting.PLAN_SCHEMA,
                trace_context=dict(project_id=identity, operation_id=op['id'], analysis_id=call['id']))
            completed = False
            for event in service.gateway.stream(request):
                if event.kind is StreamEventKind.DELTA:
                    raw += event.text
                if event.kind in {StreamEventKind.COMPLETED, StreamEventKind.TRUNCATED}:
                    if event.result:
                        raw, call_id = event.result.content, event.result.call_id
                    if event.kind is StreamEventKind.TRUNCATED:
                        raise ValueError('Analyse tronquée. Tu peux reprendre cette opération.')
                    completed = True
                    break
            if not completed:
                raise ValueError('Analyse interrompue avant une réponse complète.')
            value = json.loads(strip_markdown_fence(raw))
            value = policy.validate_review(value) if reviewing else policy.validate_action(value)
            with service._lock:
                project = service._load(identity)
                current = self._operation(project, op['id'])
                if reviewing:
                    current['review'] = dict(value, model_id=op['progression_model_id'], analysis_id=call['id'],
                                             reviewed_at=journey.timestamp())
                    if value['assessment'] == 'unusable':
                        current.update(status='paused', error=value['observation'])
                    else:
                        self._commit(project, current)
                else:
                    current.update(action=value, phase='prompting', error=None)
                entry = next(c for c in current['analyses'] if c['id'] == call['id'])
                entry.update(status='succeeded', raw=raw[:100000], call_id=call_id, finished_at=journey.timestamp())
                service._save(project)
            service._report(call_id, True)
        except Exception as error:
            with service._lock:
                project = service._load(identity)
                entry = next(c for c in self._operation(project, op['id'])['analyses'] if c['id'] == call['id'])
                entry.update(status='failed', raw=raw[:100000], call_id=call_id, error=str(error), finished_at=journey.timestamp())
                service._save(project)
            service._report(call_id, False, error)
            raise

    @staticmethod
    def _commit(project, operation):
        # Validate the exact gap again before changing the order. Existing step records stay intact.
        _, _, index = policy.anchors(project, operation['after_frame_id'], operation['before_frame_id'])
        order = [s['id'] for s in journey.ordered_steps(project)]
        order.insert(index, operation['id'])
        operation.update(status='completed', phase='completed', error=None, finished_at=journey.timestamp())
        step = {k: deepcopy(v) for k, v in operation.items() if k not in {'analyses', 'request_key'}}
        step['manual'] = True
        project.setdefault('manual_steps', []).append(step)
        project['sequence_order'] = order
        if operation['kind'] == 'append':
            project['current_asset_id'] = operation['output_asset_id']
        if project['phase'] in {'planning', 'ready'}:
            project.update(phase='planning', next_action=None)
            # A fresh initial decision will see the real final state, including a manual append.
