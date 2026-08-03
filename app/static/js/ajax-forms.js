(function () {
    "use strict";

    const FORM_SELECTOR = "form[data-ajax-submit]";
    let requestInProgress = false;

    function splitSelectors(value) {
        return String(value || "")
            .split(",")
            .map(function (item) { return item.trim(); })
            .filter(Boolean);
    }

    function showFlashStack(nextDocument) {
        const currentStack = document.querySelector(".flash-stack");
        const nextStack = nextDocument.querySelector(".flash-stack");

        if (currentStack) {
            currentStack.remove();
        }

        if (!nextStack) return;

        const main = document.querySelector("main.page-shell");
        if (!main) return;
        main.insertBefore(document.importNode(nextStack, true), main.firstChild);
    }

    function removeFloatingControls() {
        document.querySelectorAll(".custom-floating-panel").forEach(function (panel) {
            panel.remove();
        });
    }

    function replaceFragments(nextDocument, selectors) {
        let replaced = 0;
        removeFloatingControls();

        selectors.forEach(function (selector) {
            const currentItems = Array.from(document.querySelectorAll(selector));
            const nextItems = Array.from(nextDocument.querySelectorAll(selector));

            currentItems.forEach(function (currentItem, index) {
                const nextItem = nextItems[index];
                if (!nextItem) return;
                currentItem.replaceWith(document.importNode(nextItem, true));
                replaced += 1;
            });
        });

        return replaced;
    }

    function resetForm(form) {
        if (form.dataset.ajaxReset !== "true") return;
        form.reset();
    }

    function hasErrorFlash(nextDocument) {
        return Boolean(nextDocument.querySelector(
            ".flash-error, .flash-danger, .flash-warning"
        ));
    }

    function restoreButton(button, disabled) {
        if (!button) return;
        button.disabled = disabled;
    }

    async function submitForm(form, submitter) {
        const selectors = splitSelectors(form.dataset.ajaxUpdate);
        if (!selectors.length || requestInProgress) return false;

        requestInProgress = true;
        restoreButton(submitter, true);

        try {
            const formData = new FormData(form);
            const csrfMeta = document.querySelector("meta[name='csrf-token']");
            const csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";
            if (csrfToken && !formData.has("_csrf_token")) {
                formData.append("_csrf_token", csrfToken);
            }

            const response = await window.fetch(form.action || window.location.href, {
                method: (form.method || "POST").toUpperCase(),
                body: formData,
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "fetch",
                    "X-CSRFToken": csrfToken,
                },
            });

            const contentType = response.headers.get("content-type") || "";
            if (!contentType.includes("text/html")) {
                return false;
            }

            const html = await response.text();
            const nextDocument = new DOMParser().parseFromString(html, "text/html");
            showFlashStack(nextDocument);

            const replaced = replaceFragments(nextDocument, selectors);
            if (!replaced) {
                return false;
            }

            if (!hasErrorFlash(nextDocument)) {
                resetForm(form);
            }
            document.dispatchEvent(new CustomEvent("shans:ajax-updated", {
                detail: {
                    form: form,
                    selectors: selectors,
                    url: response.url,
                },
            }));
            return true;
        } catch (error) {
            return false;
        } finally {
            requestInProgress = false;
            restoreButton(submitter, false);
        }
    }

    document.addEventListener("submit", async function (event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;
        if (!form.matches(FORM_SELECTOR)) return;

        event.preventDefault();
        const handled = await submitForm(form, event.submitter);
        if (!handled) {
            form.removeAttribute("data-ajax-submit");
            form.submit();
        }
    });
}());
