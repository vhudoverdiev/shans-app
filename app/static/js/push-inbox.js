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
    const clearAllButton = document.querySelector("[data-push-inbox-clear-all]");
    const csrfMeta = document.querySelector("meta[name='csrf-token']");
    const csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";
    const syncChannelName = "shans-push-inbox-sync";
    const syncStorageKey = "shans-push-inbox-state";
    const logoUrl = sheet ? String(sheet.dataset.logoUrl || "").trim() : "";
    const apiTrigger = triggers.find(function (trigger) {
        return trigger.dataset.inboxUrl && trigger.dataset.readUrl
            && trigger.dataset.deleteUrl && trigger.dataset.clearUrl;
    });
    let notifications = [];
    let requestInProgress = false;
    let markReadInProgress = false;
    let deleteInProgress = false;
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

    function normalizeNotificationTitle(value) {
        const title = String(value || "Шанс").trim();
        return title === "Шанс - скрипт" || title === "Шанс-скрипт"
            ? "Вк аккануты"
            : title;
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
                trigger.hidden = unreadCount === 0
                    && trigger.dataset.pushInboxFloatingPersistent !== "true";
            }
            trigger.setAttribute(
                "aria-label",
                unreadCount > 0
                    ? `Открыть новые уведомления: ${unreadCount}`
                    : "Открыть уведомления за последние 3 дня"
            );
        });
        const hasVisibleFloatingTrigger = floatingTriggers.some(function (trigger) {
            return !trigger.hidden;
        });
        document.documentElement.classList.toggle(
            "shans-push-inbox-floating-active",
            hasVisibleFloatingTrigger
        );
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
        if (logoUrl) {
            const logo = document.createElement("img");
            logo.src = logoUrl;
            logo.alt = "";
            icon.appendChild(logo);
        } else {
            icon.textContent = "Ш";
        }

        const content = document.createElement("div");
        content.className = "mobile-push-inbox-item-content";

        const titleRow = document.createElement("div");
        titleRow.className = "mobile-push-inbox-item-title-row";

        const title = document.createElement("h3");
        title.textContent = normalizeNotificationTitle(notification.title);
        titleRow.appendChild(title);

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "mobile-push-inbox-delete";
        deleteButton.dataset.notificationId = String(notification.id || "");
        deleteButton.setAttribute("aria-label", "Удалить уведомление");
        deleteButton.title = "Удалить";
        deleteButton.textContent = "×";
        titleRow.appendChild(deleteButton);
        content.appendChild(titleRow);

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

        content.appendChild(footer);
        card.appendChild(icon);
        card.appendChild(content);
        return card;
    }

    function renderNotifications() {
        list.replaceChildren();
        if (clearAllButton) {
            clearAllButton.hidden = notifications.length === 0;
        }
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

    async function deleteNotification(notificationId) {
        const id = Number.parseInt(notificationId, 10);
        if (!id || deleteInProgress) return;
        deleteInProgress = true;
        try {
            const response = await window.fetch(apiTrigger.dataset.deleteUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({ id: id }),
            });
            if (!response.ok) return;
            const payload = await response.json();
            notifications = notifications.filter(function (notification) {
                return Number.parseInt(notification.id, 10) !== id;
            });
            renderNotifications();
            setUnreadCount(payload.unreadCount, true);
        } catch (_error) {
            // The list will be refreshed by the next polling cycle.
        } finally {
            deleteInProgress = false;
        }
    }

    async function clearNotifications() {
        if (!notifications.length || deleteInProgress) return;
        deleteInProgress = true;
        try {
            const response = await window.fetch(apiTrigger.dataset.clearUrl, {
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
            notifications = [];
            renderNotifications();
            setUnreadCount(payload.unreadCount, true);
        } catch (_error) {
            // The list will be refreshed by the next polling cycle.
        } finally {
            deleteInProgress = false;
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
    list.addEventListener("click", function (event) {
        const target = event.target instanceof Element
            ? event.target
            : event.target.parentElement;
        const deleteButton = target ? target.closest("[data-notification-id]") : null;
        if (!deleteButton) return;
        event.preventDefault();
        event.stopPropagation();
        deleteNotification(deleteButton.dataset.notificationId);
    });
    if (clearAllButton) {
        clearAllButton.addEventListener("click", function () {
            clearNotifications();
        });
    }
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
        trigger.hidden = trigger.dataset.pushInboxFloatingPersistent !== "true";
    });
    document.documentElement.classList.toggle(
        "shans-push-inbox-floating-active",
        floatingTriggers.some(function (trigger) {
            return !trigger.hidden;
        })
    );
    loadNotifications(true);
})();
