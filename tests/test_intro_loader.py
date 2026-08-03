import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "base.html"
STYLESHEET = PROJECT_ROOT / "app" / "static" / "css" / "style.css"
INTRO_SCRIPT = PROJECT_ROOT / "app" / "static" / "js" / "intro-loader.js"


class IntroLoaderTests(unittest.TestCase):
    def test_base_template_bootstraps_session_intro(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("skip_intro_loader", template)
        self.assertIn("request.endpoint in [", template)
        self.assertIn("'learning.english_day_test'", template)
        self.assertIn("'learning.it_day_test'", template)
        self.assertIn("'workouts.plan_detail'", template)
        self.assertIn("'workouts.edit_plan'", template)
        self.assertIn("'nutrition.edit_profile'", template)
        self.assertIn("const skipIntroLoader = {{ 'true' if skip_intro_loader else 'false' }};", template)
        self.assertIn("if (skipIntroLoader) {", template)
        self.assertIn('document.documentElement.classList.remove("app-intro-pending");', template)
        self.assertIn("window.__shansShouldRunIntro = false;", template)
        self.assertIn(
            '<html lang="ru" class="{% if not skip_intro_loader %}app-intro-pending{% endif %}',
            template,
        )
        self.assertIn("const standaloneDisplayMode = window.matchMedia", template)
        self.assertIn('window.matchMedia("(display-mode: standalone)").matches', template)
        self.assertIn("const isStandaloneApp = standaloneDisplayMode", template)
        self.assertIn("window.navigator.standalone === true", template)
        self.assertIn('classList.add("shans-standalone-app")', template)
        self.assertIn("if (isStandaloneApp) {", template)
        self.assertIn("window.__shansShouldRunIntro = false", template)
        self.assertIn('const introKey = "shans-intro-session-v1"', template)
        self.assertIn("window.sessionStorage.getItem(introKey)", template)
        self.assertIn("window.sessionStorage.setItem(introKey, \"1\")", template)
        self.assertIn("window.__shansShouldRunIntro = true", template)
        self.assertIn("function scheduleIntroFallback()", template)
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
        self.assertIn("{% if not skip_intro_loader %}", template)
        self.assertIn("filename='js/intro-loader.js'", template)

    def test_day_test_pages_do_not_render_intro_loader_markup(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("skip_intro_loader", template)
        self.assertIn("return;", template.split("if (skipIntroLoader) {", 1)[1].split("}", 1)[0])
        self.assertIn(
            "{% if not skip_intro_loader %}\n"
            "    <script src=\"{{ url_for('static', filename='js/intro-loader.js'",
            template,
        )
        self.assertIn(
            "{% if not skip_intro_loader %}\n"
            "    <div class=\"app-intro\" id=\"app-intro\"",
            template,
        )

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
        standalone_position = template.index("const standaloneDisplayMode")
        session_position = template.index('const introKey = "shans-intro-session-v1"')
        standalone_block = template.split("if (isStandaloneApp) {", 1)[1].split("}", 1)[0]

        self.assertLess(standalone_position, session_position)
        self.assertIn('document.documentElement.classList.remove("app-intro-pending");', standalone_block)
        self.assertIn("window.__shansShouldRunIntro = false;", standalone_block)
        self.assertIn("return;", standalone_block)

    def test_standalone_css_prevents_second_logo_before_javascript_finishes(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        standalone_css = template.split("@media (display-mode: standalone)", 1)[1].split(
            "</style>",
            1,
        )[0]

        self.assertIn("html.app-intro-pending body > :not(#app-intro)", standalone_css)
        self.assertIn("visibility: visible !important;", standalone_css)
        self.assertIn("html.app-intro-pending #app-intro", standalone_css)
        self.assertIn("display: none !important;", standalone_css)

    def test_storage_unavailable_still_runs_first_visit_intro(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        storage_catch = template.split("} catch (storageError) {", 1)[1].split(
            "}",
            1,
        )[0]
        bootstrap_catch = template.split("} catch (error) {", 1)[1].split(
            "</script>",
            1,
        )[0]

        self.assertIn("introAlreadyShown = false;", storage_catch)
        self.assertIn("window.__shansShouldRunIntro = true;", bootstrap_catch)
        self.assertIn("scheduleIntroFallback();", bootstrap_catch)
        self.assertNotIn(
            'document.documentElement.classList.remove("app-intro-pending");',
            bootstrap_catch,
        )

    def test_standalone_checks_tolerate_missing_navigator(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        script = INTRO_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "|| (window.navigator && window.navigator.standalone === true)",
            template,
        )
        self.assertIn(
            "|| (window.navigator && window.navigator.standalone === true)",
            script,
        )

    def test_intro_script_cleans_up_after_animation(self):
        script = INTRO_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function isStandaloneApp()", script)
        self.assertIn("function removeIntroWithoutAnimation()", script)
        self.assertIn('classList.contains("app-intro-pending")', script)
        self.assertIn("!window.__shansShouldRunIntro", script)
        self.assertIn("intro.hidden = false", script)
        self.assertIn("function waitForIntroLogoImage()", script)
        self.assertIn('intro.querySelector(".app-intro-logo-mark")', script)
        self.assertIn("logoImage.decode()", script)
        self.assertIn('classList.add("app-intro-running")', script)
        self.assertIn('classList.add("app-intro-leaving")', script)
        self.assertIn("intro.remove()", script)
        self.assertIn("window.__shansShouldRunIntro = false", script)
        self.assertIn("window.clearTimeout(window.__shansIntroFallbackTimer)", script)
        self.assertIn("prefers-reduced-motion: reduce", script)

    def test_intro_script_rechecks_standalone_before_showing_logo(self):
        script = INTRO_SCRIPT.read_text(encoding="utf-8")

        standalone_check_position = script.index("if (isStandaloneApp())")
        show_logo_position = script.index("intro.hidden = false")
        standalone_block = script.split("if (isStandaloneApp()) {", 1)[1].split("}", 1)[0]

        self.assertLess(standalone_check_position, show_logo_position)
        self.assertIn("removeIntroWithoutAnimation();", standalone_block)
        self.assertIn("return;", standalone_block)

    def test_intro_waits_for_logo_before_revealing_logo_container(self):
        script = INTRO_SCRIPT.read_text(encoding="utf-8")
        wait_position = script.index("waitForIntroLogoImage().then")
        show_logo_position = script.index("intro.hidden = false")
        running_position = script.index('classList.add("app-intro-running")')

        self.assertLess(wait_position, show_logo_position)
        self.assertLess(show_logo_position, running_position)
        self.assertIn("logoImage.addEventListener(\"load\", finish)", script)
        self.assertIn("logoImage.addEventListener(\"error\", finish)", script)
        self.assertIn("window.setTimeout(finish, 700)", script)

    def test_critical_intro_css_keeps_logo_hidden_until_image_is_ready(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        critical_logo = template.split("html.app-intro-pending .app-intro-logo {", 1)[1].split(
            "}",
            1,
        )[0]
        critical_progress = template.split("html.app-intro-pending .app-intro-progress {", 1)[1].split(
            "}",
            1,
        )[0]

        self.assertIn("opacity: 0;", critical_logo)
        self.assertIn("transform: translateY(8px) scale(0.94);", critical_logo)
        self.assertIn("background: transparent;", critical_logo)
        self.assertIn("opacity: 0;", critical_progress)
        self.assertIn("transform: translateY(6px);", critical_progress)

    def test_intro_logo_container_does_not_paint_before_logo_image(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        stylesheet = STYLESHEET.read_text(encoding="utf-8")
        critical_logo = template.split("html.app-intro-pending .app-intro-logo {", 1)[1].split(
            "}",
            1,
        )[0]
        runtime_logo = stylesheet.split(".app-intro-logo {", 1)[1].split(
            "}",
            1,
        )[0]

        for logo_block in (critical_logo, runtime_logo):
            self.assertIn("background: transparent;", logo_block)
            self.assertNotIn("linear-gradient(135deg, #2563eb, #7c3aed)", logo_block)
        self.assertIn("filename='logo.png'", template)

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
