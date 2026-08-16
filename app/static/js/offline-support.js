(function () {
    "use strict";

    const OFFLINE_PAGE_URL = "/static/offline.html";
    let connectionLost = document.documentElement.dataset.shansOfflineSnapshot === "true";
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
        const currentUrl = new URL(window.location.href);
        if (currentUrl.searchParams.has("_shans_network")) {
            currentUrl.searchParams.delete("_shans_network");
            window.history.replaceState(null, "", currentUrl.pathname + currentUrl.search + currentUrl.hash);
        }
        navigator.serviceWorker.register("/service-worker.js", {
            scope: "/",
            updateViaCache: "none",
        }).catch(function () {
            // Offline support is progressive enhancement; the site remains usable without it.
        });
    }, { once: true });

    window.addEventListener("offline", function () {
        connectionLost = true;
    });

    window.addEventListener("online", function () {
        connectionLost = false;
    });

    document.addEventListener("submit", function (event) {
        if (!connectionLost || event.defaultPrevented) {
            return;
        }
        event.preventDefault();
        redirectToOffline("offline");
    });
}());
