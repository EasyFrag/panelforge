"""Small dance workshop; execution remains in the shared H3 render service."""
from dataclasses import replace
from uuid import uuid4

from panelforge.domain.dance import DanceReference
from panelforge.domain.h3_render import H3RenderProject, H3RenderInputMode
from .dance_prompting import default_prompt, validate_prompt
from .prompt_lab import CompletionRequest


class DanceService:
    def __init__(self, render):
        self.render = render
        self.assets, self.media = render.assets, render.dance_media

    def get(self, project_id):
        project = self.render.get(project_id)
        if project.dance_reference is None:
            raise ValueError('Ce projet ne fait pas partie de l’atelier Danse.')
        return project

    def list(self):
        return [p for p in self.render.projects.list(10000) if p.dance_reference][:100]

    def import_video(self, content):
        if not content or len(content) > 256 * 1024 * 1024:
            raise ValueError('Choisissez une vidéo de moins de 256 Mio.')
        info = self.media.inspect(content)
        if info['duration_seconds'] < 124 / 24:
            raise ValueError('La vidéo doit durer au moins 5,2 secondes.')
        asset = self.assets.create(content, media_type='video/mp4')
        return {'asset_id': asset.asset_id, **info}

    def create(self, *, image, video_asset_id, start, duration, keep_audio, title):
        source = self.assets.get(video_asset_id)
        if source.media_type != 'video/mp4':
            raise ValueError('La référence doit être une vidéo importée.')
        photo = self.media.image(image)
        clip, info = self.media.prepare(self.assets.read_bytes(video_asset_id), start=start, duration=duration)
        project_id = 'dance-' + uuid4().hex
        image_asset = self.assets.create(photo, media_type='image/png', source_run_id=project_id)
        clip_asset = self.assets.create(clip, media_type='video/mp4', source_run_id=project_id)
        ref = DanceReference(source_asset_id=video_asset_id, clip_asset_id=clip_asset.asset_id,
                             label=title.strip()[:120] or 'Nouvelle danse', start_seconds=start,
                             duration_seconds=info['duration_seconds'], frame_count=info['frame_count'],
                             has_audio=info['has_audio'], keep_audio=keep_audio)
        return self.render.projects.create(H3RenderProject(
            project_id=project_id, source_session_id=project_id, source_prompt_revision_id='dance:1.0.0',
            model_id='dance-template:1.0.0', input_mode=H3RenderInputMode.REF2VA,
            current_prompt=default_prompt(has_audio=ref.has_audio and ref.keep_audio),
            reference_asset_ids=(image_asset.asset_id,), reference_labels=('Personnage et décor',),
            dance_reference=ref))

    def save_prompt(self, project_id, prompt):
        with self.render._lock:
            project = self.get(project_id)
            ref = project.dance_reference
            prompt = validate_prompt(prompt, has_audio=ref.has_audio and ref.keep_audio)
            return self.render.projects.save(replace(project, current_prompt=prompt))

    def polish(self, project_id, *, prompt, instruction, model_id):
        project = self.get(project_id)
        ref = project.dance_reference
        prompt = validate_prompt(prompt, has_audio=ref.has_audio and ref.keep_audio)
        if not model_id or not instruction.strip():
            raise ValueError('Choisissez le modèle et indiquez l’ajustement souhaité.')
        result = self.render.gateway.complete(CompletionRequest(
            model_id=model_id, operation_id='dance.prompt.polish', max_tokens=4096,
            system_prompt='Edit a concise MiniMax H3 dance-transfer prompt. Return only the complete English prompt, with the same six section headers and reference labels. Picture 1 controls character identity, outfit, environment, framing and lighting; Video 1 controls choreography and timing only. Keep one continuous Shot 1. Audio 1, when present, is the original excerpt soundtrack. Never invent timestamped choreography, new references, camera moves, dialogue or a story. The reference media are not attached: do not claim to have seen them. Apply only the user adjustment, preserving these source roles. Avoid repetition and contradictory preservation instructions.',
            user_prompt=f'CURRENT PROMPT\n{prompt}\n\nADJUSTMENT\n{instruction.strip()[:4000]}',
            trace_context={'project_id': project_id, 'prompt_version': '1.0.0'}))
        if result.finish_reason == 'length':
            raise ValueError('Le modèle a tronqué sa proposition. Le prompt actuel est conservé.')
        revised = validate_prompt(result.content.strip(), has_audio=ref.has_audio and ref.keep_audio)
        # Return a proposal; the user can compare or discard before saving/rendering.
        return revised

    def finalize(self, project_id, attempt_id, megapixels):
        with self.render._lock:
            project = self.get(project_id)
            attempt = project.attempt(attempt_id)
            return self.render.prepare_attempt(project_id, prompt=attempt.prompt,
                settings=replace(attempt.settings, megapixels=megapixels),
                initial_megapixels=attempt.initial_megapixels, music_enabled=attempt.music_enabled,
                spectrum_enabled=attempt.spectrum_enabled, video_lora=attempt.video_lora,
                video_loras=attempt.video_loras, force_upscale=attempt.force_upscale,
                recipe_id=attempt.recipe.recipe_id, recipe_version=attempt.recipe.version,
                bunny=attempt.bunny, checkpoint=attempt.checkpoint,
                dance_stage='refine', source_attempt_id=attempt_id)
