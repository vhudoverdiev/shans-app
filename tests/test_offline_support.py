import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "base.html"
REGISTRATION_SCRIPT = PROJECT_ROOT / "app" / "static" / "js" / "offline-support.js"
SERVICE_WORKER = PROJECT_ROOT / "app" / "static" / "service-worker.js"
OFFLINE_PAGE = PROJECT_ROOT / "app" / "static" / "offline.html"


class OfflineSupportTests(unittest.TestCase):
    def test_service_worker_is_registered_without_blocking_vpn_connections(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        script = REGISTRATION_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("filename='js/offline-support.js'", template)
        self.assertIn('navigator.serviceWorker.register("/service-worker.js"', script)
        self.assertIn('scope: "/"', script)
        self.assertIn('updateViaCache: "none"', script)
        self.assertIn('window.addEventListener("offline"', script)
        self.assertNotIn("navigator.onLine", script)
        self.assertNotIn("navigator.connection", script)
        self.assertNotIn("effectiveType", script)
        self.assertNotIn("downlink", script)
        self.assertNotIn("showOfflinePageWhenDisconnected", script)
        self.assertNotIn('"/health?connection_check="', script)
        self.assertIn("window.location.replace(buildOfflineUrl(reason))", script)

    def test_lte_and_vpn_are_not_rejected_by_connection_quality_hints(self):
        script = REGISTRATION_SCRIPT.read_text(encoding="utf-8")

        for unreliable_hint in (
            "navigator.connection",
            "mozConnection",
            "webkitConnection",
            "effectiveType",
            "downlink",
            "connection_check",
        ):
            self.assertNotIn(unreliable_hint, script)

    def test_real_offline_event_keeps_current_page_readable_until_navigation(self):
        script = REGISTRATION_SCRIPT.read_text(encoding="utf-8")

        offline_listener = script.split('window.addEventListener("offline"', 1)[1]
        offline_handler = offline_listener.split("});", 1)[0]
        self.assertIn("connectionLost = true", offline_handler)
        self.assertNotIn("redirectToOffline", offline_handler)
        self.assertIn('window.addEventListener("online"', script)
        self.assertIn("connectionLost = false", script)
        self.assertIn('target.searchParams.set("reason", reason || "offline")', script)

    def test_offline_links_can_use_cached_pages_but_forms_stay_blocked(self):
        script = REGISTRATION_SCRIPT.read_text(encoding="utf-8")

        self.assertNotIn('document.addEventListener("click"', script)
        self.assertIn("event.preventDefault()", script)
        self.assertIn('document.addEventListener("submit"', script)
        self.assertIn('redirectToOffline("offline")', script)

    def test_previously_opened_pages_and_assets_are_available_offline_with_notice(self):
        service_worker = SERVICE_WORKER.read_text(encoding="utf-8")

        self.assertIn('const PAGE_CACHE_NAME = "shans-pages-v1"', service_worker)
        self.assertIn("pageCache.put(event.request, networkResponse.clone())", service_worker)
        self.assertIn("pageCache.match(event.request)", service_worker)
        self.assertIn("return addOfflineNotice(cachedPage)", service_worker)
        self.assertIn("Связь потеряна или её глушат. Показана сохранённая версия страницы.", service_worker)
        self.assertIn('data-shans-offline-snapshot="true"', service_worker)
        self.assertIn('dataset.shansOfflineSnapshot === "true"', REGISTRATION_SCRIPT.read_text(encoding="utf-8"))
        self.assertIn("cache.put(event.request, networkResponse.clone())", service_worker)
        self.assertIn("cache.match(event.request, { ignoreSearch: true })", service_worker)

    def test_logout_clears_private_offline_page_cache(self):
        service_worker = SERVICE_WORKER.read_text(encoding="utf-8")

        self.assertIn('["/login", "/logout"].includes(requestUrl.pathname)', service_worker)
        self.assertIn("await caches.delete(PAGE_CACHE_NAME)", service_worker)
        self.assertIn('!["/login", "/logout", OFFLINE_PAGE_URL]', service_worker)
        self.assertIn('new URL(networkResponse.url || requestUrl.href).pathname === "/login"', service_worker)

    def test_service_worker_precaches_and_serves_offline_navigation(self):
        service_worker = SERVICE_WORKER.read_text(encoding="utf-8")

        self.assertIn('const OFFLINE_CACHE_NAME = `${OFFLINE_CACHE_PREFIX}v15`', service_worker)
        self.assertIn('const OFFLINE_PAGE_URL = "/static/offline.html"', service_worker)
        self.assertIn('const DEFAULT_ICON_URL = "/static/pwa-icon-512-shans-v2.png"', service_worker)
        self.assertIn('const OFFLINE_LOGO_URL = "/static/logo.png"', service_worker)
        self.assertIn("OFFLINE_LOGO_URL", service_worker)
        self.assertIn('addEventListener("install"', service_worker)
        self.assertIn('addEventListener("activate"', service_worker)
        self.assertIn('addEventListener("fetch"', service_worker)
        self.assertIn('const isNavigation = event.request.mode === "navigate"', service_worker)
        self.assertIn("const networkResponse = await fetchWithTimeout(event.request)", service_worker)
        self.assertIn("cache.match(OFFLINE_PAGE_URL)", service_worker)
        self.assertNotIn("cache.addAll", service_worker)
        self.assertIn('requestUrl.pathname === OFFLINE_PAGE_URL', service_worker)
        self.assertIn('offlineUrl.searchParams.set("reason", "interference")', service_worker)
        self.assertIn("Response.redirect(buildInterferenceUrl(returnPath), 302)", service_worker)

    def test_optional_logo_failure_cannot_cancel_offline_cache_installation(self):
        service_worker = SERVICE_WORKER.read_text(encoding="utf-8")
        install_block = service_worker.split('self.addEventListener("install"', 1)[1].split(
            'self.addEventListener("activate"', 1
        )[0]

        offline_page_cache = 'await cache.add(new Request(OFFLINE_PAGE_URL, { cache: "reload" }));'
        logo_cache = 'await cache.add(new Request(OFFLINE_LOGO_URL, { cache: "reload" }));'
        self.assertLess(install_block.index(offline_page_cache), install_block.index("try {"))
        self.assertIn(logo_cache, install_block)
        self.assertIn("catch (_error)", install_block)
        self.assertNotIn("cache.addAll", install_block)

    def test_unreachable_site_redirects_to_interference_message_without_looping(self):
        service_worker = SERVICE_WORKER.read_text(encoding="utf-8")
        page = OFFLINE_PAGE.read_text(encoding="utf-8")

        self.assertIn('offlineUrl.searchParams.set("reason", "interference")', service_worker)
        self.assertIn('offlineUrl.searchParams.set("return", returnPath || "/")', service_worker)
        self.assertIn('requestUrl.pathname === OFFLINE_PAGE_URL', service_worker)
        self.assertIn("return cachedOfflinePage", service_worker)
        self.assertIn('reason === "interference"', page)
        self.assertIn("Интернет недоступен или связь глушат", page)
        self.assertIn("Возможно, связь глушат. Включите белые списки", page)

    def test_hanging_navigation_is_aborted_and_falls_back_from_white_screen(self):
        service_worker = SERVICE_WORKER.read_text(encoding="utf-8")

        self.assertIn("const NAVIGATION_TIMEOUT_MS = 3000", service_worker)
        self.assertIn("async function fetchWithTimeout(request)", service_worker)
        self.assertIn("const controller = new AbortController()", service_worker)
        self.assertIn("controller.abort()", service_worker)
        self.assertIn("fetch(request, { signal: controller.signal })", service_worker)
        self.assertIn("return await Promise.race([", service_worker)
        self.assertIn('reject(new Error("Network request timed out"))', service_worker)
        self.assertIn("clearTimeout(timeoutId)", service_worker)
        self.assertIn("const networkResponse = await fetchWithTimeout(event.request)", service_worker)

    def test_hanging_css_or_javascript_redirects_instead_of_leaving_white_screen(self):
        service_worker = SERVICE_WORKER.read_text(encoding="utf-8")

        self.assertIn('new Set(["style", "script"])', service_worker)
        self.assertIn("CRITICAL_RESOURCE_DESTINATIONS.has(event.request.destination)", service_worker)
        self.assertIn("await self.clients.get(event.clientId)", service_worker)
        self.assertIn("await windowClient.navigate(buildInterferenceUrl(returnPath))", service_worker)
        self.assertIn("window.location.replace(${JSON.stringify(interferenceUrl)})", service_worker)
        self.assertIn('event.request.destination === "style"', service_worker)
        self.assertIn('"text/css; charset=utf-8"', service_worker)
        self.assertIn('"application/javascript; charset=utf-8"', service_worker)

    def test_offline_logo_has_network_independent_sh_fallback(self):
        page = OFFLINE_PAGE.read_text(encoding="utf-8")

        self.assertIn('<svg class="offline-logo-fallback" viewBox="0 0 1254 1254"', page)
        self.assertIn('<path fill="#fff"', page)
        self.assertIn('onerror="this.remove()"', page)
        self.assertNotIn('onerror="this.hidden=true"', page)
        self.assertLess(page.index("offline-logo-fallback"), page.index('src="/static/logo.png"'))

    def test_offline_logo_uses_the_same_vertical_geometry_as_online_intro(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        page = OFFLINE_PAGE.read_text(encoding="utf-8")

        self.assertIn("--offline-visual-lift: 44px", page)
        self.assertIn("--app-intro-visual-lift: 44px", template)
        self.assertIn("--offline-visual-lift: 58px", page)
        self.assertIn("--app-intro-visual-lift: 58px", template)
        self.assertIn("top: calc(50% - var(--offline-composition-offset) - var(--offline-visual-lift));", page)
        self.assertIn("transform: translate(-50%, -50%) scale(0.94);", page)
        self.assertIn('window.matchMedia("(display-mode: standalone)")', page)

    def test_offline_intro_animation_matches_online_intro_without_side_fly_in(self):
        page = OFFLINE_PAGE.read_text(encoding="utf-8")

        self.assertIn("animation: offline-logo-in 0.32s ease-out both", page)
        self.assertIn("transform: translate(-50%, -50%) scale(0.98)", page)
        self.assertIn("transform: translate(-50%, -50%) scale(1)", page)
        self.assertIn("animation: offline-progress-in 0.32s ease-out 0.18s both", page)
        self.assertIn("animation: offline-progress-flow 1.08s ease-in-out infinite", page)
        self.assertNotIn("translateY(14px)", page)
        self.assertNotIn("rotate(-5deg)", page)
        self.assertNotIn('class="offline-loader-glow"', page)

    def test_offline_page_has_intro_message_and_retry_flow(self):
        page = OFFLINE_PAGE.read_text(encoding="utf-8")

        self.assertIn('class="offline-logo"', page)
        self.assertIn('class="offline-logo-fallback"', page)
        self.assertIn('<svg class="offline-logo-fallback"', page)
        self.assertIn('onerror="this.remove()"', page)
        self.assertIn("Отсутствует подключение к интернету", page)
        self.assertIn('id="offline-retry"', page)
        self.assertIn("Повторить попытку", page)
        self.assertIn('window.fetch("/health?offline_retry="', page)
        self.assertIn('cache: "no-store"', page)
        self.assertIn("}, 3000);", page)
        self.assertNotIn("}, 12000);", page)
        self.assertIn("new URLSearchParams(window.location.search)", page)
        self.assertIn('reason === "weak"', page)
        self.assertIn("Слабое подключение к интернету", page)
        self.assertIn('reason === "interference"', page)
        self.assertIn("Интернет недоступен или связь глушат", page)
        self.assertIn("Возможно, связь глушат. Включите белые списки", page)
        self.assertIn("window.location.assign(returnPath)", page)
        self.assertNotIn("window.location.reload()", page)
        self.assertIn("Интернет всё ещё недоступен", page)

    def test_recovered_connection_automatically_returns_to_saved_location(self):
        page = OFFLINE_PAGE.read_text(encoding="utf-8")

        self.assertIn('window.addEventListener("online"', page)
        self.assertIn("Соединение появилось. Возвращаем вас на сайт…", page)
        self.assertIn("if (!retryButton.disabled)", page)
        self.assertIn("retryButton.click()", page)
        self.assertIn("window.location.assign(returnPath)", page)
        self.assertIn("window.location.pathname + window.location.search + window.location.hash", REGISTRATION_SCRIPT.read_text(encoding="utf-8"))

    def test_cold_pwa_launch_shows_cached_logo_before_network_check(self):
        service_worker = SERVICE_WORKER.read_text(encoding="utf-8")
        page = OFFLINE_PAGE.read_text(encoding="utf-8")

        self.assertIn("const isColdLaunch = isNavigation", service_worker)
        self.assertIn("!event.request.referrer", service_worker)
        self.assertIn("return addLaunchContext(launchPage, returnPath)", service_worker)
        self.assertIn("window.__shansLaunchCheck=true", service_worker)
        self.assertIn("const isLaunchCheck = window.__shansLaunchCheck === true", page)
        self.assertIn("Promise.all([", page)
        self.assertIn("checkConnection()", page)
        self.assertIn("window.location.assign(buildNetworkReturnPath())", page)
        self.assertIn('currentUrl.searchParams.delete("_shans_network")', REGISTRATION_SCRIPT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
