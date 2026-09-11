"""User-run browser scenario: real workshop DOM/JS, fake HTTP, no models."""

import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

STATIC = Path(__file__).resolve().parents[1] / "src/panelforge/features/lab/static"


class BunnyBrowserTest(unittest.TestCase):
    def test_recipe_turbo_drafts_and_resume_in_both_workshops(self):
        self.run_scenario(multiple=False)

    def test_multiple_loras_drafts_order_forces_missing_models_and_resume(self):
        self.run_scenario(multiple=True)

    def run_scenario(self, *, multiple):
        browsers = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright").glob("chromium-*/chrome-win64/chrome.exe"))
        if not browsers:
            self.skipTest("local Chromium not installed")
        index = (STATIC / "index.html").read_text(encoding="utf-8")
        markup = ""
        for prefix in ("h3r", "ref2vr"):
            start = index.index(f'<section id="{prefix}-lab"')
            depth = 0
            for match in re.finditer(r"</?section\b[^>]*>", index[start:]):
                depth += -1 if match.group().startswith("</") else 1
                if depth == 0:
                    markup += index[start:start + match.end()]
                    break
        bootstrap = "const multiple = " + str(multiple).lower() + ";" + r"""
        const calls = [], projects = {}, sourceMode = {};
        const eros = '10Eros_Max_h3_hybrid_beta5.safetensors';
        let checkpointMissing = false, checkpointOffline = false;
        let loraMissing = false, loraOffline = false;
        const ratio = '9:16 (Portrait Widescreen)', lora = 'minmax_nsfw/Motion_Repair.safetensors';
        const combat = 'minmax_nsfw/H3_Combat_V2.safetensors', bunnyVersion = multiple ? '0.1.2' : '0.1.0';
        const ids = { 'h3-base': ['minimax-h3-latent-speed', multiple ? '0.1.5' : '0.1.3'], ref2va: ['minimax-h3-ref2v', multiple ? '0.2.3' : '0.2.1'] };
        function spec(mode, bunny) {
          const [id, version] = bunny ? ['minimax-h3-bunny', bunnyVersion] : ids[mode];
          return {checkpoint_selection: {supported: true, default_label: "Default fixture model"}, recipe: {id, version}, render_recipes: [
            {id: ids[mode][0], version: ids[mode][1], label: 'Rendu actuel'},
            {id: 'minimax-h3-bunny', version: bunnyVersion, label: 'BUNNY'}],
            defaults: {aspect_ratio: ratio, megapixels: bunny ? 0.9 : 0.2,
              initial_megapixels: bunny ? 0.9 : 0.2, duration_seconds: 10, steps: bunny ? 9 : 25, seed_locked: true},
            aspect_ratios: [ratio], limits: {initial_megapixels: {}},
            llm_models: [{model_id: 'fake'}], revision_versions: [{version: '0.2.0', label: 'Stable'}], default_revision_version: '0.2.0',
            video_lora: {models: multiple ? [combat, lora] : [lora], supported: true, defaults: {strength: 0.5, clip_last_layer: -2}},
            video_lora_stack: {supported: multiple, mode: bunny ? 'per_pass' : 'shared', defaults: {
              version: '0.1.0', enabled: bunny, clip_last_layer: bunny ? null : -2,
              entries: bunny ? [combat, lora].map(name => ({name, enabled: true, strength: 0.6, second_strength: 0.2})) : []}},
            bunny: bunny ? {model_label: mode === 'ref2va' ? 'Hybride FL2VA + REF2VA' : 'FL2VA', default_lora: lora,
              lora_first_strength: 0.6, lora_second_strength: 0.2,
              turbo_profiles: {on: {base_steps: 9, coarse_steps: 4, refine_steps: 5}, off: {base_steps: 30, coarse_steps: 25, refine_steps: 5}}} : null};
        }
        const request = async (raw, options = {}) => {
          const url = new URL(raw, 'http://fake'), body = options.body ? JSON.parse(options.body) : null;
          calls.push({url: url.pathname, body});
          if (url.pathname === '/api/h3-render/video-loras') {
            if (loraOffline) throw new Error('LoRA offline');
            return {models: loraMissing ? [combat] : [combat, lora]};
          }
          if (url.pathname === '/api/h3-render/checkpoints') {
            if (checkpointOffline) throw new Error('Bucket offline');
            return {models: checkpointMissing ? [] : [{name: eros, label: 'EROS beta5'}]};
          }
          if (url.pathname === '/api/h3-render/spec') return spec(url.searchParams.get('mode'), url.searchParams.get('recipe_id') === 'minimax-h3-bunny');
          if (url.pathname.includes('/from-session/')) {
            const source = url.pathname.split('/').at(-1), mode = sourceMode[source], id = `project-${source}`;
            projects[id] ||= {project_id: id, source_session_id: source, source_prompt_revision_id: 'revision', input_mode: mode === 'ref2va' ? 'ref2va' : 'fl2va',
              model_id: 'fake', current_prompt: 'Original prompt', attempts: [], turns: []};
            return {project: structuredClone(projects[id])};
          }
          const id = url.pathname.split('/')[4], project = projects[id];
          if (!project) throw new Error('Unexpected request ' + raw);
          if (url.pathname.endsWith('/attempts') && body) {
            project.current_prompt = body.prompt;
            project.attempts.push({attempt_id: `attempt-${project.attempts.length}`, index: project.attempts.length + 1,
              recipe: {recipe_id: body.recipe_id, version: body.recipe_version}, bunny: body.bunny, checkpoint: body.checkpoint,
              settings: body, initial_megapixels: body.initial_megapixels, video_lora: body.video_lora, video_loras: body.video_loras,
              prompt: body.prompt, effective_prompt: body.prompt, status: 'created', keyframes: []});
          } else if (url.pathname.endsWith('/start')) project.attempts.at(-1).status = 'succeeded';
          else if (url.pathname.endsWith('/resume')) project.current_prompt = project.attempts.at(-1).prompt;
          else if (options.method) throw new Error('Unexpected mutation ' + raw);
          return {project: structuredClone(project)};
        };
        window.fetch = () => { throw new Error('Real network forbidden'); };
        window.WebSocket = class { constructor() { throw new Error('No real preview in browser fixture'); } };
        window.PanelForgeLabCore = {request, observeRenderAttempts() {}};
        window.PanelForgeModelPicker = {populate(el) {el.innerHTML = '<option value="fake">Fake model</option>';}, select(el, id) {el.value = id;}, setDisabled() {}};
        """
        scenario = r"""
        (async () => {try {
          const check = (v, m) => {if (!v) throw new Error(m);};
          const until = async f => {for (let i = 0; i < 200 && !f(); i++) await new Promise(r => setTimeout(r, 5)); check(f(), 'timed out');};
          for (const [prefix, mode, eventName] of [['h3r', 'h3-base', 'panelforge:h3-base-context'], ['ref2vr', 'ref2va', 'panelforge:ref2v-context']]) {
            sourceMode[prefix] = mode;
            const el = key => document.getElementById(`${prefix}-${key}`);
            const change = (key, value) => {const field = el(key); if (field.type === 'checkbox') field.checked = value; else field.value = value; field.dispatchEvent(new Event('change'));};
            const input = (key, value) => {el(key).value = value; el(key).dispatchEvent(new Event('input'));};
            const pick = async value => {change('render-recipe', value); await until(() => el('render-recipe').value === value && !el('render-recipe').disabled);};
            const legacy = ids[mode].join('@'), bunny = 'minimax-h3-bunny@' + bunnyVersion;
            const rows = () => [...el('lora-stack').querySelectorAll('[data-lora-row]')];
            const control = (index, selector) => rows()[index].querySelector(selector);
            const force = (index, key, value) => {const field = control(index, `[data-lora-force="${key}"]`); field.value = value; field.dispatchEvent(new Event('input'));};
            window.dispatchEvent(new CustomEvent(eventName, {detail: {ready: true, session_id: prefix, prompt_revision_id: 'revision'}}));
            const readsBeforeOpen = calls.filter(c => c.url.endsWith('/checkpoints')).length;
            await until(() => el('render-recipe').value === legacy);
            check(calls.filter(c => c.url.endsWith('/checkpoints')).length === readsBeforeOpen, 'no eager inventory read');
            check(!el('checkpoint-panel').open && !el('checkpoint-panel').hidden, 'compact selector closed by default');
            el('checkpoint-panel').open = true;
            await until(() => [...el('checkpoint').options].some(o => o.value === eros));
            change('checkpoint', eros);
            check(el('checkpoint-summary').textContent.includes('EROS'), 'collapsed summary shows chosen model');
            el('checkpoint-panel').open = false;
            check(!el('initial-megapixels').closest('label').hidden, 'first-pass MP remains visible in both recipes');
            check(!el('initial-megapixels').disabled && !el('megapixels').disabled, 'both current resolutions editable');
            check(el('megapixels').value === '0.2' && el('initial-megapixels').value === '0.2', 'both current resolutions default to 0.2');
            check(el('seed-lock').checked, 'seed reuse defaults to checked in both workshops');
            if (multiple) {
              check(el('video-lora-profile').value === 'standard' && el('lora-stack').hidden, 'basic stays Standard');
              change('video-lora-profile', 'lora');
              el('lora-stack').querySelector('[data-lora-add]').click();
              check(rows().length === 2 && !el('lora-stack').querySelector('[data-lora-force="second_strength"]'), 'basic has two single-strength rows');
              force(0, 'strength', '0.4'); force(1, 'strength', '0.8');
              el('lora-stack').querySelector('[data-lora-clip]').click();
            }
            check(el('megapixels').closest('label').textContent.includes('MP après upscale'), 'final output field labelled explicitly');
            input('prompt', 'My edited prompt'); input('megapixels', '0.8');
            const seed = el('seed').value;
            await pick(bunny);
            check(el('prompt').value === 'My edited prompt' && el('seed').value === seed, 'prompt and seed survive switch');
            check(!el('checkpoint').value, 'new recipe starts with its default checkpoint');
            change('checkpoint', eros);
            check(el('initial-megapixels').value === '0.9' && el('megapixels').value === '0.9', 'BUNNY resolution defaults');
            check(!el('initial-megapixels').disabled && !el('megapixels').disabled, 'both BUNNY resolutions editable');
            check(!el('initial-megapixels').closest('label').textContent.includes('Fixé'), 'fixed-value hint cleared on recipe switch');
            check(el('bunny-geometry').textContent.includes('×1.000'), 'x1 geometry');
            check(el('bunny-turbo').checked && el('bunny-coarse').value === '4', 'Turbo profile default');
            check(el('bunny-turbo').getClientRects().length > 0 && !el('bunny-turbo').closest('details'), 'Turbo visible without opening a menu');
            check(el('bunny-turbo-note').textContent.includes('intègre déjà Turbo'), 'integrated Turbo checkpoint guidance');
            if (multiple) {
              check(rows().length === 2 && el('video-lora-fields').hidden, 'new controls replace legacy fields');
              check(control(0, '[data-lora-model]').value === combat && control(1, '[data-lora-model]').value === lora, 'Combat then Motion default');
              check(rows().every((row, i) => control(i, '[data-lora-force="strength"]').value === '0.6' && control(i, '[data-lora-force="second_strength"]').value === '0.2'), 'four default forces');
              force(0, 'strength', '0.75'); force(0, 'second_strength', '0.1');
              force(1, 'strength', '0.65'); force(1, 'second_strength', '0.25');
              const field = control(0, '[data-lora-force="strength"]'); field.focus();
              input('prompt', 'My edited prompt');
              check(control(0, '[data-lora-force="strength"]') === field, 'unrelated control refresh does not recreate rows');
              el('lora-stack').querySelector('[data-lora-swap]').click();
              check(control(0, '[data-lora-model]').value === lora && control(0, '[data-lora-force="second_strength"]').value === '0.25', 'swapping moves both forces');
              control(1, '[data-lora-enabled]').click();
              change('video-lora-profile', 'standard'); change('video-lora-profile', 'lora');
              check(!control(1, '[data-lora-enabled]').checked, 'profile switch preserves disabled row');
            } else check(el('video-lora-model').value === lora && el('video-lora-strength').value === '0.6' && el('bunny-lora-second').value === '0.2', 'single LoRA two forces');
            check(el('spectrum').closest('label').hidden && el('video-lora-clip').closest('label').hidden, 'unsupported controls hidden');
            change('bunny-turbo', false);
            check(el('bunny-base').value === '9' && el('bunny-coarse').value === '4' && el('bunny-refine').value === '5', 'integrated Turbo keeps fast steps');
            check(el('checkpoint').value === eros && el('seed').value === seed, 'Turbo toggle preserves checkpoint and seed');
            el('render').click();
            await until(() => projects[`project-${prefix}`].attempts.at(-1)?.status === 'succeeded' && !el('render-recipe').disabled);
            const fast = calls.filter(c => c.url === `/api/h3-render/projects/project-${prefix}/attempts`).at(-1).body;
            check(fast.checkpoint === eros && !fast.bunny.turbo_enabled && fast.bunny.base_steps === 9 && fast.bunny.coarse_steps === 4 && fast.bunny.refine_steps === 5, 'API receives integrated Turbo checkpoint with unchanged fast schedule');
            const saved = structuredClone(projects[`project-${prefix}`]);
            await pick(legacy);
            window.dispatchEvent(new CustomEvent(eventName, {detail: {ready: false}}));
            window.dispatchEvent(new CustomEvent(eventName, {detail: {project_id: saved.project_id}}));
            await until(() => el('render-recipe').value === bunny && !el('render-recipe').disabled);
            check(!el('bunny-turbo').checked && el('bunny-base').value === '9' && el('bunny-coarse').value === '4', 'reopening an integrated Turbo render restores toggle and fast steps');
            const sampling = el('bunny-controls').querySelector('details'); sampling.open = true;
            sampling.querySelector('[data-bunny-sampling="off"]').click();
            check(el('bunny-base').value === '30' && el('bunny-coarse').value === '25' && !el('bunny-turbo').checked, 'classic steps require an explicit choice independent of Turbo');
            sampling.querySelector('[data-bunny-sampling="on"]').click();
            check(el('bunny-base').value === '9' && el('bunny-coarse').value === '4' && !el('bunny-turbo').checked, 'fast steps never reenable extra Turbo');
            sampling.querySelector('[data-bunny-sampling="off"]').click();
            input('bunny-coarse', '24'); change('bunny-turbo', true); change('bunny-turbo', false);
            check(el('bunny-base').value === '30' && el('bunny-coarse').value === '24', 'custom steps unchanged by either Turbo toggle');
            change('bunny-preview', false);
            await pick(legacy);
            check(el('megapixels').value === '0.8' && el('bunny-controls').hidden, 'legacy draft restored');
            check(el('checkpoint').value === eros, 'recipe draft restores checkpoint');
            if (multiple) check(control(0, '[data-lora-force="strength"]').value === '0.4' && !el('lora-stack').querySelector('[data-lora-clip]').checked, 'basic LoRA draft isolated from Bunny');
            await pick(bunny);
            check(el('bunny-coarse').value === '24' && !el('bunny-preview').checked && !el('bunny-turbo').checked, 'BUNNY draft restored');
            check(!calls.some(c => c.url.endsWith('/attempts') && c.body?.prompt === 'My edited prompt' && c.body.recipe_id === ids[mode][0]), 'switch never renders');
            check(!el('render').disabled, 'BUNNY ready');
            el('render').click();
            await until(() => projects[`project-${prefix}`].attempts.at(-1)?.status === 'succeeded' && !el('render-recipe').disabled);
            const sent = calls.filter(c => c.url === `/api/h3-render/projects/project-${prefix}/attempts`).at(-1).body;
            check(sent.bunny.coarse_steps === 24 && sent.steps === 29 && sent.bunny.turbo_enabled === false, 'API receives sampling profile');
            check(sent.checkpoint === eros, 'selected checkpoint sent with render');
            check(sent.recipe_id === 'minimax-h3-bunny' && !sent.spectrum_enabled, 'recipe and compatible switches sent');
            if (multiple) {
              check(sent.video_lora === null && sent.video_loras.clip_last_layer === null, 'one unambiguous new contract');
              const [first, second] = sent.video_loras.entries;
              check(first.name === lora && first.strength === 0.65 && first.second_strength === 0.25 && first.enabled, 'first slot snapshot');
              check(second.name === combat && second.strength === 0.75 && second.second_strength === 0.1 && !second.enabled, 'second disabled slot snapshot');
            } else check(sent.video_lora.clip_last_layer === null, 'legacy compatible LoRA sent');
            await pick(legacy);
            [...el('attempts').querySelectorAll('button')].find(b => b.textContent === 'Reprendre prompt + réglages').click();
            await until(() => el('render-recipe').value === bunny && !el('render-recipe').disabled);
            check(el('bunny-coarse').value === '24' && !el('bunny-turbo').checked, 'resume restores saved recipe and profile');
            check(el('checkpoint').value === eros, 'resume restores saved checkpoint');
            if (multiple) {
              check(control(0, '[data-lora-model]').value === lora && !control(1, '[data-lora-enabled]').checked, 'resume restores exact stack');
              loraMissing = true; el('lora-stack').querySelector('[data-lora-refresh]').click();
              await until(() => el('lora-stack').textContent.includes('LoRA indisponible'));
              check(el('render').disabled && control(0, '[data-lora-model]').value === lora, 'missing model blocks without fallback');
              control(0, '[data-lora-enabled]').click();
              check(!el('render').disabled, 'disabled missing model does not block');
              control(0, '[data-lora-enabled]').click();
              loraOffline = true; el('lora-stack').querySelector('[data-lora-refresh]').click();
              await until(() => !el('lora-stack').querySelector('[data-lora-refresh]').disabled);
              check(control(0, '[data-lora-model]').value === lora, 'network failure preserves all settings');
              loraMissing = loraOffline = false;
              el('lora-stack').querySelector('[data-lora-refresh]').click();
              await until(() => !el('render').disabled);
              el('lora-stack').querySelector('[data-lora-remove]').click();
              check(rows().length === 1 && control(0, '[data-lora-model]').value === combat, 'remove only selected slot');
            }
            checkpointMissing = true;
            el('checkpoint-refresh').click();
            await until(() => el('checkpoint-note').textContent.includes('indisponible'));
            check(el('checkpoint').value === eros, 'missing checkpoint does not silently fall back');
            checkpointOffline = true;
            el('checkpoint-refresh').click();
            await until(() => el('checkpoint-note').textContent.includes('offline'));
            check(el('checkpoint').value === eros, 'network error preserves selection');
            change('checkpoint', '');
            check(el('checkpoint-summary').textContent.includes('Par défaut'), 'explicit reset restores default');
            checkpointMissing = checkpointOffline = false;
          }
          check(!calls.some(c => c.url.includes('chat') || c.url.includes('llm')), 'no LLM call');
          if (multiple) {
            const host = document.createElement('div'); host.id = 'legacy-fixture-lora-stack'; document.body.append(host);
            const editor = window.PanelForgeH3Loras.mount('legacy-fixture', {request, onChange() {}});
            const fixture = spec('h3-base', true);
            editor.configure(fixture.video_lora_stack, fixture.video_lora);
            editor.restoreAttempt({video_lora: {name: lora, strength: 0.45, clip_last_layer: null}, bunny: {lora_second_strength: 0.15}});
            check(editor.value.entries.length === 1 && editor.value.entries[0].name === lora && editor.value.entries[0].second_strength === 0.15, 'legacy single-LoRA resume never appends the new defaults');
            editor.restoreAttempt({video_lora: null});
            check(!editor.value.enabled && editor.value.entries.length === 0, 'legacy Standard resume stays empty');
          }
          document.getElementById('result').textContent = 'PASS';
        } catch (e) {document.getElementById('result').textContent = 'FAIL: ' + e.stack;}})();
        """
        source = "\n".join((STATIC / name).read_text(encoding="utf-8") for name in ("h3-checkpoints.js", "h3-loras.js", "h3-render-lab.js"))
        html = '<meta charset="utf-8"><pre id="result">PENDING</pre>' + markup
        html += '<script>' + bootstrap + '</script><script>' + source + '</script><script>' + scenario + '</script>'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "bunny.html"
            page.write_text(html, encoding="utf-8")
            result = subprocess.run([str(browsers[-1]), "--headless", "--disable-gpu", "--disable-background-networking", "--no-first-run",
                "--virtual-time-budget=10000", f"--user-data-dir={root / 'profile'}", "--dump-dom", page.as_uri()],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr[-1000:])
            self.assertIn('<pre id="result">PASS</pre>', result.stdout)
