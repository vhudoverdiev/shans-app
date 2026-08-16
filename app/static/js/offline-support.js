(function () {
    "use strict";

    let connectionLost = false;
    if (!("serviceWorker" in navigator) || !window.isSecureContext) {
        return;
    }

    function showConnectionModal() {
        if (document.getElementById("connection-lost-modal")) {
            return;
        }
        const modal = document.createElement("div");
        modal.id = "connection-lost-modal";
        modal.setAttribute("role", "dialog");
        modal.setAttribute("aria-modal", "true");
        modal.setAttribute("aria-labelledby", "connection-lost-title");
        modal.style.cssText = "position:fixed;inset:0;z-index:30000;display:grid;place-items:center;padding:20px;background:rgba(15,23,42,.48);backdrop-filter:blur(5px);-webkit-backdrop-filter:blur(5px)";
        modal.innerHTML = '<div style="width:min(100%,420px);padding:28px 22px;border-radius:24px;background:#fff;box-shadow:0 28px 70px rgba(15,23,42,.24);text-align:center;color:#111827"><div aria-hidden="true" style="width:64px;height:64px;margin:0 auto 18px;border-radius:22px;display:grid;place-items:center;background:#eef2ff;color:#4f46e5;font-size:32px">⌁</div><h2 id="connection-lost-title" style="margin:0;font:800 25px/1.2 Arial,sans-serif">Нет интернета или связь глушат</h2><p style="margin:13px 0 0;color:#64748b;font:400 15px/1.5 Arial,sans-serif">Проверьте подключение. Если связь глушат, включите белые списки.</p><button type="button" id="connection-lost-retry" style="width:100%;min-height:52px;margin-top:22px;border:0;border-radius:16px;background:linear-gradient(135deg,#2563eb,#7c3aed);color:#fff;font:700 16px Arial,sans-serif">Проверить соединение</button><p id="connection-lost-status" role="status" aria-live="polite" style="min-height:20px;margin:12px 0 0;color:#dc2626;font:600 14px/1.4 Arial,sans-serif"></p></div>';
        document.body.appendChild(modal);

        const retry = modal.querySelector("#connection-lost-retry");
        const status = modal.querySelector("#connection-lost-status");
        retry.addEventListener("click", async function () {
            retry.disabled = true;
            retry.textContent = "Проверяем…";
            const controller = new AbortController();
            const timeoutId = window.setTimeout(function () { controller.abort(); }, 3000);
            try {
                const response = await window.fetch("/health?modal_retry=" + Date.now(), {
                    cache: "no-store",
                    credentials: "same-origin",
                    signal: controller.signal,
                });
                if (!response.ok) {
                    throw new Error("Unavailable");
                }
                connectionLost = false;
                modal.remove();
            } catch (_error) {
                status.textContent = "Соединение пока недоступно.";
                retry.disabled = false;
                retry.textContent = "Проверить соединение";
            } finally {
                window.clearTimeout(timeoutId);
            }
        });
        retry.focus();
    }

    window.addEventListener("load", function () {
        const currentUrl = new URL(window.location.href);
        if (currentUrl.searchParams.has("_shans_network")
            || currentUrl.searchParams.has("_shans_launch")) {
            currentUrl.searchParams.delete("_shans_network");
            currentUrl.searchParams.delete("_shans_launch");
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
        showConnectionModal();
    });

    window.addEventListener("online", function () {
        const retry = document.getElementById("connection-lost-retry");
        if (retry && !retry.disabled) {
            retry.click();
        }
    });

    document.addEventListener("submit", function (event) {
        if (!connectionLost || event.defaultPrevented) {
            return;
        }
        event.preventDefault();
        showConnectionModal();
    });

    if (connectionLost) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", showConnectionModal, { once: true });
        } else {
            showConnectionModal();
        }
    }
}());
