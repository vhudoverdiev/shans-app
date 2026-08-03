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
        if (search.dataset.nutritionSearchReady === "1") return;
        search.dataset.nutritionSearchReady = "1";

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
            if (button.dataset.nutritionSelectReady === "1") return;
            button.dataset.nutritionSelectReady = "1";
            button.addEventListener("click", function () {
                input.value = button.dataset.selectFood || "";
                if ("open" in entryCard) {
                    entryCard.open = true;
                }
                entryCard.scrollIntoView({ behavior: "smooth", block: "center" });
            });
        });
    }

    function initializeNutritionPage() {
        initializeCatalogSearch();
        initializeFoodSelection();
    }

    document.addEventListener("DOMContentLoaded", function () {
        initializeNutritionPage();
    });

    document.addEventListener("shans:ajax-updated", function () {
        initializeNutritionPage();
    });
}());
