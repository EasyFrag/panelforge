"""Durable localization and composition shared by automatic steps and local additions."""
from copy import deepcopy
import json

from panelforge.domain import image_journeys as journey
from panelforge.domain.image_journey_masks import validate_plan
from . import image_journey_mask_prompting as prompting
from .prompt_lab import CompletionRequest, ImageInput, StreamEventKind
from .revised_documents import strip_markdown_fence


class ImageJourneyProtection:
    def __init__(self, service, compositor):
        self.service, self.compositor = service, compositor

    def advance(self, identity, step_id, *, manual=False):
        service = self.service

        def find(project):
            return next(s for s in project['image_operations' if manual else 'steps'] if s['id'] == step_id)

        def checkpoint(**values):
            with service._lock:
                project = service._load(identity)
                find(project).setdefault('protection', {}).update(values)
                service._save(project)

        with service._lock:
            project = service._load(identity)
            step = deepcopy(find(project))
            # A paused automatic journey may select a different vision model before retrying.
            model_id = step['progression_model_id'] if manual else project['progression_model_id']
        if self.compositor is None:
            raise ValueError('Le composant de masque automatique n’est pas configuré.')
        source = service.assets.read_bytes(step['source_asset_id'])
        raw_image = service.assets.read_bytes(step['raw_output_asset_id'])
        plan = step.get('protection', {}).get('plan')
        if plan is None:
            call_id, raw = None, ''
            analysis_id = journey.identity('mask')
            checkpoint(status='analyzing', analysis_id=analysis_id, model_id=model_id,
                       policy_version=prompting.VERSION, started_at=journey.timestamp(), error=None)
            try:
                images = []
                for content, label in ((source, 'BEFORE — source exacte'), (raw_image, 'GENERATED — rendu brut')):
                    images.append(ImageInput('image/png', content, label))
                request = CompletionRequest(model_id=model_id, system_prompt=prompting.SYSTEM,
                    user_prompt=json.dumps(dict(action=step['action'], dimensions=service.images.dimensions(source)), ensure_ascii=False),
                    images=tuple(images), max_tokens=16000, include_reasoning=False,
                    operation_id=prompting.VERSION, output_schema=prompting.SCHEMA,
                    trace_context=dict(project_id=identity, step_id=step_id, analysis_id=analysis_id))
                completed = False
                for event in service.gateway.stream(request):
                    if event.kind is StreamEventKind.DELTA:
                        raw += event.text
                    if event.kind in {StreamEventKind.COMPLETED, StreamEventKind.TRUNCATED}:
                        if event.result:
                            raw, call_id = event.result.content, event.result.call_id
                        if event.kind is StreamEventKind.TRUNCATED:
                            raise ValueError('Le calcul du masque a été tronqué. Reprendre réutilisera le rendu existant.')
                        completed = True
                        break
                if not completed:
                    raise ValueError('Le calcul du masque a été interrompu. Reprendre réutilisera le rendu existant.')
                plan = validate_plan(json.loads(strip_markdown_fence(raw)))
                checkpoint(status='localized', plan=plan, call_id=call_id, raw=raw[:100000])
                service._report(call_id, True)
            except Exception as error:
                checkpoint(status='failed', call_id=call_id, raw=raw[:100000], error=str(error))
                service._report(call_id, False, error)
                raise
        # A failed/restarted composition reuses the saved plan and the same raw render.
        result = self.compositor.compose(source, raw_image, plan)
        mask = service.assets.create(result.mask_png, media_type='image/png', source_run_id=identity)
        output = service.assets.create(result.image_png, media_type='image/png', source_run_id=identity)
        with service._lock:
            project = service._load(identity)
            current = find(project)
            current.update(output_asset_id=output.asset_id,
                           output_dimensions=list(service.images.dimensions(result.image_png)))
            current.setdefault('protection', {}).update(status='completed', mask_asset_id=mask.asset_id,
                coverage=result.coverage, finished_at=journey.timestamp(), error=None)
            if manual:
                current['phase'] = 'reviewing'
            else:
                project['phase'] = 'reviewing'
                service._settle_pause(project)
            service._save(project)
