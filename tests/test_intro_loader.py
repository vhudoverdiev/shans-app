import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "base.html"
STYLESHEET = PROJECT_ROOT / "app" / "static" / "css" / "style.css"
INTRO_SCRIPT = PROJECT_ROOT / "app" / "static" / "js" / "intro-loader.js"


class IntroLoaderTests(unittest.TestCase):
    def test_base_template_bootstraps_first_visit_intro(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('const introKey = "shans-intro-seen-v1"', template)
        self.assertIn("window.sessionStorage.getItem(introKey)", template)
        self.assertIn("}, 3000);", template)
        self.assertIn("onerror=\"document.documentElement.classList.remove('app-intro-pending')\"", template)
        self.assertIn('class="app-intro" id="app-intro"', template)
        self.assertIn("app-intro-logo\">Ш", template)
        self.assertIn("filename='js/intro-loader.js'", template)

    def test_intro_script_cleans_up_after_animation(self):
        script = INTRO_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('classList.contains("app-intro-pending")', script)
        self.assertIn('classList.add("app-intro-running")', script)
        self.assertIn('classList.add("app-intro-leaving")', script)
        self.assertIn("intro.remove()", script)
        self.assertIn("prefers-reduced-motion: reduce", script)

    def test_intro_styles_reuse_brand_gradient_and_support_reduced_motion(self):
        stylesheet = STYLESHEET.read_text(encoding="utf-8")

        self.assertIn(".app-intro-logo", stylesheet)
        self.assertIn("linear-gradient(135deg, #2563eb, #7c3aed)", stylesheet)
        self.assertIn("@keyframes app-intro-logo-in", stylesheet)
        self.assertIn("@media (prefers-reduced-motion: reduce)", stylesheet)


if __name__ == "__main__":
    unittest.main()
