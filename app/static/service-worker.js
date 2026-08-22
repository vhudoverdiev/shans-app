const DEFAULT_NOTIFICATION_URL = "/planner.schedule?calendar=personal&view=day";
const DEFAULT_ICON_URL = "/static/pwa-icon-512-shans-v2.png";
const OFFLINE_CACHE_PREFIX = "shans-offline-";
const OFFLINE_CACHE_NAME = `${OFFLINE_CACHE_PREFIX}v22`;
const OFFLINE_PAGE_URL = "/static/offline.html";
const OFFLINE_LOGO_URL = "/static/logo.png";
const NAVIGATION_TIMEOUT_MS = 3000;

const CRITICAL_RESOURCE_DESTINATIONS = new Set(["style", "script"]);

async function fetchWithTimeout(request) {
    const controller = new AbortController();
    let timeoutId;
    const timeoutPromise = new Promise(function (_resolve, reject) {
        timeoutId = setTimeout(function () {
            controller.abort();
            reject(new Error("Network request timed out"));
        }, NAVIGATION_TIMEOUT_MS);
    });

    try {
        return await Promise.race([
            fetch(request, { signal: controller.signal }),
            timeoutPromise,
        ]);
    } finally {
        clearTimeout(timeoutId);
    }
}

function buildInterferenceUrl(returnPath) {
    const offlineUrl = new URL(OFFLINE_PAGE_URL, self.location.origin);
    offlineUrl.searchParams.set("reason", "interference");
    offlineUrl.searchParams.set("return", returnPath || "/");
    return offlineUrl.href;
}

async function addLaunchContext(response, returnPath) {
    const headers = new Headers(response.headers);
    headers.delete("Content-Length");
    headers.delete("Content-Encoding");
    headers.delete("ETag");
    const html = await response.text();
    const launchContext = `<script>window.__shansLaunchCheck=true;window.__shansLaunchReturn=${JSON.stringify(returnPath)};</script>`;
    return new Response(html.replace("</head>", `${launchContext}</head>`), {
        status: response.status,
        statusText: response.statusText,
        headers: headers,
    });
}

self.addEventListener("install", function (event) {
    event.waitUntil((async function () {
        const cache = await caches.open(OFFLINE_CACHE_NAME);
        // Cache entries independently so the offline document can still install
        // if the canonical logo request fails temporarily.
        await cache.add(new Request(OFFLINE_PAGE_URL, { cache: "reload" }));
        try {
            await cache.add(new Request(OFFLINE_LOGO_URL, { cache: "reload" }));
        } catch (_error) {
            // A later controlled logo request gets another chance to populate it.
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
    if (event.request.method !== "GET") {
        return;
    }

    const requestUrl = new URL(event.request.url);
    const isNavigation = event.request.mode === "navigate";
    const isCriticalResource = requestUrl.origin === self.location.origin
        && CRITICAL_RESOURCE_DESTINATIONS.has(event.request.destination);
    const isCanonicalLogo = requestUrl.origin === self.location.origin
        && requestUrl.pathname === OFFLINE_LOGO_URL;

    if (!isNavigation && !isCriticalResource && !isCanonicalLogo) {
        return;
    }

    event.respondWith((async function () {
        const cache = await caches.open(OFFLINE_CACHE_NAME);
        if (isCanonicalLogo) {
            const cachedLogo = await cache.match(OFFLINE_LOGO_URL, { ignoreSearch: true });
            if (cachedLogo) {
                return cachedLogo;
            }
            const networkLogo = await fetch(event.request);
            if (networkLogo.ok) {
                await cache.put(OFFLINE_LOGO_URL, networkLogo.clone());
            }
            return networkLogo;
        }
        if (requestUrl.pathname === OFFLINE_PAGE_URL) {
            const cachedOfflinePage = await cache.match(OFFLINE_PAGE_URL);
            if (cachedOfflinePage) {
                return cachedOfflinePage;
            }
        }

        const isColdLaunch = isNavigation
            && requestUrl.searchParams.has("_shans_launch")
            && !requestUrl.searchParams.has("_shans_network");
        if (isColdLaunch) {
            const launchPage = await cache.match(OFFLINE_PAGE_URL);
            if (launchPage) {
                const returnUrl = new URL(requestUrl.href);
                returnUrl.searchParams.delete("_shans_launch");
                const returnPath = returnUrl.pathname + returnUrl.search + returnUrl.hash;
                return addLaunchContext(launchPage, returnPath);
            }
        }

        try {
            const networkResponse = await fetchWithTimeout(event.request);
            if (isCriticalResource && networkResponse.ok) {
                await cache.put(event.request, networkResponse.clone());
            }
            return networkResponse;
        } catch (_error) {
            if (isCriticalResource) {
                const cachedResource = await cache.match(event.request, { ignoreSearch: true });
                if (cachedResource) {
                    return cachedResource;
                }
            }
            const offlinePage = await cache.match(OFFLINE_PAGE_URL);
            if (offlinePage) {
                if (isCriticalResource) {
                    const windowClient = event.clientId
                        ? await self.clients.get(event.clientId)
                        : null;
                    const clientUrl = windowClient ? new URL(windowClient.url) : null;
                    const returnPath = clientUrl
                        ? clientUrl.pathname + clientUrl.search + clientUrl.hash
                        : "/";
                    if (windowClient && "navigate" in windowClient) {
                        try {
                            await windowClient.navigate(buildInterferenceUrl(returnPath));
                        } catch (_navigationError) {
                            // The JavaScript fallback below handles iOS clients
                            // that reject WindowClient.navigate while launching.
                        }
                    }
                    const interferenceUrl = buildInterferenceUrl(returnPath);
                    const fallbackBody = event.request.destination === "script"
                        ? `window.location.replace(${JSON.stringify(interferenceUrl)});`
                        : "";
                    return new Response(fallbackBody, {
                        status: 504,
                        headers: {
                            "Content-Type": event.request.destination === "style"
                                ? "text/css; charset=utf-8"
                                : "application/javascript; charset=utf-8",
                        },
                    });
                }
                const returnPath = requestUrl.pathname + requestUrl.search + requestUrl.hash;
                return Response.redirect(buildInterferenceUrl(returnPath), 302);
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
