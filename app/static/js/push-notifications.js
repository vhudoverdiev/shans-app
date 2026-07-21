(function () {
    "use strict";

    const card = document.getElementById("push-notifications-card");
    if (!card) return;

    const toggleButton = document.getElementById("push-notifications-toggle");
    const testButton = document.getElementById("push-notifications-test");
    const statusText = document.getElementById("push-notifications-status");
    const csrfMeta = document.querySelector("meta[name='csrf-token']");
    const csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";
    let registration = null;
    let subscription = null;
    let publicKey = "";

    function isStandaloneApp() {
        return window.matchMedia("(display-mode: standalone)").matches
            || window.navigator.standalone === true;
    }

    function setStatus(message, state) {
        if (!statusText) return;
        statusText.textContent = message;
        statusText.dataset.state = state || "idle";
    }

    function setBusy(isBusy) {
        if (toggleButton) toggleButton.disabled = isBusy;
        if (testButton) testButton.disabled = isBusy;
    }

    function syncButtons() {
        const enabled = Boolean(subscription);
        if (toggleButton) {
            toggleButton.textContent = enabled ? "Отключить уведомления" : "Включить уведомления";
            toggleButton.classList.toggle("btn-danger", enabled);
            toggleButton.classList.toggle("btn-primary", !enabled);
        }
        if (testButton) {
            testButton.hidden = !enabled;
        }
    }

    function urlBase64ToUint8Array(value) {
        const padding = "=".repeat((4 - value.length % 4) % 4);
        const base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
        const rawData = window.atob(base64);
        return Uint8Array.from(rawData, function (character) {
            return character.charCodeAt(0);
        });
    }

    async function apiRequest(url, body) {
        const response = await window.fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify(body || {}),
        });
        const payload = await response.json().catch(function () { return {}; });
        if (!response.ok || payload.ok === false) {
            throw new Error(payload.message || "Не удалось выполнить действие.");
        }
        return payload;
    }

    async function initialize() {
        if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
            setStatus("Это устройство не поддерживает Web Push.", "error");
            if (toggleButton) toggleButton.disabled = true;
            return;
        }

        const configResponse = await window.fetch(card.dataset.configUrl, {
            credentials: "same-origin",
        });
        if (!configResponse.ok) {
            throw new Error("Не удалось загрузить настройки уведомлений.");
        }
        const config = await configResponse.json();
        publicKey = config.publicKey || "";
        registration = await navigator.serviceWorker.register(config.serviceWorkerUrl, { scope: "/" });
        await navigator.serviceWorker.ready;
        subscription = await registration.pushManager.getSubscription();
        syncButtons();

        if (subscription) {
            setStatus("Уведомления личного графика включены на этом устройстве.", "success");
        } else if (!isStandaloneApp()) {
            setStatus("Откройте сайт через значок «Шанс» на экране домой, чтобы включить уведомления.", "info");
        } else if (Notification.permission === "denied") {
            setStatus("Уведомления запрещены в настройках iPhone для приложения «Шанс».", "error");
        } else {
            setStatus("Уведомления выключены.", "idle");
        }
    }

    async function enableNotifications() {
        if (!isStandaloneApp()) {
            throw new Error("Сначала добавьте «Шанс» на экран домой и откройте приложение через его значок.");
        }
        const permission = await Notification.requestPermission();
        if (permission !== "granted") {
            throw new Error("Разрешение не выдано. Проверьте настройки уведомлений iPhone.");
        }
        if (!publicKey || !registration) {
            throw new Error("Настройки уведомлений ещё не загружены.");
        }

        const newSubscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(publicKey),
        });
        try {
            await apiRequest(card.dataset.subscribeUrl, {
                subscription: newSubscription.toJSON(),
                origin: window.location.origin,
            });
        } catch (error) {
            await newSubscription.unsubscribe();
            throw error;
        }
        subscription = newSubscription;
        setStatus("Уведомления личного графика включены на этом устройстве.", "success");
    }

    async function disableNotifications() {
        if (!subscription) return;
        await apiRequest(card.dataset.unsubscribeUrl, {
            endpoint: subscription.endpoint,
        });
        await subscription.unsubscribe();
        subscription = null;
        setStatus("Уведомления выключены.", "idle");
    }

    if (toggleButton) {
        toggleButton.addEventListener("click", async function () {
            setBusy(true);
            try {
                if (subscription) {
                    await disableNotifications();
                } else {
                    await enableNotifications();
                }
            } catch (error) {
                setStatus(error && error.message ? error.message : "Не удалось изменить настройки.", "error");
            } finally {
                syncButtons();
                setBusy(false);
            }
        });
    }

    if (testButton) {
        testButton.addEventListener("click", async function () {
            if (!subscription) return;
            setBusy(true);
            try {
                const result = await apiRequest(card.dataset.testUrl, {
                    endpoint: subscription.endpoint,
                });
                setStatus(result.message || "Тестовое уведомление отправлено.", "success");
            } catch (error) {
                setStatus(error && error.message ? error.message : "Не удалось отправить уведомление.", "error");
            } finally {
                setBusy(false);
            }
        });
    }

    initialize().catch(function (error) {
        setStatus(error && error.message ? error.message : "Не удалось настроить уведомления.", "error");
        if (toggleButton) toggleButton.disabled = true;
    });
})();
