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
        self.assertIn('const introKey = "shans-intro-session-v1"', template)
        self.assertIn("window.sessionStorage.getItem(introKey)", template)
        self.assertIn("window.sessionStorage.setItem(introKey, \"1\")", template)
        self.assertIn("if (introAlreadyShown) {", template)
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

    def test_login_page_keeps_first_launch_logo_intro_enabled(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        skip_expression = template.split("{% set skip_intro_loader =", 1)[1].split(
            "%}",
            1,
        )[0]

        self.assertNotIn("request.endpoint == 'login'", skip_expression)
        self.assertIn("{% if request.endpoint == 'login' %} login-centered-document{% endif %}", template)
        self.assertIn(
            '<html lang="ru" class="{% if not skip_intro_loader %}app-intro-pending{% endif %}{% if request.endpoint == \'login\' %}',
            template,
        )
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

    def test_login_intro_respects_existing_session_storage_marker_after_first_show(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        storage_block = template.split('const introKey = "shans-intro-session-v1"', 1)[1].split(
            "if (introAlreadyShown) {",
            1,
        )[0]
        skip_existing_block = template.split("if (introAlreadyShown) {", 1)[1].split(
            "}",
            1,
        )[0]

        self.assertIn("window.sessionStorage.getItem(introKey)", storage_block)
        self.assertIn("window.sessionStorage.setItem(introKey, \"1\")", storage_block)
        self.assertNotIn("forceIntroLoader", storage_block)
        self.assertIn('document.documentElement.classList.remove("app-intro-pending");', skip_existing_block)
        self.assertIn("window.__shansShouldRunIntro = false;", skip_existing_block)
        self.assertIn("return;", skip_existing_block)

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

    def test_installed_pwa_runs_custom_intro_once_per_session(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        standalone_position = template.index("const standaloneDisplayMode")
        session_position = template.index('const introKey = "shans-intro-session-v1"')
        storage_block = template.split('const introKey = "shans-intro-session-v1"', 1)[1].split(
            "if (introAlreadyShown) {",
            1,
        )[0]
        runtime_critical_styles = template.split("</noscript>", 1)[1].split(
            "{% set static_asset_version",
            1,
        )[0]

        self.assertLess(standalone_position, session_position)
        self.assertNotIn("forceIntroLoader", template)
        self.assertIn("window.sessionStorage.getItem(introKey)", storage_block)
        self.assertNotIn("if (isStandaloneApp) {", template)
        self.assertNotIn("display: none !important;", runtime_critical_styles)

    def test_standalone_critical_css_does_not_hide_custom_intro(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        runtime_critical_styles = template.split("</noscript>", 1)[1].split(
            "{% set static_asset_version",
            1,
        )[0]

        self.assertNotIn("@media (display-mode: standalone)", template)
        self.assertNotIn("display: none !important;", runtime_critical_styles)

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

    def test_standalone_detection_tolerates_missing_navigator(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            "|| (window.navigator && window.navigator.standalone === true)",
            template,
        )

    def test_intro_script_cleans_up_after_animation(self):
        script = INTRO_SCRIPT.read_text(encoding="utf-8")

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

    def test_intro_script_does_not_cancel_standalone_before_showing_logo(self):
        script = INTRO_SCRIPT.read_text(encoding="utf-8")

        show_logo_position = script.index("intro.hidden = false")

        self.assertNotIn("function isStandaloneApp()", script)
        self.assertNotIn("if (isStandaloneApp())", script)
        self.assertNotIn("window.navigator.standalone", script)
        self.assertLess(script.index("waitForIntroLogoImage().then"), show_logo_position)

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
        self.assertIn("position: absolute;", critical_logo)
        self.assertIn(
            "top: calc(50% - var(--app-intro-composition-offset) - var(--app-intro-visual-lift));",
            critical_logo,
        )
        self.assertIn("left: 50%;", critical_logo)
        self.assertIn("transform: translate(-50%, -50%) scale(0.94);", critical_logo)
        self.assertIn("background: transparent;", critical_logo)
        self.assertIn("position: absolute;", critical_progress)
        self.assertIn(
            "top: calc(50% + (var(--app-intro-logo-size) / 2) + var(--app-intro-progress-gap) - var(--app-intro-composition-offset) - var(--app-intro-visual-lift));",
            critical_progress,
        )
        self.assertIn("left: 50%;", critical_progress)
        self.assertIn("opacity: 0;", critical_progress)
        self.assertIn("transform: translate(-50%, 6px);", critical_progress)

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

    def test_intro_running_logo_is_visible_without_start_delay(self):
        stylesheet = STYLESHEET.read_text(encoding="utf-8")
        running_logo = stylesheet.split(".app-intro-running .app-intro-logo {", 1)[1].split(
            "}",
            1,
        )[0]
        logo_keyframes = stylesheet.split("@keyframes app-intro-logo-in {", 1)[1].split(
            "@keyframes app-intro-progress-in",
            1,
        )[0]

        self.assertIn("opacity: 1;", running_logo)
        self.assertIn("transform: translate(-50%, -50%) scale(1);", running_logo)
        self.assertIn("animation: app-intro-logo-in 0.32s ease-out both;", running_logo)
        self.assertNotIn("0.08s", running_logo)
        self.assertNotIn("opacity: 0;", logo_keyframes)
        self.assertIn("transform: translate(-50%, -50%) scale(1);", logo_keyframes)

    def test_intro_logo_is_centered_independently_from_progress_bar(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        stylesheet = STYLESHEET.read_text(encoding="utf-8")
        critical_stage = template.split("html.app-intro-pending .app-intro-stage {", 1)[1].split(
            "}",
            1,
        )[0]
        runtime_stage = stylesheet.split(".app-intro-stage {", 1)[1].split(
            "}",
            1,
        )[0]
        runtime_logo = stylesheet.split(".app-intro-logo {", 1)[1].split(
            "}",
            1,
        )[0]
        runtime_progress = stylesheet.split(".app-intro-progress {", 1)[1].split(
            "}",
            1,
        )[0]

        for stage_block in (critical_stage, runtime_stage):
            self.assertIn("--app-intro-logo-size:", stage_block)
            self.assertIn("--app-intro-progress-gap:", stage_block)
            self.assertIn("--app-intro-progress-height:", stage_block)
            self.assertIn("--app-intro-visual-lift:", stage_block)
            self.assertIn("--app-intro-composition-offset:", stage_block)
            self.assertIn("display: grid;", stage_block)
            self.assertIn("place-items: center;", stage_block)
            self.assertNotIn("flex-direction: column;", stage_block)

        self.assertIn("position: absolute;", runtime_logo)
        self.assertIn(
            "top: calc(50% - var(--app-intro-composition-offset) - var(--app-intro-visual-lift));",
            runtime_logo,
        )
        self.assertIn("left: 50%;", runtime_logo)
        self.assertIn("transform: translate(-50%, -50%) scale(0.94);", runtime_logo)
        self.assertIn("position: absolute;", runtime_progress)
        self.assertIn(
            "top: calc(50% + (var(--app-intro-logo-size) / 2) + var(--app-intro-progress-gap) - var(--app-intro-composition-offset) - var(--app-intro-visual-lift));",
            runtime_progress,
        )
        self.assertIn("left: 50%;", runtime_progress)
        self.assertNotIn("margin-top:", runtime_progress)

    def test_intro_has_extra_visual_lift_in_standalone_app_mode(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        stylesheet = STYLESHEET.read_text(encoding="utf-8")

        self.assertIn("html.shans-standalone-app.app-intro-pending .app-intro-stage", template)
        self.assertIn("--app-intro-visual-lift: 58px;", template)
        self.assertIn("html.shans-standalone-app .app-intro-stage", stylesheet)
        self.assertIn("--app-intro-visual-lift: 58px;", stylesheet)

    def test_intro_progress_bar_is_styled_loader_not_plain_line(self):
        stylesheet = STYLESHEET.read_text(encoding="utf-8")
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        progress_block = stylesheet.split(".app-intro-progress {", 1)[1].split(
            "}",
            1,
        )[0]
        progress_fill_block = stylesheet.split(".app-intro-progress span {", 1)[1].split(
            "}",
            1,
        )[0]
        progress_flow_keyframes = stylesheet.split("@keyframes app-intro-progress-flow {", 1)[1].split(
            "@media (max-width: 768px)",
            1,
        )[0]

        self.assertNotIn("translateX(-105%)", stylesheet)
        self.assertNotIn("@keyframes app-intro-progress {", stylesheet)
        self.assertNotIn("app-intro-orbit", template)
        self.assertNotIn("app-intro-orbit", stylesheet)
        self.assertNotIn("app-intro-glow", template)
        self.assertNotIn("app-intro-glow", stylesheet)
        self.assertIn("height: var(--app-intro-progress-height);", progress_block)
        self.assertIn("padding: 2px;", progress_block)
        self.assertIn(
            "top: calc(50% + (var(--app-intro-logo-size) / 2) + var(--app-intro-progress-gap) - var(--app-intro-composition-offset) - var(--app-intro-visual-lift));",
            progress_block,
        )
        self.assertIn("border: 1px solid rgba(124, 58, 237, 0.16);", progress_block)
        self.assertIn("box-shadow:", progress_block)
        self.assertIn("background-size: 220% 100%;", progress_fill_block)
        self.assertIn("animation: app-intro-progress-flow 1.08s ease-in-out infinite;", progress_fill_block)
        self.assertIn("@keyframes app-intro-progress-in", stylesheet)
        self.assertIn("@keyframes app-intro-progress-flow", stylesheet)
        self.assertIn("background-position: 100% 50%;", progress_flow_keyframes)
        self.assertIn("transform: scaleX(1);", progress_flow_keyframes)

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
