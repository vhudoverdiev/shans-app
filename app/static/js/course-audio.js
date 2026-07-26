(function () {
    "use strict";

    const STORAGE_KEY = "shans.courseAudio.enabled";
    const speech = window.speechSynthesis;
    const controller = document.querySelector("[data-course-audio]");
    const dataNode = document.getElementById("course-audio-segments");

    if (!controller || !dataNode) {
        return;
    }

    const toggleButton = controller.querySelector("[data-course-audio-toggle]");
    const playButton = controller.querySelector("[data-course-audio-play]");
    const stopButton = controller.querySelector("[data-course-audio-stop]");
    const statusNode = controller.querySelector("[data-course-audio-status]");
    const pronounceButtons = Array.from(document.querySelectorAll("[data-course-pronounce]"));

    let segments = [];
    try {
        segments = JSON.parse(dataNode.textContent || "[]")
            .filter((segment) => segment && segment.text)
            .map((segment) => ({
                lang: segment.lang || "ru-RU",
                text: String(segment.text).trim(),
            }))
            .filter((segment) => segment.text.length > 0);
    } catch (_error) {
        segments = [];
    }

    function setStatus(message) {
        if (statusNode) {
            statusNode.textContent = message || "";
        }
    }

    function supportsSpeech() {
        return Boolean(speech && window.SpeechSynthesisUtterance);
    }

    if (!supportsSpeech()) {
        controller.classList.add("course-audio-unavailable");
        if (toggleButton) toggleButton.disabled = true;
        if (playButton) playButton.disabled = true;
        if (stopButton) stopButton.hidden = true;
        setStatus("Озвучка недоступна в этом браузере.");
        return;
    }

    function isEnabled() {
        return window.localStorage.getItem(STORAGE_KEY) === "1";
    }

    function getVoices() {
        return speech.getVoices ? speech.getVoices() : [];
    }

    function pickVoice(lang) {
        const voices = getVoices();
        const exact = voices.find((voice) => voice.lang === lang);
        if (exact) return exact;
        const prefix = String(lang).slice(0, 2).toLowerCase();
        return voices.find((voice) => String(voice.lang).toLowerCase().startsWith(prefix)) || null;
    }

    function syncEnabledState() {
        const enabled = isEnabled();
        controller.classList.toggle("course-audio-enabled", enabled);
        if (toggleButton) {
            toggleButton.setAttribute("aria-pressed", enabled ? "true" : "false");
            toggleButton.textContent = enabled ? "Озвучка включена" : "Включить озвучку";
        }
        if (playButton) {
            playButton.disabled = !enabled || segments.length === 0;
        }
        if (!enabled) {
            setStatus("Озвучка выключена.");
        } else if (segments.length === 0) {
            setStatus("Для этого урока нет текста озвучки.");
        } else {
            setStatus("Готово к воспроизведению.");
        }
    }

    function setPlaying(isPlaying) {
        controller.classList.toggle("course-audio-playing", isPlaying);
        if (playButton) {
            playButton.disabled = isPlaying || !isEnabled() || segments.length === 0;
            playButton.textContent = isPlaying ? "Озвучивается..." : "Озвучить урок";
        }
        if (stopButton) {
            stopButton.hidden = !isPlaying;
        }
    }

    function buildUtterance(segment) {
        const utterance = new SpeechSynthesisUtterance(segment.text);
        utterance.lang = segment.lang;
        utterance.rate = segment.lang.startsWith("en") ? 0.84 : 0.95;
        utterance.pitch = 1;
        const voice = pickVoice(segment.lang);
        if (voice) {
            utterance.voice = voice;
        }
        return utterance;
    }

    function stopSpeech(message) {
        speech.cancel();
        setPlaying(false);
        if (message) {
            setStatus(message);
        }
    }

    function speakNext(index) {
        if (index >= segments.length) {
            setPlaying(false);
            setStatus("Урок озвучен полностью.");
            return;
        }

        const segment = segments[index];
        const utterance = buildUtterance(segment);

        utterance.onend = function () {
            speakNext(index + 1);
        };
        utterance.onerror = function () {
            setPlaying(false);
            setStatus("Не удалось воспроизвести озвучку. Попробуйте ещё раз.");
        };

        speech.speak(utterance);
    }

    function speakSingle(text, lang) {
        const cleanText = String(text || "").trim();
        if (!cleanText) {
            return;
        }
        if (!isEnabled()) {
            window.localStorage.setItem(STORAGE_KEY, "1");
            syncEnabledState();
        }
        stopSpeech();
        setStatus(lang && lang.startsWith("en") ? "Произношу по-английски..." : "Озвучиваю...");
        const utterance = buildUtterance({
            lang: lang || "en-US",
            text: cleanText,
        });
        utterance.onend = function () {
            setStatus("Готово к воспроизведению.");
        };
        utterance.onerror = function () {
            setStatus("Не удалось воспроизвести произношение. Попробуйте ещё раз.");
        };
        speech.speak(utterance);
    }

    function playSpeech() {
        if (!isEnabled()) {
            window.localStorage.setItem(STORAGE_KEY, "1");
            syncEnabledState();
        }
        if (!segments.length) {
            setStatus("Для этого урока нет текста озвучки.");
            return;
        }
        stopSpeech();
        setPlaying(true);
        setStatus("Озвучиваю урок...");
        speakNext(0);
    }

    if (toggleButton) {
        toggleButton.addEventListener("click", function () {
            const enabled = !isEnabled();
            window.localStorage.setItem(STORAGE_KEY, enabled ? "1" : "0");
            if (!enabled) {
                stopSpeech("Озвучка выключена.");
            }
            syncEnabledState();
        });
    }

    if (playButton) {
        playButton.addEventListener("click", playSpeech);
    }

    if (stopButton) {
        stopButton.addEventListener("click", function () {
            stopSpeech("Озвучка остановлена.");
        });
    }

    pronounceButtons.forEach((button) => {
        button.addEventListener("click", function () {
            speakSingle(
                button.getAttribute("data-course-pronounce"),
                button.getAttribute("data-course-pronounce-lang") || "en-US",
            );
        });
    });

    if (speech.onvoiceschanged !== undefined) {
        speech.onvoiceschanged = syncEnabledState;
    }

    window.addEventListener("pagehide", function () {
        speech.cancel();
    });

    syncEnabledState();
})();
