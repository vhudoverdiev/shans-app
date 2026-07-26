(function () {
    "use strict";

    const root = document.documentElement;
    const intro = document.getElementById("app-intro");

    if (!root.classList.contains("app-intro-pending") || !window.__shansShouldRunIntro) {
        if (intro) {
            intro.remove();
        }
        window.__shansShouldRunIntro = false;
        return;
    }

    if (!intro) {
        root.classList.remove("app-intro-pending");
        return;
    }

    if (window.__shansIntroFallbackTimer) {
        window.clearTimeout(window.__shansIntroFallbackTimer);
        window.__shansIntroFallbackTimer = null;
    }

    intro.hidden = false;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const visibleDuration = reducedMotion ? 160 : 1550;
    const exitDuration = reducedMotion ? 20 : 430;

    window.requestAnimationFrame(function () {
        root.classList.remove("app-intro-pending");
        root.classList.add("app-intro-running");

        window.setTimeout(function () {
            intro.classList.add("app-intro-leaving");

            window.setTimeout(function () {
                intro.remove();
                root.classList.remove("app-intro-running");
                window.__shansShouldRunIntro = false;
            }, exitDuration);
        }, visibleDuration);
    });
}());
