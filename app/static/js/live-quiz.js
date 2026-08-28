(function () {
    "use strict";

    const form = document.querySelector("[data-live-quiz]");
    if (!form || !window.fetch) return;

    const csrfInput = form.querySelector('input[name="_csrf_token"]');
    const submitButton = form.querySelector(".quiz-submit");
    submitButton.type = "button";
    submitButton.disabled = true;
    submitButton.textContent = "Ответьте на все вопросы";
    form.querySelectorAll("[data-live-question] input").forEach(function (input) {
        input.disabled = true;
    });
    form.querySelectorAll("[data-answer-question]").forEach(function (button) {
        button.disabled = true;
    });

    function lockQuestion(fieldset) {
        fieldset.querySelectorAll("input").forEach(function (input) {
            if ((input.type === "text" && input.value) || input.checked) {
                const mirror = document.createElement("input");
                mirror.type = "hidden";
                mirror.name = input.name;
                mirror.value = input.value;
                fieldset.appendChild(mirror);
            }
            input.disabled = true;
        });
        const answerButton = fieldset.querySelector("[data-answer-question]");
        if (answerButton) answerButton.disabled = true;
        fieldset.dataset.answered = "true";
    }

    function showFeedback(fieldset, result) {
        const feedback = fieldset.querySelector("[data-live-feedback]");
        feedback.className = "quiz-inline-feedback " + (result.correct ? "quiz-inline-feedback-correct" : "quiz-inline-feedback-wrong");
        feedback.textContent = result.correct
            ? "Верно. " + result.explanation
            : "Неверно. Правильный ответ: " + result.correct_answer + ". " + result.explanation;
        feedback.hidden = false;
        fieldset.classList.toggle("quiz-question-correct", result.correct);
        fieldset.classList.toggle("quiz-question-wrong", !result.correct);
    }

    function buildExtraQuestion(question) {
        const fieldset = document.createElement("fieldset");
        fieldset.className = "quiz-question quiz-question-" + question.answer_type;
        fieldset.dataset.liveQuestion = "";
        fieldset.dataset.questionIndex = String(question.live_index);
        fieldset.dataset.questionStage = "extra";

        const legend = document.createElement("legend");
        const number = document.createElement("span");
        number.textContent = "+" + (question.live_index + 1);
        number.className = "quiz-question-number";
        const promptCopy = document.createElement("span");
        promptCopy.className = "quiz-question-copy";
        promptCopy.textContent = question.prompt;
        legend.append(number, promptCopy);
        if (question.prompt_speech) {
            legend.appendChild(buildPronounceButton(question.prompt_speech));
        }
        fieldset.appendChild(legend);

        if (question.answer_hint) {
            const hint = document.createElement("p");
            hint.className = "quiz-answer-hint";
            hint.textContent = question.answer_hint;
            fieldset.appendChild(hint);
        }
        if (question.answer_type === "text") {
            const label = document.createElement("label");
            label.className = "quiz-text-answer";
            const caption = document.createElement("span");
            caption.textContent = "Ваш ответ";
            const input = document.createElement("input");
            input.type = "text";
            input.required = true;
            input.maxLength = 300;
            input.autocomplete = "off";
            input.placeholder = "Введите ответ самостоятельно";
            label.append(caption, input);
            fieldset.appendChild(label);
        } else {
            const options = document.createElement("div");
            options.className = "quiz-options";
            question.options.forEach(function (value, index) {
                const row = document.createElement("div");
                row.className = "quiz-option-row";
                const label = document.createElement("label");
                label.className = "quiz-option";
                const input = document.createElement("input");
                input.type = question.answer_type === "multiple" ? "checkbox" : "radio";
                input.name = "live_extra_" + question.live_index;
                input.value = String(index);
                const text = document.createElement("span");
                text.textContent = value;
                label.append(input, text);
                row.appendChild(label);
                if (question.option_speech && question.option_speech[index]) {
                    row.appendChild(buildPronounceButton(question.option_speech[index]));
                }
                options.appendChild(row);
            });
            fieldset.appendChild(options);
        }
        const answerButton = document.createElement("button");
        answerButton.type = "button";
        answerButton.className = "btn quiz-answer-button";
        answerButton.dataset.answerQuestion = "";
        answerButton.textContent = "Ответить";
        fieldset.appendChild(answerButton);
        const feedback = document.createElement("div");
        feedback.className = "quiz-inline-feedback";
        feedback.dataset.liveFeedback = "";
        feedback.setAttribute("role", "status");
        feedback.setAttribute("aria-live", "polite");
        feedback.hidden = true;
        fieldset.appendChild(feedback);
        return fieldset;
    }

    function buildPronounceButton(text) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "course-pronounce-button quiz-pronounce-button";
        button.dataset.coursePronounce = "";
        button.dataset.pronounceText = text;
        button.dataset.pronounceLang = "en-US";
        button.setAttribute("aria-label", "Прослушать: " + text);
        button.title = "Прослушать английский текст";
        const icon = document.createElement("span");
        icon.className = "course-audio-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = "🔊";
        button.appendChild(icon);
        return button;
    }

    function addQuestions(questions) {
        if (!questions.length) return;
        questions.forEach(function (question) {
            form.insertBefore(buildExtraQuestion(question), submitButton);
        });
    }

    function restoreAnswer(fieldset, result) {
        const inputs = Array.from(fieldset.querySelectorAll("input"));
        if (Array.isArray(result.answer)) {
            const selected = new Set(result.answer.map(String));
            inputs.forEach(function (input) { input.checked = selected.has(input.value); });
        } else {
            const answer = String(result.answer == null ? "" : result.answer);
            const textInput = inputs.find(function (input) { return input.type === "text"; });
            if (textInput) {
                textInput.value = answer;
            } else {
                inputs.forEach(function (input) { input.checked = input.value === answer; });
            }
        }
        lockQuestion(fieldset);
        showFeedback(fieldset, result);
    }

    function restoreAnswerGroup(stage, answers) {
        Object.keys(answers || {}).forEach(function (index) {
            const selector = '[data-live-question][data-question-stage="' + stage + '"][data-question-index="' + index + '"]';
            const fieldset = form.querySelector(selector);
            if (fieldset) restoreAnswer(fieldset, answers[index]);
        });
    }

    async function restoreAttempt() {
        const url = new URL(form.dataset.stateUrl, window.location.origin);
        url.searchParams.set("course", form.dataset.course);
        url.searchParams.set("item_number", form.dataset.itemNumber);
        url.searchParams.set("seed", form.dataset.quizSeed);
        try {
            const response = await fetch(url.toString(), {credentials: "same-origin", cache: "no-store"});
            if (!response.ok) return;
            const state = await response.json();
            addQuestions(state.extra_questions || []);
            restoreAnswerGroup("base", state.base_answers);
            restoreAnswerGroup("extra", state.extra_answers);
            if (state.complete) enableContinuation(state);
            form.dispatchEvent(new CustomEvent("livequiz:restored", {
                bubbles: true,
                detail: {
                    hasAnswers: Object.keys(state.base_answers || {}).length > 0
                        || Object.keys(state.extra_answers || {}).length > 0
                }
            }));
        } catch (_error) {
            // The unanswered form remains usable if restoring temporary state fails.
        } finally {
            form.querySelectorAll("[data-live-question]:not([data-answered='true']) input").forEach(function (input) {
                input.disabled = false;
            });
            form.querySelectorAll("[data-live-question]:not([data-answered='true']) [data-answer-question]").forEach(function (button) {
                button.disabled = false;
            });
        }
    }

    function enableContinuation(result) {
        submitButton.disabled = false;
        submitButton.textContent = result.continue_label;
        submitButton.dataset.continueUrl = result.continue_url;
        submitButton.classList.toggle("btn-danger", !result.passed);
        submitButton.scrollIntoView({behavior: "smooth", block: "nearest"});
    }

    // Keep answer writes ordered so every request sees the previous persisted state.
    let answerQueue = Promise.resolve();

    function enqueueQuestion(fieldset) {
        if (!fieldset || fieldset.dataset.answered === "true" || fieldset.dataset.queued === "true") return;
        fieldset.dataset.queued = "true";
        const answerButton = fieldset.querySelector("[data-answer-question]");
        if (answerButton) answerButton.disabled = true;
        answerQueue = answerQueue
            .then(function () { return checkQuestion(fieldset); })
            .finally(function () {
                delete fieldset.dataset.queued;
                if (answerButton && fieldset.dataset.answered !== "true") answerButton.disabled = false;
            });
    }

    async function checkQuestion(fieldset) {
        if (fieldset.dataset.answered === "true" || fieldset.dataset.checking === "true") return;
        const inputs = Array.from(fieldset.querySelectorAll("input"));
        const textInput = inputs.find(function (input) { return input.type === "text"; });
        let answer;
        if (textInput) {
            answer = textInput.value.trim();
            if (!answer) {
                showInputPrompt(fieldset, "Сначала введите ответ.");
                return;
            }
        } else {
            const checked = inputs.filter(function (input) { return input.checked; });
            const isMultiple = inputs.some(function (input) { return input.type === "checkbox"; });
            if (!checked.length) {
                showInputPrompt(fieldset, "Сначала выберите вариант ответа.");
                return;
            }
            if (isMultiple && checked.length !== 2) {
                showInputPrompt(fieldset, "Выберите ровно два варианта, затем нажмите «Ответить».");
                return;
            }
            answer = isMultiple ? checked.map(function (input) { return input.value; }) : checked[0].value;
        }
        fieldset.dataset.checking = "true";
        try {
            const response = await fetch(form.dataset.checkUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {"Content-Type": "application/json", "X-CSRFToken": csrfInput.value},
                body: JSON.stringify({
                    course: form.dataset.course,
                    item_number: Number(form.dataset.itemNumber),
                    seed: Number(form.dataset.quizSeed),
                    stage: fieldset.dataset.questionStage,
                    question_index: Number(fieldset.dataset.questionIndex),
                    answer: answer
                })
            });
            if (!response.ok) throw new Error("Не удалось проверить ответ.");
            const result = await response.json();
            lockQuestion(fieldset);
            showFeedback(fieldset, result);
            addQuestions(result.added_questions || []);
            if (result.complete) enableContinuation(result);
        } catch (_error) {
            delete fieldset.dataset.checking;
            submitButton.type = "submit";
            submitButton.disabled = false;
            submitButton.textContent = "Отправить ответы без мгновенной проверки";
            const feedback = fieldset.querySelector("[data-live-feedback]");
            feedback.className = "quiz-inline-feedback quiz-inline-feedback-wrong";
            feedback.textContent = "Мгновенная проверка недоступна. Можно отправить тест обычной кнопкой ниже.";
            feedback.hidden = false;
        }
    }

    function showInputPrompt(fieldset, message) {
        const feedback = fieldset.querySelector("[data-live-feedback]");
        feedback.className = "quiz-inline-feedback quiz-inline-feedback-prompt";
        feedback.textContent = message;
        feedback.hidden = false;
    }

    form.addEventListener("click", function (event) {
        const button = event.target.closest("[data-answer-question]");
        if (!button) return;
        enqueueQuestion(button.closest("[data-live-question]"));
    });
    submitButton.addEventListener("click", function () {
        if (submitButton.disabled || !submitButton.dataset.continueUrl) return;
        window.location.assign(submitButton.dataset.continueUrl);
    });
    restoreAttempt();
}());
