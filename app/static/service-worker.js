const DEFAULT_NOTIFICATION_URL = "/planner.schedule?calendar=personal&view=day";
const DEFAULT_ICON_URL = "/static/pwa-icon-512-shans-v2.png";
const OFFLINE_CACHE_PREFIX = "shans-offline-";
const OFFLINE_CACHE_NAME = `${OFFLINE_CACHE_PREFIX}v3`;
const OFFLINE_PAGE_URL = "/static/offline.html";
const OFFLINE_LOGO_URL = "/static/logo.png";

self.addEventListener("install", function (event) {
    event.waitUntil((async function () {
        const cache = await caches.open(OFFLINE_CACHE_NAME);
        // Cache entries independently: an optional image must never prevent the
        // offline document and the new worker from being installed.
        await cache.add(new Request(OFFLINE_PAGE_URL, { cache: "reload" }));
        try {
            await cache.add(new Request(OFFLINE_LOGO_URL, { cache: "reload" }));
        } catch (_error) {
            // The offline page contains its own logo fallback.
        }
        await self.skipWaiting();
    })());
});

self.addEventListener("activate", function (event) {
    event.waitUntil((async function () {
        const cacheNames = await caches.keys();
        await Promise.all(cacheNames.map(function (cacheName) {
            if (cacheName.startsWith(OFFLINE_CACHE_PREFIX) && cacheName !== OFFLINE_CACHE_NAME) {
                return caches.delete(cacheName);
            }
            return Promise.resolve(false);
        }));
        await self.clients.claim();
    })());
});

self.addEventListener("fetch", function (event) {
    if (event.request.method !== "GET" || event.request.mode !== "navigate") {
        return;
    }

    event.respondWith((async function () {
        const requestUrl = new URL(event.request.url);
        const cache = await caches.open(OFFLINE_CACHE_NAME);

        if (requestUrl.pathname === OFFLINE_PAGE_URL) {
            const cachedOfflinePage = await cache.match(OFFLINE_PAGE_URL);
            if (cachedOfflinePage) {
                return cachedOfflinePage;
            }
        }

        try {
            return await fetch(event.request);
        } catch (_error) {
            const offlinePage = await cache.match(OFFLINE_PAGE_URL);
            if (offlinePage) {
                const returnPath = requestUrl.pathname + requestUrl.search + requestUrl.hash;
                const offlineUrl = new URL(OFFLINE_PAGE_URL, self.location.origin);
                offlineUrl.searchParams.set("reason", "interference");
                offlineUrl.searchParams.set("return", returnPath);
                return Response.redirect(offlineUrl.href, 302);
            }
            return new Response("Отсутствует подключение к интернету.", {
                status: 503,
                headers: { "Content-Type": "text/plain; charset=utf-8" },
            });
        }
    })());
});

self.addEventListener("push", function (event) {
    event.waitUntil((async function () {
        let payload = {};
        if (event.data) {
            try {
                payload = event.data.json();
            } catch (_error) {
                payload = { notification: { body: event.data.text() } };
            }
        }

        const notification = payload.notification || payload;
        const title = notification.title || "Шанс";
        const navigate = notification.navigate || DEFAULT_NOTIFICATION_URL;
        await self.registration.showNotification(title, {
            body: notification.body || "Новое уведомление личного графика.",
            icon: notification.icon || DEFAULT_ICON_URL,
            badge: DEFAULT_ICON_URL,
            tag: notification.tag || "shans-schedule",
            silent: Boolean(notification.silent),
            data: { navigate: navigate },
        });

        const windows = await self.clients.matchAll({
            type: "window",
            includeUncontrolled: true,
        });
        windows.forEach(function (windowClient) {
            windowClient.postMessage({ type: "shans-push-received" });
        });
    })());
});

self.addEventListener("notificationclick", function (event) {
    event.notification.close();
    const targetUrl = new URL(
        event.notification.data && event.notification.data.navigate
            ? event.notification.data.navigate
            : DEFAULT_NOTIFICATION_URL,
        self.location.origin
    ).href;

    event.waitUntil((async function () {
        const windows = await self.clients.matchAll({
            type: "window",
            includeUncontrolled: true,
        });
        for (const windowClient of windows) {
            if (windowClient.url.startsWith(self.location.origin)) {
                if ("navigate" in windowClient) {
                    await windowClient.navigate(targetUrl);
                }
                return windowClient.focus();
            }
        }
        return self.clients.openWindow(targetUrl);
    })());
});
