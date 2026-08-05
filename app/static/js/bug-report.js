(function () {
    "use strict";

    const trigger = document.querySelector("[data-bug-report-trigger]");
    const sheet = document.getElementById("bug-report-sheet");
    const form = document.getElementById("bug-report-form");
    const status = document.getElementById("bug-report-status");
    const closeButtons = document.querySelectorAll("[data-bug-report-close]");
    const csrfMeta = document.querySelector("meta[name='csrf-token']");
    const csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";
    let requestInProgress = false;

    if (!trigger || !sheet || !form) {
        return;
    }

    function setStatus(message, isError) {
        if (!status) return;
        status.textContent = message || "";
        status.hidden = !message;
        status.classList.toggle("bug-report-status-error", Boolean(isError));
        status.classList.toggle("bug-report-status-success", Boolean(message && !isError));
    }

    function openSheet() {
        sheet.hidden = false;
        trigger.setAttribute("aria-expanded", "true");
        document.body.classList.add("bug-report-open");
        window.requestAnimationFrame(function () {
            sheet.classList.add("bug-report-sheet-open");
        });
        const nameInput = form.querySelector("[name='name']");
        if (nameInput) {
            nameInput.focus();
        }
    }

    function closeSheet() {
        sheet.classList.remove("bug-report-sheet-open");
        trigger.setAttribute("aria-expanded", "false");
        document.body.classList.remove("bug-report-open");
        window.setTimeout(function () {
            sheet.hidden = true;
            trigger.focus();
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

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        if (requestInProgress) return;

        const formData = new FormData(form);
        const payload = {
            name: String(formData.get("name") || "").trim(),
            description: String(formData.get("description") || "").trim(),
            page_url: window.location.href,
        };

        if (!payload.name || !payload.description) {
            setStatus("Заполните имя и описание ошибки.", true);
            return;
        }

        requestInProgress = true;
        setStatus("Отправляем...", false);
        try {
            const response = await window.fetch(sheet.dataset.submitUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify(payload),
            });
            const result = await response.json().catch(function () {
                return {};
            });
            if (!response.ok || !result.ok) {
                throw new Error(result.message || "Не удалось отправить сообщение.");
            }

            form.reset();
            setStatus(result.message || "Спасибо, сообщение отправлено.", false);
            window.setTimeout(closeSheet, 900);
        } catch (error) {
            setStatus(error.message || "Не удалось отправить сообщение.", true);
        } finally {
            requestInProgress = false;
        }
    });
})();
