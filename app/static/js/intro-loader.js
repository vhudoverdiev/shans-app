(function () {
    "use strict";

    const root = document.documentElement;
    const intro = document.getElementById("app-intro");

    function clearIntroFallbackTimer() {
        if (window.__shansIntroFallbackTimer) {
            window.clearTimeout(window.__shansIntroFallbackTimer);
            window.__shansIntroFallbackTimer = null;
        }
    }

    function removeIntroWithoutAnimation() {
        if (intro) {
            intro.remove();
        }
        root.classList.remove("app-intro-pending");
        root.classList.remove("app-intro-running");
        window.__shansShouldRunIntro = false;
        clearIntroFallbackTimer();
    }

    function waitForIntroLogoImage() {
        const logoImage = intro ? intro.querySelector(".app-intro-logo-mark") : null;
        if (!logoImage) {
            return Promise.resolve();
        }

        function decodeReadyImage() {
            if (!logoImage.decode) {
                return Promise.resolve();
            }
            return logoImage.decode().catch(function () {
                return undefined;
            });
        }

        if (logoImage.complete && logoImage.naturalWidth > 0) {
            return decodeReadyImage();
        }

        return new Promise(function (resolve) {
            let settled = false;
            let timeoutId = null;

            function finish() {
                if (settled) {
                    return;
                }
                settled = true;
                if (timeoutId) {
                    window.clearTimeout(timeoutId);
                }
                logoImage.removeEventListener("load", finish);
                logoImage.removeEventListener("error", finish);
                decodeReadyImage().then(resolve);
            }

            timeoutId = window.setTimeout(finish, 700);
            logoImage.addEventListener("load", finish);
            logoImage.addEventListener("error", finish);
        });
    }

    if (!root.classList.contains("app-intro-pending") || !window.__shansShouldRunIntro) {
        if (intro) {
            intro.remove();
        }
        window.__shansShouldRunIntro = false;
        clearIntroFallbackTimer();
        return;
    }

    if (!intro) {
        root.classList.remove("app-intro-pending");
        clearIntroFallbackTimer();
        return;
    }

    clearIntroFallbackTimer();

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const visibleDuration = reducedMotion ? 160 : 1550;
    const exitDuration = reducedMotion ? 20 : 430;

    waitForIntroLogoImage().then(function () {
        if (!window.__shansShouldRunIntro) {
            removeIntroWithoutAnimation();
            return;
        }

        intro.hidden = false;

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
    });
}());
