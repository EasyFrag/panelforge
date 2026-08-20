import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = PROJECT_ROOT / "src" / "panelforge" / "features" / "lab" / "static"


class StoryboardLabUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        cls.navigation = (STATIC_ROOT / "prompt-lab.js").read_text(encoding="utf-8")
        cls.script = (STATIC_ROOT / "storyboard-lab.js").read_text(encoding="utf-8")
        cls.styles = (STATIC_ROOT / "lab.css").read_text(encoding="utf-8")

    def test_exposes_standalone_storyboard_workspace(self):
        self.assertIn('data-lab-view="storyboard-lab"', self.page)
        self.assertIn('id="storyboard-lab-workspace"', self.page)
        self.assertIn('/static/storyboard-lab.js?v=20260820.1', self.page)
        self.assertIn('id="storyboard-lab-source"', self.page)
        self.assertIn('id="storyboard-lab-model"', self.page)
        self.assertIn('id="storyboard-lab-recipe"', self.page)
        self.assertIn('id="storyboard-lab-prompt"', self.page)
        self.assertNotIn('id="storyboard-lab-prompt" readonly', self.page)
        self.assertIn('id="storyboard-lab-variables"', self.page)
        self.assertIn('id="storyboard-lab-history-list"', self.page)
        self.assertIn('id="storyboard-lab-send-to-image-lab"', self.page)
        self.assertIn('id="storyboard-lab-show-reasoning" type="checkbox"', self.page)
        self.assertIn('id="storyboard-lab-reasoning-panel"', self.page)
        self.assertIn('storyboardLab: $("#storyboard-lab-workspace")', self.navigation)
        self.assertIn(
            'elements.storyboardLab.hidden = view !== "storyboard-lab"',
            self.navigation,
        )

        ids = re.findall(r'\bid="([^"]+)"', self.page)
        self.assertEqual(len(ids), len(set(ids)), "HTML IDs must remain unique")

    def test_uses_one_create_call_followed_by_the_sse_generation(self):
        self.assertIn('request("/api/storyboard-lab/spec")', self.script)
        self.assertIn('request("/api/storyboard-lab/runs?limit=30")', self.script)
        self.assertIn('request("/api/storyboard-lab/runs", {', self.script)
        self.assertIn('/generate/stream`', self.script)
        self.assertIn('method: "POST"', self.script)
        self.assertIn('source_text: sourceText', self.script)
        self.assertIn('panel_count: panelCount', self.script)
        self.assertIn('model_id: modelId', self.script)
        self.assertIn('window.PanelForgePromptLab', self.script)
        self.assertIn('api.updateStreamState(elements.stream, event)', self.script)
        self.assertIn('reasoningTrace.begin("Storyboard")', self.script)
        self.assertIn("reasoningTrace.streamUrl", self.script)
        self.assertIn("reasoningTrace.handle(event)", self.script)
        self.assertIn("reasoningTrace.finish()", self.script)
        self.assertIn("panelforge.debug.show_reasoning", self.navigation)
        self.assertNotIn("/api/comfy", self.script)
        self.assertNotIn("/api/krea", self.script.lower())

    def test_keeps_geometry_and_recipe_explicit(self):
        for expected in (
            '2: Object.freeze({ panel_count: 2, columns: 2, rows: 1, page_aspect_ratio: "4:3"',
            '4: Object.freeze({ panel_count: 4, columns: 2, rows: 2, page_aspect_ratio: "2:3"',
            '6: Object.freeze({ panel_count: 6, columns: 3, rows: 2, page_aspect_ratio: "1:1"',
            '9: Object.freeze({ panel_count: 9, columns: 3, rows: 3, page_aspect_ratio: "2:3"',
        ):
            self.assertIn(expected, self.script)
        self.assertIn("window.PanelForgeModelPicker.populate", self.script)
        self.assertIn("KREA2 Storyboard photo · v1", self.page)
        self.assertIn(".storyboard-panel-options", self.styles)
        self.assertIn(".storyboard-prompt-output", self.styles)

    def test_initializes_lazily_and_preserves_failed_candidate(self):
        self.assertIn(
            'navButton.addEventListener("click", initialize)',
            self.script,
        )
        self.assertIn("return initialize();", self.script)
        self.assertTrue(self.script.rstrip().endswith("renderRun(null);\n})();"))
        self.assertIn("run.raw_response", self.script)
        self.assertIn('truncated: "Écourté"', self.script)
        self.assertIn("Brouillon diagnostic", self.script)
        self.assertIn('if (results[0].status === "rejected") state.initialized = false', self.script)

    def test_history_can_reopen_and_relaunch_runs(self):
        self.assertIn('open.textContent = "Ouvrir"', self.script)
        self.assertIn('relaunch.textContent = "Relancer"', self.script)
        self.assertIn("openRun(runId(run))", self.script)
        self.assertIn("relaunchRun(run)", self.script)
        self.assertIn("event.storyboard_run", self.script)
        self.assertIn("payload && payload.run ? payload.run : payload", self.script)
        self.assertNotIn('return "Date inconnue"', self.script)

    def test_can_prefill_krea2_image_lab_without_starting_a_render(self):
        self.assertIn("window.PanelForgeKrea2ImageLab", self.script)
        self.assertIn("bridge.prefill({", self.script)
        self.assertIn("source_storyboard_run_id: runId(state.activeRun)", self.script)
        self.assertNotIn("source_prompt_sha256", self.script)
        self.assertNotIn("window.crypto.subtle", self.script)
        bridge = self.script.split("async function sendToImageLab()", 1)[1].split("async function initialize()", 1)[0]
        self.assertIn("const prompt = elements.prompt.value.trim()", bridge)
        self.assertIn("prompt,", bridge)
        self.assertNotIn("/api/image-lab/krea2/runs", bridge)
        self.assertNotIn("startRun", bridge)


if __name__ == "__main__":
    unittest.main()
