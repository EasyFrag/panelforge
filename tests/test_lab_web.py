import sys
import tempfile
import unittest
import re
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

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

    def running_models(self):
        return ("Qwen3.8-27B",)


class FakeComfyRuntime:
    def __init__(self):
        self.free_calls = 0
        self.running = ()
        self.pending = ()

    @property
    def websocket_url(self):
        return "ws://gpu.test:8188/ws?clientId=runtime"

    def get_system_stats(self):
        return SimpleNamespace(
            devices=(
                SimpleNamespace(
                    name="NVIDIA RTX PRO 6000",
                    vram_total=1000,
                    vram_free=375,
                ),
            )
        )

    def get_queue(self):
        return SimpleNamespace(running=self.running, pending=self.pending)

    def free_vram(self):
        self.free_calls += 1


class FakeLocalGpuMonitor:
    def get_stats(self):
        return SimpleNamespace(
            name="NVIDIA GeForce RTX 5090",
            total_bytes=32_607 * 1024**2,
            used_bytes=30_000 * 1024**2,
            free_bytes=2_188 * 1024**2,
            used_percent=92.0,
            temperature_c=67.0,
        )


class FakeLlmActivityMonitor:
    def __init__(self):
        self.calls = ()

    def active_calls(self):
        return self.calls


class FakeRuntimeSocket:
    def __init__(self):
        self.messages = [
            json.dumps({"type": "progress", "data": {"value": 2}}),
            json.dumps(
                {
                    "type": "crystools.monitor",
                    "data": {
                        "gpus": [
                            {
                                "gpu_utilization": 71,
                                "gpu_temperature": 62,
                                "vram_used_percent": 29,
                            }
                        ]
                    },
                }
            ),
        ]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def recv(self):
        if self.messages:
            return self.messages.pop(0)
        await asyncio.Future()


class FakeRuntimeConnector:
    def __init__(self):
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        return FakeRuntimeSocket()


class LabWebTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        assets = LocalAssetStore(self.temporary_directory.name)
        self.assets = assets
        runs = LocalRunStore(self.temporary_directory.name)
        recipe = ChangeViewPresetRecipe(load_change_view_preset(PRESET_DIRECTORY))
        self.comfy = ImmediateComfy()
        self.model_runtime = FakeModelRuntime()
        self.comfy_runtime = FakeComfyRuntime()
        self.local_gpu_monitor = FakeLocalGpuMonitor()
        self.llm_activity_monitor = FakeLlmActivityMonitor()
        self.runtime_connector = FakeRuntimeConnector()
        runner = ChangeViewRunner(
            recipe=recipe,
            comfy=self.comfy,
            assets=assets,
            runs=runs,
        )
        self.client = TestClient(
            create_app(
                runner,
                model_runtime=self.model_runtime,
                llm_activity_monitor=self.llm_activity_monitor,
                comfy_runtime=self.comfy_runtime,
                local_gpu_monitor=self.local_gpu_monitor,
                runtime_monitor_connector=self.runtime_connector,
            )
        )

    def tearDown(self):
        self.client.close()
        self.temporary_directory.cleanup()

    def test_serves_page_and_curated_recipe_spec(self):
        page = self.client.get("/")
        script = self.client.get("/static/lab.js")
        stylesheet = self.client.get("/static/lab.css")
        spec = self.client.get("/api/change-view/spec")

        self.assertEqual(page.status_code, 200)
        self.assertIn("PanelForge", page.text)
        self.assertIn('id="release-llm-vram"', page.text)
        self.assertIn('id="release-comfy-vram"', page.text)
        self.assertIn('id="runtime-monitor"', page.text)
        self.assertIn('id="runtime-server-monitor"', page.text)
        self.assertIn('id="runtime-local-monitor"', page.text)
        self.assertIn('id="runtime-local-vram"', page.text)
        self.assertIn('id="runtime-local-temp"', page.text)
        self.assertIn('id="runtime-services" class="runtime-services warning" hidden', page.text)
        self.assertLess(
            page.text.index('id="release-llm-vram"'),
            page.text.index('id="release-comfy-vram"'),
        )
        self.assertIn("/static/lab.js?v=20260831.1", page.text)
        self.assertEqual(page.headers["cache-control"], "no-store")
        self.assertEqual(script.status_code, 200)
        self.assertEqual(stylesheet.status_code, 200)
        self.assertEqual(script.headers["cache-control"], "no-store")
        self.assertIn("/api/change-view/preview", script.text)
        self.assertIn("/api/model-runtime/unload", script.text)
        self.assertIn("/api/comfy-runtime/free", script.text)
        self.assertIn("/api/runtime/status", script.text)
        self.assertIn("/api/runtime/events", script.text)
        self.assertIn("window.setTimeout(refreshRuntimeStatus, 1000)", script.text)
        self.assertNotIn('id="runtime-gpu"', page.text)
        self.assertNotIn('ui["runtime-gpu"]', script.text)
        self.assertIn('percent > 30 ? "yellow" : "green"', script.text)
        self.assertIn("((temperature - 25) / (100 - 25)) * 100", script.text)
        self.assertIn('temperature <= 60 ? "green" : temperature <= 80 ? "orange" : "red"', script.text)
        self.assertIn('ui["runtime-services"].hidden = serviceWarnings.length === 0', script.text)
        self.assertIn('serviceWarnings.push("GPU local indisponible")', script.text)
        self.assertIn('preferredPromptModelId = "Qwen3.8-27B"', script.text)
        self.assertIn('includes("qwen3.8-27b")', script.text)
        self.assertIn('includes("qwen3.6-27b")', script.text)
        self.assertIn("PanelForgeModelPicker", script.text)
        self.assertIn('data-lab-view="ref2v-direct"', page.text)
        self.assertIn('id="ref2vd-workspace"', page.text)
        self.assertIn('id="ref2vd-image-input" type="file"', page.text)
        self.assertIn("multiple", page.text)
        self.assertIn("/static/lab.css?v=20260903.3", page.text)
        self.assertIn("/static/ref2v-direct.js?v=20260904.1", page.text)
        direct_script = self.client.get("/static/ref2v-direct.js")
        core_script = self.client.get("/static/lab-core.js")
        self.assertEqual(direct_script.status_code, 200)
        self.assertIn('const preferredCookbookVersion = "0.4.0"', direct_script.text)
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
        self.assertIn(
            'core.decorateSessionLink(button, session.references)',
            direct_script.text,
        )
        self.assertIn('.session-link.has-session-thumbnails', stylesheet.text)
        self.assertIn('.session-link-thumbnail', stylesheet.text)
        self.assertIn('object-fit: cover', stylesheet.text)
        self.assertNotIn("/references/${", direct_script.text)
        self.assertNotIn("crypto.randomUUID", direct_script.text)
        self.assertEqual(core_script.status_code, 200)
        self.assertIn("/static/lab-core.js?v=20260901.2", page.text)
        self.assertIn("function errorDetailMessage(detail)", core_script.text)
        self.assertIn('item.loc.filter((part) => part !== "body")', core_script.text)
        self.assertNotIn('data-lab-view="storyboard-lab"', page.text)
        self.assertNotIn('data-lab-view="prompt-lab"', page.text)
        self.assertNotIn('data-lab-view="archives"', page.text)
        self.assertNotIn('id="archives-workspace"', page.text)
        self.assertNotIn('data-lab-view="i2v"', page.text)
        self.assertNotIn('data-lab-view="ref2v"', page.text)
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
        self.assertIn("function intentionRequestsMultipleShots(value)", direct_script.text)
        self.assertIn("function invalidateRoleConfirmation()", direct_script.text)
        self.assertIn("state.rolesConfirmed", direct_script.text)
        self.assertIn("if (!state.rolesConfirmed)", direct_script.text)
        self.assertIn("state.rolesConfirmed = false", direct_script.text)
        self.assertIn("allAdditionalReferencesAreSubjects", direct_script.text)
        self.assertIn("function playCompletionTone()", core_script.text)
        self.assertIn('oscillator.type = "triangle"', core_script.text)
        self.assertIn("frequency: 660", core_script.text)
        self.assertIn("frequency: 880", core_script.text)
        self.assertIn("function playFailureTone()", core_script.text)
        self.assertIn("frequency: 440", core_script.text)
        self.assertIn("frequency: 220", core_script.text)
        self.assertIn("function createLlmOutcomeTone()", core_script.text)
        self.assertIn("function truncationMessage(event = {})", core_script.text)
        self.assertIn("Le raisonnement interne compte dans ce budget", core_script.text)
        self.assertIn("truncationError = core.truncationMessage(event)", direct_script.text)
        self.assertIn("if (!started || settled) return", core_script.text)
        self.assertIn("{ completionTone = false }", core_script.text)
        self.assertIn("exponentialRampToValueAtTime(0.08", core_script.text)
        self.assertIn('event.kind === "completed"', core_script.text)
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

    def test_exposes_the_local_unsloth_switch_for_every_llm_selector(self):
        page = self.client.get("/")
        script = self.client.get("/static/lab.js")

        self.assertEqual(page.text.count('data-llm-local-for="'), 14)
        for select_id in (
            "krea2-assisted-llm",
            "krea2-batch-llm",
            "krea2-edit-llm",
            "i2vd-model",
            "ref2vd-model",
            "social-llm",
            "production-llm",
            "krea2-assisted-revision-llm",
            "h3r-revision-model",
            "ref2vr-revision-model",
            "production-v2-initial-llm",
            "production-v2-krea-llm",
            "production-v2-compile-llm",
            "production-v2-video-llm",
        ):
            self.assertIn(
                f'data-llm-local-for="{select_id}"',
                page.text,
            )
        self.assertIn('new Set(["local"])', script.text)
        self.assertNotIn('model.id.startsWith("vllm::")', script.text)
        self.assertEqual(page.text.count("Local · Unsloth"), 14)
        self.assertIn("Aucun modèle local disponible", script.text)

    def test_serves_the_h3_base_workspace_with_optional_boundary_frames(self):
        page = self.client.get("/")
        script = self.client.get("/static/i2v-direct.js")
        render_script = self.client.get("/static/h3-render-lab.js")
        styles = self.client.get("/static/lab.css")
        core_script = self.client.get("/static/lab-core.js")

        self.assertEqual(page.status_code, 200)
        self.assertEqual(script.status_code, 200)
        self.assertEqual(render_script.status_code, 200)
        self.assertIn('data-lab-view="i2v-direct"', page.text)
        self.assertIn('data-lab-view="i2v-direct">H3 Base</button>', page.text)
        self.assertIn('id="i2vd-workspace"', page.text)
        self.assertIn('id="i2vd-image-input" type="file"', page.text)
        self.assertIn('id="i2vd-last-image-input" type="file"', page.text)
        self.assertIn('id="i2vd-input-mode"', page.text)
        self.assertNotIn(
            'id="i2vd-image-input" type="file" accept="image/png,image/jpeg,image/webp" multiple',
            page.text,
        )
        self.assertIn('id="i2vd-brief-step"', page.text)
        self.assertIn('id="i2vd-plan-step"', page.text)
        self.assertIn('id="i2vd-prompt-step"', page.text)
        self.assertIn('id="h3r-lab"', page.text)
        self.assertIn('id="h3r-music"', page.text)
        self.assertIn('id="h3r-spectrum" type="checkbox"', page.text)
        self.assertIn('id="ref2vr-spectrum" type="checkbox"', page.text)
        self.assertIn('id="h3r-attempts"', page.text)
        self.assertIn('/static/h3-render-lab.js?v=20260902.2', page.text)
        self.assertIn('id="h3r-render-progress"', page.text)
        self.assertIn('id="ref2vr-render-progress"', page.text)
        self.assertIn('payload.type === "panelforge_render_progress"', render_script.text)
        production_script = self.client.get("/static/production-lab.js")
        self.assertIn('id="production-render-progress"', page.text)
        self.assertIn('payload.type === "panelforge_render_progress"', production_script.text)
        self.assertIn('/static/production-lab.js?v=20260903.2', page.text)
        self.assertIn('id="h3r-video-lora-profile"', page.text)
        self.assertIn('id="h3r-video-lora-model"', page.text)
        self.assertIn('id="h3r-video-lora-strength"', page.text)
        self.assertIn('id="ref2vr-video-lora-profile"', page.text)
        self.assertIn('id="ref2vr-video-lora-model"', page.text)
        self.assertIn('id="ref2vr-video-lora-strength"', page.text)
        self.assertIn('video_lora: elements.videoLoraProfile', render_script.text)
        self.assertIn('spectrum_enabled: elements.spectrum.checked', render_script.text)
        self.assertIn('elements.spectrum.checked = false', render_script.text)
        self.assertIn('id="h3r-revision-version"', page.text)
        self.assertIn('id="h3r-revision-model"', page.text)
        self.assertIn(
            'id="h3r-revision-audacity" type="range" min="0" max="3" step="1" value="0"',
            page.text,
        )
        self.assertIn('id="h3r-revision-audacity-value">0/3</output>', page.text)
        self.assertIn('0 standard historique', page.text)
        self.assertIn(
            'id="ref2vr-revision-audacity" type="range" min="0" max="3" step="1" value="0"',
            page.text,
        )
        self.assertIn('revision_audacity: Number(elements.revisionAudacity?.value || 0)', render_script.text)
        self.assertIn('id="ref2vr-revision-model"', page.text)
        self.assertIn('id="ref2vr-revision-version"', page.text)
        self.assertIn('id="h3r-revision-draft"', page.text)
        self.assertIn('id="ref2vr-revision-draft"', page.text)
        self.assertIn('id="h3r-revision-retry"', page.text)
        self.assertIn('id="ref2vr-revision-retry"', page.text)
        self.assertIn("repair_rejected: repairRejected", render_script.text)
        self.assertIn("function renderWarnings()", render_script.text)
        self.assertIn('elements.duration.addEventListener("input", renderWarnings)', render_script.text)
        self.assertIn('panelforge:h3-base-context', script.text)
        self.assertIn('/api/h3-render/projects/', render_script.text)
        self.assertIn("core.createLlmOutcomeTone()", render_script.text)
        self.assertIn("outcomeTone.success()", render_script.text)
        self.assertIn("outcomeTone.failure()", render_script.text)
        self.assertIn('/static/i2v-direct.js?v=20260831.1', page.text)
        self.assertIn('id="i2vd-animal-interview-fields"', page.text)
        self.assertEqual(page.text.count('class="field-label animal-interview-primary-field"'), 2)
        self.assertIn('id="i2vd-dialogue-language"', page.text)
        self.assertIn('id="i2vd-partial-script"', page.text)
        self.assertIn('aria-label="Afficher le guide de durée du dialogue"', page.text)
        self.assertIn('id="i2vd-duration-guide"', page.text)
        self.assertIn('Une réplique ≈ 4 s ; deux ≈ 8 s ; quatre ≈ 16 s.', page.text)
        self.assertIn('id="i2vd-remove-first-image"', page.text)
        self.assertIn('id="i2vd-remove-last-image"', page.text)
        self.assertIn('id="i2vd-setup-preview"', page.text)
        self.assertIn('id="i2vd-setup-first-image"', page.text)
        self.assertIn('id="i2vd-setup-last-image"', page.text)
        self.assertIn(
            ".h3-base-frame-inputs .i2v-upload > b,",
            styles.text,
        )
        self.assertIn("text-overflow: ellipsis", styles.text)
        self.assertIn('.h3-base-setup-preview[data-count="1"]', styles.text)
        self.assertIn(".h3-base-setup-frame img", styles.text)
        self.assertIn("object-fit: contain", styles.text)
        self.assertIn('title.title = reference.label', script.text)
        self.assertIn("function removeSelectedFile(slot)", script.text)
        self.assertIn("function renderSetupPreview()", script.text)
        self.assertIn("const visible = !state.session && count > 0", script.text)
        self.assertIn('elements.empty.hidden = Boolean(session)', script.text)
        self.assertIn('elements.editor.hidden = !session', script.text)
        self.assertIn('elements.removeFirstImage.addEventListener("click"', script.text)
        self.assertIn('elements.removeLastImage.addEventListener("click"', script.text)
        self.assertIn('const monoProfile = { id: "minimax.h3.fl2va.direct", version: "0.3.3" }', script.text)
        self.assertIn('const multishotProfile = { id: "minimax.h3.fl2va.direct.multishot", version: "0.1.0" }', script.text)
        self.assertIn('const animalInterviewProfile = { id: "minimax.h3.base.animal-interview", version: "0.1.0" }', script.text)
        self.assertIn('const preferredCookbookKey = `${monoCookbookId}@${monoProfile.version}`', script.text)
        self.assertIn('elements.cookbook.value = cookbookKey(compositionReference || state.cookbook)', script.text)
        self.assertIn('const selectedCookbook = directCookbooks().find(', script.text)
        self.assertIn('const monoCookbookId = "minimax.h3.fl2va.direct"', script.text)
        self.assertIn('const multishotCookbookId = "minimax.h3.fl2va.direct.multishot"', script.text)
        self.assertIn('const animalInterviewCookbookId = "minimax.h3.base.animal-interview"', script.text)
        self.assertIn('Multi-plan structuré · 2 à 4 plans (${cookbook.version})', script.text)
        self.assertIn('Mono-plan · interview d’animal (${cookbook.version})', script.text)
        self.assertIn('Mono-plan · standard (${cookbook.version})', script.text)
        self.assertIn('item.target_mode === "fl2va_direct"', script.text)
        self.assertIn('body.append("roles", "first_frame")', script.text)
        self.assertIn('body.append("usages", "first_frame")', script.text)
        self.assertIn('body.append("roles", "last_frame")', script.text)
        self.assertIn('body.append("usages", "last_frame")', script.text)
        self.assertIn('first_frame: first ? [first.id] : []', script.text)
        self.assertIn('last_frame: last ? [last.id] : []', script.text)
        self.assertIn('function animalInterviewSourceText()', script.text)
        self.assertIn('function countAnimalInterviewReplies(script)', script.text)
        self.assertIn('const recommendedDuration = replyCount * 4', script.text)
        self.assertIn('renderAnimalInterviewDurationGuide(animalRecipe)', script.text)
        self.assertIn('function hydrateSourceInputs(sourceText)', script.text)
        self.assertIn('sessionInputModeLabel(session)', script.text)
        self.assertIn('core.decorateSessionLink(button, session.references)', script.text)
        self.assertIn('function decorateSessionLink(button, references)', core_script.text)
        self.assertIn('image.loading = "lazy"', core_script.text)
        self.assertIn('session-link-thumbnail', core_script.text)
        self.assertIn("beat-sheet/reconcile/stream", script.text)
        self.assertIn('i2vDirect: $("#i2vd-workspace")', core_script.text)
        self.assertIn(
            '[elements.i2vDirect, view === "i2v-direct"]',
            core_script.text,
        )

    def test_serves_video_lab_and_ref2v_prefill_bridge(self):
        page = self.client.get("/")
        script = self.client.get("/static/video-lab.js")
        ref2v_script = self.client.get("/static/ref2v-direct.js")
        navigation = self.client.get("/static/lab-core.js")

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
        self.assertIn('/static/video-lab.js?v=20260831.1', page.text)
        self.assertIn('type === "panelforge_render_progress"', script.text)

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

    def test_direct_creative_freedom_uses_permissions_and_h3_audacity(self):
        page = self.client.get("/")
        scripts = (
            self.client.get("/static/i2v-direct.js"),
            self.client.get("/static/ref2v-direct.js"),
        )

        for prefix in ("i2vd", "ref2vd"):
            for axis in ("scene-life", "camera", "extra-motion"):
                self.assertIn(
                    f'id="{prefix}-creative-{axis}" type="range" min="0" max="3" step="1" value="0"',
                    page.text,
                )
                self.assertIn(f'id="{prefix}-creative-{axis}-value">0</output>', page.text)
        for prefix in ("i2vd", "ref2vd"):
            self.assertIn(f'id="{prefix}-creative-direction" type="checkbox"', page.text)
            self.assertIn(
                f'id="{prefix}-creative-audacity" type="range" min="0" max="3" step="1" value="2"',
                page.text,
            )
            self.assertIn(f'id="{prefix}-creative-audacity-value">2</output>', page.text)
        self.assertEqual(page.text.count("L’audace fixe l’objectif de nouveauté"), 2)
        self.assertIn('id="h3r-revision-audacity-value">0/3</output>', page.text)
        self.assertIn('id="ref2vr-revision-audacity-value">0/3</output>', page.text)

        for script in scripts:
            self.assertEqual(script.status_code, 200)
            self.assertIn("function legacyCreativeLevel(value)", script.text)
            self.assertIn("function currentCreativeAxes()", script.text)
            self.assertIn("function creativeAxesMatch(brief)", script.text)
            self.assertIn("function creativePayload()", script.text)
            self.assertIn("creative_axes", script.text)
            self.assertNotIn("setFreedom", script.text)
            self.assertIn("function creativeAudacityMatch(brief)", script.text)
            self.assertIn("creative_audacity", script.text)

    def test_exposes_shared_quick_mode_for_both_direct_workspaces(self):
        page = self.client.get("/")
        quick = self.client.get("/static/quick-pipeline.js")
        i2v = self.client.get("/static/i2v-direct.js")
        ref2v = self.client.get("/static/ref2v-direct.js")

        self.assertEqual(quick.status_code, 200)
        self.assertIn('/static/quick-pipeline.js?v=20260830.2', page.text)
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
        self.assertIn("const maxAttemptsPerStep = 2", quick.text)
        self.assertIn("attempt <= maxAttemptsPerStep", quick.text)
        self.assertIn('publish(sessionId, "retrying"', quick.text)
        self.assertIn("onAttemptOutcome(step, false, attempt)", quick.text)
        self.assertIn('["running", "retrying"].includes(record.status)', quick.text)
        self.assertIn('status: "interrupted"', quick.text)
        self.assertNotIn("reconcile", quick.text)
        for script in (i2v.text, ref2v.text):
            self.assertIn("quickPipeline.runDirect", script)
            self.assertIn('generateBrief: () => streamBrief(false)', script)
            self.assertIn('approvePrompt: () => documentAction("final-prompt", "approve")', script)
            self.assertIn("!(documentState.validation_errors || []).length", script)
            self.assertNotIn("validation_warnings || []", script.split("function quickSnapshot()", 1)[1].split("function renderQuickStatus()", 1)[0])
            self.assertIn("reasoningTrace.streamUrl", script)
            self.assertIn("core.playCompletionTone()", script)
            self.assertIn("core.playFailureTone()", script)
            self.assertIn("tentative ${record.attempt}/${record.maxAttempts}", script)
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
        prompt_navigation = self.client.get("/static/lab-core.js")
        scripts = {
            "i2vd": self.client.get("/static/i2v-direct.js").text,
            "ref2vd": self.client.get("/static/ref2v-direct.js").text,
        }

        self.assertEqual(page.status_code, 200)
        self.assertLess(
            page.text.index('id="i2vd-new-session"'),
            page.text.index('id="release-llm-vram"'),
        )
        self.assertLess(
            page.text.index('id="ref2vd-new-session"'),
            page.text.index('id="release-llm-vram"'),
        )
        self.assertLess(
            page.text.index('id="i2vd-new-session"'),
            page.text.index('id="i2vd-fork-session"'),
        )
        self.assertLess(
            page.text.index('id="ref2vd-new-session"'),
            page.text.index('id="ref2vd-fork-session"'),
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
            self.assertIn("elements.forkSession.hidden = !session", script)
            self.assertIn("reasoningTrace.begin(traceLabel, traceStep)", script)
            self.assertIn(f'brief: $("#{prefix}-brief-step")', script)
            self.assertIn(
                "elements.newSession.hidden = !session && !state.forkSource",
                script,
            )
            self.assertIn("elements.sessionConfig.textContent", script)
            if prefix == "i2vd":
                self.assertIn(
                    "Modèle : ${session.model_id} · ${briefLabel} · Plan/Writer : ${recipeLabel}",
                    script,
                )
            else:
                self.assertIn(
                    "Modèle : ${session.model_id} · ${briefLabel} · Recette : ${recipeLabel}",
                    script,
                )
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

        self.assertIn('anchor.before(panel)', prompt_navigation.text)
        self.assertIn('panel.scrollIntoView({ behavior: "smooth", block: "nearest" })', prompt_navigation.text)

        self.assertIn("...creativeBriefPayload()", scripts["ref2vd"])
        self.assertIn("inherit_brief_variant: false", scripts["ref2vd"])
        self.assertIn("profile_id: profile.id", scripts["i2vd"])
        self.assertIn("profile_version: profile.version", scripts["i2vd"])

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

    def test_runtime_status_combines_gpu_queue_and_llama_without_errors(self):
        response = self.client.get("/api/runtime/status")

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["gpu"]["used_bytes"], 625)
        self.assertEqual(payload["gpu"]["used_percent"], 62.5)
        self.assertTrue(payload["local_gpu"]["available"])
        self.assertEqual(payload["local_gpu"]["name"], "NVIDIA GeForce RTX 5090")
        self.assertEqual(payload["local_gpu"]["used_percent"], 92.0)
        self.assertEqual(payload["local_gpu"]["temperature_c"], 67.0)
        self.assertEqual(payload["comfy"]["queue_running"], 0)
        self.assertTrue(payload["comfy"]["cleanup_allowed"])
        self.assertEqual(payload["llm"]["running_models"], ["Qwen3.8-27B"])
        self.assertEqual(payload["production_resources"], [])

    def test_runtime_status_reports_non_production_comfy_and_llm_activity(self):
        self.comfy_runtime.running = (
            SimpleNamespace(client_id="panelforge-krea2-assisted-test"),
        )
        self.llm_activity_monitor.calls = (
            SimpleNamespace(
                call_id="llm-active",
                operation_id="krea2.assisted.creation_chat@0.3.0",
                model_id="local::qwen",
            ),
        )

        payload = self.client.get("/api/runtime/status").json()

        self.assertEqual(payload["comfy"]["active_operations"], ["KREA2"])
        self.assertEqual(payload["llm"]["active_calls"], [{
            "call_id": "llm-active",
            "source": "local",
            "operation": "krea2.assisted.creation_chat@0.3.0",
            "label": "KREA2",
        }])

    def test_runtime_status_degrades_to_warnings_when_services_are_offline(self):
        class Offline:
            def __getattr__(self, _name):
                raise OSError("private infrastructure detail")

        with tempfile.TemporaryDirectory() as workspace:
            assets = LocalAssetStore(workspace)
            runs = LocalRunStore(workspace)
            recipe = ChangeViewPresetRecipe(load_change_view_preset(PRESET_DIRECTORY))
            app = create_app(
                ChangeViewRunner(
                    recipe=recipe,
                    comfy=ImmediateComfy(),
                    assets=assets,
                    runs=runs,
                ),
                model_runtime=Offline(),
                comfy_runtime=Offline(),
                local_gpu_monitor=Offline(),
            )
            with TestClient(app) as client:
                response = client.get("/api/runtime/status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["comfy"]["available"])
        self.assertFalse(payload["llm"]["available"])
        self.assertFalse(payload["local_gpu"]["available"])
        self.assertEqual(payload["comfy"]["warning"], "ComfyUI indisponible.")
        self.assertEqual(payload["llm"]["warning"], "llama.swap indisponible.")
        self.assertEqual(payload["local_gpu"]["warning"], "GPU local indisponible.")
        self.assertNotIn("private infrastructure detail", response.text)

    def test_unloads_comfy_only_when_requested(self):
        response = self.client.post("/api/comfy-runtime/free")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.comfy_runtime.free_calls, 1)

    def test_runtime_websocket_forwards_only_crystools_telemetry(self):
        with self.client.websocket_connect("/api/runtime/events") as websocket:
            connected = websocket.receive_json()
            telemetry = websocket.receive_json()
            websocket.close()

        self.assertEqual(connected["type"], "panelforge_runtime_status")
        self.assertEqual(connected["data"]["status"], "connected")
        self.assertEqual(telemetry["type"], "crystools.monitor")
        self.assertEqual(telemetry["data"]["gpus"][0]["gpu_temperature"], 62)
        self.assertEqual(
            self.runtime_connector.urls,
            [self.comfy_runtime.websocket_url],
        )

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
