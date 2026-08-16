(function () {
    "use strict";

    const OFFLINE_PAGE_URL = "/static/offline.html";
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

    window.addEventListener("load", function () {
        navigator.serviceWorker.register("/service-worker.js", {
            scope: "/",
            updateViaCache: "none",
        }).catch(function () {
            // Offline support is progressive enhancement; the site remains usable without it.
        });
    }, { once: true });

    window.addEventListener("offline", function () {
        redirectToOffline("offline");
    });
}());
