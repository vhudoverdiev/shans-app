document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-presentation-viewer]").forEach((viewer) => {
        const image = viewer.querySelector("[data-slide-image]");
        const dots = Array.from(viewer.querySelectorAll("[data-slide-dot]"));
        const current = viewer.querySelector("[data-slide-current]");
        const prev = viewer.querySelector("[data-slide-prev]");
        const next = viewer.querySelector("[data-slide-next]");
        const stage = viewer.querySelector(".python-presentation-stage");
        const fullscreenButton = viewer.querySelector("[data-presentation-fullscreen]");
        const closeButton = viewer.querySelector("[data-presentation-close]");
        const mobileCurrent = viewer.querySelector("[data-slide-current-mobile]");

        if (!image || !dots.length || !current || !prev || !next) {
            return;
        }

        let activeIndex = 0;
        let touchStartX = 0;
        let touchStartY = 0;

        function showSlide(index) {
            activeIndex = Math.max(0, Math.min(index, dots.length - 1));
            const activeDot = dots[activeIndex];
            image.src = activeDot.dataset.slideSrc;
            image.alt = "Слайд " + (activeIndex + 1) + " из " + dots.length;
            current.textContent = String(activeIndex + 1);
            if (mobileCurrent) {
                mobileCurrent.textContent = String(activeIndex + 1);
            }
            prev.disabled = activeIndex === 0;
            next.disabled = activeIndex === dots.length - 1;
            dots.forEach((dot, dotIndex) => {
                const isActive = dotIndex === activeIndex;
                dot.classList.toggle("python-presentation-dot-active", isActive);
                dot.setAttribute("aria-current", isActive ? "true" : "false");
            });
            activeDot.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
        }

        function setFullscreen(isFullscreen) {
            viewer.classList.toggle("python-presentation-fullscreen-active", isFullscreen);
            document.documentElement.classList.toggle("presentation-viewer-lock", isFullscreen);
            if (fullscreenButton) {
                fullscreenButton.setAttribute("aria-expanded", isFullscreen ? "true" : "false");
                fullscreenButton.textContent = isFullscreen ? "Закрыть" : "На весь экран";
            }
            if (isFullscreen && stage) {
                stage.focus({ preventScroll: true });
            }
        }

        prev.addEventListener("click", () => showSlide(activeIndex - 1));
        next.addEventListener("click", () => showSlide(activeIndex + 1));
        dots.forEach((dot, index) => dot.addEventListener("click", () => showSlide(index)));
        if (fullscreenButton) {
            fullscreenButton.setAttribute("aria-expanded", "false");
            fullscreenButton.addEventListener("click", () => setFullscreen(!viewer.classList.contains("python-presentation-fullscreen-active")));
        }
        if (closeButton) {
            closeButton.addEventListener("click", () => setFullscreen(false));
        }
        if (stage) {
            stage.addEventListener("keydown", (event) => {
                if (event.key === "ArrowLeft") {
                    event.preventDefault();
                    showSlide(activeIndex - 1);
                }
                if (event.key === "ArrowRight") {
                    event.preventDefault();
                    showSlide(activeIndex + 1);
                }
                if (event.key === "Escape") {
                    setFullscreen(false);
                }
            });
            stage.addEventListener("touchstart", (event) => {
                if (!event.changedTouches.length) return;
                touchStartX = event.changedTouches[0].clientX;
                touchStartY = event.changedTouches[0].clientY;
            }, { passive: true });
            stage.addEventListener("touchend", (event) => {
                if (!event.changedTouches.length) return;
                const deltaX = event.changedTouches[0].clientX - touchStartX;
                const deltaY = event.changedTouches[0].clientY - touchStartY;
                if (Math.abs(deltaX) < 44 || Math.abs(deltaX) < Math.abs(deltaY) * 1.35) return;
                showSlide(activeIndex + (deltaX < 0 ? 1 : -1));
            }, { passive: true });
        }
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && viewer.classList.contains("python-presentation-fullscreen-active")) {
                setFullscreen(false);
            }
        });
        showSlide(0);
    });
});
