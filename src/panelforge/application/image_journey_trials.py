"""Durable, frozen-prompt replays at one fixed image size; no model calls."""
from copy import deepcopy
from uuid import NAMESPACE_URL, uuid5

from panelforge.domain import image_journeys as policy
from panelforge.domain.minimax_edit import MinimaxEditSettings


class ImageJourneyTrials:
    def __init__(self, service):
        self.service = service

    @staticmethod
    def needs_work(project):
        return any(t['status'] in {'running', 'pausing'} or any(
            s['status'] in {'queued', 'submitting', 'running', 'cancel_pending'} for s in t['steps'])
            for t in project.get('fixed_trials', []))

    @staticmethod
    def recover(project):
        changed = False
        for trial in project.get('fixed_trials', []):
            if trial['status'] in {'running', 'pausing'}:
                trial.update(status='paused', error='Essai suspendu au redémarrage. Tu peux reprendre.')
                changed = True
        return changed

    def start(self, identity, *, version, command, count):
        from .image_journeys import JourneyConflict
        service = self.service
        policy.request_id(command)
        if type(count) is not int or not 1 <= count <= policy.MAX_IMAGES:
            raise ValueError('Nombre d’images invalide.')
        with service._lock:
            project = service._load(identity)
            trials = project.setdefault('fixed_trials', [])
            previous = next((t for t in trials if t['command'] == command), None)
            if previous:
                if previous['count'] != count:
                    raise JourneyConflict('Cette commande correspond déjà à un autre essai.')
                return project
            service._load(identity, version)
            if any(t['status'] != 'completed' for t in trials):
                raise JourneyConflict('Termine ou reprends l’essai en cours avant d’en créer un autre.')
            if not service.renderer.minimax.workflow.manifest['capabilities'].get('native_reference'):
                raise ValueError('L’essai à dimensions fixes nécessite le nouveau workflow MiniMax.')
            originals = project['steps'][:count]
            if len(originals) != count or any(not s.get('output_asset_id') for s in originals):
                raise ValueError('Choisis uniquement des étapes déjà produites depuis le départ.')
            trial_id = 'journey-trial-' + uuid5(NAMESPACE_URL, identity + '/' + command).hex
            steps = []
            for index, original in enumerate(originals, 1):
                snapshot = service.renderer.comparison_snapshot(original, 1)
                step_id = 'journey-trial-step-' + uuid5(NAMESPACE_URL, trial_id + '/' + str(index)).hex
                snapshot['settings'].update(resolution='source', reference_mode='native')
                steps.append(dict(snapshot, id=step_id, journey_id=identity, index=index,
                    step_id=original['id'], render_request_id=step_id, source_asset_id=None,
                    status='pending', output_asset_id=None, error=None))
            content = service.assets.read_bytes(project['source_asset_id'])
            dimensions = MinimaxEditSettings(resolution='1').dimensions(service.images.dimensions(content))
            prepared = service.images.prepare_fixed_source(content, dimensions)
            source = service.assets.create(prepared, media_type='image/png', source_run_id=trial_id)
            for step in steps:
                step.update(dimensions=list(dimensions), source_dimensions=list(dimensions))
            steps[0]['source_asset_id'] = source.asset_id
            trials.append(dict(id=trial_id, command=command, count=count, status='running', error=None,
                source_asset_id=source.asset_id, original_asset_id=project['source_asset_id'],
                dimensions=list(dimensions), steps=steps, created_at=policy.timestamp()))
            service._save(project)
        service._wake.set()
        return project

    def control(self, identity, trial_id, *, action):
        service = self.service
        if action not in {'pause', 'resume'}:
            raise ValueError('Commande d’essai inconnue.')
        with service._lock:
            project = service._load(identity)
            trial = next(t for t in project.get('fixed_trials', []) if t['id'] == trial_id)
            if trial['status'] == 'completed':
                return project
            if action == 'pause':
                if trial['status'] != 'running':
                    return project
                trial['status'] = 'pausing' if any(s['status'] in {
                    'preparing', 'queued', 'submitting', 'running', 'cancel_pending'} for s in trial['steps']) else 'paused'
            else:
                if trial['status'] != 'paused':
                    return project
                for step in trial['steps']:
                    if step['status'] in {'failed', 'cancelled'}:
                        step.update(render_request_id=policy.identity('render'), status='pending', error=None,
                                    output_asset_id=None)
                trial.update(status='running', error=None)
            service._save(project)
        service._wake.set()
        return project

    def advance(self, identity):
        service = self.service
        with service._lock:
            if service._stop.is_set():
                return
            project = service._load(identity)
            for trial in project.get('fixed_trials', []):
                if trial['status'] == 'completed':
                    continue
                before = deepcopy(trial)
                try:
                    self._advance(trial, project)
                except Exception as error:
                    trial.update(status='paused', error=str(error))
                if before != trial:
                    service._save(project)

    def _advance(self, trial, project):
        service = self.service
        step = next((s for s in trial['steps'] if s['status'] != 'succeeded'), None)
        if step is None:
            trial.update(status='completed', error=None)
            return
        attempt = None
        if step['status'] != 'pending':
            attempt = service.renderer.comparison_result(step)
        if attempt:
            self._collect(trial, step, attempt)
            return
        if trial['status'] != 'running':
            if trial['status'] == 'pausing':
                trial['status'] = 'paused'
            return
        # Store intent before queueing; a lost acknowledgement reuses this exact request.
        step['status'] = 'preparing'
        service._save(project)
        try:
            attempt = service.renderer.queue_comparison(step)
        except Exception:
            attempt = service.renderer.comparison_result(step)
            if attempt is None:
                raise
        self._collect(trial, step, attempt)

    def _collect(self, trial, step, attempt):
        service = self.service
        service._comparison_result(step, attempt)
        if step['status'] == 'succeeded':
            actual = service.images.dimensions(service.assets.read_bytes(step['output_asset_id']))
            if list(actual) != trial['dimensions']:
                step.update(status='failed', rejected_asset_id=step['output_asset_id'], output_asset_id=None,
                    error='Le moteur a renvoyé des dimensions différentes de celles demandées.')
            elif step['index'] == trial['count']:
                trial.update(status='completed', error=None)
                return
            else:
                trial['steps'][step['index']]['source_asset_id'] = step['output_asset_id']
        if step['status'] in {'failed', 'cancelled'}:
            trial.update(status='paused', error=step.get('error') or 'Rendu interrompu. Tu peux reprendre.')
        elif trial['status'] == 'pausing' and step['status'] == 'succeeded':
            trial['status'] = 'paused'
