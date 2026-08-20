import sys
import tempfile
import unittest
import re
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.application import ChangeViewRunner
from panelforge.features.lab.web import create_app
from panelforge.infrastructure.presets import (
    ChangeViewPresetRecipe,
    load_change_view_preset,
)
from panelforge.infrastructure.storage import LocalAssetStore, LocalRunStore


PRESET_DIRECTORY = (
    PROJECT_ROOT
    / "workflows"
    / "character.change_view"
    / "qwen-edit-2511-multiple-angles"
    / "0.2.0"
)
PNG = b"\x89PNG\r\n\x1a\nimage-content"


@dataclass(frozen=True)
class Uploaded:
    workflow_value: str = "panelforge/uploaded.png"


class ImmediateComfy:
    def __init__(self):
        self.submitted = []

    def upload_image(self, content, *, filename, subfolder=""):
        return Uploaded()

    def submit_workflow(self, workflow):
        self.submitted.append(workflow)
        return "prompt-1"

    def get_history(self, prompt_id):
        return {
            prompt_id: {
                "status": {"status_str": "success", "completed": True},
                "outputs": {
                    "9": {
                        "images": [
                            {
                                "filename": "result.png",
                                "subfolder": "",
                                "type": "output",
                            }
                        ]
                    }
                },
            }
        }

    def download_output(self, *, filename, subfolder="", folder_type="output"):
        return PNG


class FakeModelRuntime:
    def __init__(self):
        self.unload_calls = 0

    def unload_all(self):
        self.unload_calls += 1


class LabWebTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        assets = LocalAssetStore(self.temporary_directory.name)
        self.assets = assets
        runs = LocalRunStore(self.temporary_directory.name)
        recipe = ChangeViewPresetRecipe(load_change_view_preset(PRESET_DIRECTORY))
        self.comfy = ImmediateComfy()
        self.model_runtime = FakeModelRuntime()
        runner = ChangeViewRunner(
            recipe=recipe,
            comfy=self.comfy,
            assets=assets,
            runs=runs,
        )
        self.client = TestClient(
            create_app(runner, model_runtime=self.model_runtime)
        )

    def tearDown(self):
        self.client.close()
        self.temporary_directory.cleanup()

    def test_serves_page_and_curated_recipe_spec(self):
        page = self.client.get("/")
        script = self.client.get("/static/lab.js")
        spec = self.client.get("/api/change-view/spec")

        self.assertEqual(page.status_code, 200)
        self.assertIn("PanelForge", page.text)
        self.assertIn('id="release-vram"', page.text)
        self.assertIn("/static/lab.js?v=20260815.1", page.text)
        self.assertEqual(page.headers["cache-control"], "no-store")
        self.assertEqual(script.status_code, 200)
        self.assertEqual(script.headers["cache-control"], "no-store")
        self.assertIn("/api/change-view/preview", script.text)
        self.assertIn("/api/model-runtime/unload", script.text)
        self.assertIn('preferredPromptModelId = "Qwen3.8-27B"', script.text)
        self.assertIn('includes("qwen3.8-27b")', script.text)
        self.assertIn('includes("qwen3.6-27b")', script.text)
        self.assertIn("PanelForgeModelPicker", script.text)
        self.assertIn('data-lab-view="ref2v-direct"', page.text)
        self.assertIn('id="ref2vd-workspace"', page.text)
        self.assertIn('id="ref2vd-image-input" type="file"', page.text)
        self.assertIn("multiple", page.text)
        self.assertIn("/static/lab.css?v=20260820.1", page.text)
        self.assertIn("/static/ref2v-direct.js?v=20260816.4", page.text)
        direct_script = self.client.get("/static/ref2v-direct.js")
        prompt_script = self.client.get("/static/prompt-lab.js")
        self.assertEqual(direct_script.status_code, 200)
        self.assertIn('const preferredCookbookVersion = "0.3.3"', direct_script.text)
        self.assertIn('const multishotCookbookId = "minimax.h3.ref2v.direct.multishot"', direct_script.text)
        self.assertIn('2–6 plans automatiques', direct_script.text)
        self.assertIn('for (let index = 0; index < shots.length; index += 1)', direct_script.text)
        self.assertIn('return `${cookbook.id}@${cookbook.version}`', direct_script.text)
        self.assertIn('id="ref2vd-cookbook"', page.text)
        self.assertIn('id="ref2vd-multishot-summary"', page.text)
        self.assertIn("shot.primary_action", direct_script.text)
        self.assertIn("shot.observable_end_state", direct_script.text)
        self.assertIn("shot.active_picture_labels", direct_script.text)
        self.assertIn("plan.final_state.final_hold_ms", direct_script.text)
        self.assertIn("function cameraSummary(camera)", direct_script.text)
        self.assertIn("camera.target_clause", direct_script.text)
        self.assertIn('typeof shot !== "object"', direct_script.text)
        self.assertIn("function resetCookbookSelection()", direct_script.text)
        self.assertIn("const preservedCookbook = activeCookbookSpec() || state.cookbook", direct_script.text)
        self.assertNotIn("state.composition = null;\n    resetCookbookSelection();", direct_script.text)
        self.assertIn("const selectedCookbook = compositionReference || state.cookbook", direct_script.text)
        self.assertIn("if (selectedCookbook) showCookbookSelection(selectedCookbook)", direct_script.text)
        self.assertIn('bindings: { references:', direct_script.text)
        self.assertNotIn("/references/${", direct_script.text)
        self.assertNotIn("crypto.randomUUID", direct_script.text)
        self.assertEqual(prompt_script.status_code, 200)
        self.assertIn("/static/prompt-lab.js?v=20260820.1", page.text)
        self.assertIn('data-lab-view="archives"', page.text)
        self.assertIn('id="archives-workspace"', page.text)
        self.assertIn('data-archive-view="i2v"', page.text)
        self.assertIn('data-archive-view="ref2v"', page.text)
        self.assertNotIn('data-lab-view="i2v"', page.text)
        self.assertNotIn('data-lab-view="ref2v"', page.text)
        self.assertIn('class="prompt-workspace i2v-workspace legacy-archive"', page.text)
        self.assertIn('id="ref2vd-mode-warning"', page.text)
        self.assertIn('id="ref2vd-role-warning"', page.text)
        self.assertIn('id="ref2vd-role-confirmation"', page.text)
        self.assertIn('id="ref2vd-role-help"', page.text)
        self.assertIn('id="ref2vd-role-help-body"', page.text)
        self.assertIn('aria-label="Ce que contrôle chaque rôle d’image"', page.text)
        self.assertIn("function renderRoleHelp()", direct_script.text)
        for expected in (
            "État visible complet à 0,00 s",
            "Identité, apparence stable",
            "État visuel d’un instant intermédiaire",
            "Environnement, matériaux, géométrie spatiale",
            "Composition, cadrage et équilibre spatial",
            "Style visuel, palette, texture",
            "Mécanique de l’action, dynamique corporelle",
            "État visuel final exact",
        ):
            self.assertIn(expected, direct_script.text)
        self.assertIn("function lockLegacyArchives()", prompt_script.text)
        self.assertIn("new MutationObserver(lockTextareas)", prompt_script.text)
        self.assertIn("if (!textarea.readOnly) textarea.readOnly = true", prompt_script.text)
        self.assertIn('button.id.endsWith("-copy-prompt")', prompt_script.text)
        self.assertIn("function intentionRequestsMultipleShots(value)", direct_script.text)
        self.assertIn("function invalidateRoleConfirmation()", direct_script.text)
        self.assertIn("state.rolesConfirmed", direct_script.text)
        self.assertIn("if (!state.rolesConfirmed)", direct_script.text)
        self.assertIn("state.rolesConfirmed = false", direct_script.text)
        self.assertIn("allAdditionalReferencesAreSubjects", direct_script.text)
        self.assertIn("function playCompletionTone()", prompt_script.text)
        self.assertIn('oscillator.type = "triangle"', prompt_script.text)
        self.assertIn("frequency: 660", prompt_script.text)
        self.assertIn("frequency: 880", prompt_script.text)
        self.assertIn("exponentialRampToValueAtTime(0.08", prompt_script.text)
        self.assertIn('event.kind === "completed"', prompt_script.text)
        ids = re.findall(r'\bid="([^"]+)"', page.text)
        self.assertEqual(len(ids), len(set(ids)), "HTML IDs must remain unique")
        self.assertEqual(spec.status_code, 200)
        payload = spec.json()
        self.assertEqual(payload["recipe"]["version"], "0.2.0")
        self.assertEqual(payload["prompt_policy"], "locked")
        self.assertEqual(
            payload["controls"]["multiple_angles_lora_strength"]["maximum"],
            2.0,
        )
        self.assertIsInstance(payload["controls"]["seed"]["default"], str)

    def test_serves_the_parallel_direct_i2v_workspace(self):
        page = self.client.get("/")
        script = self.client.get("/static/i2v-direct.js")
        prompt_script = self.client.get("/static/prompt-lab.js")

        self.assertEqual(page.status_code, 200)
        self.assertEqual(script.status_code, 200)
        self.assertIn('data-lab-view="i2v-direct"', page.text)
        self.assertIn('id="i2vd-workspace"', page.text)
        self.assertIn('id="i2vd-image-input" type="file"', page.text)
        self.assertNotIn(
            'id="i2vd-image-input" type="file" accept="image/png,image/jpeg,image/webp" multiple',
            page.text,
        )
        self.assertIn('id="i2vd-brief-step"', page.text)
        self.assertIn('id="i2vd-plan-step"', page.text)
        self.assertIn('id="i2vd-prompt-step"', page.text)
        self.assertIn('/static/i2v-direct.js?v=20260816.2', page.text)
        self.assertIn('const preferredCookbookVersion = "0.2.0"', script.text)
        self.assertIn('elements.cookbook.value = compositionReference', script.text)
        self.assertIn('const selectedCookbook = directCookbooks().find(', script.text)
        self.assertIn('const profileId = "minimax.h3.i2v.direct"', script.text)
        self.assertIn('const cookbookId = "minimax.h3.i2v.direct"', script.text)
        self.assertIn('item.target_mode === "i2v_direct"', script.text)
        self.assertIn('body.append("roles", "first_frame")', script.text)
        self.assertIn('body.append("usages", "first_frame")', script.text)
        self.assertIn('bindings: { first_frame: [reference.id] }', script.text)
        self.assertIn("beat-sheet/reconcile/stream", script.text)
        self.assertIn('i2vDirect: $("#i2vd-workspace")', prompt_script.text)
        self.assertIn(
            'elements.i2vDirect.hidden = view !== "i2v-direct"',
            prompt_script.text,
        )

    def test_serves_video_lab_and_ref2v_prefill_bridge(self):
        page = self.client.get("/")
        script = self.client.get("/static/video-lab.js")
        ref2v_script = self.client.get("/static/ref2v-direct.js")
        navigation = self.client.get("/static/prompt-lab.js")

        self.assertEqual(page.status_code, 200)
        self.assertEqual(script.status_code, 200)
        self.assertIn('data-lab-view="video-lab"', page.text)
        self.assertIn('id="video-lab-workspace"', page.text)
        self.assertIn('id="video-lab-images"', page.text)
        self.assertIn('id="video-lab-preview"', page.text)
        self.assertIn('id="video-lab-preview-video"', page.text)
        self.assertIn('autoplay muted loop playsinline', page.text)
        self.assertIn('id="video-lab-output"', page.text)
        self.assertNotIn('id="video-lab-play-with-sound"', page.text)
        self.assertNotIn('id="video-lab-output-diagnostic"', page.text)
        self.assertIn('preload="metadata"', page.text)
        self.assertIn('id="video-lab-cancel"', page.text)
        self.assertIn('id="video-lab-history-list"', page.text)
        self.assertIn('value="h3-balanced"', page.text)
        self.assertIn('value="2:3 (Portrait Photo)"', page.text)
        self.assertIn('min="5" max="15"', page.text)
        self.assertIn('Modifier la durée ne réécrit pas les timestamps du prompt.', page.text)
        self.assertIn('/static/video-lab.js?v=20260816.6', page.text)

        self.assertIn('request("/api/video-lab/runs"', script.text)
        self.assertIn('/start`, { method: "POST" }', script.text)
        self.assertIn('/cancel`, { method: "POST" }', script.text)
        self.assertIn('body.append("source_asset_ids"', script.text)
        self.assertIn('body.append("source_labels"', script.text)
        self.assertIn('body.append("images"', script.text)
        self.assertIn('function runId(run)', script.text)
        self.assertIn('run.id || run.run_id', script.text)
        self.assertIn('new WebSocket(websocketUrl(run))', script.text)
        self.assertIn('type === "panelforge_preview_status"', script.text)
        self.assertIn("window.setTimeout(finish, 12000)", script.text)
        self.assertIn('playbackUrl.searchParams.set("_pf_media"', script.text)
        self.assertNotIn('function playOutputWithSound()', script.text)
        self.assertNotIn('elements.output.webkitAudioDecodedByteCount', script.text)
        self.assertNotIn('elements.output.audioTracks', script.text)
        self.assertIn('buffer.slice(8)', script.text)
        self.assertIn('imageFormat === 3 ? "image/webp"', script.text)
        self.assertIn('view.getUint32(0, false) !== 1', script.text)
        self.assertIn('type === "kj_preview_override"', script.text)
        self.assertIn('previewBlobFromBase64(data.image, mime)', script.text)
        self.assertIn('startsWith("video/")', script.text)
        self.assertIn('renderSocketProgress(data.step, data.total)', script.text)
        self.assertIn('renderSelect(elements.megapixels', script.text)
        self.assertIn('state.busy || isActive(state.activeRun)', script.text)
        self.assertIn('elements.historyList.querySelectorAll("button")', script.text)
        self.assertGreaterEqual(script.text.count('if (state.busy || isActive(state.activeRun)) return;'), 3)
        self.assertIn('panelforge.video-lab.seed-lock', script.text)
        self.assertIn('eventExecutionId !== activeExecutionId', script.text)
        self.assertIn('cancel_pending: "Annulation à confirmer"', script.text)

        self.assertIn('id="ref2vd-send-video-lab"', page.text)
        self.assertIn('window.PanelForgeVideoLab.prefill({', ref2v_script.text)
        self.assertIn('prompt: visiblePrompt', ref2v_script.text)
        self.assertIn('duration_seconds: planDurationSeconds', ref2v_script.text)
        self.assertIn('!prompt.active_revision_id', ref2v_script.text)
        self.assertIn('videoLab: $("#video-lab-workspace")', navigation.text)
        self.assertIn('PanelForgeLabNavigation', navigation.text)

    def test_asset_content_supports_full_and_partial_byte_reads(self):
        content = b"0123456789"
        asset = self.assets.create(content, media_type="video/mp4")
        url = f"/api/assets/{asset.asset_id}/content"

        full = self.client.get(url)
        bounded = self.client.get(url, headers={"Range": "bytes=2-5"})
        open_ended = self.client.get(url, headers={"Range": "bytes=7-"})
        suffix = self.client.get(url, headers={"Range": "bytes=-3"})
        clamped = self.client.get(url, headers={"Range": "bytes=8-99"})

        self.assertEqual(full.status_code, 200)
        self.assertEqual(full.content, content)
        self.assertEqual(full.headers["accept-ranges"], "bytes")
        self.assertEqual(full.headers["content-type"], "video/mp4")
        for response, expected, content_range in (
            (bounded, b"2345", "bytes 2-5/10"),
            (open_ended, b"789", "bytes 7-9/10"),
            (suffix, b"789", "bytes 7-9/10"),
            (clamped, b"89", "bytes 8-9/10"),
        ):
            self.assertEqual(response.status_code, 206)
            self.assertEqual(response.content, expected)
            self.assertEqual(response.headers["content-range"], content_range)
            self.assertEqual(response.headers["accept-ranges"], "bytes")
            self.assertEqual(response.headers["content-type"], "video/mp4")
            self.assertEqual(response.headers["content-length"], str(len(expected)))

    def test_asset_content_rejects_invalid_or_unsatisfiable_ranges(self):
        asset = self.assets.create(b"0123456789", media_type="video/mp4")
        url = f"/api/assets/{asset.asset_id}/content"

        for value in ("bytes=10-", "bytes=5-2", "bytes=-0", "bytes=0-1,4-5"):
            with self.subTest(value=value):
                response = self.client.get(url, headers={"Range": value})
                self.assertEqual(response.status_code, 416)
                self.assertEqual(response.content, b"")
                self.assertEqual(response.headers["content-range"], "bytes */10")
                self.assertEqual(response.headers["accept-ranges"], "bytes")

    def test_direct_creative_freedom_uses_discrete_modes(self):
        page = self.client.get("/")
        scripts = (
            self.client.get("/static/i2v-direct.js"),
            self.client.get("/static/ref2v-direct.js"),
        )

        expected_options = (
            ("0", "Factuel strict"),
            ("35", "Conservateur"),
            ("50", "Équilibré"),
            ("80", "Cinématographique"),
            ("100", "Exploratoire"),
        )
        for prefix in ("i2vd", "ref2vd"):
            match = re.search(
                rf'<select id="{prefix}-freedom"[^>]*>(.*?)</select>',
                page.text,
                re.DOTALL,
            )
            self.assertIsNotNone(match)
            options = re.findall(r'<option value="(\d+)"[^>]*>([^<]+)</option>', match.group(1))
            self.assertEqual(options, list(expected_options))
            self.assertIn('<option value="35" data-description=', match.group(1))
            self.assertIn('selected>Conservateur</option>', match.group(1))
            self.assertNotIn(f'id="{prefix}-freedom" type="range"', page.text)
            self.assertNotIn(f'id="{prefix}-freedom-value"', page.text)
        self.assertEqual(page.text.count("Agit sur le Brief ; son effet sur le Plan et le prompt final est indirect."), 2)

        for script in scripts:
            self.assertEqual(script.status_code, 200)
            self.assertIn("function setFreedom(value)", script.text)
            self.assertIn('option[data-legacy-freedom]', script.text)
            self.assertIn('legacyOption.dataset.legacyFreedom = "true"', script.text)
            self.assertIn('valeur historique ${normalized}/100', script.text)
            self.assertIn('setFreedom(session.active_brief.creative_freedom ?? 35)', script.text)
            self.assertIn('setFreedom(35)', script.text)
            self.assertIn('elements.freedom.addEventListener("change"', script.text)
            self.assertIn('creative_freedom: Number(elements.freedom.value)', script.text)
            self.assertNotIn("freedomValue", script.text)

    def test_exposes_shared_quick_mode_for_both_direct_workspaces(self):
        page = self.client.get("/")
        quick = self.client.get("/static/quick-pipeline.js")
        i2v = self.client.get("/static/i2v-direct.js")
        ref2v = self.client.get("/static/ref2v-direct.js")

        self.assertEqual(quick.status_code, 200)
        self.assertIn('/static/quick-pipeline.js?v=20260813.1', page.text)
        self.assertIn('id="i2vd-quick-mode" type="checkbox"', page.text)
        self.assertIn('id="ref2vd-execution-mode"', page.text)
        self.assertIn('id="ref2vd-execution-mode-control"', page.text)
        self.assertIn('>Orchestration', page.text)
        self.assertIn('<option value="supervised" selected>', page.text)
        self.assertIn('<option value="quick">', page.text)
        self.assertIn('3 appels LLM', page.text)
        self.assertNotIn('<option value="super_fast">', page.text)
        for prefix in ("i2vd", "ref2vd"):
            self.assertIn(f'id="{prefix}-quick-status"', page.text)
            self.assertIn(f'id="{prefix}-quick-resume"', page.text)
            self.assertIn(f'id="{prefix}-show-reasoning" type="checkbox"', page.text)
            self.assertIn(f'id="{prefix}-reasoning-panel"', page.text)
        ordered_actions = (
            'action: "generateBrief"',
            'action: "approveBrief"',
            'action: "generatePlan"',
            'action: "approvePlan"',
            'action: "generatePrompt"',
            'action: "approvePrompt"',
        )
        positions = [quick.text.index(action) for action in ordered_actions]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('if (snapshot()[step.complete]) continue', quick.text)
        self.assertIn('status: "interrupted"', quick.text)
        self.assertNotIn("reconcile", quick.text)
        for script in (i2v.text, ref2v.text):
            self.assertIn("quickPipeline.runDirect", script)
            self.assertIn('generateBrief: () => streamBrief(false)', script)
            self.assertIn('approvePrompt: () => documentAction("final-prompt", "approve")', script)
            self.assertIn("!(documentState.validation_errors || []).length", script)
            self.assertNotIn("validation_warnings || []", script.split("function quickSnapshot()", 1)[1].split("function renderQuickStatus()", 1)[0])
            self.assertIn("reasoningTrace.streamUrl", script)
        self.assertIn("async function runSuperFastMode", ref2v.text)
        self.assertIn("/super-fast/stream", ref2v.text)
        self.assertIn("minimax.h3.ref2v.direct.multishot.superfast", ref2v.text)
        self.assertIn("Multi-plan direct · 1 appel · expérimental", ref2v.text)
        self.assertIn("Multi-plan structuré · 2–6 plans", ref2v.text)
        self.assertIn("Mono-plan · standard", ref2v.text)
        self.assertIn("available.push(superFastCookbookSpec())", ref2v.text)
        self.assertIn("if (created && requestedDirectRecipe) await runSuperFastMode()", ref2v.text)
        self.assertIn("else if (created && requestedMode === \"quick\") await runQuickMode()", ref2v.text)
        self.assertIn("elements.executionModeControl.hidden = recipeOwnsExecution", ref2v.text)
        self.assertIn("state.cookbook = isSuperFastReference(preservedCookbook)", ref2v.text)
        self.assertNotIn('elements.executionMode.value === "super_fast"', ref2v.text)
        self.assertIn("openedSuperFast = Boolean(", ref2v.text)
        self.assertIn("Parcours interrompu avant la validation du Prompt", ref2v.text)
        self.assertIn("completedBecameIncomplete", ref2v.text)
        self.assertIn('const superFastCookbookVersion = "0.2.0"', ref2v.text)
        self.assertIn("elements.steps.plan.hidden = superFast", ref2v.text)
        self.assertIn(
            "const promptPrerequisite = directSuperFast ? briefState.ready : planState.ready",
            ref2v.text,
        )
        super_fast_body = ref2v.text.split("async function runSuperFastMode()", 1)[1].split(
            "function resumeAutomaticMode()", 1
        )[0]
        self.assertIn(
            "const streamView = directToPrompt ? elements.prompt : elements.plan",
            super_fast_body,
        )
        self.assertIn("streamView,", super_fast_body)
        self.assertIn("superFastRunApproved()", super_fast_body)
        self.assertIn("if (directToPrompt) revealSuperFastPrompt()", super_fast_body)
        self.assertIn("showStageError(streamView", super_fast_body)
        self.assertIn("function generateSuperFastOrStage(stage)", ref2v.text)
        self.assertIn(
            'elements.plan.generate.addEventListener("click", () => generateSuperFastOrStage("beat-sheet"))',
            ref2v.text,
        )
        self.assertIn(
            'elements.prompt.generate.addEventListener("click", () => generateSuperFastOrStage("final-prompt"))',
            ref2v.text,
        )

    def test_exposes_direct_rerun_compound_actions_and_reference_name_copy(self):
        page = self.client.get("/")
        prompt_navigation = self.client.get("/static/prompt-lab.js")
        scripts = {
            "i2vd": self.client.get("/static/i2v-direct.js").text,
            "ref2vd": self.client.get("/static/ref2v-direct.js").text,
        }

        self.assertEqual(page.status_code, 200)
        self.assertLess(
            page.text.index('id="i2vd-new-session"'),
            page.text.index('id="release-vram"'),
        )
        self.assertLess(
            page.text.index('id="ref2vd-new-session"'),
            page.text.index('id="release-vram"'),
        )
        for prefix in scripts:
            self.assertEqual(page.text.count(f'id="{prefix}-new-session"'), 1)
            for suffix in (
                "fork-session",
                "session-config",
                "rewrite-approve-brief",
                "apply-approve-arbitrations",
                "prompt-references",
            ):
                self.assertIn(f'id="{prefix}-{suffix}"', page.text)

        self.assertIn(
            'elements.i2vDirectNewRun.hidden = view !== "i2v-direct"',
            prompt_navigation.text,
        )
        self.assertIn(
            'elements.ref2vDirectNewRun.hidden = view !== "ref2v-direct"',
            prompt_navigation.text,
        )
        for prefix, script in scripts.items():
            self.assertIn("function prepareFork()", script)
            self.assertIn("state.forkSource = source", script)
            self.assertIn("/fork`", script)
            self.assertIn("const requestId = ++state.openRequestId", script)
            self.assertIn("requestId !== state.openRequestId", script)
            self.assertIn(
                "core.request(`/api/prompt-lab/sessions/${sessionId}`)",
                script,
            )
            self.assertIn("clearStageDrafts()", script)
            self.assertIn("state.openingSessionId", script)
            self.assertIn("state.compoundRunning", script)
            self.assertIn(
                'JSON.stringify({ model_id: elements.model.value })',
                script,
            )
            self.assertIn(
                "elements.newSession.hidden = !session && !state.forkSource",
                script,
            )
            self.assertIn("elements.sessionConfig.textContent", script)
            self.assertIn("Modèle : ${session.model_id} · Recette : ${recipeLabel}", script)
            self.assertIn("next.open = true", script)
            self.assertIn(
                'next.scrollIntoView({ behavior: "smooth", block: "start" })',
                script,
            )
            self.assertIn("copyText(reference.label)", script)
            self.assertIn("document.execCommand(\"copy\")", script)
            self.assertIn("documentState.active_revision_id", script)
            self.assertIn("previousRevisionId", script)
            self.assertIn("generatedDocument(", script)
            self.assertNotIn("copyText(label.textContent)", script)

        self.assertIn(
            'elements.brief.rewriteApprove.addEventListener("click", reviseAndApproveBrief)',
            scripts["i2vd"],
        )
        self.assertIn(
            'elements.brief.rewriteApprove.addEventListener("click", reviseAndApproveBrief)',
            scripts["ref2vd"],
        )
        self.assertIn(
            'elements.applyApproveArbitrations.addEventListener("click", reconcileAndApprovePlan)',
            scripts["i2vd"],
        )
        self.assertIn(
            'elements.applyApproveArbitrations.addEventListener("click", reconcileAndApprovePlan)',
            scripts["ref2vd"],
        )
        self.assertIn("activeRevisionId", scripts["i2vd"])
        self.assertIn("currentRevisionId", scripts["ref2vd"])

    def test_unloads_the_external_model_runtime(self):
        response = self.client.post("/api/model-runtime/unload")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "unloaded")
        self.assertEqual(self.model_runtime.unload_calls, 1)

    def test_preview_uses_the_protected_angle_grammar(self):
        response = self.client.post(
            "/api/change-view/preview",
            json={
                "azimuth": "back",
                "elevation": "low",
                "shot_size": "wide",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["compiled_prompt"],
            "<sks> back view low-angle shot wide shot",
        )

    def test_upload_generates_persists_and_serves_a_candidate(self):
        seed = "18446744073709551615"
        response = self.client.post(
            "/api/runs",
            files={"source_image": ("character.png", PNG, "image/png")},
            data={
                "azimuth": "back",
                "elevation": "low",
                "shot_size": "wide",
                "lora_strength": "1.25",
                "seed": seed,
            },
        )

        self.assertEqual(response.status_code, 202)
        created = response.json()
        self.assertEqual(created["status"], "created")
        self.assertEqual(created["controls"]["seed"], seed)
        self.assertEqual(
            created["experimental_overrides"],
            ["multiple_angles_lora_strength"],
        )

        completed = self.client.get(f"/api/runs/{created['run_id']}")
        self.assertEqual(completed.status_code, 200)
        run = completed.json()
        self.assertEqual(run["status"], "succeeded")
        self.assertIsNotNone(run["result_asset_id"])
        content = self.client.get(run["result_url"])
        self.assertEqual(content.status_code, 200)
        self.assertEqual(content.content, PNG)
        self.assertEqual(content.headers["content-type"], "image/png")
        self.assertEqual(
            self.comfy.submitted[0]["108"]["inputs"]["seed"],
            int(seed),
        )

    def test_review_and_reuse_create_explicit_lineage(self):
        first = self.client.post(
            "/api/runs",
            files={"source_image": ("character.png", PNG, "image/png")},
            data={"seed": "42", "lora_strength": "1.0"},
        ).json()
        completed = self.client.get(f"/api/runs/{first['run_id']}").json()

        review = self.client.post(
            f"/api/runs/{first['run_id']}/review",
            json={"decision": "kept"},
        )
        reuse = self.client.post(f"/api/runs/{first['run_id']}/reuse")
        second = self.client.post(
            "/api/runs",
            data={
                "source_asset_id": reuse.json()["source_asset_id"],
                "seed": "43",
                "lora_strength": "1.0",
            },
        )

        self.assertEqual(review.status_code, 200)
        self.assertEqual(review.json()["decision"], "kept")
        self.assertEqual(second.status_code, 202)
        self.assertEqual(second.json()["parent_run_id"], completed["run_id"])

    def test_rejects_unsupported_image_bytes_and_imprecise_seed_syntax(self):
        bad_image = self.client.post(
            "/api/runs",
            files={"source_image": ("fake.png", b"not-an-image", "image/png")},
            data={"seed": "42"},
        )
        bad_seed = self.client.post(
            "/api/runs",
            files={"source_image": ("character.png", PNG, "image/png")},
            data={"seed": "1e6"},
        )

        self.assertEqual(bad_image.status_code, 422)
        self.assertEqual(bad_seed.status_code, 422)


if __name__ == "__main__":
    unittest.main()
