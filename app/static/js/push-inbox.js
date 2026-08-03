(function () {
    "use strict";

    const triggers = Array.from(document.querySelectorAll("[data-push-inbox-trigger]"));
    const floatingTriggers = triggers.filter(function (trigger) {
        return trigger.hasAttribute("data-push-inbox-floating");
    });
    const countBadges = Array.from(document.querySelectorAll("[data-push-inbox-count]"));
    const sheet = document.getElementById("mobile-push-inbox-sheet");
    const list = document.getElementById("mobile-push-inbox-list");
    const closeButtons = document.querySelectorAll("[data-push-inbox-close]");
    const csrfMeta = document.querySelector("meta[name='csrf-token']");
    const csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";
    const syncChannelName = "shans-push-inbox-sync";
    const syncStorageKey = "shans-push-inbox-state";
    const apiTrigger = triggers.find(function (trigger) {
        return trigger.dataset.inboxUrl && trigger.dataset.readUrl;
    });
    let notifications = [];
    let requestInProgress = false;
    let markReadInProgress = false;
    let broadcastChannel = null;

    if (!triggers.length || !apiTrigger || !sheet || !list) {
        return;
    }

    if ("BroadcastChannel" in window) {
        broadcastChannel = new BroadcastChannel(syncChannelName);
        broadcastChannel.addEventListener("message", function (event) {
            if (event.data && event.data.type === "unread-count") {
                setUnreadCount(event.data.unreadCount, false);
            }
        });
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

    function broadcastUnreadCount(unreadCount) {
        const payload = {
            type: "unread-count",
            unreadCount: unreadCount,
            updatedAt: Date.now(),
        };
        if (broadcastChannel) {
            broadcastChannel.postMessage(payload);
        }
        try {
            window.localStorage.setItem(syncStorageKey, JSON.stringify(payload));
        } catch (_error) {
            // Storage sync is best-effort; BroadcastChannel or polling will cover modern browsers.
        }
    }

    function setUnreadCount(value, shouldBroadcast) {
        const unreadCount = Math.max(0, Number.parseInt(value, 10) || 0);
        countBadges.forEach(function (badge) {
            badge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
            badge.hidden = unreadCount === 0;
        });
        triggers.forEach(function (trigger) {
            trigger.dataset.unreadCount = String(unreadCount);
            trigger.classList.toggle("push-inbox-has-unread", unreadCount > 0);
            if (trigger.hasAttribute("data-push-inbox-floating")) {
                trigger.hidden = unreadCount === 0;
            }
            trigger.setAttribute(
                "aria-label",
                unreadCount > 0
                    ? `Открыть новые уведомления: ${unreadCount}`
                    : "Открыть уведомления за последние 3 дня"
            );
        });
        if (shouldBroadcast) {
            broadcastUnreadCount(unreadCount);
        }
        if (unreadCount === 0 && notifications.some(function (notification) {
            return notification.unread || !notification.readAt;
        })) {
            notifications = notifications.map(function (notification) {
                return Object.assign({}, notification, {
                    unread: false,
                    readAt: notification.readAt || new Date().toISOString(),
                });
            });
            renderNotifications();
        }
    }

    function createEmptyState() {
        const emptyState = document.createElement("div");
        emptyState.className = "mobile-push-inbox-empty";
        emptyState.textContent = "За последние 3 дня уведомлений нет.";
        return emptyState;
    }

    function createNotificationCard(notification) {
        const card = document.createElement("article");
        card.className = "mobile-push-inbox-item";
        if (notification.unread || !notification.readAt) {
            card.classList.add("mobile-push-inbox-item-unread");
        }

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
        if (!notifications.length) {
            list.appendChild(createEmptyState());
            return;
        }
        notifications.forEach(function (notification) {
            list.appendChild(createNotificationCard(notification));
        });
    }

    async function loadNotifications(shouldBroadcast) {
        if (requestInProgress) return;
        requestInProgress = true;
        try {
            const response = await window.fetch(apiTrigger.dataset.inboxUrl, {
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
            setUnreadCount(payload.unreadCount, shouldBroadcast);
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
            const response = await window.fetch(apiTrigger.dataset.readUrl, {
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
            notifications = notifications.map(function (notification) {
                return Object.assign({}, notification, {
                    unread: false,
                    readAt: notification.readAt || new Date().toISOString(),
                });
            });
            renderNotifications();
            setUnreadCount(payload.unreadCount, true);
        } catch (_error) {
            // Keep the unread indicator so the request can be retried later.
        } finally {
            markReadInProgress = false;
        }
    }

    function openSheet(event) {
        const opener = event ? event.currentTarget : null;
        sheet.hidden = false;
        triggers.forEach(function (trigger) {
            trigger.setAttribute("aria-expanded", "true");
        });
        document.body.classList.add("mobile-push-inbox-open");
        window.requestAnimationFrame(function () {
            sheet.classList.add("mobile-push-inbox-sheet-open");
        });
        const closeButton = sheet.querySelector(".mobile-push-inbox-close");
        if (closeButton) closeButton.focus();
        markNotificationsRead();
        if (opener) {
            sheet.dataset.returnFocus = opener.id || "";
        }
    }

    function closeSheet() {
        sheet.classList.remove("mobile-push-inbox-sheet-open");
        triggers.forEach(function (trigger) {
            trigger.setAttribute("aria-expanded", "false");
        });
        document.body.classList.remove("mobile-push-inbox-open");
        window.setTimeout(function () {
            sheet.hidden = true;
            const returnFocusId = sheet.dataset.returnFocus || "";
            const returnFocusTarget = returnFocusId ? document.getElementById(returnFocusId) : null;
            if (returnFocusTarget && !returnFocusTarget.hidden) {
                returnFocusTarget.focus();
            }
            sheet.dataset.returnFocus = "";
        }, 180);
    }

    triggers.forEach(function (trigger) {
        trigger.addEventListener("click", openSheet);
    });
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
            loadNotifications(true);
        }
    });
    window.addEventListener("focus", function () {
        loadNotifications(true);
    });
    window.addEventListener("storage", function (event) {
        if (event.key !== syncStorageKey || !event.newValue) return;
        try {
            const payload = JSON.parse(event.newValue);
            if (payload && payload.type === "unread-count") {
                setUnreadCount(payload.unreadCount, false);
            }
        } catch (_error) {
            // Ignore malformed storage events from older tabs.
        }
    });

    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.addEventListener("message", function (event) {
            if (event.data && event.data.type === "shans-push-received") {
                window.setTimeout(function () {
                    loadNotifications(true);
                }, 800);
            }
        });
    }

    window.setInterval(function () {
        if (document.visibilityState === "visible") {
            loadNotifications(true);
        }
    }, 60000);

    setUnreadCount(0, false);
    floatingTriggers.forEach(function (trigger) {
        trigger.hidden = true;
    });
    loadNotifications(true);
})();
