(function () {
    "use strict";

    const shell = document.querySelector("[data-floating-video-player]");
    const anchor = document.querySelector("[data-video-anchor]");
    if (!shell || !anchor) {
        return;
    }

    const video = shell.querySelector("video");
    const poster = shell.querySelector("[data-video-poster]");
    const playButton = shell.querySelector("[data-video-play]");
    const expandButton = shell.querySelector("[data-video-expand]");
    const closeButton = shell.querySelector("[data-video-close]");
    let started = video.currentTime > 0;
    let anchorVisible = true;
    let floatingDismissed = false;

    function updateMediaMetadata() {
        if (!("mediaSession" in navigator) || typeof MediaMetadata === "undefined") {
            return;
        }
        const title = poster ? String(poster.querySelector("strong")?.textContent || "").trim() : "";
        navigator.mediaSession.metadata = new MediaMetadata({
            title: title || document.title.split("|")[0].trim(),
            artist: "Шанс",
            album: "Обучение",
            artwork: [
                { src: "/static/logo.png", sizes: "384x384", type: "image/png" },
                { src: "/static/pwa-icon-512-shans-v2.png", sizes: "512x512", type: "image/png" },
            ],
        });
    }

    function updateFloatingState() {
        shell.classList.toggle(
            "python-video-shell-floating",
            started && !anchorVisible && !floatingDismissed,
        );
    }

    function hidePoster() {
        poster.hidden = true;
    }

    playButton.addEventListener("click", function () {
        floatingDismissed = false;
        video.play().catch(function () {
            poster.hidden = false;
        });
    });

    video.addEventListener("play", function () {
        updateMediaMetadata();
        started = true;
        floatingDismissed = false;
        hidePoster();
        updateFloatingState();
    });

    video.addEventListener("ended", function () {
        started = false;
        shell.classList.remove("python-video-shell-floating");
        poster.hidden = false;
    });

    expandButton.addEventListener("click", function () {
        shell.classList.remove("python-video-shell-floating");
        anchor.scrollIntoView({ behavior: "smooth", block: "center" });
    });

    closeButton.addEventListener("click", function () {
        video.pause();
        floatingDismissed = true;
        shell.classList.remove("python-video-shell-floating");
    });

    if ("IntersectionObserver" in window) {
        const observer = new IntersectionObserver(function (entries) {
            anchorVisible = entries[0].isIntersecting;
            updateFloatingState();
        }, { threshold: 0.15 });
        observer.observe(anchor);
    }
}());
