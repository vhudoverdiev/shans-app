(function () {
    "use strict";

    const OFFLINE_PAGE_URL = "/static/offline.html";
    const HEALTH_TIMEOUT_MS = 4500;
    const SLOW_CONNECTION_TYPES = new Set(["slow-2g", "2g"]);

    if (!("serviceWorker" in navigator) || !window.isSecureContext) {
        return;
    }

    function isOfflinePage() {
        return window.location.pathname === OFFLINE_PAGE_URL;
    }

    function buildOfflineUrl(reason) {
        const target = new URL(OFFLINE_PAGE_URL, window.location.origin);
        target.searchParams.set("reason", reason || "offline");
        target.searchParams.set(
            "return",
            window.location.pathname + window.location.search + window.location.hash,
        );
        return target.href;
    }

    function redirectToOffline(reason) {
        if (isOfflinePage()) {
            return;
        }
        window.location.replace(buildOfflineUrl(reason));
    }

    function hasVeryWeakConnectionHint() {
        const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
        if (!connection) {
            return false;
        }
        if (SLOW_CONNECTION_TYPES.has(connection.effectiveType)) {
            return true;
        }
        return typeof connection.downlink === "number" && connection.downlink > 0 && connection.downlink < 0.15;
    }

    async function verifyReachable() {
        if (!window.fetch || !window.AbortController) {
            return;
        }
        if (!navigator.onLine) {
            redirectToOffline("offline");
            return;
        }
        if (hasVeryWeakConnectionHint()) {
            redirectToOffline("weak");
            return;
        }

        const controller = new AbortController();
        const timeoutId = window.setTimeout(function () {
            controller.abort();
        }, HEALTH_TIMEOUT_MS);

        try {
            const response = await window.fetch("/health?connection_check=" + Date.now(), {
                cache: "no-store",
                credentials: "same-origin",
                signal: controller.signal,
            });
            if (!response.ok) {
                redirectToOffline("weak");
            }
        } catch (_error) {
            redirectToOffline(navigator.onLine ? "weak" : "offline");
        } finally {
            window.clearTimeout(timeoutId);
        }
    }

    window.addEventListener("load", function () {
        navigator.serviceWorker.register("/service-worker.js", {
            scope: "/",
            updateViaCache: "none",
        }).catch(function () {
            // Offline support is progressive enhancement; the site remains usable without it.
        });

        verifyReachable();
    }, { once: true });

    window.addEventListener("offline", function () {
        redirectToOffline("offline");
    });
}());
