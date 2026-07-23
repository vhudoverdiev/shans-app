const DEFAULT_NOTIFICATION_URL = "/planner.schedule?calendar=personal&view=day";
const DEFAULT_ICON_URL = "/static/apple-touch-icon.png";
const OFFLINE_CACHE_PREFIX = "shans-offline-";
const OFFLINE_CACHE_NAME = `${OFFLINE_CACHE_PREFIX}v1`;
const OFFLINE_PAGE_URL = "/static/offline.html";
const OFFLINE_LOGO_URL = "/static/logo.png";

self.addEventListener("install", function (event) {
    event.waitUntil((async function () {
        const cache = await caches.open(OFFLINE_CACHE_NAME);
        await cache.addAll([
            new Request(OFFLINE_PAGE_URL, { cache: "reload" }),
            new Request(OFFLINE_LOGO_URL, { cache: "reload" }),
        ]);
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
        try {
            return await fetch(event.request);
        } catch (_error) {
            const cache = await caches.open(OFFLINE_CACHE_NAME);
            const offlinePage = await cache.match(OFFLINE_PAGE_URL);
            if (offlinePage) {
                return offlinePage;
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
