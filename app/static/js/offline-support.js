(function () {
    "use strict";

    if (!("serviceWorker" in navigator) || !window.isSecureContext) {
        return;
    }

    window.addEventListener("load", function () {
        navigator.serviceWorker.register("/service-worker.js", {
            scope: "/",
            updateViaCache: "none",
        }).catch(function () {
            // Offline support is progressive enhancement; the site remains usable without it.
        });
    }, { once: true });
}());
