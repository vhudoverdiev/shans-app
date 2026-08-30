(function () {
    "use strict";

    const toggle = document.querySelector("[data-interview-test-toggle]");
    const test = document.getElementById("interview-test");
    if (!toggle || !test) return;

    toggle.addEventListener("click", function () {
        test.hidden = false;
        toggle.setAttribute("aria-expanded", "true");
        test.scrollIntoView({ behavior: "smooth", block: "start" });
    });
})();
