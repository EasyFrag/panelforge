from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "panelforge" / "features" / "lab" / "static"


class SocialLabUiTest(unittest.TestCase):
    def test_video_lab_exposes_instagram_copy_workspace(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        core = (STATIC / "lab-core.js").read_text(encoding="utf-8")
        script = (STATIC / "social-lab.js").read_text(encoding="utf-8")
        self.assertIn('data-video-lab-mode="social-lab"', html)
        self.assertIn('id="social-lab-workspace"', html)
        self.assertIn('id="social-language"', html)
        self.assertIn('value="en" selected', html)
        self.assertIn('id="social-variant-count"', html)
        self.assertIn('value="3"', html)
        self.assertIn('id="social-profile"', html)
        self.assertIn('id="social-message"', html)
        self.assertIn("[0.10, 0.35, 0.65, 0.90]", script)
        self.assertIn('copy.textContent = "Tout copier"', script)
        self.assertIn("project.turns", script)
        self.assertIn("core.createLlmOutcomeTone()", script)
        self.assertIn("outcomeTone.success()", script)
        self.assertIn("outcomeTone.failure()", script)
        self.assertIn("{ completionTone: false }", script)
        first_modebar = html.split('class="video-lab-modebar"', 1)[1]
        self.assertLess(
            first_modebar.index('data-video-lab-mode="social-lab"'),
            first_modebar.index('data-video-lab-mode="video-lab"'),
        )
        self.assertIn(
            'button.dataset.labView === "video-lab"\n          ? "social-lab"',
            core,
        )
        self.assertIn(
            'document.querySelectorAll(\'[data-lab-view="video-lab"], [data-video-lab-mode="social-lab"]\')',
            script,
        )


if __name__ == "__main__":
    unittest.main()
