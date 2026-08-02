(function () {
    "use strict";

    const VOICE_PREFERENCES = {
        ru: [
            "microsoft svetlana online",
            "microsoft dmitry online",
            "google русский",
            "google russian",
            "yandex",
            "alena",
            "svetlana",
            "dmitry",
            "milena",
        ],
        en: [
            "microsoft aria online",
            "microsoft jenny online",
            "microsoft guy online",
            "google us english",
            "google uk english female",
            "google uk english male",
            "samantha",
            "ava",
            "allison",
            "daniel",
        ],
    };
    const speech = window.speechSynthesis;
    const controller = document.querySelector("[data-course-audio]");
    const dataNode = document.getElementById("course-audio-segments");

    if (!controller || !dataNode) {
        return;
    }

    const playButton = controller.querySelector("[data-course-audio-play]");
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
        if (playButton) playButton.disabled = true;
        pronounceButtons.forEach((button) => {
            button.disabled = true;
        });
        setStatus("Озвучка недоступна в этом браузере.");
        return;
    }

    function getVoices() {
        return speech.getVoices ? speech.getVoices() : [];
    }

    function normalizeVoiceName(value) {
        return String(value || "").toLowerCase();
    }

    function voiceScore(voice, lang) {
        const targetLang = String(lang || "ru-RU").toLowerCase();
        const targetPrefix = targetLang.slice(0, 2);
        const voiceLang = String(voice.lang || "").toLowerCase();
        const voiceName = normalizeVoiceName(`${voice.name} ${voice.voiceURI}`);
        let score = 0;

        if (voiceLang === targetLang) score += 80;
        if (voiceLang.startsWith(targetPrefix)) score += 45;
        if (voice.localService === false) score += 18;
        if (voice.default) score += 6;
        if (voiceName.includes("natural")) score += 20;
        if (voiceName.includes("online")) score += 16;
        if (voiceName.includes("neural")) score += 16;
        if (voiceName.includes("premium")) score += 10;

        (VOICE_PREFERENCES[targetPrefix] || []).forEach((keyword, index) => {
            if (voiceName.includes(keyword)) {
                score += 120 - index * 6;
            }
        });

        return score;
    }

    function pickVoice(lang) {
        const voices = getVoices();
        const prefix = String(lang).slice(0, 2).toLowerCase();
        return voices
            .filter((voice) => String(voice.lang || "").toLowerCase().startsWith(prefix))
            .sort((left, right) => voiceScore(right, lang) - voiceScore(left, lang))[0] || null;
    }

    function getProsody(lang) {
        if (String(lang || "").startsWith("en")) {
            return {
                rate: 0.86,
                pitch: 1.02,
                volume: 0.98,
                pauseAfter: 360,
            };
        }

        return {
            rate: 0.92,
            pitch: 1.04,
            volume: 1,
            pauseAfter: 460,
        };
    }

    function getSegmentPause(segment) {
        const text = String(segment.text || "");
        const prosody = getProsody(segment.lang);

        if (/^(День|Словарь|Предложения|Практика|Разбор кода)\b/i.test(text)) {
            return prosody.pauseAfter + 260;
        }
        if (/[!?…]$/.test(text)) {
            return prosody.pauseAfter + 180;
        }
        if (text.length < 22) {
            return Math.max(220, prosody.pauseAfter - 120);
        }

        return prosody.pauseAfter;
    }

    function syncReadyState() {
        if (playButton) {
            playButton.disabled = segments.length === 0;
        }
        if (segments.length === 0) {
            setStatus("Для этого урока нет текста озвучки.");
        } else {
            setStatus("");
        }
    }

    function setPlaying(isPlaying) {
        controller.classList.toggle("course-audio-playing", isPlaying);
        if (playButton) {
            playButton.disabled = segments.length === 0;
            playButton.setAttribute("aria-pressed", isPlaying ? "true" : "false");
        }
    }

    function setPronounceButton(button, isPlaying) {
        if (!button) return;
        button.classList.toggle("course-pronounce-button-playing", isPlaying);
        button.setAttribute("aria-pressed", isPlaying ? "true" : "false");
    }

    function resetPronounceButtons() {
        pronounceButtons.forEach((button) => {
            setPronounceButton(button, false);
        });
    }

    function buildUtterance(segment) {
        const utterance = new SpeechSynthesisUtterance(segment.text);
        const prosody = getProsody(segment.lang);
        utterance.lang = segment.lang;
        utterance.rate = prosody.rate;
        utterance.pitch = prosody.pitch;
        utterance.volume = prosody.volume;
        const voice = pickVoice(segment.lang);
        if (voice) {
            utterance.voice = voice;
        }
        return utterance;
    }

    function stopSpeech(message) {
        speech.cancel();
        setPlaying(false);
        resetPronounceButtons();
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
            window.setTimeout(function () {
                speakNext(index + 1);
            }, getSegmentPause(segment));
        };
        utterance.onerror = function () {
            setPlaying(false);
            setStatus("Не удалось воспроизвести озвучку. Попробуйте ещё раз.");
        };

        speech.speak(utterance);
    }

    function playSpeech() {
        if (!segments.length) {
            setStatus("Для этого урока нет текста озвучки.");
            return;
        }
        stopSpeech();
        setPlaying(true);
        setStatus("Озвучиваю урок...");
        speakNext(0);
    }

    function playPronunciation(button) {
        const text = String(button.dataset.pronounceText || "").trim();
        const lang = button.dataset.pronounceLang || "en-US";
        if (!text) return;

        if (button.getAttribute("aria-pressed") === "true") {
            stopSpeech("Произношение остановлено.");
            return;
        }

        stopSpeech();
        setPronounceButton(button, true);
        setStatus(`Произношу: ${text}`);

        const utterance = buildUtterance({ lang, text });
        utterance.onend = function () {
            setPronounceButton(button, false);
            setStatus("");
        };
        utterance.onerror = function () {
            setPronounceButton(button, false);
            setStatus("Не удалось воспроизвести произношение. Попробуйте ещё раз.");
        };
        speech.speak(utterance);
    }

    if (playButton) {
        playButton.addEventListener("click", function () {
            if (controller.classList.contains("course-audio-playing")) {
                stopSpeech("Озвучка остановлена.");
                return;
            }
            playSpeech();
        });
    }

    pronounceButtons.forEach((button) => {
        button.setAttribute("aria-pressed", "false");
        button.addEventListener("click", function () {
            playPronunciation(button);
        });
    });

    if (speech.onvoiceschanged !== undefined) {
        speech.onvoiceschanged = syncReadyState;
    }

    window.addEventListener("pagehide", function () {
        speech.cancel();
    });

    syncReadyState();
})();
