"""Short source-role contract for dance; no invented choreography or timestamps."""
import re

VERSION = '1.0.0'
FIELDS = ('subject_definitions', 'summary', 'retention_analysis', 'detailed_description',
          'overall_soundscape', 'non_diegetic_music')


def default_prompt(has_audio):
    audio_definition = '\n<Audio 1> is the synchronized soundtrack of <Video 1>.' if has_audio else ''
    audio_retention = '\n<Audio 1>: fully_copy - retain the original soundtrack and its timing.' if has_audio else ''
    return f'''subject_definitions:
<Subject 1> is the character in <Picture 1>, which defines identity, proportions, outfit and visual style. Its dance movement comes from <Video 1>.
<Subject 2> is the environment in <Picture 1>, defining background, layout, framing and lighting.
<Video 1> provides only the performer's choreography, movement sequence and timing.{audio_definition}

summary:
[reference generation{' + audio reuse' if has_audio else ''}] Animate <Subject 1> dancing inside <Subject 2>, transferring the performance from <Video 1> into the visual world of <Picture 1>.

retention_analysis:
<Subject 1>: fully_preserved - retain the character's appearance and proportions from <Picture 1> throughout the movement.
<Subject 2>: fully_preserved - retain the photo's environment, lighting and framing.
<Video 1>: attribute_transfer - transfer the dance and its timing only; its performer identity, background and camera movement are not copied.{audio_retention}

detailed_description:
The visual style, composition and lighting follow <Picture 1>.
[Shot 1] A single continuous shot, with the camera fixed in the viewpoint of <Picture 1>. <Subject 1> performs the choreography of the dancer in <Video 1>, in the same order and at the same pace, naturally adapted to the character's proportions. Feet remain supported by the floor in <Subject 2>; the body and limbs stay coherent through turns and self-occlusion. Keep the character inside the frame, with space for the supplied movement. Preserve the photo's surroundings throughout. Do not introduce other people, choreography, cuts or text.

overall_soundscape:
{'Reuse <Audio 1> in sync with the performance, without additional voices or sound effects.' if has_audio else 'No dialogue or additional sound effects.'}

non_diegetic_music:
{'Keep the music already present in <Audio 1>; no additional music.' if has_audio else 'N/A'}'''


def validate_prompt(text, has_audio):
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 60000:
        raise ValueError('Le prompt de danse est vide ou trop long.')
    headers = re.findall(r'(?m)^([a-z_]+):\s*', text)
    if headers != list(FIELDS):
        raise ValueError('Conservez les six rubriques du prompt de danse.')
    allowed = {('Subject', '1'), ('Subject', '2'), ('Picture', '1'), ('Video', '1')}
    if has_audio:
        allowed.add(('Audio', '1'))
    labels = set(re.findall(r'<(Subject|Picture|Video|Audio)\s+(\d+)>', text))
    if any(not re.fullmatch(r'<(Subject|Picture|Video|Audio) [1-9]\d*>', label)
           for label in re.findall(r'<[^<>]+>', text)):
        raise ValueError('Utilisez les balises natives, par exemple <Picture 1> et <Video 1>.')
    if not {('Picture', '1'), ('Video', '1')} <= labels or labels - allowed:
        raise ValueError('Le prompt doit utiliser uniquement la photo et l’extrait réellement fournis.')
    if has_audio and ('Audio', '1') not in labels:
        raise ValueError('Conservez le lien au son original <Audio 1>.')
    if re.findall(r'\[Shot\s+\d+\]', text) != ['[Shot 1]']:
        raise ValueError('La danse utilise un seul plan continu.')
    return text.strip()
