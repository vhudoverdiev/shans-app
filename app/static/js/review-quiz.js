(function () {
    "use strict";

    const form = document.querySelector("[data-review-quiz]");
    if (!form || !window.fetch) return;

    const csrf = form.querySelector('input[name="_csrf_token"]');
    const submit = form.querySelector(".quiz-submit");
    const questions = Array.from(form.querySelectorAll("[data-live-question]"));
    submit.disabled = true;
    submit.textContent = "Ответьте на все вопросы";

    function selectedAnswer(fieldset) {
        const inputs = Array.from(fieldset.querySelectorAll("input:not([type=hidden])"));
        const text = inputs.find(function (input) { return input.type === "text"; });
        if (text) return text.value.trim();
        const checked = inputs.filter(function (input) { return input.checked; });
        if (fieldset.classList.contains("quiz-question-multiple")) {
            return checked.map(function (input) { return input.value; });
        }
        return checked.length ? checked[0].value : "";
    }

    function lockAnswer(fieldset) {
        fieldset.querySelectorAll("input:not([type=hidden])").forEach(function (input) {
            if ((input.type === "text" && input.value.trim()) || input.checked) {
                const mirror = document.createElement("input");
                mirror.type = "hidden";
                mirror.name = input.name;
                mirror.value = input.value;
                fieldset.appendChild(mirror);
            }
            input.disabled = true;
        });
        fieldset.dataset.answered = "true";
        const button = fieldset.querySelector("[data-answer-question]");
        if (button) button.disabled = true;
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

    function updateSubmit() {
        const complete = questions.every(function (fieldset) { return fieldset.dataset.answered === "true"; });
        submit.disabled = !complete;
        submit.textContent = complete ? "Завершить тест" : "Ответьте на все вопросы";
    }

    form.addEventListener("click", async function (event) {
        const button = event.target.closest("[data-answer-question]");
        if (!button || !form.contains(button)) return;
        const fieldset = button.closest("[data-live-question]");
        const answer = selectedAnswer(fieldset);
        const empty = Array.isArray(answer) ? answer.length === 0 : answer === "";
        if (empty) {
            const feedback = fieldset.querySelector("[data-live-feedback]");
            feedback.className = "quiz-inline-feedback quiz-inline-feedback-wrong";
            feedback.textContent = "Сначала выберите или напишите ответ.";
            feedback.hidden = false;
            return;
        }
        button.disabled = true;
        try {
            const response = await fetch(form.dataset.checkUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {"Content-Type": "application/json", "X-CSRFToken": csrf.value},
                body: JSON.stringify({
                    course: form.dataset.course,
                    end_day: Number(form.dataset.endDay),
                    seed: Number(form.dataset.quizSeed),
                    question_index: Number(fieldset.dataset.questionIndex),
                    answer: answer
                })
            });
            if (!response.ok) throw new Error("check_failed");
            const result = await response.json();
            lockAnswer(fieldset);
            showFeedback(fieldset, result);
            updateSubmit();
        } catch (_error) {
            button.disabled = false;
            const feedback = fieldset.querySelector("[data-live-feedback]");
            feedback.className = "quiz-inline-feedback quiz-inline-feedback-wrong";
            feedback.textContent = "Не удалось проверить ответ. Повторите попытку.";
            feedback.hidden = false;
        }
    });
}());
