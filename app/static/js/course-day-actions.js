(function () {
    "use strict";

    function createTestLink(testUrl) {
        const link = document.createElement("a");
        link.className = "btn btn-primary lesson-next-button";
        link.href = testUrl;
        link.textContent = "Пройти тест";
        return link;
    }

    function getCsrfToken() {
        const meta = document.querySelector("meta[name='csrf-token']");
        return meta ? meta.getAttribute("content") : "";
    }

    document.querySelectorAll("[data-course-day-reset-form]").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            event.preventDefault();

            const button = form.querySelector("button[type='submit']");
            const testUrl = form.dataset.testUrl;
            const csrfToken = getCsrfToken();
            const formData = new FormData(form);
            if (csrfToken && !formData.has("_csrf_token")) {
                formData.append("_csrf_token", csrfToken);
            }

            if (button) {
                button.disabled = true;
            }

            window.fetch(form.action, {
                method: "POST",
                body: formData,
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
            }).then(function (response) {
                if (!response.ok) {
                    throw new Error("Reset request failed");
                }
                return response.json();
            }).then(function (payload) {
                form.replaceWith(createTestLink(payload.test_url || testUrl));
            }).catch(function () {
                if (button) {
                    button.disabled = false;
                }
            });
        });
    });
}());
