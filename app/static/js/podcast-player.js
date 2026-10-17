(() => {
    "use strict";
    const player = document.querySelector("[data-podcast-player]");
    if (!player) return;
    const audio = player.querySelector("audio");
    const button = player.querySelector("[data-podcast-play]");
    const status = player.querySelector("[data-podcast-status]");
    if (!audio || !button || !status) return;

    const update = () => {
        const playing = !audio.paused && !audio.ended;
        button.textContent = playing ? "Пауза" : "Прослушать";
        button.setAttribute("aria-pressed", String(playing));
    };
    const showError = () => {
        status.textContent = "Не удалось воспроизвести аудио. Попробуйте ещё раз или скачайте подкаст.";
        update();
    };
    button.hidden = false;
    button.addEventListener("click", async () => {
        status.textContent = "";
        if (!audio.paused) {
            audio.pause();
            return;
        }
        try {
            await audio.play();
        } catch (error) {
            showError();
        }
    });
    audio.addEventListener("play", update);
    audio.addEventListener("playing", () => { status.textContent = ""; });
    audio.addEventListener("pause", update);
    audio.addEventListener("ended", update);
    audio.addEventListener("error", showError);
})();
