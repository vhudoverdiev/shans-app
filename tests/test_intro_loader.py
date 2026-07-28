import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "base.html"
STYLESHEET = PROJECT_ROOT / "app" / "static" / "css" / "style.css"
INTRO_SCRIPT = PROJECT_ROOT / "app" / "static" / "js" / "intro-loader.js"


class IntroLoaderTests(unittest.TestCase):
    def test_base_template_bootstraps_session_intro(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('<html lang="ru" class="app-intro-pending', template)
        self.assertIn('const isStandaloneApp = window.matchMedia("(display-mode: standalone)").matches', template)
        self.assertIn("window.navigator.standalone === true", template)
        self.assertIn("if (isStandaloneApp) {", template)
        self.assertIn("window.__shansShouldRunIntro = false", template)
        self.assertIn('const introKey = "shans-intro-session-v1"', template)
        self.assertIn("window.sessionStorage.getItem(introKey)", template)
        self.assertIn("window.sessionStorage.setItem(introKey, \"1\")", template)
        self.assertIn("window.__shansShouldRunIntro = true", template)
        self.assertIn("window.__shansIntroFallbackTimer", template)
        self.assertIn("}, 8000);", template)
        self.assertNotIn("}, 3000);", template)
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
        bootstrap_position = template.index('const introKey = "shans-intro-session-v1"')
        first_stylesheet_position = template.index('rel="stylesheet"')

        self.assertLess(bootstrap_position, first_stylesheet_position)
        self.assertIn(
            "html.app-intro-pending body > :not(#app-intro) {\n            visibility: hidden !important;",
            template,
        )
        self.assertIn(
            "html.app-intro-pending #app-intro[hidden] {\n            display: grid !important;",
            template,
        )
        self.assertLess(template.index("html.app-intro-pending #app-intro"), first_stylesheet_position)
        self.assertNotIn("window.localStorage.getItem(introKey)", template)
        self.assertNotIn("window.localStorage.setItem(introKey, \"1\")", template)

    def test_installed_pwa_skips_custom_intro_after_native_splash(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        standalone_position = template.index("const isStandaloneApp")
        session_position = template.index('const introKey = "shans-intro-session-v1"')
        standalone_block = template.split("if (isStandaloneApp) {", 1)[1].split("}", 1)[0]

        self.assertLess(standalone_position, session_position)
        self.assertIn('document.documentElement.classList.remove("app-intro-pending");', standalone_block)
        self.assertIn("window.__shansShouldRunIntro = false;", standalone_block)
        self.assertIn("return;", standalone_block)

    def test_intro_script_cleans_up_after_animation(self):
        script = INTRO_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('classList.contains("app-intro-pending")', script)
        self.assertIn("!window.__shansShouldRunIntro", script)
        self.assertIn("intro.hidden = false", script)
        self.assertIn('classList.add("app-intro-running")', script)
        self.assertIn('classList.add("app-intro-leaving")', script)
        self.assertIn("intro.remove()", script)
        self.assertIn("window.__shansShouldRunIntro = false", script)
        self.assertIn("window.clearTimeout(window.__shansIntroFallbackTimer)", script)
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

    def test_intro_progress_bar_does_not_slide_in_from_the_left(self):
        stylesheet = STYLESHEET.read_text(encoding="utf-8")
        template = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertNotIn("translateX(-105%)", stylesheet)
        self.assertNotIn("@keyframes app-intro-progress {", stylesheet)
        self.assertNotIn("app-intro-orbit", template)
        self.assertNotIn("app-intro-orbit", stylesheet)
        self.assertNotIn("app-intro-glow", template)
        self.assertNotIn("app-intro-glow", stylesheet)
        self.assertIn("@keyframes app-intro-progress-in", stylesheet)

    def test_intro_uses_dynamic_viewport_without_standalone_second_logo(self):
        stylesheet = STYLESHEET.read_text(encoding="utf-8")

        self.assertRegex(
            stylesheet,
            r"\.app-intro\s*\{[^}]*height:\s*100vh;[^}]*height:\s*100dvh;",
        )
        self.assertNotIn("@media (display-mode: standalone)", stylesheet)
        self.assertNotIn("translateY(clamp(-24px", stylesheet)

    def test_intro_logo_uses_the_exact_header_logo_asset(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        intro_logo = template.split('<div class="app-intro-logo">', 1)[1].split(
            "</div>",
            1,
        )[0]

        self.assertIn("<img", intro_logo)
        self.assertIn("filename='logo.png'", intro_logo)
        self.assertNotIn("<svg", intro_logo)
        self.assertNotIn("<path", intro_logo)
        self.assertNotIn("logo-intro.png", template)


if __name__ == "__main__":
    unittest.main()
