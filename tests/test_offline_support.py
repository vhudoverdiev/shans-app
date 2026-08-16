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

    def test_real_offline_browser_event_opens_the_offline_page(self):
        script = REGISTRATION_SCRIPT.read_text(encoding="utf-8")

        offline_listener = script.split('window.addEventListener("offline"', 1)[1]
        self.assertIn('redirectToOffline("offline")', offline_listener)
        self.assertIn('target.searchParams.set("reason", reason || "offline")', script)

    def test_service_worker_precaches_and_serves_offline_navigation(self):
        service_worker = SERVICE_WORKER.read_text(encoding="utf-8")

        self.assertIn('const OFFLINE_PAGE_URL = "/static/offline.html"', service_worker)
        self.assertIn('const DEFAULT_ICON_URL = "/static/pwa-icon-512-shans-v2.png"', service_worker)
        self.assertIn('const OFFLINE_LOGO_URL = "/static/logo.png"', service_worker)
        self.assertIn("OFFLINE_LOGO_URL", service_worker)
        self.assertIn('addEventListener("install"', service_worker)
        self.assertIn('addEventListener("activate"', service_worker)
        self.assertIn('addEventListener("fetch"', service_worker)
        self.assertIn('event.request.mode !== "navigate"', service_worker)
        self.assertIn("return await fetch(event.request)", service_worker)
        self.assertIn("cache.match(OFFLINE_PAGE_URL)", service_worker)
        self.assertNotIn("cache.addAll", service_worker)
        self.assertIn('requestUrl.pathname === OFFLINE_PAGE_URL', service_worker)
        self.assertIn('offlineUrl.searchParams.set("reason", "interference")', service_worker)
        self.assertIn("Response.redirect(offlineUrl.href, 302)", service_worker)

    def test_optional_logo_failure_cannot_cancel_offline_cache_installation(self):
        service_worker = SERVICE_WORKER.read_text(encoding="utf-8")

        offline_page_cache = 'await cache.add(new Request(OFFLINE_PAGE_URL, { cache: "reload" }));'
        logo_cache = 'await cache.add(new Request(OFFLINE_LOGO_URL, { cache: "reload" }));'
        self.assertLess(service_worker.index(offline_page_cache), service_worker.index("try {"))
        self.assertIn(logo_cache, service_worker)
        self.assertIn("catch (_error)", service_worker)
        self.assertNotIn("cache.addAll", service_worker)

    def test_unreachable_site_redirects_to_interference_message_without_looping(self):
        service_worker = SERVICE_WORKER.read_text(encoding="utf-8")
        page = OFFLINE_PAGE.read_text(encoding="utf-8")

        self.assertIn('offlineUrl.searchParams.set("reason", "interference")', service_worker)
        self.assertIn('offlineUrl.searchParams.set("return", returnPath)', service_worker)
        self.assertIn('requestUrl.pathname === OFFLINE_PAGE_URL', service_worker)
        self.assertIn("return cachedOfflinePage", service_worker)
        self.assertIn('reason === "interference"', page)
        self.assertIn("Интернет недоступен или связь глушат", page)
        self.assertIn("Возможно, связь глушат. Включите белые списки", page)

    def test_offline_logo_has_network_independent_sh_fallback(self):
        page = OFFLINE_PAGE.read_text(encoding="utf-8")

        self.assertIn('<span class="offline-logo-fallback" aria-hidden="true">Ш</span>', page)
        self.assertIn('onerror="this.hidden=true"', page)
        self.assertLess(page.index("offline-logo-fallback"), page.index('src="/static/logo.png"'))

    def test_offline_page_has_intro_message_and_retry_flow(self):
        page = OFFLINE_PAGE.read_text(encoding="utf-8")

        self.assertIn('class="offline-logo"', page)
        self.assertIn('class="offline-logo-fallback"', page)
        self.assertIn('>Ш</span>', page)
        self.assertIn('onerror="this.hidden=true"', page)
        self.assertIn("Отсутствует подключение к интернету", page)
        self.assertIn('id="offline-retry"', page)
        self.assertIn("Повторить попытку", page)
        self.assertIn('window.fetch("/health?offline_retry="', page)
        self.assertIn('cache: "no-store"', page)
        self.assertIn("}, 12000);", page)
        self.assertIn("new URLSearchParams(window.location.search)", page)
        self.assertIn('reason === "weak"', page)
        self.assertIn("Слабое подключение к интернету", page)
        self.assertIn('reason === "interference"', page)
        self.assertIn("Интернет недоступен или связь глушат", page)
        self.assertIn("Возможно, связь глушат. Включите белые списки", page)
        self.assertIn("window.location.assign(returnPath)", page)
        self.assertNotIn("window.location.reload()", page)
        self.assertIn("Интернет всё ещё недоступен", page)


if __name__ == "__main__":
    unittest.main()
