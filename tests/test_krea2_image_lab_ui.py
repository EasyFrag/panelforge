import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = PROJECT_ROOT / "src" / "panelforge" / "features" / "lab" / "static"


class Krea2ImageLabUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        cls.navigation = (STATIC_ROOT / "prompt-lab.js").read_text(encoding="utf-8")
        cls.script = (STATIC_ROOT / "krea2-image-lab.js").read_text(encoding="utf-8")
        cls.styles = (STATIC_ROOT / "lab.css").read_text(encoding="utf-8")

    def test_exposes_krea2_as_a_mode_inside_image_lab(self):
        self.assertIn('/static/krea2-image-lab.js?v=20260817.1', self.page)
        self.assertIn('data-image-lab-mode="change-view"', self.page)
        self.assertIn('data-image-lab-mode="krea2-image-lab"', self.page)
        self.assertIn('id="krea2-image-lab-workspace"', self.page)
        self.assertIn('krea2ImageLab: $("#krea2-image-lab-workspace")', self.navigation)
        self.assertIn('elements.krea2ImageLab.hidden = view !== "krea2-image-lab"', self.navigation)
        self.assertIn('imageLabActive ? "change-view" : view', self.navigation)
        self.assertIn(".image-lab-modebar", self.styles)

        ids = re.findall(r'\bid="([^"]+)"', self.page)
        self.assertEqual(len(ids), len(set(ids)), "HTML IDs must remain unique")

    def test_has_compact_generation_controls_and_png_only_output(self):
        for control_id in (
            "krea2-image-lab-prompt",
            "krea2-image-lab-model",
            "krea2-image-lab-refresh-models",
            "krea2-image-lab-ratio",
            "krea2-image-lab-megapixels",
            "krea2-image-lab-seed",
            "krea2-image-lab-seed-lock",
            "krea2-image-lab-randomize-seed",
            "krea2-image-lab-generate",
            "krea2-image-lab-output",
            "krea2-image-lab-cancel",
            "krea2-image-lab-reuse-seed",
            "krea2-image-lab-download",
            "krea2-image-lab-history-list",
        ):
            self.assertIn(f'id="{control_id}"', self.page)
        self.assertIn('min="0.5" max="4"', self.page)
        self.assertIn('value="3"', self.page)
        workspace = self.page.split('id="krea2-image-lab-workspace"', 1)[1].split('id="storyboard-lab-workspace"', 1)[0]
        self.assertNotIn("Preview", workspace)
        self.assertNotIn("<video", workspace)
        self.assertIn("Sortie PNG", workspace)
        self.assertNotIn("WebSocket", self.script)
        self.assertNotIn("preview", self.script.lower())

    def test_final_png_is_contained_without_being_stretched(self):
        self.assertIn('/static/lab.css?v=20260823.4', self.page)
        self.assertIn(".krea2-image-lab-output { width: min(100%, 760px)", self.styles)
        self.assertIn("min-height: clamp(300px, 42vw, 600px)", self.styles)
        self.assertIn("width: auto; height: auto; max-width: 100%; max-height: 580px", self.styles)

    def test_long_krea2_names_and_history_entries_cannot_widen_the_page(self):
        self.assertIn(
            ".krea2-image-lab-parameter-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr))",
            self.styles,
        )
        self.assertIn(
            ".krea2-image-lab-results .storyboard-metadata span { min-width: 0; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }",
            self.styles,
        )
        self.assertIn(".krea2-image-lab-history ul { min-width: 0; max-width: 100%; overflow: hidden; }", self.styles)
        self.assertIn(
            "grid-template-columns: minmax(0, 1fr) auto auto;",
            self.styles,
        )

    def test_long_checkpoint_names_cannot_expand_the_krea2_workspace(self):
        self.assertIn(".krea2-image-lab-workspace { grid-template-columns: minmax(320px, 390px) minmax(0, 1fr); width: 100%; min-width: 0; }", self.styles)
        self.assertIn(".krea2-image-lab-controls select { min-width: 0; max-width: 100%; }", self.styles)
        self.assertIn(".krea2-image-lab-controls select { display: block; text-overflow: ellipsis; }", self.styles)
        self.assertIn("grid-template-columns: minmax(0, 1fr) auto auto", self.styles)
        self.assertIn(".krea2-image-lab-history li > div { min-width: 0; max-width: 100%; overflow: hidden; }", self.styles)

    def test_uses_the_krea2_api_and_dynamic_model_refresh(self):
        for route in (
            'request("/api/image-lab/krea2/spec")',
            'request("/api/image-lab/krea2/models/refresh", { method: "POST" })',
            'request("/api/image-lab/krea2/runs", {',
            '/api/image-lab/krea2/runs/${encodeURIComponent(runId(prepared))}/start',
            '/api/image-lab/krea2/runs/${encodeURIComponent(runId(state.activeRun))}/cancel',
            'request("/api/image-lab/krea2/runs?limit=30")',
        ):
            self.assertIn(route, self.script)
        self.assertIn('preferredModelFragment = "krea2gptgrandpussytruth_gptint4int8convrot"', self.script)
        self.assertIn(
            'preferredModelId = "Krea2/krea2GPTGrandPUSSYTruth_gptINT4INT8Convrot.safetensors"',
            self.script,
        )
        self.assertIn('model.selectable !== false && model.installed !== false', self.script)
        self.assertIn('model.qualified === false', self.script)
        self.assertIn('seed: elements.seed.value.trim()', self.script)

    def test_storyboard_prefill_keeps_full_enum_ratios_and_never_starts(self):
        for ratio in (
            "1:1 (Square)",
            "2:3 (Portrait Photo)",
            "3:2 (Photo)",
            "3:4 (Portrait Standard)",
            "4:3 (Standard)",
            "9:16 (Portrait Widescreen)",
            "16:9 (Widescreen)",
            "21:9 (Ultrawide)",
        ):
            self.assertIn(f'"{ratio}"', self.script)
        self.assertIn("aspectRatioEnum.filter((ratio) => advertised.has(ratio))", self.script)
        for mapping in (
            '2: "4:3 (Standard)"',
            '4: "2:3 (Portrait Photo)"',
            '6: "1:1 (Square)"',
            '9: "2:3 (Portrait Photo)"',
        ):
            self.assertIn(mapping, self.script)
        self.assertIn("source_storyboard_run_id", self.script)
        prefill = self.script.split("async function prefill(", 1)[1].split("elements.form.addEventListener", 1)[0]
        self.assertNotIn('/api/image-lab/krea2/runs', prefill)
        self.assertNotIn("startRun(", prefill)
        self.assertIn('switchView("krea2-image-lab")', prefill)
        self.assertIn("if (!await initialize())", prefill)
        self.assertIn("selectAvailableValue(elements.ratio, suggestedRatio)", prefill)
        self.assertIn("suggested_ratio: suggestedRatio", prefill)
        self.assertIn("Ratio conseillé", self.script)
        self.assertIn(".krea2-image-lab-provenance.warning", self.styles)

    def test_resolution_estimate_matches_workflow_megapixel_units(self):
        self.assertIn("megapixels * 1024 * 1024", self.script)
        self.assertIn("Math.sqrt(area / (ratio.width * ratio.height))", self.script)
        self.assertIn("roundedDimension(ratio.width * scale)", self.script)
        self.assertIn("roundedDimension(ratio.height * scale)", self.script)
        self.assertNotIn("roundedDimension(area / width)", self.script)
        self.assertIn("roundedDimension", self.script)
        self.assertIn("megapixels * 10 - Math.round(megapixels * 10)", self.script)

    def test_storyboard_provenance_leaves_the_final_prompt_hash_to_the_server(self):
        create_body = self.script.split("function createBody()", 1)[1].split("function stopPolling()", 1)[0]
        self.assertIn("prompt: elements.prompt.value.trim()", create_body)
        self.assertIn("body.source_storyboard_run_id", create_body)
        self.assertNotIn("source_prompt_sha256", create_body)
        self.assertNotIn("SubtleCrypto", self.script)

    def test_seed_lock_and_historical_unavailable_values_are_safe(self):
        self.assertIn(
            "JSON.stringify({ locked: true, seed: elements.seed.value.trim() })",
            self.script,
        )
        self.assertIn("elements.seed.value = randomSeed();\n  restoreSeedLock();", self.script)
        self.assertIn("option.disabled = true", self.script)
        self.assertIn("selectStoredValue(elements.model", self.script)
        self.assertIn("Valeurs indisponibles", self.script)
        self.assertIn('runParameter(state.activeRun, "seed") === null', self.script)

    def test_only_real_comfy_execution_states_block_or_offer_cancellation(self):
        self.assertIn(
            'activeStatuses = new Set(["queued", "running", "cancel_pending"])',
            self.script,
        )
        self.assertIn("elements.cancel.disabled = state.busy || !isActive(state.activeRun)", self.script)


if __name__ == "__main__":
    unittest.main()
