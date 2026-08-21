(function () {
    "use strict";

    const form = document.querySelector("[data-live-quiz]");
    if (!form || !window.fetch) return;

    const csrfInput = form.querySelector('input[name="_csrf_token"]');
    const submitButton = form.querySelector(".quiz-submit");
    const extraHeading = document.createElement("div");
    extraHeading.className = "quiz-live-extra-heading";
    extraHeading.innerHTML = "<strong>Дополнительное закрепление</strong><span>Новые вопросы появляются здесь сразу после ошибки.</span>";
    extraHeading.hidden = true;
    form.insertBefore(extraHeading, submitButton);
    submitButton.hidden = true;

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
        legend.append(number, document.createTextNode(question.prompt));
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
                const label = document.createElement("label");
                label.className = "quiz-option";
                const input = document.createElement("input");
                input.type = question.answer_type === "multiple" ? "checkbox" : "radio";
                input.name = "live_extra_" + question.live_index;
                input.value = String(index);
                const text = document.createElement("span");
                text.textContent = value;
                label.append(input, text);
                options.appendChild(label);
            });
            fieldset.appendChild(options);
        }
        const feedback = document.createElement("div");
        feedback.className = "quiz-inline-feedback";
        feedback.dataset.liveFeedback = "";
        feedback.setAttribute("role", "status");
        feedback.setAttribute("aria-live", "polite");
        feedback.hidden = true;
        fieldset.appendChild(feedback);
        return fieldset;
    }

    function addQuestions(questions) {
        if (!questions.length) return;
        extraHeading.hidden = false;
        questions.forEach(function (question) {
            form.insertBefore(buildExtraQuestion(question), submitButton);
        });
    }

    function showCompletion(result) {
        const resultBox = document.createElement("section");
        resultBox.className = "quiz-result " + (result.passed ? "quiz-result-passed" : "quiz-result-failed");
        resultBox.setAttribute("role", "status");
        resultBox.innerHTML = '<div class="quiz-result-score"></div><div><h2></h2><p></p></div>';
        resultBox.querySelector(".quiz-result-score").textContent = result.score + " / " + result.total;
        resultBox.querySelector("h2").textContent = result.passed ? "Тест пройден" : "Стоит повторить материал";
        resultBox.querySelector("p").textContent = result.passed
            ? "Результат сохранён автоматически."
            : "Для прохождения нужно минимум " + result.pass_score + " правильных ответов.";
        form.after(resultBox);
        resultBox.scrollIntoView({behavior: "smooth", block: "nearest"});
    }

    async function checkQuestion(fieldset) {
        if (fieldset.dataset.answered === "true" || fieldset.dataset.checking === "true") return;
        const inputs = Array.from(fieldset.querySelectorAll("input"));
        const textInput = inputs.find(function (input) { return input.type === "text"; });
        let answer;
        if (textInput) {
            answer = textInput.value.trim();
            if (!answer) return;
        } else {
            const checked = inputs.filter(function (input) { return input.checked; });
            const isMultiple = inputs.some(function (input) { return input.type === "checkbox"; });
            if (!checked.length || (isMultiple && checked.length !== 2)) return;
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
            if (result.complete) showCompletion(result);
        } catch (_error) {
            delete fieldset.dataset.checking;
            submitButton.hidden = false;
            const feedback = fieldset.querySelector("[data-live-feedback]");
            feedback.className = "quiz-inline-feedback quiz-inline-feedback-wrong";
            feedback.textContent = "Мгновенная проверка недоступна. Можно отправить тест обычной кнопкой ниже.";
            feedback.hidden = false;
        }
    }

    form.addEventListener("change", function (event) {
        const input = event.target.closest('input[type="radio"], input[type="checkbox"]');
        if (!input) return;
        checkQuestion(input.closest("[data-live-question]"));
    });
    form.addEventListener("focusout", function (event) {
        if (event.target.matches('input[type="text"]')) checkQuestion(event.target.closest("[data-live-question]"));
    });
    form.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && event.target.matches('input[type="text"]')) {
            event.preventDefault();
            checkQuestion(event.target.closest("[data-live-question]"));
        }
    });
}());
