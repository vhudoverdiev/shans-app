(function () {
    "use strict";

    const mobileQuery = window.matchMedia("(max-width: 900px) and (pointer: coarse)");
    const trigger = document.getElementById("mobile-push-inbox-trigger");
    const countBadge = document.getElementById("mobile-push-inbox-count");
    const sheet = document.getElementById("mobile-push-inbox-sheet");
    const list = document.getElementById("mobile-push-inbox-list");
    const closeButtons = document.querySelectorAll("[data-push-inbox-close]");
    const csrfMeta = document.querySelector("meta[name='csrf-token']");
    const csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";
    let notifications = [];
    let requestInProgress = false;
    let markReadInProgress = false;

    if (!mobileQuery.matches || !trigger || !countBadge || !sheet || !list) {
        return;
    }

    function formatCreatedAt(value) {
        const rawValue = String(value || "").trim();
        if (!rawValue) return "";
        const normalizedValue = rawValue.includes("T")
            ? rawValue
            : rawValue.replace(" ", "T") + "Z";
        const date = new Date(normalizedValue);
        if (Number.isNaN(date.getTime())) return "";
        return new Intl.DateTimeFormat("ru-RU", {
            day: "numeric",
            month: "long",
            hour: "2-digit",
            minute: "2-digit",
        }).format(date);
    }

    function safeNavigatePath(value) {
        const path = String(value || "").trim();
        return path.startsWith("/") && !path.startsWith("//") ? path : "";
    }

    function setUnreadCount(value) {
        const unreadCount = Math.max(0, Number.parseInt(value, 10) || 0);
        trigger.hidden = unreadCount === 0;
        countBadge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
        trigger.setAttribute(
            "aria-label",
            unreadCount === 1
                ? "Открыть одно непрочитанное уведомление"
                : `Открыть непрочитанные уведомления: ${unreadCount}`
        );
    }

    function createNotificationCard(notification) {
        const card = document.createElement("article");
        card.className = "mobile-push-inbox-item";

        const icon = document.createElement("span");
        icon.className = "mobile-push-inbox-item-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = "Ш";

        const content = document.createElement("div");
        content.className = "mobile-push-inbox-item-content";

        const title = document.createElement("h3");
        title.textContent = String(notification.title || "Шанс");
        content.appendChild(title);

        const body = document.createElement("p");
        body.textContent = String(notification.body || "");
        content.appendChild(body);

        const footer = document.createElement("div");
        footer.className = "mobile-push-inbox-item-footer";

        const createdAt = formatCreatedAt(notification.createdAt);
        if (createdAt) {
            const time = document.createElement("time");
            time.textContent = createdAt;
            footer.appendChild(time);
        }

        const navigatePath = safeNavigatePath(notification.navigatePath);
        if (navigatePath) {
            const link = document.createElement("a");
            link.href = navigatePath;
            link.textContent = "Открыть";
            footer.appendChild(link);
        }

        content.appendChild(footer);
        card.appendChild(icon);
        card.appendChild(content);
        return card;
    }

    function renderNotifications() {
        list.replaceChildren();
        notifications.forEach(function (notification) {
            list.appendChild(createNotificationCard(notification));
        });
    }

    async function loadNotifications() {
        if (requestInProgress) return;
        requestInProgress = true;
        try {
            const response = await window.fetch(trigger.dataset.inboxUrl, {
                credentials: "same-origin",
                cache: "no-store",
                headers: { Accept: "application/json" },
            });
            if (!response.ok) return;
            const payload = await response.json();
            notifications = Array.isArray(payload.notifications)
                ? payload.notifications
                : [];
            renderNotifications();
            setUnreadCount(payload.unreadCount);
        } catch (_error) {
            // The inbox stays unobtrusive when the device is offline.
        } finally {
            requestInProgress = false;
        }
    }

    async function markNotificationsRead() {
        if (markReadInProgress || notifications.length === 0) return;
        markReadInProgress = true;
        try {
            const response = await window.fetch(trigger.dataset.readUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: "{}",
            });
            if (!response.ok) return;
            const payload = await response.json();
            setUnreadCount(payload.unreadCount);
        } catch (_error) {
            // Keep the unread indicator so the request can be retried later.
        } finally {
            markReadInProgress = false;
        }
    }

    function openSheet() {
        if (notifications.length === 0) return;
        sheet.hidden = false;
        trigger.setAttribute("aria-expanded", "true");
        document.body.classList.add("mobile-push-inbox-open");
        window.requestAnimationFrame(function () {
            sheet.classList.add("mobile-push-inbox-sheet-open");
        });
        const closeButton = sheet.querySelector(".mobile-push-inbox-close");
        if (closeButton) closeButton.focus();
        markNotificationsRead();
    }

    function closeSheet() {
        sheet.classList.remove("mobile-push-inbox-sheet-open");
        trigger.setAttribute("aria-expanded", "false");
        document.body.classList.remove("mobile-push-inbox-open");
        window.setTimeout(function () {
            sheet.hidden = true;
        }, 180);
    }

    trigger.addEventListener("click", openSheet);
    closeButtons.forEach(function (button) {
        button.addEventListener("click", closeSheet);
    });
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !sheet.hidden) {
            closeSheet();
        }
    });
    document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "visible") {
            loadNotifications();
        }
    });
    window.addEventListener("focus", loadNotifications);

    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.addEventListener("message", function (event) {
            if (event.data && event.data.type === "shans-push-received") {
                window.setTimeout(loadNotifications, 800);
            }
        });
    }

    window.setInterval(function () {
        if (document.visibilityState === "visible") {
            loadNotifications();
        }
    }, 60000);

    loadNotifications();
})();
