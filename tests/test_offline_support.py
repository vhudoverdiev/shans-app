import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "base.html"
REGISTRATION_SCRIPT = PROJECT_ROOT / "app" / "static" / "js" / "offline-support.js"
SERVICE_WORKER = PROJECT_ROOT / "app" / "static" / "service-worker.js"
OFFLINE_PAGE = PROJECT_ROOT / "app" / "static" / "offline.html"


class OfflineSupportTests(unittest.TestCase):
    def test_service_worker_is_registered_from_every_page(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        script = REGISTRATION_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("filename='js/offline-support.js'", template)
        self.assertIn('navigator.serviceWorker.register("/service-worker.js"', script)
        self.assertIn('scope: "/"', script)
        self.assertIn('updateViaCache: "none"', script)
        self.assertIn("const HEALTH_TIMEOUT_MS = 4500", script)
        self.assertIn('"/health?connection_check="', script)
        self.assertIn("navigator.onLine", script)
        self.assertIn("hasVeryWeakConnectionHint()", script)
        self.assertIn('redirectToOffline("weak")', script)
        self.assertIn("window.location.replace(buildOfflineUrl(reason))", script)

    def test_service_worker_precaches_and_serves_offline_navigation(self):
        service_worker = SERVICE_WORKER.read_text(encoding="utf-8")

        self.assertIn('const OFFLINE_PAGE_URL = "/static/offline.html"', service_worker)
        self.assertIn('const OFFLINE_LOGO_URL = "/static/logo.png"', service_worker)
        self.assertIn("OFFLINE_LOGO_URL", service_worker)
        self.assertIn('addEventListener("install"', service_worker)
        self.assertIn('addEventListener("activate"', service_worker)
        self.assertIn('addEventListener("fetch"', service_worker)
        self.assertIn('event.request.mode !== "navigate"', service_worker)
        self.assertIn("return await fetch(event.request)", service_worker)
        self.assertIn("cache.match(OFFLINE_PAGE_URL)", service_worker)

    def test_offline_page_has_intro_message_and_retry_flow(self):
        page = OFFLINE_PAGE.read_text(encoding="utf-8")

        self.assertIn('class="offline-logo"', page)
        self.assertIn('<img src="/static/logo.png" alt="Логотип Шанс">', page)
        self.assertIn("Отсутствует подключение к интернету", page)
        self.assertIn('id="offline-retry"', page)
        self.assertIn("Повторить попытку", page)
        self.assertIn('window.fetch("/health?offline_retry="', page)
        self.assertIn('cache: "no-store"', page)
        self.assertIn("new URLSearchParams(window.location.search)", page)
        self.assertIn('reason === "weak"', page)
        self.assertIn("Слабое подключение к интернету", page)
        self.assertIn("window.location.assign(returnPath)", page)
        self.assertNotIn("window.location.reload()", page)
        self.assertIn("Интернет всё ещё недоступен", page)


if __name__ == "__main__":
    unittest.main()
