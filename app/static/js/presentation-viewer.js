document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-presentation-viewer]").forEach((viewer) => {
        const toggle = viewer.querySelector("[data-presentation-toggle]");
        const frame = viewer.querySelector("[data-presentation-frame]");

        if (!toggle || !frame) {
            return;
        }

        toggle.addEventListener("click", () => {
            const willOpen = frame.hidden;
            frame.hidden = !willOpen;
            toggle.setAttribute("aria-expanded", String(willOpen));
            const closedLabel = toggle.dataset.closedLabel || toggle.textContent;
            toggle.dataset.closedLabel = closedLabel;
            toggle.textContent = willOpen ? "Скрыть" : closedLabel;

            if (willOpen) {
                frame.scrollIntoView({ behavior: "smooth", block: "start" });
            }
        });
    });
});
