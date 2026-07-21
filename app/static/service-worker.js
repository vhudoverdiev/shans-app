const DEFAULT_NOTIFICATION_URL = "/planner.schedule?calendar=personal&view=day";
const DEFAULT_ICON_URL = "/static/apple-touch-icon.png";

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
