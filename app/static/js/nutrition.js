(function () {
    "use strict";

    function normalize(value) {
        return String(value || "").trim().toLocaleLowerCase("ru");
    }

    function initializeCatalogSearch() {
        const search = document.getElementById("nutrition-catalog-search");
        const rows = Array.from(document.querySelectorAll("[data-food-search]"));
        const count = document.getElementById("nutrition-visible-count");
        const noResults = document.getElementById("nutrition-no-results");

        if (!search || rows.length === 0) return;

        function applyFilter() {
            const query = normalize(search.value);
            let visible = 0;

            rows.forEach(function (row) {
                const matches = !query || normalize(row.dataset.foodSearch).includes(query);
                row.hidden = !matches;
                if (matches) visible += 1;
            });

            if (count) count.textContent = String(visible);
            if (noResults) noResults.hidden = visible !== 0;
        }

        search.addEventListener("input", applyFilter);
        applyFilter();
    }

    function initializeFoodSelection() {
        const input = document.getElementById("food-query");
        const entryCard = document.getElementById("add-food-entry");
        if (!input || !entryCard) return;

        document.querySelectorAll("[data-select-food]").forEach(function (button) {
            button.addEventListener("click", function () {
                input.value = button.dataset.selectFood || "";
                if ("open" in entryCard) {
                    entryCard.open = true;
                }
                entryCard.scrollIntoView({ behavior: "smooth", block: "center" });
            });
        });
    }

    function initializeCustomFoodShortcut() {
        const customCard = document.getElementById("custom-food");
        const trigger = document.querySelector("[data-open-custom-food]");
        const firstInput = document.getElementById("custom-food-name");
        if (!customCard || !trigger) return;

        trigger.setAttribute("aria-expanded", "false");

        trigger.addEventListener("click", function () {
            const shouldShow = customCard.hidden;
            customCard.hidden = !shouldShow;
            trigger.setAttribute("aria-expanded", shouldShow ? "true" : "false");
            trigger.classList.toggle("nutrition-icon-button-active", shouldShow);

            if (shouldShow) {
                customCard.scrollIntoView({ behavior: "smooth", block: "start" });
                if (firstInput) {
                    window.setTimeout(function () {
                        firstInput.focus({ preventScroll: true });
                    }, 250);
                }
            }
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        initializeCatalogSearch();
        initializeFoodSelection();
        initializeCustomFoodShortcut();
    });
}());
