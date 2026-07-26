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
        self.assertIn('class="app-intro" id="app-intro" aria-hidden="true" hidden', template)
        self.assertIn('class="app-intro-logo"', template)
        self.assertIn("filename='logo.png'", template)
        self.assertIn('class="app-intro-logo-mark"', template)
        self.assertIn('class="brand-badge"', template)
        self.assertNotIn("app-intro-wordmark", template)
        self.assertNotIn(">Шанс</div>", template)
        self.assertIn("filename='js/intro-loader.js'", template)

    def test_intro_bootstrap_hides_content_before_external_stylesheets_load(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        bootstrap_position = template.index('const introKey = "shans-intro-seen-v1"')
        first_stylesheet_position = template.index('rel="stylesheet"')

        self.assertLess(bootstrap_position, first_stylesheet_position)
        self.assertIn(
            "html.app-intro-pending body {\n            visibility: hidden;",
            template,
        )

    def test_intro_script_cleans_up_after_animation(self):
        script = INTRO_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('classList.contains("app-intro-pending")', script)
        self.assertIn("intro.hidden = false", script)
        self.assertIn('classList.add("app-intro-running")', script)
        self.assertIn('classList.add("app-intro-leaving")', script)
        self.assertIn("intro.remove()", script)
        self.assertIn("prefers-reduced-motion: reduce", script)

    def test_intro_styles_reuse_brand_gradient_and_support_reduced_motion(self):
        stylesheet = STYLESHEET.read_text(encoding="utf-8")

        self.assertIn(".app-intro-logo", stylesheet)
        self.assertIn(".app-intro-logo-mark", stylesheet)
        self.assertIn(".app-intro[hidden]", stylesheet)
        self.assertNotIn(".app-intro-wordmark", stylesheet)
        self.assertIn("linear-gradient(135deg, #2563eb, #7c3aed)", stylesheet)
        self.assertIn("@keyframes app-intro-logo-in", stylesheet)
        self.assertIn("@media (prefers-reduced-motion: reduce)", stylesheet)

    def test_intro_uses_dynamic_viewport_and_centers_installed_ios_app(self):
        stylesheet = STYLESHEET.read_text(encoding="utf-8")

        self.assertRegex(
            stylesheet,
            r"\.app-intro\s*\{[^}]*height:\s*100vh;[^}]*height:\s*100dvh;",
        )
        self.assertIn(
            "@media (display-mode: standalone) and (max-width: 768px) and (pointer: coarse)",
            stylesheet,
        )
        self.assertRegex(
            stylesheet,
            r"\.app-intro-stage\s*\{\s*transform:\s*translateY\(clamp\(-24px,\s*-2\.2dvh,\s*-16px\)\);",
        )

    def test_intro_logo_is_inline_and_cannot_fail_as_an_image_request(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        intro_logo = template.split('<div class="app-intro-logo">', 1)[1].split(
            "</div>",
            1,
        )[0]

        self.assertIn("<svg", intro_logo)
        self.assertIn("<path", intro_logo)
        self.assertNotIn("<img", intro_logo)
        self.assertNotIn("src=", intro_logo)
        self.assertNotIn("logo-intro.png", template)


if __name__ == "__main__":
    unittest.main()
